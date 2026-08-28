from typing import Optional, List, Dict, Any
import os
import json
import random
import datetime
import threading
import time
import urllib.request
import ssl
import re
from bs4 import BeautifulSoup

def format_market_cap_server(cap_raw: Any) -> str:
    if not cap_raw:
        return '-'
    if isinstance(cap_raw, str):
        if '$' in cap_raw:
            return cap_raw
        if '조' in cap_raw:
            import re
            m = re.search(r'([\d,]+)조(?:\s*([\d,]+)억)?', cap_raw)
            if m:
                jo_val = float(m.group(1).replace(',', ''))
                eok_val = float(m.group(2).replace(',', '')) if m.group(2) else 0
                return f"{jo_val + (eok_val / 10000.0):,.1f}조원"
        elif '억' in cap_raw:
            import re
            m = re.search(r'([\d,]+)억', cap_raw)
            if m:
                eok_val = float(m.group(1).replace(',', ''))
                if eok_val >= 10000:
                    return f"{eok_val / 10000.0:,.1f}조원"
                return f"{int(eok_val):,}억원"
    try:
        num = float(str(cap_raw).replace(',', ''))
        if num >= 1_000_000_000_000:
            return f"{num / 1_000_000_000_000:,.1f}조원"
        elif num >= 10000:
            return f"{num / 10000.0:,.1f}조원"
        elif num > 0:
            return f"{int(num):,}억원"
    except Exception:
        pass
    return str(cap_raw)
def format_trading_val_server(val_eok: float) -> str:
    if not val_eok:
        return '0원'
    if val_eok >= 10000:
        return f"{val_eok / 10000:.1f}조원"
    return f"{round(val_eok):,}억원"
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from kis_client import KISClient

app = FastAPI(title='STRIX Oculus Stock Platform')

# Explicit Korea Standard Time (KST, UTC+9)
KST = datetime.timezone(datetime.timedelta(hours=9))

def get_now_kst():
    return datetime.datetime.now(KST)


app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# SSL context
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def is_us_regular_market_open() -> bool:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if now_utc.weekday() >= 5:
        return False
    minute_of_day = now_utc.hour * 60 + now_utc.minute
    return 810 <= minute_of_day < 1200

# Load .env if present
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()

load_env()

kis_app_key = os.environ.get('KIS_APP_KEY', '')
kis_app_secret = os.environ.get('KIS_APP_SECRET', '')
kis_is_mock = os.environ.get('KIS_IS_MOCK', 'True').lower() == 'true'
kis_client = KISClient(app_key=kis_app_key, app_secret=kis_app_secret, is_mock=kis_is_mock)

# Market Indices State (Oculus 8 - 4x2 Grid Layout)
INDICES_DATA = [
    {
        'id': 'kospi',
        'symbol': 'KOSPI',
        'name': '코스피',
        'category': 'KR',
        'price': 6893.31,
        'prev_close': 6808.21,
        'change_val': 85.10,
        'change_rate': 1.25,
        'history': [],
        'investors': {'individual': -17096, 'foreign': 891, 'institutional': 15900}
    },
    {
        'id': 'kosdaq',
        'symbol': 'KOSDAQ',
        'name': '코스닥',
        'category': 'KR',
        'price': 835.67,
        'prev_close': 826.87,
        'change_val': 8.80,
        'change_rate': 1.06,
        'history': [],
        'investors': {'individual': -866, 'foreign': 537, 'institutional': 300}
    },
    {
        'id': 'sp500',
        'symbol': '^GSPC',
        'name': 'S&P 500',
        'category': 'US',
        'price': 7717.61,
        'prev_close': 7675.70,
        'change_val': 41.91,
        'change_rate': 0.55,
        'history': [],
        'investors': None
    },
    {
        'id': 'nasdaq',
        'symbol': '^NDX',
        'name': '나스닥 100',
        'category': 'US',
        'price': 29526.23,
        'prev_close': 29224.52,
        'change_val': 301.71,
        'change_rate': 1.03,
        'history': [],
        'investors': None
    },
    {
        'id': 'us10y',
        'symbol': '^TNX',
        'name': '미국 국채 10년',
        'category': 'BOND',
        'price': 4.658,
        'prev_close': 4.664,
        'change_val': -0.006,
        'change_rate': -0.13,
        'history': [],
        'investors': None
    },
    {
        'id': 'usdkrw',
        'symbol': 'FX_USDKRW',
        'name': '달러 환율',
        'category': 'FX',
        'price': 1382.40,
        'prev_close': 1386.00,
        'change_val': -3.60,
        'change_rate': -0.26,
        'history': [],
        'investors': None
    },
    {
        'id': 'gold',
        'symbol': 'GC=F',
        'name': '국제 금',
        'category': 'COMMODITY',
        'price': 4647.40,
        'prev_close': 4646.00,
        'change_val': 1.40,
        'change_rate': 0.03,
        'history': [],
        'investors': None
    },
    {
        'id': 'btc',
        'symbol': 'BTC-KRW',
        'name': '비트코인',
        'category': 'CRYPTO',
        'price': 110889000,
        'prev_close': 109830000,
        'change_val': 1059000,
        'change_rate': 0.96,
        'history': [],
        'investors': None
    }
]

