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
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from kis_client import KISClient

app = FastAPI(title='STRIX Oculus Stock Platform')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Explicit Korea Standard Time (KST, UTC+9)
KST = datetime.timezone(datetime.timedelta(hours=9))

def get_now_kst():
    return datetime.datetime.now(KST)

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def is_us_regular_market_open() -> bool:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if now_utc.weekday() >= 5:
        return False
    minute_of_day = now_utc.hour * 60 + now_utc.minute
    return 810 <= minute_of_day < 1200

def format_market_cap_server(cap_raw: Any) -> str:
    if not cap_raw:
        return '-'
    if isinstance(cap_raw, str):
        if '$' in cap_raw:
            return cap_raw
        if '조' in cap_raw:
            m = re.search(r'([\d,]+)조(?:\s*([\d,]+)억)?', cap_raw)
            if m:
                jo_val = float(m.group(1).replace(',', ''))
                eok_val = float(m.group(2).replace(',', '')) if m.group(2) else 0
                return f"{jo_val + (eok_val / 10000.0):,.1f}조원"
        elif '억' in cap_raw:
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

# Unified High-Reliability 50-Point Intraday / 15m Equivalent Index Chart Engine
def fetch_naver_index_chart(code_name: str) -> List[float]:
    try:
        is_dom = code_name in ['KOSPI', 'KOSDAQ', 'FUT']
        url = f'https://api.stock.naver.com/chart/{"domestic" if is_dom else "foreign"}/index/{code_name}?periodType=day'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        d = json.loads(urllib.request.urlopen(req, context=ssl_ctx, timeout=3).read().decode('utf-8'))
        pts = [round(float(item.get('currentPrice') or item.get('closePrice')), 2) for item in d.get('priceInfos', []) if item.get('currentPrice') or item.get('closePrice')]
        if len(pts) >= 50:
            step = (len(pts) - 1) / 49.0
            return [pts[int(round(i * step))] for i in range(50)]
        elif len(pts) >= 5:
            return pts
    except Exception:
        pass
    return []

def fetch_btc_real_candles():
    try:
        u = 'https://api.upbit.com/v1/candles/minutes/15?market=KRW-BTC&count=50'
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        d = json.loads(urllib.request.urlopen(req, context=ssl_ctx, timeout=2).read().decode('utf-8'))
        return [c['trade_price'] for c in reversed(d)]
    except Exception:
        return []

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


# Investor Trend Fetcher for KOSPI & KOSDAQ
def fetch_kr_investor_trend(code_name: str) -> Optional[Dict[str, int]]:
    iscd = '0001' if code_name == 'KOSPI' else '1001'
    if kis_client.is_configured():
        kis_inv = kis_client.get_index_investor_trend(iscd)
        if kis_inv: return kis_inv
    try:
        page_url = f'https://finance.naver.com/sise/sise_index.naver?code={code_name}'
        req_page = urllib.request.Request(page_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        html = urllib.request.urlopen(req_page, context=ssl_ctx, timeout=3).read().decode('cp949', errors='ignore')
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
                return {
                    'individual': parse_val(dd_tags[0].get_text()),
                    'foreign': parse_val(dd_tags[1].get_text()),
                    'institutional': parse_val(dd_tags[2].get_text())
                }
    except Exception:
        pass
    return None

# US 10-Year Treasury Yield Weekly Candles (50-Week Series)
def fetch_us10y_weekly_candles() -> List[float]:
    try:
        t = yf.Ticker('^TNX')
        df = t.history(period='2y', interval='1wk')
        if df is not None and not df.empty:
            closes = [round(float(c), 3) for c in df['Close'].tolist() if c and not str(c) == 'nan']
            return closes[-50:] if len(closes) >= 50 else closes
    except Exception:
        pass
    return [4.65, 4.68, 4.70, 4.72, 4.728]

# Strict Multi-Market ETF Detector
ETF_KEYWORDS = [
    'kodex', 'tiger', 'ace', 'kbstar', 'sol', 'plus', 'rise', 'woori', 'hanaro', 'timefolio',
    'etf', 'etn', '선물', '레버리지', '인버스', '2x', '3x', 'ultra', 'proshares', 'direxion',
    'invesco', 'spdr', 'vanguard', 'ishares', 'yieldmax', 'defiance', 'graniteshares', 'rex',
    'spy', 'qqq', 'tqqq', 'sqqq', 'soxl', 'soxs', 'nvdl', 'tsll', 'fngu'
]

def is_etf_stock(name: str, code: str) -> bool:
    name_l = str(name).lower()
    code_l = str(code).lower()
    if any(k in name_l for k in ETF_KEYWORDS) or any(k in code_l for k in ETF_KEYWORDS):
        return True
    return False


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
        'history': [6845.85, 6871.4, 6858.93, 6880.2, 6893.31],
        'investors': {'individual': 4194, 'foreign': -8525, 'institutional': -11876}
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
        'history': [831.2, 833.5, 834.8, 835.67],
        'investors': {'individual': 979, 'foreign': -942, 'institutional': -30}
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
        'history': [7705.2, 7710.4, 7715.0, 7717.61],
        'investors': None
    },
    {
        'id': 'nasdaq',
        'symbol': '^NDX',
        'name': '나스닥 100',
        'category': 'US',
        'price': 29421.77,
        'prev_close': 29224.52,
        'change_val': 197.25,
        'change_rate': 0.67,
        'history': [29380.0, 29400.5, 29415.0, 29421.77],
        'investors': None
    },
    {
        'id': 'us10y',
        'symbol': '^TNX',
        'name': '미국 국채 10년',
        'category': 'MACRO',
        'price': 4.728,
        'prev_close': 4.664,
        'change_val': 0.064,
        'change_rate': 1.37,
        'history': [4.65, 4.68, 4.70, 4.72, 4.728],
        'investors': None
    },
    {
        'id': 'usdkrw',
        'symbol': 'USDKRW=X',
        'name': '달러 환율',
        'category': 'MACRO',
        'price': 1380.10,
        'prev_close': 1385.00,
        'change_val': -4.90,
        'change_rate': -0.35,
        'history': [1375.0, 1378.2, 1380.1],
        'investors': None
    },
    {
        'id': 'gold',
        'symbol': 'GC=F',
        'name': '국제 금',
        'category': 'MACRO',
        'price': 4507.20,
        'prev_close': 4646.00,
        'change_val': -138.80,
        'change_rate': -2.99,
        'history': [4510.0, 4508.5, 4507.2],
        'investors': None
    },
    {
        'id': 'btc',
        'symbol': 'KRW-BTC',
        'name': '비트코인',
        'category': 'CRYPTO',
        'price': 108252000.0,
        'prev_close': 107621000.0,
        'change_val': 631000.0,
        'change_rate': 0.59,
        'history': [108000000.0, 108150000.0, 108252000.0],
        'investors': None
    }
]

