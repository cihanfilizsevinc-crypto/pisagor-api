from flask import Flask, jsonify, request
import yfinance as yf
import pandas as pd
import numpy as np
import math
import requests
import threading
import time
import os
import xml.etree.ElementTree as ET
from datetime import datetime
import io

app = Flask(__name__)

# ─── GLOBAL CACHE ─────────────────────────────────────────────────────
cache = {
    "sonuc": None, "guncelleme": None,
    "durum": "bekleniyor", "taranan": 0, "toplam": 0
}
cache_lock = threading.Lock()
sektor_cache = {"sonuc": None, "guncelleme": None}
sektor_lock = threading.Lock()
korelasyon_cache = {}
korelasyon_lock = threading.Lock()
kap_goruldu = set()
kap_lock = threading.Lock()
rapor_cache = {}
rapor_cache_lock = threading.Lock()

# ─── AYARLAR ──────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")

# ─── SEKTÖR GRUPLARI ──────────────────────────────────────────────────
SEKTORLER = {
    "Bankacılık": ["AKBNK","GARAN","HALKB","ISCTR","SKBNK","TSKB","VAKBN","YKBNK","ALBRK"],
    "Havacılık": ["THYAO","PGSUS"],
    "Enerji": ["AKSEN","AYDEM","ENJSA","EUPWR","ODAS","ZOREN","AYGAZ","TUPRS","PETKM"],
    "Teknoloji": ["LOGO","TTKOM","TCELL","NETAS","ARENA","INDES"],
    "Perakende": ["BIMAS","MGROS","SOKM","BIZIM"],
    "Otomotiv": ["FROTO","TOASO","OTKAR","ASUZU"],
    "Demir Çelik": ["EREGL","KRDMD","KRDMA","KRDMB","CEMTS"],
    "GYO": ["EKGYO","TRGYO","ISGYO","VKGYO","ALGYO"],
    "Sigorta": ["AKGRT","ANSGR","RAYSG"],
    "Gıda": ["ULKER","CCOLA","AEFES","TATGD","BANVT"],
    "Kimya": ["ALKIM","SASA","GUBRF","COFAZ","BAGFS"],
    "Savunma": ["ASELS","ROKET","HATEK"],
    "Cam & Seramik": ["SISE","TRKCM","ANACM","CIMSA","AKCNS"],
    "Holding": ["KCHOL","SAHOL","DOHOL","GLYHO","TKFEN"],
}

