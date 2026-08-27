let state = {
    marketFilter: 'all',
    sortFilter: 'trading_value',
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
            hide_warning: state.hideWarning
        });
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
            실시간 피드: <span class="font-sans text-amber-400 font-semibold">${server_time}</span>
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

        const cardStyleClasses = isSessionActive 
            ? 'border-amber-500/40 bg-gradient-to-br from-[#161B22] to-amber-950/20 shadow-md shadow-amber-500/10' 
            : 'border-[#2D333B] bg-[#161B22]';

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
    const updateTimeEl = document.getElementById('tableUpdateTime');
    if (updateTimeEl && updatedAt) {
        updateTimeEl.innerText = `순위 · 오늘 ${updatedAt} 기준`;
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
        const tradingValStr = `${stock.trading_value.toLocaleString()}억원`;

        return `
            <tr class="stock-row" onclick="openStockDetail('${stock.code}')">
                <!-- Rank -->
                <td class="font-bold text-slate-400 text-sm pl-4 w-12 text-center font-sans">
                    ${stock.rank}
                </td>
                
                <!-- Stock Info -->
                <td>
                    <div class="flex items-center gap-3">
                        <div class="logo-badge shadow-md border border-white/10" style="background-color: ${stock.badge_bg}">
                            ${stock.badge_text}
                        </div>
                        <div>
                            <div class="flex items-center gap-1.5">
                                <span class="font-bold text-slate-100 text-sm hover:text-amber-400 transition">${stock.name}</span>
                                ${stock.is_warning ? `<span class="badge-tag bg-amber-950/60 text-amber-400 border border-amber-500/40 text-[10px]">투자주의</span>` : ''}
                            </div>
                            <span class="text-xs text-slate-400 font-sans">${stock.code} · ${stock.market === 'KR' ? '국내' : '해외'}</span>
                        </div>
                    </div>
                </td>

                <!-- Price -->
                <td class="text-right font-extrabold font-sans text-slate-100 text-sm">
                    ${formattedPrice}
                </td>

                <!-- Change Rate -->
                <td class="text-right">
                    <span class="inline-block px-2.5 py-1 rounded-md text-xs font-bold font-sans ${stock.change_rate > 0 ? 'bg-red-500/15 text-[#FF5252] border border-red-500/20' : (stock.change_rate < 0 ? 'bg-blue-500/15 text-[#3B82F6] border border-blue-500/20' : 'bg-slate-800 text-slate-400')}">
                        ${changeInfo.formattedRate}
                    </span>
                </td>

                <!-- Trading Value -->
                <td class="text-right font-sans text-sm font-semibold text-slate-200">
                    ${tradingValStr}
                </td>

                <!-- Market Cap -->
                <td class="text-right font-sans text-xs text-slate-400">
                    ${stock.market_cap}
                </td>

                <!-- STRIX Trading Ratio Bar -->
                <td>
                    <div class="flex flex-col items-center gap-1">
                        <div class="ratio-bar-container">
                            <span class="text-[11px] font-bold text-blue-400 font-sans">${stock.buy_ratio}</span>
                            <div class="ratio-bar">
                                <div class="ratio-bar-buy" style="width: ${stock.buy_ratio}%"></div>
                                <div class="ratio-bar-sell" style="width: ${stock.sell_ratio}%"></div>
                            </div>
                            <span class="text-[11px] font-bold text-red-400 font-sans">${stock.sell_ratio}</span>
                        </div>
                    </div>
                </td>

                <!-- Sector -->
                <td>
                    <span class="badge-tag bg-[#21262D] text-slate-300 border border-[#2D333B] font-medium">
                        ${stock.sector || '-'}
                    </span>
                </td>

                <!-- AI Summary -->
                <td class="pr-4 max-w-xs">
                    ${stock.ai_summary ? `
                        <div class="flex items-center gap-1.5 text-xs text-slate-300 font-medium truncate" title="${stock.ai_summary}">
                            <span class="w-1.5 h-1.5 rounded-full bg-amber-400 shadow-sm shadow-amber-400 flex-shrink-0"></span>
                            <span class="truncate">${stock.ai_summary}</span>
                        </div>
                    ` : '<span class="text-slate-600 text-xs">-</span>'}
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

    document.getElementById('modalTradingValue').innerText = `${stock.trading_value.toLocaleString()} 억원`;
    document.getElementById('modalMarketCap').innerText = stock.market_cap;
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

    // 1-second interval
    setInterval(() => {
        fetchMarketStatus();
        fetchIndices();
        fetchStocks();
    }, 1000);
});