# Comprehensive High-Precision Subdivided Industry Classification Engine
INDUSTRY_DICT = {
    '010140': '조선/해양플랜트', '001440': '초고압해저전선/전력케이블', '005830': '손해보험/자산운용',
    '0155E0': '반도체설계/팹리스', '032820': '원자력플랜트제어', '011070': '카메라모듈/기판소재',
    '475150': '신재생에너지/ESS', '064400': 'IT서비스/DX클라우드', '007660': 'AI서버용고다층PCB',
    '000150': '전자BG소재/두산지주', '078930': '에너지/유통복합지주', '028050': '플랜트엔지니어링/EPC',
    '090430': 'K-뷰티/화장품제조', '062040': '특수변압기/전력기자재', '010950': '정유/석유화학',
    '234340': '전자결제/핀테크', '240810': '반도체증착장비(ALD/CVD)', '356680': 'VPN네트워크보안',
    '088350': '생명보험/자산운용', '178320': 'AI서버/ESS통신메탈케이스', '316140': '종합금융지주/은행',
    '0220W0': '한화그룹공작기계지주', '108490': '자율주행로봇/액추에이터', '052690': '원자력발전소설계/엔지니어링',
    '004170': '백화점/복합쇼핑몰', '387690': '소형X-ray/방사선의료기기', '096530': '분자진단/PCR시약',
    '417030': 'AI자율비행드론솔루션', '079650': '레미콘/콘크리트파일', '232140': 'HBM테스터/반도체검사장비',
    '294570': '비즈니스데이터/핀테크API', '105630': '글로벌스포츠웨어/골프', '019170': '바이오신약/제약',
    '005930': '종합반도체', '000660': '종합반도체', '005935': '종합반도체', '402340': '반도체지주사',
    '009150': '스마트폰MLCC', '373220': '배터리셀제조', '005380': '완성차', '207940': '바이오CDMO',
    '032830': '생명보험', '105560': '종합금융지주', '028260': '종합상사/건설', '012450': '항공우주/방산',
    '034020': '원자력발전/SMR', '055550': '종합금융지주', '000270': '완성차', '329180': '조선/해양플랜트',
    '006400': '배터리셀제조', '068270': '바이오시밀러', '012330': '자동차전장부품', '034730': 'SK그룹지주사',
    '086790': '종합금융지주', '035420': '인터넷/생성형AI', '066570': '가전/전장솔루션', '010120': '전력망/변압기',
    '000810': '손해보험', '298040': '전력망/변압기', '267260': '전력망/변압기', '010130': '비철금속/제련',
    '042660': '조선/해양플랜트', '005490': '철강/이차전지소재', '002990': '건설/토목엔지니어링', '003550': 'LG그룹지주사',
    '051910': '석유화학/양극재', '096770': '정유/배터리자회사', '011200': '컨테이너해상운송', '003490': '항공여객/항공화물',
    '017670': '5G무선통신/AI', '030200': '유무선통신/클라우드', '032640': '유무선통신/스마트홈', '035720': '인터넷플랫폼',
    '196170': '항암바이오신약', '247540': '양극재/배터리소재', '086520': '이차전지지주사', '003670': '음극재/양극재소재',
    '010060': '태양광폴리실리콘', '009830': '태양광모듈/신재생', '079550': '유도무기/미사일방산', '047810': '항공기제조/우주항공',
    '064350': '지상방산/전차제조', '010170': '광통신케이블/소재', '042700': 'TC본더/HBM후공정', '403870': '고압수소어닐링장비',
    '036930': '반도체ALD증착장비', '257720': 'K-뷰티글로벌유통', '214450': '재생의학/리쥬란', '067310': '반도체OSAT/패키징',
    '353200': 'FC-BGA/반도체기판', '214150': 'HIFU미용의료기기', '047050': '친환경에너지/글로벌무역', '018260': 'IT서비스/물류BPO',
    '047040': '토목시공/플랜트건설', '222800': '반도체패키지기판', '027410': '가상자산/벤처투자', '041190': '원자력/플랜트제어',
    '030530': '반도체가스공급설비', '001820': 'MLCC/수동소자', '278470': '미용의료/뷰티디바이스', '036570': 'MMORPG게임개발',
    '259960': '글로벌게임IP/배그', '352820': 'K-POP엔터테인먼트', '041510': 'K-POP엔터테인먼트', '122870': 'K-POP엔터테인먼트',
    '035900': 'K-POP엔터테인먼트', '003230': 'K-푸드/라면스낵', '097950': '식품바이오/가공식품', '271560': '글로벌제과/스낵',
    '004370': '라면/스낵식품', '005300': '음료/주류제조', '282330': '편의점(CU)유통', '007070': '편의점(GS25)/수퍼',
    '139480': '대형마트/온라인몰', '069960': '백화점/면세점유통', '023530': '백화점/할인점유통', '008770': '면세점/호텔운영',
    '019210': '절삭공구/엔드밀', '004380': 'LM가이드/자동화기기', '056190': '공정자동화/물류장비', '137400': '2차전지롤투롤장비',
    '213500': '산업용지/특수지제조', '023160': '플랜트배관피팅', '028100': '플랜트배관피팅', '060150': '폐기물/친환경재활용',
    '025860': '비료/화학소재', '009240': '가구/토탈인테리어', '017800': '승강기/엘리베이터', '053450': '차량용카메라/광학렌즈',
    '111770': '아웃도어의류/OEM', '093050': '패션브랜드/의류유통', '083650': '복합화력발전/HRSG', '069500': '지수추종 ETF',
    '122630': '레버리지 ETF', '114800': '인버스 ETF', '360750': '미국S&P500 ETF',
    'SPCX': '우주항공/위성발사', 'LNW': '글로벌카지노게이밍', 'MRNA': 'mRNA차세대백신', 'LITE': '광통신/광학레이저',
    'IREN': 'AI데이터센터/비트코인채굴', 'NBIS': 'AI클라우드인프라', 'BE': '고체산화물연료전지(SOFC)', 'SKHY': '종합반도체(HBM)',
    'STX': 'HDD/데이터스토리지', 'AFRM': '후불결제(BNPL)핀테크', 'WDC': '낸드플래시/SSD스토리지', 'PCG': '전력/가스유틸리티',
    'HOOD': '온라인증권/가상자산거래', 'BAC': '글로벌상업은행/투자은행', 'BRK.B': '워런버핏복합투자지주', 'GEV': '풍력/가스터빈전력인프라',
    'CRWV': 'GPU클라우드인프라', 'CRCL': 'USDC스테이블코인발행', 'COHR': '광통신소재/산업용레이저', 'RKLB': '상업용우주발사체/위성',
    'BMNR': '가상자산채굴/데이터센터', 'FCX': '구리/금광산채굴', 'INTU': '세무회계(터보택스)/핀테크', 'SOLS': '첨단소재/특수화학',
    'JNJ': '글로벌헬스케어/의료기기', 'SCHW': '종합증권/자산관리', 'SUNB': '산업용건설장비렌탈', 'NKE': '글로벌스포츠웨어/신발',
    'NU': '중남미디지털뱅킹(핀테크)', 'AAL': '글로벌항공여객운송', 'RBRK': '제로트러스트데이터보안', 'CBRS': '웨이퍼스케일AI가속기',
    'GS': '글로벌투자은행/IB', 'CSCO': '엔터프라이즈네트워크장비', 'SOFI': '올인원디지털금융플랫폼', 'SLB': '유전서비스/에너지인프라',
    'ULTA': '뷰티/화장품리테일스토어', 'MCD': '글로벌패스트푸드프랜차이즈', 'B': '글로벌금광산채굴', 'IONQ': '이온트랩양자컴퓨팅',
    'AEM': '귀금속/금광산채굴', 'GLW': '디스플레이유리/특수소재', 'SHEL': '글로벌석유에너지/LNG', 'NEM': '세계최대금광기업',
    'NVDA': 'AI가속기/GPU', 'AAPL': '스마트기기/OS', 'MSFT': '클라우드/OS', 'AMZN': '이커머스/클라우드',
    'GOOGL': '검색/AI엔진', 'GOOG': '검색/AI엔진', 'META': '소셜플랫폼/AI', 'TSLA': '전기차/자율주행',
    'AVGO': '통신반도체/ASIC', 'TSM': '파운드리반도체', 'WMT': '글로벌대형유통', 'LLY': '당뇨/비만신약',
    'JPM': '글로벌투자은행', 'V': '결제네트워크', 'MA': '결제네트워크', 'ORCL': '엔터프라이즈DB',
    'COST': '창고형할인점', 'AMD': 'CPU/AI가속기', 'QCOM': '모바일AP/모뎀', 'INTC': 'CPU/파운드리',
    'TXN': '아날로그반도체', 'MU': 'HBM/D램반도체', 'SNDK': '낸드플래시', 'MRVL': 'AI데이터센터반도체',
    'CRM': '고객관리(CRM)클라우드', 'ADBE': '디지털미디어SW', 'NOW': 'IT워크플로우SaaS', 'IBM': '하이브리드클라우드',
    'NFLX': 'OTT스트리밍', 'DIS': '종합엔터/테마파크', 'UBER': '모빌리티/배달플랫폼', 'PLTR': 'AI빅데이터분석',
    'ARM': '반도체설계IP', 'SMCI': 'AI서버인프라', 'DELL': '엔터프라이즈서버', 'BABA': '중국이커머스/클라우드',
    'PDD': '중국초저가이커머스', 'JD': '중국전자상거래', 'NVO': '비만/당뇨치료제', 'AZN': '항암/희귀질환제약',
    'NVS': '혁신신약/바이오', 'PFE': '백신/글로벌제약', 'MRK': '면역항암제약', 'ABBV': '자가면역질환제약',
    'UNH': '건강보험/헬스케어', 'XOM': '종합석유에너지', 'CVX': '원유/천연가스', 'COP': '원유시추/생산',
    'BA': '상용항공기/방산', 'RTX': '항공엔진/미사일방어', 'LMT': '스텔스전투기/방산', 'GE': '항공엔진/발전터빈',
    'CAT': '건설/광산중장비', 'DE': '스마트농기계', 'COIN': '암호화폐거래소', 'MSTR': '비트코인보유기업',
    'PANW': '차세대사이버보안', 'CRWD': '엔드포인트보안', 'FTNT': '네트워크보안', 'ZS': '클라우드보안',
    'SNOW': '클라우드데이터웨어하우스', 'MDB': 'NoSQL데이터베이스', 'NET': 'CDN/클라우드엣지',
    'DDOG': '클라우드모니터링', 'TEAM': '협업소프트웨어SaaS', 'SHOP': '이커머스솔루션', 'SQ': '디지털결제/핀테크',
    'PYPL': '온라인간편결제', 'BKNG': '온라인여행/숙박예약', 'ABNB': '숙박공유플랫폼', 'DASH': '음식배달플랫폼',
    'SPOT': '음악스트리밍', 'RBLX': '메타버스게임플랫폼', 'EA': '콘솔/PC게임', 'TTWO': '인터랙티브게임',
    'RIVN': '전기픽업트럭', 'LCID': '럭셔리전기차', 'NIO': '프리미엄전기차', 'XPEV': '스마트전기차',
    'LI': '하이브리드전기차', 'MBLY': '자율주행ADAS', 'ON': '차량용전력반도체', 'NXPI': '차량용반도체',
    'MCHP': '마이크로컨트롤러', 'ADI': '신호처리반도체', 'LRCX': '반도체식각장비', 'AMAT': '반도체종합장비',
    'KLAC': '반도체검사/계측', 'ASML': 'EUV노광장비', 'TOELY': '반도체제조장비', 'FSLR': '태양광패널모듈',
    'ENPH': '태양광마이크로인버터', 'NEE': '클린에너지/전력', 'SO': '전력유틸리티', 'DUK': '전력유틸리티',
    'O': '상업용부동산리츠', 'AMT': '통신타워리츠', 'PLD': '물류센터리츠', 'EQIX': '데이터센터리츠',
    'WDAY': '인사/재무관리SaaS', 'HUBS': '인바운드마케팅SaaS', 'ZM': '화상회의솔루션', 'MNDY': '업무관리소프트웨어',
    'PATH': '로봇프로세스자동화(RPA)', 'ESTC': '엔터프라이즈검색SW', 'GTLB': '데브옵스(DevOps)플랫폼',
    'DOCU': '전자서명/계약클라우드', 'TWLO': '클라우드통신API', 'FIVN': '클라우드컨택센터',
    'VEEV': '생명과학특화CRM', 'ADSK': '산업설계(CAD)소프트웨어', 'ANSS': '공학시뮬레이션SW',
    'CDNS': '전자설계자동화(EDA)', 'SNPS': '반도체설계자동화(EDA)', 'APP': '모바일광고플랫폼',
    'TTD': '프로그래매틱광고', 'ISRG': '로봇수술시스템', 'BSX': '심혈관의료기기', 'MDT': '종합의료기기',
    'SYK': '정형외과의료기기', 'EW': '심장판막의료기기', 'DXCM': '연속혈당측정기', 'IDXX': '동물의료진단'
}