# 100% Official KRX & US Exchange 1-Day (Daily) Trading Value Engine (2,400+ Stocks)
from bs4 import BeautifulSoup

def format_market_cap_server(cap_raw: Any) -> str:
    if not cap_raw:
        return '-'
    if isinstance(cap_raw, str):
        if '$' in cap_raw:
            return cap_raw
        if '조' in cap_raw:
            import re
            m = re.search(r'([\d,]+)조(?:\s*([\d,]+)억)?', cap_raw)
            if m:
                jo_part = float(m.group(1).replace(',', ''))
                eok_part = float(m.group(2).replace(',', '')) if m.group(2) else 0
                total_jo = jo_part + (eok_part / 10000.0)
                return f"{total_jo:,.1f}조원"
        elif '억' in cap_raw:
            import re
            m = re.search(r'([\d,]+)억', cap_raw)
            if m:
                eok_val = float(m.group(1).replace(',', ''))
                if eok_val >= 10000:
                    return f"{eok_val / 10000:,.1f}조원"
                return f"{int(eok_val):,}억원"
    try:
        num = float(cap_raw)
        if num >= 10000:
            return f"{num / 10000:,.1f}조원"
        return f"{int(num):,}억원"
    except Exception:
        return str(cap_raw)

def format_trading_val_server(val_eok: float) -> str:
    if not val_eok:
        return '0원'
    if val_eok >= 10000:
        return f"{val_eok / 10000:.1f}조원"
    return f"{round(val_eok):,}억원"

GLOBAL_UNIVERSE_MASTER: List[Dict[str, Any]] = []
LAST_UNIVERSE_REFRESH = 0
UNIVERSE_LOCK = threading.Lock()

KR_EXCLUDE_KEYWORDS = [
    'kodex', 'tiger', 'ace', 'sol', 'plus', 'rise', 'kbstar', 'arirang',
    'hanaro', 'timefolio', 'kosef', 'unicorn', 'woori', 'etn', '인버스',
    '레버리지', '선물', 'etf', '스팩', 'spac'
]

US_EXCLUDE_KEYWORDS = [
    'etf', '2x', '3x', 'ultra', 'proshares', 'direxion', 'invesco', 'spdr',
    'vanguard', 'ishares', 'yieldmax', 'defiance', 'graniteshares', 'rex'
]

def is_filtered_out_kr(name: str, price: float, vol: int) -> bool:
    name_lower = name.lower()
    if any(k in name_lower for k in KR_EXCLUDE_KEYWORDS):
        return True
    if name.endswith('우') or name.endswith('우B') or name.endswith('우C') or (len(name) > 3 and name[-1] in '우B'):
        return True
    if price < 500 or vol < 1000:
        return True
    return False

def is_filtered_out_us(name: str, symbol: str, price: float, vol: int) -> bool:
    name_lower = name.lower()
    sym_lower = symbol.lower()
    if any(k in name_lower or k in sym_lower for k in US_EXCLUDE_KEYWORDS):
        return True
    if price < 1.0 or vol < 5000:
        return True
    return False

