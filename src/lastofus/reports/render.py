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

    # Multi-asset VR section
    multi_vr_section = _build_multi_vr_section(results, active_periods)

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
    #chart-container, #mvr-chart-container {{ min-height: 450px; }}
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
    .card-badge {{ display:inline-block; font-size:0.72rem; font-weight:700; padding:3px 9px; border-radius:12px; white-space:nowrap; letter-spacing:0.03em; }}
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
      &#x1F4C8; 라오어 무한매수법 — 백테스트 대시보드
    </span>
    <span class="text-muted small">생성일: {gen_date}</span>
  </div>
</nav>

<div class="container-fluid py-3">

  <!-- Overview cards -->
  <div class="row g-3 mb-4">
    <div class="col-12">
      <div class="card">
        <div class="card-header d-flex align-items-center gap-2">
          <span class="card-badge" style="background:#7c9fff;color:#0f1117">전략 개요</span>
          <span>5가지 전략 비교 — V2.2 · V3.0 · V4.0 · VR · VR5.0</span>
        </div>
        <div class="card-body">
          <div class="row g-3">
            <div class="col-md-4">
              <div style="border-left:3px solid #4caf93;padding-left:10px;">
                <div style="font-weight:700;color:#4caf93;margin-bottom:4px;">📊 V2.2 (무한매수법)</div>
                <ul class="small mb-0" style="color:#9aa0c0;padding-left:16px;">
                  <li>40분할, 하루 LOC 분할매수</li>
                  <li>US 3x +10% / KR 2x +7% 익절</li>
                  <li>전반전: 평단×1.05 / 평단 이중 주문</li>
                  <li>후반전: 평단 이하만 보수적 매수</li>
                  <li>40회 소진 시 25% 쿼터컷</li>
                </ul>
              </div>
            </div>
            <div class="col-md-4">
              <div style="border-left:3px solid #f0a500;padding-left:10px;">
                <div style="font-weight:700;color:#f0a500;margin-bottom:4px;">🚀 V3.0 (공격형)</div>
                <ul class="small mb-0" style="color:#9aa0c0;padding-left:16px;">
                  <li><strong>20분할</strong> (V2.2의 절반)</li>
                  <li>US 3x +15% / SOXL +20% 익절</li>
                  <li>별% 공식: <code>(15−1.5T)%</code></li>
                  <li>전반전: 별% / 평단 이중 주문</li>
                  <li>후반전: 별%(음수 가능) 집중 매수</li>
                  <li>부분복리 50% 재투자 지원</li>
                </ul>
              </div>
            </div>
            <div class="col-md-4">
              <div style="border-left:3px solid #e05c5c;padding-left:10px;">
                <div style="font-weight:700;color:#e05c5c;margin-bottom:4px;">🔻 V4.0 (일반+리버스)</div>
                <ul class="small mb-0" style="color:#9aa0c0;padding-left:16px;">
                  <li>2026 최신 오피셜 (일반모드+리버스모드)</li>
                  <li>1회매수금 = 잔금/(분할수−T) 매일 변동</li>
                  <li>매도: 1/4 쿼터매도 + 3/4 익절 지정가</li>
                  <li>소진 시 리버스모드 — 무한매도+쿼터매수</li>
                  <li>사이클 종료해도 T는 ×0.25로 이월</li>
                </ul>
              </div>
            </div>
            <div class="col-md-4">
              <div style="border-left:3px solid #9b59b6;padding-left:10px;">
                <div style="font-weight:700;color:#9b59b6;margin-bottom:4px;">⚖️ VR (밸류리밸런싱, 근사)</div>
                <ul class="small mb-0" style="color:#9aa0c0;padding-left:16px;">
                  <li>V목표값 기반 2주 사이클 재배분</li>
                  <li>V(n) = V(n-1) × (1 + G×0.1%) (근사 공식)</li>
                  <li>밴드 이탈 시 기계적 매수/매도</li>
                  <li>Slope G=11 / 밴드 ±8% 기본값</li>
                  <li>현금 풀 25% 유지, 2주마다 적립</li>
                </ul>
              </div>
            </div>
            <div class="col-md-4">
              <div style="border-left:3px solid #17becf;padding-left:10px;">
                <div style="font-weight:700;color:#17becf;margin-bottom:4px;">⚖️ VR 5.0 (오피셜 공식)</div>
                <ul class="small mb-0" style="color:#9aa0c0;padding-left:16px;">
                  <li>다음V = V + Pool/G + 적립금(−인출금)</li>
                  <li>밴드 ±15% 오피셜 (상단초과→V로 매도)</li>
                  <li>G=10(적립/거치) 시작, 1년마다 완화</li>
                  <li>Pool 사용한도: 적립75%/거치50%/인출25%</li>
                  <li>적립식/거치식/인출식 — 공식은 동일</li>
                </ul>
              </div>
            </div>
          </div>
          <div class="mt-2 small" style="color:#6b7280;">
            ※ 원금: US $10,000 / KR ₩10,000,000 | 벤치마크: Buy&amp;Hold, DCA(40일 균등)
            · V4.0/VR5.0 출처: <a href="https://quantstack.app/" target="_blank" style="color:#7c9fff">quantstack.app</a> (비공식 정리, 원저작권 라오어)
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Period tabs -->
  <div class="card mb-4">
    <div class="card-header" style="padding-bottom:0">
      <div class="d-flex align-items-center gap-2 mb-2">
        <span class="card-badge" style="background:#4caf93;color:#0f1117">백테스트 결과</span>
        <span style="font-size:0.85rem;color:#9aa0c0">구간을 선택하고 종목을 클릭하면 차트가 바뀝니다 · 수치는 <strong style="color:#e0e0e0">투입금 대비 연환산/총수익</strong></span>
      </div>
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
          <div class="d-flex align-items-center gap-2 mb-1">
            <span class="card-badge" style="background:#f0a500;color:#0f1117">자본금 곡선</span>
            <span style="font-size:0.78rem;color:#6b7280">위 표에서 종목을 클릭하면 그래프가 바뀝니다</span>
          </div>
          <div style="font-size:1.05rem;font-weight:700;color:#e0e0e0;">
            <span id="chart-ticker-code" style="color:#7c9fff;margin-right:6px;">—</span>
            <span id="chart-ticker-name" style="color:#e0e0e0;"></span>
          </div>
        </div>
        <div class="d-flex align-items-center gap-3">
          <!-- 전략 선택기 -->
          <div class="btn-group btn-group-sm" role="group" aria-label="전략 선택">
            <button type="button" class="btn btn-outline-success active" id="btn-strat-v22"
              onclick="selectStrategy('v22')">V2.2</button>
            <button type="button" class="btn btn-outline-warning" id="btn-strat-v30"
              onclick="selectStrategy('v30')">V3.0</button>
            <button type="button" class="btn btn-outline-danger" id="btn-strat-v4"
              onclick="selectStrategy('v4')">V4.0</button>
            <button type="button" class="btn btn-outline-info" id="btn-strat-vr"
              onclick="selectStrategy('vr')">VR</button>
            <button type="button" class="btn btn-outline-primary" id="btn-strat-vr5"
              onclick="selectStrategy('vr5')">VR5.0</button>
          </div>
          <span id="chart-period-badge" style="background:#2d3154;color:#9aa0c0;padding:3px 10px;border-radius:12px;font-size:0.8rem;"></span>
        </div>
      </div>
    </div>
    <div class="card-body">

      <!-- 범례 설명 -->
      <div id="legend-v22" class="d-flex flex-wrap gap-3 mb-3 px-1" style="font-size:0.82rem;color:#9aa0c0;border-bottom:1px solid #2d3154;padding-bottom:10px;">
        <span><span style="display:inline-block;width:22px;height:3px;background:#4caf93;border-radius:2px;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#4caf93;">V2.2 전략</strong>&nbsp;40분할 LOC, 평단×1.05/평단 이중 주문</span>
        <span><span style="display:inline-block;width:22px;height:2px;background:#7c9fff;vertical-align:middle;margin-right:5px;border-top:2px dotted #7c9fff;"></span>
          <strong style="color:#7c9fff;">Buy &amp; Hold</strong>&nbsp;첫날 전액 매수</span>
        <span><span style="display:inline-block;width:22px;height:0;border-top:2px dashed #f0a500;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#f0a500;">月DCA</strong>&nbsp;매월 초 균등 적립 (원금÷월수)</span>
        <span style="margin-left:auto;color:#6b7280;font-size:0.75rem;align-self:center;">※ 투입원금=100 정규화 | stat: 투입금 대비 연환산</span>
      </div>
      <div id="legend-v30" class="d-flex flex-wrap gap-3 mb-3 px-1" style="display:none!important;font-size:0.82rem;color:#9aa0c0;border-bottom:1px solid #2d3154;padding-bottom:10px;">
        <span><span style="display:inline-block;width:22px;height:3px;background:#f0a500;border-radius:2px;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#f0a500;">V3.0 전략</strong>&nbsp;20분할, 별%=(15−1.5T)%, 부분복리</span>
        <span><span style="display:inline-block;width:22px;height:2px;background:#7c9fff;vertical-align:middle;margin-right:5px;border-top:2px dotted #7c9fff;"></span>
          <strong style="color:#7c9fff;">Buy &amp; Hold</strong></span>
        <span><span style="display:inline-block;width:22px;height:0;border-top:2px dashed #f0a500;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#f0a500;">月DCA</strong>&nbsp;매월 초 균등 적립</span>
        <span style="margin-left:auto;color:#6b7280;font-size:0.75rem;align-self:center;">※ 투입원금=100 정규화</span>
      </div>
      <div id="legend-v4" class="d-flex flex-wrap gap-3 mb-3 px-1" style="display:none!important;font-size:0.82rem;color:#9aa0c0;border-bottom:1px solid #2d3154;padding-bottom:10px;">
        <span><span style="display:inline-block;width:22px;height:3px;background:#e05c5c;border-radius:2px;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#e05c5c;">V4.0 전략</strong>&nbsp;1회매수금=잔금/(분할수−T), 소진 시 리버스모드(무한매도+쿼터매수)</span>
        <span><span style="display:inline-block;width:22px;height:2px;background:#7c9fff;vertical-align:middle;margin-right:5px;border-top:2px dotted #7c9fff;"></span>
          <strong style="color:#7c9fff;">Buy &amp; Hold</strong></span>
        <span><span style="display:inline-block;width:22px;height:0;border-top:2px dashed #f0a500;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#f0a500;">月DCA</strong>&nbsp;매월 초 균등 적립</span>
        <span style="margin-left:auto;color:#6b7280;font-size:0.75rem;align-self:center;">※ 투입원금=100 정규화</span>
      </div>
      <div id="legend-vr" class="d-flex flex-wrap gap-3 mb-3 px-1" style="display:none!important;font-size:0.82rem;color:#9aa0c0;border-bottom:1px solid #2d3154;padding-bottom:10px;">
        <span><span style="display:inline-block;width:22px;height:3px;background:#9b59b6;border-radius:2px;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#9b59b6;">VR (2주 적립)</strong>&nbsp;주식 75%+풀 25%, 2주마다 입금+리밸런싱</span>
        <span><span style="display:inline-block;width:22px;height:3px;background:#e05c5c;border-radius:2px;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#e05c5c;">月VR (적립식)</strong>&nbsp;매월 균등 적립 + 2주 리밸런싱</span>
        <span><span style="display:inline-block;width:22px;height:0;border-top:2px dashed #f0a500;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#f0a500;">月DCA</strong>&nbsp;매월 초 균등 적립</span>
        <span><span style="display:inline-block;width:22px;height:2px;background:#7c9fff;vertical-align:middle;margin-right:5px;border-top:2px dotted #7c9fff;"></span>
          <strong style="color:#7c9fff;">Buy &amp; Hold</strong></span>
        <span style="margin-left:auto;color:#6b7280;font-size:0.75rem;align-self:center;">※ 투입원금=100 정규화 | stat: 투입금 대비 연환산</span>
      </div>
      <div id="legend-vr5" class="d-flex flex-wrap gap-3 mb-3 px-1" style="display:none!important;font-size:0.82rem;color:#9aa0c0;border-bottom:1px solid #2d3154;padding-bottom:10px;">
        <span><span style="display:inline-block;width:22px;height:3px;background:#17becf;border-radius:2px;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#17becf;">VR 5.0 (오피셜 공식)</strong>&nbsp;다음V=V+Pool/G+적립금, 밴드 ±15%, G=10 적립식</span>
        <span><span style="display:inline-block;width:22px;height:0;border-top:2px dashed #f0a500;vertical-align:middle;margin-right:5px;"></span>
          <strong style="color:#f0a500;">月DCA</strong>&nbsp;매월 초 균등 적립</span>
        <span><span style="display:inline-block;width:22px;height:2px;background:#7c9fff;vertical-align:middle;margin-right:5px;border-top:2px dotted #7c9fff;"></span>
          <strong style="color:#7c9fff;">Buy &amp; Hold</strong></span>
        <span style="margin-left:auto;color:#6b7280;font-size:0.75rem;align-self:center;">※ 투입원금=100 정규화 | stat: 투입금 대비 연환산</span>
      </div>

      <div id="summary-stats-container" class="summary-stats mb-3"></div>
      <div id="chart-container">
        <div class="d-flex align-items-center justify-content-center" style="height:400px;color:#6b7280;">
          &#x1F447; 위 표에서 종목을 클릭하면 자본금 곡선이 표시됩니다
        </div>
      </div>
    </div>
  </div>

  <!-- Multi-asset VR -->
  {multi_vr_section}

  <!-- Daily Actions -->
  <div class="card daily-action-card mb-4">
    <div class="card-header d-flex align-items-center gap-2">
      <span class="card-badge" style="background:#3d9970;color:#fff">매일 할 일</span>
      <span>Daily Action Guide — 주문 입력 · 체결 확인 · 업데이트</span>
    </div>
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

  <!-- ════════════════════════════════════════════════════════════════
       VR 전략 실전 가이드 (접이식)
       ════════════════════════════════════════════════════════════════ -->
  <div class="card mb-4">
    <div class="card-header d-flex justify-content-between align-items-center"
         style="cursor:pointer;user-select:none" data-bs-toggle="collapse" data-bs-target="#vr-guide-collapse">
      <div class="d-flex align-items-center gap-2">
        <span class="card-badge" style="background:#9b59b6;color:#fff">VR 가이드</span>
        <div>
          <div style="font-weight:700;color:#e0e0e0">VR (밸류리밸런싱) 전략</div>
          <div style="font-size:0.78rem;color:#6b7280">원리 · 실전 방법 · 수치 예시 · 무한매수법과 비교</div>
        </div>
      </div>
      <span style="color:#9b59b6;font-size:0.85rem;white-space:nowrap">▼ 펼치기</span>
    </div>
    <div class="collapse" id="vr-guide-collapse">
      <div class="card-body" style="font-size:0.88rem;color:#c0c4d6;line-height:1.8">

        <!-- 핵심 아이디어 -->
        <div style="background:#1e2040;border-radius:8px;padding:14px 18px;margin-bottom:20px;border-left:4px solid #9b59b6">
          <div style="font-weight:700;color:#9b59b6;font-size:1rem;margin-bottom:6px;">핵심 아이디어 한 줄 요약</div>
          <div style="color:#e0e0e0;font-size:0.95rem;">
            <strong>"2주마다 목표보다 많으면 팔아서 현금 확보, 적으면 현금으로 사서 채운다 —<br>
            그 목표를 매 2주마다 1.1%씩 자동으로 올려간다."</strong>
          </div>
        </div>

        <!-- 두 바구니 구조 -->
        <div class="row g-3 mb-4">
          <div class="col-12">
            <div style="font-weight:700;color:#7cb9ff;margin-bottom:10px;">&#x1F4B0; Step 0 — 자산을 두 바구니로 나누기 (시작 1회만)</div>
          </div>
          <div class="col-md-5">
            <div style="background:#1a3a1a;border:1px solid #2d6a2d;border-radius:8px;padding:14px;text-align:center">
              <div style="font-size:1.5rem;margin-bottom:4px;">📈</div>
              <div style="font-weight:700;color:#4caf93;font-size:1.1rem;">주식 바구니 75%</div>
              <div style="color:#9aa0c0;font-size:0.85rem;margin-top:4px;">ETF를 즉시 매수하여 보유<br>예) $10,000 중 <strong style="color:#4caf93">$7,500</strong></div>
            </div>
          </div>
          <div class="col-md-2 d-flex align-items-center justify-content-center">
            <div style="color:#6b7280;font-size:1.5rem;">⇄</div>
          </div>
          <div class="col-md-5">
            <div style="background:#1a1a3a;border:1px solid #3a3a8a;border-radius:8px;padding:14px;text-align:center">
              <div style="font-size:1.5rem;margin-bottom:4px;">💵</div>
              <div style="font-weight:700;color:#7c9fff;font-size:1.1rem;">현금 풀 25%</div>
              <div style="color:#9aa0c0;font-size:0.85rem;margin-top:4px;">언제든 사고팔 수 있는 대기 자금<br>예) $10,000 중 <strong style="color:#7c9fff">$2,500</strong></div>
            </div>
          </div>
        </div>

        <!-- V목표값 -->
        <div style="border-left:3px solid #f0a500;padding-left:14px;margin-bottom:20px;">
          <div style="font-weight:700;color:#f0a500;margin-bottom:8px;">&#x1F4C8; V목표값 (V-target) 이란?</div>
          <p class="mb-2">내 <strong>주식 바구니가 도달해야 할 목표 금액</strong>입니다. 처음에는 주식 바구니 금액과 동일하게 시작하고, 2주마다 조금씩 올라갑니다.</p>
          <div style="background:#1e2040;border-radius:6px;padding:10px 14px;font-family:monospace;font-size:0.85rem;color:#9aa0c0;margin-bottom:8px;">
            V목표(n) = V목표(n-1) × (1 + Slope × 0.001)<br>
            <span style="color:#6b7280"># Slope=11 기본값 → 2주마다 1.1% 성장</span>
          </div>
          <div style="font-size:0.82rem;color:#6b7280">
            2주 ≈ 1.1% 성장 → 연간 약 32% 상승 목표 (복리 기준)<br>
            V목표는 실제 주가와 무관하게 <strong>내가 설정한 목표 성장 곡선</strong>입니다.
          </div>
        </div>

        <!-- 2주마다 하는 3단계 -->
        <div style="font-weight:700;color:#7cb9ff;margin-bottom:12px;">&#x23F0; 2주(10 거래일)마다 하는 일 — 3단계</div>
        <div class="row g-3 mb-4">
          <div class="col-md-4">
            <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
              <div style="color:#f0a500;font-weight:700;font-size:1rem;margin-bottom:8px;">Step 1 &nbsp;💰 입금</div>
              <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:0">
                정기 적립금 <strong>$200</strong>을 현금 풀에 넣는다.<br><br>
                <span style="color:#6b7280">(선택 사항, 0원도 가능)<br>꾸준한 적립이 장기 성과를 높임</span>
              </p>
            </div>
          </div>
          <div class="col-md-4">
            <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
              <div style="color:#f0a500;font-weight:700;font-size:1rem;margin-bottom:8px;">Step 2 &nbsp;📊 V목표 갱신</div>
              <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:0">
                V목표 = 직전 V목표 × 1.011<br><br>
                <span style="color:#6b7280">자동 계산. 숫자만 업데이트</span>
              </p>
            </div>
          </div>
          <div class="col-md-4">
            <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
              <div style="color:#f0a500;font-weight:700;font-size:1rem;margin-bottom:8px;">Step 3 &nbsp;⚖️ 밴드 체크 → 매매</div>
              <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:0">
                주식 평가금과 V목표를 비교:<br>
                <span style="color:#e05c5c">• 주식 > V × 1.08 → 초과분 <strong>매도</strong></span><br>
                <span style="color:#4caf93">• 주식 &lt; V × 0.92 → 부족분 <strong>매수</strong></span><br>
                <span style="color:#6b7280">• 그 사이 → 아무것도 안 함</span>
              </p>
            </div>
          </div>
        </div>

        <!-- 수치 예시 -->
        <div style="font-weight:700;color:#7cb9ff;margin-bottom:12px;">&#x1F9EE; 수치 예시 — TQQQ $10,000 시작, Slope=11, 밴드 ±8%</div>
        <div class="table-responsive mb-3">
          <table class="table table-sm" style="font-size:0.82rem">
            <thead>
              <tr style="background:#222541">
                <th style="white-space:nowrap">시점</th>
                <th>TQQQ 주가</th>
                <th>보유 주수</th>
                <th>주식 평가금</th>
                <th>V목표</th>
                <th>밴드 범위</th>
                <th>현금 풀</th>
                <th style="min-width:200px">액션</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>시작일</strong></td>
                <td>$75</td>
                <td>100주</td>
                <td>$7,500</td>
                <td>$7,500</td>
                <td>$6,900 ~ $8,100</td>
                <td>$2,500</td>
                <td style="color:#6b7280">매수 완료 (75% 투자)</td>
              </tr>
              <tr style="background:#1e2040">
                <td><strong>2주 후</strong></td>
                <td>$78</td>
                <td>100주</td>
                <td>$7,800</td>
                <td>$7,583</td>
                <td>$6,977 ~ $8,189</td>
                <td>$2,700</td>
                <td style="color:#6b7280">① $200 입금 &nbsp;② V갱신<br>③ $7,800 ∈ 밴드 → <strong>대기</strong></td>
              </tr>
              <tr>
                <td><strong>4주 후</strong></td>
                <td>$90</td>
                <td>100주</td>
                <td><strong style="color:#e05c5c">$9,000</strong></td>
                <td>$7,666</td>
                <td>$7,053 ~ $8,279</td>
                <td>$2,900</td>
                <td style="color:#e05c5c">
                  ③ <strong>$9,000 &gt; $8,279 → 매도!</strong><br>
                  초과 = $9,000 − $7,666 = $1,334<br>
                  → $1,334 ÷ $90 = <strong>14.8주 매도</strong><br>
                  → 풀 +$1,334 → 풀 $4,234
                </td>
              </tr>
              <tr style="background:#1e2040">
                <td><strong>6주 후</strong></td>
                <td>$70</td>
                <td>85.2주</td>
                <td><strong style="color:#4caf93">$5,964</strong></td>
                <td>$7,750</td>
                <td>$7,130 ~ $8,370</td>
                <td>$4,434</td>
                <td style="color:#4caf93">
                  ③ <strong>$5,964 &lt; $7,130 → 매수!</strong><br>
                  부족 = $7,750 − $5,964 = $1,786<br>
                  → $1,786 ÷ $70 = <strong>25.5주 매수</strong><br>
                  → 풀 −$1,786 → 풀 $2,848
                </td>
              </tr>
              <tr>
                <td><strong>8주 후</strong></td>
                <td>$76</td>
                <td>110.7주</td>
                <td>$8,413</td>
                <td>$7,835</td>
                <td>$7,208 ~ $8,461</td>
                <td>$3,048</td>
                <td style="color:#6b7280">③ $8,413 ∈ 밴드 → <strong>대기</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 실전 체크리스트 -->
        <div style="font-weight:700;color:#7cb9ff;margin-bottom:10px;">&#x1F4CB; 실전 체크리스트 — 매 2주마다</div>
        <div class="row g-3 mb-3">
          <div class="col-md-6">
            <div style="background:#1a2035;border:1px solid #2d3154;border-radius:8px;padding:14px">
              <ol style="color:#9aa0c0;font-size:0.85rem;margin-bottom:0;padding-left:18px">
                <li style="margin-bottom:6px">증권사 앱에서 ETF 현재가 확인</li>
                <li style="margin-bottom:6px"><strong>주식 평가금</strong> = 보유 주수 × 현재가 계산</li>
                <li style="margin-bottom:6px"><strong>V목표</strong> = 직전 V목표 × 1.011 계산</li>
                <li style="margin-bottom:6px">현금 풀에 $200 입금</li>
                <li style="margin-bottom:6px">밴드 상단 = V목표 × 1.08 / 하단 = V목표 × 0.92 계산</li>
                <li>주식 평가금이 밴드 밖이면 LOC 주문으로 매수 or 매도</li>
              </ol>
            </div>
          </div>
          <div class="col-md-6">
            <div style="background:#1a2035;border:1px solid #2d3154;border-radius:8px;padding:14px">
              <div style="font-weight:600;color:#e0e0e0;margin-bottom:8px;">&#x1F4A1; 실전 팁</div>
              <ul style="color:#9aa0c0;font-size:0.85rem;margin-bottom:0;padding-left:18px">
                <li style="margin-bottom:5px">매매가 없는 주(대기)가 더 많습니다 — 정상입니다</li>
                <li style="margin-bottom:5px">LOC(장 마감 지정가) 주문 사용 권장</li>
                <li style="margin-bottom:5px">V목표값은 스프레드시트에 기록해두면 편합니다</li>
                <li style="margin-bottom:5px">현금 풀이 고갈되면 매수를 못 할 수 있으므로 초기 25% 유지가 중요</li>
                <li>하락장에서도 자동으로 저가 매수 → 심리적으로 규칙 준수가 핵심</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- 무한매수법과 비교 -->
        <div style="background:#1a2035;border:1px solid #3d5a99;border-radius:8px;padding:14px 18px;">
          <div style="font-weight:700;color:#7cb9ff;margin-bottom:8px;">&#x1F4CA; VR vs 무한매수법 V2.2 — 한눈에 비교</div>
          <div class="table-responsive">
            <table class="table table-sm mb-0" style="font-size:0.82rem">
              <thead><tr><th></th><th style="color:#9b59b6">VR (밸류리밸런싱)</th><th style="color:#4caf93">무한매수법 V2.2</th></tr></thead>
              <tbody>
                <tr><td>매매 주기</td><td>2주마다 1회 체크</td><td>매일 LOC 주문</td></tr>
                <tr><td>익절 시점</td><td>주식 평가금이 V목표 8% 초과 시 일부 매도</td><td>전체 수익 +10% 달성 시 전량 매도</td></tr>
                <tr><td>손절</td><td>없음 (하락 시 추가 매수)</td><td>40회 소진 시 25% 쿼터컷</td></tr>
                <tr><td>현금 관리</td><td>풀(25%)에서 자동 운용</td><td>원금 40분할 순차 집행</td></tr>
                <tr><td>하락장</td><td>자동 추가 매수 (풀 고갈 위험)</td><td>평단 낮추기 (쿼터컷 위험)</td></tr>
                <tr><td>상승장</td><td>일부 자동 이익 실현</td><td>목표 도달 시 전량 청산 → 재시작</td></tr>
                <tr><td>적합한 투자자</td><td>장기 보유, 주 1회 관리 선호</td><td>매일 주문, 사이클 완주 지향</td></tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- ════════════════════════════════════════════════════════════════
       지표 해설 (접이식)
       ════════════════════════════════════════════════════════════════ -->
  <div class="card mb-4">
    <div class="card-header d-flex justify-content-between align-items-center"
         style="cursor:pointer;user-select:none" data-bs-toggle="collapse" data-bs-target="#guide-collapse">
      <div class="d-flex align-items-center gap-2">
        <span class="card-badge" style="background:#7c9fff;color:#0f1117">지표 해설</span>
        <div>
          <div style="font-weight:700;color:#e0e0e0">연환산(CAGR) · 총수익률 · 공정 비교 방법</div>
          <div style="font-size:0.78rem;color:#6b7280">CAGR 공식 · 총수익률 의미 · 구간 비교 주의사항 · 투입금 대비 기준</div>
        </div>
      </div>
      <span style="color:#7c9fff;font-size:0.85rem;white-space:nowrap">▼ 펼치기</span>
    </div>
    <div class="collapse" id="guide-collapse">
      <div class="card-body" style="font-size:0.88rem;color:#c0c4d6;line-height:1.75">

        <!-- ① 연환산 -->
        <div class="row g-4 mb-4">
          <div class="col-md-6">
            <div style="border-left:3px solid #7c9fff;padding-left:12px;">
              <div style="font-weight:700;color:#7c9fff;margin-bottom:6px;">① 연환산 수익률 (CAGR)</div>
              <p class="mb-2">
                <strong>Compound Annual Growth Rate</strong> — 매년 평균 몇 % 복리로 성장했는지를 나타냅니다.<br>
                구간 길이가 서로 다른 결과를 <strong>1년 단위로 통일</strong>해 비교할 때 사용합니다.
              </p>
              <div style="background:#1e2040;border-radius:6px;padding:10px 14px;font-family:monospace;font-size:0.82rem;color:#9aa0c0">
                CAGR = (최종평가금 / 투입원금)<sup>1/연수</sup> − 1
              </div>
              <p class="mt-2 mb-0" style="font-size:0.82rem;color:#6b7280">
                예) 원금 $10,000 → 3년 후 $14,000<br>
                CAGR = (14,000/10,000)<sup>1/3</sup> − 1 = <strong style="color:#4caf93">11.9%</strong>
              </p>
            </div>
          </div>

          <!-- ② 총수익률 -->
          <div class="col-md-6">
            <div style="border-left:3px solid #4caf93;padding-left:12px;">
              <div style="font-weight:700;color:#4caf93;margin-bottom:6px;">② 총수익률 (Total Return)</div>
              <p class="mb-2">
                투입한 돈이 전체 기간 동안 <strong>실제로 얼마나 불었는지</strong>를 나타냅니다.<br>
                "내 계좌가 결과적으로 얼마가 됐나" — 절대 결과 확인에 사용합니다.
              </p>
              <div style="background:#1e2040;border-radius:6px;padding:10px 14px;font-family:monospace;font-size:0.82rem;color:#9aa0c0">
                총수익률 = (최종평가금 − 투입원금) / 투입원금 × 100%
              </div>
              <p class="mt-2 mb-0" style="font-size:0.82rem;color:#6b7280">
                예) $10,000 → $14,000<br>
                총수익률 = (14,000 − 10,000) / 10,000 = <strong style="color:#4caf93">+40%</strong>
              </p>
            </div>
          </div>
        </div>

        <!-- ③ 왜 연환산이 필요한가 -->
        <div style="border-left:3px solid #f0a500;padding-left:12px;margin-bottom:20px;">
          <div style="font-weight:700;color:#f0a500;margin-bottom:6px;">③ 왜 연환산이 필요한가? — 구간 길이가 다를 때</div>
          <p class="mb-2">총수익률만 보면 기간이 긴 쪽이 항상 유리해 보여 <strong>공정한 비교가 불가능</strong>합니다.</p>
          <div class="table-responsive">
            <table class="table table-sm mb-2" style="font-size:0.82rem;max-width:520px">
              <thead><tr>
                <th>구간</th><th>총수익률</th><th>연환산(CAGR)</th><th>해석</th>
              </tr></thead>
              <tbody>
                <tr><td>TQQQ 1년</td><td>+50%</td><td style="color:#4caf93"><strong>+50.0%</strong></td><td>올해가 가장 좋은 해</td></tr>
                <tr><td>TQQQ 3년</td><td>+150%</td><td>+35.6%</td><td>속도는 그 다음</td></tr>
                <tr><td>TQQQ 5년</td><td>+200%</td><td>+24.6%</td><td>총액은 크지만 속도는 느림</td></tr>
              </tbody>
            </table>
          </div>
          <p class="mb-0" style="font-size:0.82rem;color:#6b7280">
            총수익만 보면 5년이 가장 좋아 보이지만, 연환산으로 보면 1년이 가장 효율적임을 알 수 있습니다.
          </p>
        </div>

        <!-- ④ 낮은 연환산 + 높은 총수익 역설 -->
        <div style="border-left:3px solid #e05c5c;padding-left:12px;margin-bottom:20px;">
          <div style="font-weight:700;color:#e05c5c;margin-bottom:6px;">④ 역설 — 연환산이 낮은데 총수익이 더 높을 수 있다?</div>
          <p class="mb-2">
            <strong>full(전체) 구간</strong>은 종목마다 시작일이 다릅니다.<br>
            QQQ(1999년 상장, ~26년) vs VOO(2010년 상장, ~16년)처럼 기간이 다르면 이런 역설이 발생합니다.
          </p>
          <div class="table-responsive">
            <table class="table table-sm mb-2" style="font-size:0.82rem;max-width:600px">
              <thead><tr>
                <th>전략/종목</th><th>연환산</th><th>기간</th><th>계산</th><th>총수익</th>
              </tr></thead>
              <tbody>
                <tr>
                  <td>QQQ V3.0</td>
                  <td>4.5%</td>
                  <td>26년</td>
                  <td style="font-family:monospace;font-size:0.78rem">(1.045)²⁶ − 1</td>
                  <td style="color:#4caf93"><strong>+213%</strong></td>
                </tr>
                <tr>
                  <td>VOO V2.2</td>
                  <td>6.2%</td>
                  <td>16년</td>
                  <td style="font-family:monospace;font-size:0.78rem">(1.062)¹⁶ − 1</td>
                  <td style="color:#9aa0c0">+163%</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="mb-0" style="font-size:0.82rem;">
            <span style="color:#e05c5c">⚠️</span>
            <strong>결론: full 구간의 총수익률은 종목끼리 비교하면 안 됩니다.</strong><br>
            <span style="color:#6b7280">서로 다른 시작일 때문에 기간 자체가 달라 총수익 크기 비교가 무의미합니다.<br>
            공정한 비교는 반드시 <strong style="color:#7c9fff">같은 구간(3yr, 5yr 등)에서 연환산(CAGR)으로</strong> 해야 합니다.</span>
          </p>
        </div>

        <!-- ⑤ 투입금 대비 -->
        <div style="border-left:3px solid #9b59b6;padding-left:12px;margin-bottom:20px;">
          <div style="font-weight:700;color:#9b59b6;margin-bottom:6px;">⑤ 투입금 대비 연환산 (cagr_on_invested) — 이 대시보드의 기준</div>
          <p class="mb-2">
            VR·月DCA처럼 <strong>돈을 여러 번 나눠 투입하는 전략</strong>은 총 투입금이 다릅니다.<br>
            공정한 비교를 위해 <strong>최종 평가금 ÷ 총 투입금</strong> 기준으로 연환산을 계산합니다.
          </p>
          <div class="table-responsive">
            <table class="table table-sm mb-2" style="font-size:0.82rem;max-width:640px">
              <thead><tr><th>전략</th><th>투입 방식</th><th>총 투입금</th><th>CAGR 기준</th></tr></thead>
              <tbody>
                <tr><td>BaH / V2.2 / V3.0</td><td>첫날 전액</td><td>원금 = $10,000</td><td>최종 ÷ $10,000</td></tr>
                <tr><td>月DCA</td><td>매월 균등 분할</td><td>합계 = $10,000</td><td>최종 ÷ $10,000</td></tr>
                <tr><td>VR (2주 적립)</td><td>초기 + 2주마다 $200</td><td>$10,000 + 적립 합계</td><td>최종 ÷ 총투입금</td></tr>
              </tbody>
            </table>
          </div>
          <p class="mb-0" style="font-size:0.82rem;color:#6b7280">
            ※ 月DCA의 경우 돈이 늦게 투입될수록 복리 기간이 짧아 실제 IRR은 표시값보다 높을 수 있습니다.<br>
            정확한 비교는 IRR(내부수익률)이 필요하지만, 이 대시보드는 직관적인 <strong>총투입금 대비 연환산</strong>을 사용합니다.
          </p>
        </div>

        <!-- ⑥ 올바른 비교 방법 요약 -->
        <div style="background:#1a2035;border:1px solid #3d5a99;border-radius:8px;padding:14px 18px;margin-bottom:24px;">
          <div style="font-weight:700;color:#7cb9ff;margin-bottom:8px;">&#x2705; 올바른 비교 방법 요약</div>
          <ul class="mb-0" style="color:#9aa0c0;padding-left:18px;">
            <li><strong style="color:#e0e0e0">같은 구간 탭</strong>에서 비교하세요 — 3yr끼리, 5yr끼리</li>
            <li><strong style="color:#e0e0e0">연환산(CAGR)</strong>으로 "속도"를 비교하고, <strong style="color:#e0e0e0">총수익률</strong>로 "절대 크기"를 확인하세요</li>
            <li><strong style="color:#e0e0e0">full 구간</strong>은 종목마다 시작일이 달라 <strong style="color:#e05c5c">총수익률 직접 비교는 무의미</strong>합니다 — 연환산만 비교하세요</li>
            <li>VR처럼 <strong style="color:#e0e0e0">추가 납입이 있는 전략</strong>은 총 투입금 기준 CAGR로 표시되어 있습니다</li>
          </ul>
        </div>

        <!-- ⑦ 테이블 컬럼 해설 -->
        <div style="border-top:1px solid #2d3154;padding-top:20px;">
          <div style="font-weight:700;color:#7cb9ff;font-size:1rem;margin-bottom:14px;">&#x1F4CB; 테이블 컬럼 해설 — 숫자만 봐도 바로 알 수 있게</div>
          <div class="row g-3">

            <!-- B&H -->
            <div class="col-md-6">
              <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
                <div style="font-weight:700;color:#7c9fff;margin-bottom:6px;">📌 B&H (Buy &amp; Hold, 그냥 사서 보유)</div>
                <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:8px;">
                  "아무 전략 없이 첫날 전액 매수해서 끝까지 보유하면 얼마?" 기준값입니다.<br>
                  내 전략이 이 숫자보다 <strong style="color:#4caf93">높으면 전략이 효과적</strong>, 낮으면 그냥 들고 있는 게 나았다는 뜻입니다.
                </p>
                <div style="background:#131628;border-radius:6px;padding:8px 12px;font-size:0.82rem">
                  <div style="color:#6b7280;margin-bottom:4px;">수치 해석 예시</div>
                  <div><span style="color:#4caf93">B&H 연환산 21%</span> → "가만히 뒀어도 연 21% 성장"</div>
                  <div><span style="color:#9aa0c0">B&H 총수익 +303%</span> → "3배 이상이 됨"</div>
                  <div style="margin-top:4px;color:#f0a500">⚠ 내 전략 연환산이 B&H보다 낮다면 전략이 오히려 방해가 된 것</div>
                </div>
              </div>
            </div>

            <!-- 연환산/총수익 -->
            <div class="col-md-6">
              <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
                <div style="font-weight:700;color:#4caf93;margin-bottom:6px;">📈 연환산↗ / 총수익 (두 줄로 표시)</div>
                <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:8px;">
                  <strong style="color:#e0e0e0">윗줄 연환산</strong>: 매년 평균 몇 %씩 복리로 성장했나 → 구간 비교용<br>
                  <strong style="color:#6b7280">아랫줄 총수익</strong>: 실제 내 돈이 얼마나 불었나 → 절대 크기 확인용
                </p>
                <div style="background:#131628;border-radius:6px;padding:8px 12px;font-size:0.82rem">
                  <div style="color:#6b7280;margin-bottom:4px;">수치 해석 예시</div>
                  <div><span style="color:#4caf93">18.1%</span> / <span style="color:#6b7280">총 +70.4%</span></div>
                  <div style="color:#9aa0c0">→ "3년간 매년 평균 18.1% 성장, 원금이 1.7배"</div>
                  <div style="margin-top:4px"><span style="color:#e05c5c">-44.2%</span> / <span style="color:#6b7280">총 -44.3%</span></div>
                  <div style="color:#9aa0c0">→ "1년 구간에서 거의 반토막"</div>
                </div>
              </div>
            </div>

            <!-- MDD -->
            <div class="col-md-6">
              <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
                <div style="font-weight:700;color:#e05c5c;margin-bottom:6px;">📉 MDD (최대낙폭, Maximum DrawDown)</div>
                <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:8px;">
                  전체 기간 중 <strong>가장 높았던 순간에서 가장 낮은 순간까지 얼마나 떨어졌는지</strong>입니다.<br>
                  "내가 최악의 타이밍에 샀다면 얼마나 손해를 봤을까?" — 심리적 버티기의 기준입니다.
                </p>
                <div style="background:#131628;border-radius:6px;padding:8px 12px;font-size:0.82rem">
                  <div style="color:#6b7280;margin-bottom:6px;">수치 해석</div>
                  <div class="d-flex flex-column gap-1">
                    <div><span style="background:#1a3a1a;color:#4caf93;padding:2px 8px;border-radius:4px;font-size:0.8rem">0% ~ -10%</span> <span style="color:#9aa0c0;margin-left:6px">안전 — 거의 손실 없음</span></div>
                    <div><span style="background:#3a2a00;color:#f0a500;padding:2px 8px;border-radius:4px;font-size:0.8rem">-10% ~ -30%</span> <span style="color:#9aa0c0;margin-left:6px">보통 — 감내 가능한 수준</span></div>
                    <div><span style="background:#3a1a1a;color:#e05c5c;padding:2px 8px;border-radius:4px;font-size:0.8rem">-30% 이상</span> <span style="color:#9aa0c0;margin-left:6px">위험 — 심리적으로 버티기 어려움</span></div>
                  </div>
                  <div style="margin-top:8px;color:#6b7280">예) MDD -82% → "최고점에서 5분의 1 토막"</div>
                </div>
              </div>
            </div>

            <!-- Sharpe -->
            <div class="col-md-6">
              <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
                <div style="font-weight:700;color:#f0a500;margin-bottom:6px;">⚡ Sharpe (샤프 지수, 위험 대비 수익)</div>
                <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:8px;">
                  "같은 수익이라면 덜 흔들린 전략이 더 좋다"는 기준입니다.<br>
                  <strong>수익률 ÷ 변동성</strong>으로 계산 — 숫자가 클수록 안정적으로 수익을 냈다는 뜻입니다.
                </p>
                <div style="background:#131628;border-radius:6px;padding:8px 12px;font-size:0.82rem">
                  <div style="color:#6b7280;margin-bottom:6px;">수치 해석</div>
                  <div class="d-flex flex-column gap-1">
                    <div><span style="background:#1a3a1a;color:#4caf93;padding:2px 8px;border-radius:4px;font-size:0.8rem">1.0 이상</span> <span style="color:#9aa0c0;margin-left:6px">좋음 — 안정적 수익</span></div>
                    <div><span style="background:#3a2a00;color:#f0a500;padding:2px 8px;border-radius:4px;font-size:0.8rem">0.5 ~ 1.0</span> <span style="color:#9aa0c0;margin-left:6px">보통</span></div>
                    <div><span style="background:#3a1a1a;color:#e05c5c;padding:2px 8px;border-radius:4px;font-size:0.8rem">0 이하</span> <span style="color:#9aa0c0;margin-left:6px">나쁨 — 위험 감수 대비 수익 없음</span></div>
                  </div>
                  <div style="margin-top:8px;color:#6b7280">예) Sharpe 0.82 → "위험 1만큼 감수해서 수익 0.82 획득"</div>
                </div>
              </div>
            </div>

            <!-- 사이클 -->
            <div class="col-md-6">
              <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
                <div style="font-weight:700;color:#f0a500;margin-bottom:6px;">🔄 사이클 (목표 달성 후 재시작 횟수)</div>
                <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:8px;">
                  무한매수법에서 목표 수익(예: +10%)을 달성하고 <strong>전량 매도 → 새 사이클 시작</strong>한 횟수입니다.<br>
                  많을수록 수익 실현이 자주 일어났다는 뜻입니다.
                </p>
                <div style="background:#131628;border-radius:6px;padding:8px 12px;font-size:0.82rem">
                  <div style="color:#6b7280;margin-bottom:4px;">수치 해석 예시</div>
                  <div style="color:#9aa0c0">사이클 <span style="color:#f0a500">0</span> → 한 번도 목표 달성 못함 (하락장 내내 버팀)</div>
                  <div style="color:#9aa0c0">사이클 <span style="color:#f0a500">5</span> → 3년간 5번 +10% 달성 후 재시작</div>
                  <div style="color:#9aa0c0">사이클 <span style="color:#f0a500">15</span> → 자주 익절, 활발히 운용됨</div>
                  <div style="margin-top:6px;color:#6b7280">※ VR 전략은 사이클 개념이 없어 항상 0</div>
                </div>
              </div>
            </div>

            <!-- 쿼터컷 -->
            <div class="col-md-6">
              <div style="background:#1e2040;border-radius:8px;padding:14px;height:100%">
                <div style="font-weight:700;color:#e05c5c;margin-bottom:6px;">✂️ 쿼터컷 (강제 25% 손절 횟수)</div>
                <p style="color:#9aa0c0;font-size:0.85rem;margin-bottom:8px;">
                  40번 분할 매수를 모두 써도 목표 수익에 못 미칠 때 <strong>보유량의 25%를 강제로 손절</strong>한 횟수입니다.<br>
                  <strong style="color:#e05c5c">적을수록 좋습니다.</strong> 0이면 한 번도 손절 없이 운용된 것입니다.
                </p>
                <div style="background:#131628;border-radius:6px;padding:8px 12px;font-size:0.82rem">
                  <div style="color:#6b7280;margin-bottom:4px;">수치 해석 예시</div>
                  <div style="color:#9aa0c0">쿼터컷 <span style="color:#4caf93">0</span> → 손절 없음, 이상적</div>
                  <div style="color:#9aa0c0">쿼터컷 <span style="color:#f0a500">2</span> → 2번 강제 손절 → 하락장이 길었음</div>
                  <div style="color:#9aa0c0">쿼터컷 <span style="color:#e05c5c">5↑</span> → 잦은 손절 → 전략·종목 재검토 필요</div>
                  <div style="margin-top:6px;color:#6b7280">
                    ※ 쿼터컷은 손실이지만 더 큰 손실을 막기 위한 "안전장치"입니다<br>
                    쿼터컷 후에는 원금의 75%로 새 사이클을 시작합니다
                  </div>
                </div>
              </div>
            </div>

          </div><!-- /row -->
        </div><!-- /테이블 컬럼 해설 -->

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
// Strategy selector
// ============================================================
let selectedStrategy = 'v22';
let lastTicker = null;
let lastPeriod = null;

