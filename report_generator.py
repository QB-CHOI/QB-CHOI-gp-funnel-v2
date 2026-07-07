"""
경영진 보고용 HTML 보고서 생성기.
추가 패키지 없이 순수 HTML/CSS로 구성 → 브라우저 Ctrl+P → PDF 저장.
"""
from datetime import date as _date


def generate_html_report(
    period_label: str,
    first_date,
    last_date,
    total_now: int,
    diff: int,
    pct: float,
    period_spend: int,
    conv_rate: float,
    insight_lines: list,
    perf_rows: list,          # [{'채팅방', '현재 인원', '증감', '증감률', '평가', '_members', '_change'}]
    ad_rows: list = None,     # [{'채널', '집행 금액(원)', '비중'}]
    chart_trend_html: str = None,   # plotly to_html fragment (추이 차트)
    chart_snap_html: str = None,    # plotly to_html fragment (현황 스냅샷)
    comparison_rows: list = None,   # [{'label': '전주 대비', 'diff': int, 'pct': float, 'ref_date': str}]
) -> str:
    today_str = str(_date.today())

    # ── CSS ─────────────────────────────────────────────────────────
    css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;
        color: #212121;
        background: #fff;
        font-size: 13px;
        line-height: 1.6;
    }
    .page { max-width: 820px; margin: 0 auto; padding: 32px 40px; }

    /* 헤더 */
    .report-header {
        border-bottom: 3px solid #1565C0;
        padding-bottom: 14px;
        margin-bottom: 24px;
    }
    .report-title { font-size: 22px; font-weight: 700; color: #1565C0; }
    .report-meta  { font-size: 12px; color: #757575; margin-top: 4px; }

    /* KPI 타일 */
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
    .kpi-card {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 14px 16px;
        background: #F8F9FA;
    }
    .kpi-label { font-size: 11px; color: #757575; margin-bottom: 4px; }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1565C0; }
    .kpi-delta { font-size: 11px; margin-top: 3px; }
    .kpi-delta.pos { color: #2E7D32; }
    .kpi-delta.neg { color: #C62828; }
    .kpi-delta.neu { color: #757575; }

    /* 인사이트 */
    .insight-box {
        background: #E3F2FD;
        border-left: 4px solid #1565C0;
        border-radius: 0 8px 8px 0;
        padding: 14px 18px;
        margin-bottom: 24px;
    }
    .insight-box h3 { font-size: 13px; color: #1565C0; margin-bottom: 8px; }
    .insight-box ul { padding-left: 16px; }
    .insight-box li { margin-bottom: 5px; }

    /* 성과표 */
    .section-title { font-size: 14px; font-weight: 700; color: #37474F; margin-bottom: 12px; border-bottom: 1px solid #E0E0E0; padding-bottom: 6px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
    th {
        background: #37474F;
        color: #fff;
        padding: 8px 10px;
        text-align: left;
        font-size: 12px;
        font-weight: 600;
    }
    td { padding: 7px 10px; border-bottom: 1px solid #EEEEEE; font-size: 12px; }
    tr:nth-child(even) td { background: #F5F5F5; }

    /* CSS 바 차트 */
    .bar-cell { padding: 5px 10px; }
    .bar-wrap { display: flex; align-items: center; gap: 8px; }
    .bar-bg { flex: 1; background: #EEEEEE; border-radius: 3px; height: 12px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 3px; }
    .bar-label { font-size: 11px; white-space: nowrap; min-width: 60px; text-align: right; }

    /* 기간 비교 */
    .compare-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 24px; }
    .compare-card {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 12px 14px;
        background: #FAFAFA;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    .compare-label { font-size: 11px; color: #757575; }
    .compare-value { font-size: 17px; font-weight: 700; }
    .compare-sub { font-size: 10px; color: #9E9E9E; }

    /* 광고비 */
    .ad-table th { background: #455A64; }

    /* 푸터 */
    .footer { font-size: 11px; color: #9E9E9E; text-align: center; margin-top: 32px; padding-top: 12px; border-top: 1px solid #E0E0E0; }

    /* 차트 컨테이너 */
    .chart-section { margin-bottom: 28px; }
    .chart-section .section-title { margin-bottom: 10px; }
    .chart-wrap { border: 1px solid #E0E0E0; border-radius: 8px; overflow: hidden; }
    .chart-wrap .plotly-graph-div { width: 100% !important; }

    /* 인쇄 */
    @media print {
        body { font-size: 11px; }
        .page { padding: 0; }
        .kpi-card { break-inside: avoid; }
        .insight-box { break-inside: avoid; }
        .chart-section { break-inside: avoid; }
    }
    """

    # ── KPI HTML ────────────────────────────────────────────────────
    sign   = "+" if diff >= 0 else ""
    diff_class = "pos" if diff > 0 else ("neg" if diff < 0 else "neu")
    pct_class  = diff_class

    cpm_html = ""
    if period_spend > 0 and diff > 0:
        cpm = round(period_spend / diff)
        cpm_html = f'<div class="kpi-delta neu">CPM {cpm:,}원/명</div>'

    kpi_html = f"""
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">현재 총 인원</div>
            <div class="kpi-value">{total_now:,}명</div>
            <div class="kpi-delta {diff_class}">{sign}{diff:,}명 ({sign}{pct:.1f}%)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">기간 순증감</div>
            <div class="kpi-value" style="color:{'#2E7D32' if diff>0 else ('#C62828' if diff<0 else '#757575')}">{sign}{diff:,}명</div>
            <div class="kpi-delta neu">{first_date} → {last_date}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">광고비 집행</div>
            <div class="kpi-value">{f"{period_spend:,}원" if period_spend > 0 else "없음"}</div>
            {cpm_html}
        </div>
        <div class="kpi-card">
            <div class="kpi-label">수강 전환율</div>
            <div class="kpi-value">{f"{conv_rate}%" if conv_rate > 0 else "—"}</div>
            <div class="kpi-delta neu">{'강의 신청 기준' if conv_rate > 0 else '전환 데이터 없음'}</div>
        </div>
    </div>
    """

    # ── 인사이트 HTML ───────────────────────────────────────────────
    insight_items = "".join(f"<li>{ln.replace('**', '<b>').replace('**', '</b>')}</li>" for ln in insight_lines)
    # 볼드 처리: **text** → <b>text</b>  (짝수 번째 ** 닫기)
    def md_bold(text: str) -> str:
        parts = text.split("**")
        result = []
        for i, part in enumerate(parts):
            result.append(part if i % 2 == 0 else f"<b>{part}</b>")
        return "".join(result)

    insight_items = "".join(f"<li>{md_bold(ln)}</li>" for ln in insight_lines)
    insight_html  = f"""
    <div class="insight-box">
        <h3>💡 자동 분석 인사이트</h3>
        <ul>{insight_items}</ul>
    </div>
    """

    # ── 성과표 + CSS 바 차트 ────────────────────────────────────────
    if perf_rows:
        max_members = max(r.get('_members', 0) for r in perf_rows) or 1
        rows_html = ""
        for r in perf_rows:
            members  = r.get('_members', 0)
            chg      = r.get('_change', 0)
            bar_pct  = round(members / max_members * 100)
            bar_color = '#2E7D32' if chg > 0 else ('#C62828' if chg < 0 else '#1565C0')
            chg_color = '#2E7D32' if chg > 0 else ('#C62828' if chg < 0 else '#757575')
            rows_html += f"""
            <tr>
                <td>{r['채팅방']}</td>
                <td class="bar-cell">
                    <div class="bar-wrap">
                        <div class="bar-bg"><div class="bar-fill" style="width:{bar_pct}%;background:{bar_color}"></div></div>
                        <span class="bar-label">{r['현재 인원']}</span>
                    </div>
                </td>
                <td style="color:{chg_color};font-weight:600">{r['증감']}</td>
                <td style="color:{chg_color}">{r['증감률']}</td>
                <td style="text-align:center">{r['평가']}</td>
            </tr>"""

        perf_html = f"""
        <div class="section-title">채팅방별 성과 요약</div>
        <table>
            <thead><tr><th>채팅방</th><th>현재 인원</th><th>증감</th><th>증감률</th><th>평가</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        """
    else:
        perf_html = ""

    # ── 광고비 ───────────────────────────────────────────────────────
    ad_html = ""
    if ad_rows:
        ad_rows_html = "".join(
            f"<tr><td>{r['채널']}</td><td style='text-align:right'>{r['집행 금액(원)']}</td><td style='text-align:right'>{r['비중']}</td></tr>"
            for r in ad_rows
        )
        ad_html = f"""
        <div class="section-title">광고비 채널별 집행 내역</div>
        <table class="ad-table">
            <thead><tr><th>채널</th><th style='text-align:right'>집행 금액(원)</th><th style='text-align:right'>비중</th></tr></thead>
            <tbody>{ad_rows_html}</tbody>
        </table>
        """

    # ── 기간 비교 KPI ────────────────────────────────────────────────
    compare_html = ""
    if comparison_rows:
        cards = ""
        for cr in comparison_rows:
            d   = cr.get('diff', 0)
            p   = cr.get('pct', 0.0)
            s   = "+" if d >= 0 else ""
            col = "#2E7D32" if d > 0 else ("#C62828" if d < 0 else "#757575")
            arrow = "▲" if d > 0 else ("▼" if d < 0 else "➡")
            cards += f"""
            <div class="compare-card">
                <div class="compare-label">{cr.get('label', '')}</div>
                <div class="compare-value" style="color:{col}">{arrow} {s}{d:,}명</div>
                <div class="compare-sub">{s}{p:.1f}% · 기준 {cr.get('ref_date', '')}</div>
            </div>"""
        compare_html = f"""
        <div class="section-title">기간 비교</div>
        <div class="compare-grid">{cards}</div>
        """

    # ── Plotly 차트 섹션 ─────────────────────────────────────────────
    plotly_js_tag = '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>'
    has_charts = bool(chart_trend_html or chart_snap_html)

    def _chart_section(title: str, fragment: str) -> str:
        return f"""
        <div class="chart-section">
            <div class="section-title">{title}</div>
            <div class="chart-wrap">{fragment}</div>
        </div>"""

    chart_snap_section  = _chart_section("채팅방별 현재 인원 현황", chart_snap_html)  if chart_snap_html  else ""
    chart_trend_section = _chart_section("인원 추이 및 예측",       chart_trend_html) if chart_trend_html else ""

    # ── 조립 ────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>채팅방 인원 분석 보고서 — {period_label}</title>
{plotly_js_tag if has_charts else ""}
<style>{css}</style>
</head>
<body>
<div class="page">
    <div class="report-header">
        <div class="report-title">채팅방 인원 분석 보고서</div>
        <div class="report-meta">보고 기간: {period_label} ({first_date} ~ {last_date}) &nbsp;|&nbsp; 작성일: {today_str}</div>
    </div>
    {kpi_html}
    {compare_html}
    {insight_html}
    {chart_snap_section}
    {chart_trend_section}
    {perf_html}
    {ad_html}
    <div class="footer">본 보고서는 채팅방 인원 분석 시스템에서 자동 생성되었습니다.</div>
</div>
</body>
</html>"""

    return html
