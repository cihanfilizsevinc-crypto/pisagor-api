# ═══════════════════════════════════════════════════════════
#  PİSAGOR PRO API
#  Flask tabanlı, Make.com'dan çağrılır
#  Yahoo Finance'den gerçek veri çeker
#  Pisagor hesaplamalarını yapar
#  AL/SAT sinyali döndürür
# ═══════════════════════════════════════════════════════════

from flask import Flask, jsonify, request
import yfinance as yf
import pandas as pd
import numpy as np
import math

app = Flask(__name__)

# ─── PİSAGOR HESAPLAMALARI ───────────────────────────────────
def geometrik_oran():
    """
    v1 hatası: aritmetik ortalama → yanlış
    v2 düzeltme: geometrik ortalama
    """
    ucluler = [
        (5.0/3.0,  5.0/4.0),   # 3-4-5
        (13.0/5.0, 13.0/12.0), # 5-12-13
        (17.0/8.0, 17.0/15.0), # 8-15-17
        (25.0/7.0, 25.0/24.0), # 7-24-25
    ]
    log_a = sum(math.log(r[0]) for r in ucluler) / len(ucluler)
    log_b = sum(math.log(r[1]) for r in ucluler) / len(ucluler)
    return math.exp(log_a), math.exp(log_b)

def pisagor_ma(close):
    """Normalize edilmiş ağırlıklı ortalama"""
    agirliklar = [(5.0, 3), (13.0, 5), (17.0, 8), (25.0, 7)]
    toplam_agirlik = sum(a for a, _ in agirliklar)
    
    pma = pd.Series(0.0, index=close.index)
    for agirlik, periyot in agirliklar:
        sma = close.rolling(window=periyot).mean()
        pma += (agirlik / toplam_agirlik) * sma
    return pma

def hesapla_rsi(close, periyot=14):
    delta = close.diff()
    kazan = delta.where(delta > 0, 0.0).rolling(window=periyot).mean()
    kayip = (-delta.where(delta < 0, 0.0)).rolling(window=periyot).mean()
    rs = kazan / kayip
    return 100 - (100 / (1 + rs))

def hesapla_adx(high, low, close, periyot=14):
    """Gerçek ADX hesaplama"""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(window=periyot).mean()
    
    dm_plus  = (high - high.shift()).where((high - high.shift()) > (low.shift() - low), 0.0)
    dm_minus = (low.shift() - low).where((low.shift() - low) > (high - high.shift()), 0.0)
    dm_plus  = dm_plus.where(dm_plus > 0, 0.0)
    dm_minus = dm_minus.where(dm_minus > 0, 0.0)
    
    di_plus  = 100 * dm_plus.rolling(window=periyot).mean() / atr
    di_minus = 100 * dm_minus.rolling(window=periyot).mean() / atr
    
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
    adx = dx.rolling(window=periyot).mean()
    
    return adx, di_plus, di_minus