# ─── BIST HİSSELERİ ───────────────────────────────────────────────────
BIST_TUMU = [
    "ACSEL","ADEL","ADESE","ADGYO","AEFES","AFYON","AGESA","AGROT","AGYO",
    "AHGAZ","AKBNK","AKCNS","AKFEN","AKFGY","AKGRT","AKMGY","AKSA","AKSEN",
    "AKSGY","AKSUE","AKTIF","ALARK","ALBRK","ALCAR","ALFAS","ALGYO","ALKA",
    "ALKIM","ALKLC","ALMAD","ALTINS","ALTIN","ALYAG","ANELE","ANGEN","ANHYT",
    "ANSGR","ARASE","ARCLK","ARDYZ","ARENA","ARSAN","ARTE","ARTMS","ASCEL",
    "ASELS","ASGYO","ASTOR","ASUZU","ATAGY","ATAKP","ATATP","ATEKS","ATLAS",
    "AVOD","AVTUR","AYCES","AYDEM","AYEN","AYES","AYGAZ","AZTEK","BAGFS",
    "BAKAB","BALAT","BANVT","BARMA","BASCM","BASGZ","BAYRK","BEGYO","BERA",
    "BEYAZ","BFREN","BIGCH","BIMAS","BIOEN","BIZIM","BJKAS","BKFIN","BLCYT",
    "BMSCH","BMSTL","BNTAS","BOBET","BORLS","BORSK","BOSSA","BRISA","BRKO",
    "BRMEN","BRKVY","BRLSM","BRSAN","BRYAT","BSOKE","BTCIM","BUCIM","BURCE",
    "BURVA","BVSAN","CAFER","CANTE","CCOLA","CELHA","CEMAS","CEMTS","CEOEM",
    "CGCAM","CIMSA","CLEBI","CMBTN","CMENT","COFAZ","CRDFA","CRFSA","CUSAN",
    "CVKMD","CYMPA","DAGHL","DAGI","DAPGM","DARDL","DCTTR","DENGE","DERHL",
    "DERIM","DESPC","DEVA","DGATE","DGGYO","DGKLB","DGNMO","DITAS","DMSAS",
    "DNISI","DOAS","DOBUR","DOCO","DOGUB","DOHOL","DOKTA","DURDO","DYOBY",
    "DZGYO","ECILC","ECZYT","EDIP","EGGUB","EGPRO","EGSER","EKSUN","ELITE",
    "EMKEL","EMNIS","ENJSA","ENKAI","ENSRI","EPLAS","ERBOS","EREGL","ERSU",
    "ESCAR","ESCOM","ESEN","ETILR","ETYAT","EUHOL","EUKYO","EUPWR","EUREN",
    "EUYO","EVYES","FADE","FENER","FMIZP","FONET","FORMT","FORTE","FRIGO",
    "FROTO","FZLGY","GARAN","GARFA","GEDIK","GEDZA","GENIL","GENTS","GEREL",
    "GLYHO","GMTAS","GOKNR","GOLTS","GOODY","GOZDE","GRSEL","GRTRK","GSDDE",
    "GSDHO","GSRAY","GUBRF","GUNDG","GUSGR","GVZGY","HALKB","HATEK","HDFGS",
    "HEDEF","HEKTS","HKTM","HLGYO","HOROZ","HRKET","HTTBT","HUNER","HURGZ",
    "ICBCT","ICUGS","IDGYO","IEYHO","IGDAS","IHAAS","IHEVA","IHGZT","IHLAS",
    "IHLGM","IHYAY","IMASM","INDES","INFO","INGRM","INTEM","INVEO","IPEKE",
    "ISBIR","ISCTR","ISYAT","ITTFK","IZFAS","IZMDC","JANTS","KAPLM","KAREL",
    "KARSN","KARTN","KAYSE","KBORU","KCAER","KCHOL","KENT","KERVN","KERVT",
    "KGYO","KIMMR","KLGYO","KLMSN","KLNMA","KLRHO","KLSER","KMPUR","KNFRT",
    "KONYA","KORDS","KOZAA","KOZAL","KRDMA","KRDMB","KRDMD","KRGYO","KRONT",
    "KRPLS","KRSTL","KRTEK","KSTUR","KTLEV","KUTPO","LATEK","LKMNH","LKMR",
    "LOGO","LRSHO","LUKSK","MAALT","MACKO","MAGEN","MAKIM","MAKTK","MANAS",
    "MARBL","MAVI","MEGAP","MEKAG","MERKO","METRO","MGROS","MHRGY","MIPAZ",
    "MNDRS","MNDTR","MOBTL","MOGAN","MSGYO","MTRKS","MZHLD","NATEN","NETAS",
    "NIBAS","NILYT","NTHOL","NTTUR","NUGYO","NUHCM","OBAMS","OBASE","ODAS",
    "ONCSM","ONRYT","ORCAY","ORGE","ORMA","OSMEN","OSTIM","OTKAR","OYAKC",
    "OYYAT","OZGYO","OZKGY","OZRDN","OZSUB","PAGYO","PAMEL","PAPIL","PARSN",
    "PASEU","PCILT","PEGYO","PEKGY","PENGD","PENTA","PETKM","PETUN","PGSUS",
    "PINSU","PKART","PKENT","PLTUR","PNLSN","POLHO","POLTK","PRDGS","PRZMA",
    "PSDTC","PSGYO","PTOFS","RALYH","RAYSG","RYGYO","SAMAT","SANEL","SANFM",
    "SANKO","SARKY","SASA","SAYAS","SDTTR","SEGYO","SEKFK","SEKUR","SELEC",
    "SELGD","SELVA","SEYKM","SILVR","SISE","SKBNK","SKYLP","SMART","SNGYO",
    "SNICA","SNKRN","SODSN","SOKM","SONME","SRVGY","SUMAS","SUNTK","SURGY",
    "SUWEN","TACTR","TATGD","TCELL","TDGYO","TEKTU","TETMT","TEZOL","THYAO",
    "TIRE","TKFEN","TKNSA","TLMAN","TMSN","TOASO","TRCAS","TRGYO","TRILC",
    "TSGYO","TSKB","TSPOR","TTKOM","TTRAK","TUCLK","TUKAS","TUPRS","TURSG",
    "UFUK","ULKER","ULUFA","ULUSE","ULUUN","UNLU","USAK","USDTN","VAKBN",
    "VAKFN","VAKKO","VANGD","VBTYZ","VERTU","VESBE","VESTL","VKGYO","VKFYO",
    "VRGYO","YATAS","YAYLA","YBTAS","YGYO","YIGIT","YKBNK","YKSLN","YONGA",
    "YUNSA","ZEDUR","ZOREN","ZRGYO"
]

# ─── VERİ ÇEKME ───────────────────────────────────────────────────────
def veri_cek(ticker):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=6mo&interval=1d"
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv = result["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open": ohlcv["open"], "high": ohlcv["high"],
            "low": ohlcv["low"], "close": ohlcv["close"],
            "volume": ohlcv["volume"],
        }, index=pd.to_datetime(timestamps, unit="s"))
        df = df.dropna()
        if len(df) > 30:
            return df
    except:
        pass
    try:
        hisse = yf.Ticker(ticker)
        df = hisse.history(period="6mo", interval="1d")
        if len(df) > 30:
            df.columns = [c.lower() for c in df.columns]
            return df
    except:
        pass
    return None