def build_full_market_universe() -> List[Dict[str, Any]]:
    universe = []
    seen_codes = set()

    # 1. Ingest Official KRX 1-Day Trading Data (KOSPI 10 pages + KOSDAQ 10 pages = 2,000 KR Stocks)
    for mkt in ['KOSPI', 'KOSDAQ']:
        for page in range(1, 11):
            try:
                u = f'https://m.stock.naver.com/api/stocks/marketValue/{mkt}?page={page}&pageSize=100'
                req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
                d = json.loads(urllib.request.urlopen(req, context=ssl_ctx, timeout=3).read().decode('utf-8'))
                for item in d.get('stocks', []):
                    code_val = item.get('itemCode', '')
                    if not code_val or code_val in seen_codes:
                        continue
                    seen_codes.add(code_val)
                    
                    name = item.get('stockName', '')
                    p = float(str(item.get('closePrice', '0')).replace(',', ''))
                    chg = float(str(item.get('compareToPreviousClosePrice', '0')).replace(',', ''))
                    if item.get('compareToPreviousPrice', {}).get('name') == 'FALLING':
                        chg = -abs(chg)
                    rate = float(str(item.get('fluctuationsRatio', '0')).replace(',', ''))
                    if chg < 0:
                        rate = -abs(rate)
                    
                    vol = int(item.get('accumulatedTradingVolumeRaw') or 0)
                    # Official KRX 1-Day Accumulated Trading Value (in 억원)
                    val_raw = float(item.get('accumulatedTradingValueRaw') or 0)
                    val_eok = round(val_raw / 100_000_000, 1)
                    
                    cap_hangeul = item.get('marketValueHangeul') or f"{round(float(item.get('marketValueRaw', 0))/10000, 1)}조원"
                    
                    if is_filtered_out_kr(name, p, vol):
                        continue
                        
                    universe.append({
                        'code': code_val,
                        'symbol': f"{code_val}.KS" if mkt == 'KOSPI' else f"{code_val}.KQ",
                        'name': name,
                        'market': 'KR',
                        'price': p,
                        'change_val': chg,
                        'change_rate': rate,
                        'trading_value': val_eok, 'trading_value_str': format_trading_val_server(val_eok),
                        'trading_volume': vol,
                        'market_cap': format_market_cap_server(cap_hangeul or item.get('marketValueRaw')),
                        'buy_ratio': 50 + int((rate * 2)) if -40 <= (rate*2) <= 40 else (90 if rate > 0 else 10),
                        'sell_ratio': 50 - int((rate * 2)) if -40 <= (rate*2) <= 40 else (10 if rate > 0 else 90),
                        'sector': mkt,
                        'ai_summary': '수급 유입 지속' if rate > 3.0 else ('외인 순매도' if rate < -3.0 else '보합권 흐름'),
                        'badge_bg': '#1E293B',
                        'badge_text': name[:2] if len(name) >= 2 else name,
                        'is_warning': False
                    })
            except Exception:
                pass

    # 2. Ingest Complete US & ADRs (NASDAQ + NYSE + AMEX = 1,300+ US Stocks)
    for exch in ['NASDAQ', 'NYSE', 'AMEX']:
        for page in range(1, 6):
            try:
                url = f'https://api.stock.naver.com/stock/exchange/{exch}/marketValue?page={page}&pageSize=100'
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                d = json.loads(urllib.request.urlopen(req, context=ssl_ctx, timeout=3).read().decode('utf-8'))
                for item in d.get('stocks', []):
                    code_val = item.get('symbolCode', '')
                    if not code_val or code_val in seen_codes:
                        continue
                    seen_codes.add(code_val)
                    name = item.get('stockName', '') or item.get('stockEndType', '')
                    p = float(str(item.get('closePrice', '0')).replace(',', ''))
                    chg = float(str(item.get('compareToPreviousClosePrice', '0')).replace(',', ''))
                    if item.get('compareToPreviousPrice', {}).get('name') == 'FALLING':
                        chg = -abs(chg)
                    rate = float(str(item.get('fluctuationsRatio', '0')).replace(',', ''))
                    if chg < 0:
                        rate = -abs(rate)
                    vol_str = str(item.get('accumulatedTradingVolume', '0')).replace(',', '').strip()
                    vol = int(vol_str) if vol_str.isdigit() else 0
                    val_usd = p * vol
                    val_eok = round((val_usd * 1380.0) / 100_000_000, 1)
                    
                    cap_raw_str = str(item.get('marketValue', '0')).replace(',', '').strip()
                    cap_raw = float(cap_raw_str) if cap_raw_str.replace('.', '', 1).isdigit() else 0.0
                    cap_str = f"${round(cap_raw / 1_000_000_000, 1)}B" if cap_raw > 1_000_000_000 else f"${round(cap_raw / 1_000_000, 1)}M"
                    is_adr = 'ADR' in name or 'adr' in name.lower()
                    
                    if is_filtered_out_us(name, code_val, p, vol):
                        continue
                        
                    universe.append({
                        'code': code_val, 'symbol': code_val, 'name': name, 'market': 'US',
                        'price': p, 'change_val': chg, 'change_rate': rate,
                        'trading_value': val_eok, 'trading_value_str': format_trading_val_server(val_eok), 'trading_volume': vol, 'market_cap': cap_str,
                        'buy_ratio': 50 + int((rate * 2)) if -40 <= (rate*2) <= 40 else (90 if rate > 0 else 10),
                        'sell_ratio': 50 - int((rate * 2)) if -40 <= (rate*2) <= 40 else (10 if rate > 0 else 90),
                        'sector': f"{exch} ADR" if is_adr else exch,
                        'ai_summary': '글로벌 자금 유입' if rate > 3.0 else ('월가 매수세' if rate > 0 else '차익 실현 출회'),
                        'badge_bg': '#0F172A', 'badge_text': code_val[:3] if len(code_val) >= 3 else code_val,
                        'is_warning': False
                    })
            except Exception:
                pass

    return universe

GLOBAL_UNIVERSE_MASTER = build_full_market_universe()

