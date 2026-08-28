
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

function formatMarketCap(cap) {
    if (!cap) return '-';
    if (typeof cap === 'string') {
        if (cap.includes('조원') || cap.includes('억원') || cap.includes('$') || cap.includes('T') || cap.includes('B') || cap.includes('M')) {
            return cap;
        }
        if (cap.includes('조')) {
            const m = cap.match(/([\d,.]+)\s*조(?:\s*([\d,.]+)\s*억)?/);
            if (m) {
                const jo = parseFloat(m[1].replace(/,/g, ''));
                const eok = m[2] ? parseFloat(m[2].replace(/,/g, '')) : 0;
                return `${(jo + (eok / 10000)).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}조원`;
            }
        } else if (cap.includes('억')) {
            const m = cap.match(/([\d,.]+)\s*억/);
            if (m) {
                const eok = parseFloat(m[1].replace(/,/g, ''));
                if (eok >= 10000) {
                    return `${(eok / 10000).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}조원`;
                }
                return `${Math.round(eok).toLocaleString('ko-KR')}억원`;
            }
        }
    }
    const num = Number(cap);
    if (!isNaN(num)) {
        if (num >= 10000) {
            return `${(num / 10000).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}조원`;
        }
        return `${Math.round(num).toLocaleString('ko-KR')}억원`;
    }
    return cap;
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
    selectedStock: null
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

        return `
            <div class="index-card ${cardStyleClasses} flex flex-col justify-between h-[215px]">
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
                    ${formatMarketCap(stock.market_cap)}
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
document.addEventListener('DOMContentLoaded', () => {
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

    // Optimal Golden-Standard Live Intervals (Zero Server Strain + High Responsiveness)
    setInterval(updateClockTick, 1000);    // Smooth 1-second local clock tick
    setInterval(fetchIndices, 3000);       // Global Indices every 3 seconds
    setInterval(fetchStocks, 5000);        // Stock Quotes & Execution Strength every 5 seconds
    setInterval(fetchMarketStatus, 15000); // Market Session Status sync every 15 seconds
});