# ─── SEKTÖR ROTASYONU ─────────────────────────────────────────────────
def sektor_performans_hesapla():
    """Her sektörün son 1 hafta, 1 ay performansını hesapla"""
    sonuclar = {}

    for sektor, hisseler in SEKTORLER.items():
        haftalik = []
        aylik = []

        for h in hisseler:
            try:
                ticker = yf.Ticker(f"{h}.IS")
                df = ticker.history(period="1mo", interval="1d")
                if df is not None and len(df) > 5:
                    close = df["Close"].dropna()
                    if len(close) >= 5:
                        haftalik_perf = (close.iloc[-1] / close.iloc[-5] - 1) * 100
                        aylik_perf = (close.iloc[-1] / close.iloc[0] - 1) * 100
                        haftalik.append(haftalik_perf)
                        aylik.append(aylik_perf)
            except:
                pass
            time.sleep(0.2)

        if haftalik:
            sonuclar[sektor] = {
                "haftalik": round(np.mean(haftalik), 2),
                "aylik": round(np.mean(aylik), 2),
                "hisse_sayisi": len(hisseler),
                "veri_sayisi": len(haftalik)
            }

    # Performansa göre sırala
    siralanmis = sorted(sonuclar.items(), key=lambda x: x[1]["haftalik"], reverse=True)
    
    return {
        "hesaplama_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "en_iyi_sektor": siralanmis[0][0] if siralanmis else None,
        "en_kotu_sektor": siralanmis[-1][0] if siralanmis else None,
        "sektorler": dict(siralanmis)
    }

