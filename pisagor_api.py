from flask import Flask, jsonify, request
import yfinance as yf
import pandas as pd
import numpy as np
import math
import requests

app = Flask(__name__)

def veri_cek(ticker):
    """Yahoo Finance'den veri çek — birden fazla yöntem dene"""
    
    # Yöntem 1: yfinance ile dene
    try:
        hisse = yf.Ticker(ticker)
        df = hisse.history(period="6mo", interval="1d")
        if len(df) > 60:
            df.columns = [c.lower() for c in df.columns]
            return df
    except:
        pass
    
    # Yöntem 2: yfinance download farklı parametrelerle
    try:
        df = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
            prepost=False,
            threads=False,
            proxy=None
        )
        if len(df) > 60:
            df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
            return df
    except:
        pass

    # Yöntem 3: Direkt Yahoo Finance v8 API
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=6mo&interval=1d"
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv = result["indicators"]["quote"][0]
        
        df = pd.DataFrame({
            "open"  : ohlcv["open"],
            "high"  : ohlcv["high"],
            "low"   : ohlcv["low"],
            "close" : ohlcv["close"],
            "volume": ohlcv["volume"],
        }, index=pd.to_datetime(timestamps, unit="s"))
        
        df = df.dropna()
        if len(df) > 60:
            return df
    except:
        pass

    # Yöntem 4: Yahoo Finance v7
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query2.finance.yahoo.com/v7/finance/download/{ticker}?range=6mo&interval=1d&events=history"
        r = requests.get(url, headers=headers, timeout=15)
        from io import StringIO
        df = pd.read_csv(StringIO(r.text))
        df.columns = [c.lower() for c in df.columns]
        df = df.dropna()
        df.index = pd.to_datetime(df["date"])
        if len(df) > 60:
            return df
    except:
        pass

    return None

def geometrik_oran():
    ucluler = [
        (5.0/3.0,  5.0/4.0),
        (13.0/5.0, 13.0/12.0),
        (17.0/8.0, 17.0/15.0),
        (25.0/7.0, 25.0/24.0),
    ]
    log_a = sum(math.log(r[0]) for r in ucluler) / len(ucluler)
    log_b = sum(math.log(r[1]) for r in ucluler) / len(ucluler)
    return math.exp(log_a), math.exp(log_b)

def pisagor_ma(close):
    agirliklar = [(5.0, 3), (13.0, 5), (17.0, 8), (25.0, 7)]
    toplam = sum(a for a, _ in agirliklar)
    pma = pd.Series(0.0, index=close.index)
    for agirlik, periyot in agirliklar:
        pma += (agirlik / toplam) * close.rolling(window=periyot).mean()
    return pma

def hesapla_rsi(close, periyot=14):
    delta = close.diff()
    kazan = delta.where(delta > 0, 0.0).rolling(window=periyot).mean()
    kayip = (-delta.where(delta < 0, 0.0)).rolling(window=periyot).mean()
    rs = kazan / kayip
    return 100 - (100 / (1 + rs))

def hesapla_adx(high, low, close, periyot=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=periyot).mean()
    dm_p = (high - high.shift()).where((high - high.shift()) > (low.shift() - low), 0.0).clip(lower=0)
    dm_m = (low.shift() - low).where((low.shift() - low) > (high - high.shift()), 0.0).clip(lower=0)
    di_p = 100 * dm_p.rolling(window=periyot).mean() / atr
    di_m = 100 * dm_m.rolling(window=periyot).mean() / atr
    dx   = 100 * (di_p - di_m).abs() / (di_p + di_m)
    adx  = dx.rolling(window=periyot).mean()
    return adx, di_p, di_m

