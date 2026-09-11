# ==============================================================================
# ⚡ 24/7 CLOUD-READY MULTI-THREADED TRADING BOT WITH FLASK WRAPPER
# ==============================================================================

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask

# ------------------------------------------------------------------------------
# 🌐 FLASK WEB SERVER FOR KEEP-ALIVE
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "🟢 Institutional AI Trading Bot is Active & Running 24/7 on Cloud!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------------------------
# ⚙️ BOT CONFIGURATION
# ------------------------------------------------------------------------------
TOKEN = "8554753865:AAEzsaFTVFBXT2xKv-bwrA4Mu_Csf0YzA2A"
BD_TIMEZONE = timezone(timedelta(hours=6))

conn = sqlite3.connect('institutional_ai_memory.db', check_same_thread=False)
cursor = conn.cursor()
db_lock = threading.Lock()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS trade_outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        asset TEXT,
        strategy_id TEXT,
        signal_type TEXT,
        entry_price REAL,
        exit_price REAL,
        win_rate_score REAL,
        result TEXT,
        analysis_reason TEXT
    )
''')
conn.commit()

ALL_FOREX_PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "USDCHF=X", "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X",
    "AUDJPY=X", "CADJPY=X", "EURAUD=X", "GBPAUD=X", "EURCHF=X"
]

def get_chat_id():
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        res = requests.get(url).json()
        if res.get("result") and len(res["result"]) > 0:
            return res["result"][-1]["message"]["chat"]["id"]
    except:
        pass
    return None

CHAT_ID = get_chat_id()

def send_telegram_msg(msg):
    if CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def log_trade_to_db(asset, strat_id, signal_type, entry_p, exit_p, score, result, reason):
    now_bd = datetime.now(BD_TIMEZONE).strftime('%Y-%m-%d %I:%M:%S %p')
    with db_lock:
        cursor.execute('''
            INSERT INTO trade_outcomes (timestamp, asset, strategy_id, signal_type, entry_price, exit_price, win_rate_score, result, analysis_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (now_bd, asset, strat_id, signal_type, entry_p, exit_p, score, result, reason))
        conn.commit()

def generate_performance_analytics():
    with db_lock:
        cursor.execute("SELECT strategy_id, result FROM trade_outcomes")
        rows = cursor.fetchall()
    
    if not rows: return "No trade memory recorded yet."

    total_trades = len(rows)
    wins = sum(1 for r in rows if r[1] == "WIN 🟢")
    losses = sum(1 for r in rows if r[1] == "LOSS 🔴")
    overall_win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0

    strat_stats = {}
    for strat_id, result in rows:
        if strat_id not in strat_stats: strat_stats[strat_id] = {"W": 0, "L": 0, "R": 0}
        if result == "WIN 🟢": strat_stats[strat_id]["W"] += 1
        elif result == "LOSS 🔴": strat_stats[strat_id]["L"] += 1
        else: strat_stats[strat_id]["R"] += 1

    strat_report = ""
    for st_id, counts in strat_stats.items():
        w, l = counts["W"], counts["L"]
        total = w + l
        wr = (w / total * 100) if total > 0 else 0.0
        strat_report += f"• *{st_id}:* `{wr:.1f}%` ({w}W / {l}L)\n"

    return (
        f"📈 *[DATABASE ANALYTICS REPORT]*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Total Trades:* `{total_trades}` | Win Rate: *{overall_win_rate:.1f}%* ({wins}W / {losses}L)\n\n"
        f"🏷️ *STRATEGY BREAKDOWN:*\n{strat_report}"
        f"━━━━━━━━━━━━━━━━━━━"
    )

def evaluate_trade_outcome_async(pair, strat_id, action_type, entry_price, confidence_score, primary_reason, wait_seconds):
    time.sleep(wait_seconds + 65)
    clean_pair = pair.replace("=X", "")
    exit_price = None

    for attempt in range(1, 4):
        try:
            df = yf.download(tickers=pair, period="1d", interval="1m", progress=False)
            if not df.empty and len(df) > 0:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                exit_price = float(df['Close'].iloc[-1])
                break
        except:
            pass
        time.sleep(5)

    if exit_price is None or exit_price == 0: exit_price = entry_price

    result = "REFUND ⚪"
    if "BUY" in action_type:
        if exit_price > entry_price: result = "WIN 🟢"
        elif exit_price < entry_price: result = "LOSS 🔴"
    elif "SELL" in action_type:
        if exit_price < entry_price: result = "WIN 🟢"
        elif exit_price > entry_price: result = "LOSS 🔴"

    log_trade_to_db(clean_pair, strat_id, action_type, entry_price, exit_price, confidence_score, result, primary_reason)
    analytics_report = generate_performance_analytics()
    send_telegram_msg(f"🎯 *Trade Outcome:* *{result}* on `{clean_pair}`\n\n{analytics_report}")

