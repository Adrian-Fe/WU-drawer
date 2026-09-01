import csv
import re
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
import yfinance as yf

CSV_FILE = "history.csv"
TARGETS = {
    "EUR": "https://www.westernunion.com/de/en/currency-converter/eur-to-ars-rate.html",
    "USD": "https://www.westernunion.com/us/en/currency-converter/usd-to-ars-rate.html",
    "GBP": "https://www.westernunion.com/gb/en/currency-converter/gbp-to-ars-rate.html",
    "CAD": "https://www.westernunion.com/ca/en/currency-converter/cad-to-ars-rate.html",
}


def parse_numeric_value(raw_value):
    value = str(raw_value or "").strip().replace(" ", "")
    if not value:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        if value.count(",") > 1:
            value = value.replace(",", "")
        else:
            integer_part, decimal_part = value.split(",", 1)
            if len(decimal_part) <= 2:
                value = f"{integer_part}.{decimal_part}"
            else:
                value = value.replace(",", "")

    try:
        return float(value)
    except ValueError:
        return None


def extract_wu_rate(html, currency):
    text = re.sub(r"<[^>]+>", " ", html)
    cur = currency.upper()
    patterns = [
        rf"FX:\s*(?:\d[\d.,]*)\s*{cur}\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
        rf"(?:\d[\d.,]*)\s*{cur}\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
        rf"1\s*{cur}\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
        rf"{cur}\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            rate = parse_numeric_value(match.group(1))
            if rate is not None:
                return rate
    return None


def archived_wu_rate(currency, target_url, date):
    date = date.date() if hasattr(date, "date") else date
    for offset in range(0, 3):
        check_date = date + timedelta(days=offset)
        timestamp = check_date.strftime("%Y%m%d")
        search_url = (
            "https://web.archive.org/cdx/search/cdx?url={}&from={}&to={}&output=json"
            "&filter=statuscode:200&filter=mimetype:text/html&collapse=digest"
        ).format(quote(target_url, safe=""), timestamp, timestamp)

        try:
            response = requests.get(search_url, timeout=20)
            response.raise_for_status()
            payload = response.json()
            if len(payload) < 2:
                continue

            for snapshot in payload[1:10]:
                archived_url = f"https://web.archive.org/web/{snapshot[1]}/{target_url}"
                try:
                    page = requests.get(archived_url, timeout=20)
                    page.raise_for_status()
                    rate = extract_wu_rate(page.text, currency)
                    if rate is not None:
                        return round(rate, 4), snapshot[1]
                except Exception:
                    continue
        except Exception:
            continue

    return None, None


def build_interbank_lookup(currency):
    ticker = yf.Ticker(f"{currency}ARS=X")
    hist = ticker.history(period="180d", interval="1d")
    lookup = {}
    for index, row in hist.iterrows():
        if "Close" not in row or row["Close"] is None:
            continue
        lookup[index.strftime("%Y-%m-%d")] = float(row["Close"])
    return lookup


def closest_interbank_rate(lookup, target_date):
    if not lookup:
        return None
    target_day = target_date.date() if hasattr(target_date, "date") else target_date
    for offset in range(0, 14):
        candidate = (target_day - timedelta(days=offset)).isoformat()
        if candidate in lookup:
            return round(lookup[candidate], 4)
    for offset in range(1, 14):
        candidate = (target_day + timedelta(days=offset)).isoformat()
        if candidate in lookup:
            return round(lookup[candidate], 4)
    return None


def make_history():
    start_date = datetime.utcnow().date() - timedelta(days=89)
    end_date = datetime.utcnow().date()
    lookup_map = {currency: build_interbank_lookup(currency) for currency in TARGETS}
    rows = []

    for currency, target_url in TARGETS.items():
        for offset in range((end_date - start_date).days + 1):
            current_date = start_date + timedelta(days=offset)
            date_obj = datetime.combine(current_date, datetime.min.time())
            wu_rate, snapshot = archived_wu_rate(currency, target_url, date_obj)
            ib_rate = closest_interbank_rate(lookup_map[currency], date_obj)
            rows.append({
                "timestamp_utc": date_obj.strftime("%Y-%m-%d 12:00:00 UTC"),
                "send_currency": currency,
                "receive_currency": "ARS",
                "exchange_rate": wu_rate if wu_rate is not None else "N/A",
                "interbank_rate": ib_rate if ib_rate is not None else "N/A",
                "wu_source": f"Wayback:{snapshot}" if snapshot else "N/A",
            })

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["timestamp_utc", "send_currency", "receive_currency", "exchange_rate", "interbank_rate", "wu_source"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Geschrieben: {len(rows)} Zeilen nach {CSV_FILE}")


if __name__ == "__main__":
    make_history()