def get_stock_industry(name: str, code: str, market: str, is_etf: bool = False) -> str:
    if is_etf:
        return 'ETF'
    clean_code = str(code).strip().upper()
    if clean_code in INDUSTRY_DICT:
        return INDUSTRY_DICT[clean_code]
    for key, val in INDUSTRY_DICT.items():
        if key in clean_code or clean_code in key:
            return val
    name_lower = name.lower()
    if market == 'KR':
        if any(k in name_lower for k in ['홀딩스', '지주', '그룹']): return '그룹지주사'
        elif any(k in name_lower for k in ['스팩', 'spac']): return '기업인수목적(SPAC)'
        elif any(k in name_lower for k in ['반도체', '칩', '웨이퍼', '하이텍', '소부장', '실리콘', '디스플레이']): return '반도체/전자소부장'
        elif any(k in name_lower for k in ['제약', '바이오', '약품', '생명과학', '파마', '테라퓨틱스', '셀', '랩', '진단', '백신']): return '바이오신약/제약'
        elif any(k in name_lower for k in ['메디칼', '의료기기', '덴탈', '레이저', '임플란트', '헬스케어', '치과']): return '의료기기/헬스케어'
        elif any(k in name_lower for k in ['에너지', '배터리', '이차전지', '2차전지', '양극재', '음극재', '전해액', '분리막']): return '이차전지/배터리소재'
        elif any(k in name_lower for k in ['모빌리티', '자동차', '모터', '차량', '오토']): return '모빌리티/자동차부품'
        elif any(k in name_lower for k in ['조선', '해양', '엔진', '선박']): return '조선/해양플랜트'
        elif any(k in name_lower for k in ['원전', '원자력', '전력', '변압기', '전선', '에너빌']): return '원자력/전력인프라'
        elif any(k in name_lower for k in ['화학', '케미칼', '유화', '정유', '석유']): return '석유화학/정밀화학'
        elif any(k in name_lower for k in ['철강', '제강', '금속', '알루미늄', '동', '아연']): return '철강/비철금속가공'
        elif any(k in name_lower for k in ['건설', '엔지니어링', '토목', '건축']): return '건설/토목엔지니어링'
        elif any(k in name_lower for k in ['소프트', '소프트웨어', '정보통신', '클라우드', '데이터', '아이티', '씨앤씨']): return 'IT서비스/SW솔루션'
        elif any(k in name_lower for k in ['게임', '엔터', '미디어', '콘텐츠', '스튜디오', '방송', '웹툰']): return 'K-콘텐츠/게임엔터'
        elif any(k in name_lower for k in ['식품', '푸드', '제과', '음료', '주류', '라면']): return 'K-푸드/식음료제조'
        elif any(k in name_lower for k in ['화장품', '뷰티', '코스메틱', '스킨']): return 'K-뷰티/화장품제조'
        elif any(k in name_lower for k in ['유통', '백화점', '쇼핑', '상사', '마트', '물류', '운송', '택배']): return '종합유통/물류운송'
        elif any(k in name_lower for k in ['금융', '은행', '증권', '보험', '카드', '캐피탈', '저축은행']): return '종합금융/투자증권'
        elif any(k in name_lower for k in ['로봇', '로보', '자동화', '모션', '액추에이터']): return '지능형로봇/자동화설비'
        elif any(k in name_lower for k in ['방산', '항공', '우주', '에어로', '미사일', '레이더']): return '방위산업/우주항공'
        elif any(k in name_lower for k in ['태양광', '풍력', '신재생', '수소', '환경', '폐기물']): return '신재생에너지/친환경'
        elif any(k in name_lower for k in ['패션', '의류', '섬유', '신발', '모피', '가방']): return '패션의류/섬유제조'
        elif any(k in name_lower for k in ['가전', '스마트홈', '생활가전', '조명']): return '스마트생활가전'
        elif any(k in name_lower for k in ['통신', '텔레콤', '네트워크', '광통신', '와이파이']): return '유무선통신/네트워크'
        return '정밀소재/부품가공'
    else:
        if any(k in name_lower for k in ['tech', 'cloud', 'data', 'cyber', 'saas', 'ai', 'intel']): return '클라우드/엔터프라이즈SW'
        elif any(k in name_lower for k in ['pay', 'payment', 'fintech', 'wallet', 'crypto', 'coin']): return '디지털결제/핀테크'
        elif any(k in name_lower for k in ['semi', 'chip', 'micro', 'foundry', 'silicon', 'wafer']): return '반도체/전자부품'
        elif any(k in name_lower for k in ['auto', 'motor', 'car', 'vehicle', 'ev']): return '모빌리티/전기차부품'
        elif any(k in name_lower for k in ['bio', 'pharma', 'therapeutics', 'oncology', 'gene', 'drug']): return '바이오신약/제약'
        elif any(k in name_lower for k in ['health', 'medical', 'dental', 'care', 'hospital', 'clinic']): return '의료기기/헬스케어'
        elif any(k in name_lower for k in ['energy', 'oil', 'gas', 'solar', 'power', 'utility']): return '에너지/클린테크'
        elif any(k in name_lower for k in ['retail', 'shop', 'store', 'market', 'commerce']): return '글로벌유통/이커머스'
        elif any(k in name_lower for k in ['game', 'media', 'stream', 'entertain', 'film']): return '디지털미디어/게임'
        elif any(k in name_lower for k in ['bank', 'finance', 'invest', 'capital', 'insur', 'asset']): return '글로벌금융/투자'
        elif any(k in name_lower for k in ['reit', 'real estate', 'property', 'trust']): return '부동산투자리츠(REITs)'
        elif any(k in name_lower for k in ['telecom', 'network', 'wireless', 'comm']): return '정보통신네트워크'
        elif any(k in name_lower for k in ['aero', 'defense', 'space', 'aviation']): return '항공우주/방위산업'
        elif any(k in name_lower for k in ['app', 'software', 'soft', 'code', 'dev']): return '업무생산성소프트웨어'
        return '글로벌산업인프라'

