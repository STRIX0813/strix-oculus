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
from typing import Optional, List
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

# Market Indices State
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
        'investors': {'individual': -17096, 'foreign': 891, 'institutional': 1590}
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
        'investors': {'individual': -866, 'foreign': 537, 'institutional': 350}
    },
    {
        'id': 'kospi_night',
        'symbol': 'KOSPI200NF',
        'name': '코스피 야간선물',
        'category': 'KR_FUTURES',
        'price': 382.45,
        'prev_close': 380.80,
        'change_val': 1.65,
        'change_rate': 0.43,
        'history': [],
        'investors': None
    },
    {
        'id': 'usdkrw',
        'symbol': 'FX_USDKRW',
        'name': '달러 환율',
        'category': 'FX',
        'price': 1380.40,
        'prev_close': 1386.00,
        'change_val': -5.60,
        'change_rate': -0.40,
        'history': [],
        'investors': None
    },
    {
        'id': 'gold',
        'symbol': 'GC=F',
        'name': '국제 금',
        'category': 'COMMODITY',
        'price': 4665.00,
        'prev_close': 4653.30,
        'change_val': 11.70,
        'change_rate': 0.25,
        'history': [],
        'investors': None
    },
    {
        'id': 'sp500',
        'symbol': 'ES=F',
        'name': 'S&P 500 선물',
        'category': 'US',
        'price': 7713.75,
        'prev_close': 7690.00,
        'change_val': 23.75,
        'change_rate': 0.31,
        'history': [],
        'investors': None
    },
    {
        'id': 'nasdaq',
        'symbol': 'NQ=F',
        'name': '나스닥 100 선물',
        'category': 'US',
        'price': 29458.00,
        'prev_close': 29289.50,
        'change_val': 168.50,
        'change_rate': 0.58,
        'history': [],
        'investors': None
    },
    {
        'id': 'sox',
        'symbol': '.SOX',
        'name': '필라델피아 반도체',
        'category': 'US',
        'price': 11611.23,
        'prev_close': 11588.03,
        'change_val': 23.20,
        'change_rate': 0.20,
        'history': [],
        'investors': None
    },
    {
        'id': 'vix',
        'symbol': '.VIX',
        'name': 'VIX',
        'category': 'US',
        'price': 15.21,
        'prev_close': 15.45,
        'change_val': -0.24,
        'change_rate': -1.55,
        'history': [],
        'investors': None
    },
    {
        'id': 'btc',
        'symbol': 'BTC-KRW',
        'name': '비트코인',
        'category': 'CRYPTO',
        'price': 109123000,
        'prev_close': 109830000,
        'change_val': -707000,
        'change_rate': -0.64,
        'history': [],
        'investors': None
    }
]

