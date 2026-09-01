import os
import re
import csv
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

CSV_FILE = "rates.csv"
TARGET_URL = "https://www.westernunion.com/de/en/currency-converter/eur-to-ars-rate.html"


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


def extract_rate():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US"
        )
        page = context.new_page()

        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        try:
            cookie_btn = page.locator("#onetrust-accept-btn-handler")
            if cookie_btn.is_visible(timeout=5000):
                cookie_btn.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        page.wait_for_timeout(4000)
        page_text = page.inner_text("body")

        rate_val = None
        patterns = [
            r"FX:\s*(?:\d[\d.,]*)\s*EUR\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
            r"(?:\d[\d.,]*)\s*EUR\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS",
            r"1\s*EUR\s*(?:[-–=]|to)\s*([\d.,]+)\s*ARS"
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                rate_val = parse_numeric_value(match.group(1))
                if rate_val is not None:
                    break

        if not rate_val:
            selectors = [
                "[data-testid='exchange-rate']",
                ".exchange-rate",
                "#exchangeRate",
                ".fx-rate"
            ]
            for selector in selectors:
                el = page.locator(selector).first
                if el.is_visible():
                    text = el.inner_text()
                    sub_match = re.search(r"([\d.,]+)", text)
                    if sub_match:
                        rate_val = parse_numeric_value(sub_match.group(1))
                        if rate_val is not None:
                            break

        browser.close()
        return rate_val


def record_rate(rate):
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp_utc", "send_currency", "receive_currency", "exchange_rate"])

        writer.writerow([now_utc, "EUR", "ARS", rate if rate is not None else "N/A"])
        print(f"Recorded: {now_utc} | EUR/ARS = {rate}")


if __name__ == "__main__":
    extracted_rate = extract_rate()
    if extracted_rate:
        print(f"Successfully scraped rate: {extracted_rate}")
        record_rate(extracted_rate)
    else:
        print("Warning: Could not isolate numeric rate. Logging failed attempt.")
        record_rate(None)