def arka_plan_sektor():
    """Her 4 saatte bir sektör analizi yap"""
    time.sleep(60)  # İlk 1 dakika bekle
    while True:
        try:
            sonuc = sektor_performans_hesapla()
            with sektor_lock:
                sektor_cache["sonuc"] = sonuc
                sektor_cache["guncelleme"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Sektör rotasyonu Telegram'a gönder
            mesaj = sektor_telegram_mesaj(sonuc)
            if mesaj:
                telegram_gonder(mesaj)
        except:
            pass
        time.sleep(14400)  # 4 saat

def sektor_telegram_mesaj(sonuc):
    if not sonuc or not sonuc.get("sektorler"):
        return None
    
    sektorler = sonuc["sektorler"]
    mesaj = f"📊 *SEKTÖR ROTASYONU*\n_{sonuc['hesaplama_tarihi']}_\n\n"
    
    # En iyi 3
    mesaj += "🟢 *En Güçlü Sektörler:*\n"
    for i, (s, v) in enumerate(list(sektorler.items())[:3]):
        mesaj += f"{i+1}. {s}: %{v['haftalik']:+.1f} (hafta) | %{v['aylik']:+.1f} (ay)\n"
    
    # En kötü 3
    mesaj += "\n🔴 *En Zayıf Sektörler:*\n"
    items = list(sektorler.items())
    for i, (s, v) in enumerate(items[-3:]):
        mesaj += f"{len(items)-2+i}. {s}: %{v['haftalik']:+.1f} (hafta) | %{v['aylik']:+.1f} (ay)\n"
    
    return mesaj

# ─── KORELASYON ANALİZİ ───────────────────────────────────────────────
def korelasyon_hesapla(hisse1, hisse2, periyot=60):
    """İki hisse arasındaki korelasyonu hesapla"""
    cache_key = f"{hisse1}_{hisse2}"
    
    with korelasyon_lock:
        if cache_key in korelasyon_cache:
            return korelasyon_cache[cache_key]
    
    try:
        df1 = veri_cek(f"{hisse1}.IS")
        df2 = veri_cek(f"{hisse2}.IS")
        
        if df1 is None or df2 is None:
            return None
        
        close1 = df1["close"].squeeze().astype(float)
        close2 = df2["close"].squeeze().astype(float)
        
        # Ortak tarihleri al
        ortak = close1.index.intersection(close2.index)
        if len(ortak) < 20:
            return None
        
        c1 = close1[ortak].tail(periyot)
        c2 = close2[ortak].tail(periyot)
        
        # Günlük getiri korelasyonu
        r1 = c1.pct_change().dropna()
        r2 = c2.pct_change().dropna()
        
        korel = round(float(r1.corr(r2)), 3)
        
        sonuc = {
            "hisse1": hisse1, "hisse2": hisse2,
            "korelasyon": korel,
            "guc": "ÇOK GÜÇLÜ" if abs(korel) > 0.8 else "GÜÇLÜ" if abs(korel) > 0.6 else "ORTA" if abs(korel) > 0.4 else "ZAYIF",
            "yön": "POZİTİF" if korel > 0 else "NEGATİF",
            "periyot_gun": periyot
        }
        
        with korelasyon_lock:
            korelasyon_cache[cache_key] = sonuc
            korelasyon_cache[f"{hisse2}_{hisse1}"] = sonuc
        
        return sonuc
    except:
        return None

def sektor_korelasyon(sektor_adi):
    """Bir sektördeki tüm hisselerin korelasyon matrisi"""
    if sektor_adi not in SEKTORLER:
        return None
    
    hisseler = SEKTORLER[sektor_adi]
    sonuclar = []
    
    for i in range(len(hisseler)):
        for j in range(i+1, len(hisseler)):
            korel = korelasyon_hesapla(hisseler[i], hisseler[j])
            if korel:
                sonuclar.append(korel)
    
    sonuclar.sort(key=lambda x: abs(x["korelasyon"]), reverse=True)
    return {
        "sektor": sektor_adi,
        "hisseler": hisseler,
        "korelasyonlar": sonuclar[:10]
    }

def en_yuksek_korelasyon(hisse_kodu, top=5):
    """Bir hisseyle en yüksek korelasyonlu diğer hisseleri bul"""
    # Aynı sektördeki hisselere bak
    sektor = None
    for s, hisseler in SEKTORLER.items():
        if hisse_kodu in hisseler:
            sektor = s
            break
    
    karsilastir = []
    if sektor:
        karsilastir = [h for h in SEKTORLER[sektor] if h != hisse_kodu]
    else:
        # Sektör bulunamazsa BIST100'den örnekle
        karsilastir = ["THYAO","GARAN","ASELS","KCHOL","BIMAS","EREGL","TUPRS","AKBNK","ISCTR","SISE"]
    
    sonuclar = []
    for h in karsilastir[:10]:
        korel = korelasyon_hesapla(hisse_kodu, h)
        if korel:
            sonuclar.append(korel)
    
    sonuclar.sort(key=lambda x: abs(x["korelasyon"]), reverse=True)
    return sonuclar[:top]

# ─── TEKNİK GÖSTERGELER ───────────────────────────────────────────────
def geometrik_oran():
    ucluler = [(5.0/3.0,5.0/4.0),(13.0/5.0,13.0/12.0),(17.0/8.0,17.0/15.0),(25.0/7.0,25.0/24.0)]
    log_a = sum(math.log(r[0]) for r in ucluler)/len(ucluler)
    log_b = sum(math.log(r[1]) for r in ucluler)/len(ucluler)
    return math.exp(log_a), math.exp(log_b)

def pisagor_ma(close):
    agirliklar = [(5.0,3),(13.0,5),(17.0,8),(25.0,7)]
    toplam = sum(a for a,_ in agirliklar)
    pma = pd.Series(0.0, index=close.index)
    for agirlik, periyot in agirliklar:
        pma += (agirlik/toplam)*close.rolling(window=periyot).mean()
    return pma

def hesapla_rsi(close, periyot=14):
    delta = close.diff()
    kazan = delta.where(delta>0,0.0).rolling(window=periyot).mean()
    kayip = (-delta.where(delta<0,0.0)).rolling(window=periyot).mean()
    return 100-(100/(1+kazan/kayip))

def hesapla_macd(close, hizli=12, yavas=26, sinyal=9):
    ema_h = close.ewm(span=hizli, adjust=False).mean()
    ema_y = close.ewm(span=yavas, adjust=False).mean()
    macd = ema_h - ema_y
    sig = macd.ewm(span=sinyal, adjust=False).mean()
    return macd, sig, macd-sig

def hesapla_bollinger(close, periyot=20, std_carp=2):
    orta = close.rolling(window=periyot).mean()
    std = close.rolling(window=periyot).std()
    return orta+std_carp*std, orta, orta-std_carp*std

def hesapla_adx(high, low, close, periyot=14):
    tr = pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
    atr = tr.rolling(window=periyot).mean()
    dm_p = (high-high.shift()).where((high-high.shift())>(low.shift()-low),0.0).clip(lower=0)
    dm_m = (low.shift()-low).where((low.shift()-low)>(high-high.shift()),0.0).clip(lower=0)
    di_p = 100*dm_p.rolling(window=periyot).mean()/atr
    di_m = 100*dm_m.rolling(window=periyot).mean()/atr
    dx = 100*(di_p-di_m).abs()/(di_p+di_m)
    return dx.rolling(window=periyot).mean(), di_p, di_m

# ─── HABER & AI ───────────────────────────────────────────────────────
def haber_cek(hisse_kodu, max_haber=5):
    try:
        url = f"https://news.google.com/rss/search?q={hisse_kodu}+hisse+borsa&hl=tr&gl=TR&ceid=TR:tr"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            haberler = []
            for item in root.findall(".//item")[:max_haber]:
                baslik = item.find("title"); tarih = item.find("pubDate")
                if baslik is not None and baslik.text:
                    haberler.append({"baslik": baslik.text, "tarih": tarih.text if tarih is not None else ""})
            return haberler
    except:
        pass
    return []

def duygu_analizi(hisse_kodu, haberler):
    if not haberler or not ANTHROPIC_KEY:
        return None
    haber_metni = "\n".join([f"- {h['baslik']}" for h in haberler[:5]])
    prompt = f"""{hisse_kodu} haberleri:\n{haber_metni}\n\nSadece:\nDUYGU: [POZİTİF/NEGATİF/NÖTR]\nPUAN: [-10/+10]\nÖZET: [tek cümle]"""
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 100, "messages": [{"role": "user", "content": prompt}]},
            timeout=15)
        if r.status_code == 200:
            yanit = r.json()["content"][0]["text"].strip()
            duygu="NÖTR"; puan=0; ozet=""
            for satir in yanit.split("\n"):
                if "DUYGU:" in satir: duygu=satir.split("DUYGU:")[-1].strip()
                elif "PUAN:" in satir:
                    try: puan=int(satir.split("PUAN:")[-1].strip())
                    except: puan=0
                elif "ÖZET:" in satir: ozet=satir.split("ÖZET:")[-1].strip()
            return {"duygu":duygu,"puan":puan,"ozet":ozet}
    except:
        pass
    return None

def ai_yorum(sonuc):
    if not ANTHROPIC_KEY:
        return None
    try:
        prompt = f"""Borsa analisti: {sonuc['hisse']} için 2 cümle teknik yorum. Türkçe. Tavsiye verme.
RSI:{sonuc['rsi']} ADX:{sonuc['adx']} MACD:{sonuc.get('macd_durum','')} Trend:{sonuc['trend']}"""
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 150, "messages": [{"role": "user", "content": prompt}]},
            timeout=15)
        if r.status_code == 200:
            return r.json()["content"][0]["text"].strip()
    except:
        pass
    return None