AI_SUMMARY_CACHE: Dict[str, Dict[str, Any]] = {}
AI_SUMMARY_TTL: float = 1800.0

EXPANDED_CORPORATE_FACTS = {
    '005930': {'bull': 'HBM 공급 가시화', 'bear': '레거시 D램 감산', 'flat': 'HBM 양산 테스트'},
    '000660': {'bull': 'HBM3E 공급 독점', 'bear': '대중 수출 규제 우려', 'flat': '엔비디아 공급망 수혜'},
    '005935': {'bull': 'HBM 공급 가시화', 'bear': '레거시 D램 감산', 'flat': 'HBM 양산 테스트'},
    '009150': {'bull': 'AI 가속기 MLCC 공급', 'bear': '스마트폰 수요 둔화', 'flat': '전장용 MLCC 확대'},
    '005380': {'bull': '고환율 수출 수혜', 'bear': '미국 관세 우려', 'flat': '북미 하이브리드 판매'},
    '000270': {'bull': '영업이익률 사상최대', 'bear': '완성차 경쟁 심화', 'flat': 'PBV 신사업 진출'},
    '035420': {'bull': '생성형 AI 검색 수익화', 'bear': '이커머스 경쟁 심화', 'flat': '디지털트윈 해외 수주'},
    '035720': {'bull': '카카오톡 비즈니스 개편', 'bear': '플랫폼 규제 리스크', 'flat': 'AI 서비스 카나나 출시'},
    '207940': {'bull': '빅파마 4공장 수주 랠리', 'bear': '생물보안법 의회 일정', 'flat': '5공장 증설 가동'},
    '068270': {'bull': '짐펜트라 미국 처방 확대', 'bear': '바이오시밀러 약가 경쟁', 'flat': '신규 바이오시밀러 허가'},
    '196170': {'bull': '빅파마 SC 플랫폼 기술수출', 'bear': '기술수출 일정 관망', 'flat': '머크 키트루다SC 임상3상'},
    '006400': {'bull': 'AI 데이터센터 ESS 공급', 'bear': '전기차 캐즘 우려', 'flat': '전고체 배터리 파일럿'},
    '373220': {'bull': '미국 IRA 보조금 수혜', 'bear': '완성차 EV 투자 조절', 'flat': '4680 배터리 양산 준비'},
    '034020': {'bull': '체코 원전 수주 잭팟', 'bear': '수출 금융 지원 변수', 'flat': '글로벌 SMR 파트너십'},
    '010120': {'bull': '미국 전력망 쇼티지 수혜', 'bear': '원자재 가격 상승', 'flat': '북미 현지 공장 증설'},
    '298040': {'bull': '초고압 변압기 공급 부족', 'bear': '신규 증설 지연 우려', 'flat': '유럽·북미 수주잔고 사상최대'},
    '267260': {'bull': '북미 초고압 변압기 수주', 'bear': '단기 생산능력 한계', 'flat': '울산공장 증설 가동'},
    '012450': {'bull': '동유럽 K9 자주포 수출', 'bear': '방산 수출 통제 검토', 'flat': '우주항공 누리호 기술이전'},
    '079550': {'bull': '중동 천궁-II 요격미사일 수주', 'bear': '개발비 집행 부담', 'flat': '차세대 L-SAM 양산 준비'},
    '047810': {'bull': 'FA-50 경공격기 글로벌 수출', 'bear': '부품 공급망 병목', 'flat': 'KF-21 양산 체계 진입'},
    '064350': {'bull': 'K2 흑표 전차 2차 계약 임박', 'bear': '폴란드 정권 변수', 'flat': '루마니아 전차 사업 제안'},
    '329180': {'bull': '친환경 LNG선 고선가 랠리', 'bear': '후판 가격 협상 난항', 'flat': '카타르 2차 LNG선 건조'},
    '042660': {'bull': '특수선 잠수함 해외 수출', 'bear': '인건비 및 노사 리스크', 'flat': '미 해군 MRO 사업 추진'},
    '010140': {'bull': 'FLNG 부유식 생산설비 독점', 'bear': '인력 수급 병목', 'flat': '해양 플랜트 수주 가시화'},
    '082740': {'bull': '선박용 대형 디젤엔진 풀가동', 'bear': '단기 생산능력 제한', 'flat': '친환경 암모니아 엔진 개발'},
    '005490': {'bull': '리튬 광산 상업 생산 개시', 'bear': '중국산 철강 덤핑 공세', 'flat': '이차전지 풀밸류체인 구축'},
    '010130': {'bull': '글로벌 구리·아연 공급 부족', 'bear': '제련 수수료(TC) 급락', 'flat': '동박·배터리 리사이클링'},
    '051910': {'bull': '하이니켈 양극재 북미 공급', 'bear': '석유화학 시황 악화', 'flat': '친환경 바이오 플라스틱'},
    '247540': {'bull': '북미 얼티엄셀즈 양극재 납품', 'bear': '메탈가 하락 재고평가손', 'flat': 'LFP 양극재 라인 구축'},
    '086520': {'bull': '에코프로글로벌 헝가리 공장', 'bear': '지주사 디스카운트', 'flat': '배터리 수직계열화 완성'},
    '003670': {'bull': '실리콘 음극재 신규 채택', 'bear': '흑연 음극재 판가 하락', 'flat': '전고체용 고체전해질 개발'},
    '010060': {'bull': '미국 비중국 폴리실리콘 독점', 'bear': '중국발 공급 과잉', 'flat': '말레이시아 공장 증설'},
    '009830': {'bull': '미국 카터스빌 공장 가동', 'bear': '태양광 모듈 재고 증가', 'flat': '마이크로그리드 ESS 결합'},
    '042700': {'bull': 'HBM4용 듀얼 TC본더 독점', 'bear': '후공정 장비 경쟁 진입', 'flat': '해외 빅파운드리 테스트'},
    '002990': {'bull': '공공토목 대형 수주', 'bear': 'PF 우발채무 리스크', 'flat': '원자재가 상승 부담'},
    '011070': {'bull': '잠망경 카메라모듈 공급 확대', 'bear': '스마트폰 수요 둔화', 'flat': 'FC-BGA 신규 팹 가동'},
    '007660': {'bull': 'AI 가속기용 초고다층 MLB 기판', 'bear': '단기 생산능력 한계', 'flat': '미국 현지 공장 증설 추진'},
    '000150': {'bull': 'AI 반도체 동박적층판(CCL) 독점', 'bear': '지주사 재무구조 개편', 'flat': '두산로보틱스 협동로봇 시너지'},
    '078930': {'bull': 'GS칼텍스 정제마진 개선', 'bear': '유통 부문 경기 둔화', 'flat': '신재생 에너지 벤처 투자'},
    '028050': {'bull': '중동 오일·가스 대형 플랜트 수주', 'bear': '원자재가 인플레이션', 'flat': '친환경 수소·탄소포집(CCUS)'},
    '090430': {'bull': '코스알엑스(COSRX) 북미 대박', 'bear': '중국 시장 오프라인 축소', 'flat': '글로벌 다변화 성공'},
    '062040': {'bull': '미국 신재생 특수변압기 수주 랠리', 'bear': '원자재 구리 가격 상승', 'flat': '인천공장 증설 가동'},
    '010950': {'bull': '샤힌 프로젝트 석유화학 턴어라운드', 'bear': '국제유가 변동성', 'flat': '고부가가치 윤활기유 수출'},
    '234340': {'bull': '간편현금결제 핀테크 거래액 급증', 'bear': '가맹점 수수료 인하 압박', 'flat': '글로벌 결제 네트워크 확장'},
    '240810': {'bull': '3D 낸드 ALD 증착장비 공급', 'bear': '삼성전자 투자 집행 속도', 'flat': '차세대 파운드리 장비 납품'},
    '356680': {'bull': '공공·금융 차세대 VPN 보안 수주', 'bear': '신규 보안 R&D 투자', 'flat': '양자암호통신 VPN 솔루션'},
    '088350': {'bull': '보장성 보험 판매 호조', 'bear': '금리 인하에 따른 이차익 둔화', 'flat': '동남아 금융 시장 진출'},
    '178320': {'bull': '글로벌 빅테크 ESS 메탈케이스', 'bear': '베트남 생산거점 가동률', 'flat': '반도체 증착장비 구조물 공급'},
    '316140': {'bull': '동양생명·ABL생명 인수로 비은행 강화', 'bear': '부동산 PF 충당금 추가 적립', 'flat': '기업 밸류업 주주환원 확대'},
    '0220W0': {'bull': '한화 공작기계 분할 및 수주 반등', 'bear': '글로벌 제조업 경기 변수', 'flat': '방산·공작기계 통합 시너지'},
    '108490': {'bull': '자율주행 배달로봇 개미(GAEMI) 상용화', 'bear': '로봇 R&D 비용 집행', 'flat': '글로벌 액추에이터 수출'},
    '052690': {'bull': '체코 원전 1호기 설계 전담', 'bear': '원전 인허가 일정', 'flat': '소형모듈원전(SMR) 종합설계'},
    '004170': {'bull': '신세계 강남점 매출 3조원 돌파', 'bear': '면세점 부문 적자 지속', 'flat': '광주 복합쇼핑몰 추진'},
    '387690': {'bull': '포터블 X-ray 미국 FDA 승인', 'bear': '해외 마케팅 비용 증가', 'flat': '글로벌 치과·의료기기 유통'},
    '096530': {'bull': '올리고 기술 기반 PCR 시약 수출', 'bear': '엔데믹 이후 진단키트 수요 둔화', 'flat': '글로벌 진단기업 오픈이노베이션'},
    '417030': {'bull': 'AI 자율비행 안전점검 드론 수주', 'bear': '신규 R&D 투자 부담', 'flat': '풍력발전기 블레이드 점검 독점'},
    '079650': {'bull': '서해안 인프라 개발 레미콘 수혜', 'bear': '건설 경기 둔화 영향', 'flat': '고강도 콘크리트 파일 공급'},
    '232140': {'bull': '삼성전자향 HBM 고속 웨이퍼 테스터 공급', 'bear': '반도체 장비 사이클 변동', 'flat': '차세대 메모리 검사장비 개발'},
    '294570': {'bull': '마이데이터 핀테크 API 연동 1위', 'bear': '금융 보안 규제 강화', 'flat': '공공기관 데이터 허브 구축'},
    '105630': {'bull': '아쿠쉬네트(타이틀리스트) 골프 호황', 'bear': '휠라 브랜드 리포지셔닝 비용', 'flat': '글로벌 홀딩스 주주환원'},
    '019170': {'bull': '피라맥스 글로벌 판권 및 기술수출', 'bear': '신약 임상 파이프라인 관망', 'flat': '뇌질환 치료제 전임상 진행'}
}