def analiz_et(ticker, periyot="3mo", lookback=50):
    """
    Hisse analizi yap, Pisagor sinyali döndür
    """
    try:
        # Veri çek
        hisse = yf.download(ticker, period=periyot, interval="1d", progress=False)
        if len(hisse) < lookback + 10:
            return {"hata": f"Yetersiz veri: {len(hisse)} bar"}
        
        close  = hisse["Close"].squeeze()
        high   = hisse["High"].squeeze()
        low    = hisse["Low"].squeeze()
        volume = hisse["Volume"].squeeze()
        
        # Pisagor hesaplamaları
        avg_ra, avg_rb = geometrik_oran()
        pma = pisagor_ma(close)
        
        atr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1).rolling(window=lookback).mean()
        
        b_upper = pma + atr * avg_ra
        b_mid_u = pma + atr * avg_rb
        b_mid_d = pma - atr * avg_rb
        b_lower = pma - atr * avg_ra
        
        # Trend
        trend_yukari = (close > pma) & (pma > pma.shift(3))
        trend_asagi  = (close < pma) & (pma < pma.shift(3))
        
        # RSI
        rsi = hesapla_rsi(close)
        
        # ADX
        adx, di_plus, di_minus = hesapla_adx(high, low, close)
        
        # Hacim filtresi
        vol_ort = volume.rolling(20).mean()
        vol_guclu = volume > vol_ort * 1.2
        
        # Pisagor momentum
        momentum = ((close - pma) / atr * 10).where(atr > 0, 0.0)
        
        # İvme (trend güçleniyor mu?)
        pma_hiz   = pma - pma.shift(3)
        pma_ivme  = pma_hiz - pma_hiz.shift(3)
        
        # ─── SİNYAL KOŞULLARI ───────────────────────────────
        # Crossover tespiti
        cross_up_mid   = (close > b_mid_d) & (close.shift() <= b_mid_d.shift())
        cross_dn_mid   = (close < b_mid_u) & (close.shift() >= b_mid_u.shift())
        cross_up_lower = (close > b_lower) & (close.shift() <= b_lower.shift())
        cross_dn_upper = (close < b_upper) & (close.shift() >= b_upper.shift())
        
        # Filtreler
        rsi_al_ok  = rsi < 70
        rsi_sat_ok = rsi > 35
        adx_ok     = adx >= 18
        di_bull    = di_plus > di_minus
        di_bear    = di_minus > di_plus
        
        # Normal sinyaller
        al_sinyal  = cross_up_mid & trend_yukari & rsi_al_ok & adx_ok & vol_guclu & di_bull
        sat_sinyal = cross_dn_mid & trend_asagi  & rsi_sat_ok & adx_ok & vol_guclu & di_bear
        
        # Güçlü sinyaller
        guclu_al  = cross_up_lower & trend_yukari & (rsi < 50) & adx_ok & vol_guclu & di_bull
        guclu_sat = cross_dn_upper & trend_asagi  & (rsi > 55) & adx_ok & vol_guclu & di_bear
        
        # Sinyal kalite skoru
        def skor_hesapla(idx, yon="al"):
            if yon == "al":
                return int(trend_yukari.iloc[idx]) + int(rsi_al_ok.iloc[idx]) + \
                       int(adx_ok.iloc[idx]) + int(vol_guclu.iloc[idx]) + int(di_bull.iloc[idx])
            else:
                return int(trend_asagi.iloc[idx]) + int(rsi_sat_ok.iloc[idx]) + \
                       int(adx_ok.iloc[idx]) + int(vol_guclu.iloc[idx]) + int(di_bear.iloc[idx])
        
        # Son bar değerleri
        son = -1
        son_fiyat   = round(float(close.iloc[son]), 2)
        son_pma     = round(float(pma.iloc[son]), 2)
        son_b_upper = round(float(b_upper.iloc[son]), 2)
        son_b_mid_u = round(float(b_mid_u.iloc[son]), 2)
        son_b_mid_d = round(float(b_mid_d.iloc[son]), 2)
        son_b_lower = round(float(b_lower.iloc[son]), 2)
        son_rsi     = round(float(rsi.iloc[son]), 1)
        son_adx     = round(float(adx.iloc[son]), 1)
        son_dip     = round(float(di_plus.iloc[son]), 1)
        son_dim     = round(float(di_minus.iloc[son]), 1)
        son_mom     = round(float(momentum.iloc[son]), 2)
        son_ivme    = float(pma_ivme.iloc[son])
        
        # Trend durumu
        t_yukari = bool(trend_yukari.iloc[son])
        t_asagi  = bool(trend_asagi.iloc[son])
        trend_txt = "YUKARI" if t_yukari else "ASAGI" if t_asagi else "YATAY"
        
        # Sinyal tespiti (son 2 bar)
        sinyal_tip   = "BEKLE"
        sinyal_guclu = False
        sinyal_skor  = 0
        tp_seviye    = None
        sl_seviye    = None
        
        if guclu_al.iloc[son]:
            sinyal_tip   = "AL"
            sinyal_guclu = True
            sinyal_skor  = skor_hesapla(son, "al")
            tp_seviye    = son_b_mid_u
            sl_seviye    = round(son_b_lower * 0.98, 2)
        elif al_sinyal.iloc[son]:
            sinyal_tip   = "AL"
            sinyal_guclu = False
            sinyal_skor  = skor_hesapla(son, "al")
            tp_seviye    = son_b_mid_u
            sl_seviye    = round(son_b_mid_d * 0.99, 2)
        elif guclu_sat.iloc[son]:
            sinyal_tip   = "SAT"
            sinyal_guclu = True
            sinyal_skor  = skor_hesapla(son, "sat")
            tp_seviye    = son_b_mid_d
            sl_seviye    = round(son_b_upper * 1.02, 2)
        elif sat_sinyal.iloc[son]:
            sinyal_tip   = "SAT"
            sinyal_guclu = False
            sinyal_skor  = skor_hesapla(son, "sat")
            tp_seviye    = son_b_mid_d
            sl_seviye    = round(son_b_mid_u * 1.01, 2)
        
        # Yıldız skoru
        yildiz = "★" * sinyal_skor + "☆" * (5 - sinyal_skor)
        
        return {
            "hisse"      : ticker,
            "fiyat"      : son_fiyat,
            "sinyal"     : sinyal_tip,
            "guclu"      : sinyal_guclu,
            "skor"       : sinyal_skor,
            "yildiz"     : yildiz,
            "tp"         : tp_seviye,
            "sl"         : sl_seviye,
            "trend"      : trend_txt,
            "rsi"        : son_rsi,
            "adx"        : son_adx,
            "di_plus"    : son_dip,
            "di_minus"   : son_dim,
            "momentum"   : son_mom,
            "ivme"       : "GUCLENIYOR" if son_ivme > 0 and t_yukari else "ZAYIFLIYOR" if son_ivme < 0 and t_asagi else "SABIT",
            "pisagor_ma" : son_pma,
            "ust_direnc" : son_b_upper,
            "ara_ust"    : son_b_mid_u,
            "ara_alt"    : son_b_mid_d,
            "alt_destek" : son_b_lower,
            "geo_oran_a" : round(avg_ra, 3),
            "geo_oran_b" : round(avg_rb, 3),
        }
    except Exception as e:
        return {"hata": str(e), "hisse": ticker}

