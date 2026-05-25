import requests
from datetime import datetime

def get_last_10_1m_bars():
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=10"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if not isinstance(data, list):
            print("Błąd API:", data)
            return []
        bars = []
        for bar in data:
            open_time = datetime.fromtimestamp(bar[0] / 1000).strftime('%H:%M')
            o = float(bar[1])
            h = float(bar[2])
            l = float(bar[3])
            c = float(bar[4])
            v = float(bar[5])
            color = "green" if c > o else "red"
            bars.append({"time": open_time, "open": o, "close": c, "volume": v, "color": color})
        return bars
    except Exception as e:
        print("Błąd pobierania:", e)
        return []

def check_volume_pattern(bars):
    if len(bars) < 2:
        return "Za mało danych do analizy."
    for i in range(1, len(bars)):
        curr = bars[i]
        prev = bars[i-1]
        if curr["color"] != prev["color"]:
            # Znajdź ostatni bar o tym samym kolorze co curr przed tym barem
            last_same_color_vol = 0
            for j in range(i-1, -1, -1):
                if bars[j]["color"] == curr["color"]:
                    last_same_color_vol = bars[j]["volume"]
                    break
            if curr["volume"] > last_same_color_vol:
                return f"WZORZEC WYKRYTY! Bar {curr['time']}: kolor {curr['color']}, volume {curr['volume']:.2f} > poprzedni {last_same_color_vol:.2f}"
    return "Brak wzorca w ostatnich 10 barach 1m."

# === URUCHOMIENIE ===
print("=== BTC 1m Volume Pattern Checker ===")
bars = get_last_10_1m_bars()
if bars:
    print("Ostatnie 10 barów 1m (najnowszy na końcu):")
    for b in bars:
        print(f"{b['time']} | {b['color']:6} | vol: {b['volume']:.2f}")
    print()
    result = check_volume_pattern(bars)
    print(result)
else:
    print("Nie udało się pobrać danych.")