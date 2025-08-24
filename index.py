import os
import json
import telebot
import requests
import pandas as pd
import numpy as np
import time
import threading
from flask import Flask, request
from telebot import types

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://shayubott.onrender.com/" + BOT_TOKEN)
CHAT_ID = int(os.getenv("CHAT_ID", "1263295916"))
BINANCE_URL = "https://api.binance.com/api/v3/klines"
ALL_COINS_URL = "https://api.binance.com/api/v3/ticker/24hr"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === STORAGE ===
COINS_FILE = "coins.json"
auto_signal_thread = None
signal_settings = {
    "rsi_strong_buy": 20,
    "rsi_strong_sell": 80,
    "signal_validity": 300,
    "max_signals_per_scan": 5
}

# === HELPERS ===
def load_coins():
    if not os.path.exists(COINS_FILE):
        with open(COINS_FILE, "w") as f: json.dump([], f)
    with open(COINS_FILE, "r") as f:
        return json.load(f)

def save_coins(coins):
    with open(COINS_FILE, "w") as f: json.dump(coins, f)

def get_coin_name(symbol):
    for q in ["USDT","BTC","BNB","ETH","EUR","BRL","GBP"]:
        if symbol.endswith(q): return symbol.replace(q,"")
    return symbol

def get_klines(symbol, interval="1m", limit=100):
    try:
        url = f"{BINANCE_URL}?symbol={symbol}&interval={interval}&limit={limit}"
        data = requests.get(url, timeout=10).json()
        df = pd.DataFrame(data, columns=[
            "time","o","h","l","c","v","ct","qv","tn","tb","qtb","ignore"
        ])
        df["c"] = df["c"].astype(float)
        return df
    except:
        return None

def get_rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta>0, delta, 0)
    loss = np.where(delta<0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100/(1+rs))

# === ANALYSIS ===
def analyze_coin(symbol, interval="1m", strong_only=False):
    df = get_klines(symbol, interval, 100)
    if df is None or df.empty: return None
    close = df["c"]; price = close.iloc[-1]; rsi = get_rsi(close).iloc[-1]

    if strong_only:
        if rsi < signal_settings["rsi_strong_buy"]:
            signal, emoji = "Strong Buy", "🔺🟢"
        elif rsi > signal_settings["rsi_strong_sell"]:
            signal, emoji = "Strong Sell", "🔻🔴"
        else: return None
    else:
        if rsi < 30: signal, emoji = "Buy", "🟢"
        elif rsi > 70: signal, emoji = "Sell", "🔴"
        else: signal, emoji = "Neutral", "⚪"

    sl = round(price * (0.97 if "Buy" in signal else 1.03),5)
    tp = round(price * (1.03 if "Buy" in signal else 0.97),5)
    validity = f"{int(signal_settings['signal_validity']/60)}m"

    return {
        "symbol": get_coin_name(symbol),
        "price": round(price,5),
        "signal": signal,
        "emoji": emoji,
        "stop_loss": sl,
        "take_profit": tp,
        "validity": validity
    }

def get_all_coins():
    data = requests.get(ALL_COINS_URL, timeout=10).json()
    return [d["symbol"] for d in data]

# === AUTO SIGNALS ===
def run_auto_signals():
    last_signals = {}
    while True:
        try:
            coins = get_all_coins()
            sent = 0
            for sym in coins:
                res = analyze_coin(sym, strong_only=True)
                if res:
                    key = f"{res['symbol']}_{res['signal']}"
                    if key not in last_signals:
                        txt = f"🪙 {res['symbol']} | ${res['price']}\n{res['emoji']} {res['signal']}\nSL: {res['stop_loss']} | TP: {res['take_profit']}\nValid: {res['validity']}"
                        bot.send_message(CHAT_ID, txt)
                        last_signals[key] = time.time()
                        sent += 1
                        if sent >= signal_settings["max_signals_per_scan"]: break
            now = time.time()
            last_signals = {k:v for k,v in last_signals.items() if now-v < signal_settings["signal_validity"]}
            time.sleep(60)
        except Exception as e:
            print("Signal loop error:", e)
            time.sleep(60)

def start_auto_signal_thread():
    global auto_signal_thread
    if auto_signal_thread is None or not auto_signal_thread.is_alive():
        auto_signal_thread = threading.Thread(target=run_auto_signals, daemon=True)
        auto_signal_thread.start()

# === INLINE MENUS ===
def main_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📊 My Coins", callback_data="mycoins"))
    kb.add(types.InlineKeyboardButton("➕ Add Coin", callback_data="addcoin"))
    kb.add(types.InlineKeyboardButton("➖ Remove Coin", callback_data="removecoin"))
    kb.add(types.InlineKeyboardButton("📈 Technical Analysis", callback_data="analyse"))
    kb.add(types.InlineKeyboardButton("🚀 Movers", callback_data="movers"))
    kb.add(types.InlineKeyboardButton("⚡ Signals", callback_data="signals"))
    return kb

