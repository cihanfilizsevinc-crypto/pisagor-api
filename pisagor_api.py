from flask import Flask, jsonify, request
import yfinance as yf
import pandas as pd
import numpy as np
import math
import requests
import threading
import time
from datetime import datetime

app = Flask(__name__)

# ─── GLOBAL CACHE ─────────────────────────────────────────────────────
cache = {
    "sonuc": None,
    "guncelleme": None,
    "durum": "bekleniyor",
    "taranan": 0,
    "toplam": 0
}
cache_lock = threading.Lock()

# ─── KAP CACHE ────────────────────────────────────────────────────────
kap_goruldu = set()
kap_lock = threading.Lock()

# ─── TELEGRAM BİLGİLERİ ───────────────────────────────────────────────
# Bunları Railway'de environment variable olarak ayarlayacağız
import os
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

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
        if len(df) > 60:
            return df
    except:
        pass
    try:
        hisse = yf.Ticker(ticker)
        df = hisse.history(period="6mo", interval="1d")
        if len(df) > 60:
            df.columns = [c.lower() for c in df.columns]
            return df
    except:
        pass
    return None

# ─── HESAPLAMA ────────────────────────────────────────────────────────
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

def hesapla_adx(high, low, close, periyot=14):
    tr = pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
    atr = tr.rolling(window=periyot).mean()
    dm_p = (high-high.shift()).where((high-high.shift())>(low.shift()-low),0.0).clip(lower=0)
    dm_m = (low.shift()-low).where((low.shift()-low)>(high-high.shift()),0.0).clip(lower=0)
    di_p = 100*dm_p.rolling(window=periyot).mean()/atr
    di_m = 100*dm_m.rolling(window=periyot).mean()/atr
    dx = 100*(di_p-di_m).abs()/(di_p+di_m)
    return dx.rolling(window=periyot).mean(), di_p, di_m

def analiz_et(ticker, lookback=50):
    df = veri_cek(ticker)
    if df is None or len(df) < lookback+10:
        return {"hata": f"Veri yok: {ticker}", "hisse": ticker}
    close=df["close"].squeeze().astype(float)
    high=df["high"].squeeze().astype(float)
    low=df["low"].squeeze().astype(float)
    volume=df["volume"].squeeze().astype(float)
    avg_ra,avg_rb = geometrik_oran()
    pma = pisagor_ma(close)
    atr = pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1).rolling(window=lookback).mean()
    b_up=pma+atr*avg_ra; b_mu=pma+atr*avg_rb; b_md=pma-atr*avg_rb; b_lo=pma-atr*avg_ra
    trend_up=(close>pma)&(pma>pma.shift(3))
    trend_down=(close<pma)&(pma<pma.shift(3))
    rsi=hesapla_rsi(close); adx,dip,dim=hesapla_adx(high,low,close)
    vol_ok=volume>volume.rolling(20).mean()*1.2
    rsi_al=rsi<70; rsi_sat=rsi>35; adx_ok=adx>=18; di_bull=dip>dim; di_bear=dim>dip
    cross_up_mid=(close>b_md)&(close.shift()<=b_md.shift())
    cross_dn_mid=(close<b_mu)&(close.shift()>=b_mu.shift())
    cross_up_lower=(close>b_lo)&(close.shift()<=b_lo.shift())
    cross_dn_upper=(close<b_up)&(close.shift()>=b_up.shift())
    al_sinyal=cross_up_mid&trend_up&rsi_al&adx_ok&vol_ok&di_bull
    sat_sinyal=cross_dn_mid&trend_down&rsi_sat&adx_ok&vol_ok&di_bear
    guclu_al=cross_up_lower&trend_up&(rsi<50)&adx_ok&vol_ok&di_bull
    guclu_sat=cross_dn_upper&trend_down&(rsi>55)&adx_ok&vol_ok&di_bear
    s=-1
    t_up=bool(trend_up.iloc[s]); t_down=bool(trend_down.iloc[s])
    trend_txt="YUKARI" if t_up else "ASAGI" if t_down else "YATAY"
    son_fiyat=round(float(close.iloc[s]),2); son_pma=round(float(pma.iloc[s]),2)
    son_b_up=round(float(b_up.iloc[s]),2); son_b_mu=round(float(b_mu.iloc[s]),2)
    son_b_md=round(float(b_md.iloc[s]),2); son_b_lo=round(float(b_lo.iloc[s]),2)
    son_rsi=round(float(rsi.iloc[s]),1); son_adx=round(float(adx.iloc[s]),1)
    son_dip=round(float(dip.iloc[s]),1); son_dim=round(float(dim.iloc[s]),1)
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
    return {
        "hisse":ticker,"fiyat":son_fiyat,"sinyal":sinyal_tip,"guclu":sinyal_guclu,
        "skor":sinyal_skor,"yildiz":"★"*sinyal_skor+"☆"*(5-sinyal_skor),
        "tp":tp_sev,"sl":sl_sev,"trend":trend_txt,"rsi":son_rsi,"adx":son_adx,
        "di_plus":son_dip,"di_minus":son_dim,"pisagor_ma":son_pma,
        "ust_direnc":son_b_up,"ara_ust":son_b_mu,"ara_alt":son_b_md,
        "alt_destek":son_b_lo,"bar_sayisi":len(df)
    }