def analiz_et(ticker, lookback=50):
    df = veri_cek(ticker)
    
    if df is None or len(df) < lookback + 10:
        bar_say = len(df) if df is not None else 0
        return {"hata": f"Veri alinamadi: {ticker} — {bar_say} bar", "hisse": ticker}
    
    close  = df["close"].squeeze().astype(float)
    high   = df["high"].squeeze().astype(float)
    low    = df["low"].squeeze().astype(float)
    volume = df["volume"].squeeze().astype(float)
    
    avg_ra, avg_rb = geometrik_oran()
    pma = pisagor_ma(close)
    
    atr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1).rolling(window=lookback).mean()
    
    b_up = pma + atr * avg_ra
    b_mu = pma + atr * avg_rb
    b_md = pma - atr * avg_rb
    b_lo = pma - atr * avg_ra
    
    trend_up   = (close > pma) & (pma > pma.shift(3))
    trend_down = (close < pma) & (pma < pma.shift(3))
    
    rsi = hesapla_rsi(close)
    adx, dip, dim = hesapla_adx(high, low, close)
    vol_ma = volume.rolling(20).mean()
    vol_ok = volume > vol_ma * 1.2
    mom = ((close - pma) / atr * 10).where(atr > 0, 0.0)
    
    cross_up_mid   = (close > b_md) & (close.shift() <= b_md.shift())
    cross_dn_mid   = (close < b_mu) & (close.shift() >= b_mu.shift())
    cross_up_lower = (close > b_lo) & (close.shift() <= b_lo.shift())
    cross_dn_upper = (close < b_up) & (close.shift() >= b_up.shift())
    
    rsi_al  = rsi < 70
    rsi_sat = rsi > 35
    adx_ok  = adx >= 18
    di_bull = dip > dim
    di_bear = dim > dip
    
    al_sinyal  = cross_up_mid   & trend_up   & rsi_al  & adx_ok & vol_ok & di_bull
    sat_sinyal = cross_dn_mid   & trend_down & rsi_sat & adx_ok & vol_ok & di_bear
    guclu_al   = cross_up_lower & trend_up   & (rsi < 50) & adx_ok & vol_ok & di_bull
    guclu_sat  = cross_dn_upper & trend_down & (rsi > 55) & adx_ok & vol_ok & di_bear
    
    s = -1
    son_fiyat = round(float(close.iloc[s]), 2)
    son_pma   = round(float(pma.iloc[s]), 2)
    son_b_up  = round(float(b_up.iloc[s]), 2)
    son_b_mu  = round(float(b_mu.iloc[s]), 2)
    son_b_md  = round(float(b_md.iloc[s]), 2)
    son_b_lo  = round(float(b_lo.iloc[s]), 2)
    son_rsi   = round(float(rsi.iloc[s]), 1)
    son_adx   = round(float(adx.iloc[s]), 1)
    son_dip   = round(float(dip.iloc[s]), 1)
    son_dim   = round(float(dim.iloc[s]), 1)
    son_mom   = round(float(mom.iloc[s]), 2)
    
    t_up   = bool(trend_up.iloc[s])
    t_down = bool(trend_down.iloc[s])
    trend_txt = "YUKARI" if t_up else "ASAGI" if t_down else "YATAY"
    
    sinyal_tip = "BEKLE"
    sinyal_guclu = False
    sinyal_skor  = 0
    tp_sev = None
    sl_sev = None
    
    if bool(guclu_al.iloc[s]):
        sinyal_tip = "AL"; sinyal_guclu = True
        sinyal_skor = int(t_up) + int(bool(rsi_al.iloc[s])) + int(bool(adx_ok.iloc[s])) + int(bool(vol_ok.iloc[s])) + int(bool(di_bull.iloc[s]))
        tp_sev = son_b_mu; sl_sev = round(son_b_lo * 0.98, 2)
    elif bool(al_sinyal.iloc[s]):
        sinyal_tip = "AL"
        sinyal_skor = int(t_up) + int(bool(rsi_al.iloc[s])) + int(bool(adx_ok.iloc[s])) + int(bool(vol_ok.iloc[s])) + int(bool(di_bull.iloc[s]))
        tp_sev = son_b_mu; sl_sev = round(son_b_md * 0.99, 2)
    elif bool(guclu_sat.iloc[s]):
        sinyal_tip = "SAT"; sinyal_guclu = True
        sinyal_skor = int(t_down) + int(bool(rsi_sat.iloc[s])) + int(bool(adx_ok.iloc[s])) + int(bool(vol_ok.iloc[s])) + int(bool(di_bear.iloc[s]))
        tp_sev = son_b_md; sl_sev = round(son_b_up * 1.02, 2)
    elif bool(sat_sinyal.iloc[s]):
        sinyal_tip = "SAT"
        sinyal_skor = int(t_down) + int(bool(rsi_sat.iloc[s])) + int(bool(adx_ok.iloc[s])) + int(bool(vol_ok.iloc[s])) + int(bool(di_bear.iloc[s]))
        tp_sev = son_b_md; sl_sev = round(son_b_mu * 1.01, 2)
    
    yildiz = "★" * sinyal_skor + "☆" * (5 - sinyal_skor)
    
    return {
        "hisse": ticker, "fiyat": son_fiyat, "sinyal": sinyal_tip,
        "guclu": sinyal_guclu, "skor": sinyal_skor, "yildiz": yildiz,
        "tp": tp_sev, "sl": sl_sev, "trend": trend_txt,
        "rsi": son_rsi, "adx": son_adx, "di_plus": son_dip, "di_minus": son_dim,
        "momentum": son_mom, "pisagor_ma": son_pma,
        "ust_direnc": son_b_up, "ara_ust": son_b_mu,
        "ara_alt": son_b_md, "alt_destek": son_b_lo,
        "geo_oran_a": round(avg_ra, 3), "geo_oran_b": round(avg_rb, 3),
        "bar_sayisi": len(df)
    }

