import os
import sys
import time
import requests
import pandas as pd
import schedule
from flask import Flask
from threading import Thread

# ============================================================
# BULUT SUNUCULARI İÇİN WEB SUNUCUSU (KEEP ALIVE)
# ============================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Aktif ve Çalışıyor!"

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ============================================================
# TELEGRAM BİLGİLERİ
# ============================================================
TELEGRAM_BOT_TOKEN = "8121274228:AAGbrZJcigwTvQDAjnomC73Drv0rpGUnDhc"
TELEGRAM_CHAT_ID = "1130184561"

TIMEFRAME = "30m"
TOP_COIN_COUNT = 50
EXCLUDED_BASES = {"USDT", "USDC", "USDE", "USD1", "USDD", "DAI", "TUSD", "FDUSD", "BUSD"}

def send_telegram_message(message):
    url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    max_length = 4000
    for i in range(0, len(message), max_length):
        chunk = message[i:i + max_length]
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"}
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code != 200:
                print(f"Telegram Hatası: {response.text}")
        except Exception as e:
            print(f"Telegram bağlantı hatası: {e}")

# ============================================================
# MEXC API - EN YÜKSEK HACİMLİ 50 USDT ÇİFTİ
# ============================================================
def get_top_50_volume_mexc_pairs():
    print("\nMEXC hacim listesi alınıyor...")
    url = "https://mexc.com"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return []
        
        tickers = response.json()
        usdt_pairs = []
        
        for ticker in tickers:
            symbol = ticker.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
                
            base = symbol[:-4]
            if base in EXCLUDED_BASES:
                continue
                
            if base.endswith("L") or base.endswith("S") or any(x in base for x in ["UP", "DOWN"]):
                continue
                
            try:
                quote_volume = float(ticker.get("quoteVolume", 0))
            except:
                continue
                
            if quote_volume <= 0:
                continue
                
            usdt_pairs.append({"symbol": symbol, "volume": quote_volume})
            
        usdt_pairs.sort(key=lambda x: x["volume"], reverse=True)
        return [item["symbol"] for item in usdt_pairs[:TOP_COIN_COUNT]]
    except Exception as e:
        print(f"MEXC hacim listesi hatası: {e}")
        return []

# ============================================================
# MEXC OHLCV VE ANALİZ
# ============================================================
def get_ohlcv(symbol, limit=100):
    url = "https://mexc.com"
    params = {"symbol": symbol, "interval": TIMEFRAME, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            return None
        data = response.json()
        rows = [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in data]
        return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    except Exception as e:
        return None

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))

def analyze_coin(symbol):
    try:
        df = get_ohlcv(symbol, 100)
        if df is None or len(df) < 60:
            return None

        df["EMA50"] = calculate_ema(df["close"], 50)
        df["RSI"] = calculate_rsi(df["close"], 14)

        last_row = df.iloc[-1]
        close = last_row["close"]
        ema50 = last_row["EMA50"]
        rsi = last_row["RSI"]

        signal = "NÖTR"
        if close > ema50 and rsi < 40:
            signal = "🟢 AL (EMA50 Üstü + Düşük RSI)"
        elif close < ema50 and rsi > 60:
            signal = "🔴 SAT (EMA50 Altı + Yüksek RSI)"

        return {
            "symbol": f"{symbol[:-4]}/{symbol[-4:]}",
            "close": close,
            "ema50": ema50,
            "rsi": rsi,
            "signal": signal
        }
    except:
        return None

def run_analysis_job():
    print(f"\nTarama başlatıldı... ({time.strftime('%H:%M:%S')})")
    symbols = get_top_50_volume_mexc_pairs()
    if not symbols:
        return

    active_signals = []
    for symbol in symbols:
        result = analyze_coin(symbol)
        if result and result["signal"] != "NÖTR":
            active_signals.append(result)
        time.sleep(0.1)

    if active_signals:
        message = "📊 *MEXC Teknik Analiz Raporu (30m)* 📊\n\n"
        for sig in active_signals:
            message += (
                f"🪙 *{sig['symbol']}*\n"
                f"💰 Fiyat: `{sig['close']}`\n"
                f"📈 EMA50: `{sig['ema50']:.4f}`\n"
                f"📉 RSI (14): `{sig['rsi']:.2f}`\n"
                f"🚨 Sinyal: *{sig['signal']}*\n"
                f"-------------------------\n"
            )
        send_telegram_message(message)

# ============================================================
# ANA ÇALIŞTIRICI
# ============================================================
if __name__ == "__main__":
    # 1. Arka planda web sunucusunu başlat (Bulut kapanmasın diye)
    server_thread = Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    # 2. İlk taramayı hemen yap
    run_analysis_job()

    # 3. Zamanlayıcıyı kur (30 dakikada bir)
    schedule.every(30).minutes.do(run_analysis_job)

    print("Bot ve Web Sunucusu aktif. Zamanlayıcı devrede...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(10)
            
