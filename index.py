import os
import telebot
import requests
import time
import threading
import numpy as np
import pandas as pd
from flask import Flask, request
from telebot import types

# === CONFIG ===
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shayubott.onrender.com/" + BOT_TOKEN
CHAT_ID = 1263295916

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === In-memory user settings ===
user_settings = {
    "timeframe": "15m",
    "rsi": 14,
    "limit": 5
}

# --- Utils ---
def get_filtered_signals(limit=5):
    # Fake placeholder signals (should be replaced with real API logic)
    signals = [
        {"coin": "BTCUSDT", "price": 65000, "signal": "Strong Buy"},
        {"coin": "ETHUSDT", "price": 3200, "signal": "Strong Sell"},
        {"coin": "BNBUSDT", "price": 540, "signal": "Strong Buy"},
        {"coin": "XRPUSDT", "price": 0.57, "signal": "Strong Sell"},
        {"coin": "ADAUSDT", "price": 0.48, "signal": "Strong Buy"},
    ]
    return signals[:limit]

# --- Commands ---
@bot.message_handler(commands=["start"])
def start_cmd(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Signals", "⚙️ Settings", "⛔ Stop Signals", "🔄 Reset Settings")
    bot.send_message(message.chat.id, "🤖 Welcome to SaahilCryptoBot!", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📊 Signals")
def signals_cmd(message):
    signals = get_filtered_signals(user_settings["limit"])
    text = "📊 Ultra-Filtered Signals\n\n"
    for s in signals:
        text += f"🪙 {s['coin']} | ${s['price']}\n{s['signal']}\n\n"
    text += f"⚙️ Current filters: Timeframe={user_settings['timeframe']}, RSI={user_settings['rsi']}, Limit={user_settings['limit']}"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "⚙️ Settings")
def settings_cmd(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("⏱ Change Timeframe", "📈 Change RSI", "🔢 Change Limit", "⬅️ Back")
    bot.send_message(message.chat.id, "⚙️ Adjust your filters:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⏱ Change Timeframe")
def change_timeframe(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("1m", "5m", "15m", "1h", "4h", "1d", "⬅️ Back")
    bot.send_message(message.chat.id, "⏱ Select timeframe:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["1m","5m","15m","1h","4h","1d"])
def set_timeframe(message):
    user_settings["timeframe"] = message.text
    bot.send_message(message.chat.id, f"✅ Timeframe set to {message.text}")

@bot.message_handler(func=lambda m: m.text == "📈 Change RSI")
def change_rsi(message):
    bot.send_message(message.chat.id, "Enter RSI value (e.g. 14):")

@bot.message_handler(func=lambda m: m.text.isdigit() and 2 <= int(m.text) <= 50)
def set_rsi(message):
    user_settings["rsi"] = int(message.text)
    bot.send_message(message.chat.id, f"✅ RSI set to {message.text}")

@bot.message_handler(func=lambda m: m.text == "🔢 Change Limit")
def change_limit(message):
    bot.send_message(message.chat.id, "Enter number of signals to show (1-10):")

@bot.message_handler(func=lambda m: m.text.isdigit() and 1 <= int(m.text) <= 10)
def set_limit(message):
    user_settings["limit"] = int(message.text)
    bot.send_message(message.chat.id, f"✅ Limit set to {message.text}")

@bot.message_handler(func=lambda m: m.text == "⛔ Stop Signals")
def stop_signals(message):
    bot.send_message(message.chat.id, "🛑 Auto-signals stopped.")

@bot.message_handler(func=lambda m: m.text == "🔄 Reset Settings")
def reset_settings(message):
    user_settings.update({"timeframe": "15m", "rsi": 14, "limit": 5})
    bot.send_message(message.chat.id, "♻️ Settings reset to default.")

# --- Flask webhook ---
@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    json_str = request.stream.read().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=port)