def telegram_mesaj(sonuc):
    if "hata" in sonuc or sonuc["sinyal"] == "BEKLE":
        return None
    guclu = "💪 GÜÇLÜ " if sonuc["guclu"] else ""
    emoji = "🟢" if sonuc["sinyal"] == "AL" else "🔴"
    trend_emoji = "📈" if sonuc["trend"] == "YUKARI" else "📉" if sonuc["trend"] == "ASAGI" else "➡️"
    mesaj = f"""{emoji} *{guclu}{sonuc['sinyal']} SİNYALİ* — {sonuc['hisse']}
{sonuc['yildiz']}

💰 Fiyat: *{sonuc['fiyat']}₺*
{trend_emoji} Trend: {sonuc['trend']}

📊 *Teknik Göstergeler*
• RSI: {sonuc['rsi']}
• ADX: {sonuc['adx']} {"✅" if sonuc['adx'] >= 18 else "⚠️"}
• DI+/DI-: {sonuc['di_plus']} / {sonuc['di_minus']}
• Momentum: {sonuc['momentum']}

📐 *Pisagor Seviyeleri*
• Üst Direnç: {sonuc['ust_direnc']}
• Pisagor MA: {sonuc['pisagor_ma']}
• Alt Destek: {sonuc['alt_destek']}"""
    if sonuc["tp"]:
        mesaj += f"\n\n🎯 *Hedef (TP)*: {sonuc['tp']}₺"
    if sonuc["sl"]:
        mesaj += f"\n🛑 *Stop (SL)*: {sonuc['sl']}₺"
    mesaj += "\n\n⚠️ _Teknik gösterge bilgisidir, yatırım tavsiyesi değildir._"
    return mesaj

@app.route("/")
def anasayfa():
    return jsonify({"sistem": "Pisagor PRO API", "versiyon": "3.1",
        "endpointler": {"/analiz/<ticker>": "Tam analiz", "/sinyal/<ticker>": "Sadece sinyal", "/tarama": "Çoklu tarama (POST)"}})

@app.route("/analiz/<ticker>")
def analiz(ticker):
    if not ticker.endswith(".IS"):
        ticker = ticker + ".IS"
    return jsonify(analiz_et(ticker))

@app.route("/sinyal/<ticker>")
def sinyal(ticker):
    if not ticker.endswith(".IS"):
        ticker = ticker + ".IS"
    sonuc = analiz_et(ticker)
    if "hata" in sonuc or sonuc["sinyal"] == "BEKLE":
        return jsonify({"sinyal": False, "mesaj": None, "detay": sonuc})
    return jsonify({"sinyal": True, "tip": sonuc["sinyal"], "guclu": sonuc["guclu"],
        "skor": sonuc["skor"], "hisse": ticker, "fiyat": sonuc["fiyat"],
        "mesaj": telegram_mesaj(sonuc), "detay": sonuc})

@app.route("/tarama", methods=["GET", "POST"])
def tarama():
    if request.method == "POST":
        data = request.json or {}
        hisseler = data.get("hisseler", [])
    else:
        hisseler = []
    
    if not hisseler:
        hisseler = ["THYAO", "GARAN", "ASELS", "KCHOL", "SAHOL",
                    "SISE", "AKBNK", "YKBNK", "ISCTR", "BIMAS",
                    "EREGL", "TUPRS", "PETKM", "KOZAL", "FROTO"]
    
    sinyaller = []
    for h in hisseler:
        ticker = h if h.endswith(".IS") else h + ".IS"
        sonuc = analiz_et(ticker)
        if "hata" not in sonuc and sonuc["sinyal"] != "BEKLE":
            sinyaller.append({"hisse": h, "sinyal": sonuc["sinyal"],
                "guclu": sonuc["guclu"], "skor": sonuc["skor"],
                "fiyat": sonuc["fiyat"], "mesaj": telegram_mesaj(sonuc)})
    
    sinyaller.sort(key=lambda x: x["skor"], reverse=True)
    return jsonify({"taranan": len(hisseler), "sinyal_sayisi": len(sinyaller), "sinyaller": sinyaller})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