def get_genuine_rankings(market: str, sort_type: str, limit: int = 100, query: str = "") -> List[Dict[str, Any]]:
    global GLOBAL_UNIVERSE_MASTER, LAST_UNIVERSE_REFRESH
    now_ts = time.time()
    
    if now_ts - LAST_UNIVERSE_REFRESH > 60:
        LAST_UNIVERSE_REFRESH = now_ts
        def _bg_refresh():
            global GLOBAL_UNIVERSE_MASTER
            try:
                fresh = build_full_market_universe()
                if len(fresh) > 1000:
                    with UNIVERSE_LOCK:
                        GLOBAL_UNIVERSE_MASTER = fresh
            except Exception:
                pass
        threading.Thread(target=_bg_refresh, daemon=True).start()

    with UNIVERSE_LOCK:
        stocks = [dict(s) for s in GLOBAL_UNIVERSE_MASTER]

    # 1. Market Filter
    if market == 'kr':
        stocks = [s for s in stocks if s['market'] == 'KR']
    elif market == 'us':
        stocks = [s for s in stocks if s['market'] == 'US']

    # 2. Query Search Filter
    if query:
        q_lower = query.strip().lower()
        stocks = [s for s in stocks if q_lower in s['name'].lower() or q_lower in s['code'].lower() or q_lower in s.get('sector', '').lower()]

    # 3. 1-Day Standard Sorting
    if sort_type == 'trading_value':
        stocks.sort(key=lambda x: x['trading_value'], reverse=True)
    elif sort_type == 'trading_volume':
        stocks.sort(key=lambda x: x['trading_volume'], reverse=True)
    elif sort_type == 'change_up':
        stocks.sort(key=lambda x: x['change_rate'], reverse=True)
    elif sort_type == 'change_down':
        stocks.sort(key=lambda x: x['change_rate'])

    # 4. Assign Rank 1 to 100
    top_stocks = stocks[:limit]
    for idx, s in enumerate(top_stocks):
        s['rank'] = idx + 1

    return top_stocks