def compute_atr(df, length=14):
    tr = pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift(1)).abs(), (df['Low'] - df['Close'].shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(length).mean()

def compute_adx(df, length=14):
    up_move, down_move = df['High'] - df['High'].shift(1), df['Low'].shift(1) - df['Low']
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = compute_atr(df, length)
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(length).mean() / (atr + 1e-9))
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(length).mean() / (atr + 1e-9))
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
    return dx.rolling(length).mean()

def compute_rsi(df, length=14):
    delta = df['Close'].diff()
    gain, loss = (delta.where(delta > 0, 0)).rolling(length).mean(), (-delta.where(delta < 0, 0)).rolling(length).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def compute_bollinger_bands(df, length=20, std_dev=2):
    middle = df['Close'].rolling(length).mean()
    std = df['Close'].rolling(length).std()
    return middle + (std * std_dev), middle, middle - (std * std_dev)

def strategy_1_trend_momentum(df, df_5m):
    ema8, ema21 = df['Close'].ewm(span=8, adjust=False).mean().iloc[-1], df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
    ema20_5m, ema50_5m = df_5m['Close'].ewm(span=20, adjust=False).mean().iloc[-1], df_5m['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    htf_trend = "BULLISH" if ema20_5m > ema50_5m else "BEARISH"
    rsi_val = compute_rsi(df).iloc[-1]
    curr_c, curr_o, curr_h, curr_l = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1]), float(df['High'].iloc[-1]), float(df['Low'].iloc[-1])
    body, total_range = abs(curr_c - curr_o), max(curr_h - curr_l, 0.00001)

    if (body / total_range) > 0.65:
        if ema8 > ema21 and htf_trend == "BULLISH" and 52 <= rsi_val <= 70:
            return "BUY", 88, f"EMA8/21 Bull Cross + HTF Trend + RSI ({rsi_val:.1f})"
        elif ema8 < ema21 and htf_trend == "BEARISH" and 30 <= rsi_val <= 48:
            return "SELL", 88, f"EMA8/21 Bear Cross + HTF Trend + RSI ({rsi_val:.1f})"
    return None, 0, ""

def strategy_2_bollinger_reversal(df):
    bb_upper, bb_mid, bb_lower = compute_bollinger_bands(df)
    rsi_val = compute_rsi(df).iloc[-1]
    curr_c, curr_o, curr_h, curr_l = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1]), float(df['High'].iloc[-1]), float(df['Low'].iloc[-1])
    curr_bbu, curr_bbl = float(bb_upper.iloc[-1]), float(bb_lower.iloc[-1])
    body = abs(curr_c - curr_o)
    upper_wick, lower_wick = curr_h - max(curr_c, curr_o), min(curr_c, curr_o) - curr_l

    if curr_l <= curr_bbl and rsi_val < 32 and lower_wick > body * 1.2:
        return "BUY", 90, f"BB Lower Overextension + Oversold RSI ({rsi_val:.1f})"
    elif curr_h >= curr_bbu and rsi_val > 68 and upper_wick > body * 1.2:
        return "SELL", 90, f"BB Upper Overextension + Overbought RSI ({rsi_val:.1f})"
    return None, 0, ""

def strategy_3_micro_sr_bounce(df):
    recent_min, recent_max = float(df['Low'].iloc[-20:-2].min()), float(df['High'].iloc[-20:-2].max())
    curr_c, curr_o, curr_h, curr_l = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1]), float(df['High'].iloc[-1]), float(df['Low'].iloc[-1])
    body = abs(curr_c - curr_o)
    lower_wick, upper_wick = min(curr_c, curr_o) - curr_l, curr_h - max(curr_c, curr_o)

    if curr_l <= recent_min and curr_c > recent_min and lower_wick > body * 1.3:
        return "BUY", 86, f"Support Zone Rejection at {recent_min:.5f}"
    elif curr_h >= recent_max and curr_c < recent_max and upper_wick > body * 1.3:
        return "SELL", 86, f"Resistance Zone Rejection at {recent_max:.5f}"
    return None, 0, ""

