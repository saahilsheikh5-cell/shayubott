import os
import telebot
import requests
import pandas as pd
import threading
import time
from telebot import types
from flask import Flask, request
import numpy as np

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q") 
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://shayubott.onrender.com/" + BOT_TOKEN)
CHAT_ID = int(os.getenv("CHAT_ID", "YOUR_CHAT_ID"))

# Binance API endpoints
ALL_COINS_URL = "https://api.binance.com/api/v3/ticker/24hr"
KLINES_URL = "https://api.binance.com/api/v3/klines"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)  # <-- This is the WSGI object Gunicorn uses

# ================= STORAGE =================
USER_COINS_FILE = "user_coins.txt"

def load_coins():
    if not os.path.exists(USER_COINS_FILE):
        return []
    with open(USER_COINS_FILE, "r") as f:
        return [line.strip() for line in f.readlines()]

def save_coins(coins):
    with open(USER_COINS_FILE, "w") as f:
        for c in coins:
            f.write(c + "\n")

# ================= TECHNICAL ANALYSIS =================
def get_klines(symbol, interval="15m", limit=100):
    url = f"{KLINES_URL}?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url, timeout=10).json()
    closes = [float(c[4]) for c in data]
    return closes

def rsi(data, period=14):
    delta = np.diff(data)
    gain = np.maximum(delta, 0)
    loss = -np.minimum(delta, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def generate_signal(symbol):
    try:
        closes = get_klines(symbol, "15m", 100)
        if len(closes) < 20:
            return None
        last_close = closes[-1]
        rsi_val = rsi(closes)[-1]

        if rsi_val < 25:
            return f"🟢 STRONG BUY {symbol} | RSI {rsi_val:.2f} | Price {last_close}"
        elif rsi_val > 75:
            return f"🔴 STRONG SELL {symbol} | RSI {rsi_val:.2f} | Price {last_close}"
        return None
    except Exception:
        return None

# ================= BACKGROUND SIGNALS =================
auto_signals_enabled = True

def signal_scanner():
    while True:
        if auto_signals_enabled:
            coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
            for c in coins:
                sig = generate_signal(c)
                if sig:
                    bot.send_message(CHAT_ID, f"⚡ {sig}")
        time.sleep(60)

threading.Thread(target=signal_scanner, daemon=True).start()

# ================= HANDLERS =================
@bot.message_handler(commands=["start"])
def start(msg):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 My Coins", "➕ Add Coin")
    markup.add("➖ Remove Coin", "🚀 Top Movers")
    markup.add("🤖 Auto Signals", "🛑 Stop Signals")
    markup.add("🔄 Reset Settings", "📡 Signals")
    bot.send_message(msg.chat.id, "🤖 Welcome! Choose an option:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📊 My Coins")
def my_coins(msg):
    coins = load_coins()
    if not coins:
        bot.send_message(msg.chat.id, "⚠️ No coins saved. Use ➕ Add Coin.")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for coin in coins:
        markup.add(coin)
    bot.send_message(msg.chat.id, "📊 Select a coin:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Add Coin")
def add_coin(msg):
    bot.send_message(msg.chat.id, "Type coin symbol (e.g., BTCUSDT):")
    bot.register_next_step_handler(msg, process_add_coin)

def process_add_coin(msg):
    coin = msg.text.upper()
    coins = load_coins()
    if coin not in coins:
        coins.append(coin)
        save_coins(coins)
        bot.send_message(msg.chat.id, f"✅ {coin} added.")
    else:
        bot.send_message(msg.chat.id, f"{coin} already exists.")

@bot.message_handler(func=lambda m: m.text == "➖ Remove Coin")
def remove_coin(msg):
    coins = load_coins()
    if not coins:
        bot.send_message(msg.chat.id, "⚠️ No coins to remove.")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for coin in coins:
        markup.add(coin)
    bot.send_message(msg.chat.id, "Select coin to remove:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_remove_coin)

def process_remove_coin(msg):
    coin = msg.text.upper()
    coins = load_coins()
    if coin in coins:
        coins.remove(coin)
        save_coins(coins)
        bot.send_message(msg.chat.id, f"❌ {coin} removed.")
    else:
        bot.send_message(msg.chat.id, "Coin not found.")

@bot.message_handler(func=lambda m: m.text == "🚀 Top Movers")
def top_movers(msg):
    data = requests.get(ALL_COINS_URL, timeout=10).json()
    df = pd.DataFrame(data)
    df["priceChangePercent"] = df["priceChangePercent"].astype(float)
    top = df.sort_values("priceChangePercent", ascending=False).head(5)
    movers = "\n".join([f"🪙 {row['symbol']} : {row['priceChangePercent']}%" for _, row in top.iterrows()])
    bot.send_message(msg.chat.id, f"🚀 Top 5 Movers (24h):\n\n{movers}")

@bot.message_handler(func=lambda m: m.text == "🤖 Auto Signals")
def enable_signals(msg):
    global auto_signals_enabled
    auto_signals_enabled = True
    bot.send_message(msg.chat.id, "✅ Auto signals ENABLED.")

@bot.message_handler(func=lambda m: m.text == "🛑 Stop Signals")
def stop_signals(msg):
    global auto_signals_enabled
    auto_signals_enabled = False
    bot.send_message(msg.chat.id, "⛔ Auto signals DISABLED.")

@bot.message_handler(func=lambda m: m.text == "🔄 Reset Settings")
def reset_settings(msg):
    save_coins([])
    bot.send_message(msg.chat.id, "🔄 Settings reset. All coins cleared.")

@bot.message_handler(commands=["signals"])
@bot.message_handler(func=lambda m: m.text == "📡 Signals")
def signals(msg):
    coins = load_coins()
    if not coins:
        coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    strong_signals = []
    for c in coins:
        sig = generate_signal(c)
        if sig:
            strong_signals.append(sig)
    if not strong_signals:
        bot.send_message(msg.chat.id, "⚡ No strong signals right now.")
    else:
        bot.send_message(msg.chat.id, "📡 Ultra-Filtered Signals:\n\n" + "\n".join(strong_signals))

# ================= FLASK WEBHOOK =================
@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot running!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    # DO NOT call app.run() when using Gunicorn