def takas_cek(hisse_kodu):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
    try:
        url = f"https://www.borsaistanbul.com/api/data/equity/investor?symbol={hisse_kodu}"
        r = requests.get(url, headers={**headers, "Referer": "https://www.borsaistanbul.com/"}, timeout=10)
        if r.status_code == 200 and r.json():
            data = r.json()
            son = data[-1] if isinstance(data, list) else data
            yabanci = float(son.get("foreignRatio", son.get("yabanci", 0)))
            net = float(son.get("netForeign", son.get("net", 0)))
            return {"hisse": hisse_kodu, "yabanci_oran": round(yabanci, 2),
                    "net_yabanci": round(net, 0), "durum": "ALICI" if net>0 else "SATICI" if net<0 else "NÖTR"}
    except:
        pass
    return None

def finansal_rapor_analiz(hisse_kodu):
    with rapor_cache_lock:
        if hisse_kodu in rapor_cache:
            return rapor_cache[hisse_kodu]
    return None

# ─── ANALİZ ───────────────────────────────────────────────────────────
def analiz_et(ticker, lookback=50):
    df = veri_cek(ticker)
    if df is None or len(df) < lookback+10:
        return {"hata": f"Veri yok: {ticker}", "hisse": ticker}
    close=df["close"].squeeze().astype(float); high=df["high"].squeeze().astype(float)
    low=df["low"].squeeze().astype(float); volume=df["volume"].squeeze().astype(float)
    avg_ra,avg_rb=geometrik_oran(); pma=pisagor_ma(close)
    atr=pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1).rolling(window=lookback).mean()
    b_up=pma+atr*avg_ra; b_mu=pma+atr*avg_rb; b_md=pma-atr*avg_rb; b_lo=pma-atr*avg_ra
    trend_up=(close>pma)&(pma>pma.shift(3)); trend_down=(close<pma)&(pma<pma.shift(3))
    rsi=hesapla_rsi(close); adx,dip,dim=hesapla_adx(high,low,close)
    macd_line,macd_sig,macd_hist=hesapla_macd(close); boll_ust,boll_mid,boll_alt=hesapla_bollinger(close)
    vol_ok=volume>volume.rolling(20).mean()*1.2
    rsi_al=rsi<70; rsi_sat=rsi>35; adx_ok=adx>=18; di_bull=dip>dim; di_bear=dim>dip
    macd_bull=macd_line>macd_sig; macd_bear=macd_line<macd_sig
    cross_up_mid=(close>b_md)&(close.shift()<=b_md.shift()); cross_dn_mid=(close<b_mu)&(close.shift()>=b_mu.shift())
    cross_up_lower=(close>b_lo)&(close.shift()<=b_lo.shift()); cross_dn_upper=(close<b_up)&(close.shift()>=b_up.shift())
    al_sinyal=cross_up_mid&trend_up&rsi_al&adx_ok&vol_ok&di_bull&macd_bull
    sat_sinyal=cross_dn_mid&trend_down&rsi_sat&adx_ok&vol_ok&di_bear&macd_bear
    guclu_al=cross_up_lower&trend_up&(rsi<50)&adx_ok&vol_ok&di_bull&macd_bull
    guclu_sat=cross_dn_upper&trend_down&(rsi>55)&adx_ok&vol_ok&di_bear&macd_bear
    s=-1
    t_up=bool(trend_up.iloc[s]); t_down=bool(trend_down.iloc[s])
    trend_txt="YUKARI" if t_up else "ASAGI" if t_down else "YATAY"
    son_fiyat=round(float(close.iloc[s]),2); son_pma=round(float(pma.iloc[s]),2)
    son_b_up=round(float(b_up.iloc[s]),2); son_b_mu=round(float(b_mu.iloc[s]),2)
    son_b_md=round(float(b_md.iloc[s]),2); son_b_lo=round(float(b_lo.iloc[s]),2)
    son_rsi=round(float(rsi.iloc[s]),1); son_adx=round(float(adx.iloc[s]),1)
    son_dip=round(float(dip.iloc[s]),1); son_dim=round(float(dim.iloc[s]),1)
    son_macd_hist=round(float(macd_hist.iloc[s]),3)
    son_boll_ust=round(float(boll_ust.iloc[s]),2); son_boll_alt=round(float(boll_alt.iloc[s]),2)
    boll_pos="ÜST BANT" if close.iloc[s]>boll_ust.iloc[s] else "ALT BANT" if close.iloc[s]<boll_alt.iloc[s] else "ORTA BANT"
    macd_durum="POZİTİF ↑" if son_macd_hist>0 else "NEGATİF ↓"
    sinyal_tip="BEKLE"; sinyal_guclu=False; sinyal_skor=0; tp_sev=None; sl_sev=None
    def skor(trend,ri,ai,vi,di):
        return int(trend)+int(bool(ri.iloc[s]))+int(bool(ai.iloc[s]))+int(bool(vi.iloc[s]))+int(bool(di.iloc[s]))
    if bool(guclu_al.iloc[s]):
        sinyal_tip="AL"; sinyal_guclu=True; sinyal_skor=skor(t_up,rsi_al,adx_ok,vol_ok,di_bull)
        tp_sev=son_b_mu; sl_sev=round(son_b_lo*0.98,2)
    elif bool(al_sinyal.iloc[s]):
        sinyal_tip="AL"; sinyal_skor=skor(t_up,rsi_al,adx_ok,vol_ok,di_bull)
        tp_sev=son_b_mu; sl_sev=round(son_b_md*0.99,2)
    elif bool(guclu_sat.iloc[s]):
        sinyal_tip="SAT"; sinyal_guclu=True; sinyal_skor=skor(t_down,rsi_sat,adx_ok,vol_ok,di_bear)
        tp_sev=son_b_md; sl_sev=round(son_b_up*1.02,2)
    elif bool(sat_sinyal.iloc[s]):
        sinyal_tip="SAT"; sinyal_skor=skor(t_down,rsi_sat,adx_ok,vol_ok,di_bear)
        tp_sev=son_b_md; sl_sev=round(son_b_mu*1.01,2)
    
    # Sektör bilgisi ekle
    sektor = next((s for s, h in SEKTORLER.items() if ticker.replace(".IS","") in h), "Diğer")
    
    return {
        "hisse":ticker,"fiyat":son_fiyat,"sinyal":sinyal_tip,"guclu":sinyal_guclu,
        "skor":sinyal_skor,"yildiz":"★"*sinyal_skor+"☆"*(5-sinyal_skor),
        "tp":tp_sev,"sl":sl_sev,"trend":trend_txt,"sektor":sektor,
        "rsi":son_rsi,"adx":son_adx,"di_plus":son_dip,"di_minus":son_dim,
        "macd_hist":son_macd_hist,"macd_durum":macd_durum,
        "boll_ust":son_boll_ust,"boll_alt":son_boll_alt,"boll_pozisyon":boll_pos,
        "pisagor_ma":son_pma,"ust_direnc":son_b_up,"ara_ust":son_b_mu,
        "ara_alt":son_b_md,"alt_destek":son_b_lo,"bar_sayisi":len(df)
    }