STOCKS_MASTER = [
    {
        'code': '000660',
        'symbol': '000660.KS',
        'name': 'SK하이닉스',
        'market': 'KR',
        'price': 1726000,
        'change_val': 38000,
        'change_rate': 2.25,
        'trading_value': 3091,
        'trading_volume': 1589000,
        'market_cap': '1,227.2조원',
        'buy_ratio': 60,
        'sell_ratio': 40,
        'sector': '종합반도체',
        'ai_summary': 'AI 메모리 훈풍',
        'badge_bg': '#EA002C',
        'badge_text': 'SK',
        'is_warning': False
    },
    {
        'code': '005930',
        'symbol': '005930.KS',
        'name': '삼성전자',
        'market': 'KR',
        'price': 265500,
        'change_val': 3980,
        'change_rate': 1.53,
        'trading_value': 2569,
        'trading_volume': 3280000,
        'market_cap': '1,675.0조원',
        'buy_ratio': 61,
        'sell_ratio': 39,
        'sector': '종합반도체',
        'ai_summary': '엔비디아발 훈풍',
        'badge_bg': '#1428A0',
        'badge_text': '삼성',
        'is_warning': False
    },
    {
        'code': '069500',
        'symbol': '069500.KS',
        'name': 'KODEX 200',
        'market': 'KR',
        'price': 109155,
        'change_val': 1440,
        'change_rate': 1.34,
        'trading_value': 1168,
        'trading_volume': 3038000,
        'market_cap': '25.0조원',
        'buy_ratio': 66,
        'sell_ratio': 34,
        'sector': '지수ETF',
        'ai_summary': '메모리 수요 기대',
        'badge_bg': '#0F4C81',
        'badge_text': 'KODEX',
        'is_warning': False
    },
    {
        'code': '122630',
        'symbol': '122630.KS',
        'name': 'KODEX 레버리지',
        'market': 'KR',
        'price': 110305,
        'change_val': 2800,
        'change_rate': 2.61,
        'trading_value': 1012,
        'trading_volume': 4950000,
        'market_cap': '5.7조원',
        'buy_ratio': 49,
        'sell_ratio': 51,
        'sector': '파생ETF',
        'ai_summary': '메모리 수요 기대',
        'badge_bg': '#1D4ED8',
        'badge_text': '2X',
        'is_warning': False
    },
    {
        'code': '005380',
        'symbol': '005380.KS',
        'name': '현대차',
        'market': 'KR',
        'price': 395000,
        'change_val': -13000,
        'change_rate': -3.19,
        'trading_value': 630,
        'trading_volume': 254000,
        'market_cap': '96.0조원',
        'buy_ratio': 21,
        'sell_ratio': 79,
        'sector': '자동차브랜드',
        'ai_summary': '신사업 구체성 부족',
        'badge_bg': '#002C5F',
        'badge_text': 'HYU',
        'is_warning': False
    },
    {
        'code': '009150',
        'symbol': '009150.KS',
        'name': '삼성전기',
        'market': 'KR',
        'price': 1382000,
        'change_val': 52000,
        'change_rate': 3.91,
        'trading_value': 598,
        'trading_volume': 364000,
        'market_cap': '100.1조원',
        'buy_ratio': 74,
        'sell_ratio': 26,
        'sector': '스마트폰MLCC',
        'ai_summary': 'AI 부품 수요 부각',
        'badge_bg': '#1428A0',
        'badge_text': '삼성',
        'is_warning': False
    },
    {
        'code': '133690',
        'symbol': '133690.KS',
        'name': 'TIGER 미국나스닥100',
        'market': 'KR',
        'price': 179875,
        'change_val': 1230,
        'change_rate': 0.69,
        'trading_value': 592,
        'trading_volume': 526000,
        'market_cap': '11.3조원',
        'buy_ratio': 28,
        'sell_ratio': 72,
        'sector': '해외ETF',
        'ai_summary': '빅테크 지수 추종',
        'badge_bg': '#D97706',
        'badge_text': 'TIGER',
        'is_warning': False
    },
    {
        'code': '000500',
        'symbol': '000500.KS',
        'name': '가온전선',
        'market': 'KR',
        'price': 207000,
        'change_val': 37800,
        'change_rate': 22.34,
        'trading_value': 572,
        'trading_volume': 1210000,
        'market_cap': '5.0조원',
        'buy_ratio': 54,
        'sell_ratio': 46,
        'sector': '전기설비',
        'ai_summary': '미국 전력장비 제한',
        'badge_bg': '#0284C7',
        'badge_text': '가온',
        'is_warning': True
    },
    {
        'code': '010120',
        'symbol': '010120.KS',
        'name': 'LS ELECTRIC',
        'market': 'KR',
        'price': 216000,
        'change_val': 14500,
        'change_rate': 7.20,
        'trading_value': 434,
        'trading_volume': 204000,
        'market_cap': '30.2조원',
        'buy_ratio': 81,
        'sell_ratio': 19,
        'sector': '전기설비',
        'ai_summary': '미국 장비금지 수혜',
        'badge_bg': '#0F172A',
        'badge_text': 'LS',
        'is_warning': False
    },
    {
        'code': 'NVDA',
        'symbol': 'NVDA',
        'name': '엔비디아',
        'market': 'US',
        'price': 306162,
        'change_val': 15800,
        'change_rate': 5.46,
        'trading_value': 313,
        'trading_volume': 45100000,
        'market_cap': '7,118.1조원',
        'buy_ratio': 32,
        'sell_ratio': 68,
        'sector': '반도체팹리스',
        'ai_summary': '호실적과 성장 전망',
        'badge_bg': '#76B900',
        'badge_text': 'NVDA',
        'is_warning': False
    },
    {
        'code': '012330',
        'symbol': '012330.KS',
        'name': '현대모비스',
        'market': 'KR',
        'price': 450000,
        'change_val': -14000,
        'change_rate': -3.01,
        'trading_value': 310,
        'trading_volume': 142000,
        'market_cap': '42.0조원',
        'buy_ratio': 16,
        'sell_ratio': 84,
        'sector': '자동차새시',
        'ai_summary': '주주환원 실망감',
        'badge_bg': '#1E293B',
        'badge_text': '모비스',
        'is_warning': False
    },
    {
        'code': '402340',
        'symbol': '402340.KS',
        'name': 'SK스퀘어',
        'market': 'KR',
        'price': 1067000,
        'change_val': 9000,
        'change_rate': 0.85,
        'trading_value': 302,
        'trading_volume': 85000,
        'market_cap': '138.3조원',
        'buy_ratio': 49,
        'sell_ratio': 51,
        'sector': '지주사',
        'ai_summary': '엔비디아 훈풍',
        'badge_bg': '#EA002C',
        'badge_text': 'SK',
        'is_warning': False
    },
    {
        'code': '006400',
        'symbol': '006400.KS',
        'name': '삼성SDI',
        'market': 'KR',
        'price': 567000,
        'change_val': 51000,
        'change_rate': 9.88,
        'trading_value': 279,
        'trading_volume': 72500,
        'market_cap': '41.8조원',
        'buy_ratio': 84,
        'sell_ratio': 16,
        'sector': '배터리제조',
        'ai_summary': '4조원대 현금 확보',
        'badge_bg': '#1428A0',
        'badge_text': '삼성',
        'is_warning': False
    },
    {
        'code': 'TSLA',
        'symbol': 'TSLA',
        'name': '테슬라',
        'market': 'US',
        'price': 345.82,
        'change_val': -4.88,
        'change_rate': -1.39,
        'trading_value': 1850,
        'trading_volume': 38200000,
        'market_cap': '6980억$',
        'buy_ratio': 72,
        'sell_ratio': 28,
        'sector': '전기차',
        'ai_summary': '로보택시 공개 일정 기대감 반영',
        'badge_bg': '#E82127',
        'badge_text': 'TSLA',
        'is_warning': False
    },
    {
        'code': 'AAPL',
        'symbol': 'AAPL',
        'name': '애플',
        'market': 'US',
        'price': 313.45,
        'change_val': 4.10,
        'change_rate': 1.33,
        'trading_value': 1420,
        'trading_volume': 28900000,
        'market_cap': '3.43조$',
        'buy_ratio': 58,
        'sell_ratio': 42,
        'sector': '빅테크',
        'ai_summary': 'Apple Intelligence 기기 교체 수요',
        'badge_bg': '#555555',
        'badge_text': 'AAPL',
        'is_warning': False
    }
]

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
        df = t.history(period='1d', interval='5m')
        if df is not None and not df.empty:
            closes = [round(float(c), 2) for c in df['Close'].tolist()]
            return closes[-count:] if len(closes) >= count else closes
    except Exception:
        pass
    return []

