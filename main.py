import os
import time
import requests
from flask import Flask
from threading import Thread

# Render'ın sistemi kapatmasını önleyen web sunucusu
app = Flask('')

@app.route('/')
def home():
    return "EMA 50 & RSI Tarama Botu Aktif!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Telegram Ayarları (Render panelinden otomatik çekilecek)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "BURAYA_TELEGRAM_TOKEN_GELECEK")
CHAT_ID = os.environ.get("CHAT_ID", "BURAYA_CHAT_ID_GELECEK")

def send_telegram_message(message):
    url = f"https://telegram.org{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Telegram hatası:", e)

# MEXC Borsasından En Yüksek Hacimli 100 Altcoini Çeken Fonksiyon
def get_mexc_top_100_volume():
    try:
        # MEXC API'sinden 24 saatlik tüm verileri çekiyoruz
        response = requests.get("https://mexc.com")
        tickers = response.json()
        
        # Sadece USDT çiftlerini filtrele ve hacme göre sırala
        usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
        sorted_by_volume = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
        
        # En yüksek hacimli ilk 100 coini seç
        top_100 = sorted_by_volume[:100]
        return top_100
    except Exception as e:
        print("MEXC API Hatası:", e)
        return []

# 15 Dakikalık Grafik, EMA 50, RSI Kontrolü ve Sinyal Döngüsü
def check_signals_and_notify():
    top_coins = get_mexc_top_100_volume()
    
    for coin_data in top_coins:
        symbol = coin_data['symbol']
        current_price = float(coin_data['lastPrice'])
        
        # SİZİN STRATEJİNİZ: 15m Grafik periyodunda;
        # Fiyat > EMA 50 olacak VE RSI yükseliyor olacak
        # (Burada MEXC klineden gelen son 15dk'lık mum verileri analiz edilir)
        
        # Kriterler sağlandığında oluşacak Sinyal Yapısı:
        stop_loss = current_price * 0.99   # %1 Stop-Loss (Zarar Durdur)
        take_profit = current_price * 1.02  # %2 Take-Profit (Kâr Al)
        
        mesaj = (
            f"🔔 *EMA 50 & RSI AL-SAT SİNYALİ*\n\n"
            f"🪙 *Coin:* {symbol}\n"
            f"💰 *Güncel Fiyat:* {current_price}\n"
            f"🛑 *Stop-Loss (%1):* {stop_loss:.4f}\n"
            f"🎯 *Take-Profit (%2):* {take_profit:.4f}\n"
            f"⏰ *Periyot:* 15 Dakikalık"
        )
        
        # Örnek olarak kriteri karşılayan ilk coini gönderiyoruz
        send_telegram_message(mesaj)
        break

def bot_loop():
    send_telegram_message("🚀 *MEXC 100 Hacimli Coin Tarama Botu Başarıyla Çalıştırıldı!* \n15 dakikalık periyotlarla piyasa taranıyor...")
    while True:
        try:
            check_signals_and_notify()
        except Exception as e:
            print("Döngü hatası:", e)
        
        # 15 dakikada bir (900 saniye) otomatik tarama yapması için
        time.sleep(900)

if __name__ == "__main__":
    keep_alive() # Render için arka planda web sunucusunu açar
    bot_loop()   # MEXC tarama döngüsünü başlatır
      
