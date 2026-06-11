"""Generate a self-contained HTML dashboard from backtest results.

The output is a single index.html file that uses:
  - Bootstrap 5.3 (CDN)
  - Plotly.js 2.x (CDN)
  - All data embedded as JSON in a <script> tag
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lastofus.config import get_period_labels, TICKER_CONFIG, TICKER_GROUPS

PERIOD_LABELS = get_period_labels()  # 실행 시점 연도 반영

_OUTPUT_DIR = Path(__file__).parents[3] / "reports" / "html"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_dashboard(
    results: dict[str, Any],
    output_dir: str | Path | None = None,
) -> Path:
    """Write index.html to *output_dir* and return the full path."""
    out_dir = Path(output_dir) if output_dir else _OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"

    html = _build_html(results)
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write(html)

    return out_file


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _build_html(results: dict[str, Any]) -> str:
    periods = list(PERIOD_LABELS.keys())
    period_labels = PERIOD_LABELS

    # Collect all valid period keys actually present in results
    active_periods: list[str] = []
    for p in periods:
        for ticker_data in results.values():
            if p in ticker_data and not ticker_data[p].get("skip"):
                active_periods.append(p)
                break

    json_data = json.dumps(results, ensure_ascii=False, default=_json_default)

    # Build summary table rows per group
    table_rows_html = _build_table_rows(results, active_periods)

    # Build period tab buttons
    tab_buttons = "\n".join(
        f'<button class="nav-link {"active" if i == 0 else ""}" '
        f'id="tab-{p}" data-bs-toggle="tab" data-bs-target="#pane-{p}" '
        f'type="button" role="tab">{period_labels.get(p, p)}</button>'
        for i, p in enumerate(active_periods)
    )

    # Build period tab panes (each pane shows that period's table)
    tab_panes = "\n".join(
        _build_period_pane(p, results, p == active_periods[0])
        for p in active_periods
    )

    from datetime import date
    gen_date = date.today().strftime("%Y-%m-%d")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>라오어 무한매수법 V2.2 백테스트 대시보드</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%231a1d2e'/%3E%3Ctext x='50%25' y='54%25' dominant-baseline='middle' text-anchor='middle' font-size='38' font-family='Arial,sans-serif' fill='%237c9fff'%3E%E2%88%9E%3C/text%3E%3C/svg%3E">
  <link rel="shortcut icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%231a1d2e'/%3E%3Ctext x='50%25' y='54%25' dominant-baseline='middle' text-anchor='middle' font-size='38' font-family='Arial,sans-serif' fill='%237c9fff'%3E%E2%88%9E%3C/text%3E%3C/svg%3E">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js" charset="utf-8"></script>
  <style>
    body {{ font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; background: #0f1117; color: #e0e0e0; }}
    .navbar {{ background: #1a1d2e !important; border-bottom: 1px solid #2d3154; }}
    .navbar-brand {{ color: #7c9fff !important; font-weight: 700; font-size: 1.1rem; }}
    .card {{ background: #1a1d2e; border: 1px solid #2d3154; }}
    .card-header {{ background: #222541; border-bottom: 1px solid #2d3154; font-weight: 600; }}
    .nav-tabs .nav-link {{ color: #9aa0c0; border: 1px solid #2d3154; background: #1a1d2e; margin-right: 3px; }}
    .nav-tabs .nav-link.active {{ color: #fff; background: #2d3154; border-color: #4c5699; }}
    /* ── 테이블 전역 다크 테마 ──────────────────────────────────────────── */
    .table {{
      --bs-table-bg: #1a1d2e;
      --bs-table-color: #e0e0e0;
      --bs-table-border-color: #2d3154;
      --bs-table-striped-bg: #1e2040;
      --bs-table-striped-color: #e0e0e0;
      --bs-table-hover-bg: #252847;
      --bs-table-hover-color: #e0e0e0;
      --bs-table-active-bg: #1e3a5f;
      color: #e0e0e0;
      border-color: #2d3154;
    }}
    /* Bootstrap 5는 td/th에 var(--bs-table-bg)를 직접 적용함 — 변수만 교체하면 됨 */
    .table thead th {{
      --bs-table-bg: #222541;
      color: #9aa0c0;
      border-color: #2d3154;
      font-size: 0.8rem;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    .table tbody tr {{
      border-color: #2d3154;
      cursor: pointer;
      transition: background-color 0.15s;
    }}
    .table tbody tr:hover {{ --bs-table-bg: #252847; }}
    .table tbody tr.selected {{ --bs-table-bg: #1e3a5f; }}
    .table td, .table th {{
      border-color: #2d3154;
      font-size: 0.85rem;
      vertical-align: middle;
    }}
    /* table-sm 내부 (명령어 표 등) */
    .table-sm td, .table-sm th {{
      font-size: 0.8rem;
      padding: 0.3rem 0.5rem;
    }}
    .badge-group {{ font-size: 0.7rem; padding: 2px 6px; border-radius: 3px; }}
    .cagr-pos {{ color: #4caf93; font-weight: 600; }}
    .cagr-neg {{ color: #e05c5c; font-weight: 600; }}
    .cagr-zero {{ color: #9aa0c0; }}
    .mdd-bad {{ color: #e05c5c; }}
    .mdd-ok {{ color: #9aa0c0; }}
    .metric-cell {{ text-align: right; }}
    .ticker-name {{ font-weight: 600; color: #7c9fff; }}
    .ticker-sub {{ font-size: 0.75rem; color: #6b7280; }}
    #chart-container {{ min-height: 450px; }}
    .chart-title {{ font-size: 0.95rem; color: #9aa0c0; margin-bottom: 6px; }}
    .summary-stats {{ display: flex; gap: 16px; flex-wrap: wrap; }}
    .stat-box {{ background: #222541; border: 1px solid #2d3154; border-radius: 6px; padding: 10px 16px; min-width: 130px; }}
    .stat-label {{ font-size: 0.7rem; color: #6b7280; text-transform: uppercase; }}
    .stat-value {{ font-size: 1.2rem; font-weight: 700; margin-top: 2px; }}
    .group-header td {{ background-color: #1e2040 !important; color: #7c9fff; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; padding: 4px 8px !important; cursor: default; }}
    .group-header:hover td {{ background-color: #1e2040 !important; }}
    code {{ background: #2a2f4a; color: #7cb9ff; padding: 1px 5px; border-radius: 3px; font-size: 0.82em; }}
    .legend-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }}
    footer {{ border-top: 1px solid #2d3154; margin-top: 40px; padding: 20px 0; color: #6b7280; font-size: 0.8rem; }}
    .daily-action-card {{ background: #1a2035; border: 1px solid #3d5a99; }}
    .daily-action-card .card-header {{ background: #1e2d50; color: #7cb9ff; }}
    .action-badge {{ background: #2d4a7a; color: #7cb9ff; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }}
    @media (max-width: 768px) {{
      .table td, .table th {{ font-size: 0.75rem; padding: 4px; }}
      .stat-box {{ min-width: 100px; }}
    }}
  </style>
</head>
<body>

<nav class="navbar navbar-expand-lg">
  <div class="container-fluid">
    <span class="navbar-brand">
      &#x1F4C8; 라오어 무한매수법 V2.2 — 백테스트 대시보드
    </span>
    <span class="text-muted small">생성일: {gen_date}</span>
  </div>
</nav>

<div class="container-fluid py-3">

  <!-- Overview cards -->
  <div class="row g-3 mb-4">
    <div class="col-12">
      <div class="card">
        <div class="card-header">&#x1F3AF; 전략 개요 — 라오어 무한매수법 V2.2</div>
        <div class="card-body">
          <div class="row g-2">
            <div class="col-md-6">
              <p class="mb-1 small text-muted">3x/2x 레버리지 ETF를 매일 종가 LOC 주문으로 매수하고, 목표 수익률 달성 시 전량 매도합니다.</p>
              <ul class="small mb-0" style="color:#9aa0c0">
                <li>US 3x ETF (TQQQ, SPXL, UPRO): 수익 목표 <strong style="color:#4caf93">+10%</strong></li>
                <li>US 1x ETF (QQQ, VOO): 수익 목표 <strong style="color:#4caf93">+10%</strong></li>
                <li>KR 2x ETF (KODEX레버리지 등): 수익 목표 <strong style="color:#4caf93">+7%</strong></li>
                <li>40 분할 매수 → 소진 시 25% 쿼터컷 후 재시작</li>
              </ul>
            </div>
            <div class="col-md-6">
              <ul class="small mb-0" style="color:#9aa0c0">
                <li>전반전(0~50%): 평단가 및 평단가×1.05 이하 시 각 0.5유닛 매수</li>
                <li>후반전(50~100%): 평단가 이하 시만 1.0유닛 매수</li>
                <li>벤치마크: Buy &amp; Hold, DCA(40일 균등 분할)</li>
                <li>원금: US $10,000 / KR 10,000,000원</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Period tabs -->
  <div class="card mb-4">
    <div class="card-header">
      <ul class="nav nav-tabs card-header-tabs" id="periodTabs" role="tablist">
        {tab_buttons}
      </ul>
    </div>
    <div class="card-body p-0">
      <div class="tab-content" id="periodTabContent">
        {tab_panes}
      </div>
    </div>
  </div>

  <!-- Chart section -->
  <div class="card mb-4">
    <div class="card-header">
      <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
        <div>
          <div style="font-size:0.75rem;color:#6b7280;margin-bottom:2px;">
            &#x1F4CA; 자본금 곡선 &nbsp;—&nbsp; <span style="color:#9aa0c0">위 표에서 종목을 클릭하면 그래프가 바뀝니다</span>
          </div>
          <div style="font-size:1.05rem;font-weight:700;color:#e0e0e0;">
            <span id="chart-ticker-code" style="color:#7c9fff;margin-right:6px;">—</span>
            <span id="chart-ticker-name" style="color:#e0e0e0;"></span>
          </div>
        </div>
        <div class="text-end">
          <span id="chart-period-badge" style="background:#2d3154;color:#9aa0c0;padding:3px 10px;border-radius:12px;font-size:0.8rem;"></span>
        </div>
      </div>
    </div>
    <div class="card-body">

      <!-- 범례 설명 -->
      <div class="d-flex flex-wrap gap-3 mb-3 px-1" style="font-size:0.82rem;color:#9aa0c0;border-bottom:1px solid #2d3154;padding-bottom:10px;">
        <span>
          <span style="display:inline-block;width:22px;height:3px;background:#4caf93;border-radius:2px;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#4caf93;">전략 V2.2</strong>
          &nbsp;라오어 무한매수법 — 매일 LOC 분할매수, 목표 수익 달성 시 전량 익절
        </span>
        <span>
          <span style="display:inline-block;width:22px;height:2px;background:#7c9fff;vertical-align:middle;margin-right:5px;border-top:2px dotted #7c9fff;"></span>
          <strong style="color:#7c9fff;">Buy &amp; Hold</strong>
          &nbsp;첫날 원금 전액 매수 후 끝까지 보유 (매도 없음)
        </span>
        <span>
          <span style="display:inline-block;width:22px;height:0;border-top:2px dashed #f0a500;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#f0a500;">DCA (적립식)</strong>
          &nbsp;원금을 40등분해 처음 40 거래일에 매일 균등 매수 후 보유
        </span>
        <span style="margin-left:auto;color:#6b7280;font-size:0.75rem;align-self:center;">
          ※ Y축: 원금=100 기준 정규화
        </span>
      </div>

      <div id="summary-stats-container" class="summary-stats mb-3"></div>
      <div id="chart-container">
        <div class="d-flex align-items-center justify-content-center" style="height:400px;color:#6b7280;">
          &#x1F447; 위 표에서 종목을 클릭하면 자본금 곡선이 표시됩니다
        </div>
      </div>
    </div>
  </div>

  <!-- Daily Actions -->
  <div class="card daily-action-card mb-4">
    <div class="card-header">&#x23F0; 매일 할 일 (Daily Action Guide)</div>
    <div class="card-body">
      <div class="row g-3">
        <div class="col-md-6">
          <h6 class="text-info">&#x1F1FA;&#x1F1F8; 미국 주식 (매일 오전 5~6시 KST, 장 마감 전)</h6>
          <ol class="small" style="color:#9aa0c0">
            <li>터미널에서 <code>make orders</code> 실행 → 오늘 주문 목록 확인</li>
            <li>증권사 앱에서 각 티커의 <strong>LOC(장 마감 지정가)</strong> 매수 주문 입력</li>
            <li>목표 수익 도달 티커는 <strong>지정가 매도</strong> 주문 입력</li>
            <li>체결 후 <code>state/TICKER_state.json</code> 파일 업데이트</li>
            <li><code>make daily</code> 실행 → 대시보드 최신화</li>
          </ol>
        </div>
        <div class="col-md-6">
          <h6 class="text-warning">&#x1F1F0;&#x1F1F7; 한국 주식 (매일 15:00~15:30 KST)</h6>
          <ol class="small" style="color:#9aa0c0">
            <li>터미널에서 <code>make orders</code> 실행 → 오늘 주문 목록 확인</li>
            <li>HTS/MTS에서 <strong>시장가 또는 지정가</strong> 매수 주문 입력</li>
            <li>목표 수익 도달 종목은 <strong>지정가 매도</strong> 주문</li>
            <li>체결 후 state 파일 업데이트</li>
            <li><code>make daily</code> 실행 → 대시보드 최신화</li>
          </ol>
        </div>
        <div class="col-md-6">
          <h6 class="text-success">&#x1F4BB; 유용한 명령어</h6>
          <table class="table table-sm" style="font-size:0.8rem">
            <tbody>
              <tr><td><code>make install</code></td><td>최초 설치</td></tr>
              <tr><td><code>make fetch</code></td><td>시세 데이터 다운로드</td></tr>
              <tr><td><code>make backtest</code></td><td>백테스트 실행</td></tr>
              <tr><td><code>make dashboard</code></td><td>대시보드 생성</td></tr>
              <tr><td><code>make daily</code></td><td>전체 업데이트 (매일 실행)</td></tr>
              <tr><td><code>make orders</code></td><td>오늘 주문 목록 출력</td></tr>
              <tr><td><code>make publish</code></td><td>서버에 배포</td></tr>
            </tbody>
          </table>
        </div>
        <div class="col-md-6">
          <h6 class="text-danger">&#x26A0;&#xFE0F; 주의 사항</h6>
          <ul class="small" style="color:#9aa0c0">
            <li>이 백테스트는 <strong>과거 데이터 기반</strong>이며 미래 수익을 보장하지 않습니다.</li>
            <li>레버리지 ETF는 변동성이 크며 장기 보유 시 <strong>음의 복리 효과</strong>가 발생할 수 있습니다.</li>
            <li>투자 결정은 반드시 <strong>본인의 판단</strong>으로 하세요.</li>
            <li>쿼터컷 발생 시 손실을 확정하므로 심리적 대비가 필요합니다.</li>
          </ul>
          <div class="mt-2 p-2" style="background:#1e2040;border-radius:6px;font-size:0.8rem">
            <strong>권장 크론 스케줄:</strong><br>
            <code>0 6 * * 1-5  cd /path/to/project && make daily</code>
            <br><small class="text-muted">(평일 오전 6시 KST 자동 업데이트)</small>
          </div>
        </div>
      </div>
    </div>
  </div>

</div><!-- /container -->

<footer class="container-fluid text-center">
  <p>
    라오어 무한매수법 V2.2 백테스트 시스템 |
    기존 대시보드: <a href="http://psncs.iptime.org/stock_candle/index.html" target="_blank" style="color:#7c9fff">stock_candle</a>
  </p>
  <p>
    <a href="https://github.com/cheoljoo/the-last-of-us-stock/blob/main/plan-opus.md" target="_blank" style="color:#7c9fff">
      &#x1F4D6; 전략 설계 문서 (plan-opus.md)
    </a>
    &nbsp;&nbsp;|&nbsp;&nbsp;
    <a href="https://github.com/cheoljoo/the-last-of-us-stock" target="_blank" style="color:#7c9fff">
      &#x1F4E6; 소스코드 (GitHub)
    </a>
  </p>
  <p class="text-muted">생성: {gen_date} | 투자는 본인 책임입니다.</p>
</footer>

<script>
// ============================================================
// Embedded result data
// ============================================================
const RESULTS = {json_data};

const PERIOD_LABELS = {json.dumps(PERIOD_LABELS, ensure_ascii=False)};
const TICKER_CONFIG = {json.dumps(
    {k: {"name": v["name"], "market": v["market"], "leverage": v["leverage"]}
     for k, v in TICKER_CONFIG.items()},
    ensure_ascii=False
)};

// ============================================================
// Table row click → draw chart
// ============================================================
let selectedRow = null;

document.querySelectorAll('tr[data-ticker]').forEach(row => {{
  row.addEventListener('click', function() {{
    const ticker = this.dataset.ticker;
    const period = this.dataset.period;

    // Highlight row
    if (selectedRow) selectedRow.classList.remove('selected');
    this.classList.add('selected');
    selectedRow = this;

    drawChart(ticker, period);
  }});
}});

function drawChart(ticker, period) {{
  const res = RESULTS[ticker] && RESULTS[ticker][period];
  if (!res || res.skip) {{
    document.getElementById('chart-container').innerHTML =
      '<div class="d-flex align-items-center justify-content-center" style="height:400px;color:#6b7280">데이터 없음</div>';
    return;
  }}

  const cfg = TICKER_CONFIG[ticker] || {{}};
  const levLabel = cfg.leverage ? `${{cfg.leverage}}x` : '';
  const mktLabel = cfg.market === 'KR' ? '🇰🇷' : '🇺🇸';
  document.getElementById('chart-ticker-code').textContent = ticker;
  document.getElementById('chart-ticker-name').textContent =
    (cfg.name || '') + (levLabel ? '  ·  레버리지 ' + levLabel : '') + '  ' + mktLabel;
  document.getElementById('chart-period-badge').textContent =
    PERIOD_LABELS[period] || period;

  const dates   = res.dates || [];
  const strat   = res.equity_strategy || [];
  const bah     = res.equity_bah || [];
  const dca     = res.equity_dca || [];
  const principal = res.principal || 10000;

  // Normalise to 100
  const norm = arr => arr.map(v => v / principal * 100);

  const traces = [
    {{ x: dates, y: norm(strat), name: '전략 (V2.2)', line: {{ color: '#4caf93', width: 2 }} }},
    {{ x: dates, y: norm(bah),   name: 'Buy & Hold', line: {{ color: '#7c9fff', width: 1.5, dash: 'dot' }} }},
    {{ x: dates, y: norm(dca),   name: 'DCA',         line: {{ color: '#f0a500', width: 1.5, dash: 'dash' }} }},
  ];

  const chartTitle = `${{ticker}}  ${{cfg.name || ''}}  ·  ${{PERIOD_LABELS[period] || period}}`;
  const layout = {{
    paper_bgcolor: '#1a1d2e',
    plot_bgcolor:  '#1a1d2e',
    font:          {{ color: '#9aa0c0', size: 11 }},
    title:         {{ text: chartTitle, font: {{ color: '#e0e0e0', size: 13 }}, x: 0.01, xanchor: 'left' }},
    xaxis:         {{ gridcolor: '#2d3154', showgrid: true }},
    yaxis:         {{ gridcolor: '#2d3154', showgrid: true, title: '수익률 (원금=100)' }},
    legend:        {{ orientation: 'h', y: 1.12, font: {{ size: 12 }} }},
    margin:        {{ t: 60, b: 40, l: 60, r: 20 }},
    hovermode:     'x unified',
    shapes: [{{
      type: 'line', xref: 'paper', x0: 0, x1: 1,
      y0: 100, y1: 100,
      line: {{ color: '#4d5166', width: 1, dash: 'dot' }}
    }}],
  }};

  Plotly.newPlot('chart-container', traces, layout, {{responsive: true}});

  // Show summary stats
  const ms = res.metrics_strategy || {{}};
  const mb = res.metrics_bah || {{}};
  const container = document.getElementById('summary-stats-container');
  container.style.display = 'flex';
  container.innerHTML = `
    <div class="stat-box">
      <div class="stat-label">전략 CAGR</div>
      <div class="stat-value ${{(ms.cagr||0) >= 0 ? 'cagr-pos' : 'cagr-neg'}}">${{pct(ms.cagr)}}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">B&H CAGR</div>
      <div class="stat-value ${{(mb.cagr||0) >= 0 ? 'cagr-pos' : 'cagr-neg'}}">${{pct(mb.cagr)}}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">전략 MDD</div>
      <div class="stat-value ${{(ms.mdd||0) < -0.3 ? 'cagr-neg' : 'mdd-ok'}}">${{pct(ms.mdd)}}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Sharpe</div>
      <div class="stat-value">${{(ms.sharpe||0).toFixed(2)}}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">사이클 수</div>
      <div class="stat-value" style="color:#f0a500">${{res.final_cycles || 0}}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">쿼터컷 수</div>
      <div class="stat-value" style="color:#e05c5c">${{res.final_quarter_cuts || 0}}</div>
    </div>
  `;
}}

function pct(v) {{
  if (v === undefined || v === null || isNaN(v)) return 'N/A';
  return (v * 100).toFixed(1) + '%';
}}

// Activate first tab's first row on load
window.addEventListener('load', () => {{
  const firstRow = document.querySelector('tr[data-ticker]');
  if (firstRow) firstRow.click();
}});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def _build_table_rows(results: dict, active_periods: list[str]) -> str:
    """Build HTML table rows grouped by TICKER_GROUPS for the main summary view."""
    rows = []
    for group_name, tickers in TICKER_GROUPS.items():
        rows.append(
            f'<tr class="group-header"><td colspan="20">{group_name}</td></tr>'
        )
        for ticker in tickers:
            if ticker not in results:
                continue
            cfg = TICKER_CONFIG.get(ticker, {})
            name = cfg.get("name", ticker)
            # Use first active period for the clickable row default
            first_period = active_periods[0] if active_periods else "3yr"
            res = results.get(ticker, {}).get(first_period, {})
            ms = res.get("metrics_strategy", {}) if not res.get("skip") else {}

            cells = []
            for p in active_periods:
                r = results.get(ticker, {}).get(p, {})
                if r.get("skip") or not r:
                    cells.append('<td class="metric-cell text-muted small">—</td><td class="metric-cell text-muted small">—</td>')
                else:
                    m = r.get("metrics_strategy", {})
                    mb = r.get("metrics_bah", {})
                    cagr = m.get("cagr", 0)
                    mdd  = m.get("mdd", 0)
                    bah_cagr = mb.get("cagr", 0)
                    cagr_class = "cagr-pos" if cagr > 0 else ("cagr-neg" if cagr < 0 else "cagr-zero")
                    mdd_class  = "mdd-bad" if mdd < -0.30 else "mdd-ok"
                    cells.append(
                        f'<td class="metric-cell"><span class="{cagr_class}">{cagr*100:.1f}%</span>'
                        f'<br><small class="text-muted">{bah_cagr*100:.1f}%</small></td>'
                        f'<td class="metric-cell {mdd_class}">{mdd*100:.1f}%</td>'
                    )

            row_cells = "\n".join(cells)
            rows.append(
                f'<tr data-ticker="{ticker}" data-period="{first_period}">'
                f'<td><div class="ticker-name">{ticker}</div>'
                f'<div class="ticker-sub">{name}</div></td>'
                f'{row_cells}'
                f'</tr>'
            )
    return "\n".join(rows)


def _build_period_pane(period: str, results: dict, is_active: bool) -> str:
    """Build one tab-pane for a given period with a full comparison table."""
    active_class = "show active" if is_active else ""
    label = PERIOD_LABELS.get(period, period)

    rows = []
    for group_name, tickers in TICKER_GROUPS.items():
        rows.append(
            f'<tr class="group-header"><td colspan="9">{group_name}</td></tr>'
        )
        for ticker in tickers:
            if ticker not in results:
                continue
            cfg = TICKER_CONFIG.get(ticker, {})
            name = cfg.get("name", ticker)
            r = results.get(ticker, {}).get(period, {})

            if r.get("skip") or not r:
                rows.append(
                    f'<tr data-ticker="{ticker}" data-period="{period}">'
                    f'<td><div class="ticker-name">{ticker}</div>'
                    f'<div class="ticker-sub">{name}</div></td>'
                    f'<td colspan="8" class="text-muted small text-center">데이터 없음</td>'
                    f'</tr>'
                )
                continue

            ms  = r.get("metrics_strategy", {})
            mb  = r.get("metrics_bah", {})
            md  = r.get("metrics_dca", {})
            cagr    = ms.get("cagr", 0)
            mdd     = ms.get("mdd", 0)
            sharpe  = ms.get("sharpe", 0)
            sortino = ms.get("sortino", 0)
            cycles  = r.get("final_cycles", 0)
            qcuts   = r.get("final_quarter_cuts", 0)
            bah_c   = mb.get("cagr", 0)
            dca_c   = md.get("cagr", 0)

            cagr_class = "cagr-pos" if cagr > 0 else ("cagr-neg" if cagr < 0 else "cagr-zero")
            mdd_class  = "mdd-bad" if mdd < -0.30 else "mdd-ok"

            rows.append(
                f'<tr data-ticker="{ticker}" data-period="{period}">'
                f'<td><div class="ticker-name">{ticker}</div>'
                f'<div class="ticker-sub">{name}</div></td>'
                f'<td class="metric-cell"><span class="{cagr_class}">{cagr*100:.1f}%</span></td>'
                f'<td class="metric-cell text-muted small">{bah_c*100:.1f}%</td>'
                f'<td class="metric-cell text-muted small">{dca_c*100:.1f}%</td>'
                f'<td class="metric-cell {mdd_class}">{mdd*100:.1f}%</td>'
                f'<td class="metric-cell">{sharpe:.2f}</td>'
                f'<td class="metric-cell">{sortino:.2f}</td>'
                f'<td class="metric-cell" style="color:#f0a500">{cycles}</td>'
                f'<td class="metric-cell" style="color:#e05c5c">{qcuts}</td>'
                f'</tr>'
            )

    rows_html = "\n".join(rows)

    return f"""
<div class="tab-pane fade {active_class}" id="pane-{period}" role="tabpanel">
  <div class="table-responsive" style="max-height:500px;overflow-y:auto">
    <table class="table table-hover mb-0">
      <thead>
        <tr>
          <th style="min-width:180px">티커 / 이름</th>
          <th class="metric-cell">전략 CAGR</th>
          <th class="metric-cell">B&H CAGR</th>
          <th class="metric-cell">DCA CAGR</th>
          <th class="metric-cell">MDD</th>
          <th class="metric-cell">Sharpe</th>
          <th class="metric-cell">Sortino</th>
          <th class="metric-cell">사이클</th>
          <th class="metric-cell">쿼터컷</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>
  <div class="p-2 text-muted small">
    구간: {label} | 티커 클릭 시 자본금 곡선 표시
  </div>
</div>"""


# ---------------------------------------------------------------------------
# JSON serialiser
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Not serialisable: {type(obj)}")