def timeframe_menu(symbol):
    kb = types.InlineKeyboardMarkup()
    for tf in ["1m","5m","15m","1h","4h","1d"]:
        kb.add(types.InlineKeyboardButton(tf, callback_data=f"ta:{symbol}:{tf}"))
    return kb

# === HANDLERS ===
@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(msg.chat.id, "Welcome to SaahilCryptoBot 🚀", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data=="mycoins":
        coins = load_coins()
        if not coins:
            bot.answer_callback_query(call.id,"No coins saved!")
            return
        kb = types.InlineKeyboardMarkup()
        for c in coins:
            kb.add(types.InlineKeyboardButton(c, callback_data=f"coin:{c}"))
        bot.send_message(call.message.chat.id,"📊 Your Coins:",reply_markup=kb)

    elif call.data.startswith("coin:"):
        sym = call.data.split(":")[1]
        bot.send_message(call.message.chat.id, f"Select timeframe for {sym}", reply_markup=timeframe_menu(sym))

    elif call.data.startswith("ta:"):
        _, sym, tf = call.data.split(":")
        res = analyze_coin(sym, interval=tf)
        if res:
            txt = f"🪙 {res['symbol']} ({tf}) | ${res['price']}\n{res['emoji']} {res['signal']}\nSL: {res['stop_loss']} | TP: {res['take_profit']}\nValid: {res['validity']}"
            bot.send_message(call.message.chat.id, txt)
        else:
            bot.send_message(call.message.chat.id, f"⚠ Could not analyze {sym} {tf}")

    elif call.data=="addcoin":
        msg = bot.send_message(call.message.chat.id,"Type coin symbol (e.g. BTCUSDT):")
        bot.register_next_step_handler(msg, add_coin)

    elif call.data=="removecoin":
        coins = load_coins()
        if not coins:
            bot.send_message(call.message.chat.id,"No coins saved.")
            return
        kb = types.InlineKeyboardMarkup()
        for c in coins:
            kb.add(types.InlineKeyboardButton(f"❌ {c}", callback_data=f"del:{c}"))
        bot.send_message(call.message.chat.id,"Select coin to remove:", reply_markup=kb)

    elif call.data.startswith("del:"):
        sym = call.data.split(":")[1]
        coins = load_coins()
        if sym in coins:
            coins.remove(sym); save_coins(coins)
            bot.send_message(call.message.chat.id,f"✅ Removed {sym}")
        else:
            bot.send_message(call.message.chat.id,f"{sym} not found")

    elif call.data=="analyse":
        msg = bot.send_message(call.message.chat.id,"Send coin symbol (e.g. ETHUSDT):")
        bot.register_next_step_handler(msg, analyse_coin_input)

    elif call.data=="movers":
        data = requests.get(ALL_COINS_URL).json()
        df = pd.DataFrame(data)
        df["priceChangePercent"] = df["priceChangePercent"].astype(float)
        top = df.nlargest(3,"priceChangePercent")[["symbol","priceChangePercent"]]
        worst = df.nsmallest(3,"priceChangePercent")[["symbol","priceChangePercent"]]
        text = "🚀 Top Movers (24h):\n\n"
        text += "Top Gainers:\n" + "\n".join([f"{r.symbol}: {r.priceChangePercent}%" for r in top.itertuples()]) + "\n\n"
        text += "Top Losers:\n" + "\n".join([f"{r.symbol}: {r.priceChangePercent}%" for r in worst.itertuples()])
        bot.send_message(call.message.chat.id,text)

    elif call.data=="signals":
        coins = get_all_coins()
        shown = 0
        for sym in coins:
            res = analyze_coin(sym,strong_only=True)
            if res:
                txt = f"🪙 {res['symbol']} | ${res['price']}\n{res['emoji']} {res['signal']}\nSL: {res['stop_loss']} | TP: {res['take_profit']}\nValid: {res['validity']}"
                bot.send_message(call.message.chat.id, txt)
                shown+=1
                if shown>=signal_settings["max_signals_per_scan"]: break

def add_coin(msg):
    sym = msg.text.upper()
    coins = load_coins()
    if sym not in coins:
        coins.append(sym); save_coins(coins)
        bot.send_message(msg.chat.id,f"✅ Added {sym}")
    else:
        bot.send_message(msg.chat.id,"Already saved.")

def analyse_coin_input(msg):
    sym = msg.text.upper()
    bot.send_message(msg.chat.id,f"Select timeframe for {sym}",reply_markup=timeframe_menu(sym))

# === WEBHOOK ===
@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!",200

@app.route("/")
def index():
    return "Bot running!"

# === RUN ===
if __name__=="__main__":
    start_auto_signal_thread()
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))