const STRATEGIES = ['v22','v30','v4','vr','vr5'];

function selectStrategy(name) {{
  selectedStrategy = name;
  // Update button states
  STRATEGIES.forEach(s => {{
    const btn = document.getElementById('btn-strat-' + s);
    if (!btn) return;
    btn.classList.remove('active','btn-success','btn-warning','btn-danger','btn-info','btn-primary',
                         'btn-outline-success','btn-outline-warning','btn-outline-danger','btn-outline-info','btn-outline-primary');
  }});
  const colors = {{v22:'success', v30:'warning', v4:'danger', vr:'info', vr5:'primary'}};
  STRATEGIES.forEach(s => {{
    const btn = document.getElementById('btn-strat-' + s);
    if (!btn) return;
    if (s === name) {{
      btn.classList.add('btn-' + colors[s], 'active');
    }} else {{
      btn.classList.add('btn-outline-' + colors[s]);
    }}
  }});
  // Update legend visibility
  STRATEGIES.forEach(s => {{
    const el = document.getElementById('legend-' + s);
    if (el) el.style.display = s === name ? '' : 'none';
  }});
  // Redraw if ticker already selected
  if (lastTicker && lastPeriod) drawChart(lastTicker, lastPeriod);
}}

// ============================================================
// Table row click → draw chart
// ============================================================
let selectedRow = null;

