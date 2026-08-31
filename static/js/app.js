// 1-Second Smooth Local Clock Ticker

function updateClockTick() {

    const clockEl = document.getElementById('serverTimeClock');

    if (!clockEl) return;

    const now = new Date();

    const h = String(now.getHours()).padStart(2, '0');

    const m = String(now.getMinutes()).padStart(2, '0');

    const s = String(now.getSeconds()).padStart(2, '0');

    clockEl.innerText = `${h}:${m}:${s}`;

}

// ==========================================

// Theme Toggle Engine (Dark / Light Mode)

// ==========================================

function initTheme() {

    const savedTheme = localStorage.getItem('strix_oculus_theme') || 'dark';

    applyTheme(savedTheme);

}

function applyTheme(theme) {

    const isLight = theme === 'light';

    if (isLight) {

        document.body.classList.add('light-theme');

    } else {

        document.body.classList.remove('light-theme');

    }

    localStorage.setItem('strix_oculus_theme', theme);

    const iconEl = document.getElementById('themeIcon');

    const labelEl = document.getElementById('themeLabel');

    if (iconEl) {

        iconEl.innerText = isLight ? '🌙' : '☀️';

    }

    if (labelEl) {

        labelEl.innerText = isLight ? '다크 모드' : '라이트 모드';

    }

}

function toggleTheme() {

    const isCurrentlyLight = document.body.classList.contains('light-theme');

    const nextTheme = isCurrentlyLight ? 'dark' : 'light';

    applyTheme(nextTheme);

}

// Checkbox format toggle

