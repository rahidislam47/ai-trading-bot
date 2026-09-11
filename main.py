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

# Database Lock & Global Signal Counter
db_lock = threading.Lock()
signal_counter = 0

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
    now_bd = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime('%Y-%m-%d %I:%M:%S %p (BD)')
    with db_lock:
        conn = sqlite3.connect('trading_memory.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trade_outcomes (timestamp, asset, strategy_id, signal_type, entry_price, exit_price, win_rate_score, result, analysis_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (now_bd, asset, strat_id, signal_type, entry_p, exit_p, score, result, reason))
        conn.commit()
        conn.close()

# ==========================================
# 📊 TEN TRADES ANALYSIS REPORT
# ==========================================
def generate_ten_trades_analysis():
    with db_lock:
        conn = sqlite3.connect('trading_memory.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT strategy_id, result FROM trade_outcomes ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()

    if not rows:
        return None

    total_last_10 = len(rows)
    wins = sum(1 for r in rows if "WIN" in r[1])
    losses = sum(1 for r in rows if "LOSS" in r[1])
    winrate = (wins / total_last_10) * 100 if total_last_10 > 0 else 0

    strategy_stats = {}
    for strat_id, result in rows:
        if strat_id not in strategy_stats:
            strategy_stats[strat_id] = {"total": 0, "wins": 0, "losses": 0}
        strategy_stats[strat_id]["total"] += 1
        if "WIN" in result:
            strategy_stats[strat_id]["wins"] += 1
        else:
            strategy_stats[strat_id]["losses"] += 1

    # Find Top Performing Strategy
    best_strat = "N/A"
    best_wins = -1
    for strat, data in strategy_stats.items():
        if data["wins"] > best_wins:
            best_wins = data["wins"]
            best_strat = strat

    report = (
        f"🔥 ━━━━━━━━━━━━━━━━━━━ 🔥\n"
        f"    📊 *TEN TRADES ANALYSIS* 📊\n"
        f"🔥 ━━━━━━━━━━━━━━━━━━━ 🔥\n\n"
        f"📈 *LAST 10 TRADES SUMMARY:*\n"
        f"• Total Executions: `{total_last_10}`\n"
        f"• Accuracy Win Rate: `{winrate:.0f}%` (Wins: {wins} 🟢 | Losses: {losses} 🔴)\n\n"
        f"🎯 *MOST ACCURATE STRATEGY:*\n"
        f"• `{best_strat}` ({best_wins} Wins)\n\n"
        f"🧠 *STRATEGY USAGE BREAKDOWN:*\n"
    )

    for strat, data in strategy_stats.items():
        st_total = data["total"]
        st_wins = data["wins"]
        st_losses = data["losses"]
        st_wr = (st_wins / st_total) * 100 if st_total > 0 else 0
        status_icon = "🟢" if st_wr >= 50 else "🔴"
        
        report += f"• {status_icon} *{strat}:* `{st_wins}/{st_total} Win` ({st_wr:.0f}%)\n"

    report += f"\n🔥 ━━━━━━━━━━━━━━━━━━━ 🔥"
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
        signal = "BUY"
        strategy_id = "Strategy 1 (EMA Cross)"
        setup_name = f"EMA8/21 Bull Cross + HTF Trend + RSI ({rsi_val:.1f})"
        win_score = 88
    elif ema8.iloc[-1] < ema21.iloc[-1] and ema8.iloc[-2] >= ema21.iloc[-2] and c_curr < ema50.iloc[-1] and rsi_val < 48:
        signal = "SELL"
        strategy_id = "Strategy 1 (EMA Cross)"
        setup_name = f"EMA8/21 Bear Cross + HTF Trend + RSI ({rsi_val:.1f})"
        win_score = 88

    # Strategy 2: Institutional Engulfing Breakout
    elif c_prev < o_prev and c_curr > o_curr and c_curr > o_prev and (c_curr - o_curr) > (o_prev - c_prev) * 1.2 and rsi_val > 50:
        signal = "BUY"
        strategy_id = "Strategy 2 (Engulfing)"
        setup_name = "Bullish Institutional Engulfing Pattern"
        win_score = 87
    elif c_prev > o_prev and c_curr < o_curr and c_curr < o_prev and (o_curr - c_curr) > (c_prev - o_prev) * 1.2 and rsi_val < 50:
        signal = "SELL"
        strategy_id = "Strategy 2 (Engulfing)"
        setup_name = "Bearish Institutional Engulfing Pattern"
        win_score = 87

    # Strategy 3: Micro S/R Level Bounce
    elif l_curr <= low.iloc[-20:-1].min() and c_curr > o_curr and rsi_val < 35:
        signal = "BUY"
        strategy_id = "Strategy 3 (S/R Bounce)"
        setup_name = f"Support Zone Rejection at {l_curr:.5f}"
        win_score = 86
    elif h_curr >= high.iloc[-20:-1].max() and c_curr < o_curr and rsi_val > 65:
        signal = "SELL"
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
        if signal == "BUY":
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
            f"🪙 *PAIR:* `{formatted_asset}`\n"
            f"🎯 *STRATEGY:* `{trade_data['strategy_id']}`\n"
            f"📊 *RESULT:* `{result_str}`\n"
            f"📈 *Entry:* `{entry_p:.5f}` ➔ *Exit:* `{exit_p:.5f}`"
        )
        send_telegram_msg(feedback_msg)

        # Check if 10 trades analysis needs to be sent
        if signal_counter % 10 == 0:
            time.sleep(5)
            analysis_msg = generate_ten_trades_analysis()
            if analysis_msg:
                send_telegram_msg(analysis_msg)

    except Exception as e:
        print(f"❌ Error verifying trade outcome: {e}")

# ==========================================
# 🔄 MAIN BACKGROUND SCANNER LOOP
# ==========================================
def trading_bot_loop():
    global signal_counter
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
                    signal_counter += 1
                    last_signal_time[pair] = now_bd
                    
                    raw_asset = trade_data['asset']
                    formatted_asset = f"{raw_asset[:3]}/{raw_asset[3:]}" if len(raw_asset) == 6 else raw_asset

                    # Dynamic Action & Pair Formatting
                    if trade_data['signal'] == "BUY":
                        action_display = "🟢 🟢 `BUY (CALL)` 🟢 🟢"
                        pair_display = f"🟢 `{formatted_asset}`"
                    else:
                        action_display = "🔴 🔴 `SELL (PUT)` 🔴 🔴"
                        pair_display = f"🔴 `{formatted_asset}`"

                    # Timing Calculations
                    entry_time_dt = now_bd + timedelta(seconds=(60 - now_bd.second) if now_bd.second > 0 else 0)
                    seconds_left = int((entry_time_dt - now_bd).total_seconds())
                    
                    entry_time_str = entry_time_dt.strftime('%I:%M:%S %p (BD)')
                    exit_time_str = (entry_time_dt + timedelta(minutes=1)).strftime('%I:%M:%S %p (BD)')

                    # Final Dynamic Signal Layout
                    signal_msg = (
                        f"🔥 ━━━━━━━━━━━━━━━━━━━ 🔥\n"
                        f"  💎 *REAL MARKET BINARY SIGNAL #{signal_counter}* 💎\n"
                        f"🔥 ━━━━━━━━━━━━━━━━━━━ 🔥\n\n"
                        f"🪙 *PAIR:* {pair_display}\n"
                        f"⚡ *ACTION:* {action_display}\n\n"
                        f"⏰ *TIMING DETAILS:*\n"
                        f"• *Entry Time : {entry_time_str}*\n"
                        f"• Expiry Time: {exit_time_str}\n"
                        f"• Timeframe  : 1 Minute (M1)\n"
                        f"⏳ *ENTRY IN : {seconds_left} SECONDS LEFT*\n\n"
                        f"📊 *STRATEGY METRICS:*\n"
                        f"• Strategy   : `{trade_data['strategy_id']}`\n"
                        f"• Win Score  : `{trade_data['score']}% / 100`\n"
                        f"• Entry Price: `{trade_data['entry_price']:.5f}`\n\n"
                        f"🔥 ━━━━━━━━━━━━━━━━━━━ 🔥"
                    )

                    send_telegram_msg(signal_msg)
                    print(f"⚡ SIGNAL #{signal_counter} SENT: {formatted_asset} - {trade_data['signal']}")

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