# ─── TELEGRAM ─────────────────────────────────────────────────────────
def telegram_mesaj(sonuc, ai_yorum_metni=None, haber_analizi=None, takas=None, korelasyonlar=None):
    guclu="💪 GÜÇLÜ " if sonuc["guclu"] else ""
    emoji="🟢" if sonuc["sinyal"]=="AL" else "🔴"
    trend_emoji="📈" if sonuc["trend"]=="YUKARI" else "📉" if sonuc["trend"]=="ASAGI" else "➡️"
    macd_emoji="📊↑" if sonuc.get("macd_hist",0)>0 else "📊↓"
    sektor = sonuc.get("sektor","")
    
    mesaj=f"""{emoji} *{guclu}{sonuc['sinyal']} SİNYALİ* — {sonuc['hisse']}
{sonuc['yildiz']} | 🏭 {sektor}

💰 Fiyat: *{sonuc['fiyat']}₺*
{trend_emoji} Trend: {sonuc['trend']}

📊 *Teknik*
• RSI: {sonuc['rsi']} {"🔥" if sonuc['rsi']<30 else "✅" if sonuc['rsi']<70 else "⚠️"} | ADX: {sonuc['adx']} {"✅" if sonuc['adx']>=18 else "⚠️"}
• MACD: {sonuc.get('macd_durum','N/A')} {macd_emoji}
• Bollinger: {sonuc.get('boll_pozisyon','N/A')}

📐 Üst: {sonuc['ust_direnc']} | MA: {sonuc['pisagor_ma']} | Alt: {sonuc['alt_destek']}"""

    if sonuc["tp"]:
        mesaj+=f"\n🎯 TP: {sonuc['tp']}₺  🛑 SL: {sonuc['sl']}₺"
    
    if takas:
        de="🟢" if takas.get("durum")=="ALICI" else "🔴" if takas.get("durum")=="SATICI" else "⚪"
        mesaj+=f"\n\n💱 Takas: Yabancı %{takas.get('yabanci_oran','?')} {de}"
    
    if haber_analizi:
        de="✅" if haber_analizi["puan"]>3 else "⚠️" if haber_analizi["puan"]<-3 else "➡️"
        mesaj+=f"\n📰 Haber: {haber_analizi['duygu']} {de} ({haber_analizi['puan']:+d})"
        if haber_analizi.get("ozet"):
            mesaj+=f"\n_{haber_analizi['ozet']}_"
    
    # Korelasyon uyarısı
    if korelasyonlar:
        guclu_korel = [k for k in korelasyonlar if abs(k["korelasyon"]) > 0.7]
        if guclu_korel:
            diger = guclu_korel[0]["hisse2"] if guclu_korel[0]["hisse1"] == sonuc["hisse"].replace(".IS","") else guclu_korel[0]["hisse1"]
            mesaj+=f"\n\n🔗 *Korelasyon*: {diger} ile %{abs(guclu_korel[0]['korelasyon'])*100:.0f} uyumlu hareket ediyor"
    
    if ai_yorum_metni:
        mesaj+=f"\n\n🤖 *AI:* _{ai_yorum_metni}_"
    
    mesaj+="\n\n⚠️ _Yatırım tavsiyesi değildir._"
    return mesaj