def telegram_mesaj(sonuc):
    guclu="💪 GÜÇLÜ " if sonuc["guclu"] else ""
    emoji="🟢" if sonuc["sinyal"]=="AL" else "🔴"
    trend_emoji="📈" if sonuc["trend"]=="YUKARI" else "📉" if sonuc["trend"]=="ASAGI" else "➡️"
    mesaj=f"""{emoji} *{guclu}{sonuc['sinyal']} SİNYALİ* — {sonuc['hisse']}
{sonuc['yildiz']}

💰 Fiyat: *{sonuc['fiyat']}₺*
{trend_emoji} Trend: {sonuc['trend']}

📊 *Teknik Göstergeler*
• RSI: {sonuc['rsi']}
• ADX: {sonuc['adx']} {"✅" if sonuc['adx']>=18 else "⚠️"}
• DI+/DI-: {sonuc['di_plus']} / {sonuc['di_minus']}

📐 *Pisagor Seviyeleri*
• Üst Direnç: {sonuc['ust_direnc']}
• Pisagor MA: {sonuc['pisagor_ma']}
• Alt Destek: {sonuc['alt_destek']}"""
    if sonuc["tp"]:
        mesaj+=f"\n\n🎯 *Hedef (TP)*: {sonuc['tp']}₺"
    if sonuc["sl"]:
        mesaj+=f"\n🛑 *Stop (SL)*: {sonuc['sl']}₺"
    mesaj+="\n\n⚠️ _Teknik gösterge bilgisidir, yatırım tavsiyesi değildir._"
    return mesaj

def telegram_gonder(mesaj):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mesaj,
            "parse_mode": "Markdown"
        }, timeout=10)
        return r.status_code == 200
    except:
        return False

# ─── KAP TAKİBİ ───────────────────────────────────────────────────────
KAP_ONEMLI = ["TEMETTÜ","SERMAYE","BİRLEŞME","SATIN","FİNANSAL","GENEL KURUL","HAK KULLANIM","BEDELSIZ","KÂR PAYI"]

