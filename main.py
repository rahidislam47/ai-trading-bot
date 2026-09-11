import sys
# Real-time stdout streaming on cloud servers
sys.stdout.reconfigure(line_buffering=True)

import os
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask

# ==========================================
# 🟢 FLASK WEB SERVER FOR KEEP-ALIVE
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🟢 Institutional AI Trading Bot is Active & Running 24/7 on Cloud!"

# ==========================================
# ⚙️ CONFIGURATION & TELEGRAM SETTINGS
# ==========================================
TELEGRAM_BOT_TOKEN = "8654325516:AAF0CdoX7BJO51IVP5j4GXhWt7rKcFHoD2o"
TELEGRAM_CHAT_ID = "6106490095"

PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "NZDUSD=X",
    "USDCHF=X", "EURAUD=X", "GBPAUD=X", "GBPCAD=X", "EURNZD=X"
]

# Database Lock for multi-threaded safety
db_lock = threading.Lock()

# ==========================================
# 💾 DATABASE MANAGEMENT & MEMORY SYSTEM
# ==========================================
def init_db():
    with db_lock:
        conn = sqlite3.connect('trading_memory.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                asset TEXT,
                strategy_id TEXT,
                signal_type TEXT,
                entry_price REAL,
                exit_price REAL,
                win_rate_score INTEGER,
                result TEXT,
                analysis_reason TEXT
            )
        ''')
        conn.commit()
        conn.close()

init_db()

def log_trade_to_db(asset, strat_id, signal_type, entry_p, exit_p, score, result, reason):
    now_bd = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime('%Y-%m-%d %I:%M:%S %p')
    with db_lock:
        conn = sqlite3.connect('trading_memory.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trade_outcomes (timestamp, asset, strategy_id, signal_type, entry_price, exit_price, win_rate_score, result, analysis_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (now_bd, asset, strat_id, signal_type, entry_p, exit_p, score, result, reason))
        conn.commit()
        conn.close()

def generate_performance_analytics():
    with db_lock:
        conn = sqlite3.connect('trading_memory.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT strategy_id, result FROM trade_outcomes")
        rows = cursor.fetchall()
        conn.close()

    if not rows:
        return "📊 *Performance Memory:* No trades logged in current session."

    total_trades = len(rows)
    overall_wins = sum(1 for r in rows if "WIN" in r[1])
    overall_losses = sum(1 for r in rows if "LOSS" in r[1])
    overall_winrate = (overall_wins / total_trades) * 100 if total_trades > 0 else 0

    # Group statistics by strategy
    strategy_stats = {}
    for strat_id, result in rows:
        if strat_id not in strategy_stats:
            strategy_stats[strat_id] = {"total": 0, "wins": 0, "losses": 0}
        strategy_stats[strat_id]["total"] += 1
        if "WIN" in result:
            strategy_stats[strat_id]["wins"] += 1
        else:
            strategy_stats[strat_id]["losses"] += 1

    report = f"📊 *INSTITUTIONAL AI MEMORY REPORT*\n"
    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"📈 *OVERALL PERFORMANCE:*\n"
    report += f"• Total Executions: `{total_trades}`\n"
    report += f"• Win Rate: `{overall_winrate:.1f}%` (Wins: {overall_wins} | Losses: {overall_losses})\n\n"
    report += f"🧠 *STRATEGY BREAKDOWN:*\n"

    for strat, data in strategy_stats.items():
        st_total = data["total"]
        st_wins = data["wins"]
        st_losses = data["losses"]
        st_wr = (st_wins / st_total) * 100 if st_total > 0 else 0
        
        status_icon = "🟢" if st_wr >= 60 else "🔴"
        
        report += (
            f"\n{status_icon} *{strat}*\n"
            f"   • Total Trades: `{st_total}`\n"
            f"   • Win Rate: `{st_wr:.1f}%` (W: `{st_wins}` | L: `{st_losses}`)\n"
        )

    return report

# ==========================================
# 📲 TELEGRAM NOTIFICATION SYSTEM
# ==========================================
def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if not data.get("ok"):
            print(f"❌ Telegram API Error Response: {data}")
        return data
    except Exception as e:
        print(f"❌ Telegram Send Error: {e}")
        return None

# ==========================================
# 📊 TECHNICAL INDICATORS CALCULATOR
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ==========================================
# 🧠 INSTITUTIONAL ALGORITHMIC STRATEGIES
# ==========================================
def evaluate_market_data(df, ticker):
    if len(df) < 50:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']
    high = df['High']
    low = df['Low']
    open_p = df['Open']

    ema8 = close.ewm(span=8, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    rsi = calculate_rsi(close, 14)

    c_curr = float(close.iloc[-1])
    c_prev = float(close.iloc[-2])
    o_curr = float(open_p.iloc[-1])
    o_prev = float(open_p.iloc[-2])
    h_curr = float(high.iloc[-1])
    l_curr = float(low.iloc[-1])

    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    signal = None
    win_score = 0
    strategy_id = ""
    setup_name = ""

    # Strategy 1: Trend Momentum Scalp
    if ema8.iloc[-1] > ema21.iloc[-1] and ema8.iloc[-2] <= ema21.iloc[-2] and c_curr > ema50.iloc[-1] and rsi_val > 52:
        signal = "BUY (CALL / UP)"
        strategy_id = "Strategy 1 (EMA Cross)"
        setup_name = f"EMA8/21 Bull Cross + HTF Trend + RSI ({rsi_val:.1f})"
        win_score = 88
    elif ema8.iloc[-1] < ema21.iloc[-1] and ema8.iloc[-2] >= ema21.iloc[-2] and c_curr < ema50.iloc[-1] and rsi_val < 48:
        signal = "SELL (PUT / DOWN)"
        strategy_id = "Strategy 1 (EMA Cross)"
        setup_name = f"EMA8/21 Bear Cross + HTF Trend + RSI ({rsi_val:.1f})"
        win_score = 88

    # Strategy 2: Institutional Engulfing Breakout
    elif c_prev < o_prev and c_curr > o_curr and c_curr > o_prev and (c_curr - o_curr) > (o_prev - c_prev) * 1.2 and rsi_val > 50:
        signal = "BUY (CALL / UP)"
        strategy_id = "Strategy 2 (Engulfing)"
        setup_name = "Bullish Institutional Engulfing Pattern"
        win_score = 87
    elif c_prev > o_prev and c_curr < o_curr and c_curr < o_prev and (o_curr - c_curr) > (c_prev - o_prev) * 1.2 and rsi_val < 50:
        signal = "SELL (PUT / DOWN)"
        strategy_id = "Strategy 2 (Engulfing)"
        setup_name = "Bearish Institutional Engulfing Pattern"
        win_score = 87

    # Strategy 3: Micro S/R Level Bounce
    elif l_curr <= low.iloc[-20:-1].min() and c_curr > o_curr and rsi_val < 35:
        signal = "BUY (CALL / UP)"
        strategy_id = "Strategy 3 (S/R Bounce)"
        setup_name = f"Support Zone Rejection at {l_curr:.5f}"
        win_score = 86
    elif h_curr >= high.iloc[-20:-1].max() and c_curr < o_curr and rsi_val > 65:
        signal = "SELL (PUT / DOWN)"
        strategy_id = "Strategy 3 (S/R Bounce)"
        setup_name = f"Resistance Zone Rejection at {h_curr:.5f}"
        win_score = 86

    if signal and win_score >= 85:
        clean_asset = ticker.replace("=X", "")
        return {
            "asset": clean_asset,
            "raw_ticker": ticker,
            "signal": signal,
            "strategy_id": strategy_id,
            "setup": setup_name,
            "score": win_score,
            "entry_price": c_curr
        }
    return None

# ==========================================
# ⏱️ RESULT TRACKER & OUTCOME EVALUATOR
# ==========================================
def evaluate_trade_outcome(trade_data, entry_time):
    time.sleep(65)
    ticker = trade_data["raw_ticker"]
    entry_p = trade_data["entry_price"]
    signal = trade_data["signal"]
    asset = trade_data["asset"]

    try:
        df_after = yf.download(tickers=ticker, period="1d", interval="1m", progress=False)
        if df_after.empty:
            return

        if isinstance(df_after.columns, pd.MultiIndex):
            df_after.columns = df_after.columns.get_level_values(0)

        exit_p = float(df_after['Close'].iloc[-1])
        
        is_win = False
        if "BUY" in signal:
            is_win = exit_p > entry_p
        else:
            is_win = exit_p < entry_p

        result_str = "WIN 🟢" if is_win else "LOSS 🔴"
        reason_str = f"Entry: {entry_p:.5f} | Exit: {exit_p:.5f}"

        log_trade_to_db(
            asset, trade_data["strategy_id"], signal, 
            entry_p, exit_p, trade_data["score"], 
            result_str, reason_str
        )

        formatted_asset = f"{asset[:3]}/{asset[3:]}" if len(asset) == 6 else asset

        feedback_msg = (
            f"🎯 *TRADE OUTCOME FEEDBACK*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 *PAIR:* `#${formatted_asset}`\n"
            f"🎯 *STRATEGY:* `{trade_data['strategy_id']}`\n"
            f"📊 *RESULT:* `{result_str}`\n"
            f"📈 *Entry:* `{entry_p:.5f}` ➔ *Exit:* `{exit_p:.5f}`\n\n"
            f"{generate_performance_analytics()}"
        )
        send_telegram_msg(feedback_msg)

    except Exception as e:
        print(f"❌ Error verifying trade outcome: {e}")

# ==========================================
# 🔄 MAIN BACKGROUND SCANNER LOOP
# ==========================================
def trading_bot_loop():
    print("🚀 Institutional AI Bot Thread Started & Active!")
    last_signal_time = {}

    while True:
        try:
            now_bd = datetime.now(timezone.utc) + timedelta(hours=6)

            for pair in PAIRS:
                if pair in last_signal_time:
                    if (now_bd - last_signal_time[pair]).total_seconds() < 300:
                        continue

                df = yf.download(tickers=pair, period="1d", interval="1m", progress=False)
                if df.empty:
                    continue

                trade_data = evaluate_market_data(df, pair)
                if trade_data:
                    last_signal_time[pair] = now_bd
                    
                    # Formatting Pair Name (e.g., USDCHF -> USD/CHF)
                    raw_asset = trade_data['asset']
                    formatted_asset = f"{raw_asset[:3]}/{raw_asset[3:]}" if len(raw_asset) == 6 else raw_asset

                    # Action button formatting
                    if "BUY" in trade_data['signal']:
                        action_btn = "🟢🟢 BUY / CALL 🟢🟢"
                    else:
                        action_btn = "🔴🔴 SELL / PUT 🔴🔴"

                    # Timing calculations
                    entry_time_dt = now_bd + timedelta(seconds=(60 - now_bd.second) if now_bd.second > 0 else 0)
                    seconds_left = int((entry_time_dt - now_bd).total_seconds())
                    
                    entry_time_str = entry_time_dt.strftime('%I:%M:%S %p')
                    exit_time_str = (entry_time_dt + timedelta(minutes=1)).strftime('%I:%M:%S %p')

                    # Clean Signal Message Template
                    signal_msg = (
                        f"⚡ *NEW AI TRADE SIGNAL* ⚡\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🪙 *PAIR:* `#${formatted_asset}`\n"
                        f"🎯 *ACTION:* `{action_btn}`\n\n"
                        f"⏱️ *CANDLE TIME:* `1 MINUTE`\n"
                        f"⏳ *ENTRY IN:* `{seconds_left} SECONDS`\n"
                        f"⏰ *ENTRY AT:* `{entry_time_str}`\n"
                        f"🏁 *EXPIRY:* `{exit_time_str}`\n\n"
                        f"📊 *STRATEGY:* `{trade_data['strategy_id']}`\n"
                        f"🎯 *WIN SCORE:* `{trade_data['score']}%` | Price: `{trade_data['entry_price']:.5f}`\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    )

                    send_telegram_msg(signal_msg)
                    print(f"⚡ SIGNAL SENT: {formatted_asset} - {trade_data['signal']}")

                    eval_thread = threading.Thread(
                        target=evaluate_trade_outcome, 
                        args=(trade_data, now_bd), 
                        daemon=True
                    )
                    eval_thread.start()

            time.sleep(10)

        except Exception as e:
            print(f"❌ Error in Bot Loop: {e}")
            time.sleep(10)

# ==========================================
# 🚀 GLOBAL THREAD INITIATION FOR GUNICORN
# ==========================================
bot_thread = threading.Thread(target=trading_bot_loop, daemon=True)
bot_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