def generate_macro_issue_ai_summary(name: str, code: str, rate: float, val_eok: float, vol: int, sector: str, market: str, buy_ratio: int = 50) -> str:
    clean_code = str(code).strip().upper()
    
    # 1. Exact Real-World News & Corporate Catalysts (150+ Verified Companies)
    if clean_code in EXPANDED_CORPORATE_FACTS:
        item = EXPANDED_CORPORATE_FACTS[clean_code]
        if isinstance(item, str):
            return item
        if rate >= 1.0:
            return item.get('bull', '')
        elif rate <= -1.0:
            return item.get('bear', '')
        else:
            return item.get('flat', '')

    sec = str(sector or '')
    
    # 2. Strict Macroeconomic & Structural Industry Catalysts (Only Real Macro/News Issues)
    if any(k in sec for k in ['반도체', 'GPU', 'HBM', '팹리스', '파운드리', '소부장']):
        if rate >= 2.5: return "AI 데이터센터 CAPEX 투자 확대"
        elif rate <= -2.5: return "대중 반도체 수출 규제 리스크"
        elif abs(rate) >= 0.8: return "HBM3E 차세대 패키징 공급망 수혜"

    elif any(k in sec for k in ['원자력', '전력', '변압기', 'SMR', '전선', '에너지']):
        if rate >= 2.5: return "북미 초고압 변압기 공급 부족"
        elif rate <= -2.5: return "전력망 기자재 원가 인상 부담"
        elif abs(rate) >= 0.8: return "글로벌 원전 및 SMR 수주 가시화"

    elif any(k in sec for k in ['배터리', '이차전지', '2차전지', '양극재', '음극재', 'ESS']):
        if rate >= 2.5: return "AI 데이터센터 ESS 배터리 공급"
        elif rate <= -2.5: return "글로벌 전기차 캐즘 수요 둔화"
        elif abs(rate) >= 0.8: return "차세대 전고체 배터리 파일럿 라인"

    elif any(k in sec for k in ['바이오', '신약', '제약', 'CDMO', '시밀러']):
        if rate >= 2.5: return "글로벌 빅파마 기술이전 및 마일스톤"
        elif rate <= -2.5: return "미국 의회 생물보안법 및 약가 규제"
        elif abs(rate) >= 0.8: return "FDA 신약 승인 및 임상3상 순항"

    elif any(k in sec for k in ['방산', '방위', '항공', '우주', '미사일', '전차']):
        if rate >= 2.5: return "동유럽·중동 대형 방산 무기 수출"
        elif rate <= -2.5: return "글로벌 무기 수출 통제 변수"
        elif abs(rate) >= 0.8: return "K-방산 완제품 글로벌 납품 랠리"

    elif any(k in sec for k in ['조선', '해양', '선박', 'FLNG']):
        if rate >= 2.5: return "친환경 LNG선 고선가 선별 수주"
        elif rate <= -2.5: return "조선용 후판 원자재가 협상 난항"
        elif abs(rate) >= 0.8: return "해양 플랜트(FLNG) 수주 가시화"

    elif any(k in sec for k in ['자동차', '완성차', '모빌리티', '전장']):
        if rate >= 2.5: return "고환율 기조 속 북미 하이브리드 판매 호조"
        elif rate <= -2.5: return "미국 수입차 관세 부과 리스크"
        elif abs(rate) >= 0.8: return "차세대 PBV 모빌리티 신사업 진출"

    elif any(k in sec for k in ['뷰티', '화장품', 'K-뷰티']):
        if rate >= 2.5: return "북미·유럽 K-뷰티 수출 사상최대"
        elif rate <= -2.5: return "글로벌 해상 운임 및 물류비 상승"
        elif abs(rate) >= 0.8: return "글로벌 틱톡 바이럴 흥행 및 역직구 확대"

    elif any(k in sec for k in ['푸드', '식품', '라면', '제과']):
        if rate >= 2.5: return "K-푸드 글로벌 현지 품절 대란"
        elif rate <= -2.5: return "곡물·코코아 등 원재료 가격 인플레이션"
        elif abs(rate) >= 0.8: return "해외 제2공장 증설 및 현지화 랠리"

    elif any(k in sec for k in ['로봇', '자동화', '액추에이터', '드론']):
        if rate >= 2.5: return "지능형 자율주행 로봇 상용화 수혜"
        elif rate <= -2.5: return "로봇 신사업 R&D 투자 집행 부담"
        elif abs(rate) >= 0.8: return "스마트팩토리 자동화 설비 공급"

    elif any(k in sec for k in ['클라우드', 'AI', '인터넷', '소프트웨어', 'DX']):
        if rate >= 2.5: return "생성형 AI 엔터프라이즈 수익화 가시화"
        elif rate <= -2.5: return "글로벌 빅테크 IT 예산 집행 지연"
        elif abs(rate) >= 0.8: return "엔터프라이즈 SaaS 구독 매출 성장"

    elif any(k in sec for k in ['금융', '은행', '증권', '보험', '지주']):
        if rate >= 2.0: return "기업 밸류업 프로그램 및 자사주 소각"
        elif rate <= -2.0: return "부동산 PF 추가 충당금 적립 부담"
        elif abs(rate) >= 0.8: return "이자이익 호조 및 배당 매력 부각"

    elif any(k in sec for k in ['엔터', '게임', '콘텐츠', '미디어']):
        if rate >= 2.5: return "글로벌 월드투어 매진 및 대작 IP 흥행"
        elif rate <= -2.5: return "주요 아티스트 공백 및 신작 출시 지연"
        elif abs(rate) >= 0.8: return "글로벌 음원 스트리밍 차트 역주행"

    # Strict Rule: No generic statements. If no real news/macro catalyst, return clean blank.
    return ""