def telegram_gonder(mesaj):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        r=requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":mesaj,"parse_mode":"Markdown"},timeout=10)
        return r.status_code==200
    except:
        return False

# ─── KAP TAKİBİ ───────────────────────────────────────────────────────
KAP_ONEMLI=["TEMETTÜ","SERMAYE","BİRLEŞME","SATIN","FİNANSAL","GENEL KURUL","HAK KULLANIM","BEDELSIZ","KÂR PAYI"]

def kap_cek():
    try:
        headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://www.kap.org.tr/"}
        r=requests.get("https://www.kap.org.tr/tr/api/disclosures",headers=headers,timeout=15)
        if r.status_code==200:
            return r.json()
    except:
        pass
    return None

def kap_mesaj(b):
    hisse=", ".join(b["stockCodes"][:3]) if b.get("stockCodes") else ""
    baslik=b.get("title",b.get("subject","Açıklama"))[:150]
    tip=b.get("disclosureType",b.get("type",""))
    tarih=b.get("publishDate",b.get("date",""))
    onemli=any(k in (tip+baslik).upper() for k in KAP_ONEMLI)
    emoji="🔴" if onemli else "📋"
    m=f"{emoji} *KAP BİLDİRİMİ*\n\n"
    if hisse: m+=f"🏢 *{hisse}*\n"
    m+=f"📌 {baslik}\n"
    if tip: m+=f"📂 {tip}\n"
    if tarih: m+=f"🕐 {tarih}\n"
    m+="\n🔗 kap.org.tr"
    return m

def arka_plan_kap():
    global kap_goruldu
    time.sleep(30)
    while True:
        try:
            data=kap_cek()
            if data:
                bildirimler=data if isinstance(data,list) else data.get("content",[])
                for b in bildirimler[:30]:
                    bid=str(b.get("id",b.get("disclosureId",b.get("no",""))))
                    if bid and bid not in kap_goruldu:
                        with kap_lock:
                            kap_goruldu.add(bid)
                        telegram_gonder(kap_mesaj(b))
                        time.sleep(1)
        except:
            pass
        time.sleep(900)