def telegram_mesaj_olustur(sonuc):
    """Telegram için okunabilir mesaj oluştur"""
    if "hata" in sonuc:
        return None
    if sonuc["sinyal"] == "BEKLE":
        return None
    
    guclu_prefix = "💪 GÜÇLÜ " if sonuc["guclu"] else ""
    sinyal_emoji = "🟢" if sonuc["sinyal"] == "AL" else "🔴"
    trend_emoji  = "📈" if sonuc["trend"] == "YUKARI" else "📉" if sonuc["trend"] == "ASAGI" else "➡️"
    
    mesaj = f"""{sinyal_emoji} *{guclu_prefix}{sonuc['sinyal']} SİNYALİ* — {sonuc['hisse']}
{sonuc['yildiz']}

💰 Fiyat: *{sonuc['fiyat']}₺*
{trend_emoji} Trend: {sonuc['trend']}

📊 *Teknik Göstergeler*
• RSI: {sonuc['rsi']}
• ADX: {sonuc['adx']} {"✅" if sonuc['adx'] >= 18 else "⚠️"}
• DI+/DI-: {sonuc['di_plus']} / {sonuc['di_minus']}
• Momentum: {sonuc['momentum']}
• İvme: {sonuc['ivme']}

📐 *Pisagor Seviyeleri*
• Üst Direnç: {sonuc['ust_direnc']}
• Ara Üst: {sonuc['ara_ust']}
• Pisagor MA: {sonuc['pisagor_ma']}
• Ara Alt: {sonuc['ara_alt']}
• Alt Destek: {sonuc['alt_destek']}"""

    if sonuc["tp"]:
        mesaj += f"\n\n🎯 *Hedef Fiyat (TP)*: {sonuc['tp']}₺"
    if sonuc["sl"]:
        mesaj += f"\n🛑 *Stop Loss (SL)*: {sonuc['sl']}₺"
    
    mesaj += "\n\n⚠️ _Bu bir yatırım tavsiyesi değildir. Teknik gösterge bilgisidir._"
    return mesaj