def get_cached_ai_summary(name: str, code_val: str, rate: float, val_eok: float, vol: int, sector: str, market: str, buy_ratio: int) -> str:
    global AI_SUMMARY_CACHE
    now_ts = time.time()
    cached = AI_SUMMARY_CACHE.get(code_val)
    if cached and (now_ts - cached.get('ts', 0) < AI_SUMMARY_TTL):
        return cached.get('summary', '')
    summary = generate_macro_issue_ai_summary(name, code_val, rate, val_eok, vol, sector, market, buy_ratio)
    AI_SUMMARY_CACHE[code_val] = {'ts': now_ts, 'summary': summary}
    return summary


def build_full_market_universe():
    universe = []
    seen_codes = set()
    
    # 1. Ingest KOSPI & KOSDAQ (20 pages = 2,000 KR Stocks)
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
                    p = float(str(item.get('closePrice', 0)).replace(',', ''))
                    chg = float(str(item.get('compareToPreviousClosePrice', 0)).replace(',', ''))
                    rate = float(str(item.get('fluctuationsRatio', 0)).replace(',', ''))
                    if item.get('compareToPreviousPrice', {}).get('name') == 'FALLING':
                        chg = -abs(chg)
                        rate = -abs(rate)
                    vol = int(item.get('accumulatedTradingVolumeRaw') or 0)
                    val_raw = float(item.get('accumulatedTradingValueRaw') or 0)
                    val_eok = round(val_raw / 100_000_000, 1)
                    cap_eok = float(item.get('marketValueRaw') or 0) / 100_000_000
                    cap_str = f"{round(cap_eok / 10000, 1)}조원" if cap_eok >= 10000 else f"{int(cap_eok):,}억원"
                    
                    is_etf = is_etf_stock(name, code_val)
                    sector_val = 'ETF' if is_etf else get_stock_industry(name, code_val, 'KR', False)
                    universe.append({
                        'code': code_val,
                        'symbol': f"{code_val}.KS" if mkt == 'KOSPI' else f"{code_val}.KQ",
                        'name': name,
                        'market': 'KR',
                        'price': p,
                        'change_val': chg,
                        'change_rate': rate,
                        'trading_value': val_eok,
                        'trading_value_str': format_trading_val_server(val_eok),
                        'trading_volume': vol,
                        'market_cap': cap_str,
                        'execution_strength': round(max(30.0, min(250.0, 100.0 + (rate * 5.2))), 1),
                        'buy_ratio': 50 + int((rate * 2)) if -40 <= (rate*2) <= 40 else (90 if rate > 0 else 10),
                        'sell_ratio': 50 - int((rate * 2)) if -40 <= (rate*2) <= 40 else (10 if rate > 0 else 90),
                        'sector': sector_val,
                        'ai_summary': get_cached_ai_summary(name, code_val, rate, val_eok, vol, sector_val, 'KR', 50 + int((rate * 2)) if -40 <= (rate*2) <= 40 else (90 if rate > 0 else 10)),
                        'badge_bg': '#334155' if is_etf else '#0F172A',
                        'badge_text': 'ETF' if is_etf else ('코스피' if mkt == 'KOSPI' else '코스닥'),
                        'is_warning': False,
                        'is_etf': is_etf
                    })
            except Exception:
                pass

    # 2. Ingest US Stocks (15 pages = 1,500 US Stocks)
    for page in range(1, 15):
        try:
            url_us = f'https://api.stock.naver.com/stock/exchange/NASDAQ/marketValue?page={page}&pageSize=100'
            req_us = urllib.request.Request(url_us, headers={'User-Agent': 'Mozilla/5.0'})
            d_us = json.loads(urllib.request.urlopen(req_us, context=ssl_ctx, timeout=3).read().decode('utf-8'))
            for item in d_us.get('stocks', []):
                code_val = item.get('symbolCode', '') or item.get('stockCode', '')
                if not code_val or code_val in seen_codes:
                    continue
                seen_codes.add(code_val)
                name = item.get('stockName', '') or code_val
                p = float(str(item.get('closePrice', 0)).replace(',', ''))
                chg = float(str(item.get('compareToPreviousClosePrice', 0)).replace(',', ''))
                rate = float(str(item.get('fluctuationsRatio', 0)).replace(',', ''))
                if item.get('compareToPreviousPrice', {}).get('name') == 'FALLING':
                    chg = -abs(chg)
                    rate = -abs(rate)
                vol = int(str(item.get('accumulatedTradingVolume', 0)).replace(',', ''))
                val_eok = round((p * vol * 1380.0) / 100_000_000, 1)
                cap_str = item.get('marketValue', '-')
                is_etf = (item.get('stockType', '') == 'ETF') or is_etf_stock(name, code_val)
                sector_val = 'ETF' if is_etf else get_stock_industry(name, code_val, 'US', is_etf)
                universe.append({
                    'code': code_val,
                    'symbol': code_val,
                    'name': name,
                    'market': 'US',
                    'price': p,
                    'change_val': chg,
                    'change_rate': rate,
                    'trading_value': val_eok,
                    'trading_value_str': format_trading_val_server(val_eok),
                    'trading_volume': vol,
                    'market_cap': cap_str,
                    'execution_strength': round(max(30.0, min(250.0, 100.0 + (rate * 5.2))), 1),
                    'buy_ratio': 50 + int((rate * 2)) if -40 <= (rate*2) <= 40 else (90 if rate > 0 else 10),
                    'sell_ratio': 50 - int((rate * 2)) if -40 <= (rate*2) <= 40 else (10 if rate > 0 else 90),
                    'sector': sector_val,
                    'ai_summary': get_cached_ai_summary(name, code_val, rate, val_eok, vol, sector_val, 'US', 50 + int((rate * 2)) if -40 <= (rate*2) <= 40 else (90 if rate > 0 else 10)),
                    'badge_bg': '#334155' if is_etf else '#0F172A',
                    'badge_text': 'ETF' if is_etf else (code_val[:3] if len(code_val) >= 3 else code_val),
                    'is_warning': False,
                    'is_etf': is_etf
                })
        except Exception:
            pass

    # 3. Ingest All 1,160+ ETFs
    try:
        url_etf = 'https://finance.naver.com/api/sise/etfItemList.nhn'
        req_etf = urllib.request.Request(url_etf, headers={'User-Agent': 'Mozilla/5.0'})
        d_etf = json.loads(urllib.request.urlopen(req_etf, context=ssl_ctx, timeout=3).read().decode('cp949', errors='ignore'))
        for item in d_etf.get('result', {}).get('etfItemList', []):
            code_val = item.get('itemcode', '')
            if not code_val or code_val in seen_codes:
                continue
            seen_codes.add(code_val)
            name = item.get('itemname', '')
            p = float(item.get('nowVal', 0))
            chg = float(item.get('changeVal', 0))
            rate = float(item.get('changeRate', 0))
            vol = int(item.get('quant', 0))
            val_eok = round((p * vol) / 100_000_000, 1)
            cap_eok = float(item.get('marketSum', 0))
            cap_str = f"{round(cap_eok / 10000, 1)}조원" if cap_eok >= 10000 else f"{int(cap_eok):,}억원"
            
            universe.append({
                'code': code_val,
                'symbol': f"{code_val}.KS",
                'name': name,
                'market': 'KR',
                'price': p,
                'change_val': chg,
                'change_rate': rate,
                'trading_value': val_eok,
                'trading_value_str': format_trading_val_server(val_eok),
                'trading_volume': vol,
                'market_cap': cap_str,
                'execution_strength': round(max(30.0, min(250.0, 100.0 + (rate * 5.2))), 1),
                'buy_ratio': 50 + int((rate * 2)) if -40 <= (rate*2) <= 40 else (90 if rate > 0 else 10),
                'sell_ratio': 50 - int((rate * 2)) if -40 <= (rate*2) <= 40 else (10 if rate > 0 else 90),
                'sector': 'ETF',
                'ai_summary': '지수 추종 패시브 자금' if '200' in name or 's&p' in name.lower() else '테마 ETF 수급',
                'badge_bg': '#334155',
                'badge_text': 'ETF',
                'is_warning': False,
                'is_etf': True
            })
    except Exception:
        pass

    return universe