# ─── ARKA PLAN TARAMA ─────────────────────────────────────────────────
def arka_plan_tara():
    global cache
    while True:
        with cache_lock:
            cache["durum"]="taraniyor"; cache["taranan"]=0; cache["toplam"]=len(BIST_TUMU)
        sinyaller=[]
        for h in BIST_TUMU:
            try:
                ticker=h+".IS"; sonuc=analiz_et(ticker)
                if "hata" not in sonuc and sonuc["sinyal"]!="BEKLE":
                    haber_sonuc=None; ai_yorum_metni=None; takas_sonuc=None; korel_sonuc=None
                    if sonuc["guclu"]:
                        takas_sonuc=takas_cek(h)
                        haberler=haber_cek(h)
                        if haberler: haber_sonuc=duygu_analizi(h,haberler)
                        korel_sonuc=en_yuksek_korelasyon(h, top=3)
                        ai_yorum_metni=ai_yorum(sonuc)
                        time.sleep(1)
                    mesaj=telegram_mesaj(sonuc,ai_yorum_metni,haber_sonuc,takas_sonuc,korel_sonuc)
                    sinyaller.append({
                        "hisse":h,"sinyal":sonuc["sinyal"],"guclu":sonuc["guclu"],
                        "skor":sonuc["skor"],"fiyat":sonuc["fiyat"],"sektor":sonuc.get("sektor",""),
                        "rsi":sonuc["rsi"],"adx":sonuc["adx"],
                        "macd_durum":sonuc.get("macd_durum",""),
                        "boll_pozisyon":sonuc.get("boll_pozisyon",""),
                        "trend":sonuc["trend"],"takas":takas_sonuc,
                        "haber_duygu":haber_sonuc,"korelasyonlar":korel_sonuc,
                        "ai_yorum":ai_yorum_metni,"mesaj":mesaj
                    })
            except:
                pass
            with cache_lock:
                cache["taranan"]+=1
            time.sleep(0.5)
        sinyaller.sort(key=lambda x:x["skor"],reverse=True)
        with cache_lock:
            cache["sonuc"]=sinyaller
            cache["guncelleme"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cache["durum"]="tamamlandi"; cache["taranan"]=len(BIST_TUMU)
        time.sleep(7200)

# ─── ENDPOINT'LER ─────────────────────────────────────────────────────
@app.route("/")
def anasayfa():
    with cache_lock:
        d=cache["durum"]; t=cache["taranan"]; top=cache["toplam"]; g=cache["guncelleme"]
    with sektor_lock:
        sg=sektor_cache.get("guncelleme","Henüz hesaplanmadı")
    return jsonify({
        "sistem":"Pisagor PRO API","versiyon":"12.0",
        "toplam_hisse":len(BIST_TUMU),
        "tarama_durumu":d,"taranan":f"{t}/{top}","son_guncelleme":g,
        "sektor_guncelleme":sg,
        "ozellikler":["Pisagor MA","RSI","ADX","MACD","Bollinger","KAP Takibi","AI Yorumu",
                      "Haber Duygu","Takas & Yabancı","Finansal Rapor AI","Sektör Rotasyonu","Korelasyon Analizi"],
        "endpointler":{
            "/tarama":"Sinyal sonuçları","/durum":"Tarama durumu",
            "/sektor":"Sektör rotasyonu","/sektor/<ad>":"Sektör korelasyon analizi",
            "/korelasyon/<h1>/<h2>":"İki hisse korelasyonu",
            "/korelasyon/<ticker>":"Hissenin en yüksek korelasyonları",
            "/kap":"KAP bildirimleri","/haber/<ticker>":"Haber duygu analizi",
            "/takas/<ticker>":"Takas & yabancı","/analiz/<ticker>":"Tam hisse analizi",
            "/liste":"Hisse listesi"
        }
    })

@app.route("/durum")
def durum():
    with cache_lock:
        return jsonify({"durum":cache["durum"],"taranan":cache["taranan"],
            "toplam":cache["toplam"],"yuzde":round(cache["taranan"]/max(cache["toplam"],1)*100,1),
            "son_guncelleme":cache["guncelleme"]})

@app.route("/tarama")
def tarama():
    with cache_lock:
        sonuc=cache["sonuc"]; g=cache["guncelleme"]; d=cache["durum"]; t=cache["taranan"]; top=cache["toplam"]
    if sonuc is None:
        return jsonify({"durum":d,"mesaj":f"Tarama devam ediyor... {t}/{top}","sinyal_sayisi":0,"sinyaller":[]})
    return jsonify({"durum":d,"son_guncelleme":g,"taranan":top,"sinyal_sayisi":len(sonuc),"sinyaller":sonuc})

@app.route("/sektor")
def sektor():
    with sektor_lock:
        sonuc=sektor_cache["sonuc"]
    if not sonuc:
        return jsonify({"mesaj":"Sektör analizi henüz tamamlanmadı, ~1 saat sonra tekrar dene"})
    return jsonify(sonuc)

@app.route("/sektor/<sektor_adi>")
def sektor_detay(sektor_adi):
    # URL encoding düzelt
    sektor_adi = sektor_adi.replace("-"," ")
    if sektor_adi not in SEKTORLER:
        return jsonify({"hata":f"Sektör bulunamadı","mevcut":list(SEKTORLER.keys())})
    return jsonify(sektor_korelasyon(sektor_adi))

@app.route("/korelasyon/<h1>/<h2>")
def korelasyon_iki(h1, h2):
    sonuc=korelasyon_hesapla(h1.upper(), h2.upper())
    if not sonuc:
        return jsonify({"hata":"Korelasyon hesaplanamadı"})
    return jsonify(sonuc)

@app.route("/korelasyon/<ticker>")
def korelasyon_hisse(ticker):
    sonuclar=en_yuksek_korelasyon(ticker.upper())
    return jsonify({"hisse":ticker,"korelasyonlar":sonuclar})

@app.route("/haber/<ticker>")
def haber(ticker):
    haberler=haber_cek(ticker.upper())
    if not haberler:
        return jsonify({"hata":"Haber bulunamadı"})
    return jsonify({"ticker":ticker,"haberler":haberler,"duygu_analizi":duygu_analizi(ticker.upper(),haberler)})

@app.route("/takas/<ticker>")
def takas(ticker):
    sonuc=takas_cek(ticker.upper())
    if not sonuc:
        return jsonify({"hata":"Takas verisi bulunamadı"})
    return jsonify(sonuc)

@app.route("/kap")
def kap():
    data=kap_cek()
    if not data:
        return jsonify({"hata":"KAP'a erişilemedi"})
    bildirimler=data if isinstance(data,list) else data.get("content",[])
    sonuc=[{"id":b.get("id",""),"hisse":b.get("stockCodes",[]),"baslik":b.get("title",""),
            "tip":b.get("disclosureType",""),"tarih":b.get("publishDate","")} for b in bildirimler[:20]]
    return jsonify({"toplam":len(sonuc),"bildirimler":sonuc})

@app.route("/analiz/<ticker>")
def analiz(ticker):
    if not ticker.endswith(".IS"):
        ticker=ticker+".IS"
    h=ticker.replace(".IS",""); sonuc=analiz_et(ticker)
    if "hata" not in sonuc:
        sonuc["korelasyonlar"]=en_yuksek_korelasyon(h, top=3)
        if sonuc["sinyal"]!="BEKLE" and ANTHROPIC_KEY:
            haberler=haber_cek(h)
            sonuc["haber_analizi"]=duygu_analizi(h,haberler) if haberler else None
            sonuc["takas"]=takas_cek(h)
            sonuc["ai_yorum"]=ai_yorum(sonuc)
    return jsonify(sonuc)

@app.route("/liste")
def liste():
    return jsonify({"toplam":len(BIST_TUMU),"hisseler":BIST_TUMU,"sektorler":SEKTORLER})

# ─── BAŞLANGIÇ ────────────────────────────────────────────────────────
def baslat():
    t1=threading.Thread(target=arka_plan_tara, daemon=True)
    t2=threading.Thread(target=arka_plan_kap, daemon=True)
    t3=threading.Thread(target=arka_plan_sektor, daemon=True)
    t1.start(); t2.start(); t3.start()

if __name__=="__main__":
    baslat()
    app.run(host="0.0.0.0", port=5000, debug=False)
else:
    baslat()