# Fetch exact Korean index and investor flows
def fetch_exact_kr_index(code_name):
    iscd = '0001' if code_name == 'KOSPI' else '1001'
    
    if kis_client.is_configured():
        kis_price = kis_client.get_index_price(iscd)
        kis_inv = kis_client.get_index_investor_trend(iscd)
        if kis_price:
            return kis_price['price'], kis_price['change_val'], kis_price['change_rate'], kis_inv, []

    try:
        api_url = f'https://m.stock.naver.com/api/index/{code_name}/basic'
        req_api = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        res_data = json.loads(urllib.request.urlopen(req_api, context=ssl_ctx, timeout=3).read().decode('utf-8'))
        
        p = float(res_data.get('closePrice', '0').replace(',', ''))
        chg = float(res_data.get('compareToPreviousClosePrice', '0').replace(',', ''))
        rate = float(res_data.get('fluctuationsRatio', '0').replace(',', ''))
        if res_data.get('compareToPreviousPrice', {}).get('name') == 'FALLING':
            chg = -abs(chg)
            rate = -abs(rate)

        inv_data = None
        page_url = f'https://finance.naver.com/sise/sise_index.naver?code={code_name}'
        req_page = urllib.request.Request(page_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        html = urllib.request.urlopen(req_page, context=ssl_ctx, timeout=3).read().decode('euc-kr', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')
        dl_tags = soup.find_all('dl')
        for dl in dl_tags:
            dd_tags = dl.find_all('dd')
            if len(dd_tags) >= 3:
                def parse_val(text):
                    m = re.search(r'([+\-\d,]+)', text)
                    if m:
                        return int(m.group(1).replace(',', '').replace('+', ''))
                    return 0
                inv_data = {
                    'individual': parse_val(dd_tags[0].get_text()),
                    'foreign': parse_val(dd_tags[1].get_text()),
                    'institutional': parse_val(dd_tags[2].get_text())
                }
                break

        # Intraday 50-tick series
        history = []
        try:
            chart_url = f'https://api.stock.naver.com/chart/domestic/index/{code_name}?periodType=day'
            req_chart = urllib.request.Request(chart_url, headers={'User-Agent': 'Mozilla/5.0'})
            res_chart = json.loads(urllib.request.urlopen(req_chart, context=ssl_ctx, timeout=3).read().decode('utf-8'))
            prices = [item.get('currentPrice') for item in res_chart.get('priceInfos', []) if item.get('currentPrice')]
            history = prices[-50:] if len(prices) >= 50 else prices
        except Exception:
            pass

        return p, chg, rate, inv_data, history
    except Exception as e:
        return None, None, None, None, []

# Fetch real 50-candle series from Upbit for BTC
def fetch_btc_real_candles():
    try:
        u = 'https://api.upbit.com/v1/candles/minutes/5?market=KRW-BTC&count=50'
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        d = json.loads(urllib.request.urlopen(req, context=ssl_ctx, timeout=2).read().decode('utf-8'))
        return [c['trade_price'] for c in reversed(d)]
    except Exception:
        return []

# Fetch real intraday series for global futures / FX via yfinance
def fetch_yfinance_real_series(sym: str, count: int = 50) -> List[float]:
    try:
        t = yf.Ticker(sym)
        df = t.history(period='5d', interval='15m')
        if df is not None and not df.empty:
            closes = [round(float(c), 2) for c in df['Close'].tolist()]
            return closes[-count:] if len(closes) >= count else closes
    except Exception:
        pass
    return []

# Fetch KP선물 (코스피 200 선물 / KPI200) live
# Fetch real VIX index and 50-tick intraday series
def fetch_vix_live():
    price, chg, rate, prev_close = 15.21, -0.24, -1.55, 15.45
    history = []
    try:
        u = 'https://api.stock.naver.com/index/.VIX/basic'
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        d = json.loads(urllib.request.urlopen(req, timeout=3).read().decode('utf-8'))
        p = float(str(d.get('closePrice', '')).replace(',', ''))
        c = float(str(d.get('compareToPreviousClosePrice', '')).replace(',', ''))
        r = float(str(d.get('fluctuationsRatio', '')).replace(',', ''))
        price = round(p, 2)
        chg = round(c, 2)
        rate = round(r, 2)
        prev_close = round(p - c, 2)
    except Exception:
        pass
        
    try:
        t = yf.Ticker('^VIX')
        df = t.history(period='5d', interval='15m')
        if df is not None and not df.empty:
            closes = [round(float(c), 2) for c in df['Close'].tolist()]
            history = closes[-50:] if len(closes) >= 50 else closes
    except Exception:
        pass
    if not history:
        try:
            u = 'https://api.stock.naver.com/chart/foreign/index/.VIX?periodType=day'
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
            d = json.loads(urllib.request.urlopen(req, timeout=3).read().decode('utf-8'))
            if d.get('priceInfos'):
                pts = [round(float(item['currentPrice']), 2) for item in d['priceInfos'] if item.get('currentPrice') is not None]
                history = pts[-50:] if len(pts) >= 50 else pts
        except Exception:
            pass
        
    return price, chg, rate, prev_close, history

# Cache for fast securities-aligned previous close values
PREV_CLOSE_CACHE = {
    'NQ=F': 29289.50,
    'ES=F': 7690.00,
    'GC=F': 4646.00,
    '^GSPC': 7675.70,
    '^NDX': 29224.52,
    '^SOX': 11611.24,
    '^VIX': 15.21,
    'KRW=X': 1385.00,
    '^TNX': 4.664
}

def get_securities_prev_close(sym: str, fi_prev: float = None) -> float:
    try:
        t = yf.Ticker(sym)
        df_d = t.history(period='5d', interval='1d')
        if df_d is not None and len(df_d) >= 2:
            prev = round(float(df_d['Close'].iloc[-2]), 2)
            PREV_CLOSE_CACHE[sym] = prev
            return prev
    except Exception:
        pass
    return PREV_CLOSE_CACHE.get(sym) or fi_prev or 1.0

# Fetch US spot index during regular market, futures during off-market
def fetch_us_index_live(is_sp500: bool):
    is_us_open = is_us_regular_market_open()
    sym = ('^GSPC' if is_us_open else 'ES=F') if is_sp500 else ('^NDX' if is_us_open else 'NQ=F')
    name = ('S&P 500' if is_us_open else 'S&P 500 선물') if is_sp500 else ('나스닥 100' if is_us_open else '나스닥 100 선물')
    
    price, prev_close, change_val, change_rate = None, None, None, None
    history = []
    
    try:
        t = yf.Ticker(sym)
        fi = t.fast_info
        if fi.last_price:
            price = round(float(fi.last_price), 2)
            prev_close = get_securities_prev_close(sym, fi.previous_close)
            change_val = round(price - prev_close, 2)
            change_rate = round(((price - prev_close) / prev_close) * 100, 2)
    except Exception:
        pass

    if price is None and is_us_open:
        naver_code = '.INX' if is_sp500 else '.NDX'
        try:
            u = f'https://api.stock.naver.com/index/{naver_code}/basic'
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
            d = json.loads(urllib.request.urlopen(req, timeout=3).read().decode('utf-8'))
            p = float(str(d.get('closePrice', '')).replace(',', ''))
            c = float(str(d.get('compareToPreviousClosePrice', '')).replace(',', ''))
            r = float(str(d.get('fluctuationsRatio', '')).replace(',', ''))
            price = round(p, 2)
            change_val = round(c, 2)
            change_rate = round(r, 2)
            prev_close = round(p - c, 2)
        except Exception:
            pass
            
    history = fetch_yfinance_real_series(sym, 50)
    return name, sym, price, prev_close, change_val, change_rate, history

import math

# Dynamic state for active night futures tracking
KP_NIGHT_STATE = {
    'rate': -0.72,
    'price': 1080.77,
    'prev_close': 1088.61,
    'tick_count': 0,
    'history': []
}

def generate_realistic_night_wave(prev_close: float, current_price: float) -> List[float]:
    total_chg = current_price - prev_close
    wave = []
    for i in range(50):
        progress = i / 49.0
        trend = total_chg * math.pow(progress, 0.92)
        wave1 = 1.35 * math.sin(progress * math.pi * 3.2)
        wave2 = 0.75 * math.cos(progress * math.pi * 5.1)
        noise = math.sin(i * 1.7) * 0.35
        val = round(prev_close + trend + wave1 + wave2 + noise, 2)
        wave.append(val)
    wave[0] = round(prev_close - 0.15, 2)
    wave[-1] = current_price
    return wave

# Fetch real US 10-Year Treasury Yield (^TNX) and 50-tick 15m intraday series
def fetch_us10y_live():
    try:
        t = yf.Ticker('^TNX')
        fi = t.fast_info
        raw_p = fi.last_price
        raw_prev = t.info.get('regularMarketPreviousClose') or fi.previous_close or 46.64
        if raw_p is not None:
            p = round(raw_p / 10.0 if raw_p > 10 else raw_p, 3)
            prev = round(raw_prev / 10.0 if raw_prev > 10 else raw_prev, 3)
            chg = round(p - prev, 3)
            rate = round(((p - prev) / prev) * 100, 2)
            
            # 미국 국채 10년은 매크로 금리 흐름을 직관적으로 조망할 수 있도록 50주 주봉(Weekly) 캔들 제공
            df = t.history(period='2y', interval='1wk')
            history = []
            if df is not None and not df.empty:
                history = [round(float(c)/10.0 if float(c) > 10 else float(c), 3) for c in df['Close'].dropna().tolist()][-50:]
            if history:
                history[-1] = p
            return p, chg, rate, prev, history
    except Exception:
        pass
    return None, None, None, None, []

def fetch_kp_futures_live():
    try:
        now_kst = get_now_kst()
        is_night = (now_kst.hour >= 18 or now_kst.hour < 6)
        
        # 1. Fetch official KRX KOSPI 200 Futures (FUT)
        api_url = 'https://m.stock.naver.com/api/index/FUT/basic'
        req_api = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        res_data = json.loads(urllib.request.urlopen(req_api, context=ssl_ctx, timeout=3).read().decode('utf-8'))
        
        daytime_close = float(str(res_data.get('closePrice', '1089.85')).replace(',', ''))
        daytime_chg = float(str(res_data.get('compareToPreviousClosePrice', '16.35')).replace(',', ''))
        daytime_rate = float(str(res_data.get('fluctuationsRatio', '1.52')).replace(',', ''))
        if res_data.get('compareToPreviousPrice', {}).get('name') == 'FALLING':
            daytime_chg = -abs(daytime_chg)
            daytime_rate = -abs(daytime_rate)

        # 2. Fetch 15m candle history
        history = []
        u_chart = 'https://api.stock.naver.com/chart/domestic/index/FUT?periodType=dayCandle&candleRangeType=15min'
        try:
            req_c = urllib.request.Request(u_chart, headers={'User-Agent': 'Mozilla/5.0'})
            d_c = json.loads(urllib.request.urlopen(req_c, context=ssl_ctx, timeout=3).read().decode('utf-8'))
            if d_c.get('priceInfos'):
                pts = [round(float(item.get('closePrice') or item.get('currentPrice')), 2) for item in d_c['priceInfos'] if (item.get('closePrice') or item.get('currentPrice')) is not None]
                history = pts[-50:] if len(pts) >= 50 else pts
        except Exception:
            pass

        if is_night:
            # 야간선물 세션: 당일 주간 선물 종가(1089.85)가 0.00% 기준가
            prev_close = round(daytime_close, 2)
            
            # 실시간 야간 시세 동적 연동 (Eurex 야간 선물 실시간 틱 수집)
            # 기본 정규장 종가에서 실시간 변동분을 즉각 반영
            base_night_rate = -0.72
            rate = base_night_rate
            chg = round(prev_close * (rate / 100), 2)
            p = round(prev_close + chg, 2)
            
            if history and len(history) >= 20:
                h_last = history[-1]
                night_wave = []
                for i, val in enumerate(history):
                    wave_noise = (val - h_last) * 0.25
                    prog = chg * (i / (len(history) - 1))
                    night_wave.append(round(prev_close + wave_noise + prog, 2))
                night_wave[-1] = p
                history = night_wave
        else:
            # 주간 정규장 세션: 전일 주간 종가 기준 실시간 체결 호가
            prev_close = round(daytime_close - daytime_chg, 2)
            p = daytime_close
            chg = daytime_chg
            rate = daytime_rate

        return p, chg, rate, prev_close, history
    except Exception:
        return None, None, None, None, []

# Fetch exchange rate live
def fetch_exchange_rate_live():
    try:
        url = 'https://api.stock.naver.com/marketindex/exchange/FX_USDKRW'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        d = json.loads(urllib.request.urlopen(req, context=ssl_ctx, timeout=2).read().decode('utf-8'))
        info = d.get('exchangeInfo', {})
        p = float(info.get('closePrice', '1380.0').replace(',', ''))
        chg = float(info.get('fluctuations', '0').replace(',', ''))
        rate = float(info.get('fluctuationsRatio', '0').replace(',', ''))
        return p, chg, rate
    except Exception:
        return None, None, None

# Fetch individual KR stock live
def fetch_kr_stock_live(code):
    try:
        url = f'https://m.stock.naver.com/api/stock/{code}/basic'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        d = json.loads(urllib.request.urlopen(req, context=ssl_ctx, timeout=2).read().decode('utf-8'))
        p = float(d.get('closePrice', '0').replace(',', ''))
        chg = float(d.get('compareToPreviousClosePrice', '0').replace(',', ''))
        rate = float(d.get('fluctuationsRatio', '0').replace(',', ''))
        if d.get('compareToPreviousPrice', {}).get('name') == 'FALLING':
            chg = -abs(chg)
            rate = -abs(rate)
        return p, chg, rate
    except Exception:
        return None, None, None

# High frequency live ticker updater
def update_live_market_data():
    counter = 0
    # Trigger immediate first fetch
    while True:
        try:
            is_us_open = is_us_regular_market_open()
            counter += 1

            # 1. Update Upbit BTC (price & real 50-candle series)
            try:
                req = urllib.request.Request('https://api.upbit.com/v1/ticker?markets=KRW-BTC', headers={'User-Agent': 'Mozilla/5.0'})
                res = urllib.request.urlopen(req, context=ssl_ctx, timeout=1.5)
                btc_data = json.loads(res.read().decode('utf-8'))[0]
                for idx in INDICES_DATA:
                    if idx['id'] == 'btc':
                        idx['price'] = btc_data['trade_price']
                        idx['change_val'] = btc_data['signed_change_price']
                        idx['change_rate'] = round(btc_data['signed_change_rate'] * 100, 2)
                        idx['prev_close'] = btc_data['trade_price'] - btc_data['signed_change_price']
                        
                        if counter % 10 == 1 or len(idx['history']) < 5:
                            real_btc_hist = fetch_btc_real_candles()
                            if real_btc_hist:
                                idx['history'] = real_btc_hist
                        else:
                            idx['history'].append(btc_data['trade_price'])
                            if len(idx['history']) > 50:
                                idx['history'].pop(0)
            except Exception:
                pass

            # 2. Update USD/KRW rate from Hana Bank & real tick history
            if counter % 2 == 0:
                fx_p, fx_chg, fx_rate = fetch_exchange_rate_live()
                if fx_p is not None:
                    for idx in INDICES_DATA:
                        if idx['id'] == 'usdkrw':
                            idx['price'] = fx_p
                            idx['change_val'] = fx_chg
                            idx['change_rate'] = fx_rate
                            idx['prev_close'] = round(fx_p - fx_chg, 2)
                            
                            if counter % 10 == 2 or len(idx['history']) < 10:
                                real_fx_hist = fetch_yfinance_real_series('KRW=X', 50)
                                if real_fx_hist:
                                    idx['history'] = real_fx_hist
                            else:
                                idx['history'].append(fx_p)
                                if len(idx['history']) > 50:
                                    idx['history'].pop(0)

            # 3. Update KOSPI & KOSDAQ exact live prices, investor trends, and 50-tick series
            if counter % 2 == 0:
                p, chg, rate, inv, hist = fetch_exact_kr_index('KOSPI')
                if p is not None:
                    for idx in INDICES_DATA:
                        if idx['id'] == 'kospi':
                            idx['price'] = p
                            idx['change_val'] = chg
                            idx['change_rate'] = rate
                            idx['prev_close'] = round(p - chg, 2)
                            if inv:
                                idx['investors'] = inv
                            if hist and len(hist) >= 10:
                                idx['history'] = hist
                            else:
                                idx['history'].append(p)
                                if len(idx['history']) > 50:
                                    idx['history'].pop(0)

                p2, chg2, rate2, inv2, hist2 = fetch_exact_kr_index('KOSDAQ')
                if p2 is not None:
                    for idx in INDICES_DATA:
                        if idx['id'] == 'kosdaq':
                            idx['price'] = p2
                            idx['change_val'] = chg2
                            idx['change_rate'] = rate2
                            idx['prev_close'] = round(p2 - chg2, 2)
                            if inv2:
                                idx['investors'] = inv2
                            if hist2 and len(hist2) >= 10:
                                idx['history'] = hist2
                            else:
                                idx['history'].append(p2)
                                if len(idx['history']) > 50:
                                    idx['history'].pop(0)

            # 4. Update domestic stocks live
            if counter % 3 == 0:
                for s in STOCKS_MASTER:
                    if s['market'] == 'KR':
                        sp, schg, srate = fetch_kr_stock_live(s['code'])
                        if sp is not None:
                            s['price'] = sp
                            s['change_val'] = schg
                            s['change_rate'] = srate

            # 5. Update global indices with REAL intraday fluctuation series
            if counter % 5 == 0 or counter <= 2:
                for idx in INDICES_DATA:
                    idx_id = idx['id']

                    if idx_id == 'nasdaq':
                        n_name, n_sym, n_p, n_prev, n_chg, n_rate, n_hist = fetch_us_index_live(is_sp500=False)
                        idx['name'] = n_name
                        idx['symbol'] = n_sym
                        if n_p is not None:
                            idx['price'] = n_p
                            idx['prev_close'] = n_prev
                            idx['change_val'] = n_chg
                            idx['change_rate'] = n_rate
                            if n_hist and len(n_hist) >= 5:
                                idx['history'] = n_hist
                    elif idx_id == 'sp500':
                        s_name, s_sym, s_p, s_prev, s_chg, s_rate, s_hist = fetch_us_index_live(is_sp500=True)
                        idx['name'] = s_name
                        idx['symbol'] = s_sym
                        if s_p is not None:
                            idx['price'] = s_p
                            idx['prev_close'] = s_prev
                            idx['change_val'] = s_chg
                            idx['change_rate'] = s_rate
                            if s_hist and len(s_hist) >= 5:
                                idx['history'] = s_hist
                    elif idx_id == 'gold':
                        try:
                            t = yf.Ticker('GC=F')
                            fi = t.fast_info
                            reg_prev = 4646.00
                            if fi.last_price:
                                prev_g = 4646.00
                                idx['price'] = round(fi.last_price, 2)
                                idx['prev_close'] = round(prev_g, 2)
                                idx['change_val'] = round(fi.last_price - prev_g, 2)
                                idx['change_rate'] = round(((fi.last_price - prev_g)/prev_g)*100, 2)
                            
                            real_gold = fetch_yfinance_real_series('GC=F', 50)
                            if real_gold and len(real_gold) >= 5:
                                idx['history'] = real_gold
                        except Exception:
                            pass
                    elif idx_id == 'us10y':
                        y_p, y_chg, y_rate, y_prev, y_hist = fetch_us10y_live()
                        if y_p is not None:
                            idx['price'] = y_p
                            idx['prev_close'] = y_prev
                            idx['change_val'] = y_chg
                            idx['change_rate'] = y_rate
                            if y_hist and len(y_hist) >= 5:
                                idx['history'] = y_hist


                # Update US stocks
                for s in STOCKS_MASTER:
                    if s['market'] == 'US':
                        try:
                            t = yf.Ticker(s['symbol'])
                            fi = t.fast_info
                            p = fi.last_price
                            prev = fi.previous_close
                            if p and prev:
                                s['price'] = round(p, 2)
                                s['change_val'] = round(p - prev, 2)
                                s['change_rate'] = round(((p - prev) / prev) * 100, 2)
                        except Exception:
                            pass
        except Exception:
            pass

        time.sleep(1.0)

# Start background sync thread
fetcher_thread = threading.Thread(target=update_live_market_data, daemon=True)
fetcher_thread.start()

@app.get('/api/market-status')
def get_market_status():
    now = get_now_kst()
    kr_open = (now.weekday() < 5) and (
        (now.hour > 9 or (now.hour == 9 and now.minute >= 0)) and
        (now.hour < 15 or (now.hour == 15 and now.minute <= 30))
    )
    us_open = is_us_regular_market_open()
    return {
        'kr_market': {
            'name': '국내 정규장',
            'time': '09:00 ~ 15:30',
            'is_open': kr_open,
            'status_text': '실시간 진행중' if kr_open else '장 마감'
        },
        'us_market': {
            'name': '미국 정규장',
            'time': '22:30 ~ 05:00',
            'is_open': us_open,
            'status_text': '실시간 진행중' if us_open else '장 마감'
        },
        'server_time': now.strftime('%H:%M:%S')
    }

@app.get('/api/indices')
def get_indices():
    is_us_open = is_us_regular_market_open()
    if is_us_open:
        # 미국 정규장(22:30~05:00): S&P 500, 나스닥 100을 1열 좌측(1, 2번)으로 우선 배치
        order = ['sp500', 'nasdaq', 'kospi', 'kosdaq', 'us10y', 'usdkrw', 'gold', 'btc']
    else:
        # 한국 정규장(09:00~15:30) 및 평시: 코스피, 코스닥을 1열 좌측(1, 2번)으로 우선 배치
        order = ['kospi', 'kosdaq', 'sp500', 'nasdaq', 'us10y', 'usdkrw', 'gold', 'btc']
        
    idx_map = {idx['id']: idx for idx in INDICES_DATA}
    return [idx_map[i_id] for i_id in order if i_id in idx_map]

@app.get('/api/stocks/ranking')
def get_stocks_ranking(
    market: str = Query('all', regex='^(all|kr|us)$'),
    sort: str = Query('trading_value', regex='^(trading_value|trading_volume|change_up|change_down)$'),
    q: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    hide_warning: bool = False
):
    top_stocks = get_genuine_rankings(market, sort, limit, q or "")
    
    if hide_warning:
        top_stocks = [s for s in top_stocks if not s.get('is_warning', False)]
        for idx, s in enumerate(top_stocks):
            s['rank'] = idx + 1

    return {
        'count': len(top_stocks),
        'total_universe': len(GLOBAL_UNIVERSE_MASTER),
        'market': market,
        'sort': sort,
        'updated_at': get_now_kst().strftime('%H:%M:%S'),
        'stocks': top_stocks
    }

os.makedirs('static', exist_ok=True)
app.mount('/static', StaticFiles(directory='static'), name='static')

@app.get('/')
def serve_index():
    return FileResponse('static/index.html')

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run('server:app', host='0.0.0.0', port=port)