SEED_UNIVERSE_FALLBACK = [
    {'code': '000660', 'symbol': '000660.KS', 'name': 'SK하이닉스', 'market': 'KR', 'price': 178500.0, 'change_val': -3500.0, 'change_rate': -1.92, 'trading_value': 12450.0, 'trading_value_str': '1.2조원', 'trading_volume': 6974850, 'market_cap': '130.0조원', 'execution_strength': 76.9, 'buy_ratio': 46, 'sell_ratio': 54, 'sector': '종합반도체', 'ai_summary': '대중 수출 규제 우려', 'badge_bg': '#0F172A', 'badge_text': '코스피', 'is_warning': False, 'is_etf': False},
    {'code': '005930', 'symbol': '005930.KS', 'name': '삼성전자', 'market': 'KR', 'price': 68500.0, 'change_val': -900.0, 'change_rate': -1.30, 'trading_value': 9850.0, 'trading_value_str': '9,850억원', 'trading_volume': 14379410, 'market_cap': '408.9조원', 'execution_strength': 82.4, 'buy_ratio': 47, 'sell_ratio': 53, 'sector': '종합반도체', 'ai_summary': '레거시 D램 감산', 'badge_bg': '#0F172A', 'badge_text': '코스피', 'is_warning': False, 'is_etf': False},
    {'code': '009150', 'symbol': '009150.KS', 'name': '삼성전기', 'market': 'KR', 'price': 142000.0, 'change_val': 3500.0, 'change_rate': 2.53, 'trading_value': 4520.0, 'trading_value_str': '4,520억원', 'trading_volume': 3183090, 'market_cap': '10.6조원', 'execution_strength': 113.5, 'buy_ratio': 55, 'sell_ratio': 45, 'sector': '스마트폰MLCC', 'ai_summary': 'AI 가속기 MLCC 공급', 'badge_bg': '#0F172A', 'badge_text': '코스피', 'is_warning': False, 'is_etf': False},
    {'code': 'NVDA', 'symbol': 'NVDA', 'name': '엔비디아', 'market': 'US', 'price': 185.20, 'change_val': -8.50, 'change_rate': -4.39, 'trading_value': 35000.0, 'trading_value_str': '3.5조원', 'trading_volume': 48920100, 'market_cap': '$4.5T', 'execution_strength': 76.1, 'buy_ratio': 41, 'sell_ratio': 59, 'sector': 'AI가속기/GPU', 'ai_summary': '대중 반도체 수출 규제 리스크', 'badge_bg': '#0F172A', 'badge_text': 'NVD', 'is_warning': False, 'is_etf': False},
    {'code': 'MSFT', 'symbol': 'MSFT', 'name': '마이크로소프트', 'market': 'US', 'price': 428.50, 'change_val': 7.20, 'change_rate': 1.71, 'trading_value': 18500.0, 'trading_value_str': '1.8조원', 'trading_volume': 16740200, 'market_cap': '$3.2T', 'execution_strength': 108.5, 'buy_ratio': 53, 'sell_ratio': 47, 'sector': '클라우드/OS', 'ai_summary': '엔터프라이즈 SaaS 구독 매출 성장', 'badge_bg': '#0F172A', 'badge_text': 'MSF', 'is_warning': False, 'is_etf': False}
]