document.querySelectorAll('tr[data-ticker]').forEach(row => {{
  row.addEventListener('click', function() {{
    const ticker = this.dataset.ticker;
    const period = this.dataset.period;
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
  lastTicker = ticker;
  lastPeriod = period;

  const cfg = TICKER_CONFIG[ticker] || {{}};
  const levLabel = cfg.leverage ? `${{cfg.leverage}}x` : '';
  const mktLabel = cfg.market === 'KR' ? '🇰🇷' : '🇺🇸';
  document.getElementById('chart-ticker-code').textContent = ticker;
  document.getElementById('chart-ticker-name').textContent =
    (cfg.name || '') + (levLabel ? '  ·  ' + levLabel : '') + '  ' + mktLabel;
  document.getElementById('chart-period-badge').textContent =
    PERIOD_LABELS[period] || period;

  const dates = res.dates || [];
  const principal = res.principal || 10000;
  const norm = arr => arr.map(v => v / principal * 100);
  const chartTitle = `${{ticker}}  ${{cfg.name || ''}}  ·  ${{PERIOD_LABELS[period] || period}}`;

  const baseLayout = {{
    paper_bgcolor: '#1a1d2e', plot_bgcolor: '#1a1d2e',
    font: {{ color: '#9aa0c0', size: 11 }},
    title: {{ text: chartTitle, font: {{ color: '#e0e0e0', size: 13 }}, x: 0.01, xanchor: 'left' }},
    xaxis: {{ gridcolor: '#2d3154', showgrid: true }},
    yaxis: {{ gridcolor: '#2d3154', showgrid: true, title: '평가금 (투입원금=100)' }},
    legend: {{ orientation: 'h', y: 1.14, font: {{ size: 11 }} }},
    margin: {{ t: 65, b: 40, l: 65, r: 20 }},
    hovermode: 'x unified',
    shapes: [{{ type:'line', xref:'paper', x0:0, x1:1, y0:100, y1:100,
                line: {{ color:'#4d5166', width:1, dash:'dot' }} }}],
  }};

  // 월DCA는 모든 전략 뷰에서 공통 벤치마크로 표시
  const mdca = res.monthly_dca || {{}};
  const traceMdca = {{ x: dates, y: norm(mdca.equity||[]),
    name:'月DCA (적립식)', line:{{ color:'#f0a500', width:1.3, dash:'dash' }} }};
  const traceBah  = {{ x: dates, y: norm(res.equity_bah||[]),
    name:'Buy & Hold', line:{{ color:'#7c9fff', width:1.3, dash:'dot' }} }};

  let traces = [];
  let statsHtml = '';

  if (selectedStrategy === 'v22') {{
    const ms = res.metrics_strategy || {{}};
    const mm = mdca.metrics || {{}};
    traces = [
      {{ x: dates, y: norm(res.equity_strategy||[]), name:'V2.2 전략', line:{{ color:'#4caf93', width:2 }} }},
      traceBah, traceMdca,
    ];
    statsHtml = `
      ${{statBox('V2.2 연환산', pct(ms.cagr_on_invested), ms.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(ms.roi_on_invested))}}
      ${{statBox('B&H 연환산', pct((res.metrics_bah||{{}}).cagr_on_invested), (res.metrics_bah||{{}}).cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct((res.metrics_bah||{{}}).roi_on_invested))}}
      ${{statBox('月DCA 연환산', pct(mm.cagr_on_invested), mm.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(mm.roi_on_invested))}}
      ${{statBox('V2.2 MDD', pct(ms.mdd), ms.mdd<-0.3?'cagr-neg':'mdd-ok')}}
      ${{statBox('Sharpe', (ms.sharpe||0).toFixed(2))}}
      ${{statBox('사이클', res.final_cycles||0, '', '#f0a500')}}`;

  }} else if (selectedStrategy === 'v30') {{
    const v30 = res.v30 || {{}};
    const ms = v30.metrics || {{}};
    const ms22 = res.metrics_strategy || {{}};
    traces = [
      {{ x: dates, y: norm(v30.equity||[]), name:'V3.0 전략', line:{{ color:'#f0a500', width:2 }} }},
      {{ x: dates, y: norm(res.equity_strategy||[]), name:'V2.2 참고', line:{{ color:'#4caf93', width:1.2, dash:'dash' }} }},
      traceBah, traceMdca,
    ];
    statsHtml = `
      ${{statBox('V3.0 연환산', pct(ms.cagr_on_invested), ms.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(ms.roi_on_invested))}}
      ${{statBox('V2.2 연환산', pct(ms22.cagr_on_invested), ms22.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(ms22.roi_on_invested))}}
      ${{statBox('B&H 연환산', pct((res.metrics_bah||{{}}).cagr_on_invested), (res.metrics_bah||{{}}).cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct((res.metrics_bah||{{}}).roi_on_invested))}}
      ${{statBox('V3.0 MDD', pct(ms.mdd), ms.mdd<-0.3?'cagr-neg':'mdd-ok')}}
      ${{statBox('사이클', v30.final_cycles||0, '', '#f0a500')}}
      ${{statBox('쿼터컷', v30.final_quarter_cuts||0, '', '#e05c5c')}}`;

  }} else if (selectedStrategy === 'v4') {{
    const v4  = res.v4 || {{}};
    const ms  = v4.metrics || {{}};
    const ms30 = (res.v30 || {{}}).metrics || {{}};
    traces = [
      {{ x: dates, y: norm(v4.equity||[]), name:'V4.0 전략', line:{{ color:'#e05c5c', width:2 }} }},
      {{ x: dates, y: norm((res.v30||{{}}).equity||[]), name:'V3.0 참고', line:{{ color:'#f0a500', width:1.2, dash:'dash' }} }},
      traceBah, traceMdca,
    ];
    statsHtml = `
      ${{statBox('V4.0 연환산', pct(ms.cagr_on_invested), ms.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(ms.roi_on_invested))}}
      ${{statBox('V3.0 연환산', pct(ms30.cagr_on_invested), ms30.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(ms30.roi_on_invested))}}
      ${{statBox('B&H 연환산', pct((res.metrics_bah||{{}}).cagr_on_invested), (res.metrics_bah||{{}}).cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct((res.metrics_bah||{{}}).roi_on_invested))}}
      ${{statBox('V4.0 MDD', pct(ms.mdd), ms.mdd<-0.3?'cagr-neg':'mdd-ok')}}
      ${{statBox('사이클', v4.final_cycles||0, '', '#e05c5c')}}
      ${{statBox('쿼터매도', v4.final_quarter_cuts||0, '', '#f0a500')}}`;

  }} else if (selectedStrategy === 'vr') {{
    const vr   = res.vr || {{}};
    const mvr  = res.monthly_vr || {{}};
    const ms   = vr.metrics || {{}};
    const msm  = mvr.metrics || {{}};
    const mmdca = mdca.metrics || {{}};
    traces = [
      {{ x: dates, y: norm(vr.equity||[]),   name:'VR (2주 적립)', line:{{ color:'#9b59b6', width:2 }} }},
      {{ x: dates, y: norm(mvr.equity||[]),  name:'月VR (적립식)', line:{{ color:'#e05c5c', width:2 }} }},
      traceMdca, traceBah,
    ];
    statsHtml = `
      ${{statBox('VR 연환산', pct(ms.cagr_on_invested), ms.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(ms.roi_on_invested))}}
      ${{statBox('月VR 연환산', pct(msm.cagr_on_invested), msm.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(msm.roi_on_invested))}}
      ${{statBox('月DCA 연환산', pct(mmdca.cagr_on_invested), mmdca.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(mmdca.roi_on_invested))}}
      ${{statBox('B&H 연환산', pct((res.metrics_bah||{{}}).cagr_on_invested), (res.metrics_bah||{{}}).cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct((res.metrics_bah||{{}}).roi_on_invested))}}
      ${{statBox('VR MDD', pct(ms.mdd), ms.mdd<-0.3?'cagr-neg':'mdd-ok')}}
      ${{statBox('月VR MDD', pct(msm.mdd), msm.mdd<-0.3?'cagr-neg':'mdd-ok')}}`;

  }} else if (selectedStrategy === 'vr5') {{
    const vr5 = res.vr5 || {{}};
    const ms  = vr5.metrics || {{}};
    const mm  = mdca.metrics || {{}};
    traces = [
      {{ x: dates, y: norm(vr5.equity||[]), name:'VR 5.0 (오피셜)', line:{{ color:'#17becf', width:2 }} }},
      traceMdca, traceBah,
    ];
    statsHtml = `
      ${{statBox('VR5.0 연환산', pct(ms.cagr_on_invested), ms.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(ms.roi_on_invested))}}
      ${{statBox('月DCA 연환산', pct(mm.cagr_on_invested), mm.cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct(mm.roi_on_invested))}}
      ${{statBox('B&H 연환산', pct((res.metrics_bah||{{}}).cagr_on_invested), (res.metrics_bah||{{}}).cagr_on_invested>=0?'cagr-pos':'cagr-neg', '', pct((res.metrics_bah||{{}}).roi_on_invested))}}
      ${{statBox('VR5.0 MDD', pct(ms.mdd), ms.mdd<-0.3?'cagr-neg':'mdd-ok')}}
      ${{statBox('Sharpe', (ms.sharpe||0).toFixed(2))}}
      ${{statBox('G값', vr5.g||10, '', '#17becf')}}`;
  }}

  Plotly.newPlot('chart-container', traces, baseLayout, {{responsive: true}});

  const container = document.getElementById('summary-stats-container');
  container.style.display = 'flex';
  container.innerHTML = statsHtml;
}}

function statBox(label, value, cls='', color='', subValue='') {{
  const sub = subValue ? `<div style="font-size:0.72rem;color:#6b7280;margin-top:1px;">총 ${{subValue}}</div>` : '';
  return `<div class="stat-box">
    <div class="stat-label">${{label}}</div>
    <div class="stat-value ${{cls}}" style="${{color ? 'color:'+color : ''}}">${{value}}</div>
    ${{sub}}
  </div>`;
}}

function pct(v) {{
  if (v === undefined || v === null || isNaN(v)) return 'N/A';
  return (v * 100).toFixed(1) + '%';
}}

// ============================================================
// Multi-asset VR chart
// ============================================================
const MVR_COLORS = {{
  'QQQ100':          '#7c9fff',
  'VOO100':          '#4caf93',
  'GLD100':          '#e5d261',
  'QQQ30_VOO40_GLD30': '#e07a5f',
  'QQQ50_VOO50':     '#81b29a',
  'QQQ50_GLD50':     '#f2cc8f',
  'VOO50_GLD50':     '#b4a7d6',
}};

function normTo100(arr) {{
  if (!arr || !arr.length) return [];
  const base = arr[0] || 1;
  return arr.map(v => v / base * 100);
}}

function drawMvrChart(period) {{
  const el = document.getElementById('mvr-chart-container');
  if (!el) return;
  const mvrData = RESULTS['_multi_vr'] || {{}};
  const traces = [];
  for (const [pid, pdata] of Object.entries(mvrData)) {{
    const pr = pdata[period];
    if (!pr || pr.skip || !pr.equity || !pr.equity.length) continue;
    traces.push({{
      x: pr.dates,
      y: normTo100(pr.equity),
      name: pdata.name,
      type: 'scatter',
      mode: 'lines',
      line: {{ color: MVR_COLORS[pid] || '#9aa0c0', width: 2 }},
    }});
  }}
  if (!traces.length) {{
    el.innerHTML = '<div class="d-flex align-items-center justify-content-center" style="height:450px;color:#6b7280;">선택 구간에 데이터가 없습니다</div>';
    return;
  }}
  const layout = {{
    paper_bgcolor: '#1a1d2e', plot_bgcolor: '#1a1d2e',
    font: {{ color: '#9aa0c0', size: 11 }},
    xaxis: {{ gridcolor: '#2d3154', showgrid: true }},
    yaxis: {{ gridcolor: '#2d3154', showgrid: true, title: '평가금 (투입원금=100)' }},
    legend: {{ orientation: 'h', y: 1.14, font: {{ size: 11 }} }},
    margin: {{ t: 65, b: 40, l: 65, r: 20 }},
    hovermode: 'x unified',
    shapes: [{{ type:'line', xref:'paper', x0:0, x1:1, y0:100, y1:100,
                line: {{ color:'#4d5166', width:1, dash:'dot' }} }}],
  }};
  Plotly.newPlot('mvr-chart-container', traces, layout, {{ responsive: true }});
}}

// Activate first tab's first row on load
window.addEventListener('load', () => {{
  selectStrategy('v22');
  const firstRow = document.querySelector('tr[data-ticker]');
  if (firstRow) firstRow.click();
  // Draw MVR chart for the initially active period tab
  const activeBtn = document.querySelector('#mvrTabs .nav-link.active');
  if (activeBtn) drawMvrChart(activeBtn.getAttribute('data-period'));
}});

// Redraw MVR chart on period tab switch
document.addEventListener('shown.bs.tab', function(e) {{
  const period = e.target.getAttribute('data-period');
  if (period && e.target.closest('#mvrTabs')) drawMvrChart(period);
}});

// Redraw when collapse section opens (chart is hidden before first open)
(function() {{
  const colEl = document.getElementById('multi-vr-collapse');
  if (colEl) colEl.addEventListener('shown.bs.collapse', function() {{
    const btn = document.querySelector('#mvrTabs .nav-link.active');
    if (btn) drawMvrChart(btn.getAttribute('data-period'));
  }});
}})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Multi-asset VR section
# ---------------------------------------------------------------------------

def _build_multi_vr_section(results: dict, active_periods: list[str]) -> str:
    """Build the multi-asset VR portfolio comparison card."""
    multi_vr = results.get("_multi_vr", {})
    if not multi_vr:
        return ""

    from lastofus.config import MULTI_VR_CONFIGS, get_period_labels
    period_labels = get_period_labels()

    # ── Period tab buttons (data-period attr used by JS drawMvrChart) ──────
    tab_btns = "\n".join(
        f'<button class="nav-link {"active" if i == 0 else ""}" '
        f'id="mvr-tab-{p}" data-bs-toggle="tab" data-bs-target="#mvr-pane-{p}" '
        f'data-period="{p}" type="button" role="tab">{period_labels.get(p, p)}</button>'
        for i, p in enumerate(active_periods)
    )

    # ── Per-period panes ───────────────────────────────────────────────────
    panes = []
    # colors: single-asset (grey tones), blended portfolios (vivid)
    portfolio_colors = {
        "QQQ100": "#7c9fff",
        "VOO100": "#4caf93",
        "GLD100": "#e5d261",
        "QQQ30_VOO40_GLD30": "#e07a5f",
        "QQQ50_VOO50":       "#81b29a",
        "QQQ50_GLD50":       "#f2cc8f",
        "VOO50_GLD50":       "#b4a7d6",
    }

    for pi, period in enumerate(active_periods):
        active_class = "show active" if pi == 0 else ""
        label = period_labels.get(period, period)

        rows = []
        prev_is_single = None
        for ci_idx, cfg in enumerate(MULTI_VR_CONFIGS):
            pid = cfg["id"]
            pdata = multi_vr.get(pid, {})
            pr = pdata.get(period, {})
            color = portfolio_colors.get(pid, "#9aa0c0")
            is_single = len(cfg["weights"]) == 1
            weights_str = " + ".join(
                f"{t} {int(w*100)}%" for t, w in cfg["weights"].items()
            )

            # Section header row between single and blended
            if prev_is_single is not None and is_single != prev_is_single:
                rows.append(
                    '<tr><td colspan="6" style="background:#1e2040;color:#e5d261;'
                    'font-size:0.75rem;font-weight:700;padding:4px 10px;letter-spacing:0.05em">'
                    '혼합 포트폴리오 (자산 간 리밸런싱)</td></tr>'
                )
            elif ci_idx == 0:
                rows.append(
                    '<tr><td colspan="6" style="background:#1e2040;color:#9aa0c0;'
                    'font-size:0.75rem;font-weight:700;padding:4px 10px;letter-spacing:0.05em">'
                    '단일 종목 VR (비교 기준)</td></tr>'
                )
            prev_is_single = is_single

            if pr.get("skip") or not pr.get("metrics"):
                rows.append(
                    f'<tr><td style="color:{color};font-weight:600">{cfg["name"]}</td>'
                    f'<td style="color:#6b7280;font-size:0.8rem">{weights_str}</td>'
                    f'<td colspan="5" class="text-muted text-center small">데이터 없음: {pr.get("reason","")}</td></tr>'
                )
                continue

            m = pr["metrics"]
            cagr_inv = m.get("cagr_on_invested", m.get("cagr", 0))
            roi_inv  = m.get("roi_on_invested", m.get("total_return", 0))
            mdd      = m.get("mdd", 0)
            sharpe   = m.get("sharpe", 0)
            n_bars   = pr.get("n_bars", 0)

            def pct(v): return f"{v*100:.1f}%"
            def cc(v):  return "cagr-pos" if v > 0 else ("cagr-neg" if v < 0 else "cagr-zero")
            mdd_cl = "mdd-bad" if mdd < -0.30 else "mdd-ok"

            rows.append(
                f'<tr>'
                f'<td style="color:{color};font-weight:600;white-space:nowrap">{cfg["name"]}</td>'
                f'<td style="color:#6b7280;font-size:0.78rem">{weights_str}</td>'
                f'<td class="metric-cell"><span class="{cc(cagr_inv)}">{pct(cagr_inv)}</span>'
                f'<br><small style="color:#6b7280">총 {pct(roi_inv)}</small></td>'
                f'<td class="metric-cell {mdd_cl}">{pct(mdd)}</td>'
                f'<td class="metric-cell">{sharpe:.2f}</td>'
                f'<td class="metric-cell" style="color:#6b7280;font-size:0.78rem">{n_bars}일</td>'
                f'</tr>'
            )

        rows_html = "\n".join(rows)

        # Equity chart data for this period (all portfolios)
        chart_data_items = []
        for ci_idx, cfg in enumerate(MULTI_VR_CONFIGS):
            pid = cfg["id"]
            pdata = multi_vr.get(pid, {})
            pr = pdata.get(period, {})
            if pr.get("skip") or not pr.get("equity"):
                continue
            eq = pr["equity"]
            dates = pr["dates"]
            color = portfolio_colors.get(pid, "#9aa0c0")
            base = eq[0] if eq[0] else 1
            norm_eq = [100.0 * v / base for v in eq]
            eq_json = json.dumps(norm_eq)
            dates_json = json.dumps(dates)
            pname = cfg["name"]
            chart_data_items.append(
                f'{{x:{dates_json},y:{eq_json},'
                f'name:"{pname}",type:"scatter",mode:"lines",'
                f'line:{{color:"{color}",width:2}}}}'
            )

        chart_id = f"mvr-chart-{period}"
        if chart_data_items:
            chart_traces = ",\n".join(chart_data_items)
            chart_js = f"""
<script>
(function(){{
  var el = document.getElementById('{chart_id}');
  if (!el) return;
  var traces = [{chart_traces}];
  var layout = {{
    paper_bgcolor:'#1a1d2e', plot_bgcolor:'#1a1d2e',
    font:{{color:'#9aa0c0',size:11}},
    xaxis:{{gridcolor:'#2d3154',showgrid:true}},
    yaxis:{{gridcolor:'#2d3154',showgrid:true,title:'평가금 (투입원금=100)'}},
    legend:{{orientation:'h',y:1.06,font:{{size:11}}}},
    margin:{{l:65,r:20,t:50,b:40}},
    hovermode:'x unified',
    autosize:true,
    shapes:[{{type:'line',xref:'paper',x0:0,x1:1,y0:100,y1:100,
              line:{{color:'#4d5166',width:1,dash:'dot'}}}}],
  }};
  Plotly.newPlot(el, traces, layout, {{responsive:true, displayModeBar:false}});
  window.addEventListener('resize', function(){{ Plotly.relayout(el, {{autosize:true}}); }});
}})();
</script>"""
        panes.append(f"""
<div class="tab-pane fade {active_class}" id="mvr-pane-{period}" role="tabpanel">
  <div class="table-responsive" style="border-bottom:1px solid #2d3154;">
    <table class="table table-hover mb-0">
      <thead>
        <tr>
          <th style="min-width:220px;position:sticky;top:0;z-index:1;background:#222541;">포트폴리오</th>
          <th style="min-width:200px;color:#6b7280;font-weight:normal;font-size:0.78rem;position:sticky;top:0;z-index:1;background:#222541;">구성 비중</th>
          <th class="metric-cell" style="position:sticky;top:0;z-index:1;background:#222541;">연환산 / 총수익<br><small style="font-weight:normal;color:#6b7280">투입금 대비</small></th>
          <th class="metric-cell" style="position:sticky;top:0;z-index:1;background:#222541;">MDD</th>
          <th class="metric-cell" style="position:sticky;top:0;z-index:1;background:#222541;">Sharpe</th>
          <th class="metric-cell" style="color:#6b7280;font-weight:normal;position:sticky;top:0;z-index:1;background:#222541;">거래일수</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <div class="pt-1 pb-0 text-muted" style="font-size:0.75rem;padding-left:4px;">구간: {label} | Slope G=11 / 밴드 ±8% / 초기 주식 75%+풀 25% / 2주 사이클 | US $10,000 일시납 (추가 납입 없음)</div>
</div>""")

    panes_html = "\n".join(panes)

    return f"""
<div class="card mb-4">
  <div class="card-header d-flex justify-content-between align-items-center"
       style="cursor:pointer;user-select:none" data-bs-toggle="collapse" data-bs-target="#multi-vr-collapse">
    <div class="d-flex align-items-center gap-2">
      <span class="card-badge" style="background:#e5d261;color:#1a1a00">멀티에셋 VR</span>
      <div>
        <div style="font-weight:700;color:#e0e0e0">멀티에셋 밸류리밸런싱 포트폴리오 비교</div>
        <div style="font-size:0.78rem;color:#6b7280">
          QQQ+VOO+금 / QQQ+VOO / QQQ+금 / VOO+금 — VR 전략 2주 사이클 리밸런싱
        </div>
      </div>
    </div>
    <span style="color:#e5d261;font-size:0.85rem;white-space:nowrap">▼ 펼치기</span>
  </div>
  <div class="collapse" id="multi-vr-collapse">
    <div class="card-body pb-0">
      <div class="mb-3 small" style="color:#9aa0c0;background:#1e2040;border-radius:8px;padding:12px 16px;">
        <div class="row g-3">
          <div class="col-md-7">
            <strong style="color:#e5d261">멀티에셋 VR이란?</strong><br>
            주식 1종목 대신 <strong>여러 자산(주식 ETF + 금)</strong>을 함께 보유하며 VR 전략을 적용합니다.<br>
            2주마다 ① 전체 자산 총액이 V목표 밴드를 벗어나면 현금 풀과 교환하고,
            ② 각 자산 간 비중도 목표 비율로 동시에 리밸런싱합니다.<br>
            <span style="color:#4caf93">금은 주식과 낮은 상관관계</span>를 가져 하락장에서 완충 역할을 기대할 수 있습니다.
          </div>
          <div class="col-md-5">
            <div style="border-left:3px solid #e5d261;padding-left:10px;">
              <div style="color:#e5d261;font-weight:700;margin-bottom:4px;">📌 운용 방식 (적립 없음 · 초기 일시납)</div>
              <ul style="color:#9aa0c0;padding-left:16px;margin-bottom:0;">
                <li>원금 $10,000 을 <strong>최초 한 번만</strong> 납입</li>
                <li>이후 <strong>추가 입금 없음</strong> (B&amp;H 리밸런싱 방식)</li>
                <li>초기 배분: 주식 75% + 현금 풀 25%</li>
                <li>2주마다 자산 비중·V목표 리밸런싱만 수행</li>
                <li>총 투입금 = 항상 $10,000 (공정 비교 가능)</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
      <ul class="nav nav-tabs mb-0" id="mvrTabs" role="tablist" style="border-bottom:none;">
        {tab_btns}
      </ul>
      <div class="tab-content border border-top-0 p-0" style="border-color:#2d3154!important;border-radius:0 0 6px 6px;">
        {panes_html}
      </div>
      <!-- 공유 차트 컨테이너 — 메인 자본금 곡선과 동일한 구조 -->
      <div id="mvr-chart-container" class="mt-2"></div>
    </div>
  </div>
</div>"""



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
            f'<tr class="group-header"><td colspan="13">{group_name}</td></tr>'
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
                    f'<td colspan="14" class="text-muted small text-center">데이터 없음</td>'
                    f'</tr>'
                )
                continue

            ms   = r.get("metrics_strategy", {})
            mb   = r.get("metrics_bah", {})
            mv30 = r.get("v30", {}).get("metrics", {})
            mv4  = r.get("v4", {}).get("metrics", {})
            mvr  = r.get("vr", {}).get("metrics", {})
            mvr5 = r.get("vr5", {}).get("metrics", {})
            mmdca = r.get("monthly_dca", {}).get("metrics", {})
            mmvr  = r.get("monthly_vr", {}).get("metrics", {})

            def ci(m):    return m.get("cagr_on_invested", m.get("cagr", 0))
            def roi(m):   return m.get("roi_on_invested", m.get("total_return", 0))
            def cls_c(v): return "cagr-pos" if v > 0 else ("cagr-neg" if v < 0 else "cagr-zero")
            def pc(v):    return f"{v*100:.1f}%"

            cagr   = ci(ms);   roi_v22  = roi(ms);   cagr_c  = cls_c(cagr)
            v30_c  = ci(mv30); roi_v30  = roi(mv30); v30_cl  = cls_c(v30_c)
            v4_c   = ci(mv4);  roi_v4   = roi(mv4);  v4_cl   = cls_c(v4_c)
            vr_c   = ci(mvr);  roi_vr   = roi(mvr);  vr_cl   = cls_c(vr_c)
            vr5_c  = ci(mvr5); roi_vr5  = roi(mvr5); vr5_cl  = cls_c(vr5_c)
            mdca_c = ci(mmdca);roi_mdca = roi(mmdca); mdca_cl = cls_c(mdca_c)
            mvr_c  = ci(mmvr); roi_mvr  = roi(mmvr); mvr_cl  = cls_c(mvr_c)
            bah_c  = ci(mb);   roi_bah  = roi(mb);   bah_cl  = cls_c(bah_c)
            mdd    = ms.get("mdd", 0)
            sharpe = ms.get("sharpe", 0)
            cycles = r.get("final_cycles", 0)
            qcuts  = r.get("final_quarter_cuts", 0)
            mdd_cl = "mdd-bad" if mdd < -0.30 else "mdd-ok"

            def cell(cagr_v, roi_v, cagr_cls, extra_style=""):
                return (
                    f'<td class="metric-cell">'
                    f'<span class="{cagr_cls}"{extra_style}>{pc(cagr_v)}</span>'
                    f'<br><small style="color:#6b7280">총 {pc(roi_v)}</small>'
                    f'</td>'
                )

            rows.append(
                f'<tr data-ticker="{ticker}" data-period="{period}">'
                f'<td><div class="ticker-name">{ticker}</div>'
                f'<div class="ticker-sub">{name}</div></td>'
                + cell(cagr,   roi_v22,  cagr_c)
                + cell(v30_c,  roi_v30,  v30_cl,  ' style="color:#f0a500"')
                + cell(v4_c,   roi_v4,   v4_cl,   ' style="color:#e05c5c"')
                + cell(vr_c,   roi_vr,   vr_cl,   ' style="color:#9b59b6"')
                + cell(vr5_c,  roi_vr5,  vr5_cl,  ' style="color:#17becf"')
                + cell(mdca_c, roi_mdca, mdca_cl, ' style="color:#f0a500"')
                + cell(mvr_c,  roi_mvr,  mvr_cl,  ' style="color:#e05c5c"')
                + f'<td class="metric-cell text-muted small">{pc(bah_c)}<br><small style="color:#6b7280">총 {pc(roi_bah)}</small></td>'
                + f'<td class="metric-cell {mdd_cl}">{pc(mdd)}</td>'
                + f'<td class="metric-cell">{sharpe:.2f}</td>'
                + f'<td class="metric-cell" style="color:#f0a500">{cycles}</td>'
                + f'<td class="metric-cell" style="color:#e05c5c">{qcuts}</td>'
                + f'</tr>'
            )

    rows_html = "\n".join(rows)

    return f"""
<div class="tab-pane fade {active_class}" id="pane-{period}" role="tabpanel">
  <div class="table-responsive">
    <table class="table table-hover mb-0" style="width:100%">
      <thead>
        <tr>
          <th style="min-width:180px">티커 / 이름</th>
          <th class="metric-cell" style="color:#4caf93">V2.2<br><small style="font-weight:normal">연환산/총수익</small></th>
          <th class="metric-cell" style="color:#f0a500">V3.0<br><small style="font-weight:normal">연환산/총수익</small></th>
          <th class="metric-cell" style="color:#e05c5c">V4.0<br><small style="font-weight:normal">연환산/총수익</small></th>
          <th class="metric-cell" style="color:#9b59b6">VR<br><small style="font-weight:normal">연환산/총수익</small></th>
          <th class="metric-cell" style="color:#17becf">VR5.0<br><small style="font-weight:normal">연환산/총수익</small></th>
          <th class="metric-cell" style="color:#f0a500">月DCA<br><small style="font-weight:normal">연환산/총수익</small></th>
          <th class="metric-cell" style="color:#e05c5c">月VR<br><small style="font-weight:normal">연환산/총수익</small></th>
          <th class="metric-cell">B&H<br><small style="font-weight:normal">연환산/총수익</small></th>
          <th class="metric-cell">MDD</th>
          <th class="metric-cell">Sharpe</th>
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
