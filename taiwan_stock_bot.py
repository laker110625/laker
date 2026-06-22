"""
台股掃圖 Telegram 機器人
每天週一至週五 08:30 自動掃描並發送結果到 Telegram 群組
使用方式：
  pip install yfinance pandas schedule requests
  python taiwan_stock_bot.py
"""

import yfinance as yf
import pandas as pd
import requests
import schedule
import time
from datetime import datetime

# ── 設定區（不需要改其他地方） ────────────────────────────────
TELEGRAM_TOKEN = "8980106087:AAGLN-D8d3py-Hup1RpwSyrS_nbvfBdPLoI"
CHAT_ID        = "-5358545118"
SCAN_TIME      = "08:30"  # 每天發送時間

STOCK_LIST = [
    "2330", "2317", "2454", "2308", "2382",
    "2303", "2881", "2882", "2886", "2891",
    "2412", "2002", "1301", "1303", "2207",
    "3008", "2357", "2379", "2395", "4938",
    "2408", "2474", "3711", "2327", "6505",
    "2353", "2912", "1216", "2105", "2915",
]

# ── Telegram 發送 ──────────────────────────────────────────────

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[發送失敗] {e}")

# ── 資料與計算 ─────────────────────────────────────────────────

def get_stock_data(symbol):
    try:
        df = yf.download(f"{symbol}.TW", period="3mo", progress=False, auto_adjust=True)
        if df.empty or len(df) < 62:
            return None
        return df
    except Exception:
        return None

def calc_ma(df):
    df = df.copy()
    df["MA5"]  = df["Close"].rolling(5).mean()
    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    return df

# ── K線型態 ────────────────────────────────────────────────────

def is_hammer(df):
    r = df.iloc[-1]
    body  = abs(float(r["Close"]) - float(r["Open"]))
    lower = float(min(r["Close"], r["Open"])) - float(r["Low"])
    upper = float(r["High"]) - float(max(r["Close"], r["Open"]))
    if body == 0:
        return False
    return lower >= 2 * body and upper <= 0.3 * body

def is_bullish_engulfing(df):
    if len(df) < 2:
        return False
    prev, curr = df.iloc[-2], df.iloc[-1]
    return (float(prev["Close"]) < float(prev["Open"]) and
            float(curr["Close"]) > float(curr["Open"]) and
            float(curr["Open"]) <= float(prev["Close"]) and
            float(curr["Close"]) >= float(prev["Open"]))

def is_gap_up(df):
    if len(df) < 2:
        return False
    return float(df.iloc[-1]["Low"]) > float(df.iloc[-2]["High"])

# ── 均線訊號 ───────────────────────────────────────────────────

def is_golden_cross(df):
    if len(df) < 2:
        return False
    p, c = df.iloc[-2], df.iloc[-1]
    return float(p["MA5"]) <= float(p["MA20"]) and float(c["MA5"]) > float(c["MA20"])

def is_bull_alignment(df):
    r = df.iloc[-1]
    return float(r["MA5"]) > float(r["MA10"]) > float(r["MA20"]) > float(r["MA60"])

PATTERN_CHECKS = {
    "🔨鎚子線":   is_hammer,
    "🟢多頭吞噬": is_bullish_engulfing,
    "⬆️跳空缺口": is_gap_up,
}

MA_CHECKS = {
    "✨黃金交叉": is_golden_cross,
    "📈多頭排列": is_bull_alignment,
}

# ── 掃描與發送 ─────────────────────────────────────────────────

def run_scan():
    # 週六、週日跳過
    if datetime.now().weekday() >= 5:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 假日，跳過掃描")
        return

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 開始掃描...")
    send_telegram(f"🔍 <b>台股掃圖開始</b>｜{datetime.now().strftime('%Y-%m-%d %H:%M')}\n掃描 {len(STOCK_LIST)} 檔中，請稍候...")

    results = []
    for symbol in STOCK_LIST:
        df = get_stock_data(symbol)
        if df is None:
            continue
        df = calc_ma(df)
        df = df.dropna()
        if len(df) < 2:
            continue

        matched_patterns = [name for name, fn in PATTERN_CHECKS.items() if fn(df)]
        matched_ma       = [name for name, fn in MA_CHECKS.items()       if fn(df)]

        if matched_patterns or matched_ma:
            close  = float(df.iloc[-1]["Close"])
            change = close - float(df.iloc[-2]["Close"])
            pct    = change / float(df.iloc[-2]["Close"]) * 100
            results.append({
                "代號":     symbol,
                "收盤價":   round(close, 2),
                "漲跌幅":   round(pct, 2),
                "型態":     matched_patterns,
                "均線":     matched_ma,
            })
        time.sleep(0.3)

    # 組成訊息
    if not results:
        msg = "📊 <b>掃描完成</b>\n今日無符合條件的股票。"
    else:
        lines = [f"📊 <b>台股掃圖結果</b>｜共 {len(results)} 檔\n"]
        for r in results:
            arrow = "▲" if r["漲跌幅"] >= 0 else "▼"
            signals = r["型態"] + r["均線"]
            lines.append(
                f"<b>{r['代號']}</b>  {r['收盤價']:.2f}  {arrow}{abs(r['漲跌幅']):.2f}%\n"
                f"  {' | '.join(signals)}"
            )
        msg = "\n".join(lines)

    send_telegram(msg)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 發送完成，{len(results)} 檔符合條件")

# ── 主程式 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"台股掃圖機器人啟動，每天 {SCAN_TIME} 自動掃描（週一至週五）")
    print("按 Ctrl+C 停止\n")

    # 排程設定
    schedule.every().day.at(SCAN_TIME).do(run_scan)

    # 啟動時先跑一次（方便測試）
    run_scan()

    while True:
        schedule.run_pending()
        time.sleep(30)