def strategy_4_engulfing_breakout(df):
    curr_c, curr_o = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1])
    prev_c, prev_o = float(df['Close'].iloc[-2]), float(df['Open'].iloc[-2])
    atr_val = float(compute_atr(df).iloc[-1])
    body_curr, body_prev = abs(curr_c - curr_o), abs(prev_c - prev_o)

    if curr_c > curr_o and prev_c < prev_o and curr_c > prev_o and curr_o < prev_c and body_curr > 1.5 * body_prev and body_curr > atr_val:
        return "BUY", 87, "Bullish Institutional Engulfing Pattern"
    elif curr_c < curr_o and prev_c > prev_o and curr_c < prev_o and curr_o > prev_c and body_curr > 1.5 * body_prev and body_curr > atr_val:
        return "SELL", 87, "Bearish Institutional Engulfing Pattern"
    return None, 0, ""

def run_modular_analysis(symbol):
    clean_pair = symbol.replace("=X", "")
    
    df = yf.download(tickers=symbol, period="1d", interval="1m", progress=False)
    if df.empty or len(df) < 50: return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    df_5m = yf.download(tickers=symbol, period="1d", interval="5m", progress=False)
    if df_5m.empty or len(df_5m) < 20: return
    if isinstance(df_5m.columns, pd.MultiIndex): df_5m.columns = df_5m.columns.get_level_values(0)

    adx_val = float(compute_adx(df).iloc[-1])
    atr_val = float(compute_atr(df).iloc[-1])
    avg_atr = float(compute_atr(df).iloc[-20:].mean())

    if adx_val < 11 or atr_val > 2.8 * avg_atr: return

    strategies_to_run = [
        ("STRATEGY_1", "Trend Momentum Scalp", lambda: strategy_1_trend_momentum(df, df_5m)),
        ("STRATEGY_2", "Bollinger Extreme Reversal", lambda: strategy_2_bollinger_reversal(df)),
        ("STRATEGY_3", "Micro S/R Level Bounce", lambda: strategy_3_micro_sr_bounce(df)),
        ("STRATEGY_4", "Engulfing Breakout", lambda: strategy_4_engulfing_breakout(df))
    ]

    for strat_id, strat_name, strat_func in strategies_to_run:
        action, score, reason = strat_func()
        
        if action and score >= 85:
            now_bd = datetime.now(BD_TIMEZONE)
            curr_seconds = now_bd.second
            seconds_remaining = 60 - curr_seconds

            next_candle_start = (now_bd + timedelta(seconds=seconds_remaining)).strftime("%I:%M:%S %p")
            next_candle_end = (now_bd + timedelta(seconds=seconds_remaining + 60)).strftime("%I:%M:%S %p")
            action_emoji = "🟢 BUY (CALL / UP)" if action == "BUY" else "🔴 SELL (PUT / DOWN)"
            entry_p = float(df['Close'].iloc[-1])

            signal_msg = (
                f"🚨 *HIGH CONFLUENCE AI TRADE SIGNAL* 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🪙 *ASSET:* `{clean_pair}`\n"
                f"🏷️ *STRATEGY:* `#{strat_id}: {strat_name}`\n"
                f"📶 *ACTION:* *{action_emoji}*\n\n"
                f"⏰ *TIMING & EXPIRY:*\n"
                f"• *Entry Time:* `{next_candle_start}` (BD Time)\n"
                f"• *Candle Time:* `1 Minute`\n"
                f"• *Exit / Expiry:* `{next_candle_end}`\n"
                f"• *Preparation:* `{seconds_remaining} Seconds`\n\n"
                f"📊 *DETAILS:*\n"
                f"• *Setup:* `{reason}`\n"
                f"• *Win Score:* `{score}% / 100`\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            send_telegram_msg(signal_msg)
            
            threading.Thread(
                target=evaluate_trade_outcome_async,
                args=(symbol, strat_id, action_emoji, entry_p, score, reason, seconds_remaining),
                daemon=True
            ).start()
            break

def start_bot_loop():
    scan_cycle = 1
    while True:
        try:
            for pair in ALL_FOREX_PAIRS:
                run_modular_analysis(pair)
                time.sleep(0.3)
            scan_cycle += 1
            time.sleep(2)
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    # Start Flask Web Server in background thread
    threading.Thread(target=run_flask, daemon=True).start()
    send_telegram_msg("🚀 *[BOT DEPLOYED]* Institutional AI Bot is now Live 24/7 on Cloud!")
    # Start Trading Bot Loop
    start_bot_loop()