# Fetch KP선물 (코스피 200 선물 / KPI200) live
def fetch_kp_futures_live():
    try:
        api_url = 'https://m.stock.naver.com/api/index/KPI200/basic'
        req_api = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        res_data = json.loads(urllib.request.urlopen(req_api, context=ssl_ctx, timeout=3).read().decode('utf-8'))
        
        p = float(res_data.get('closePrice', '0').replace(',', ''))
        chg = float(res_data.get('compareToPreviousClosePrice', '0').replace(',', ''))
        rate = float(res_data.get('fluctuationsRatio', '0').replace(',', ''))
        if res_data.get('compareToPreviousPrice', {}).get('name') == 'FALLING':
            chg = -abs(chg)
            rate = -abs(rate)
            
        prev_close = round(p - chg, 2)

        chart_url = 'https://api.stock.naver.com/chart/domestic/index/KPI200?periodType=day'
        req_chart = urllib.request.Request(chart_url, headers={'User-Agent': 'Mozilla/5.0'})
        res_chart = json.loads(urllib.request.urlopen(req_chart, context=ssl_ctx, timeout=3).read().decode('utf-8'))
        prices = [item.get('currentPrice') for item in res_chart.get('priceInfos', []) if item.get('currentPrice')]
        history = prices[-50:] if len(prices) >= 50 else prices
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
                        try:
                            t = yf.Ticker('NQ=F')
                            fi = t.fast_info
                            reg_prev = t.info.get('regularMarketPreviousClose') or fi.previous_close
                            if fi.last_price and reg_prev:
                                idx['price'] = round(fi.last_price, 2)
                                idx['prev_close'] = round(reg_prev, 2)
                                idx['change_val'] = round(fi.last_price - reg_prev, 2)
                                idx['change_rate'] = round(((fi.last_price - reg_prev)/reg_prev)*100, 2)
                            
                            real_nq = fetch_yfinance_real_series('NQ=F', 50)
                            if real_nq and len(real_nq) >= 5:
                                idx['history'] = real_nq
                        except Exception:
                            pass
                    elif idx_id == 'sp500':
                        try:
                            t = yf.Ticker('ES=F')
                            fi = t.fast_info
                            reg_prev = t.info.get('regularMarketPreviousClose') or fi.previous_close
                            if fi.last_price and reg_prev:
                                idx['price'] = round(fi.last_price, 2)
                                idx['prev_close'] = round(reg_prev, 2)
                                idx['change_val'] = round(fi.last_price - reg_prev, 2)
                                idx['change_rate'] = round(((fi.last_price - reg_prev)/reg_prev)*100, 2)
                            
                            real_es = fetch_yfinance_real_series('ES=F', 50)
                            if real_es and len(real_es) >= 5:
                                idx['history'] = real_es
                        except Exception:
                            pass
                    elif idx_id == 'gold':
                        try:
                            t = yf.Ticker('GC=F')
                            fi = t.fast_info
                            reg_prev = t.info.get('regularMarketPreviousClose') or fi.previous_close
                            if fi.last_price and reg_prev:
                                idx['price'] = round(fi.last_price, 2)
                                idx['prev_close'] = round(reg_prev, 2)
                                idx['change_val'] = round(fi.last_price - reg_prev, 2)
                                idx['change_rate'] = round(((fi.last_price - reg_prev)/reg_prev)*100, 2)
                            
                            real_gold = fetch_yfinance_real_series('GC=F', 50)
                            if real_gold and len(real_gold) >= 5:
                                idx['history'] = real_gold
                        except Exception:
                            pass
                    elif idx_id == 'sox':
                        try:
                            t = yf.Ticker('^SOX')
                            fi = t.fast_info
                            if fi.last_price and fi.previous_close:
                                idx['price'] = round(fi.last_price, 2)
                                idx['prev_close'] = round(fi.previous_close, 2)
                                idx['change_val'] = round(fi.last_price - fi.previous_close, 2)
                                idx['change_rate'] = round(((fi.last_price - fi.previous_close)/fi.previous_close)*100, 2)
                            
                            real_sox = fetch_yfinance_real_series('^SOX', 50)
                            if real_sox and len(real_sox) >= 5:
                                idx['history'] = real_sox
                        except Exception:
                            pass
                    elif idx_id == 'vix':
                        try:
                            t = yf.Ticker('^VIX')
                            fi = t.fast_info
                            if fi.last_price and fi.previous_close:
                                idx['price'] = round(fi.last_price, 2)
                                idx['prev_close'] = round(fi.previous_close, 2)
                                idx['change_val'] = round(fi.last_price - fi.previous_close, 2)
                                idx['change_rate'] = round(((fi.last_price - fi.previous_close)/fi.previous_close)*100, 2)
                            
                            real_vix = fetch_yfinance_real_series('^VIX', 50)
                            if real_vix and len(real_vix) >= 5:
                                idx['history'] = real_vix
                        except Exception:
                            pass
                    elif idx_id == 'kospi_night':
                        kp_p, kp_chg, kp_rate, kp_prev, kp_hist = fetch_kp_futures_live()
                        if kp_p is not None:
                            idx['symbol'] = 'KPI200'
                            idx['price'] = kp_p
                            idx['prev_close'] = kp_prev
                            idx['change_val'] = kp_chg
                            idx['change_rate'] = kp_rate
                            if kp_hist and len(kp_hist) >= 5:
                                idx['history'] = kp_hist

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
    return INDICES_DATA

@app.get('/api/stocks/ranking')
def get_stocks_ranking(
    market: str = Query('all', regex='^(all|kr|us)$'),
    sort: str = Query('trading_value', regex='^(trading_value|trading_volume|change_up|change_down)$'),
    hide_warning: bool = False
):
    stocks = [dict(s) for s in STOCKS_MASTER]

    if market == 'kr':
        stocks = [s for s in stocks if s['market'] == 'KR']
    elif market == 'us':
        stocks = [s for s in stocks if s['market'] == 'US']

    if hide_warning:
        stocks = [s for s in stocks if not s.get('is_warning', False)]

    if sort == 'trading_value':
        stocks.sort(key=lambda x: x['trading_value'], reverse=True)
    elif sort == 'trading_volume':
        stocks.sort(key=lambda x: x['trading_volume'], reverse=True)
    elif sort == 'change_up':
        stocks.sort(key=lambda x: x['change_rate'], reverse=True)
    elif sort == 'change_down':
        stocks.sort(key=lambda x: x['change_rate'])

    for idx, s in enumerate(stocks):
        s['rank'] = idx + 1

    return {
        'count': len(stocks),
        'updated_at': get_now_kst().strftime('%H:%M:%S'),
        'stocks': stocks
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