def kap_bildirimleri_cek():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.kap.org.tr/",
        }
        r = requests.get("https://www.kap.org.tr/tr/api/disclosures", headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def kap_mesaj_olustur(b):
    hisse = ""
    if b.get("stockCodes"):
        hisse = ", ".join(b["stockCodes"][:3])
    baslik = b.get("title", b.get("subject", "Açıklama"))[:150]
    tip = b.get("disclosureType", b.get("type", ""))
    tarih = b.get("publishDate", b.get("date", ""))
    onemli = any(k in (tip+baslik).upper() for k in KAP_ONEMLI)
    emoji = "🔴" if onemli else "📋"
    mesaj = f"{emoji} *KAP BİLDİRİMİ*\n\n"
    if hisse:
        mesaj += f"🏢 *{hisse}*\n"
    mesaj += f"📌 {baslik}\n"
    if tip:
        mesaj += f"📂 {tip}\n"
    if tarih:
        mesaj += f"🕐 {tarih}\n"
    mesaj += "\n🔗 kap.org.tr"
    return mesaj

def arka_plan_kap():
    """Her 15 dakikada KAP'ı kontrol et"""
    global kap_goruldu
    time.sleep(30)  # Başlangıçta 30 sn bekle
    while True:
        try:
            data = kap_bildirimleri_cek()
            if data:
                bildirimler = data if isinstance(data, list) else data.get("content", [])
                yeni = 0
                for b in bildirimler[:30]:
                    bid = str(b.get("id", b.get("disclosureId", b.get("no", ""))))
                    if bid and bid not in kap_goruldu:
                        with kap_lock:
                            kap_goruldu.add(bid)
                        mesaj = kap_mesaj_olustur(b)
                        telegram_gonder(mesaj)
                        yeni += 1
                        time.sleep(1)
        except Exception as e:
            pass
        time.sleep(900)  # 15 dakika

# ─── ARKA PLAN TARAMA ─────────────────────────────────────────────────
def arka_plan_tara():
    global cache
    while True:
        with cache_lock:
            cache["durum"]="taraniyor"; cache["taranan"]=0; cache["toplam"]=len(BIST_TUMU)
        sinyaller=[]; hatalar=0
        for h in BIST_TUMU:
            try:
                ticker=h+".IS"
                sonuc=analiz_et(ticker)
                if "hata" not in sonuc and sonuc["sinyal"]!="BEKLE":
                    sinyaller.append({
                        "hisse":h,"sinyal":sonuc["sinyal"],"guclu":sonuc["guclu"],
                        "skor":sonuc["skor"],"fiyat":sonuc["fiyat"],"mesaj":telegram_mesaj(sonuc)
                    })
                else:
                    hatalar+=1
            except:
                hatalar+=1
            with cache_lock:
                cache["taranan"]+=1
            time.sleep(0.5)
        sinyaller.sort(key=lambda x:x["skor"],reverse=True)
        with cache_lock:
            cache["sonuc"]=sinyaller
            cache["guncelleme"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cache["durum"]="tamamlandi"
            cache["taranan"]=len(BIST_TUMU)
        time.sleep(7200)

# ─── ENDPOINT'LER ─────────────────────────────────────────────────────
@app.route("/")
def anasayfa():
    with cache_lock:
        d=cache["durum"]; t=cache["taranan"]; top=cache["toplam"]; g=cache["guncelleme"]
    return jsonify({
        "sistem":"Pisagor PRO API","versiyon":"7.0",
        "toplam_hisse":len(BIST_TUMU),
        "tarama_durumu":d,"taranan":f"{t}/{top}","son_guncelleme":g,
        "endpointler":{
            "/tarama":"Sinyal sonuçları (anında)",
            "/durum":"Tarama ilerleme durumu",
            "/kap":"KAP son bildirimleri",
            "/analiz/<ticker>":"Tek hisse analizi",
            "/liste":"Tüm hisse listesi"
        }
    })

@app.route("/durum")
def durum():
    with cache_lock:
        return jsonify({
            "durum":cache["durum"],"taranan":cache["taranan"],
            "toplam":cache["toplam"],
            "yuzde":round(cache["taranan"]/max(cache["toplam"],1)*100,1),
            "son_guncelleme":cache["guncelleme"]
        })

@app.route("/tarama")
def tarama():
    with cache_lock:
        sonuc=cache["sonuc"]; g=cache["guncelleme"]; d=cache["durum"]; t=cache["taranan"]; top=cache["toplam"]
    if sonuc is None:
        return jsonify({"durum":d,"mesaj":f"Tarama devam ediyor... {t}/{top}","sinyal_sayisi":0,"sinyaller":[]})
    return jsonify({"durum":d,"son_guncelleme":g,"taranan":top,"sinyal_sayisi":len(sonuc),"sinyaller":sonuc})

@app.route("/kap")
def kap():
    data = kap_bildirimleri_cek()
    if not data:
        return jsonify({"hata":"KAP'a erişilemedi"})
    bildirimler = data if isinstance(data, list) else data.get("content",[])
    sonuc = []
    for b in bildirimler[:20]:
        sonuc.append({
            "id": b.get("id", b.get("disclosureId","")),
            "hisse": b.get("stockCodes", []),
            "baslik": b.get("title", b.get("subject","")),
            "tip": b.get("disclosureType", b.get("type","")),
            "tarih": b.get("publishDate", b.get("date",""))
        })
    return jsonify({"toplam":len(sonuc),"bildirimler":sonuc})

@app.route("/analiz/<ticker>")
def analiz(ticker):
    if not ticker.endswith(".IS"):
        ticker=ticker+".IS"
    return jsonify(analiz_et(ticker))

@app.route("/liste")
def liste():
    return jsonify({"toplam":len(BIST_TUMU),"hisseler":BIST_TUMU})

# ─── BAŞLANGIÇ ────────────────────────────────────────────────────────
def baslat():
    global kap_lock
    kap_lock = threading.Lock()
    t1 = threading.Thread(target=arka_plan_tara, daemon=True)
    t2 = threading.Thread(target=arka_plan_kap, daemon=True)
    t1.start()
    t2.start()

if __name__ == "__main__":
    baslat()
    app.run(host="0.0.0.0", port=5000, debug=False)
else:
    baslat()
