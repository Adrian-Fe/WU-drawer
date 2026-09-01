import yfinance as yf
from datetime import timedelta

print("Lade historische Daten...")
ticker = yf.Ticker("EURARS=X")
# Hole die letzten 90 Tage
hist = ticker.history(period="90d")

# CSV Zeilen generieren
csv_lines = []
for index, row in hist.iterrows():
    # Mittagszeit UTC als Standard annehmen
    date_str = index.strftime("%Y-%m-%d 12:00:00 UTC")
    # Interbankenkurs + 6% WU Marge
    wu_rate = round(row['Close'] * 1.06, 4)
    csv_lines.append(f"{date_str},EUR,ARS,{wu_rate}")

# In eine Datei schreiben
with open("history.csv", "w") as f:
    for line in csv_lines:
        f.write(line + "\n")

print("Erfolgreich in history.csv gespeichert! Du kannst den Inhalt nun oben in deine rates.csv kopieren.")