# ═══════════════════════════════════════════════════════════
# API ENDPOINTLER
# ═══════════════════════════════════════════════════════════

@app.route("/")
def anasayfa():
    return jsonify({
        "sistem" : "Pisagor PRO API",
        "versiyon": "3.0",
        "endpointler": {
            "/analiz/<ticker>": "Tek hisse analizi (örn: /analiz/THYAO.IS)",
            "/sinyal/<ticker>": "Sadece sinyal varsa döner",
            "/tarama"         : "Birden fazla hisse tara (POST)",
        }
    })

@app.route("/analiz/<ticker>")
def analiz(ticker):
    """Tek hisse tam analiz"""
    if not ticker.endswith(".IS"):
        ticker = ticker + ".IS"
    sonuc = analiz_et(ticker)
    return jsonify(sonuc)

@app.route("/sinyal/<ticker>")
def sinyal(ticker):
    """Sadece sinyal varsa mesaj döner — Make.com bunu kullanır"""
    if not ticker.endswith(".IS"):
        ticker = ticker + ".IS"
    sonuc = analiz_et(ticker)
    
    if "hata" in sonuc or sonuc["sinyal"] == "BEKLE":
        return jsonify({"sinyal": False, "mesaj": None})
    
    mesaj = telegram_mesaj_olustur(sonuc)
    return jsonify({
        "sinyal"  : True,
        "tip"     : sonuc["sinyal"],
        "guclu"   : sonuc["guclu"],
        "skor"    : sonuc["skor"],
        "hisse"   : ticker,
        "fiyat"   : sonuc["fiyat"],
        "mesaj"   : mesaj,
        "detay"   : sonuc
    })

@app.route("/tarama", methods=["POST"])
def tarama():
    """
    Birden fazla hisse tara
    POST body: {"hisseler": ["THYAO", "GARAN", "ASELS"]}
    """
    data = request.json or {}
    hisseler = data.get("hisseler", [
        "THYAO", "GARAN", "ASELS", "KCHOL", "SAHOL",
        "SISE",  "AKBNK", "YKBNK", "ISCTR", "BIMAS",
        "EREGL", "TUPRS", "PETKM", "KOZAL", "FROTO"
    ])
    
    sinyaller = []
    tum_sonuclar = []
    
    for h in hisseler:
        ticker = h if h.endswith(".IS") else h + ".IS"
        sonuc = analiz_et(ticker)
        tum_sonuclar.append(sonuc)
        
        if "hata" not in sonuc and sonuc["sinyal"] != "BEKLE":
            mesaj = telegram_mesaj_olustur(sonuc)
            sinyaller.append({
                "hisse"  : h,
                "sinyal" : sonuc["sinyal"],
                "guclu"  : sonuc["guclu"],
                "skor"   : sonuc["skor"],
                "fiyat"  : sonuc["fiyat"],
                "mesaj"  : mesaj
            })
    
    # Skora göre sırala
    sinyaller.sort(key=lambda x: x["skor"], reverse=True)
    
    return jsonify({
        "taranan"       : len(hisseler),
        "sinyal_sayisi" : len(sinyaller),
        "sinyaller"     : sinyaller,
        "tum_sonuclar"  : tum_sonuclar
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
