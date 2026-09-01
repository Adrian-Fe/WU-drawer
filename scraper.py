import os
import re
import csv
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
import yfinance as yf

CSV_FILE = "rates.csv"

TARGETS = {
    "EUR": "https://www.westernunion.com/de/en/currency-converter/eur-to-ars-rate.html",
    "USD": "https://www.westernunion.com/us/en/currency-converter/usd-to-ars-rate.html",
    "GBP": "https://www.westernunion.com/gb/en/currency-converter/gbp-to-ars-rate.html",
    "CAD": "https://www.westernunion.com/ca/en/currency-converter/cad-to-ars-rate.html"
}


def parse_numeric_value(raw_value):
    value = raw_value.strip().replace(" ", "")
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


def get_interbank_rate(currency):
    try:
        ticker = yf.Ticker(f"{currency}ARS=X")
        return round(ticker.history(period="1d")['Close'].iloc[-1], 2)
    except Exception as e:
        print(f"Interbank-Fehler bei {currency}: {e}")
        return None


def extract_rates():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US"
        )
        page = context.new_page()

        for currency, url in TARGETS.items():
            print(f"Lade {currency}...")
            wu_rate = None
            ib_rate = get_interbank_rate(currency)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)

                page_text = page.inner_text("body")
                patterns = [
                    rf"FX:\s*(?:\d[\d.,]*)\s*{currency}\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
                    rf"(?:\d[\d.,]*)\s*{currency}\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
                    rf"1\s*{currency}\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
                    rf"{currency}\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS"
                ]

                for pattern in patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        wu_rate = parse_numeric_value(match.group(1))
                        if wu_rate is not None:
                            break

                if wu_rate is None:
                    selectors = [
                        "[data-testid='exchange-rate']",
                        ".exchange-rate",
                        "#exchangeRate",
                        ".fx-rate",
                        "[data-testid='rate-value']",
                        ".rate-value"
                    ]
                    for selector in selectors:
                        el = page.locator(selector).first
                        if el.is_visible():
                            text = el.inner_text()
                            sub_match = re.search(r"([\d.,]+)", text)
                            if sub_match:
                                wu_rate = parse_numeric_value(sub_match.group(1))
                                if wu_rate is not None:
                                    break
            except Exception as e:
                print(f"WU-Fehler bei {currency}: {e}")

            results[currency] = {"wu": wu_rate, "ib": ib_rate}

        browser.close()
        return results


def record_rates(rates_dict):
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp_utc", "send_currency", "receive_currency", "exchange_rate", "interbank_rate"])

        for currency, rates in rates_dict.items():
            wu = rates["wu"] if rates["wu"] else "N/A"
            ib = rates["ib"] if rates["ib"] else "N/A"
            writer.writerow([now_utc, currency, "ARS", wu, ib])
            print(f"Gespeichert: {currency}/ARS | WU: {wu} | Interbank: {ib}")


if __name__ == "__main__":
    extracted = extract_rates()
    record_rates(extracted)