function toggleStocksOnly() {

    state.stocksOnly = !state.stocksOnly;

    const btn = document.getElementById('btnStocksOnly');

    const dot = document.getElementById('stocksOnlyDot');

    const text = document.getElementById('stocksOnlyText');

    if (btn && dot && text) {

        if (state.stocksOnly) {

            btn.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all border border-amber-500/50 bg-amber-500/15 text-amber-400 shadow-sm shadow-amber-500/20 hover:scale-105 active:scale-95 cursor-pointer";

            dot.className = "w-2 h-2 rounded-full bg-amber-400 shadow-sm shadow-amber-400";

            text.innerText = "주식만 보기 ON";

        } else {

            btn.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all border border-[#2D333B] bg-[#1C2128] text-slate-400 hover:text-slate-200 hover:bg-[#22272E] hover:scale-105 active:scale-95 cursor-pointer";

            dot.className = "w-2 h-2 rounded-full bg-slate-500";

            text.innerText = "주식만 보기 OFF (ETF 포함)";

        }

    }

    fetchStocks();

}

function formatMarketCap(cap, isUSD = false) {
    if (!cap || cap === '-' || cap === 0) return '-';
    
    if (typeof cap === 'string') {
        const cleanStr = cap.trim();
        // If already formatted in T/B/M shorthand
        if (/^\$?\s*\d+(\.\d+)?[TBM]$/i.test(cleanStr)) {
            return cleanStr.startsWith('$') ? cleanStr : `$${cleanStr}`;
        }
        if (cleanStr.includes('조원') || cleanStr.includes('억원')) {
            return cleanStr;
        }
        if (cleanStr.includes('조')) {
            const m = cleanStr.match(/([\d,.]+)\s*조(?:\s*([\d,.]+)\s*억)?/);
            if (m) {
                const jo = parseFloat(m[1].replace(/,/g, ''));
                const eok = m[2] ? parseFloat(m[2].replace(/,/g, '')) : 0;
                return `${(jo + (eok / 10000)).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}조원`;
            }
        } else if (cleanStr.includes('억')) {
            const m = cleanStr.match(/([\d,.]+)\s*억/);
            if (m) {
                const eok = parseFloat(m[1].replace(/,/g, ''));
                if (eok >= 10000) {
                    return `${(eok / 10000).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}조원`;
                }
                return `${Math.round(eok).toLocaleString('ko-KR')}억원`;
            }
        }
    }
    
    const cleanNum = typeof cap === 'number' ? cap : parseFloat(String(cap).replace(/[^\d.-]/g, ''));
    if (!isNaN(cleanNum) && cleanNum > 0) {
        if (isUSD || String(cap).includes('$')) {
            if (cleanNum >= 1_000_000_000_000) {
                return `$${(cleanNum / 1_000_000_000_000).toFixed(1)}T`;
            } else if (cleanNum >= 1_000_000_000) {
                return `$${(cleanNum / 1_000_000_000).toFixed(1)}B`;
            } else if (cleanNum >= 1_000_000) {
                return `$${(cleanNum / 1_000_000).toFixed(1)}M`;
            } else if (cleanNum >= 1_000) {
                return `$${(cleanNum / 1_000).toFixed(1)}K`;
            }
            return `$${cleanNum.toFixed(1)}`;
        } else {
            if (cleanNum >= 10000) {
                return `${(cleanNum / 10000).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}조원`;
            }
            return `${Math.round(cleanNum).toLocaleString('ko-KR')}억원`;
        }
    }
    
    return String(cap);
}

function formatTradingValue(val) {

    if (!val || val === 0) return '0원';

    const num = Number(val);

    if (isNaN(num)) return val;

    if (num >= 10000) {

        return `${(num / 10000).toFixed(1)}조원`;

    }

    return `${Math.round(num).toLocaleString()}억원`;

}

let state = {

    marketFilter: 'all',

    sortFilter: 'trading_value',

    stocksOnly: true,

    hideWarning: false,

    searchQuery: '',

    indices: [],

    stocks: [],

    marketStatus: null,

    selectedStock: null,
    detailIndexCode: 'kospi',
    detailTimeframe: 'day',
    showMovingAverages: true,
    tvMaSeriesList: [],
    tvChart: null,
    tvCandleSeries: null,
    tvVolumeSeries: null

};

// Utilities

function formatCurrency(val, isUSD = false) {

    if (isUSD) {

        return '$' + Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    }

    return Number(val).toLocaleString('ko-KR') + '원';

}

function formatChange(val, rate, isInt = false) {

    const isUp = rate > 0;

    const isDown = rate < 0;

    const sign = isUp ? '+' : '';

    const colorClass = isUp ? 'price-up font-bold' : (isDown ? 'price-down font-bold' : 'price-neutral');

    const formattedRate = `${sign}${rate.toFixed(2)}%`;

    let formattedVal;

    if (isInt && typeof val === 'number') {

        formattedVal = `${sign}${Math.round(val).toLocaleString('ko-KR')}`;

    } else {

        formattedVal = `${sign}${typeof val === 'number' ? Number(val).toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : val}`;

    }

    return { colorClass, formattedRate, formattedVal, isUp, isDown, sign };

}

// Generate Toss-Style 50-Tick Chart with Directional Gradient (Up: Bottom, Down: Top)

function generateToss50TickChartSvg(history, prevClose, isUp = true) {

    const width = 200;

    const height = 52;

    const padding = 4;

    // Slice exact last 50 ticks

    let rawData = (history && history.length >= 2) ? history.slice(-50) : [prevClose * 0.998, prevClose * 1.002];

    // Dynamic full-height scale for maximum visible volatility

    const minVal = Math.min(...rawData, prevClose);

    const maxVal = Math.max(...rawData, prevClose);

    const range = (maxVal - minVal) || 1;

    // Dotted baseline Y position (전일 종가 기준선)

    const baselineY = height - padding - ((prevClose - minVal) / range) * (height - padding * 2);

    // Map 50-tick points across full dynamic range

    const points = rawData.map((val, idx) => {

        const x = padding + (idx / (rawData.length - 1)) * (width - padding * 2);

        const y = height - padding - ((val - minVal) / range) * (height - padding * 2);

        return { x, y };

    });

    // Build smooth cubic bezier curve

    let pathD = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;

    for (let i = 1; i < points.length; i++) {

        const prev = points[i - 1];

        const curr = points[i];

        const cx = (prev.x + curr.x) / 2;

        pathD += ` C ${cx.toFixed(1)} ${prev.y.toFixed(1)}, ${cx.toFixed(1)} ${curr.y.toFixed(1)}, ${curr.x.toFixed(1)} ${curr.y.toFixed(1)}`;

    }

    const lastPoint = points[points.length - 1];

    const strokeColor = isUp ? '#FF5252' : '#3B82F6';

    const gradId = `grad-toss50t-${Math.random().toString(36).substr(2, 8)}`;

    // Directional Area: isUp extends down to floor (height), isDown extends up to ceiling (0)

    const areaD = isUp 

        ? `${pathD} L ${lastPoint.x.toFixed(1)} ${height} L ${points[0].x.toFixed(1)} ${height} Z`

        : `${pathD} L ${lastPoint.x.toFixed(1)} 0 L ${points[0].x.toFixed(1)} 0 Z`;

    return `

    <svg viewBox="0 0 ${width} ${height}" class="sparkline-svg w-full h-[52px]" preserveAspectRatio="none">

        <defs>

            <linearGradient id="${gradId}" x1="0" y1="${isUp ? '0' : '1'}" x2="0" y2="${isUp ? '1' : '0'}">

                <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.36"/>

                <stop offset="60%" stop-color="${strokeColor}" stop-opacity="0.12"/>

                <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0"/>

            </linearGradient>

        </defs>

        <!-- 1. Dotted Reference Baseline (전일 종가 기준선) -->

        <line x1="0" y1="${baselineY.toFixed(1)}" x2="${width}" y2="${baselineY.toFixed(1)}" stroke="#475569" stroke-width="1.1" stroke-dasharray="3,3" opacity="0.65"/>

        <!-- 2. Directional Area Under/Above Curve -->

        <path d="${areaD}" fill="url(#${gradId})" />

        <!-- 3. Main Toss 50-Tick Trajectory Stroke -->

        <path d="${pathD}" fill="none" stroke="${strokeColor}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />

        <!-- 4. Live Current Price Beacon Dot -->

        <circle cx="${lastPoint.x.toFixed(1)}" cy="${lastPoint.y.toFixed(1)}" r="3" fill="${strokeColor}" />

    </svg>`;

}

// Fetch Market Status

async function fetchMarketStatus() {

    try {

        const res = await fetch('/api/market-status');

        const data = await res.json();

        state.marketStatus = data;

        renderMarketStatus();

    } catch (e) {

        console.error('Market status fetch error:', e);

    }

}

// Fetch Indices

async function fetchIndices() {

    try {

        const res = await fetch('/api/indices');

        const data = await res.json();

        state.indices = data;

        renderIndices();

    } catch (e) {

        console.error('Indices fetch error:', e);

    }

}

// Fetch Stocks Ranking

async function fetchStocks() {

    try {

        const params = new URLSearchParams({

            market: state.marketFilter,

            sort: state.sortFilter,

            stocks_only: state.stocksOnly,

            limit: 100,

            hide_warning: state.hideWarning

        });

        if (state.searchQuery && state.searchQuery.trim()) {

            params.append('q', state.searchQuery.trim());

        }

        const res = await fetch(`/api/stocks/ranking?${params}`);

        const data = await res.json();

        state.stocks = data.stocks;

        renderStocks(data.updated_at);

    } catch (e) {

        console.error('Stocks fetch error:', e);

    }

}

// Render Top Status Header

function renderMarketStatus() {
    if (!state.marketStatus) return;
    const container = document.getElementById('marketStatusContainer');
    if (!container) return;

    const { kr_market, us_market, server_time } = state.marketStatus;

    container.innerHTML = `

        <div class="flex flex-wrap items-center gap-6 text-xs text-slate-400 font-medium">

            <!-- 1. 국내 정규장 -->

            <div class="flex items-center gap-2">

                <span class="w-2.5 h-2.5 rounded-full ${kr_market.is_open ? 'bg-amber-400 shadow-sm shadow-amber-400 animate-pulse' : 'bg-slate-500'}"></span>

                <span class="text-slate-200 font-semibold">${kr_market.name}</span>

                <span class="text-slate-400 font-sans">${kr_market.time}</span>

                <span class="text-[11px] font-medium px-1.5 py-0.5 rounded ${kr_market.is_open ? 'bg-amber-400/10 text-amber-400' : 'bg-slate-800 text-slate-400'}">${kr_market.status_text}</span>

            </div>

            <!-- 2. 미국 정규장 -->

            ${us_market ? `

                <div class="flex items-center gap-2">

                    <span class="w-2.5 h-2.5 rounded-full ${us_market.is_open ? 'bg-amber-400 shadow-sm shadow-amber-400 animate-pulse' : 'bg-slate-500'}"></span>

                    <span class="text-slate-200 font-semibold">${us_market.name}</span>

                    <span class="text-slate-400 font-sans">${us_market.time}</span>

                    <span class="text-[11px] font-medium px-1.5 py-0.5 rounded ${us_market.is_open ? 'bg-amber-400/10 text-amber-400' : 'bg-slate-800 text-slate-400'}">${us_market.status_text}</span>

                </div>

            ` : ''}

        </div>

        <div class="text-xs text-slate-500">

            실시간 피드: <span id="serverTimeClock" class="font-sans text-amber-400 font-semibold">${server_time}</span>

        </div>

    `;

}

// Render Major Indices Cards (Toss Securities Clean Card + 50-Tick Chart + Dotted Baseline)

function renderIndices() {

    const container = document.getElementById('indicesContainer');

    if (!container || !state.indices.length) return;

    const krOpen = state.marketStatus?.kr_market?.is_open ?? false;

    const usOpen = state.marketStatus?.us_market?.is_open ?? false;

    container.innerHTML = state.indices.map((idx) => {

        const isBTC = idx.id === 'btc';

        const isUS10Y = idx.id === 'us10y';

        const isUp = idx.change_rate >= 0;

        const changeInfo = formatChange(idx.change_val, idx.change_rate, isBTC);

        const prevCloseVal = idx.prev_close || (idx.price - (idx.change_val || 0));

        let priceHtml = '';

        if (isBTC) {

            priceHtml = `<span class="text-lg font-extrabold text-white tracking-tight font-sans">${Math.round(idx.price).toLocaleString('ko-KR')}</span><span class="text-xs font-semibold text-slate-300 font-sans ml-1">원</span>`;

        } else if (isUS10Y) {

            priceHtml = `<span class="text-lg font-extrabold text-white tracking-tight font-sans">${Number(idx.price).toFixed(3)}</span><span class="text-xs font-semibold text-slate-300 font-sans ml-1">%</span>`;

        } else {

            const formattedPrice = typeof idx.price === 'number' ? idx.price.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : idx.price;

            priceHtml = `<span class="text-lg font-extrabold text-white tracking-tight font-sans">${formattedPrice}</span>`;

        }

        // Active Market Session Border Highlight (국내 장중 -> 코스피/코스닥, 미국 본장 -> S&P500/나스닥100)

        let isSessionActive = false;

        if (krOpen && (idx.id === 'kospi' || idx.id === 'kosdaq')) {

            isSessionActive = true;

        } else if (usOpen && (idx.id === 'sp500' || idx.id === 'nasdaq')) {

            isSessionActive = true;

        }

                const cardStyleClasses = isSessionActive ? 'session-active' : '';
        const isClickable = true;
        const clickAttr = `onclick="navigateToIndexDetail('${idx.id}')"`;
        const cursorAttr = 'cursor-pointer hover:border-amber-400/80 hover:shadow-lg hover:shadow-amber-500/10 transition duration-200';

        return `
            <div class="index-card ${cardStyleClasses} ${cursorAttr} flex flex-col justify-between h-[215px]" ${clickAttr}>

                <!-- 1. Card Header: Title, Price, Change Info (Zero-Overflow Responsive Layout) -->

                <div class="flex flex-col gap-1 mb-1">

                    <span class="font-bold text-slate-200 text-xs sm:text-sm tracking-tight truncate">${idx.name}</span>

                    <div class="flex items-baseline">

                        ${priceHtml}

                    </div>

                    <div class="flex items-center gap-1 text-[11px] sm:text-xs ${changeInfo.colorClass} font-sans flex-wrap">

                        <span>${isUS10Y ? (isUp ? '+' : '') + Number(idx.change_val).toFixed(3) + '%p' : changeInfo.formattedVal}</span>

                        <span class="font-bold">(${changeInfo.formattedRate})</span>

                    </div>

                </div>

                <!-- 2. Toss Style 50-Tick Chart with Dotted Baseline & Contrast Area Gradient -->

                <div class="my-auto py-1">

                    ${generateToss50TickChartSvg(idx.history, prevCloseVal, isUp)}

                </div>

                <!-- 3. Footer: Investor Flows (Only on KOSPI / KOSDAQ, no extra labels on other cards) -->

                ${idx.investors ? `

                    <div class="pt-2 mt-auto border-t border-[#2D333B] h-[36px] flex items-center justify-center">

                        <div class="w-full grid grid-cols-3 text-center font-sans">

                            <div class="flex flex-col items-center">

                                <span class="text-[10px] text-slate-400 font-sans tracking-tight">개인</span>

                                <span class="text-[11px] ${idx.investors.individual >= 0 ? 'text-[#FF5252]' : 'text-[#3B82F6]'} font-bold tracking-tight">

                                    ${idx.investors.individual > 0 ? '+' : ''}${idx.investors.individual.toLocaleString()}

                                </span>

                            </div>

                            <div class="flex flex-col items-center">

                                <span class="text-[10px] text-slate-400 font-sans tracking-tight">외인</span>

                                <span class="text-[11px] ${idx.investors.foreign >= 0 ? 'text-[#FF5252]' : 'text-[#3B82F6]'} font-bold tracking-tight">

                                    ${idx.investors.foreign > 0 ? '+' : ''}${idx.investors.foreign.toLocaleString()}

                                </span>

                            </div>

                            <div class="flex flex-col items-center">

                                <span class="text-[10px] text-slate-400 font-sans tracking-tight">기관</span>

                                <span class="text-[11px] ${idx.investors.institutional >= 0 ? 'text-[#FF5252]' : 'text-[#3B82F6]'} font-bold tracking-tight">

                                    ${idx.investors.institutional > 0 ? '+' : ''}${idx.investors.institutional.toLocaleString()}

                                </span>

                            </div>

                        </div>

                    </div>

                ` : ''}

            </div>

        `;

    }).join('');

}

// Render Stocks Ranking Table

function renderStocks(updatedAt) {
    const container = document.getElementById('stocksTableBody');
    if (!container) return;

    const metricHeader = document.getElementById('colTradingMetric');

    if (metricHeader) {

        metricHeader.innerText = (state.sortFilter === 'trading_volume') ? '거래량' : '거래대금';

    }

    const updateTimeEl = document.getElementById('tableUpdateTime');

    if (updateTimeEl) {

        updateTimeEl.innerText = '순위';

    }

    let filtered = state.stocks;

    if (state.searchQuery.trim()) {

        const q = state.searchQuery.trim().toLowerCase();

        filtered = filtered.filter(s => s.name.toLowerCase().includes(q) || s.code.toLowerCase().includes(q) || (s.sector && s.sector.toLowerCase().includes(q)));

    }

    if (!filtered.length) {

        container.innerHTML = `

            <tr>

                <td colspan="8" class="text-center py-12 text-slate-500 font-medium">

                    조건에 맞는 종목 데이터가 없습니다.

                </td>

            </tr>

        `;

        return;

    }

    container.innerHTML = filtered.map((stock) => {

        const isUSD = stock.market === 'US';

        const changeInfo = formatChange(stock.change_val, stock.change_rate);

        const formattedPrice = formatCurrency(stock.price, isUSD);

        const isVolumeSort = state.sortFilter === 'trading_volume';

        const metricStr = isVolumeSort 

            ? `${Number(stock.trading_volume || 0).toLocaleString()}주` 

            : (stock.trading_value_str || formatTradingValue(stock.trading_value));

        return `

            <tr class="stock-row" onclick="openStockDetail('${stock.code}')">

                <!-- 1. Rank -->

                <td class="pl-4 pr-1 text-center font-bold text-slate-400 text-sm font-sans whitespace-nowrap">

                    ${stock.rank}

                </td>

                <!-- 2. Stock Info -->

                <td class="px-3 text-left truncate">

                    <div class="flex flex-col">

                        <div class="flex items-center gap-1.5 truncate">

                            <span class="font-bold text-slate-100 text-sm hover:text-amber-400 transition cursor-pointer truncate">${stock.name}</span>

                            ${stock.is_warning ? `<span class="badge-tag bg-amber-950/60 text-amber-400 border border-amber-500/40 text-[10px] shrink-0">투자주의</span>` : ''}

                        </div>

                        <span class="text-xs text-slate-400 font-sans mt-0.5">${stock.code} · ${stock.market === 'KR' ? '국내' : '해외'}</span>

                    </div>

                </td>

                <!-- 3. Price -->

                <td class="px-3 text-right font-extrabold font-sans text-slate-100 text-sm whitespace-nowrap">

                    ${formattedPrice}

                </td>

                <!-- 4. Change Rate (Pure Clean Colored Text Without Box) -->

                <td class="px-3 text-right whitespace-nowrap font-sans text-sm font-extrabold ${stock.change_rate > 0 ? 'text-[#FF5252]' : (stock.change_rate < 0 ? 'text-[#3B82F6]' : 'text-slate-400')}">

                    ${changeInfo.formattedRate}

                </td>

                <!-- 5. Trading Metric -->

                <td class="px-3 text-right font-sans text-sm font-semibold text-slate-200 whitespace-nowrap">

                    ${metricStr}

                </td>

                <!-- 6. Market Cap -->

                <td class="px-3 text-right font-sans text-xs text-slate-400 whitespace-nowrap">

                    ${formatMarketCap(stock.market_cap, isUSD)}

                </td>

                <!-- 7. Execution Strength (Micro Center Gauge Bar) -->

                <td class="px-2 text-center whitespace-nowrap">

                    <div class="inline-flex flex-col items-center justify-center gap-1 min-w-[72px]">

                        <span class="text-xs font-bold font-sans ${stock.execution_strength >= 100 ? 'text-[#FF5252]' : 'text-[#3B82F6]'} tracking-tight">

                            ${stock.execution_strength ? stock.execution_strength.toFixed(1) + '%' : '100.0%'}

                        </span>

                        <div class="w-16 h-1.5 rounded-full bg-[#21262D] relative flex items-center overflow-hidden">

                            <div class="absolute left-1/2 top-0 bottom-0 w-[1.5px] bg-slate-500 -translate-x-1/2 z-10"></div>

                            ${(stock.execution_strength || 100) >= 100 ? `

                                <div class="absolute left-1/2 top-0 bottom-0 bg-[#FF5252] rounded-r-full transition-all duration-300" style="width: ${Math.min(50, (((stock.execution_strength || 100) - 100) / 100) * 50)}%"></div>

                            ` : `

                                <div class="absolute right-1/2 top-0 bottom-0 bg-[#3B82F6] rounded-l-full transition-all duration-300" style="width: ${Math.min(50, ((100 - (stock.execution_strength || 100)) / 100) * 50)}%"></div>

                            `}

                        </div>

                    </div>

                </td>

                <!-- 8. Sector (Pure Clean Single-Line Text Without Box) -->

                <td class="px-3 text-left whitespace-nowrap">

                    <span class="text-xs font-semibold text-slate-300 whitespace-nowrap block">

                        ${stock.sector || '-'}

                    </span>

                </td>

                <!-- 9. AI Summary (Full Text Auto-Wrap Without Truncation) -->

                <td class="pl-3 pr-4 text-left">

                    ${stock.ai_summary ? `

                        <span class="text-xs text-slate-300 font-medium leading-snug break-words whitespace-normal block hover:text-amber-300 transition" title="${stock.ai_summary}">

                            ${stock.ai_summary}

                        </span>

                    ` : '<span class="text-slate-600 text-xs font-mono">-</span>'}

                </td>

            </tr>

        `;

    }).join('');

}

// Modal Detail View

function openStockDetail(code) {

    const stock = state.stocks.find(s => s.code === code);

    if (!stock) return;

    state.selectedStock = stock;

    const modal = document.getElementById('stockDetailModal');

    const isUSD = stock.market === 'US';

    const changeInfo = formatChange(stock.change_val, stock.change_rate);

    document.getElementById('modalStockName').innerText = stock.name;

    document.getElementById('modalStockCode').innerText = `${stock.code} · ${stock.market === 'KR' ? '국내주식' : '해외주식'}`;

    document.getElementById('modalStockPrice').innerText = formatCurrency(stock.price, isUSD);

    const rateEl = document.getElementById('modalStockRate');

    rateEl.innerText = `${changeInfo.formattedVal} (${changeInfo.formattedRate})`;

    rateEl.className = `text-sm font-bold ${changeInfo.colorClass}`;

    document.getElementById('modalTradingValue').innerText = formatTradingValue(stock.trading_value);

    document.getElementById('modalMarketCap').innerText = formatMarketCap(stock.market_cap);

    document.getElementById('modalSector').innerText = stock.sector;

    document.getElementById('modalAiSummary').innerText = stock.ai_summary || '실시간 주요 이슈 수집 중';

    // Buyer ratio in modal

    document.getElementById('modalBuyRatio').innerText = `${stock.buy_ratio}%`;

    document.getElementById('modalSellRatio').innerText = `${stock.sell_ratio}%`;

    document.getElementById('modalBuyBar').style.width = `${stock.buy_ratio}%`;

    document.getElementById('modalSellBar').style.width = `${stock.sell_ratio}%`;

    modal.classList.remove('hidden');

    modal.classList.add('flex');

}

function closeStockDetail() {

    const modal = document.getElementById('stockDetailModal');

    modal.classList.add('hidden');

    modal.classList.remove('flex');

}

// Filter and Event Listeners

function initApp() {

    // Stocks only (exclude ETF) checkbox

    const chkStocksOnly = document.getElementById('chkStocksOnly');

    if (chkStocksOnly) {

        chkStocksOnly.addEventListener('change', (e) => {

            state.stocksOnly = e.target.checked;

            fetchStocks();

        });

    }

    // Market filter buttons (전체, 국내, 해외)

    document.querySelectorAll('[data-market-filter]').forEach(btn => {

        btn.addEventListener('click', (e) => {

            document.querySelectorAll('[data-market-filter]').forEach(b => b.classList.remove('active'));

            e.target.classList.add('active');

            state.marketFilter = e.target.getAttribute('data-market-filter');

            fetchStocks();

        });

    });

    // Sort filter buttons (거래대금, 거래량, 급상승, 급하락)

    document.querySelectorAll('[data-sort-filter]').forEach(btn => {

        btn.addEventListener('click', (e) => {

            document.querySelectorAll('[data-sort-filter]').forEach(b => b.classList.remove('active'));

            e.target.classList.add('active');

            state.sortFilter = e.target.getAttribute('data-sort-filter');

            fetchStocks();

        });

    });

    // Hide warning stocks checkbox

    const hideWarningCheck = document.getElementById('hideWarningCheckbox');

    if (hideWarningCheck) {

        hideWarningCheck.addEventListener('change', (e) => {

            state.hideWarning = e.target.checked;

            fetchStocks();

        });

    }

    // Search input

    const searchInput = document.getElementById('stockSearchInput');

    if (searchInput) {

        searchInput.addEventListener('input', (e) => {

            state.searchQuery = e.target.value;

            renderStocks();

        });

    }

    // Initial load
    fetchMarketStatus();
    fetchIndices();
    fetchStocks();

    // Golden-Standard Routing on Refresh / Hash Change
    function handleRoute() {
        const hash = window.location.hash || '';
        if (hash.startsWith('#index/')) {
            const sym = hash.replace('#index/', '').toLowerCase();
            navigateToIndexDetail(sym);
        } else {
            navigateToHome();
        }
    }

    handleRoute();
    window.addEventListener('hashchange', handleRoute);

    // Optimal Golden-Standard Live Intervals (Zero Server Strain + High Responsiveness)
    setInterval(updateClockTick, 1000);    // Smooth 1-second local clock tick
    setInterval(fetchIndices, 3000);       // Global Indices every 3 seconds
    setInterval(fetchStocks, 5000);        // Stock Quotes & Execution Strength every 5 seconds
    setInterval(fetchMarketStatus, 15000); // Market Session Status sync every 15 seconds
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// =========================================================================
// ISOLATED MODULE: KOSPI/KOSDAQ Dedicated Candlestick Chart Engine (Toss)
// =========================================================================

function navigateToHome() {
    state.currentView = 'dashboard';
    const dView = document.getElementById('dashboardView');
    const iView = document.getElementById('indexDetailView');
    if (dView) dView.classList.remove('hidden');
    if (iView) iView.classList.add('hidden');
    
    const navHome = document.getElementById('navBtnHome');
    const navDetail = document.getElementById('navBtnDetail');
    if (navHome) {
        navHome.classList.add('bg-amber-500/15', 'text-amber-400', 'border-amber-500/35');
        navHome.classList.remove('text-slate-400');
    }
    if (navDetail) {
        navDetail.classList.add('hidden');
        navDetail.classList.remove('flex');
    }
    
    if (window.location.hash) {
        history.replaceState(null, '', window.location.pathname);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

const INDEX_CLIENT_META = {
    'kospi': { name: '코스피', code: 'KOSPI', country: '한국', flag: 'https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/1f1f0-1f1f7.svg', title: '🇰🇷 코스피 지수 분석' },
    'kosdaq': { name: '코스닥', code: 'KOSDAQ', country: '한국', flag: 'https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/1f1f0-1f1f7.svg', title: '🇰🇷 코스닥 지수 분석' },
    'sp500': { name: 'S&P 500', code: 'S&P 500', country: '미국', flag: 'https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/1f1fa-1f1f8.svg', title: '🇺🇸 S&P 500 지수 분석' },
    'nasdaq': { name: '나스닥 100', code: 'NASDAQ 100', country: '미국', flag: 'https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/1f1fa-1f1f8.svg', title: '🇺🇸 나스닥 100 지수 분석' },
    'us10y': { name: '미국 국채 10년', code: 'US10Y', country: '미국', flag: 'https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/1f1fa-1f1f8.svg', title: '🇺🇸 미국 국채 10년 금리 분석' },
    'usdkrw': { name: '원/달러 환율', code: 'USD/KRW', country: '환율', flag: 'https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/1f1fa-1f1f8.svg', title: '💵 원/달러 환율 분석' },
    'gold': { name: '국제 금 선물', code: 'GOLD', country: '원자재', flag: 'https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/1f4b0.svg', title: '🪙 국제 금 선물 분석' },
    'btc': { name: '비트코인', code: 'BTC', country: '가상자산', flag: 'https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/20bf.svg', title: '₿ 비트코인 시세 분석' }
};

function navigateToIndexDetail(indexId) {
    state.currentView = 'index_detail';
    state.detailIndexCode = (indexId || 'kospi').toLowerCase();
    const meta = INDEX_CLIENT_META[state.detailIndexCode] || INDEX_CLIENT_META['kospi'];
    
    const dView = document.getElementById('dashboardView');
    const iView = document.getElementById('indexDetailView');
    if (dView) dView.classList.add('hidden');
    if (iView) iView.classList.remove('hidden');
    
    const navHome = document.getElementById('navBtnHome');
    const navDetail = document.getElementById('navBtnDetail');
    if (navHome) {
        navHome.classList.remove('bg-amber-500/15', 'text-amber-400', 'border-amber-500/35');
        navHome.classList.add('text-slate-400');
    }
    if (navDetail) {
        navDetail.classList.remove('hidden');
        navDetail.classList.add('flex');
    }
    
    const detailTitle = document.getElementById('navDetailTitle');
    if (detailTitle) detailTitle.innerText = meta.title;
    
    // Instant 0ms Header Pre-fill (Eliminates all flickering!)
    const idxName = document.getElementById('detailIndexName');
    const idxPrice = document.getElementById('detailIndexPrice');
    const flagImg = document.getElementById('detailFlagIcon');
    const countryName = document.getElementById('detailCountryName');
    if (idxName) idxName.innerText = meta.name;
    if (flagImg) flagImg.src = meta.flag;
    if (countryName) countryName.innerText = meta.country;
    
    // Pre-fill price from memory cache if available
    const cachedIdx = (state.indices || []).find(i => i.id === state.detailIndexCode);
    if (cachedIdx) {
        updateIndexHeaderStats(cachedIdx, state.detailIndexCode);
    } else {
        if (idxPrice) idxPrice.innerText = '-';
    }
    
    // Clear old chart to prevent ghosting
    const mainContainer = document.getElementById('tvMainChartContainer');
    const volContainer = document.getElementById('tvVolumeChartContainer');
    if (state.tvChart) {
        try { state.tvChart.remove(); } catch(e){}
        state.tvChart = null;
    }
    if (state.tvVolChart) {
        try { state.tvVolChart.remove(); } catch(e){}
        state.tvVolChart = null;
    }
    if (mainContainer) mainContainer.innerHTML = '<div class="flex items-center justify-center h-full text-slate-500 font-mono text-sm">차트 로딩중...</div>';
    if (volContainer) volContainer.innerHTML = '';
    
    const targetHash = `#index/${state.detailIndexCode}`;
    if (window.location.hash !== targetHash) {
        history.replaceState(null, '', targetHash);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    loadIndexDetailData();
}

function calculateMA(candles, period) {
    const result = [];
    for (let i = 0; i < candles.length; i++) {
        if (i < period - 1) continue;
        let sum = 0;
        for (let j = 0; j < period; j++) {
            sum += candles[i - j].close;
        }
        result.push({
            time: candles[i].time,
            value: Number((sum / period).toFixed(2))
        });
    }
    return result;
}

function calculateVolMA(candles, period) {
    const result = [];
    for (let i = 0; i < candles.length; i++) {
        if (i < period - 1) continue;
        let sum = 0;
        for (let j = 0; j < period; j++) {
            sum += (candles[i - j].volume || 0);
        }
        result.push({
            time: candles[i].time,
            value: Number((sum / period).toFixed(0))
        });
    }
    return result;
}

function updateIndexHeaderStats(quote, idxKey) {
    if (!quote) return;
    const idxName = document.getElementById('detailIndexName');
    const idxPrice = document.getElementById('detailIndexPrice');
    const flagImg = document.getElementById('detailFlagIcon');
    const countryName = document.getElementById('detailCountryName');
    
    if (idxName) idxName.innerText = quote.name || '지수';
    if (flagImg && quote.flag) flagImg.src = quote.flag;
    
    const countryLabels = {
        'KR': '한국',
        'US': '미국',
        'FX': '환율',
        'COMM': '원자재',
        'CRYPTO': '가상자산'
    };
    if (countryName) countryName.innerText = countryLabels[quote.country] || quote.country || '글로벌';
    
    const isCrypto = (idxKey === 'btc');
    const isRate = (idxKey === 'us10y');
    
    if (idxPrice && quote.price !== undefined) {
        if (isCrypto) {
            idxPrice.innerText = Math.round(quote.price).toLocaleString('ko-KR');
        } else if (isRate) {
            idxPrice.innerText = Number(quote.price).toFixed(3);
        } else {
            idxPrice.innerText = Number(quote.price).toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    }
    
    const isUp = (quote.change_rate >= 0);
    const chgColor = isUp ? 'text-[#FF5252]' : 'text-[#3B82F6]';
    const chgSign = isUp ? '+' : '';
    const chgValStr = isRate ? (chgSign + Number(quote.change_val || 0).toFixed(3) + '%p') : (isCrypto ? (chgSign + Math.round(quote.change_val || 0).toLocaleString('ko-KR')) : (chgSign + Number(quote.change_val || 0).toFixed(2)));
    const chgRateStr = `(${chgSign}${Number(quote.change_rate || 0).toFixed(2)}%)`;
    
    const chgBadge = document.getElementById('detailIndexChangeBadge');
    if (chgBadge) {
        chgBadge.innerText = `${chgValStr} ${chgRateStr}`;
        chgBadge.className = `font-bold num-clean ${chgColor}`;
    }
    
    const elVol = document.getElementById('detailVolStr');
    const elOpen = document.getElementById('detailOpenPrice');
    const elLow = document.getElementById('detailLowPrice');
    const elHigh = document.getElementById('detailHighPrice');
    const el52L = document.getElementById('detail52WLow');
    const el52H = document.getElementById('detail52WHigh');
    
    const fmt = (v) => {
        if (v === undefined || v === null) return '-';
        if (isCrypto) return Math.round(v).toLocaleString('ko-KR');
        if (isRate) return Number(v).toFixed(3);
        return Number(v).toLocaleString('ko-KR', { minimumFractionDigits: 2 });
    };
    
    if (elVol && quote.vol_str) elVol.innerText = quote.vol_str;
    if (elOpen) elOpen.innerText = fmt(quote.open);
    if (elLow) elLow.innerText = fmt(quote.low);
    if (elHigh) elHigh.innerText = fmt(quote.high);
    if (el52L) el52L.innerText = fmt(quote.l52);
    if (el52H) el52H.innerText = fmt(quote.h52);
}

let indexDetailRefreshTimer = null;

async function loadIndexDetailData() {
    const code = (state.detailIndexCode || 'kospi').toLowerCase();
    
    try {
        const tf = state.detailTimeframe || 'day';
        const res = await fetch(`/api/index/history?code=${code}&timeframe=${tf}`);
        const data = await res.json();
        const quote = data.quote || {};
        
        updateIndexHeaderStats(quote, code);
        renderTradingViewChart(data.candles || []);
        
        // Start continuous live polling (2s interval) with real-time chart updates without refresh!
        if (indexDetailRefreshTimer) clearInterval(indexDetailRefreshTimer);
        indexDetailRefreshTimer = setInterval(async () => {
            if (state.currentView !== 'index_detail') {
                clearInterval(indexDetailRefreshTimer);
                indexDetailRefreshTimer = null;
                return;
            }
            try {
                const curTf = state.detailTimeframe || 'day';
                const qRes = await fetch(`/api/index/history?code=${code}&timeframe=${curTf}`);
                const qData = await qRes.json();
                if (qData.quote) {
                    updateIndexHeaderStats(qData.quote, code);
                }
                if (qData.candles && qData.candles.length) {
                    updateLiveChartCandles(qData.candles);
                }
            } catch(err){}
        }, 2000);
    } catch (e) {
        console.error('Failed to load index detail data:', e);
    }
}

function updateLiveChartCandles(newCandles) {
    if (!newCandles || !newCandles.length || !state.tvCandleSeries) return;
    const lastC = newCandles[newCandles.length - 1];
    if (!lastC) return;
    
    try {
        state.tvCandleSeries.update(lastC);
        const lastV = {
            time: lastC.time,
            value: (typeof lastC.volume === 'number' && !isNaN(lastC.volume)) ? Math.max(0, lastC.volume) : 0,
            color: (lastC.close >= lastC.open) ? '#EF4444' : '#3B82F6'
        };
        if (state.tvVolumeSeries) {
            state.tvVolumeSeries.update(lastV);
        }
        
        // Dynamically update latest price line color (Red for Rising, Blue for Falling)
        const prevCandleClose = (newCandles.length > 1) ? newCandles[newCandles.length - 2].close : lastC.open;
        const isUp = (lastC.close >= prevCandleClose);
        state.tvCandleSeries.applyOptions({
            priceLineColor: isUp ? '#EF4444' : '#3B82F6'
        });
        
        // Update live in-chart OHLC overlay if crosshair is not active
        const vertGuide = document.getElementById('globalCrosshairVert');
        if (!vertGuide || vertGuide.classList.contains('hidden')) {
            if (typeof updateInChartOverlay === 'function') {
                updateInChartOverlay(lastC, lastV, lastC.time);
            }
        }
    } catch (e) {
        try {
            state.tvCandleSeries.setData(newCandles);
        } catch(err){}
    }
}

function renderTradingViewChart(candles) {
    const mainContainer = document.getElementById('tvMainChartContainer');
    const volContainer = document.getElementById('tvVolumeChartContainer');
    if (!mainContainer || !volContainer) return;
    
    if (state.tvChart) {
        try { state.tvChart.remove(); } catch(e){}
        state.tvChart = null;
    }
    if (state.tvVolChart) {
        try { state.tvVolChart.remove(); } catch(e){}
        state.tvVolChart = null;
    }
    mainContainer.innerHTML = '';
    volContainer.innerHTML = '';
    
    if (typeof LightweightCharts === 'undefined') {
        mainContainer.innerHTML = '<div class="flex items-center justify-center h-full text-slate-500 font-mono text-sm">차트 엔진 로딩중...</div>';
        return;
    }
    
    if (!candles || !candles.length) {
        mainContainer.innerHTML = '<div class="flex items-center justify-center h-full text-slate-500 font-mono text-sm">캔들 데이터를 불러오는 중입니다...</div>';
        return;
    }

    const wrapper = document.getElementById('tvChartWrapper');
    const cWidth = wrapper ? wrapper.clientWidth : (mainContainer.clientWidth || 900);
    
    let mainH = 410;
    let volH = 169;
    if (isInSiteFullscreen && wrapper) {
        const totalH = wrapper.clientHeight || (window.innerHeight - 100);
        volH = 160;
        mainH = Math.max(300, totalH - volH - 2);
    }
    
    const mainPane = mainContainer.parentElement;
    const volPane = volContainer.parentElement;
    if (mainPane) mainPane.style.height = `${mainH}px`;
    if (volPane) volPane.style.height = `${volH}px`;
    
    // Dynamic Red (Rising) / Blue (Falling) color for current price line
    const lastCandle = candles[candles.length - 1];
    const prevCandleClose = (candles.length > 1) ? candles[candles.length - 2].close : lastCandle.open;
    const isLatestUp = (lastCandle.close >= prevCandleClose);
    const dynamicPriceColor = isLatestUp ? '#EF4444' : '#3B82F6';

    // 1. Top Pane: Main Candlestick Chart (Independent Price Scale, Never Below 0)
    const mainChart = LightweightCharts.createChart(mainContainer, {
        width: cWidth,
        height: mainH,
        layout: {
            background: { color: '#0B0E14' },
            textColor: '#94A3B8',
            fontFamily: 'Pretendard, -apple-system, system-ui, sans-serif',
            fontSize: 11,
        },
        grid: {
            vertLines: { color: 'rgba(30, 41, 59, 0.35)', style: 1 },
            horzLines: { color: 'rgba(30, 41, 59, 0.35)', style: 1 },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: 'rgba(226, 232, 240, 0.45)',
                width: 1,
                style: 2,
                visible: false, // Handled by global continuous vertical guideline
                labelVisible: true,
                labelBackgroundColor: '#334155',
            },
            horzLine: {
                color: 'rgba(226, 232, 240, 0.45)',
                width: 1,
                style: 2,
                visible: true,
                labelVisible: true,
                labelBackgroundColor: '#334155',
            },
        },
        rightPriceScale: {
            borderColor: '#21262D',
            textColor: '#94A3B8',
            autoScale: true,
            minimumWidth: 75,
            scaleMargins: {
                top: 0.10,
                bottom: 0.08,
            },
        },
        timeScale: {
            visible: false,
        },
    });
    state.tvChart = mainChart;
    
    // Candlestick Series (Dynamic Red/Blue Price Line, Clamped >= 0)
    const candleSeries = mainChart.addCandlestickSeries({
        upColor: '#EF4444',
        downColor: '#3B82F6',
        borderUpColor: '#EF4444',
        borderDownColor: '#3B82F6',
        wickUpColor: '#EF4444',
        wickDownColor: '#3B82F6',
        priceLineVisible: true,
        priceLineStyle: 2, // Medium dashed line
        priceLineColor: dynamicPriceColor, // Dynamic red/blue
        priceLineWidth: 1,
        lastValueVisible: true,
        autoscaleInfoProvider: (original) => {
            const res = original ? original() : null;
            if (res && res.priceRange) {
                res.priceRange.minValue = Math.max(0, res.priceRange.minValue);
            }
            return res;
        }
    });
    candleSeries.setData(candles);
    state.tvCandleSeries = candleSeries;
    
    // High / Low Peak Markers
    let maxCandle = candles[0], minCandle = candles[0];
    candles.forEach(c => {
        if (c.high > maxCandle.high) maxCandle = c;
        if (c.low < minCandle.low) minCandle = c;
    });
    
    const lastClose = candles[candles.length - 1].close;
    const maxDiffPct = ((lastClose - maxCandle.high) / maxCandle.high * 100).toFixed(2);
    const minDiffPct = ((lastClose - minCandle.low) / minCandle.low * 100).toFixed(2);
    
    const maxDate = new Date(maxCandle.time * 1000);
    const maxDateStr = `${String(maxDate.getFullYear()).slice(-2)}.${String(maxDate.getMonth()+1).padStart(2,'0')}.${String(maxDate.getDate()).padStart(2,'0')}`;
    
    const minDate = new Date(minCandle.time * 1000);
    const minDateStr = `${String(minDate.getFullYear()).slice(-2)}.${String(minDate.getMonth()+1).padStart(2,'0')}.${String(minDate.getDate()).padStart(2,'0')}`;
    
    candleSeries.setMarkers([
        {
            time: maxCandle.time,
            position: 'aboveBar',
            color: '#EF4444',
            shape: 'arrowDown',
            text: `${maxCandle.high.toLocaleString('ko-KR', {minimumFractionDigits: 2})} (${maxDiffPct}%, ${maxDateStr})`
        },
        {
            time: minCandle.time,
            position: 'belowBar',
            color: '#3B82F6',
            shape: 'arrowUp',
            text: `${minCandle.low.toLocaleString('ko-KR', {minimumFractionDigits: 2})} (+${minDiffPct}%, ${minDateStr})`
        }
    ]);
    
    // 4 Moving Average Overlays
    const ma5Data = calculateMA(candles, 5);
    const ma20Data = calculateMA(candles, 20);
    const ma60Data = calculateMA(candles, 60);
    const ma120Data = calculateMA(candles, 120);
    
    const maMap = {};
    ma5Data.forEach(d => { maMap[d.time] = { ...maMap[d.time], ma5: d.value }; });
    ma20Data.forEach(d => { maMap[d.time] = { ...maMap[d.time], ma20: d.value }; });
    ma60Data.forEach(d => { maMap[d.time] = { ...maMap[d.time], ma60: d.value }; });
    ma120Data.forEach(d => { maMap[d.time] = { ...maMap[d.time], ma120: d.value }; });
    
    state.tvMaSeriesList = [];
    if (ma5Data.length) {
        const ma5Series = mainChart.addLineSeries({ color: '#10B981', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, visible: state.showMovingAverages });
        ma5Series.setData(ma5Data);
        state.tvMaSeriesList.push(ma5Series);
    }
    if (ma20Data.length) {
        const ma20Series = mainChart.addLineSeries({ color: '#EF4444', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, visible: state.showMovingAverages });
        ma20Series.setData(ma20Data);
        state.tvMaSeriesList.push(ma20Series);
    }
    if (ma60Data.length) {
        const ma60Series = mainChart.addLineSeries({ color: '#F59E0B', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, visible: state.showMovingAverages });
        ma60Series.setData(ma60Data);
        state.tvMaSeriesList.push(ma60Series);
    }
    if (ma120Data.length) {
        const ma120Series = mainChart.addLineSeries({ color: '#8B5CF6', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, visible: state.showMovingAverages });
        ma120Series.setData(ma120Data);
        state.tvMaSeriesList.push(ma120Series);
    }
    
    // 2. Bottom Pane: Separated Volume Chart (169px, Independent Volume Scale, Strictly Clamped >= 0)
    const volChart = LightweightCharts.createChart(volContainer, {
        width: cWidth,
        height: 169,
        layout: {
            background: { color: '#0B0E14' },
            textColor: '#94A3B8',
            fontFamily: 'Pretendard, -apple-system, system-ui, sans-serif',
            fontSize: 11,
        },
        grid: {
            vertLines: { color: 'rgba(30, 41, 59, 0.35)', style: 1 },
            horzLines: { visible: false }, // Absolutely NO horizontal lines on volume
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: 'rgba(226, 232, 240, 0.45)',
                width: 1,
                style: 2,
                visible: false, // Handled by global continuous vertical guideline
                labelVisible: true,
                labelBackgroundColor: '#334155',
            },
            horzLine: {
                visible: false, // Absolutely NO horizontal line on volume
                labelVisible: false,
            },
        },
        rightPriceScale: {
            borderColor: '#21262D',
            textColor: '#94A3B8',
            autoScale: true,
            minimumWidth: 75,
            scaleMargins: {
                top: 0.15,
                bottom: 0.0,
            },
        },
        localization: {
            timeFormatter: (time) => {
                const ts = (typeof time === 'number' ? time : (time.timestamp || (time.year ? new Date(Date.UTC(time.year, time.month-1, time.day)).getTime()/1000 : 0)));
                const d = new Date(ts * 1000);
                const tf = state.detailTimeframe || 'day';
                if (['1m', '3m', '5m', '15m', '30m', '60m'].includes(tf)) {
                    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
                } else if (tf === 'year') {
                    return `${d.getUTCFullYear()}`;
                } else if (tf === 'month') {
                    return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`;
                } else {
                    return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;
                }
            },
            dateFormat: 'yyyy-MM-dd',
        },
        timeScale: {
            borderColor: '#21262D',
            timeVisible: ['1m', '3m', '5m', '15m', '30m', '60m'].includes(state.detailTimeframe),
            secondsVisible: false,
            tickMarkFormatter: (time, tickMarkType, locale) => {
                const ts = (typeof time === 'number' ? time : (time.timestamp || (time.year ? new Date(Date.UTC(time.year, time.month-1, time.day)).getTime()/1000 : 0)));
                const d = new Date(ts * 1000);
                const tf = state.detailTimeframe || 'day';
                if (tf === 'year') {
                    return `${d.getUTCFullYear()}`;
                } else if (tf === 'month') {
                    return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`;
                } else if (['1m', '3m', '5m', '15m', '30m', '60m'].includes(tf)) {
                    return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
                } else {
                    return `${String(d.getUTCMonth()+1).padStart(2,'0')}/${String(d.getUTCDate()).padStart(2,'0')}`;
                }
            }
        },
    });
    state.tvVolChart = volChart;
    
    // Volume Series (Strictly Clamped >= 0, No horizontal baseline or priceline)
    const volumeSeries = volChart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        baseLineVisible: false,
        priceLineVisible: false,
        lastValueVisible: true,
        autoscaleInfoProvider: (original) => {
            const res = original ? original() : null;
            if (res && res.priceRange) {
                res.priceRange.minValue = 0; // Strictly 0 minimum!
            }
            return res;
        }
    });
    const volData = candles.map(c => ({
        time: c.time,
        value: (typeof c.volume === 'number' && !isNaN(c.volume)) ? Math.max(0, c.volume) : 0,
        color: (c.close >= c.open) ? '#EF4444' : '#3B82F6'
    }));
    volumeSeries.setData(volData);
    state.tvVolumeSeries = volumeSeries;
    
    // Direct Volume and MA20 lookup maps by timestamp
    const volMap = {};
    candles.forEach(c => { volMap[c.time] = c.volume; });
    
    const volMa20Data = calculateVolMA(candles, 20);
    const volMaMap = {};
    volMa20Data.forEach(d => { volMaMap[d.time] = d.value; });
    
    if (volMa20Data.length) {
        const volMaSeries = volChart.addLineSeries({
            color: '#3B82F6',
            lineWidth: 1.2,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            autoscaleInfoProvider: (original) => {
                const res = original ? original() : null;
                if (res && res.priceRange) {
                    res.priceRange.minValue = 0; // Strictly 0 minimum!
                }
                return res;
            }
        });
        volMaSeries.setData(volMa20Data);
    }
    
    // 3. Two-Way Perfect Range & Scroll Synchronization
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) volChart.timeScale().setVisibleLogicalRange(range);
    });
    volChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) mainChart.timeScale().setVisibleLogicalRange(range);
    });
    
    // Map previous candle close for exact previous-day-close percentage calculations
    const prevCloseMap = {};
    for (let i = 0; i < candles.length; i++) {
        const prevC = (i > 0) ? candles[i - 1].close : candles[i].open;
        prevCloseMap[candles[i].time] = prevC;
    }

    // Function to format volume numbers e.g. 345.82M
    function formatVolM(val) {
        if (val === undefined || val === null) return '-';
        if (val === 0) return '0';
        if (val >= 1000000000) return `${(val / 1000000000).toFixed(2)}B`;
        if (val >= 1000000) return `${(val / 1000000).toFixed(2)}M`;
        if (val >= 10000) return `${(val / 1000).toFixed(1)}K`;
        return Number(val).toLocaleString('ko-KR');
    }

    // Helper to update In-Chart Live Overlays
    function updateInChartOverlay(cData, vData, timeKey) {
        const tipOpen = document.getElementById('tipOpen');
        const tipHigh = document.getElementById('tipHigh');
        const tipLow = document.getElementById('tipLow');
        const tipClose = document.getElementById('tipClose');
        
        const tipOpenChg = document.getElementById('tipOpenChg');
        const tipHighChg = document.getElementById('tipHighChg');
        const tipLowChg = document.getElementById('tipLowChg');
        const tipCloseChg = document.getElementById('tipCloseChg');
        
        const tipMa5 = document.getElementById('tipMa5');
        const tipMa20 = document.getElementById('tipMa20');
        const tipMa60 = document.getElementById('tipMa60');
        const tipMa120 = document.getElementById('tipMa120');
        
        const tipVolMa20 = document.getElementById('tipVolMa20');
        const tipVolVal = document.getElementById('tipVolVal');
        
        if (cData) {
            if (tipOpen) tipOpen.innerText = (cData.open || 0).toLocaleString('ko-KR', { minimumFractionDigits: 2 });
            if (tipHigh) tipHigh.innerText = (cData.high || 0).toLocaleString('ko-KR', { minimumFractionDigits: 2 });
            if (tipLow) tipLow.innerText = (cData.low || 0).toLocaleString('ko-KR', { minimumFractionDigits: 2 });
            if (tipClose) tipClose.innerText = (cData.close || 0).toLocaleString('ko-KR', { minimumFractionDigits: 2 });
            
            // Calculate all OHLC percentage changes strictly based on Previous Close (전일 종가)
            const prevClose = prevCloseMap[timeKey] || cData.open || 1;
            const oDiff = ((cData.open - prevClose) / prevClose * 100);
            const hDiff = ((cData.high - prevClose) / prevClose * 100);
            const lDiff = ((cData.low - prevClose) / prevClose * 100);
            const cDiff = ((cData.close - prevClose) / prevClose * 100);
            
            if (tipOpenChg) {
                const isUp = oDiff >= 0;
                tipOpenChg.innerText = `(${isUp ? '+' : ''}${oDiff.toFixed(2)}%)`;
                tipOpenChg.className = isUp ? 'font-sans text-[#EF4444] text-[10.5px] font-medium tracking-tight num-clean' : 'font-sans text-[#3B82F6] text-[10.5px] font-medium tracking-tight num-clean';
            }
            if (tipHighChg) {
                const isUp = hDiff >= 0;
                tipHighChg.innerText = `(${isUp ? '+' : ''}${hDiff.toFixed(2)}%)`;
                tipHighChg.className = isUp ? 'font-sans text-[#EF4444] text-[10.5px] font-medium tracking-tight num-clean' : 'font-sans text-[#3B82F6] text-[10.5px] font-medium tracking-tight num-clean';
            }
            if (tipLowChg) {
                const isUp = lDiff >= 0;
                tipLowChg.innerText = `(${isUp ? '+' : ''}${lDiff.toFixed(2)}%)`;
                tipLowChg.className = isUp ? 'font-sans text-[#EF4444] text-[10.5px] font-medium tracking-tight num-clean' : 'font-sans text-[#3B82F6] text-[10.5px] font-medium tracking-tight num-clean';
            }
            if (tipCloseChg) {
                const isUp = cDiff >= 0;
                tipCloseChg.innerText = `(${isUp ? '+' : ''}${cDiff.toFixed(2)}%)`;
                tipCloseChg.className = isUp ? 'font-sans text-[#EF4444] text-[10.5px] font-medium tracking-tight num-clean' : 'font-sans text-[#3B82F6] text-[10.5px] font-medium tracking-tight num-clean';
            }
        }
        
        // MAs
        const mas = maMap[timeKey] || {};
        if (tipMa5) tipMa5.innerText = mas.ma5 ? mas.ma5.toLocaleString('ko-KR', { minimumFractionDigits: 2 }) : '-';
        if (tipMa20) tipMa20.innerText = mas.ma20 ? mas.ma20.toLocaleString('ko-KR', { minimumFractionDigits: 2 }) : '-';
        if (tipMa60) tipMa60.innerText = mas.ma60 ? mas.ma60.toLocaleString('ko-KR', { minimumFractionDigits: 2 }) : '-';
        if (tipMa120) tipMa120.innerText = mas.ma120 ? mas.ma120.toLocaleString('ko-KR', { minimumFractionDigits: 2 }) : '-';
        
        // Volume values: 1. Actual Day Volume (Front), 2. 20 MA Volume (Back)
        const curVol = (vData && vData.value !== undefined) ? vData.value : (volMap[timeKey] || null);
        const vMa = volMaMap[timeKey];
        if (tipVolVal) tipVolVal.innerText = curVol ? formatVolM(curVol) : '-';
        if (tipVolMa20) tipVolMa20.innerText = vMa ? formatVolM(vMa) : '-';
    }
    
    // Crosshair Move Event Handlers
    function handleCrosshair(param) {
        if (!param.time || !param.seriesData) return;
        const cData = param.seriesData.get(candleSeries);
        const vData = param.seriesData.get(volumeSeries);
        updateInChartOverlay(cData, vData, param.time);
    }
    
    mainChart.subscribeCrosshairMove(handleCrosshair);
    volChart.subscribeCrosshairMove(handleCrosshair);
    
    // Global Full-Height Continuous Vertical Guideline & Attached Dynamic Date Box
    // wrapper is already declared above
    const vertGuide = document.getElementById('globalCrosshairVert');
    const dateBadge = document.getElementById('globalCrosshairDateBadge');
    
    if (wrapper && vertGuide) {
        wrapper.onpointermove = (e) => {
            const rect = wrapper.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const maxW = rect.width - 75; // Right price scale width
            if (x >= 0 && x <= maxW) {
                vertGuide.style.left = `${x}px`;
                vertGuide.classList.remove('hidden');
                
                // Calculate date string for this exact X coordinate
                if (dateBadge && state.tvChart) {
                    try {
                        const time = state.tvChart.timeScale().coordinateToTime(x);
                        if (time) {
                            const ts = (typeof time === 'number' ? time : (time.timestamp || (time.year ? new Date(Date.UTC(time.year, time.month-1, time.day)).getTime()/1000 : 0)));
                            const d = new Date(ts * 1000);
                            const tf = state.detailTimeframe || 'day';
                            if (['1m', '3m', '5m', '15m', '30m', '60m'].includes(tf)) {
                                dateBadge.innerText = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
                            } else if (tf === 'year') {
                                dateBadge.innerText = `${d.getUTCFullYear()}`;
                            } else if (tf === 'month') {
                                dateBadge.innerText = `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`;
                            } else {
                                dateBadge.innerText = `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;
                            }
                        } else if (candles && candles.length) {
                            // In future whitespace beyond latest candle
                            const lastC = candles[candles.length - 1];
                            const lastTime = lastC ? lastC.time : Math.floor(Date.now() / 1000);
                            const lastX = state.tvChart.timeScale().timeToCoordinate(lastTime) || maxW;
                            const diffX = x - lastX;
                            const barSpacing = (candles.length > 1) ? ((lastX - (state.tvChart.timeScale().timeToCoordinate(candles[0].time) || 0)) / candles.length) : 6;
                            const extraBars = Math.round(diffX / (barSpacing || 6));
                            const extraSeconds = extraBars * (state.detailTimeframe === 'week' ? 7*86400 : (state.detailTimeframe === 'month' ? 30*86400 : (state.detailTimeframe === 'year' ? 365*86400 : 86400)));
                            const estD = new Date((lastTime + extraSeconds) * 1000);
                            const tf = state.detailTimeframe || 'day';
                            if (tf === 'year') {
                                dateBadge.innerText = `${estD.getUTCFullYear()}`;
                            } else if (tf === 'month') {
                                dateBadge.innerText = `${estD.getUTCFullYear()}-${String(estD.getUTCMonth()+1).padStart(2,'0')}`;
                            } else {
                                dateBadge.innerText = `${estD.getUTCFullYear()}-${String(estD.getUTCMonth()+1).padStart(2,'0')}-${String(estD.getUTCDate()).padStart(2,'0')}`;
                            }
                        }
                    } catch(err){}
                }
            } else {
                vertGuide.classList.add('hidden');
            }
        };
        wrapper.onpointerleave = () => {
            vertGuide.classList.add('hidden');
        };
    }
    
    // Initial display with latest candle
    const lastC = candles[candles.length - 1];
    updateInChartOverlay(lastC, null, lastC.time);
    
    // Set moderate initial zoom and position latest candle comfortably near middle/right-center
    const totalBars = candles.length;
    let visibleBars = 130; // default for day (~6 months)
    let rightOffsetBars = 35; // places the latest candle near right-center / middle

    if (state.detailTimeframe === 'week') {
        visibleBars = 100;
        rightOffsetBars = 25;
    } else if (state.detailTimeframe === 'month') {
        visibleBars = 60;
        rightOffsetBars = 15;
    } else if (state.detailTimeframe === 'year') {
        visibleBars = Math.min(35, totalBars);
        rightOffsetBars = 8;
    } else if (['1m', '3m', '5m', '15m', '30m', '60m'].includes(state.detailTimeframe)) {
        visibleBars = 120;
        rightOffsetBars = 30;
    }

    const fromIndex = Math.max(0, totalBars - visibleBars);
    const toIndex = totalBars - 1 + rightOffsetBars;

    try {
        mainChart.timeScale().setVisibleLogicalRange({ from: fromIndex, to: toIndex });
        volChart.timeScale().setVisibleLogicalRange({ from: fromIndex, to: toIndex });
    } catch(e) {
        mainChart.timeScale().fitContent();
        volChart.timeScale().fitContent();
    }
    
    window.addEventListener('resize', () => {
        if (state.tvChart && mainContainer) {
            state.tvChart.applyOptions({ width: mainContainer.clientWidth });
        }
        if (state.tvVolChart && volContainer) {
            state.tvVolChart.applyOptions({ width: volContainer.clientWidth });
        }
    });
}

function toggleMovingAverages() {
    state.showMovingAverages = !state.showMovingAverages;
    const iconOn = document.getElementById('iconMaEyeOn');
    const iconOff = document.getElementById('iconMaEyeOff');
    const maNumbers = document.getElementById('maNumbersContainer');
    
    if (state.showMovingAverages) {
        // MA is ON: show normal eye icon and show MA numbers
        if (iconOn) iconOn.classList.remove('hidden');
        if (iconOff) iconOff.classList.add('hidden');
        if (maNumbers) maNumbers.classList.remove('hidden');
    } else {
        // MA is OFF: show slashed eye icon and hide MA numbers only
        if (iconOn) iconOn.classList.add('hidden');
        if (iconOff) iconOff.classList.remove('hidden');
        if (maNumbers) maNumbers.classList.add('hidden');
    }
    
    if (state.tvMaSeriesList && state.tvMaSeriesList.length) {
        state.tvMaSeriesList.forEach(series => {
            try {
                series.applyOptions({ visible: state.showMovingAverages });
            } catch(e) {}
        });
    }
}

function changeTimeframe(tf) {
    document.querySelectorAll('.timeframe-btn').forEach(b => {
        b.classList.remove('active', 'text-amber-400', 'bg-amber-500/15', 'border-amber-500/30');
        b.classList.add('text-slate-400', 'border-transparent');
    });
    
    const menu = document.getElementById('menuMinuteSelect');
    if (menu) menu.classList.add('hidden');
    
    const minWrapper = document.getElementById('minuteToggleWrapper');
    if (['1m', '3m', '5m', '15m', '30m', '60m'].includes(tf)) {
        const mainBtn = document.getElementById('btnActiveMinute');
        const lbl = document.getElementById('lblMinuteText');
        const labelMap = { '1m': '1분', '3m': '3분', '5m': '5분', '15m': '15분', '30m': '30분', '60m': '60분' };
        if (lbl) lbl.innerText = labelMap[tf] || tf;
        if (mainBtn) mainBtn.setAttribute('data-tf', tf);
        
        if (minWrapper) {
            minWrapper.classList.add('active', 'text-amber-400', 'bg-amber-500/15', 'border-amber-500/30');
            minWrapper.classList.remove('text-slate-400', 'border-transparent');
        }
    } else {
        const targetBtn = document.querySelector(`[data-tf="${tf}"]`);
        if (targetBtn) {
            targetBtn.classList.add('active', 'text-amber-400', 'bg-amber-500/15', 'border-amber-500/30');
            targetBtn.classList.remove('text-slate-400', 'border-transparent');
        }
    }
    
    state.detailTimeframe = tf;
    loadIndexDetailData();
}

function selectMinuteTf(tf) {
    changeTimeframe(tf);
}

function toggleMinuteDropdown(event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    const menu = document.getElementById('menuMinuteSelect');
    if (menu) menu.classList.toggle('hidden');
}

// Global click outside listener for minute dropdown
document.addEventListener('click', (e) => {
    const menu = document.getElementById('menuMinuteSelect');
    const toggleBtn = document.getElementById('btnMinuteToggle');
    const mainBtn = document.getElementById('btnActiveMinute');
    if (menu && !menu.classList.contains('hidden')) {
        if (!menu.contains(e.target) && !toggleBtn?.contains(e.target) && !mainBtn?.contains(e.target)) {
            menu.classList.add('hidden');
        }
    }
});

window.changeTimeframe = changeTimeframe;
window.selectMinuteTf = selectMinuteTf;
window.toggleMinuteDropdown = toggleMinuteDropdown;


let isInSiteFullscreen = false;

function toggleInSiteFullscreen() {
    isInSiteFullscreen = !isInSiteFullscreen;
    const card = document.getElementById('tvChartCard');
    const wrapper = document.getElementById('tvChartWrapper');
    
    const lbl = document.getElementById('lblFullscreenText');
    const iconExp = document.getElementById('iconFullscreenExpand');
    const iconCol = document.getElementById('iconFullscreenCollapse');
    
    if (isInSiteFullscreen) {
        document.body.style.overflow = 'hidden';
        if (card) {
            card.classList.add('fixed', 'inset-0', 'z-[9999]', 'bg-[#0B0E14]', 'w-screen', 'h-screen', 'p-4', 'lg:p-6', 'rounded-none', 'flex', 'flex-col');
            card.classList.remove('toss-card', 'p-5', 'space-y-3');
        }
        if (wrapper) {
            wrapper.classList.remove('h-[580px]', 'rounded-xl');
            wrapper.classList.add('flex-1', 'h-full', 'rounded-lg');
        }
        if (lbl) lbl.innerText = '원래대로';
        if (iconExp) iconExp.classList.add('hidden');
        if (iconCol) iconCol.classList.remove('hidden');
    } else {
        document.body.style.overflow = '';
        if (card) {
            card.classList.remove('fixed', 'inset-0', 'z-[9999]', 'bg-[#0B0E14]', 'w-screen', 'h-screen', 'p-4', 'lg:p-6', 'rounded-none', 'flex', 'flex-col');
            card.classList.add('toss-card', 'p-5', 'space-y-3');
        }
        if (wrapper) {
            wrapper.classList.remove('flex-1', 'h-full', 'rounded-lg');
            wrapper.classList.add('h-[580px]', 'rounded-xl');
        }
        if (lbl) lbl.innerText = '차트 크게보기';
        if (iconExp) iconExp.classList.remove('hidden');
        if (iconCol) iconCol.classList.add('hidden');
    }
    
    setTimeout(() => {
        resizeChartsToContainer();
    }, 50);
}

function resizeChartsToContainer() {
    const mainContainer = document.getElementById('tvMainChartContainer');
    const volContainer = document.getElementById('tvVolumeChartContainer');
    const wrapper = document.getElementById('tvChartWrapper');
    if (!wrapper) return;
    
    const w = wrapper.clientWidth || 900;
    if (isInSiteFullscreen) {
        const totalH = wrapper.clientHeight || 700;
        const volH = 160;
        const mainH = Math.max(300, totalH - volH - 2);
        
        const mainPane = mainContainer?.parentElement;
        const volPane = volContainer?.parentElement;
        if (mainPane) mainPane.style.height = `${mainH}px`;
        if (volPane) volPane.style.height = `${volH}px`;
        
        if (state.tvChart) state.tvChart.applyOptions({ width: w, height: mainH });
        if (state.tvVolChart) state.tvVolChart.applyOptions({ width: w, height: volH });
    } else {
        const mainPane = mainContainer?.parentElement;
        const volPane = volContainer?.parentElement;
        if (mainPane) mainPane.style.height = '410px';
        if (volPane) volPane.style.height = '169px';
        
        if (state.tvChart) state.tvChart.applyOptions({ width: w, height: 410 });
        if (state.tvVolChart) state.tvVolChart.applyOptions({ width: w, height: 169 });
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isInSiteFullscreen) {
        toggleInSiteFullscreen();
    }
});

window.addEventListener('resize', () => {
    resizeChartsToContainer();
});

window.toggleInSiteFullscreen = toggleInSiteFullscreen;
window.toggleChartFullscreen = toggleInSiteFullscreen;