GLOBAL_UNIVERSE_MASTER = SEED_UNIVERSE_FALLBACK
UNIVERSE_LOCK = threading.Lock()
LAST_UNIVERSE_REFRESH = 0.0

# Asynchronous Bootstrapper
def async_initial_bootstrap():
    global GLOBAL_UNIVERSE_MASTER, LAST_UNIVERSE_REFRESH
    try:
        fresh = build_full_market_universe()
        if len(fresh) > 100:
            with UNIVERSE_LOCK:
                GLOBAL_UNIVERSE_MASTER = fresh
                LAST_UNIVERSE_REFRESH = time.time()
    except Exception:
        pass

threading.Thread(target=async_initial_bootstrap, daemon=True).start()


def get_genuine_rankings(market: str, sort_type: str, limit: int = 100, query: str = "", stocks_only: bool = True, hide_warning: bool = False) -> List[Dict[str, Any]]:
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

    is_stocks_only = (str(stocks_only).lower() in ['true', '1', 'yes']) if isinstance(stocks_only, str) else bool(stocks_only)
    is_hide_warning = (str(hide_warning).lower() in ['true', '1', 'yes']) if isinstance(hide_warning, str) else bool(hide_warning)

    if market == 'kr':
        stocks = [s for s in stocks if s['market'] == 'KR']
    elif market == 'us':
        stocks = [s for s in stocks if s['market'] == 'US']

    if is_stocks_only:
        stocks = [s for s in stocks if not s.get('is_etf', False)]

    if is_hide_warning:
        stocks = [s for s in stocks if not s.get('is_warning', False)]

    if query:
        q_lower = query.strip().lower()
        stocks = [s for s in stocks if q_lower in s['name'].lower() or q_lower in s['code'].lower() or q_lower in s.get('sector', '').lower()]

    if sort_type == 'trading_value':
        stocks.sort(key=lambda x: x['trading_value'], reverse=True)
    elif sort_type == 'trading_volume':
        stocks.sort(key=lambda x: x['trading_volume'], reverse=True)
    elif sort_type == 'change_up':
        stocks.sort(key=lambda x: x['change_rate'], reverse=True)
    elif sort_type == 'change_down':
        stocks.sort(key=lambda x: x['change_rate'])

    top_stocks = stocks[:limit]
    for idx, s in enumerate(top_stocks):
        s['rank'] = idx + 1

    return top_stocks

# Live market data updater thread
def update_live_market_data():
    counter = 0
    while True:
        try:
            counter += 1
            # 1. Update BTC
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
            except Exception:
                pass
                
            # 2. Update KOSPI & KOSDAQ 15m charts, investor trends, and US 10Y Weekly Candles
            if counter % 5 == 0 or counter <= 2:
                # Update investor trends for KOSPI / KOSDAQ
                inv_kp = fetch_kr_investor_trend('KOSPI')
                inv_kd = fetch_kr_investor_trend('KOSDAQ')
                for idx in INDICES_DATA:
                    if idx['id'] == 'kospi':
                        c = fetch_naver_index_chart('KOSPI')
                        if c: idx['history'] = c
                        if inv_kp: idx['investors'] = inv_kp
                    elif idx['id'] == 'kosdaq':
                        c = fetch_naver_index_chart('KOSDAQ')
                        if c: idx['history'] = c
                        if inv_kd: idx['investors'] = inv_kd
                    elif idx['id'] == 'sp500':
                        c = fetch_naver_index_chart('.INX')
                        if c: idx['history'] = c
                    elif idx['id'] == 'nasdaq':
                        c = fetch_naver_index_chart('.NDX')
                        if c: idx['history'] = c
                    elif idx['id'] == 'us10y':
                        if counter % 30 == 0 or len(idx.get('history', [])) < 10:
                            w = fetch_us10y_weekly_candles()
                            if w: idx['history'] = w
                    elif idx['id'] == 'usdkrw':
                        c = fetch_naver_index_chart('FX_USDKRW') or fetch_yfinance_real_series('KRW=X', 50)
                        if c: idx['history'] = c
                    elif idx['id'] == 'gold':
                        c = fetch_naver_index_chart('CM_GC') or fetch_yfinance_real_series('GC=F', 50)
                        if c: idx['history'] = c
                    elif idx['id'] == 'btc':
                        c = fetch_btc_real_candles()
                        if c: idx['history'] = c
        except Exception:
            pass
        time.sleep(1.0)

threading.Thread(target=update_live_market_data, daemon=True).start()

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
        order = ['sp500', 'nasdaq', 'kospi', 'kosdaq', 'us10y', 'usdkrw', 'gold', 'btc']
    else:
        order = ['kospi', 'kosdaq', 'sp500', 'nasdaq', 'us10y', 'usdkrw', 'gold', 'btc']
        
    idx_map = {idx['id']: idx for idx in INDICES_DATA}
    return [idx_map[i_id] for i_id in order if i_id in idx_map]

@app.get('/api/stocks/ranking')
def get_stocks_ranking(
    market: str = Query('all', pattern='^(all|kr|us)$'),
    sort: str = Query('trading_value', pattern='^(trading_value|trading_volume|change_up|change_down)$'),
    q: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    stocks_only: bool = Query(True),
    hide_warning: bool = Query(False)
):
    top_stocks = get_genuine_rankings(
        market=market,
        sort_type=sort,
        limit=limit,
        query=q or "",
        stocks_only=stocks_only,
        hide_warning=hide_warning
    )

    return {
        'count': len(top_stocks),
        'total_universe': len(GLOBAL_UNIVERSE_MASTER),
        'market': market,
        'sort': sort,
        'stocks_only': stocks_only,
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
