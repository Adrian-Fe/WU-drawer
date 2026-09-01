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

def get_interbank_rate(currency):
    try:
        ticker = yf.Ticker(f"{currency}ARS=X")
        # Holt den aktuellsten Börsenkurs
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
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for currency, url in TARGETS.items():
            print(f"Lade {currency}...")
            wu_rate = None
            ib_rate = get_interbank_rate(currency)
            
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(3000)

                page_text = page.inner_text("body")
                match = re.search(rf"1\s*{currency}\s*=\s*([\d\.,]+)\s*ARS", page_text, re.IGNORECASE)
                
                if match:
                    raw_str = match.group(1).replace(".", "").replace(",", ".") if "," in match.group(1) and "." in match.group(1) else match.group(1).replace(",", "")
                    wu_rate = float(raw_str)
                else:
                    # Fallback Selector
                    selectors = ["[data-testid='exchange-rate']", ".exchange-rate", "#exchangeRate"]
                    for selector in selectors:
                        el = page.locator(selector).first
                        if el.is_visible():
                            sub_match = re.search(r"([\d\.,]+)", el.inner_text())
                            if sub_match:
                                wu_rate = float(sub_match.group(1).replace(",", ""))
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
            # Neue Struktur mit interbank_rate Spalte
            writer.writerow(["timestamp_utc", "send_currency", "receive_currency", "exchange_rate", "interbank_rate"])
        
        for currency, rates in rates_dict.items():
            wu = rates["wu"] if rates["wu"] else "N/A"
            ib = rates["ib"] if rates["ib"] else "N/A"
            writer.writerow([now_utc, currency, "ARS", wu, ib])
            print(f"Gespeichert: {currency}/ARS | WU: {wu} | Interbank: {ib}")

if __name__ == "__main__":
    extracted = extract_rates()
    record_rates(extracted)