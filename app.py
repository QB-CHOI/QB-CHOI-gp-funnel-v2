import streamlit as st
import pandas as pd
from datetime import date, timedelta

from github_store import (
    load_all, save_daily, delete_date,
    load_campaigns, get_current_campaigns,
    save_campaign, end_campaign, get_history, update_lecture_start_date,
    load_rooms, save_room, save_rooms_batch, delete_room,
    load_archived_rooms, archive_room, restore_room, load_all_room_names,
    update_actual_close_date,
    load_conversions, save_conversion, get_latest_conversions, delete_conversion_row,
    load_enrollments, save_enrollment, delete_enrollment,
    load_marketing, load_monthly_performance,
    load_ad_spend_monthly, save_ad_spend_monthly, AD_CHANNEL_OPTIONS,
    load_competitor_courses,
    load_cohort_revenue, load_course_summary, load_campaign_adspend,
    load_monthly_by_course, load_cohort_stage, STAGE_ORDER,
    load_cust_repeat_dist, load_cust_ltv_dist, load_cust_product_repeat,
    load_cust_cross_sell, load_cust_monthly_new_repeat,
    load_region_signups, load_region_cohort, load_region_city, CAPITAL_REGIONS,
    load_adspend, save_adspend, delete_adspend_row,
    load_content, save_content, delete_content_row,
    load_date_notes, save_date_note,
    send_slack_alert,
    PRODUCT_OPTIONS, CHANNEL_OPTIONS, CONTENT_TYPE_OPTIONS,
)
from charts import (
    trend_line_chart, change_bar_chart, total_trend_bar,
    product_bar_chart, weekly_comparison_chart, cohort_trend_chart,
    funnel_chart, conversion_rate_chart, cohort_conversion_chart,
    churn_rate_chart, roi_chart,
    ranking_chart, weekly_aggregate_chart, monthly_aggregate_chart,
    cpm_chart, content_impact_table, trend_forecast_chart,
    room_snapshot_chart, period_total_trend, calendar_heatmap_chart,
    recruitment_curve_chart, retention_after_opening_chart, cohort_efficiency_df,
    cohort_funnel_data, conversion_funnel_chart, cohort_conversion_bar_chart,
    marketing_channel_summary, marketing_channel_chart, marketing_trend_chart,
    marketing_channel_conv_chart, monthly_perf_chart, competitor_price_chart,
    cohort_revenue_chart, product_revenue_mix_chart, monthly_roas_chart,
    region_distribution_chart, region_capital_trend_chart, region_city_chart,
    region_bubble_map,
    product_ad_roi_chart, cohort_ad_roi_chart,
    overall_conversion_funnel, product_conversion_rate_chart,
    monthly_course_heatmap, monthly_course_stack,
    stage_funnel_chart, cohort_stage_matrix_chart,
    cust_repeat_donut, cust_ltv_bar, cust_product_repeat_chart,
    cross_sell_heatmap, monthly_new_repeat_chart,
    runrate_forecast_chart,
)

st.set_page_config(
    page_title="황금후추 강의 분석",
    page_icon="📊",
    layout="wide",
)

# ── 모바일 반응형 CSS ─────────────────────────────────────────────
st.markdown("""
<style>
/* 모바일(768px 이하): 3컬럼 → 1컬럼 스택 */
@media (max-width: 768px) {
    div[data-testid="column"] { min-width: 100% !important; }
    div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    /* 버튼 전체 너비 */
    div[data-testid="stButton"] button { width: 100% !important; }
    /* 숫자 입력 폰트 확대 */
    input[type="number"] { font-size: 16px !important; }
}
/* 검토 테이블 텍스트 줄 바꿈 방지 */
div[data-testid="stDataFrame"] td { white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 — 캐시 새로고침 ─────────────────────────────────────

with st.sidebar:
    st.markdown("### 📊 황금후추 강의 분석")
    st.divider()

    # 오늘 입력 상태
    _df_check = load_all()
    _today_str = str(date.today())
    if _df_check.empty or _today_str not in _df_check['date'].astype(str).values:
        st.error(f"⚠️ 오늘({_today_str}) 데이터 미입력", icon="🚨")
    else:
        _n_today = len(_df_check[_df_check['date'].astype(str) == _today_str])
        st.success(f"✅ 오늘 {_n_today}개 방 입력 완료")

    # 최근 7일 완성도 및 누락 날짜 경고
    if not _df_check.empty:
        _recent_7 = [str(date.today() - timedelta(days=i)) for i in range(7)]
        _entered_7 = set(_df_check['date'].astype(str).unique())
        _missing_7 = [d for d in _recent_7 if d not in _entered_7]
        _comp_7 = round((7 - len(_missing_7)) / 7 * 100)
        st.caption(f"최근 7일 입력률 **{_comp_7}%**")
        if _missing_7:
            st.warning("누락: " + ", ".join(sorted(_missing_7, reverse=True)[:3]) +
                       (f" 외 {len(_missing_7)-3}일" if len(_missing_7) > 3 else ""),
                       icon="📅")

    st.divider()
    if st.button("🔄 데이터 새로고침", width='stretch',
                 help="GitHub에서 최신 데이터를 강제로 다시 불러옵니다 (3분 캐시 초기화)"):
        load_all.clear()
        load_campaigns.clear()
        load_rooms.clear()
        load_conversions.clear()
        load_adspend.clear()
        load_content.clear()
        load_date_notes.clear()
        st.toast("✅ 데이터를 새로고침했습니다", icon="🔄")
        st.rerun()
    st.caption(f"마지막 갱신: {pd.Timestamp.now().strftime('%H:%M:%S')}")

# ── 세션 상태 초기화 ──────────────────────────────────────────────

if 'ocr_results' not in st.session_state:
    st.session_state.ocr_results = {}
if 'ocr_done' not in st.session_state:
    st.session_state.ocr_done = False
if 'uploaded_file_names' not in st.session_state:
    st.session_state.uploaded_file_names = []
if 'pending_delete_date' not in st.session_state:
    st.session_state.pending_delete_date = None
if '_pending_new_rooms' not in st.session_state:
    st.session_state._pending_new_rooms = {}
if '_editing_room' not in st.session_state:
    st.session_state._editing_room = None
if '_ocr_error' not in st.session_state:
    st.session_state._ocr_error = None
if '_pending_archive' not in st.session_state:
    st.session_state['_pending_archive'] = None



# ── OCR 검토 테이블 ───────────────────────────────────────────────

def _show_ocr_review(ocr_results: dict, rooms: dict, prev: dict):
    """OCR 인식 결과를 전체 채팅방 기준으로 보여주는 검토 테이블.
    인식되지 않은 방도 '미인식' 상태로 표시한다."""
    rows = []
    has_warning = False
    recognized = 0

    for rn in sorted(rooms.keys()):
        name = rooms.get(rn, f"채팅방 {rn}")
        ocr_val = ocr_results.get(rn)
        prev_val = prev.get(rn)

        if ocr_val is None:
            rows.append({
                "채팅방": name,
                "인식값": None,
                "전일": int(prev_val) if prev_val is not None else None,
                "증감": None,
                "상태": "❌ 미인식",
            })
            continue

        recognized += 1
        if prev_val is not None:
            diff = ocr_val - int(prev_val)
            pct  = abs(diff / prev_val * 100) if prev_val else 0
            # 방 규모에 비례한 임계값 (작은 방엔 느슨, 큰 방엔 엄격)
            if prev_val >= 500:
                warn_pct, alert_pct = 15, 30
            elif prev_val >= 100:
                warn_pct, alert_pct = 20, 40
            else:
                warn_pct, alert_pct = 25, 50
            if pct > alert_pct or abs(diff) > 1000:
                status = "🚨 확인 필요"
                has_warning = True
            elif pct > warn_pct or abs(diff) > 500:
                status = "⚠️ 변동 큼"
                has_warning = True
            else:
                status = "✅ 정상"
        else:
            diff = None
            status = "➕ 신규"

        rows.append({
            "채팅방": name,
            "인식값": ocr_val,
            "전일": int(prev_val) if prev_val is not None else None,
            "증감": diff,
            "상태": status,
        })

    if not rows:
        return

    total = len(rooms)
    unrecognized = total - recognized

    st.subheader(f"인식 결과 검토 ({recognized} / {total}개 인식)")

    if unrecognized > 0:
        miss_names = [rooms.get(rn, f"채팅방 {rn}") for rn in sorted(rooms.keys()) if rn not in ocr_results]
        st.error(f"❌ {unrecognized}개 미인식 — 2단계에서 직접 입력하세요: " + "  |  ".join(miss_names))
    if has_warning:
        st.warning("⚠️ 이상값 감지 — 아래 표를 확인하고 2단계에서 수정하세요.")
    if recognized == total and not has_warning:
        st.success("모든 채팅방 인식 완료. 값이 맞으면 3단계에서 저장하세요.")

    df_review = pd.DataFrame(rows)

    def _row_color(row):
        s = row.get("상태", "")
        if s == "❌ 미인식":
            return ["background-color: #ffebee"] * len(row)
        if s == "🚨 확인 필요":
            return ["background-color: #fff3e0"] * len(row)
        if s == "⚠️ 변동 큼":
            return ["background-color: #fffde7"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_review.style.apply(_row_color, axis=1),
        hide_index=True,
        column_config={
            "인식값": st.column_config.NumberColumn(format="%d명"),
            "전일": st.column_config.NumberColumn(format="%d명"),
            "증감": st.column_config.NumberColumn(format="%+d명"),
        },
    )

    # 하단 요약: OCR 인식 / 전일 데이터 / 미입력
    n_ocr   = sum(1 for r in rows if r["상태"] not in ("❌ 미인식",) and r["인식값"] is not None)
    n_miss  = sum(1 for r in rows if r["상태"] == "❌ 미인식")
    n_warn  = sum(1 for r in rows if r["상태"] in ("🚨 확인 필요", "⚠️ 변동 큼"))
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("📷 OCR 인식", f"{n_ocr}개")
    sc2.metric("❌ 미인식", f"{n_miss}개", delta=f"-{n_miss}" if n_miss else None,
               delta_color="inverse")
    sc3.metric("⚠️ 이상값", f"{n_warn}개", delta=f"{n_warn}건 확인 필요" if n_warn else "이상 없음",
               delta_color="inverse" if n_warn else "off")
    if n_warn > 0:
        st.caption("💡 이상값이 광고·이벤트 등 특수 상황이면 3단계 저장 후 메모를 남기세요. 메모는 추이 그래프에 오버레이로 표시됩니다.")


# ── 로그인 인증 ──────────────────────────────────────────────────

def _run_auth() -> bool:
    """Secrets에 app_password 가 있으면 비밀번호 게이트를 실행.
    없으면 즉시 True(통과) 반환 — 로컬 개발 시 자동 우회."""
    pw_secret = st.secrets.get("app_password", "")
    if not pw_secret:
        return True

    if st.session_state.get("_authenticated"):
        return True

    st.title("📊 황금후추 강의 분석")
    st.subheader("🔒 로그인")
    with st.form("login_form"):
        entered = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        if st.form_submit_button("로그인", type="primary", width='stretch'):
            if entered == pw_secret:
                st.session_state["_authenticated"] = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    return False


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    if not _run_auth():
        return

    st.title("📊 황금후추 강의 분석")

    (tab_ov, tab1, tab2, tab3, tab4, tab5, tab_drill, tab_prd, tab_cust, tab9, tab10,
     tab6, tab7, tab8) = st.tabs([
        "🧭 종합 보고", "📸 오늘 입력", "📊 현황", "📋 전환 분석", "📈 추이 그래프",
        "🎓 강의 분석", "🔎 강의별 상세", "📅 기간별 분석", "👥 고객 분석",
        "📢 마케팅 분석", "📍 지역 분석",
        "📑 경영진 보고", "⚙️ 채팅방 설정", "🗂️ 데이터 관리",
    ])

    with tab_ov:
        tab_overview()
    with tab1:
        tab_input()
    with tab2:
        tab_dashboard()
    with tab3:
        tab_conversion()
    with tab4:
        tab_trend()
    with tab5:
        tab_lecture_analysis()
    with tab_drill:
        tab_course_detail()
    with tab_prd:
        tab_period()
    with tab_cust:
        tab_customer()
    with tab9:
        tab_marketing()
    with tab10:
        tab_region()
    with tab6:
        tab_report()
    with tab7:
        tab_campaign()
    with tab8:
        tab_data()


# ── 탭: 고객 분석 (LTV·재구매·교차판매) ───────────────────────────

def tab_customer():
    st.header("👥 고객 분석")
    st.caption("주문 원본에서 **고객 단위**로 집계한 재구매·생애가치(LTV)·교차판매 분석입니다. "
               "개인정보는 저장하지 않고 집계 수치만 사용합니다.")

    rep = load_cust_repeat_dist()
    ltv = load_cust_ltv_dist()
    pr = load_cust_product_repeat()
    xs = load_cust_cross_sell()
    mnr = load_cust_monthly_new_repeat()
    if rep.empty and pr.empty:
        st.info("고객 집계 데이터가 없습니다.")
        return

    # ── 핵심 지표 ───────────────────────────────────────
    _tot_cust = int(rep['customers'].sum()) if not rep.empty else 0
    _repeat = int(rep[rep['bucket'] != '1회']['customers'].sum()) if not rep.empty else 0
    _repeat_rate = _repeat / _tot_cust * 100 if _tot_cust else 0
    _new_rev = int(mnr['new_revenue'].sum()) if not mnr.empty else 0
    _rep_rev = int(mnr['repeat_revenue'].sum()) if not mnr.empty else 0
    _rep_rev_share = _rep_rev / (_new_rev + _rep_rev) * 100 if (_new_rev + _rep_rev) else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 고객", f"{_tot_cust:,}명")
    c2.metric("재구매율", f"{_repeat_rate:.1f}%", help="2회 이상 결제 고객 비율")
    c3.metric("재구매 매출 비중", f"{_rep_rev_share:.0f}%",
              help=f"재구매 {_rep_rev/1e8:.1f}억 / 신규 {_new_rev/1e8:.1f}억")
    if not pr.empty:
        _hi = pr.loc[pr['avg_ltv'].idxmax()]
        c4.metric("최고 LTV 상품", f"{_hi['product']} {_hi['avg_ltv']/1e4:,.0f}만")

    if _rep_rev_share >= 40:
        st.success(f"💡 **재구매 매출이 전체의 {_rep_rev_share:.0f}%** — 신규 유치만큼 "
                   "**기존 고객 재구매·상위 과정 업셀**이 매출의 핵심 축입니다. "
                   "CRM·재구매 유도에 투자할 근거가 명확합니다.")

    # ── 재구매 분포 + LTV 분포 ──────────────────────────
    st.divider()
    d1, d2 = st.columns(2)
    with d1:
        _f = cust_repeat_donut(rep)
        if _f:
            st.plotly_chart(_f, width='stretch', key="cust_repeat")
    with d2:
        _f = cust_ltv_bar(ltv)
        if _f:
            st.plotly_chart(_f, width='stretch', key="cust_ltv")

    # ── 상품군별 재구매율·LTV ───────────────────────────
    st.divider()
    st.subheader("상품군별 재구매율 · 평균 LTV")
    _f = cust_product_repeat_chart(pr)
    if _f:
        st.plotly_chart(_f, width='stretch', key="cust_prod")
    if not pr.empty:
        _hr = pr.loc[pr['repeat_rate'].idxmax()]
        _lr = pr.loc[pr['repeat_rate'].idxmin()]
        st.info(f"💡 **{_hr['product']}**가 재구매율 **{_hr['repeat_rate']:.1f}%**로 최고 "
                "(무료→유료 전환도 높은 상품 → 충성 고객층 형성). "
                f"**{_lr['product']}**는 **{_lr['repeat_rate']:.1f}%**로 낮아 "
                "(단일 고가 상품 특성) 후속 상품 라인업이 재구매 여지를 좌우합니다.")

    # ── 교차판매 매트릭스 ───────────────────────────────
    if not xs.empty:
        st.divider()
        st.subheader("교차판매 (강의 간 이동)")
        _f = cross_sell_heatmap(xs)
        if _f:
            st.plotly_chart(_f, width='stretch', key="cust_cross")
        _top = xs.sort_values('rate', ascending=False).iloc[0]
        st.info(f"💡 **{_top['from']} 구매자의 {_top['rate']:.0f}%가 {_top['to']}도 구매** — "
                f"가장 강한 교차판매 경로입니다. {_top['from']} 고객에게 {_top['to']}를 "
                "우선 추천하는 CRM이 효과적입니다.")

    # ── 월별 신규 vs 재구매 매출 ────────────────────────
    if not mnr.empty:
        st.divider()
        st.subheader("월별 신규 vs 재구매 매출")
        _f = monthly_new_repeat_chart(mnr)
        if _f:
            st.plotly_chart(_f, width='stretch', key="cust_monthly")
        st.caption("파랑=신규 고객 첫 결제, 골드=기존 고객 재구매. 재구매 비중이 높아지는 달일수록 "
                   "고객 자산이 축적되고 있다는 신호입니다.")


# ── 탭: 기간별 분석 ───────────────────────────────────────────────

def tab_period():
    st.header("📅 기간별 분석")
    mbc = load_monthly_by_course()
    ad_m = load_ad_spend_monthly()
    if mbc.empty:
        st.info("월별×강의별 집계 데이터가 없습니다.")
        return
    st.caption("주문 원본(개인정보 제외) 기준 월별×강의별 매출·유료건·무료신청. "
               "각 강의가 **언제** 성과를 냈는지(개강 효과)를 시점축으로 봅니다.")

    _months = sorted(mbc['month'].unique())
    # ── 히트맵 ───────────────────────────────────────────
    st.subheader("월별 × 강의별 매출 히트맵")
    fig_h = monthly_course_heatmap(mbc)
    if fig_h:
        st.plotly_chart(fig_h, width='stretch', key="prd_heat")
    st.caption("색이 진한 칸 = 그 달 그 강의 매출이 큼. 강의별 개강월에 매출이 집중되는 패턴을 확인하세요.")

    # ── 월별 매출 구성 + 광고비 ──────────────────────────
    st.divider()
    st.subheader("월별 매출 구성 · 광고비 추이")
    fig_s = monthly_course_stack(mbc, ad_m if not ad_m.empty else None)
    if fig_s:
        st.plotly_chart(fig_s, width='stretch', key="prd_stack")

    # ── 특정 월 드릴다운 ─────────────────────────────────
    st.divider()
    st.subheader("월 선택 상세")
    _msel = st.selectbox("월 선택", options=_months[::-1], key="prd_month")
    _cur = mbc[mbc['month'] == _msel]
    _prev_month = _months[_months.index(_msel) - 1] if _months.index(_msel) > 0 else None
    _prev = mbc[mbc['month'] == _prev_month] if _prev_month else pd.DataFrame()

    _tot_rev = int(_cur['paid_revenue'].sum())
    _tot_ord = int(_cur['paid_orders'].sum())
    _tot_free = int(_cur['free_signups'].sum())
    _prev_rev = int(_prev['paid_revenue'].sum()) if not _prev.empty else 0
    mm1, mm2, mm3, mm4 = st.columns(4)
    mm1.metric(f"{_msel} 매출", f"{_tot_rev/1e8:,.2f}억",
               delta=(f"{(_tot_rev-_prev_rev)/1e8:+.2f}억 vs {_prev_month}" if _prev_month else None))
    mm2.metric("유료 주문", f"{_tot_ord:,}건")
    mm3.metric("무료 신청", f"{_tot_free:,}명")
    mm4.metric("월 객단가", f"{_tot_rev/_tot_ord/1e4:,.0f}만" if _tot_ord else "—")

    # 그 달의 상품군 구성표
    _cd = _cur.sort_values('paid_revenue', ascending=False)
    _cd_disp = pd.DataFrame({
        '상품군': _cd['product'],
        '매출': _cd['paid_revenue'].apply(lambda x: f"{x/1e8:,.2f}억" if x >= 1e7 else f"{x/1e4:,.0f}만"),
        '유료주문': _cd['paid_orders'].apply(lambda x: f"{x:,}건"),
        '무료신청': _cd['free_signups'].apply(lambda x: f"{x:,}명"),
        '객단가': (_cd['paid_revenue'] / _cd['paid_orders'].replace(0, pd.NA)).fillna(0).apply(
            lambda x: f"{x/1e4:,.0f}만"),
    })
    st.dataframe(_cd_disp, hide_index=True, width='stretch')
    if _tot_rev:
        _top = _cd.iloc[0]
        st.info(f"💡 **{_msel}**는 **{_top['product']}**가 매출 {_top['paid_revenue']/1e8:.2f}억으로 주도"
                f"({_top['paid_revenue']/_tot_rev*100:.0f}%). 개강·프로모션 시점과 대조해 보세요.")

    # ── 다음 기간 전망 (런레이트) ────────────────────────
    perf = load_monthly_performance()
    if not perf.empty and len(perf) >= 4:
        st.divider()
        st.subheader("📈 다음 기간 전망 (런레이트)")
        st.caption("강의 사업은 **개강 시점에 매출이 몰려** 월별 편차가 큽니다. 특정 월을 콕 집어 "
                   "예측하기보다 **최근 3개월 평균(런레이트)** 과 **최근 변동폭**으로 전망합니다. "
                   "당월(집계 진행 중)은 계산에서 제외합니다.")
        _p = perf.sort_values('month')
        _pm = _p['month'].tolist()
        _free = _p['free_signups'].tolist()
        _rev = _p['revenue'].tolist()
        # 런레이트(당월 제외 최근 3개월 평균)
        _complete = _p[_p['month'] < date.today().strftime('%Y-%m')]
        _rr_free = _complete['free_signups'].tail(3).mean() if len(_complete) >= 3 else 0
        _rr_rev = _complete['revenue'].tail(3).mean() if len(_complete) >= 3 else 0
        f1, f2, f3 = st.columns(3)
        f1.metric("무료 모객 런레이트", f"{_rr_free:,.0f}명/월",
                  help="당월 제외 최근 3개월 평균")
        f2.metric("매출 런레이트", f"{_rr_rev/1e8:,.2f}억/월")
        f3.metric("연 환산 페이스", f"{_rr_rev*12/1e8:,.0f}억/년",
                  help="현재 런레이트가 유지될 경우의 연 매출 페이스(개강 일정에 따라 변동)")

        fc1, fc2 = st.columns(2)
        with fc1:
            _ff = runrate_forecast_chart(_pm, _free, '무료 모객', unit='명',
                                         color='#7C9CBF', periods=2)
            if _ff:
                st.plotly_chart(_ff, width='stretch', key="prd_fc_free")
        with fc2:
            _fr = runrate_forecast_chart(_pm, _rev, '매출', color='#26A69A',
                                         periods=2, as_eok=True)
            if _fr:
                st.plotly_chart(_fr, width='stretch', key="prd_fc_rev")
        st.warning("⚠️ 전망은 **최근 추세 기준 참고치**입니다. 개강·프로모션이 있는 달은 크게 상회하고, "
                   "없는 달은 하회합니다. 확정 예측이 아니라 예산·목표 설정의 기준선으로 활용하세요.")


# ── 탭: 강의별 상세 (드릴다운) ────────────────────────────────────

def tab_course_detail():
    st.header("🔎 강의별 상세")
    st.caption("상품군을 선택하면 그 강의의 **모객·매출·유료 단계 전환·광고 효율·지역**을 "
               "한 화면에 모아 정밀 진단합니다.")

    cohort_rev = load_cohort_revenue()
    camp = load_campaign_adspend()
    stage = load_cohort_stage()
    mbc = load_monthly_by_course()
    cs = load_course_summary()
    if cohort_rev.empty and cs.empty:
        st.info("강의 데이터가 없습니다.")
        return

    _prods = [p for p in ['사주', '타로', '부동산', '빌딩']
              if p in cohort_rev['product'].unique()] or ['사주', '타로', '부동산', '빌딩']
    prod = st.selectbox("강의(상품군) 선택", options=_prods, key="drill_prod")

    # ── 상단 요약 KPI ────────────────────────────────────
    _cr = cohort_rev[cohort_rev['product'] == prod]
    _csum = cs[cs['product'] == prod]
    k1, k2, k3, k4 = st.columns(4)
    if not _csum.empty:
        _r = _csum.iloc[0]
        k1.metric("누적 매출", f"{int(_r['revenue'])/1e8:,.1f}억")
        k2.metric("수강생", f"{int(_r['students']):,}명")
        _cv = int(_r['students']) / int(_r['free']) * 100 if int(_r['free']) else 0
        k3.metric("무료→유료 전환", f"{_cv:.1f}%")
        k4.metric("객단가", f"{int(_r['revenue'])/int(_r['students'])/1e4:,.0f}만"
                  if int(_r['students']) else "—")

    # ── 기수별 매출 추이 ─────────────────────────────────
    st.divider()
    st.subheader("기수별 매출 · 수강생")
    fig_c = cohort_revenue_chart(cohort_rev, prod)
    if fig_c:
        st.plotly_chart(fig_c, width='stretch', key="drill_cohort")

    # ── 유료 단계 전환 (사주/타로) ───────────────────────
    _st = stage[stage['product'] == prod] if not stage.empty else pd.DataFrame()
    if not _st.empty:
        st.divider()
        st.subheader("유료 단계 전환 (기초 → 심화 → 전문가)")
        st.caption("무료→유료 이후 **상위 과정으로의 단계 전환**. 어느 단계에서 이탈하는지 봅니다.")
        sc1, sc2 = st.columns([1, 1.3])
        with sc1:
            _cohs = _st.assign(n=_st['cohort'].str.extract(r'(\d+)').astype(float)) \
                       .sort_values('n')['cohort'].tolist()
            _csel = st.selectbox("기수 선택", options=_cohs[::-1], key="drill_stage_coh")
            _sf = stage_funnel_chart(stage, prod, _csel, STAGE_ORDER)
            if _sf:
                st.plotly_chart(_sf, width='stretch', key="drill_stage_funnel")
            else:
                st.caption("이 기수는 단계 데이터가 1개뿐이라 퍼널을 표시하지 않습니다.")
        with sc2:
            _mx = cohort_stage_matrix_chart(stage, prod, STAGE_ORDER)
            if _mx:
                st.plotly_chart(_mx, width='stretch', key="drill_stage_matrix")
        # 단계 전환 인사이트 (평균 이탈)
        _rows = _st.copy()
        _b2s = _rows[(_rows['기초'] > 0) & (_rows['심화'] > 0)]
        _s2p = _rows[(_rows['심화'] > 0) & (_rows['전문가'] > 0)]
        _parts = []
        if not _b2s.empty:
            _parts.append(f"기초→심화 평균 **{(_b2s['심화']/_b2s['기초']).mean()*100:.0f}%**")
        if not _s2p.empty:
            _parts.append(f"심화→전문가 평균 **{(_s2p['전문가']/_s2p['심화']).mean()*100:.0f}%**")
        if _parts:
            st.info("💡 " + " · ".join(_parts) +
                    ". 심화→전문가 전환이 급락하는 구간이 업셀 개선 포인트입니다.")
    elif prod in ('부동산', '빌딩'):
        st.divider()
        st.caption("ℹ️ 부동산·빌딩은 단일 트랙(기초·심화 위주)이라 단계 전환표가 제공되지 않습니다.")

    # ── 광고 효율 추이 (기수/시점) ───────────────────────
    _ca = camp[camp['product'] == prod] if not camp.empty else pd.DataFrame()
    if not _ca.empty:
        st.divider()
        st.subheader("광고 효율 (기수별)")
        fig_ad = cohort_ad_roi_chart(camp, prod)
        if fig_ad:
            st.plotly_chart(fig_ad, width='stretch', key="drill_ad")

    # ── 월별 매출 시계열 (해당 강의) ─────────────────────
    _mb = mbc[mbc['product'] == prod] if not mbc.empty else pd.DataFrame()
    if not _mb.empty:
        st.divider()
        st.subheader("월별 매출 추이")
        _mb2 = _mb.sort_values('month')
        import plotly.graph_objects as _go
        _pcolor = {'사주': '#7C4DBC', '타로': '#9C6ADE',
                   '부동산': '#2E8B7A', '빌딩': '#1E6FD9'}.get(prod, '#5B8FF9')
        _figm = _go.Figure(_go.Bar(
            x=_mb2['month'], y=_mb2['paid_revenue'],
            marker_color=_pcolor,
            hovertemplate='%{x}<br>%{y:,.0f}원<extra></extra>'))
        _figm.update_layout(title=f'{prod} 월별 매출 (주문 기준)', height=320,
                            margin=dict(t=50, b=50, l=20, r=20),
                            xaxis=dict(tickangle=-45), yaxis=dict(title='매출(원)'))
        st.plotly_chart(_figm, width='stretch', key="drill_monthly")


# ── 탭: 종합 보고 (전략 대시보드) ─────────────────────────────────

def _product_master_table():
    """상품군 통합 요약: 매출·유료·무료·전환율·객단가 + 광고비·광고ROAS."""
    cs = load_course_summary()
    camp = load_campaign_adspend()
    if cs.empty:
        return pd.DataFrame()
    m = cs.copy()
    # 전환율·객단가는 매출과 동일 기준인 '세트 수강생(students)'을 분모로 사용(기준 정합)
    m['전환율'] = (m['students'] / m['free'].replace(0, pd.NA) * 100).round(1).fillna(0)
    m['객단가'] = (m['revenue'] / m['students'].replace(0, pd.NA)).fillna(0).astype(int)
    if not camp.empty:
        ad = camp.groupby('product').agg(ad=('ad_spend', 'sum'),
                                         lrev=('live_revenue', 'sum')).reset_index()
        ad['광고ROAS'] = (ad['lrev'] / ad['ad'].replace(0, pd.NA)).round(1).fillna(0)
        m = m.merge(ad[['product', 'ad', '광고ROAS']], on='product', how='left')
    else:
        m['ad'] = 0
        m['광고ROAS'] = 0
    m['ad'] = m['ad'].fillna(0)
    m['광고ROAS'] = m['광고ROAS'].fillna(0)
    return m.sort_values('revenue', ascending=False)


def tab_overview():
    st.header("🧭 종합 보고 — 전략 대시보드")
    st.caption("모객 · 매출 · 전환 · 광고 ROI · 지역을 한 화면에 종합한 경영 전략 요약입니다. "
               "모든 수치는 강의 집계·광고비·지역 실데이터에서 자동 계산됩니다.")

    cs = load_course_summary()
    if cs.empty:
        st.info("강의 집계 데이터가 아직 없습니다. 데이터가 이관되면 종합 보고가 표시됩니다.")
        return

    camp = load_campaign_adspend()
    region = load_region_signups()
    rc = load_region_cohort()
    perf = load_monthly_performance()
    ad_m = load_ad_spend_monthly()

    # ── 핵심 지표 ───────────────────────────────────────
    tot_rev = int(cs['revenue'].sum())
    tot_free = int(cs['free'].sum())
    tot_students = int(cs['students'].sum())   # 세트 수강생(매출과 동일 기준)
    conv = tot_students / tot_free * 100 if tot_free else 0

    roas_txt, _roas_help = "—", "월별 광고비 입력 시 표시"
    if not perf.empty and not ad_m.empty:
        _am = set(ad_m['month'].astype(str))
        _sp = int(ad_m['spend'].sum())
        _rv = int(perf[perf['month'].astype(str).isin(_am)]['revenue'].sum())
        if _sp:
            roas_txt = f"{_rv/_sp:.1f}배"
            _roas_help = f"매출 {_rv/1e8:.1f}억 ÷ 광고비 {_sp/1e8:.1f}억 (집행 기간)"

    cap_pct = 0.0
    if not region.empty:
        _t = int(region['signups'].sum())
        _c = int(region[region['region'].isin(CAPITAL_REGIONS)]['signups'].sum())
        cap_pct = _c / _t * 100 if _t else 0

    # 광고 최고효율 상품
    _best_ad = None
    if not camp.empty:
        _g = camp.groupby('product').agg(ad=('ad_spend', 'sum'),
                                         rev=('live_revenue', 'sum')).reset_index()
        _g = _g[_g['ad'] > 0]
        if not _g.empty:
            _g['roas'] = _g['rev'] / _g['ad']
            _best_ad = _g.loc[_g['roas'].idxmax()]

    st.markdown("#### 핵심 지표")
    a, b, c, d = st.columns(4)
    a.metric("누적 매출", f"{tot_rev/1e8:,.1f}억원")
    b.metric("무료 모객", f"{tot_free:,}명", help="무료 특강 신청 건수(중복 신청 포함)")
    c.metric("유료 수강생", f"{tot_students:,}명",
             help="세트 수강생(기초+심화+패키지·멤버십 제외). 유료 결제 건수는 "
                  f"{int(cs['paid'].sum()):,}건")
    d.metric("무료→유료 전환", f"{conv:.1f}%", help="세트 수강생 ÷ 무료 신청")
    e, f, g, h = st.columns(4)
    e.metric("누적 ROAS", roas_txt, help=_roas_help)
    f.metric("수도권 집중도", f"{cap_pct:.0f}%" if cap_pct else "—",
             help="배송지 기준 서울·경기·인천 비중")
    if _best_ad is not None:
        g.metric("광고 최고효율", f"{_best_ad['product']} {_best_ad['roas']:.1f}배")
    else:
        g.metric("광고 최고효율", "—")
    _top_rev = cs.sort_values('revenue', ascending=False).iloc[0]
    h.metric("매출 1위 상품", f"{_top_rev['product']} {_top_rev['revenue']/1e8:.1f}억")

    st.divider()

    # ── 전략 브리핑 ─────────────────────────────────────
    _brief = _strategy_briefing()
    if _brief:
        with st.container(border=True):
            st.markdown("#### 🎯 전략 브리핑 — 지금 해야 할 것")
            for _icon, _title, _body in _brief:
                st.markdown(f"- **{_icon} {_title}** — {_body}")

    st.divider()

    # ── 도식 4종 (2×2) ──────────────────────────────────
    st.markdown("#### 종합 도식")
    o1, o2 = st.columns(2)
    with o1:
        _fig = product_revenue_mix_chart(cs)
        if _fig:
            st.plotly_chart(_fig, key="ov_mix")
    with o2:
        if not camp.empty:
            _fig = product_ad_roi_chart(camp)
            if _fig:
                st.plotly_chart(_fig, key="ov_adroi")
    o3, o4 = st.columns(2)
    with o3:
        _fig = product_conversion_rate_chart(cs)
        if _fig:
            st.plotly_chart(_fig, key="ov_conv")
    with o4:
        if not region.empty:
            _fig = region_distribution_chart(region, capital=tuple(CAPITAL_REGIONS))
            if _fig:
                st.plotly_chart(_fig, key="ov_region")

    # 기간 하이라이트 — 월별×강의별 매출 히트맵 (최근 12개월)
    _mbc = load_monthly_by_course()
    if not _mbc.empty:
        _fh = monthly_course_heatmap(_mbc, months=12)
        if _fh:
            st.plotly_chart(_fh, width='stretch', key="ov_heat")
            st.caption("최근 12개월 강의별 매출 집중 시점. 상세는 **📅 기간별 분석**·**🔎 강의별 상세** 탭 참고.")

    # ── 상품군 통합 요약표 ──────────────────────────────
    st.divider()
    st.markdown("#### 상품군 통합 요약표")
    m = _product_master_table()
    if not m.empty:
        disp = pd.DataFrame({
            '상품군': m['product'],
            '누적매출': m['revenue'].apply(lambda x: f"{x/1e8:,.2f}억"),
            '수강생': m['students'].apply(lambda x: f"{x:,}명"),
            '무료모객': m['free'].apply(lambda x: f"{x:,}"),
            '전환율': m['전환율'].apply(lambda x: f"{x}%"),
            '객단가': m['객단가'].apply(lambda x: f"{x/1e4:,.0f}만"),
            '광고비': m['ad'].apply(lambda x: f"{x/1e8:,.2f}억" if x else "—"),
            '광고ROAS': m['광고ROAS'].apply(lambda x: f"{x:.1f}배" if x else "—"),
        })
        st.dataframe(disp, hide_index=True, width='stretch')
        st.caption("수강생·전환율·객단가는 **세트 수강생**(멤버십 제외, 매출과 동일 기준). "
                   "전환율=수강생÷무료신청, 객단가=매출÷수강생. "
                   "광고비·광고ROAS=통합시트 캠페인별 귀속이며, **광고ROAS의 매출은 라이브 첫전환 기준**"
                   "이라 누적매출을 광고비로 나눈 값과 다릅니다.")

    # ── 전략 결론 ───────────────────────────────────────
    st.divider()
    st.markdown("#### 📌 전략 결론")
    _pts = []
    if _best_ad is not None and not m.empty:
        _low = m.sort_values('광고ROAS')
        _low = _low[_low['광고ROAS'] > 0]
        _worst_ad = _low.iloc[0] if not _low.empty else None
        _pts.append(f"**광고 예산**: 광고 효율 1위 **{_best_ad['product']}({_best_ad['roas']:.1f}배)** 확대, "
                    + (f"효율이 낮은 **{_worst_ad['product']}({_worst_ad['광고ROAS']:.1f}배)**는 소재·타깃 개선 후 재배분."
                       if _worst_ad is not None else ""))
    _cvbest = cs.copy()
    _cvbest['cv'] = _cvbest['students'] / _cvbest['free'].replace(0, pd.NA)
    _cvbest = _cvbest.dropna(subset=['cv'])
    if not _cvbest.empty:
        _cb = _cvbest.loc[_cvbest['cv'].idxmax()]
        _pts.append(f"**모객 확대**: 전환율 최고 **{_cb['product']}({_cb['cv']*100:.1f}%)**는 무료 모객을 늘릴수록 "
                    "유료 성과 직결 — 무료 특강 물량 확대 1순위.")
    if cap_pct:
        _pts.append(f"**지역 타깃**: 수도권 집중도 **{cap_pct:.0f}%** — 광고 예산을 서울·경기·인천에 우선 배정, "
                    "부산·경남 영남권을 보조 타깃으로.")
    _hi_aov = m.sort_values('객단가', ascending=False).iloc[0] if not m.empty else None
    if _hi_aov is not None:
        _pts.append(f"**고가 라인**: 객단가 최고 **{_hi_aov['product']}({_hi_aov['객단가']/1e4:,.0f}만원)**는 "
                    "패키지·업셀 강화로 매출 레버리지가 큼.")
    for _p in _pts:
        st.markdown(f"- {_p}")


# ── 탭 1: 오늘 입력 ───────────────────────────────────────────────

def tab_input():
    ROOMS = load_rooms()
    ROOM_NUMBERS = sorted(ROOMS.keys())
    if not ROOMS:
        st.warning("채팅방이 등록되어 있지 않습니다. ⚙️ 채팅방 설정 탭에서 먼저 채팅방을 추가해주세요.")
        return
    st.header("오늘의 인원 입력")

    input_date = st.date_input("📅 날짜", value=date.today())

    # 전일 인원 사전 로드 (OCR 검토 테이블과 입력 폼에서 공용)
    df_all = load_all()
    prev = {}
    if not df_all.empty:
        today_str = str(input_date)
        df_prev = df_all[df_all['date'].astype(str) != today_str]
        if not df_prev.empty:
            prev = df_prev.sort_values('date').groupby('room_num').last()['members'].to_dict()

    # ── OCR 업로드 (선택) ──────────────────────────────────────
    st.subheader("1단계 — 스크린샷 업로드 (선택)")
    st.caption("📌 스크린샷 없이 아래 2단계에서 직접 입력해도 됩니다. 어제 값이 기본으로 채워져 있으니 바뀐 숫자만 수정하세요.")

    uploaded_files = st.file_uploader(
        "이미지 파일 선택 (PNG / JPG) — 여러 장 동시 선택 가능",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        key='screenshot_upload',
    )

    # 파일 목록이 바뀌면 OCR 상태 초기화
    current_names = [f.name for f in uploaded_files] if uploaded_files else []
    if current_names != st.session_state.uploaded_file_names:
        st.session_state.ocr_done = False
        st.session_state.ocr_results = {}
        st.session_state.uploaded_file_names = current_names

    if uploaded_files:
        from PIL import Image
        from ocr_parser import extract_from_image, get_badge_rooms

        images = []
        for f in uploaded_files:
            f.seek(0)
            images.append((f.name, Image.open(f).copy()))

        img_cols = st.columns(min(len(images), 3))
        for i, (name, img) in enumerate(images):
            with img_cols[i % 3]:
                st.image(img, caption=name, width='stretch')

        if not st.session_state.ocr_done:
            with st.spinner(f"{len(images)}장 인식 중..."):
                # ── 등록된 방 인원 인식 (ROOMS 필터 적용, 오인식 방지) ────
                merged = {}
                ocr_error = None
                try:
                    for _, img in images:
                        for r in extract_from_image(img, ROOMS):
                            if r['room_num'] not in merged:
                                merged[r['room_num']] = r['members']
                except Exception as e:
                    ocr_error = str(e)

                # ── 신규 방 후보 탐지: 배지 영역만 사용 (텍스트 오인식 차단) ──
                badge_new = {}
                try:
                    for _, img in images:
                        for rn, cnt_val in get_badge_rooms(img).items():
                            if rn not in ROOMS and rn not in badge_new:
                                badge_new[rn] = cnt_val
                except Exception:
                    pass

                st.session_state.ocr_results = merged
                st.session_state.ocr_done = True
                st.session_state._ocr_error = ocr_error
                if badge_new:
                    st.session_state._pending_new_rooms = badge_new

                for rn in ROOMS:
                    if rn in merged:
                        st.session_state[f"inp_{rn}"] = merged[rn]
                    elif prev.get(rn) is not None:
                        st.session_state[f"inp_{rn}"] = int(prev[rn])
                    else:
                        st.session_state[f"inp_{rn}"] = 0

        else:
            cnt      = len(st.session_state.ocr_results)
            total_rn = len(ROOMS)
            if cnt == total_rn:
                st.success(f"✅ {cnt}/{total_rn}개 채팅방 전체 인식 완료")
            elif cnt > 0:
                st.warning(f"⚠️ {cnt}/{total_rn}개 인식 — 미인식 방은 전일 데이터로 채워집니다. 확인 후 수정하세요.")
            else:
                st.error("❌ 채팅방을 하나도 인식하지 못했습니다. 이미지 품질을 확인하거나 직접 입력하세요.")
            if st.session_state.get('_ocr_error'):
                with st.expander("🔧 OCR 오류 상세"):
                    st.code(st.session_state._ocr_error)
            if st.button("🔄 다시 인식"):
                st.session_state.ocr_done = False
                st.session_state._pending_new_rooms = {}
                st.rerun()

        # ── 신규 채팅방 등록 확인 UI ──────────────────────────────────
        if st.session_state.get('_pending_new_rooms'):
            pending = st.session_state._pending_new_rooms
            with st.container(border=True):
                st.markdown(f"#### 🆕 새 채팅방 {len(pending)}개 감지")
                st.caption(
                    "이미지 배지에서 발견된 방입니다. **등록할 방만 체크하세요.** "
                    "OCR 오인식으로 잘못 감지된 방은 체크 해제 후 무시하세요."
                )
                selected_new = {}
                new_room_name_inputs = {}
                for rn in sorted(pending.keys()):
                    col_chk, col_cnt, col_nm = st.columns([1, 1, 3])
                    with col_chk:
                        checked = st.checkbox(f"채팅방 {rn}", key=f"chk_new_{rn}",
                                              value=True)
                        if checked:
                            selected_new[rn] = True
                    with col_cnt:
                        st.caption(f"인식 인원: {pending[rn]:,}명")
                    with col_nm:
                        new_room_name_inputs[rn] = st.text_input(
                            "방 이름",
                            value=f"채팅방 {rn}",
                            key=f"new_nm_{rn}",
                            label_visibility="collapsed",
                        )

                col_reg, col_skip = st.columns(2)
                with col_reg:
                    if st.button("✅ 선택한 방 등록", type="primary",
                                 width='stretch', key="btn_reg_new"):
                        rooms_to_add = {
                            rn: (new_room_name_inputs[rn].strip() or f"채팅방 {rn}")
                            for rn in selected_new
                        }
                        if rooms_to_add:
                            save_rooms_batch(rooms_to_add)
                            load_rooms.clear()
                            # 인식된 인원 수도 OCR 결과에 반영
                            for rn in rooms_to_add:
                                if rn in pending:
                                    st.session_state.ocr_results[rn] = pending[rn]
                                    st.session_state[f"inp_{rn}"] = pending[rn]
                        st.session_state._pending_new_rooms = {}
                        st.rerun()
                with col_skip:
                    if st.button("❌ 무시 (등록 안 함)",
                                 width='stretch', key="btn_skip_new"):
                        st.session_state._pending_new_rooms = {}
                        st.rerun()

        # ── 인식 결과 검토 테이블 ─────────────────────────────────
        if st.session_state.ocr_done:
            _show_ocr_review(st.session_state.ocr_results, ROOMS, prev)

    # ── 채팅방 빠른 관리 (잘못 등록된 방 삭제) ────────────────────
    with st.expander("🗂️ 채팅방 빠른 관리 — 잘못 등록된 방 삭제", expanded=False):
        st.caption("OCR 오인식으로 잘못 등록된 방을 여기서 바로 삭제할 수 있습니다. 이름·번호 수정은 ⚙️ 채팅방 설정 탭을 이용하세요.")
        del_cols = st.columns(3)
        for idx, rn in enumerate(ROOM_NUMBERS):
            with del_cols[idx % 3]:
                if st.button(f"🗑️ {rn} — {ROOMS[rn]}", key=f"quick_del_{rn}",
                             width='stretch'):
                    delete_room(rn)
                    load_rooms.clear()
                    st.toast(f"채팅방 {rn} 삭제 완료", icon="🗑️")
                    st.rerun()

    # ── 빠른 숫자 입력 ─────────────────────────────────────────
    with st.expander("⚡ 빠른 입력 — 숫자 목록 붙여넣기", expanded=False):
        st.caption(
            f"스크린샷 순서대로 인원 수를 입력하면 채팅방 {min(ROOM_NUMBERS)}~{max(ROOM_NUMBERS)} 순서로 자동 할당됩니다.\n"
            "공백 또는 쉼표로 구분하세요. (예: 1234 567 2100 890)"
        )
        import re as _re
        quick_text = st.text_input("인원 수 목록", placeholder="1234 567 2100 890 ...", key="quick_nums")
        if st.button("⚡ 자동 입력", key="quick_apply"):
            nums = [int(n) for n in _re.findall(r'\d+', quick_text) if 1 <= int(n) <= 99999]
            if nums:
                room_keys = sorted(ROOMS.keys())
                for i, n in enumerate(nums[:len(room_keys)]):
                    st.session_state[f"inp_{room_keys[i]}"] = n
                st.success(f"✅ {min(len(nums), len(room_keys))}개 방에 인원 입력 완료")
                st.rerun()
            else:
                st.warning("숫자를 입력해주세요.")

    # ── 인원 확인 및 수정 ──────────────────────────────────────
    st.subheader("2단계 — 인원 입력")

    _ocr_ran = st.session_state.get('ocr_done', False) and bool(st.session_state.ocr_results)
    if _ocr_ran:
        st.caption("OCR 결과를 확인하고 잘못된 숫자를 수정하세요.")
    else:
        _filled = sum(1 for rn in ROOM_NUMBERS if prev.get(rn))
        if _filled:
            st.caption(f"✅ 어제 값 {_filled}개 자동 로드됨 — 바뀐 숫자만 수정 후 저장하세요.")
        else:
            st.caption("각 채팅방의 오늘 인원을 입력하세요.")

    edited = {}
    cols = st.columns(3)

    for idx, room_num in enumerate(ROOM_NUMBERS):
        col = cols[idx % 3]
        with col:
            ocr_val  = st.session_state.ocr_results.get(room_num)
            prev_val = prev.get(room_num)

            # OCR 값 우선, 없으면 어제 값, 없으면 0
            if ocr_val is not None:
                default = int(ocr_val)
            elif prev_val is not None:
                default = int(prev_val)
            else:
                default = 0

            # help 텍스트: 값 출처 명시
            if ocr_val is not None:
                if prev_val is not None:
                    diff = int(ocr_val) - int(prev_val)
                    sign = "+" if diff >= 0 else ""
                    help_msg = f"📷 OCR 인식 | 전일: {int(prev_val):,}명 ({sign}{diff:,})"
                else:
                    help_msg = "📷 OCR 인식 | 전일 데이터 없음"
            elif prev_val is not None:
                help_msg = f"📅 전일 데이터 자동 입력 (OCR 미인식) | {int(prev_val):,}명"
            else:
                help_msg = "⚠️ 데이터 없음 — 직접 입력하세요"

            val = st.number_input(
                ROOMS[room_num],
                min_value=0,
                value=int(st.session_state.get(f"inp_{room_num}", default)),
                step=1,
                help=help_msg,
                key=f"inp_{room_num}",
            )
            edited[room_num] = val

    # ── 저장 ──────────────────────────────────────────────────
    st.subheader("3단계 — 저장")
    # 해당 날짜 데이터가 이미 존재하면 덮어쓰기 안내
    if not df_all.empty:
        _existing = df_all[df_all['date'].astype(str) == str(input_date)]
        if not _existing.empty:
            st.info(
                f"ℹ️ {input_date} 데이터가 이미 {len(_existing)}개 채팅방 저장되어 있습니다. "
                "저장하면 기존 데이터를 덮어씁니다."
            )

    # 날짜 메모 — 기존 메모 pre-fill
    _notes_all = load_date_notes()
    _existing_note = ""
    if not _notes_all.empty:
        _nr = _notes_all[_notes_all['date'].astype(str) == str(input_date)]
        if not _nr.empty:
            _existing_note = _nr['memo'].values[0]
    date_memo = st.text_input(
        "📝 오늘 메모 (선택)",
        value=_existing_note,
        placeholder="특이사항 기록 — 예: 광고 집행 시작, 이벤트 진행, 대규모 이탈 발생",
        key="date_memo_input",
    )

    col_save, col_reset = st.columns([3, 1])

    with col_save:
        if st.button("💾 저장하기", type="primary", width='stretch'):
            room_data = [
                {'room_num': rn, 'room_name': ROOMS[rn], 'members': v}
                for rn, v in edited.items()
                if v > 0
            ]
            missing_rooms = [ROOMS[rn] for rn, v in edited.items() if v == 0]
            if room_data:
                try:
                    with st.spinner("GitHub에 저장 중..."):
                        save_daily(str(input_date), room_data)
                        if date_memo.strip() or _existing_note:
                            save_date_note(str(input_date), date_memo.strip())
                    st.success(f"✅ {input_date} 데이터 저장 완료 — {len(room_data)}개 채팅방")
                    if missing_rooms:
                        st.warning(
                            f"⚠️ {len(missing_rooms)}개 채팅방이 입력되지 않았습니다:\n" +
                            "  |  ".join(missing_rooms)
                        )
                    st.session_state.ocr_done = False
                    st.session_state.ocr_results = {}
                    st.balloons()
                    # ── Slack 급감 알림 ──────────────────────────────
                    _slack_url = st.secrets.get("slack_webhook_url", "")
                    if _slack_url and prev:
                        _alerts = []
                        for _rn, _v in edited.items():
                            if _v > 0 and prev.get(_rn) is not None:
                                _pv = int(prev[_rn])
                                _diff = _v - _pv
                                _pct = abs(_diff / _pv * 100) if _pv > 0 else 0
                                if _diff < 0 and (_pct >= 10 or abs(_diff) >= 50):
                                    _alerts.append(
                                        f"• {ROOMS.get(_rn, f'채팅방{_rn}')}: "
                                        f"{_pv:,}명 → {_v:,}명 "
                                        f"({_diff:,}명, {round(_pct, 1)}% 감소)"
                                    )
                        if _alerts:
                            send_slack_alert(
                                _slack_url,
                                f"🚨 *인원 급감 알림* ({input_date})\n" + "\n".join(_alerts),
                            )
                except RuntimeError as e:
                    st.error(
                        f"❌ 저장 실패: {e}\n\n"
                        "잠시 후 다시 시도하거나, 사이드바 '🔄 데이터 새로고침' 후 재시도하세요."
                    )
            else:
                st.warning("입력된 인원이 없습니다. 숫자를 확인해주세요.")

    with col_reset:
        if st.button("초기화", width='stretch'):
            st.session_state.ocr_done = False
            st.session_state.ocr_results = {}
            st.rerun()


# ── 탭 2: 현황 대시보드 ───────────────────────────────────────────

def tab_dashboard():
    ROOMS = load_rooms()
    st.header("현황 대시보드")
    df = load_all()

    if df.empty:
        st.info("데이터가 없습니다. '오늘 입력' 탭에서 먼저 데이터를 입력해주세요.")
        return

    latest_date = df['date'].max()
    _today_str = str(date.today())

    # ── 오늘 미입력 강조 배너 ─────────────────────────────────
    if str(latest_date) < _today_str:
        st.error(
            f"📢 **오늘({_today_str}) 인원을 아직 입력하지 않았습니다!** "
            f"← '📸 오늘 입력' 탭으로 이동하여 데이터를 입력해주세요. "
            f"(최근 기록: {latest_date})"
        )

    st.caption(f"기준: {latest_date}")

    df_today = df[df['date'] == latest_date].copy()
    campaigns = get_current_campaigns()

    # ── 입력 완성도 경고 (일부 채팅방 누락) ──────────────────
    total_rooms = len(ROOMS)
    entered_rooms = len(df_today)
    if entered_rooms < total_rooms:
        missing_names = [ROOMS[rn] for rn in sorted(ROOMS.keys())
                         if rn not in df_today['room_num'].values]
        st.warning(
            f"⚠️ {latest_date} — {total_rooms - entered_rooms}개 채팅방 미입력: " +
            "  |  ".join(missing_names)
        )

    # ── 요약 지표 ──────────────────────────────────────────────
    total = int(df_today['members'].sum())
    df_changed = df_today.dropna(subset=['change'])
    net = int(df_changed['change'].sum()) if not df_changed.empty else 0
    up = int((df_changed['change'] > 0).sum()) if not df_changed.empty else 0
    down = int((df_changed['change'] < 0).sum()) if not df_changed.empty else 0

    # 입력 완수율: 첫 기록일 ~ 오늘 사이 데이터가 있는 날 비율
    first_date = df['date'].min()
    days_since = (date.today() - first_date).days + 1
    days_entered = df['date'].nunique()
    comp_rate = round(days_entered / days_since * 100, 1)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("전체 총원", f"{total:,}명")
    c2.metric("전일 대비 순증감", f"{net:+,}명")
    c3.metric("인원 증가 채팅방", f"{up}개")
    c4.metric("인원 감소 채팅방", f"{down}개")
    c5.metric("입력 완수율", f"{comp_rate}%", f"{days_entered}/{days_since}일")

    # 날짜 메모 표시
    _dash_notes = load_date_notes()
    if not _dash_notes.empty:
        _dn = _dash_notes[_dash_notes['date'].astype(str) == str(latest_date)]
        if not _dn.empty:
            st.info(f"📝 **{latest_date} 메모:** {_dn['memo'].values[0]}")

    # ── 데이터 신뢰도: 누락 날짜 감지 ──────────────────────────
    if days_since > 1:
        from datetime import timedelta as _td
        all_dates_in_range = set(
            str(first_date + _td(days=i)) for i in range(days_since)
        )
        entered_dates = set(df['date'].astype(str).unique())
        missing_dates = sorted(all_dates_in_range - entered_dates, reverse=True)
        if missing_dates:
            with st.expander(f"📅 누락 날짜 {len(missing_dates)}일 감지 — 클릭하여 확인", expanded=False):
                st.caption("아래 날짜는 데이터가 입력되지 않았습니다. 데이터 관리 탭에서 소급 입력할 수 있습니다.")
                # 최근 10개만 표시
                shown = missing_dates[:10]
                st.markdown("  ".join(f"`{d}`" for d in shown) +
                            (f"  _(외 {len(missing_dates)-10}일)_" if len(missing_dates) > 10 else ""))

    # ── 입력 현황 달력 ────────────────────────────────────────
    with st.expander("📅 입력 현황 달력 (최근 16주)", expanded=False):
        _fig_cal = calendar_heatmap_chart(df)
        if _fig_cal:
            st.plotly_chart(_fig_cal)
            _total_days = (date.today() - df['date'].min()).days + 1
            _entered_days = df['date'].nunique()
            st.caption(f"초록: 입력 완료 · 빨강: 데이터 없음 · 총 {_total_days}일 중 {_entered_days}일 입력 ({round(_entered_days/_total_days*100,1)}%)")

    # ── 증감 차트 + 상품별 분석 ───────────────────────────────
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        fig_bar = change_bar_chart(df_today, rooms=ROOMS)
        if fig_bar:
            st.plotly_chart(fig_bar)
    with col_c2:
        fig_prod = product_bar_chart(df, campaigns)
        if fig_prod:
            st.plotly_chart(fig_prod)
        elif not campaigns:
            st.info("⚙️ 채팅방 설정 탭에서 상품 정보를 등록하면 상품별 분석이 표시돼요.")

    # ── 목표 달성률 ────────────────────────────────────────────
    target_rows = [
        (rn, info)
        for rn, info in campaigns.items()
        if int(info.get('target_count', 0) or 0) > 0
    ]
    if target_rows:
        st.subheader("목표 달성 현황")
        goal_cols = st.columns(min(len(target_rows), 4))
        for i, (rn, info) in enumerate(sorted(target_rows)):
            target = int(info.get('target_count', 0))
            current_row = df_today[df_today['room_num'] == rn]
            current = int(current_row['members'].values[0]) if not current_row.empty else 0
            pct = round(current / target * 100, 1) if target else 0
            with goal_cols[i % 4]:
                st.metric(
                    label=f"{ROOMS.get(rn, f'채팅방 {rn}')}",
                    value=f"{current:,}명",
                    delta=f"목표 {pct}% ({target:,}명)",
                )

    # ── 주간 성과 랭킹 ────────────────────────────────────────────
    st.subheader("주간 성과 랭킹")
    fig_rank_top, fig_rank_bot = ranking_chart(df, rooms=ROOMS)
    if fig_rank_top or fig_rank_bot:
        rank_c1, rank_c2 = st.columns(2)
        with rank_c1:
            if fig_rank_top:
                st.plotly_chart(fig_rank_top)
            else:
                st.info("증가한 채팅방이 없습니다.")
        with rank_c2:
            if fig_rank_bot:
                st.plotly_chart(fig_rank_bot)
            else:
                st.success("감소한 채팅방이 없습니다.")
    else:
        st.info("주간 랭킹은 5일 이상 간격의 데이터가 있으면 자동으로 표시됩니다.")

    # ── 채팅방별 상세 표 ───────────────────────────────────────
    st.subheader("채팅방별 상세")

    display = df_today[['room_num', 'room_name', 'members', 'prev_members', 'change']].copy()
    display.columns = ['방 번호', '채팅방', '총원', '전일', '증감']
    display['진행 중인 강의'] = display['방 번호'].apply(
        lambda n: campaigns.get(int(n), {}).get('campaign_name', '-')
    )
    display['상품'] = display['방 번호'].apply(
        lambda n: campaigns.get(int(n), {}).get('product', '-')
    )
    display = display.sort_values('방 번호').reset_index(drop=True)

    def _style_change(series):
        return [
            'color: #2E7D32; font-weight: bold' if (not pd.isna(v) and v > 0)
            else 'color: #C62828; font-weight: bold' if (not pd.isna(v) and v < 0)
            else ''
            for v in series
        ]

    st.dataframe(
        display.style.apply(_style_change, subset=['증감']),
        hide_index=True,
        column_config={
            '총원': st.column_config.NumberColumn(format="%d명"),
            '전일': st.column_config.NumberColumn(format="%d명"),
            '증감': st.column_config.NumberColumn(format="%+d명"),
        },
    )

    # ── 텍스트 요약 ────────────────────────────────────────────
    st.subheader("요약")

    if not df_changed.empty:
        top_up = df_changed.sort_values('change', ascending=False).head(3)
        top_down = df_changed.sort_values('change').head(3)

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**인원 증가 TOP 3**")
            for _, row in top_up.iterrows():
                if row['change'] > 0:
                    camp = campaigns.get(int(row['room_num']), {}).get('campaign_name', '')
                    camp_str = f" · {camp}" if camp else ""
                    st.markdown(f"- {row['room_name']}{camp_str}: **+{int(row['change'])}명** (총 {int(row['members']):,}명)")
        with col_r:
            st.markdown("**인원 감소 TOP 3**")
            for _, row in top_down.iterrows():
                if row['change'] < 0:
                    camp = campaigns.get(int(row['room_num']), {}).get('campaign_name', '')
                    camp_str = f" · {camp}" if camp else ""
                    st.markdown(f"- {row['room_name']}{camp_str}: **{int(row['change'])}명** (총 {int(row['members']):,}명)")

    # ── 이탈률 경고 + 차트 ────────────────────────────────────
    # session_state에서 현재 임계값 읽기 (슬라이더 렌더 전에 계산에 사용)
    churn_threshold = st.session_state.get("churn_threshold", 5)
    churn_warnings: list = []

    if len(df) >= 2:
        dates_sorted = sorted(df['date'].unique())
        if len(dates_sorted) >= 2:
            # 경고 먼저 계산 (현재 threshold 기준)
            prev_date = dates_sorted[-2]
            df_prev_day = df[df['date'] == prev_date]
            for rn in df_today['room_num'].dropna().unique():
                cur_row  = df_today[df_today['room_num'] == rn]
                prev_row = df_prev_day[df_prev_day['room_num'] == rn]
                if cur_row.empty or prev_row.empty:
                    continue
                cur_m  = int(cur_row['members'].values[0])
                prev_m = int(prev_row['members'].values[0])
                if prev_m > 0 and prev_m > cur_m:
                    churn = round((prev_m - cur_m) / prev_m * 100, 1)
                    if churn >= churn_threshold:
                        churn_warnings.append(
                            f"{ROOMS.get(int(rn), f'채팅방 {rn}')} ({churn}%↓)"
                        )

            # 슬라이더 렌더 (다음 rerun부터 새 threshold 반영)
            churn_threshold = st.slider(
                "이탈률 경고 기준 (%)", min_value=1, max_value=20,
                value=churn_threshold, step=1, key="churn_threshold",
                help="전일 대비 인원 감소율이 이 값 이상이면 경고를 표시합니다."
            )
            if churn_warnings:
                st.error(
                    f"🚨 **이탈률 경고 (≥{churn_threshold}%):** " + "  |  ".join(churn_warnings) +
                    "\n\n전일 대비 인원이 기준치 이상 감소한 채팅방입니다. 콘텐츠 또는 광고 전략을 점검하세요."
                )

            # 3일 연속 이탈 경고
            if len(dates_sorted) >= 3:
                recent_3 = dates_sorted[-3:]
                declining = []
                for rn in ROOMS:
                    vals = []
                    for d in recent_3:
                        r = df[(df['date'] == d) & (df['room_num'] == rn)]
                        if not r.empty:
                            vals.append(int(r['members'].values[0]))
                    if len(vals) == 3 and vals[0] > vals[1] > vals[2]:
                        drop = vals[0] - vals[2]
                        pct = round(drop / vals[0] * 100, 1) if vals[0] > 0 else 0
                        declining.append(f"{ROOMS.get(rn, f'채팅방 {rn}')} (3일간 -{drop}명, -{pct}%)")
                if declining:
                    st.warning(
                        "📉 **3일 연속 이탈 감지:** " + "  |  ".join(declining) +
                        "\n\n최근 3일 연속으로 인원이 감소하고 있습니다. 원인을 점검하세요."
                    )

        fig_churn = churn_rate_chart(df, ROOMS, threshold=churn_threshold)
        if fig_churn:
            with st.expander("📉 이탈률 추이 차트", expanded=False):
                st.plotly_chart(fig_churn)

    # ── 채팅방별 주간 성장률 ──────────────────────────────────
    _df_dt = df.copy()
    _df_dt['date'] = pd.to_datetime(_df_dt['date'])
    _latest_dt = pd.to_datetime(latest_date)
    _week_cands = [d for d in _df_dt['date'].unique()
                   if pd.Timedelta('5 days') <= (_latest_dt - d) <= pd.Timedelta('9 days')]
    if _week_cands:
        _week_ago = max(_week_cands)
        _df_week = _df_dt[_df_dt['date'] == _week_ago]
        _growth = []
        for rn in ROOMS:
            _t = df_today[df_today['room_num'] == rn]
            _w = _df_week[_df_week['room_num'] == rn]
            if _t.empty or _w.empty:
                continue
            _cur = int(_t['members'].values[0])
            _prv = int(_w['members'].values[0])
            _rate = round((_cur - _prv) / _prv * 100, 1) if _prv > 0 else 0
            _growth.append({'name': ROOMS[rn], 'cur': _cur, 'rate': _rate})

        if _growth:
            with st.expander("📈 채팅방별 주간 성장률", expanded=False):
                st.caption(f"기준: {_week_ago.date()} → {latest_date}")
                _gcols = st.columns(min(4, len(_growth)))
                for i, g in enumerate(sorted(_growth, key=lambda x: x['rate'], reverse=True)):
                    _delta = f"+{g['rate']}%" if g['rate'] >= 0 else f"{g['rate']}%"
                    _gcols[i % 4].metric(g['name'], f"{g['cur']:,}명", _delta)

    # ── 현재 진행 중인 강의 목록 ───────────────────────────────
    if campaigns:
        st.subheader("현재 진행 중인 강의")
        camp_rows = []
        today = date.today()
        for room_num, info in sorted(campaigns.items()):
            start_str = info.get('start_date', '')
            try:
                start_dt = pd.to_datetime(start_str).date()
                day_n = (today - start_dt).days
                day_label = f"D+{day_n}"
            except Exception:
                day_label = '-'
            camp_rows.append({
                '방 번호': room_num,
                '채팅방': ROOMS.get(room_num, f'채팅방 {room_num}'),
                '강의명': info.get('campaign_name', '-'),
                '상품': info.get('product', '-'),
                '기수': info.get('cohort', '-'),
                '시작일': info.get('start_date', '-'),
                'D+N': day_label,
                '메모': info.get('memo', '-'),
            })
        st.dataframe(pd.DataFrame(camp_rows), hide_index=True)

    # ── 주간 요약 리포트 ──────────────────────────────────────
    with st.expander("📋 주간 요약 리포트", expanded=False):
        st.caption("클릭 후 Ctrl+A → Ctrl+C 로 전체 복사하여 공유하세요.")

        df_dt = df.copy()
        df_dt['date'] = pd.to_datetime(df_dt['date'])
        latest_dt = pd.to_datetime(latest_date)
        latest_total = int(df_today['members'].sum())

        # 5~9일 전 범위에서 가장 가까운 날짜 탐색
        week_cands = [d for d in df_dt['date'].unique()
                      if pd.Timedelta('5 days') <= (latest_dt - d) <= pd.Timedelta('9 days')]

        lines = []
        if week_cands:
            wa_dt   = max(week_cands)
            wa_str  = str(wa_dt.date())
            wa_total = int(df_dt[df_dt['date'] == wa_dt]['members'].sum())
            diff     = latest_total - wa_total
            diff_s   = f"+{diff:,}" if diff >= 0 else f"{diff:,}"
            lines.append(f"📊 주간 요약  {wa_str} → {latest_date}")
            lines.append(f"전체 총원: {latest_total:,}명  ({diff_s}명 전주 대비)")
        else:
            lines.append(f"📊 현황 요약  {latest_date}")
            lines.append(f"전체 총원: {latest_total:,}명")

        lines.append("")

        df_chg = df_today.dropna(subset=['change'])
        top_up = df_chg[df_chg['change'] > 0].sort_values('change', ascending=False).head(3)
        top_dn = df_chg[df_chg['change'] < 0].sort_values('change').head(3)

        if not top_up.empty:
            lines.append("▲ 인원 증가 TOP 3")
            for _, r in top_up.iterrows():
                nm = ROOMS.get(int(r['room_num']), f"채팅방 {r['room_num']}")
                lines.append(f"  {nm}  +{int(r['change']):,}명 → {int(r['members']):,}명")
            lines.append("")

        if not top_dn.empty:
            lines.append("▼ 인원 감소 TOP 3")
            for _, r in top_dn.iterrows():
                nm = ROOMS.get(int(r['room_num']), f"채팅방 {r['room_num']}")
                lines.append(f"  {nm}  {int(r['change']):,}명 → {int(r['members']):,}명")
            lines.append("")

        if churn_warnings:
            lines.append(f"⚠️ 이탈률 경고 (기준 ≥{churn_threshold}%)")
            for w in churn_warnings:
                lines.append(f"  {w}")
        else:
            lines.append(f"✅ 이탈률 경고 없음 (기준 ≥{churn_threshold}%)")

        if campaigns:
            lines.append("")
            lines.append("📚 진행 중인 강의")
            for rn, info in sorted(campaigns.items()):
                nm    = ROOMS.get(rn, f"채팅방 {rn}")
                cname = info.get('campaign_name', '-')
                mem_row = df_today[df_today['room_num'] == rn]
                mem = f"{int(mem_row['members'].values[0]):,}명" if not mem_row.empty else "-"
                lines.append(f"  {nm} ({cname}): {mem}")

        st.text_area(
            "요약 텍스트",
            value="\n".join(lines),
            height=300,
            key="weekly_summary_ta",
        )


# ── 탭 3: 전환 분석 ──────────────────────────────────────────────

def tab_conversion():
    ROOMS = load_rooms()
    st.header("전환 분석")
    st.caption("무료 특강 모객 → 유료 수강 전환을 강의 집계 실데이터로 분석하고, "
               "일별 신청·수강확정도 함께 기록합니다.")

    # ══ 실데이터 전환 (강의 집계: 무료 모객 → 유료 수강) ═══════════
    _csum = load_course_summary()
    if not _csum.empty:
        st.subheader("🔻 무료 특강 → 유료 수강 전환 (전체 실적)")
        st.caption("아임웹 강의 집계 기준. 무료 특강으로 모은 인원이 실제 유료 수강으로 "
                   "이어진 비율입니다. (세트합계·멤버십 제외)")
        _tf = int(_csum['free'].sum())
        _ts = int(_csum['students'].sum())   # 세트 수강생(매출 기준과 정합)
        _tr = int(_csum['revenue'].sum())
        _cv = (_ts / _tf * 100) if _tf else 0
        kk1, kk2, kk3, kk4 = st.columns(4)
        kk1.metric("무료 특강 모객", f"{_tf:,}명", help="무료 특강 신청 건수(중복 신청 포함)")
        kk2.metric("유료 수강생", f"{_ts:,}명",
                   help=f"세트 수강생(멤버십 제외). 유료 결제 건수는 {int(_csum['paid'].sum()):,}건")
        kk3.metric("종합 전환율", f"{_cv:.1f}%", help="세트 수강생 ÷ 무료 신청")
        kk4.metric("누적 매출", f"{_tr/1e8:,.1f}억원")

        cvc1, cvc2 = st.columns([1, 1.25])
        with cvc1:
            _ff = overall_conversion_funnel(_tf, _ts)
            if _ff:
                st.plotly_chart(_ff, key="conv_overall_funnel")
        with cvc2:
            _fp = product_conversion_rate_chart(_csum)
            if _fp:
                st.plotly_chart(_fp, key="conv_prod_rate")
        # 최고 전환 상품 인사이트
        _cc = _csum.copy()
        _cc['cv'] = _cc['students'] / _cc['free'].replace(0, pd.NA)
        _cc = _cc.dropna(subset=['cv'])
        if not _cc.empty:
            _bp = _cc.loc[_cc['cv'].idxmax()]
            st.info(f"💡 **{_bp['product']}**의 무료→유료 전환율이 **{_bp['cv']*100:.1f}%**로 가장 높습니다 — "
                    "무료 모객을 늘릴수록 유료 성과가 가장 잘 따라오는 상품군입니다.")
        st.divider()
        st.subheader("📋 일별 신청·수강 확정 기록")
        st.caption("아래는 채팅방별로 **일 단위 신청자·수강확정**을 수기 입력해 추적하는 영역입니다. "
                   "입력한 방만 그래프에 나타납니다.")

    campaigns = get_current_campaigns()
    if not campaigns:
        st.info("⚙️ 채팅방 설정 탭에서 진행 중인 강의를 먼저 등록해주세요.")
        return

    df_members = load_all()
    df_conv    = load_conversions()

    # ── 요약 지표 ──────────────────────────────────────────────
    latest_conv = get_latest_conversions()
    if not latest_conv.empty:
        total_applicants = int(latest_conv['applicants'].sum())
        total_confirmed  = int(latest_conv['confirmed'].sum())
        total_revenue    = int(latest_conv['revenue'].sum())
        conv_rate = round(total_confirmed / total_applicants * 100, 1) if total_applicants > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 신청자", f"{total_applicants:,}명")
        c2.metric("총 수강 확정", f"{total_confirmed:,}명")
        c3.metric("수강 전환율", f"{conv_rate}%")
        c4.metric("총 매출", f"{total_revenue:,}원")

        st.divider()

    # ── 퍼널 차트 ──────────────────────────────────────────────
    fig_funnel = funnel_chart(df_members, df_conv, campaigns, rooms=ROOMS)
    if fig_funnel:
        st.plotly_chart(fig_funnel)

    # ── 전환율 차트 ────────────────────────────────────────────
    fig_conv = conversion_rate_chart(df_conv, campaigns, rooms=ROOMS)
    if fig_conv:
        st.plotly_chart(fig_conv)

    # ── 기수별 전환율 비교 ─────────────────────────────────────
    fig_cohort_conv = cohort_conversion_chart(df_conv, campaigns, rooms=ROOMS)
    if fig_cohort_conv:
        st.plotly_chart(fig_cohort_conv)
    elif not df_conv.empty:
        st.info("전환 데이터를 입력하면 강의별 신청·수강확정·전환율 비교 차트가 표시됩니다.")

    # ── 전환 데이터 입력 ───────────────────────────────────────
    st.subheader("전환 데이터 입력")
    st.caption("강의별 신청자·수강 확정·매출을 기록합니다. 같은 방+날짜로 다시 저장하면 덮어씁니다.")

    with st.form("conversion_form"):
        col1, col2 = st.columns(2)
        with col1:
            conv_room = st.selectbox(
                "채팅방 (강의)",
                options=sorted(campaigns.keys()),
                format_func=lambda x: f"{ROOMS.get(x, f'채팅방 {x}')} — {campaigns[x].get('campaign_name', '')}",
            )
            conv_date = st.date_input("기준 날짜", value=date.today())
            applicants = st.number_input("신청자 수", min_value=0, step=1, value=0)
        with col2:
            confirmed = st.number_input("수강 확정자 수", min_value=0, step=1, value=0)
            revenue   = st.number_input("매출 (원)", min_value=0, step=10000, value=0,
                                        help="수강료 합계. 0이면 미입력.")
            conv_memo = st.text_input("메모", placeholder="특이사항 등")

        if st.form_submit_button("💾 저장", type="primary", width='stretch'):
            save_conversion(
                room_num=conv_room,
                date_str=str(conv_date),
                applicants=int(applicants),
                confirmed=int(confirmed),
                revenue=int(revenue),
                memo=conv_memo.strip(),
            )
            st.success(f"✅ {ROOMS.get(conv_room, f'채팅방 {conv_room}')} 전환 데이터 저장 완료")
            st.rerun()

    # ── 전환 이력 테이블 ───────────────────────────────────────
    if not df_conv.empty:
        st.subheader("전환 이력")
        disp = df_conv.copy()
        disp['채팅방'] = disp['room_num'].apply(lambda x: ROOMS.get(int(x), f"채팅방 {x}"))
        disp['강의명'] = disp['room_num'].apply(lambda x: campaigns.get(int(x), {}).get('campaign_name', '-'))
        disp['신청전환율'] = disp.apply(
            lambda r: f"{round(r['confirmed']/r['applicants']*100,1)}%"
            if r['applicants'] > 0 else '-', axis=1
        )
        disp = disp[['date', '채팅방', '강의명', 'applicants', 'confirmed', '신청전환율', 'revenue', 'memo']]
        disp.columns = ['날짜', '채팅방', '강의명', '신청자', '수강확정', '전환율', '매출(원)', '메모']
        disp = disp.sort_values('날짜', ascending=False).reset_index(drop=True)
        st.dataframe(disp, hide_index=True)
        conv_del_idx = st.number_input(
            "삭제할 행 번호 (0부터, 최신순 기준)",
            min_value=0, max_value=max(0, len(df_conv) - 1),
            step=1, key="conv_del_idx",
        )
        if st.button("🗑️ 전환 데이터 삭제", key="conv_del_btn", type="secondary"):
            delete_conversion_row(int(conv_del_idx))
            st.success("삭제 완료")
            st.rerun()

    st.divider()

    # ── 광고비 ROI 분석 ────────────────────────────────────────
    st.subheader("광고비 ROI 분석")
    st.caption("채널별 광고비를 입력하면 ROAS·CPA를 자동 계산합니다.")

    df_adspend = load_adspend()

    # ROI 요약 지표
    if not df_adspend.empty and not df_conv.empty:
        total_spend = int(df_adspend['spend'].sum())
        latest_rev  = get_latest_conversions()
        total_rev   = int(latest_rev['revenue'].sum()) if not latest_rev.empty else 0
        total_conf  = int(latest_rev['confirmed'].sum()) if not latest_rev.empty else 0
        roas = round(total_rev / total_spend, 2) if total_spend > 0 else 0
        cpa  = round(total_spend / total_conf) if total_conf > 0 else 0

        r1, r2, r3 = st.columns(3)
        r1.metric("총 광고비", f"{total_spend:,}원")
        r2.metric("ROAS", f"{roas}x", help="매출 ÷ 광고비")
        r3.metric("CPA", f"{cpa:,}원", help="광고비 ÷ 수강 확정자")

    # ROI 차트
    fig_roi = roi_chart(df_adspend, df_conv, campaigns, ROOMS)
    if fig_roi:
        st.plotly_chart(fig_roi)

    # ── CPM 분석 ──────────────────────────────────────────────────
    if not df_adspend.empty and not df_members.empty:
        st.subheader("CPM 분석 (광고비 ÷ 인원증가)")
        st.caption("채팅방별 광고비 대비 인원 증가 효율을 비교합니다. 낮을수록 효율적입니다.")
        fig_cpm = cpm_chart(df_members, df_adspend, ROOMS)
        if fig_cpm:
            st.plotly_chart(fig_cpm)

    # 광고비 입력 폼
    with st.expander("📝 광고비 입력", expanded=df_adspend.empty):
        with st.form("adspend_form"):
            col1, col2 = st.columns(2)
            with col1:
                ad_room = st.selectbox(
                    "채팅방 (강의)",
                    options=sorted(campaigns.keys()),
                    format_func=lambda x: f"{ROOMS.get(x, f'채팅방 {x}')} — {campaigns[x].get('campaign_name', '')}",
                    key="ad_room",
                )
                ad_date    = st.date_input("집행 날짜", value=date.today(), key="ad_date")
                ad_channel = st.selectbox("광고 채널", options=CHANNEL_OPTIONS, key="ad_channel")
            with col2:
                ad_spend = st.number_input("광고비 (원)", min_value=0, step=10000, value=0, key="ad_spend")
                ad_imps  = st.number_input("노출수", min_value=0, step=100, value=0, key="ad_imps")
                ad_clicks = st.number_input("클릭수", min_value=0, step=10, value=0, key="ad_clicks")
                ad_memo  = st.text_input("메모", placeholder="캠페인명 등", key="ad_memo")

            if st.form_submit_button("💾 광고비 저장", type="primary", width='stretch'):
                save_adspend(
                    room_num=ad_room, date_str=str(ad_date),
                    channel=ad_channel, spend=int(ad_spend),
                    impressions=int(ad_imps), clicks=int(ad_clicks),
                    memo=ad_memo.strip(),
                )
                st.success(f"✅ 광고비 저장 완료: {ad_channel} {int(ad_spend):,}원")
                st.rerun()

    # 광고비 이력 테이블
    if not df_adspend.empty:
        with st.expander("광고비 이력", expanded=False):
            ad_disp = df_adspend.copy()
            ad_disp['채팅방'] = ad_disp['room_num'].apply(lambda x: ROOMS.get(int(x), f"채팅방 {x}"))
            ad_disp['강의명'] = ad_disp['room_num'].apply(
                lambda x: campaigns.get(int(x), {}).get('campaign_name', '-')
            )
            ad_disp = ad_disp[['date', '채팅방', '강의명', 'channel', 'spend', 'impressions', 'clicks', 'memo']]
            ad_disp.columns = ['날짜', '채팅방', '강의명', '채널', '광고비(원)', '노출수', '클릭수', '메모']
            ad_disp = ad_disp.sort_values('날짜', ascending=False).reset_index(drop=True)
            st.dataframe(ad_disp, hide_index=True)
            ad_del_idx = st.number_input(
                "삭제할 행 번호 (0부터, 최신순 기준)",
                min_value=0, max_value=max(0, len(df_adspend) - 1),
                step=1, key="ad_del_idx",
            )
            if st.button("🗑️ 광고비 데이터 삭제", key="ad_del_btn", type="secondary"):
                delete_adspend_row(int(ad_del_idx))
                st.success("삭제 완료")
                st.rerun()

    # ── 콘텐츠 기록 ────────────────────────────────────────────────
    st.divider()
    st.subheader("콘텐츠 기록")
    st.caption("발행한 콘텐츠(영상·카드뉴스·블로그 등)를 날짜별로 기록합니다. 추이 그래프에 발행일이 오버레이로 표시됩니다.")

    df_content = load_content()

    with st.expander("📝 콘텐츠 입력", expanded=df_content.empty):
        with st.form("content_form"):
            col1, col2 = st.columns(2)
            with col1:
                c_date    = st.date_input("발행 날짜", value=date.today(), key="c_date")
                c_channel = st.selectbox("채널", options=CHANNEL_OPTIONS, key="c_channel")
                c_type    = st.selectbox("콘텐츠 유형", options=CONTENT_TYPE_OPTIONS, key="c_type")
            with col2:
                c_title = st.text_input("제목", placeholder="영상·게시물 제목", key="c_title")
                c_url   = st.text_input("URL", placeholder="https://...", key="c_url")
                c_memo  = st.text_input("메모", placeholder="특이사항", key="c_memo")

            if st.form_submit_button("💾 콘텐츠 저장", type="primary", width='stretch'):
                if not c_title.strip():
                    st.error("제목을 입력해주세요.")
                else:
                    save_content(
                        date_str=str(c_date), channel=c_channel,
                        content_type=c_type, title=c_title.strip(),
                        url=c_url.strip(), memo=c_memo.strip(),
                    )
                    st.success(f"✅ 콘텐츠 기록 저장 완료 — {c_channel} '{c_title.strip()}'")
                    st.rerun()

    if not df_content.empty:
        with st.expander("📋 콘텐츠 이력", expanded=False):
            c_disp = df_content.sort_values('date', ascending=False).reset_index()
            c_disp.columns = ['원본idx', '날짜', '채널', '유형', '제목', 'URL', '메모']
            st.dataframe(
                c_disp[['날짜', '채널', '유형', '제목', 'URL', '메모']],
                hide_index=True,
            )
            st.caption(f"총 {len(df_content)}건 기록됨")

            # 개별 삭제
            del_idx = st.number_input(
                "삭제할 행 번호 (0부터 시작, 최신순 정렬 기준)",
                min_value=0, max_value=max(0, len(df_content) - 1),
                step=1, key="content_del_idx",
            )
            if st.button("🗑️ 해당 행 삭제", key="content_del_btn", type="secondary"):
                # 최신순 정렬 후 del_idx번째 행의 원래 인덱스 추출
                sorted_df = df_content.sort_values('date', ascending=False).reset_index()
                real_idx = int(sorted_df.iloc[del_idx]['index'])
                delete_content_row(real_idx)
                st.success("삭제 완료")
                st.rerun()

    # ── 콘텐츠 효과 분석 ──────────────────────────────────────────
    if not df_content.empty and not df_members.empty:
        st.divider()
        st.subheader("📊 콘텐츠 효과 분석")
        st.caption("콘텐츠 발행일 기준 전후 3일 평균 인원을 비교합니다. (데이터가 없는 날짜는 제외)")

        df_m = df_members.copy()
        df_m['date'] = pd.to_datetime(df_m['date'])

        effect_rows = []
        for _, crow in df_content.sort_values('date', ascending=False).iterrows():
            pub_dt = pd.to_datetime(crow['date'])
            before_mask = (df_m['date'] >= pub_dt - pd.Timedelta(days=3)) & (df_m['date'] < pub_dt)
            after_mask  = (df_m['date'] > pub_dt) & (df_m['date'] <= pub_dt + pd.Timedelta(days=3))

            before_total = df_m[before_mask].groupby('date')['members'].sum()
            after_total  = df_m[after_mask].groupby('date')['members'].sum()

            if before_total.empty or after_total.empty:
                continue

            avg_before = round(before_total.mean())
            avg_after  = round(after_total.mean())
            diff       = avg_after - avg_before
            pct        = round(diff / avg_before * 100, 1) if avg_before > 0 else 0

            effect_rows.append({
                '날짜':       str(crow['date']),
                '채널':       crow.get('channel', '-'),
                '유형':       crow.get('content_type', '-'),
                '제목':       crow.get('title', '-'),
                '발행전 평균': f"{int(avg_before):,}명",
                '발행후 평균': f"{int(avg_after):,}명",
                '변화량':     f"+{int(diff):,}" if diff >= 0 else f"{int(diff):,}",
                '변화율':     f"+{pct}%" if pct >= 0 else f"{pct}%",
            })

        if effect_rows:
            st.dataframe(pd.DataFrame(effect_rows), hide_index=True)
        else:
            st.info("발행일 전후 3일 내 인원 데이터가 충분하지 않아 분석할 수 없습니다.")

    # ── 콘텐츠 상관 분석표 ────────────────────────────────────────
    if not df_content.empty and not df_members.empty:
        st.divider()
        st.subheader("📈 콘텐츠 발행 후 인원 변화 (+1일/+3일/+7일)")
        st.caption("콘텐츠 발행일 기준으로 전체 채팅방 합산 인원 변화량을 보여줍니다.")
        df_impact = content_impact_table(df_members, df_content)
        if df_impact is not None and not df_impact.empty:
            st.dataframe(df_impact, hide_index=True)
        else:
            st.info("발행일 기준 +1/+3/+7일 인원 데이터가 충분하지 않습니다.")


# ── 탭 3: 추이 그래프 ─────────────────────────────────────────────

def tab_trend():
    ROOMS = load_rooms()
    st.header("인원 추이 그래프")
    df = load_all()

    if df.empty:
        st.info("데이터가 없습니다.")
        return

    all_rooms = sorted(df['room_num'].unique().tolist())
    min_date = df['date'].min()
    max_date = df['date'].max()

    # ── 필터 바 ────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        selected = st.multiselect(
            "채팅방 선택 (비워두면 전체)",
            options=all_rooms,
            format_func=lambda x: ROOMS.get(x, f"채팅방 {x}"),
        )
    with col_f2:
        date_from = st.date_input("시작일", value=min_date, min_value=min_date, max_value=max_date)
    with col_f3:
        date_to = st.date_input("종료일", value=max_date, min_value=min_date, max_value=max_date)

    # 필터 적용
    df_filtered = df[(df['date'] >= date_from) & (df['date'] <= date_to)]
    filter_rooms = selected if selected else all_rooms
    df_filtered = df_filtered[df_filtered['room_num'].isin(filter_rooms)]

    # 선택 방의 목표 인원 조회
    campaigns = get_current_campaigns()
    targets = {
        rn: int(info.get('target_count', 0) or 0)
        for rn, info in campaigns.items()
        if rn in filter_rooms
    }

    # 광고·콘텐츠 오버레이 날짜 준비 (선택된 날짜 범위 내)
    df_adspend_trend = load_adspend()
    df_content_trend = load_content()
    ad_dates: list = []
    content_dates: list = []
    if not df_adspend_trend.empty:
        ad_dates = [
            d for d in df_adspend_trend['date'].unique()
            if date_from <= d <= date_to
        ]
    if not df_content_trend.empty:
        content_dates = [
            d for d in df_content_trend['date'].unique()
            if date_from <= d <= date_to
        ]

    # 라인 차트 (목표 인원 점선 + 광고·콘텐츠 발행일 오버레이)
    fig_line = trend_line_chart(df_filtered, filter_rooms, targets=targets,
                                rooms=ROOMS, ad_dates=ad_dates,
                                content_dates=content_dates)
    if fig_line:
        st.plotly_chart(fig_line)

    # 전체 합계 막대 차트
    fig_total = total_trend_bar(df_filtered)
    if fig_total:
        st.plotly_chart(fig_total)

    # ── 주간 비교 차트 ──────────────────────────────────────────
    fig_week = weekly_comparison_chart(df_filtered, rooms=ROOMS)
    if fig_week:
        st.plotly_chart(fig_week)
    else:
        st.info("주간 비교는 5일 이상 간격의 데이터가 있으면 자동으로 표시됩니다.")

    # ── D+N 모객 곡선 ───────────────────────────────────────────
    st.subheader("강의별 모객 곡선 비교 (D+N일 기준)")
    cohort_mode = st.radio("표시 방식", ["절대값", "순증감"], horizontal=True, key="cohort_mode")
    fig_cohort = cohort_trend_chart(df, campaigns, rooms=ROOMS, mode=cohort_mode)
    if fig_cohort:
        st.plotly_chart(fig_cohort)
    else:
        st.info("⚙️ 채팅방 설정 탭에서 강의를 등록하면 모객 곡선이 표시됩니다.")

    # ── 주간 집계 ────────────────────────────────────────────────
    st.subheader("주간 평균 인원 추이")
    fig_weekly = weekly_aggregate_chart(df_filtered, rooms=ROOMS)
    if fig_weekly:
        st.plotly_chart(fig_weekly)
    else:
        st.info("주간 집계는 7일 이상의 데이터가 있으면 자동으로 표시됩니다.")

    # ── 월간 집계 ────────────────────────────────────────────────
    st.subheader("월간 순증감 현황")
    fig_monthly = monthly_aggregate_chart(df_filtered, rooms=ROOMS)
    if fig_monthly:
        st.plotly_chart(fig_monthly)
    else:
        st.info("월간 집계는 30일 이상의 데이터가 있으면 자동으로 표시됩니다.")

    # ── 인원 예측 ────────────────────────────────────────────────
    st.subheader("인원 추이 예측 (7일)")
    forecast_rooms = st.multiselect(
        "예측할 채팅방 선택 (비워두면 전체)",
        options=filter_rooms,
        format_func=lambda x: ROOMS.get(x, f"채팅방 {x}"),
        key="forecast_rooms",
    )
    forecast_targets = forecast_rooms if forecast_rooms else filter_rooms
    fig_forecast = trend_forecast_chart(df, forecast_targets, rooms=ROOMS, forecast_days=7)
    if fig_forecast:
        st.plotly_chart(fig_forecast)
    else:
        st.info("예측 차트는 채팅방별 21일 이상의 데이터가 있으면 자동으로 표시됩니다.")

    # ── 날짜 메모 ───────────────────────────────────────────────
    _trend_notes = load_date_notes()
    if not _trend_notes.empty:
        _tn_filtered = _trend_notes[
            (_trend_notes['date'] >= date_from) &
            (_trend_notes['date'] <= date_to)
        ].sort_values('date', ascending=False)
        if not _tn_filtered.empty:
            with st.expander(f"📝 날짜 메모 ({len(_tn_filtered)}건, 선택 기간 내)", expanded=False):
                _tn_disp = _tn_filtered.copy()
                _tn_disp['date'] = _tn_disp['date'].astype(str)
                _tn_disp.columns = ['날짜', '메모']
                st.dataframe(_tn_disp, hide_index=True)


# ── 탭: 강의 분석 ────────────────────────────────────────────────

def tab_lecture_analysis():
    ROOMS    = load_all_room_names()   # 활성 + 종료 방 통합 이름
    df_all   = load_all()
    df_camps = load_campaigns()
    df_arch  = load_archived_rooms()

    st.header("🎓 강의 분석")
    st.caption("기수별 모객 효율·개강 후 잔류율·채팅방 운영 이력을 한눈에 비교합니다.")

    if df_all.empty or df_camps.empty:
        st.info("데이터가 없습니다. 강의 정보를 등록하고 인원 데이터를 입력해주세요.")
        return

    # ── 상품 필터 ─────────────────────────────────────────────
    products = sorted(df_camps['product'].dropna().unique().tolist())
    sel_product = st.selectbox(
        "상품 선택 (전체 비교 또는 특정 상품)",
        options=["전체"] + products,
        key="lecture_product_filter",
    )
    product_arg = None if sel_product == "전체" else sel_product

    # 활성 + 종료 캠페인 모두 포함
    df_camps_all = df_camps.copy()

    # ── 0. 모객 → 유료 전환 퍼널 ──────────────────────────────
    st.divider()
    st.subheader("🔻 모객 → 유료 전환 퍼널")
    st.caption("무료 웨비나 방 인원이 실제 유료 등록으로 이어진 비율입니다. "
               "웨비나 최고인원은 자동 계산되고, 유료 등록·매출은 아래에서 입력합니다.")

    df_enroll = load_enrollments()
    funnel_df = cohort_funnel_data(df_all, df_camps_all, df_enroll, rooms=ROOMS)
    if product_arg and not funnel_df.empty:
        funnel_df = funnel_df[funnel_df['product'] == product_arg]

    _has_conv = (not funnel_df.empty) and funnel_df['conversion'].notna().any()
    if _has_conv:
        # KPI 요약: 등록 데이터가 있는 기수 기준
        _fd = funnel_df[funnel_df['conversion'].notna()]
        _tot_peak = int(_fd['webinar_peak'].sum())
        _tot_enr  = int(_fd['enrolled'].sum())
        _tot_rev  = int(_fd['revenue'].sum())
        _avg_conv = round(_tot_enr / _tot_peak * 100, 2) if _tot_peak > 0 else 0
        fk1, fk2, fk3, fk4 = st.columns(4)
        fk1.metric("웨비나 최고인원 합", f"{_tot_peak:,}명")
        fk2.metric("유료 등록 합", f"{_tot_enr:,}명")
        fk3.metric("평균 전환율", f"{_avg_conv:.2f}%")
        fk4.metric("등록 매출 합", f"{_tot_rev:,}원" if _tot_rev > 0 else "—")

        # 기수별 전환율 막대 비교
        fig_conv_bar = cohort_conversion_bar_chart(funnel_df, product_arg)
        if fig_conv_bar:
            st.plotly_chart(fig_conv_bar)

        # 개별 기수 퍼널 (등록 데이터 있는 기수만 선택지 제공)
        _opts = [f"{r['product']} {r['cohort']}" for _, r in _fd.iterrows()]
        _sel = st.selectbox("기수별 상세 퍼널", options=_opts, key="funnel_cohort_sel")
        if _sel:
            _row = _fd[(_fd['product'] + ' ' + _fd['cohort']) == _sel].iloc[0]
            fig_funnel = conversion_funnel_chart(
                _row['product'], _row['cohort'],
                int(_row['webinar_peak']), int(_row['enrolled']), int(_row['revenue']),
            )
            if fig_funnel:
                st.plotly_chart(fig_funnel)
    else:
        st.info("아직 유료 등록 데이터가 없습니다. 아래에서 기수별 등록 인원을 입력하면 "
                "웨비나 최고인원과 자동 결합해 전환 퍼널이 표시됩니다.")

    # 유료 등록 입력/수정 (개인정보 없이 집계만)
    with st.expander("✏️ 유료 등록·매출 입력 / 수정", expanded=not _has_conv):
        st.caption("수강생 명단의 **집계 숫자만** 입력하세요 (이름·연락처 등 개인정보 입력 금지).")
        # 기수 목록: 캠페인 기준
        _camp_keys = (df_camps_all[['product', 'cohort']]
                      .drop_duplicates().sort_values(['product', 'cohort']))
        _key_opts = [f"{r['product']} {r['cohort']}" for _, r in _camp_keys.iterrows()]
        with st.form("enroll_form"):
            ec1, ec2, ec3 = st.columns([2, 1, 1])
            with ec1:
                _sel_key = st.selectbox("상품·기수", options=_key_opts, key="enroll_key")
            # 기존 값 자동 로드
            _cur_enr, _cur_rev = 0, 0
            if _sel_key and not df_enroll.empty:
                _p, _c = _sel_key.rsplit(' ', 1)
                _m = df_enroll[(df_enroll['product'] == _p) & (df_enroll['cohort'] == _c)]
                if not _m.empty:
                    _cur_enr = int(_m.iloc[0]['enrolled']); _cur_rev = int(_m.iloc[0]['revenue'])
            with ec2:
                _enr = st.number_input("유료 등록 인원", min_value=0, step=1, value=_cur_enr)
            with ec3:
                _rev = st.number_input("등록 매출(원)", min_value=0, step=100000, value=_cur_rev)
            if st.form_submit_button("저장", type="primary", width='stretch'):
                _p, _c = _sel_key.rsplit(' ', 1)
                save_enrollment(_p, _c, int(_enr), int(_rev))
                st.success(f"{_sel_key} — 등록 {_enr}명 저장 완료")
                st.rerun()

    # ── 1. 기수별 모객 곡선 ───────────────────────────────────
    st.divider()
    st.subheader("📈 기수별 모객 곡선 비교")
    st.caption("모객 시작일(D+0) 기준 각 기수의 인원 증가 궤적입니다. "
               "💡 위에서 **상품을 선택하면** 같은 상품의 기수끼리 선명하게 비교됩니다.")

    # '전체'는 곡선이 겹쳐 스파게티가 되므로 진행 중인 기수만 표시
    if product_arg is None:
        _recruit_camps = df_camps_all[df_camps_all['is_current'] == True]
        st.caption("현재 **진행 중인 기수**만 표시 중입니다. 종료 기수까지 보려면 상품을 선택하세요.")
    else:
        _recruit_camps = df_camps_all

    fig_recruit = recruitment_curve_chart(df_all, _recruit_camps, product_arg, rooms=ROOMS)
    if fig_recruit:
        st.plotly_chart(fig_recruit)
    else:
        st.info("강의 정보가 등록된 채팅방의 인원 데이터가 필요합니다.")

    # ── 2. 개강 후 잔류율 ─────────────────────────────────────
    st.divider()
    st.subheader("📉 개강 후 잔류율")
    st.caption("개강일 인원 = 100% 기준, 이후 날짜별 남아 있는 비율입니다.")

    has_lecture_date = df_camps_all['lecture_start_date'].astype(str).str.strip().ne('').any()
    if has_lecture_date:
        fig_ret = retention_after_opening_chart(df_all, df_camps_all, product_arg)
        if fig_ret:
            st.plotly_chart(fig_ret)
        else:
            st.info("개강일이 설정된 강의의 데이터가 필요합니다.")
    else:
        st.info("⚙️ 채팅방 설정 탭에서 각 강의의 **개강일**을 입력하면 잔류율 분석이 활성화됩니다.")

    # ── 3. 기수 효율 요약 표 ──────────────────────────────────
    st.divider()
    st.subheader("📊 기수별 모객 효율 요약")
    st.caption("회의 자료로 활용하세요. 표를 클릭하면 정렬 가능합니다.")

    eff_df = cohort_efficiency_df(df_all, df_camps_all, rooms=ROOMS)
    if product_arg and not eff_df.empty:
        eff_df = eff_df[eff_df['상품'] == product_arg]

    if not eff_df.empty:
        # 컬럼 색상 스타일링
        def _style_status(series):
            return ['color:#2E7D32;font-weight:bold' if v == '진행 중'
                    else 'color:#9E9E9E' for v in series]

        styled = eff_df.style.apply(_style_status, subset=['상태'])
        st.dataframe(styled, hide_index=True)

        # CSV 다운로드
        csv_bytes = eff_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 효율 요약 CSV 다운로드",
            data=csv_bytes,
            file_name=f"강의_모객_효율_{date.today()}.csv",
            mime='text/csv',
        )
    else:
        st.info("표시할 데이터가 없습니다.")

    # ── 4. 종료된 채팅방 이력 ─────────────────────────────────
    st.divider()
    st.subheader("🗂️ 운영 종료된 채팅방 이력")

    if df_arch.empty:
        st.info("운영 종료 처리된 채팅방이 없습니다.")
    else:
        # members 전체를 room_num으로 사전 그룹화 (O(N×M) → O(1) 조회)
        _members_by_room = {
            rn_: grp for rn_, grp in df_all.groupby('room_num')
        } if not df_all.empty else {}

        for _, ar in df_arch.sort_values('archived_date', ascending=False).iterrows():
            rn        = int(ar['room_num'])
            rname     = ar['room_name']
            arch_dt   = ar['archived_date']
            _raw_actual = ar.get('actual_close_date', '')
            actual_dt = '' if pd.isna(_raw_actual) else str(_raw_actual).strip()
            final_m   = int(ar['final_members'])
            reason    = ar['archive_reason']

            # 해당 방의 전체 인원 이력
            rdf = _members_by_room.get(rn, pd.DataFrame()).sort_values('date') if rn in _members_by_room else pd.DataFrame()
            first_m = int(rdf.iloc[0]['members']) if not rdf.empty else 0
            peak_m  = int(rdf['members'].max())   if not rdf.empty else 0
            days    = int((rdf['date'].max() - rdf['date'].min()).days) + 1 if len(rdf) > 1 else 1
            net     = final_m - first_m
            net_s   = f"+{net:,}" if net >= 0 else f"{net:,}"

            # 캠페인 이력
            camp_hist = df_camps[df_camps['room_num'] == rn]

            close_label = actual_dt if actual_dt else arch_dt
            exp_title = f"**{rname}** (채팅방 {rn}) — 종료일: {close_label}"
            exp_title += " ✅" if not camp_hist.empty else " ⚠️ 강의 미등록"

            with st.expander(exp_title, expanded=camp_hist.empty):
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("최종 인원", f"{final_m:,}명")
                mc2.metric("최고 인원", f"{peak_m:,}명")
                mc3.metric("전체 순증감", f"{net_s}명")
                mc4.metric("운영 기간", f"{days}일")

                # ── 실제 종료일 수정 (container로 대체 — 중첩 expander 금지) ──
                st.divider()
                with st.container(border=True):
                    st.markdown("**📅 실제 종료일 수정**")
                    try:
                        _init_date = date.fromisoformat(actual_dt) if actual_dt else date.fromisoformat(arch_dt)
                    except ValueError:
                        _init_date = date.today()
                    new_close = st.date_input(
                        "실제 종료일",
                        value=_init_date,
                        key=f"close_dt_{rn}",
                        help="채팅방을 실제로 나간 날짜를 입력하세요.",
                    )
                    if st.button("💾 저장", key=f"save_close_{rn}", type="primary"):
                        update_actual_close_date(rn, str(new_close))
                        st.success(f"실제 종료일 저장 완료: {new_close}")
                        st.rerun()

                # ── 강의 이력 / 누락 경고 ─────────────────────────
                st.divider()
                if not camp_hist.empty:
                    st.markdown("**강의 이력**")
                    disp = camp_hist[['campaign_name', 'product', 'cohort',
                                      'start_date', 'lecture_start_date', 'end_date', 'memo']].copy()
                    disp.columns = ['강의명', '상품', '기수', '모객 시작', '개강일', '종료일', '메모']
                    st.dataframe(disp, hide_index=True)
                else:
                    st.warning("강의(캠페인) 이력이 없습니다. 등록하면 강의 분석 탭 모객 곡선에 포함됩니다.")
                    with st.container(border=True):
                        st.markdown("**➕ 강의 빠른 등록**")
                        with st.form(key=f"quick_camp_{rn}"):
                            qc1, qc2 = st.columns(2)
                            q_name   = qc1.text_input("강의명", placeholder="예) 황금사주 무료특강")
                            q_prod   = qc2.selectbox("상품", PRODUCT_OPTIONS, key=f"qprod_{rn}")
                            qc3, qc4 = st.columns(2)
                            q_cohort = qc3.text_input("기수", placeholder="예) 11기")
                            q_target = qc4.number_input("목표 인원", min_value=0, step=50, value=0)
                            qc5, qc6 = st.columns(2)
                            q_start  = qc5.date_input("모객 시작일", key=f"qstart_{rn}")
                            q_lstart = qc6.date_input("개강일 (선택)", value=None, key=f"qlstart_{rn}")
                            if st.form_submit_button("강의 등록", type="primary", width='stretch'):
                                if q_name.strip():
                                    save_campaign(
                                        room_num=rn,
                                        campaign_name=q_name.strip(),
                                        product=q_prod,
                                        cohort=q_cohort.strip(),
                                        start_date=str(q_start),
                                        memo="",
                                        target_count=int(q_target),
                                        lecture_start_date=str(q_lstart) if q_lstart else "",
                                    )
                                    # 종료된 방이므로 is_current=False로 즉시 변경
                                    end_campaign(rn)
                                    st.success("강의 등록 완료!")
                                    st.rerun()
                                else:
                                    st.error("강의명을 입력해주세요.")

                st.caption(f"종료 사유: {reason} | 처리일: {arch_dt}")

                # ── 복원 버튼 ──────────────────────────────────────
                if st.button("↩️ 활성 채팅방으로 복원", key=f"restore_{rn}"):
                    restore_room(rn)
                    st.success(f"채팅방 {rn} — '{rname}' 복원 완료")
                    st.rerun()


# ── 탭: 마케팅 분석 ──────────────────────────────────────────────

def _strategy_briefing() -> list:
    """모든 분석 데이터를 종합해 우선순위 전략 액션을 생성(데이터 기반·자동 갱신)."""
    cs = load_course_summary()
    camp = load_campaign_adspend()
    region = load_region_signups()
    perf = load_monthly_performance()
    ad_m = load_ad_spend_monthly()
    items = []  # (아이콘, 제목, 본문)

    # 1) 전체 광고 효율 (누적 ROAS)
    if not perf.empty and not ad_m.empty:
        _am = set(ad_m['month'].astype(str))
        _rev = int(perf[perf['month'].astype(str).isin(_am)]['revenue'].sum())
        _sp = int(ad_m['spend'].sum())
        if _sp > 0:
            items.append(("📈", "전체 광고 효율",
                          f"광고비 집행 기간 누적 **ROAS {_rev/_sp:.1f}배** "
                          f"(매출 {_rev/1e8:.1f}억 ÷ 광고비 {_sp/1e8:.1f}억). "
                          "업계 목표(2배)를 크게 상회 — 광고 확대 자체는 안전한 구간입니다."))

    # 2) 상품군 광고 예산 재배분
    if not camp.empty:
        g = camp.groupby('product').agg(ad=('ad_spend', 'sum'),
                                        rev=('live_revenue', 'sum')).reset_index()
        g = g[g['ad'] > 0].copy()
        if not g.empty:
            g['roas'] = g['rev'] / g['ad']
            _b = g.loc[g['roas'].idxmax()]
            _w = g.loc[g['roas'].idxmin()]
            _t = g.loc[g['ad'].idxmax()]
            _share = _t['ad'] / g['ad'].sum() * 100
            items.append(("💰", "광고 예산 재배분",
                          f"**{_b['product']}** 광고 ROAS **{_b['roas']:.1f}배**로 최고 → **확대 1순위**. "
                          f"광고비가 **{_t['product']}에 {_share:.0f}% 집중**(ROAS {_t['roas']:.1f}배)이고 "
                          f"최저 효율은 **{_w['product']}({_w['roas']:.1f}배)** — 집중 상품의 소재·타깃 "
                          "효율 점검 후 고효율 상품으로 분산을 검토하세요."))

    # 3) 전환 강점 상품 + 고객단가 (매출 기준과 정합: students 사용)
    if not cs.empty:
        cc = cs.copy()
        cc['cv'] = cc['students'] / cc['free'].replace(0, pd.NA)
        cc = cc.dropna(subset=['cv'])
        if not cc.empty:
            _bv = cc.loc[cc['cv'].idxmax()]
            items.append(("🎯", "전환 강점 상품",
                          f"**{_bv['product']}** 무료→유료 전환 **{_bv['cv']*100:.1f}%**로 최고 → "
                          "무료 모객을 늘릴수록 유료 성과가 가장 잘 따라오는 상품입니다."))
        c2 = cs.copy()
        c2['aov'] = c2['revenue'] / c2['students'].replace(0, pd.NA)
        c2 = c2.dropna(subset=['aov'])
        if not c2.empty:
            _hp = c2.loc[c2['aov'].idxmax()]
            items.append(("💎", "고객단가 상품",
                          f"**{_hp['product']}** 객단가 **{_hp['aov']/1e4:,.0f}만원**로 최고 → "
                          "고가 패키지·업셀 여력이 큰 프리미엄 라인입니다."))

    # 4) 지역 광고 집중
    if not region.empty:
        _tot = int(region['signups'].sum())
        _cap = int(region[region['region'].isin(CAPITAL_REGIONS)]['signups'].sum())
        _loc = region[~region['region'].isin(CAPITAL_REGIONS)].sort_values('signups', ascending=False)
        _tl = _loc.iloc[0]['region'] if not _loc.empty else '—'
        if _tot:
            items.append(("📍", "지역 광고 집중",
                          f"수도권 집중도 **{_cap/_tot*100:.0f}%**(서울·경기·인천). 광고 예산을 "
                          f"수도권에 우선 배정하고, 비수도권은 **{_tl}** 등 영남권을 보조 타깃으로 운영하세요."))

    # 5) 재구매·LTV (고객 자산)
    _mnr = load_cust_monthly_new_repeat()
    _pr = load_cust_product_repeat()
    if not _mnr.empty:
        _nr = int(_mnr['new_revenue'].sum())
        _rr = int(_mnr['repeat_revenue'].sum())
        _share = _rr / (_nr + _rr) * 100 if (_nr + _rr) else 0
        _extra = ""
        if not _pr.empty:
            _hr = _pr.loc[_pr['repeat_rate'].idxmax()]
            _extra = f" 재구매율은 **{_hr['product']}({_hr['repeat_rate']:.0f}%)**가 최고."
        if _share >= 35:
            items.append(("🔁", "재구매·LTV 강화",
                          f"재구매 매출이 전체의 **{_share:.0f}%** — 신규 유치만큼 **기존 고객 업셀·"
                          f"CRM**이 매출 핵심입니다.{_extra} 상위 과정 라인업과 재구매 유도에 투자하세요."))
    return items


def tab_marketing():
    st.header("📢 마케팅 분석")

    # ══ 종합 전략 브리핑 (모든 분석 종합·데이터 자동 반영) ═══════════
    _brief = _strategy_briefing()
    if _brief:
        with st.container(border=True):
            st.markdown("### 🧭 종합 전략 브리핑")
            st.caption("광고 ROI·전환·객단가·지역 분석을 종합한 **데이터 기반 액션 요약**. "
                       "데이터가 갱신되면 문구도 자동으로 바뀝니다.")
            for _icon, _title, _body in _brief:
                st.markdown(f"- **{_icon} {_title}** — {_body}")
        st.divider()

    # ══ 전 기간 성과 추이 (주문 명단 집계) ══════════════════════
    perf = load_monthly_performance()
    ad_m = load_ad_spend_monthly()
    if not perf.empty:
        st.subheader("📈 전 기간 성과 추이")
        st.caption(f"주문 데이터 기반 월별 성과 ({perf['month'].min()} ~ {perf['month'].max()}, "
                   f"{len(perf)}개월). 개인정보 없는 집계.")
        _tot_rev = int(perf['revenue'].sum())
        _tot_free = int(perf['free_signups'].sum())
        _tot_paid = int(perf['paid_orders'].sum())
        _tot_spend_m = int(ad_m['spend'].sum()) if not ad_m.empty else 0
        # ROAS는 광고비가 집행된 달의 매출로만 계산(기간 정합)
        if not ad_m.empty:
            _ad_months = set(ad_m['month'].astype(str))
            _rev_ad = int(perf[perf['month'].astype(str).isin(_ad_months)]['revenue'].sum())
        else:
            _rev_ad = 0
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("누적 매출", f"{_tot_rev/1e8:,.1f}억원")
        m2.metric("누적 무료 신청", f"{_tot_free:,}")
        m3.metric("누적 유료 구매", f"{_tot_paid:,}건")
        if _tot_spend_m > 0:
            m4.metric("누적 ROAS", f"{_rev_ad/_tot_spend_m:,.1f}배",
                      help=f"광고비 집행 기간({min(_ad_months)}~{max(_ad_months)}) 매출 "
                           f"{_rev_ad/1e8:,.1f}억 ÷ 광고비 {_tot_spend_m/1e8:,.1f}억")
        else:
            m4.metric("평균 전환율", f"{_tot_paid/_tot_free*100:.2f}%" if _tot_free else "—")

        _camps_ov = load_campaigns()
        fig_m = monthly_perf_chart(perf, ad_m if not ad_m.empty else None,
                                   campaigns_df=_camps_ov if not _camps_ov.empty else None)
        if fig_m:
            st.plotly_chart(fig_m, key="mkt_monthly")
            st.caption("🎓 세로 점선 = 강의 모객 시작월 (개강 캠페인이 매출·유입에 미친 영향 확인용)")

        # 월별 광고비 입력
        with st.expander("✏️ 월별 광고비 입력 — ROAS·CPA 산출용", expanded=(ad_m.empty)):
            st.caption("광고 플랫폼(메타·구글 등)의 **월별 지출 총액**만 넣으면 전 기간 ROAS가 계산됩니다. "
                       "채널을 나눠 넣어도 됩니다.")
            _months = perf['month'].tolist()
            with st.form("ad_spend_form"):
                ac1, ac2, ac3 = st.columns([1.4, 1, 1.2])
                with ac1:
                    _am = st.selectbox("월", options=_months[::-1], key="ad_month")
                with ac2:
                    _ac = st.selectbox("채널", options=AD_CHANNEL_OPTIONS, key="ad_ch")
                with ac3:
                    _asp = st.number_input("광고비(원)", min_value=0, step=100000, value=0)
                if st.form_submit_button("저장", type="primary", width='stretch'):
                    save_ad_spend_monthly(_am, _ac, int(_asp))
                    st.success(f"{_am} {_ac} 광고비 {_asp:,}원 저장 완료")
                    st.rerun()
            if not ad_m.empty:
                _disp = ad_m.copy()
                _disp['spend'] = _disp['spend'].apply(lambda x: f"{x:,}원")
                st.dataframe(_disp[['month', 'channel', 'spend']].rename(
                    columns={'month': '월', 'channel': '채널', 'spend': '광고비'}),
                    hide_index=True)

        # ── 월별 광고비 vs 매출 ROAS ──────────────────────────
        if not ad_m.empty:
            fig_roas = monthly_roas_chart(perf, ad_m)
            if fig_roas:
                st.markdown("**📊 월별 광고비 대비 매출(ROAS)**")
                st.plotly_chart(fig_roas, key="mkt_roas")
                st.caption("광고비가 입력된 달만 표시. ROAS = 해당 월 매출 ÷ 광고비. "
                           "광고 효율이 낮은 달(광고비↑ ROAS↓)을 찾아 예산 배분을 조정하세요.")
        st.divider()

    # ══ 강의 ROI 분석 (강의 집계 보고서 기반) ════════════════════
    course_sum = load_course_summary()
    cohort_rev = load_cohort_revenue()
    if not course_sum.empty:
        st.subheader("🎓 강의 ROI 분석")
        st.caption("아임웹 강의별 집계(세트합계·멤버십 제외) 기준. 무료 특강 모객 → 유료 전환 성과를 "
                   "상품군·기수별로 비교합니다.")

        _tot_paid_rev = int(course_sum['revenue'].sum())
        _tot_students = int(course_sum['students'].sum())
        _tot_free_cnt = int(course_sum['free'].sum())
        _ad_all = int(ad_m['spend'].sum()) if not ad_m.empty else 0
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("강의 누적 매출", f"{_tot_paid_rev/1e8:,.1f}억원",
                  help="4개 상품군 세트합계 매출 총합")
        r2.metric("누적 유료 수강생", f"{_tot_students:,}명",
                  help=f"세트 수강생(멤버십 제외). 유료 결제 건수 {int(course_sum['paid'].sum()):,}건")
        r3.metric("누적 무료 모객", f"{_tot_free_cnt:,}명", help="무료 신청 건수(중복 포함)")
        _free2paid = (_tot_students / _tot_free_cnt * 100) if _tot_free_cnt else 0
        r4.metric("무료→유료 전환율", f"{_free2paid:.1f}%",
                  help="세트 수강생 ÷ 무료 신청 건수")

        cm1, cm2 = st.columns([1, 1.2])
        with cm1:
            fig_mix = product_revenue_mix_chart(course_sum)
            if fig_mix:
                st.plotly_chart(fig_mix, key="roi_mix")
        with cm2:
            # 상품군별 요약표 — 세트 수강생 기준(매출과 정합), 0 나눔 가드
            cs = course_sum.copy().sort_values('revenue', ascending=False)
            cs['전환율'] = (cs['students'] / cs['free'].replace(0, pd.NA) * 100).round(1).fillna(0)
            cs['객단가'] = (cs['revenue'] / cs['students'].replace(0, pd.NA)).round(0).fillna(0).astype(int)
            cs_disp = pd.DataFrame({
                '상품군': cs['product'],
                '누적매출': cs['revenue'].apply(lambda x: f"{x/1e8:,.2f}억"),
                '수강생': cs['students'].apply(lambda x: f"{x:,}명"),
                '무료모객': cs['free'].apply(lambda x: f"{x:,}명"),
                '전환율': cs['전환율'].apply(lambda x: f"{x}%"),
                '객단가': cs['객단가'].apply(lambda x: f"{x/1e4:,.0f}만원"),
            })
            st.dataframe(cs_disp, hide_index=True)
            st.caption("전환율=세트 수강생÷무료신청, 객단가=누적매출÷세트 수강생 "
                       "(매출과 동일 기준인 세트 수강생으로 계산해 정합을 맞춤. 무료신청은 중복 포함).")

        # ── 상품군별 광고 ROI (캠페인별 광고비 귀속) ──────────
        camp_ad = load_campaign_adspend()
        g = pd.DataFrame()
        if not camp_ad.empty:
            g = camp_ad.groupby('product').agg(
                ad=('ad_spend', 'sum'), rev=('live_revenue', 'sum')).reset_index()
            g = g[g['ad'] > 0].copy()
        if not g.empty:
            st.markdown("**💰 상품군별 광고 효율 (광고비 대비 ROAS)**")
            st.caption("통합시트 라이브(캠페인)별 광고비를 상품군에 귀속한 결과. "
                       "여기 '광고 매출'은 해당 캠페인 라이브가 직접 만든 매출(첫 전환 기준)이라 "
                       "위 누적매출(패키지·재구매 포함)보다 작습니다. 광고 효율만 비교하는 값입니다.")
            fig_ad = product_ad_roi_chart(camp_ad)
            if fig_ad:
                st.plotly_chart(fig_ad, key="roi_prod_ad")

            g['roas'] = g['rev'] / g['ad']
            g = g.sort_values('roas', ascending=False)
            _best_p = g.iloc[0]
            _worst_p = g.iloc[-1]
            _tot_camp_ad = int(g['ad'].sum())
            ga1, ga2, ga3 = st.columns(3)
            ga1.metric("광고 최고효율", f"{_best_p['product']} {_best_p['roas']:.1f}배",
                       help="광고비 대비 라이브 직접 매출")
            ga2.metric("광고 최저효율", f"{_worst_p['product']} {_worst_p['roas']:.1f}배")
            ga3.metric("캠페인 광고비 총계", f"{_tot_camp_ad/1e8:,.2f}억원",
                       help=f"라이브별 광고비 합 (월별 집행 총액 {int(ad_m['spend'].sum())/1e8:.2f}억과 "
                            "집계 방식 차이로 소폭 다름)" if not ad_m.empty else "라이브별 광고비 합")

            g_disp = pd.DataFrame({
                '상품군': g['product'],
                '광고비': g['ad'].apply(lambda x: f"{x/1e8:,.2f}억"),
                '광고매출': g['rev'].apply(lambda x: f"{x/1e8:,.2f}억"),
                '광고 ROAS': g['roas'].apply(lambda x: f"{x:.1f}배"),
                '광고비 비중': (g['ad'] / g['ad'].sum() * 100).apply(lambda x: f"{x:.0f}%"),
            })
            st.dataframe(g_disp, hide_index=True)
            _ad_sum = int(g['ad'].sum())
            _top_spend = g.loc[g['ad'].idxmax()]           # 광고비 최다 집중 상품군
            _top_share = _top_spend['ad'] / _ad_sum * 100 if _ad_sum else 0
            _eff_names = " · ".join(g.sort_values('roas', ascending=False).head(2)['product'].tolist())
            st.info(f"💡 **광고 전략** — **{_best_p['product']}**가 광고비 대비 매출 **{_best_p['roas']:.1f}배**로 "
                    f"가장 효율적이라 광고 확대 여지가 큽니다. 반면 **{_worst_p['product']}**는 "
                    f"**{_worst_p['roas']:.1f}배**로, 광고비 비중이 높다면 소재·타깃 개선 또는 예산 재배분이 "
                    f"필요합니다. 현재 광고비의 **{_top_share:.0f}%**가 **{_top_spend['product']}**에 집중되어 있어, "
                    f"효율 높은 **{_eff_names}**로의 분산도 검토할 만합니다.")

            # ── 기수별 광고 효율 진단 (저효율 상품 심층 분석) ──
            st.markdown("**🔬 기수별 광고 효율 진단**")
            st.caption("상품군을 골라 기수별 광고비 대비 매출(ROAS)을 진단합니다. "
                       "광고비를 많이 쓰고도 효율이 낮은 기수를 찾아 소재·타깃을 재점검하세요.")
            _diag_prods = [p for p in ['사주', '부동산', '빌딩', '타로']
                           if not camp_ad[camp_ad['product'] == p].empty]
            # 저효율(광고비 대비 ROAS 낮은) 상품을 기본 선택
            _default_idx = 0
            if not g.empty:
                _low_prod = g.sort_values('roas').iloc[0]['product']
                if _low_prod in _diag_prods:
                    _default_idx = _diag_prods.index(_low_prod)
            _dp = st.selectbox("진단 상품군", options=_diag_prods,
                               index=_default_idx, key="cohort_ad_diag")
            _fig_diag = cohort_ad_roi_chart(camp_ad, _dp)
            if _fig_diag:
                st.plotly_chart(_fig_diag, key="roi_cohort_ad_diag")
                # 기수별 진단 인사이트
                _dd = camp_ad[camp_ad['product'] == _dp].groupby('cohort', as_index=False).agg(
                    ad=('ad_spend', 'sum'), rev=('live_revenue', 'sum'))
                _dd = _dd[_dd['ad'] > 0].copy()
                if not _dd.empty:
                    _dd['roas'] = _dd['rev'] / _dd['ad']
                    _wc = _dd.loc[_dd['roas'].idxmin()]
                    _mc = _dd.loc[_dd['ad'].idxmax()]
                    _bc = _dd.loc[_dd['roas'].idxmax()]
                    _msg = (f"💡 **{_dp} 진단** — 광고비 최다 투입 기수는 **{_mc['cohort']}"
                            f"({_mc['ad']/1e8:.2f}억, ROAS {_mc['rev']/_mc['ad']:.1f}배)**, "
                            f"효율 최저는 **{_wc['cohort']}({_wc['roas']:.1f}배)**, "
                            f"최고는 **{_bc['cohort']}({_bc['roas']:.1f}배)**입니다. ")
                    if _mc['rev'] / _mc['ad'] < 3:
                        _msg += (f"광고비를 가장 많이 쓴 **{_mc['cohort']}의 효율이 낮아**, "
                                 "해당 기수의 소재·타깃·랜딩을 최우선으로 점검해야 합니다.")
                    else:
                        _msg += "광고비 배분과 효율이 대체로 정렬되어 있습니다."
                    st.info(_msg)

        # 기수별 매출 곡선 (상품군 선택)
        if not cohort_rev.empty:
            st.markdown("**기수별 매출 추이**")
            _prods = [p for p in ['사주', '타로', '부동산', '빌딩']
                      if p in cohort_rev['product'].unique()]
            _psel = st.selectbox("상품군 선택", options=_prods, key="roi_prod")
            fig_co = cohort_revenue_chart(cohort_rev, _psel)
            if fig_co:
                st.plotly_chart(fig_co, key="roi_cohort")
            # 최고/최저 기수 인사이트
            _pd = cohort_rev[cohort_rev['product'] == _psel]
            _pd = _pd[_pd['students'] > 0]
            if not _pd.empty:
                _best = _pd.loc[_pd['revenue'].idxmax()]
                _bestp = _pd.loc[(_pd['revenue'] / _pd['students']).idxmax()]
                st.info(f"💡 **{_psel}** — 최대 매출 기수: **{_best['cohort']}** "
                        f"({_best['revenue']/1e4:,.0f}만원, {_best['students']}명). "
                        f"객단가 최고 기수: **{_bestp['cohort']}** "
                        f"({_bestp['revenue']/_bestp['students']/1e4:,.0f}만원/명).")
        st.divider()

    # ══ 경쟁사 가격 벤치마크 ════════════════════════════════════
    comp = load_competitor_courses()
    if not comp.empty:
        st.subheader("🏷️ 경쟁사 가격 벤치마크")
        st.caption("경쟁사 조사 시트 기반 — 상품군별 시장 가격대와 황금후추(자사) 포지셔닝. "
                   "무료 웨비나 → 고가 전환 구조의 프리미엄 가격 전략을 시장과 비교합니다.")

        _cats = [c for c in ['사주', '타로', '부동산', '빌딩']
                 if c in comp['category'].unique()]
        # 상품군별 포지셔닝 요약 카드
        _own = comp[comp['company'].str.contains('황금후추', na=False)]
        _mkt = comp[~comp['company'].str.contains('황금후추', na=False)]
        pos_rows = []
        for c in _cats:
            o = _own[_own['category'] == c]
            m = _mkt[_mkt['category'] == c]
            if o.empty or m.empty:
                continue
            own_price = int(o['price_max'].iloc[0])
            # 경쟁사 대표가 = (min+max)/2 의 중앙값
            mids = ((m['price_min'] + m['price_max']) / 2)
            mkt_med = int(mids.median())
            ratio = own_price / mkt_med if mkt_med else 0
            pos_rows.append((c, own_price, mkt_med, int(m['price_min'].min()),
                             int(m['price_max'].max()), ratio))

        if pos_rows:
            cols = st.columns(len(pos_rows))
            for col, (c, own_p, mkt_med, mn, mx, ratio) in zip(cols, pos_rows):
                col.metric(
                    f"{c} — 자사 대표가", f"{own_p/1e4:,.0f}만원",
                    delta=f"시장 대비 {ratio:.1f}배",
                    delta_color="off",
                    help=f"경쟁사 대표가(중앙) {mkt_med/1e4:,.0f}만원 · "
                         f"시장범위 {mn/1e4:,.0f}~{mx/1e4:,.0f}만원",
                )

        _sel = st.selectbox("상품군 선택", options=_cats, key="comp_cat")
        fig_c = competitor_price_chart(comp, _sel)
        if fig_c:
            st.plotly_chart(fig_c, key="mkt_comp")

        # 포지셔닝 인사이트
        _sr = next((r for r in pos_rows if r[0] == _sel), None)
        if _sr:
            c, own_p, mkt_med, mn, mx, ratio = _sr
            if ratio >= 1.5:
                _pos = (f"황금후추 **{c}** 대표가는 **{own_p/1e4:,.0f}만원**으로 "
                        f"시장 중앙값({mkt_med/1e4:,.0f}만원)의 **{ratio:.1f}배** — "
                        f"명확한 **프리미엄 포지션**입니다. 무료 웨비나로 신뢰를 쌓아 "
                        f"고가 전환하는 구조여서, 가격보다 **콘텐츠·브랜드 차별성**이 "
                        f"핵심 경쟁력입니다.")
            elif ratio >= 0.8:
                _pos = (f"황금후추 **{c}** 대표가({own_p/1e4:,.0f}만원)는 시장 중앙값 "
                        f"({mkt_med/1e4:,.0f}만원)과 **비슷한 수준**입니다. 가격 경쟁이 "
                        f"치열한 구간이므로 차별화 포인트가 중요합니다.")
            else:
                _pos = (f"황금후추 **{c}** 대표가({own_p/1e4:,.0f}만원)는 시장 중앙값 "
                        f"({mkt_med/1e4:,.0f}만원)보다 **낮은 편**으로, 가격 경쟁력이 있는 "
                        f"포지션입니다.")
            st.info("💡 " + _pos)
        st.divider()

    # ══ 채널별 상세 (외부 채널 metrics) ═════════════════════════
    st.subheader("🔬 채널별 상세 분석")
    df = load_marketing()
    if df.empty:
        st.info("채널별 상세 데이터(채널 metrics)가 없습니다.")
        return

    d0, d1 = df['date'].min(), df['date'].max()
    st.caption(f"채널 metrics 기간: **{d0} ~ {d1}** — 채널별 일 단위 상세 (외부 시트 이관)")

    # ── KPI ──────────────────────────────────────────────
    # 총계는 '전체'(집계행)를 권위값으로, 광고비는 채널 실집행(메타)만 사용
    ch = marketing_channel_summary(df)
    _tot = df[df['channel'] == '전체']
    tot_spend = int(ch['광고비'].sum())          # '전체'행 제외 = 실제 채널 광고비
    if not _tot.empty:
        tot_rev  = int(_tot['revenue'].sum())
        tot_sess = int(_tot['sessions'].sum())
        tot_buy  = int(_tot['purchases'].sum())
    else:
        tot_rev, tot_sess, tot_buy = int(ch['매출'].sum()), int(ch['세션'].sum()), int(ch['구매'].sum())
    roas      = round(tot_rev / tot_spend, 1) if tot_spend else 0
    cpa       = round(tot_spend / tot_buy) if tot_buy else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 광고비", f"{tot_spend:,}원")
    k2.metric("총 매출", f"{tot_rev:,}원")
    k3.metric("전체 ROAS", f"{roas:,.1f}배", help="총 매출 ÷ 총 광고비 (오가닉 매출 포함)")
    k4.metric("구매 건수", f"{tot_buy:,}건")
    k5, k6, k7, k8 = st.columns(4)
    k5.metric("총 세션(유입)", f"{tot_sess:,}")
    k6.metric("구매 전환율", f"{round(tot_buy/tot_sess*100,2)}%" if tot_sess else "—")
    k7.metric("광고 CPA", f"{cpa:,}원", help="광고비 ÷ 전체 구매 건수")
    _paid_sess = int(ch[ch['광고비'] > 0]['세션'].sum())
    k8.metric("광고 CPС(세션)", f"{round(tot_spend/_paid_sess):,}원" if _paid_sess else "—",
              help="광고비 ÷ 광고 유입 세션")

    st.info("💡 **읽는 법** — 광고비는 주로 **메타**에, 매출은 **오픈채팅·유튜브·오가닉**에 잡힙니다"
            "(광고→방 유입→구매 구조). 그래서 전체 ROAS는 유료+오가닉이 섞인 값이며, "
            "채널별 효율은 아래 세션·구매·전환율로 비교하는 것이 정확합니다.")

    # ── 🎯 목표 대비 평가 (업계 벤치마크 기준선) ──────────────
    _conv_rate = (tot_buy / tot_sess * 100) if tot_sess else 0
    _cps = (tot_spend / _paid_sess) if _paid_sess else 0
    _bench = [
        ("ROAS", roas, 2.0, f"{roas:.1f}배", "≥ 2.0배", roas >= 2.0),
        ("구매 전환율", _conv_rate, 3.0, f"{_conv_rate:.2f}%", "≥ 3%", _conv_rate >= 3.0),
        ("세션 단가(CPС)", _cps, 10000, f"{_cps:,.0f}원", "≤ 10,000원", 0 < _cps <= 10000),
    ]
    st.markdown("**🎯 목표 대비 (업계 벤치마크)**")
    bc = st.columns(len(_bench))
    for col, (name, _v, _t, cur, tgt, ok) in zip(bc, _bench):
        mark = "🟢 달성" if ok else "🔴 미달"
        col.metric(name, cur, delta=f"{mark} (목표 {tgt})", delta_color="off")

    # ── 총 마케팅 비용 통합 (광고비 + 부대비용) ────────────────
    with st.expander("💰 총 마케팅 비용 반영 — 친구톡·소재비 포함 보정 ROAS/CPA"):
        st.caption(f"채널 metrics의 광고비는 **메타 실집행({tot_spend:,}원)**만 포함합니다. "
                   "여기에 CRM 친구톡 발송비·소재 제작비를 더하면 **진짜 마케팅 비용** 기준 "
                   "ROAS·CPA를 볼 수 있습니다. 아래 값은 추정 기본치이며 실제 청구서에 맞게 수정하세요.")
        e1, e2 = st.columns(2)
        with e1:
            _kakao = st.number_input(
                "친구톡/CRM 발송비(원)", min_value=0, step=100000, value=7_870_000,
                help="발송 건수 × 단가(약 15원) 기준 추정. CRM 시트 발송 내역으로 보정 가능.")
        with e2:
            _asset = st.number_input(
                "소재 제작비(원)", min_value=0, step=100000, value=1_300_000,
                help="운영 실비 시트의 디자인·영상 소재 제작비 추정.")
        _total_mkt = tot_spend + int(_kakao) + int(_asset)
        _roas_adj = round(tot_rev / _total_mkt, 1) if _total_mkt else 0
        _cpa_adj = round(_total_mkt / tot_buy) if tot_buy else 0
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("총 마케팅 비용", f"{_total_mkt/1e4:,.0f}만원",
                  delta=f"광고비 대비 +{(_total_mkt-tot_spend)/1e4:,.0f}만원", delta_color="off")
        t2.metric("보정 ROAS", f"{_roas_adj:,.1f}배",
                  delta=f"{_roas_adj-roas:+.1f}배", delta_color="off",
                  help="총 매출 ÷ 총 마케팅 비용")
        t3.metric("보정 CPA", f"{_cpa_adj:,}원",
                  delta=f"{_cpa_adj-cpa:+,}원", delta_color="inverse",
                  help="총 마케팅 비용 ÷ 구매 건수")
        t4.metric("비용 구성", f"광고 {tot_spend/_total_mkt*100:.0f}%" if _total_mkt else "—",
                  delta=f"부대 {(_kakao+_asset)/_total_mkt*100:.0f}%" if _total_mkt else None,
                  delta_color="off")

    # ── 채널별 매출 + 전환율 ──────────────────────────────
    st.divider()
    st.subheader("채널별 성과")
    c_l, c_r = st.columns(2)
    with c_l:
        fig = marketing_channel_chart(df)
        if fig:
            st.plotly_chart(fig, key="mkt_ch_rev")
    with c_r:
        fig2 = marketing_channel_conv_chart(df)
        if fig2:
            st.plotly_chart(fig2, key="mkt_ch_conv")

    # 채널 요약표
    disp = ch.copy()
    disp['광고비'] = disp['광고비'].apply(lambda x: f"{x:,}원" if x else "—")
    disp['세션']   = disp['세션'].apply(lambda x: f"{x:,}")
    disp['구매']   = disp['구매'].apply(lambda x: f"{x:,}건")
    disp['매출']   = disp['매출'].apply(lambda x: f"{x:,}원" if x else "—")
    disp['전환율'] = disp['전환율'].apply(lambda x: f"{x:.2f}%")
    disp = disp.rename(columns={'channel': '채널'})
    st.dataframe(disp, hide_index=True)

    # ── 일별 추이 ────────────────────────────────────────
    st.divider()
    st.subheader("일별 매출 · 광고비 추이")
    figt = marketing_trend_chart(df)
    if figt:
        st.plotly_chart(figt, key="mkt_trend")

    # ── 마케팅 퍼널 ──────────────────────────────────────
    st.divider()
    st.subheader("마케팅 퍼널")
    st.caption("광고비 투입 → 유입(세션) → 구매 → 매출")
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("① 광고비", f"{tot_spend/1e4:,.0f}만원")
    fc2.metric("② 유입 세션", f"{tot_sess:,}")
    fc3.metric("③ 구매", f"{tot_buy:,}건")
    fc4.metric("④ 매출", f"{tot_rev/1e8:,.2f}억원")


# ── 탭: 지역 분석 ─────────────────────────────────────────────────

def tab_region():
    st.header("📍 지역 분석")
    region = load_region_signups()
    rc = load_region_cohort()
    city = load_region_city()

    if region.empty:
        st.info("지역별 신청 데이터가 없습니다.")
        return

    st.caption("**돈사공 초급반 9~12기 배송지 주소** 기준 (국내 472건 · 개인정보 제외 지역 통계만). "
               "실물 교재를 배송하는 강의라 배송지 = 실제 거주 지역으로, 광고 타깃 지역 판단의 대표 표본입니다.")

    # ── 핵심 지표 ────────────────────────────────────────
    _tot = int(region['signups'].sum())
    _cap = int(region[region['region'].isin(CAPITAL_REGIONS)]['signups'].sum())
    _cap_pct = _cap / _tot * 100 if _tot else 0
    _busan = int(region[region['region'] == '부산']['signups'].sum())
    _local_top = region[~region['region'].isin(CAPITAL_REGIONS)].sort_values('signups', ascending=False)
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("총 신청(국내)", f"{_tot:,}건")
    g2.metric("수도권 집중도", f"{_cap_pct:.1f}%", help="서울+경기+인천 비중")
    g3.metric("서울+경기", f"{int(region[region['region'].isin(['서울','경기'])]['signups'].sum())/_tot*100:.1f}%")
    g4.metric("최대 비수도권", f"{_local_top.iloc[0]['region']} {int(_local_top.iloc[0]['signups'])}건"
              if not _local_top.empty else "—")

    st.divider()

    # ── 지역별 분포 ──────────────────────────────────────
    st.subheader("지역별 신청 분포")
    # 지도(버블) + 지역 순위 막대 나란히
    mp_l, mp_r = st.columns([1, 1])
    with mp_l:
        fig_map = region_bubble_map(region, capital=tuple(CAPITAL_REGIONS))
        if fig_map:
            st.plotly_chart(fig_map, key="rgn_map")
    with mp_r:
        fig_r = region_distribution_chart(region, capital=tuple(CAPITAL_REGIONS))
        if fig_r:
            st.plotly_chart(fig_r, key="rgn_dist")
    with st.expander("지역별 신청 수 표"):
        rd = region.copy()
        rd = rd.rename(columns={'region': '지역', 'signups': '신청', 'pct': '비율(%)'})
        st.dataframe(rd, hide_index=True, width='stretch')

    # ── 광고 집중 전략 추천 ──────────────────────────────
    st.divider()
    st.subheader("🎯 광고 집중 지역 추천")

    def _rv(name):  # 지역 신청 수 안전 조회 (없으면 0)
        _s = region[region['region'] == name]['signups']
        return int(_s.iloc[0]) if not _s.empty else 0

    _seoul, _gg = _rv('서울'), _rv('경기')
    _sg_pct = (_seoul + _gg) / _tot * 100 if _tot else 0
    st.markdown(
        f"""
- **1순위 — 수도권(서울·경기·인천)**: 전체의 **{_cap_pct:.0f}%**가 집중. 메타·구글 광고 예산의 대부분을
  서울·경기 타깃으로 배정하는 것이 효율적입니다. 특히 서울({_seoul}건)·경기({_gg}건) 2개 시도만으로
  **{_sg_pct:.0f}%**를 차지합니다.
- **2순위 — 부산·경남권**: 비수도권 중 **부산({_busan}건)**이 가장 크고 경남·대구가 뒤를 이어,
  영남권 광역타깃(부산·경남·대구)을 별도 캠페인으로 운영할 가치가 있습니다.
- **3순위 — 대전·충청권**: 대전·충남·충북 합산이 일정 규모를 형성해 중부권 보조 타깃으로 검토.
- **저효율 경계**: 전남·전북·강원·제주는 신청이 적어(각 1% 안팎) 광역 타깃보다는
  전환이 확인될 때만 리타깃팅 위주로 최소 집행을 권장합니다.
"""
    )
    st.info("💡 다른 채널에서도 **수도권 > 부산·경기·인천 집중**이 효율적이라는 결과가 나왔던 것과 "
            "이 배송지 데이터가 일치합니다. 수도권+부산에 광고를 집중하는 전략이 데이터로 뒷받침됩니다.")

    # ── 도시/구 단위 ─────────────────────────────────────
    if not city.empty:
        st.divider()
        st.subheader("상위 도시·구 단위")
        cc_l, cc_r = st.columns([1.2, 1])
        with cc_l:
            fig_c = region_city_chart(city)
            if fig_c:
                st.plotly_chart(fig_c, key="rgn_city")
        with cc_r:
            st.markdown("**세부 타깃 인사이트**")
            st.markdown(
                "- 서울 내 **강남·서초·송파(강남 3구)**가 압도적 — 고관여·고소득 타깃과 일치.\n"
                "- 동작·영등포·양천·용산 등 서울 서남권도 꾸준.\n"
                "- 경기권은 **하남·성남 분당**이 상위 — 신도시 고소득층 공략 유효.\n\n"
                "→ 메타 상세 타깃을 **강남 3구 + 분당·하남** 반경으로 좁히면 CPA 개선 여지가 있습니다.")

    # ── 기수별 수도권 비중 추이 ──────────────────────────
    if not rc.empty:
        st.divider()
        st.subheader("기수별 모집 현황")
        # 기수별 카드 (모집기간·일수·총신청·수도권 비중)
        _rcs = rc.sort_values('cohort')
        _cards = st.columns(len(_rcs))
        for _col, (_, _r) in zip(_cards, _rcs.iterrows()):
            with _col:
                st.markdown(f"**{_r['cohort']}**")
                st.metric("총 신청", f"{int(_r['total'])}명",
                          delta=f"수도권 {_r['capital_pct']:.0f}%", delta_color="off")
                st.caption(f"📅 {_r['start']}\n~ {_r['end']}\n\n⏱️ {int(_r['days'])}일 모집")

        st.markdown("**총 신청 · 수도권 비중 추이**")
        fig_t = region_capital_trend_chart(rc)
        if fig_t:
            st.plotly_chart(fig_t, key="rgn_trend")
        rc_disp = pd.DataFrame({
            '기수': rc['cohort'],
            '모집기간': rc['start'] + ' ~ ' + rc['end'],
            '모집일수': rc['days'].apply(lambda x: f"{x}일"),
            '총신청': rc['total'].apply(lambda x: f"{x}명"),
            '수도권': rc['capital'].apply(lambda x: f"{x}명"),
            '수도권비중': rc['capital_pct'].apply(lambda x: f"{x}%"),
        })
        st.dataframe(rc_disp, hide_index=True)
        _avg_days = rc['days'].mean()
        _corr_hint = ("모집 기간이 길수록 총신청이 느는 경향" if rc['days'].corr(rc['total']) > 0.3
                      else "모집 기간과 총신청의 상관은 뚜렷하지 않음")
        st.caption(f"평균 모집 {_avg_days:.0f}일. {_corr_hint}. "
                   "수도권 비중은 기수별 59~73%로 항상 과반 — 수도권 우선 전략의 근거.")


# ── 경영진 보고: 자동 인사이트 생성 ─────────────────────────────────

def _generate_insight(df_period, rooms, period_label,
                      df_adspend=None, df_conv=None,
                      df_all=None) -> list[str]:
    """기간 데이터를 분석해 한국어 인사이트 문장 리스트를 반환."""
    if df_period.empty:
        return ["해당 기간의 데이터가 없습니다."]

    dates = sorted(df_period['date'].unique())
    if len(dates) < 2:
        return [f"{period_label} 기간 내 데이터가 1일뿐이라 비교 인사이트를 생성하기 어렵습니다."]

    first_date, last_date = dates[0], dates[-1]
    first_total = int(df_period[df_period['date'] == first_date]['members'].sum())
    last_total  = int(df_period[df_period['date'] == last_date]['members'].sum())
    diff = last_total - first_total
    pct  = round(diff / first_total * 100, 1) if first_total > 0 else 0
    sign = "+" if diff >= 0 else ""
    trend_word = "증가" if diff > 0 else ("감소" if diff < 0 else "유지")

    lines = []
    lines.append(
        f"**{period_label}** 전체 채팅방 총원은 **{last_total:,}명**으로, "
        f"시작일({first_date}) 대비 **{sign}{diff:,}명({sign}{pct}%) {trend_word}**했습니다."
    )

    # 전주/전월 비교 (df_all 있을 때만)
    if df_all is not None and not df_all.empty:
        def _ref_total(delta_days: int):
            ref = pd.Timestamp(last_date) - pd.Timedelta(days=delta_days)
            cands = df_all[df_all['date'] <= ref.date()]
            if cands.empty:
                return None, None
            nearest = cands['date'].max()
            return int(df_all[df_all['date'] == nearest]['members'].sum()), nearest

        _wow_total, _wow_ref = _ref_total(7)
        if _wow_total and _wow_total > 0:
            _d = last_total - _wow_total
            _p = round(_d / _wow_total * 100, 1)
            _s = "+" if _d >= 0 else ""
            lines.append(
                f"전주 대비({_wow_ref}): **{_s}{_d:,}명({_s}{_p}%)** "
                f"{'▲' if _d > 0 else ('▼' if _d < 0 else '➡')}"
            )

        _mom_total, _mom_ref = _ref_total(30)
        if _mom_total and _mom_total > 0:
            _d = last_total - _mom_total
            _p = round(_d / _mom_total * 100, 1)
            _s = "+" if _d >= 0 else ""
            lines.append(
                f"전월 대비({_mom_ref}): **{_s}{_d:,}명({_s}{_p}%)** "
                f"{'▲' if _d > 0 else ('▼' if _d < 0 else '➡')}"
            )

    # 방별 증감 분석
    room_changes = {}
    for rn in df_period['room_num'].unique():
        rdf = df_period[df_period['room_num'] == rn].sort_values('date')
        if len(rdf) >= 2:
            room_changes[int(rn)] = int(rdf.iloc[-1]['members']) - int(rdf.iloc[0]['members'])

    if room_changes:
        top_rn  = max(room_changes, key=room_changes.get)
        top_val = room_changes[top_rn]
        bot_rn  = min(room_changes, key=room_changes.get)
        bot_val = room_changes[bot_rn]
        if top_val > 0:
            lines.append(
                f"가장 성장한 채팅방은 **{rooms.get(top_rn, f'채팅방 {top_rn}')}** ("
                f"**+{top_val:,}명**)입니다."
            )
        if bot_val < 0:
            lines.append(
                f"인원이 가장 감소한 채팅방은 **{rooms.get(bot_rn, f'채팅방 {bot_rn}')}** ("
                f"**{bot_val:,}명**)입니다."
            )

        # 전체 성장/감소 방 수
        n_up   = sum(1 for v in room_changes.values() if v > 0)
        n_down = sum(1 for v in room_changes.values() if v < 0)
        n_flat = len(room_changes) - n_up - n_down
        lines.append(
            f"채팅방 {n_up}개 증가 · {n_down}개 감소 · {n_flat}개 유지."
        )

    # 광고비
    if df_adspend is not None and not df_adspend.empty:
        pa = df_adspend[
            (df_adspend['date'] >= first_date) & (df_adspend['date'] <= last_date)
        ]
        if not pa.empty:
            spend = int(pa['spend'].sum())
            if spend > 0:
                if diff > 0:
                    cpm = round(spend / diff)
                    lines.append(
                        f"기간 중 광고비 **{spend:,}원** 집행 → "
                        f"인원 증가 기준 CPM **{cpm:,}원/명**."
                    )
                else:
                    lines.append(f"기간 중 광고비 **{spend:,}원** 집행.")

    # 전환
    if df_conv is not None and not df_conv.empty:
        pc = df_conv[
            (df_conv['date'] >= first_date) & (df_conv['date'] <= last_date)
        ]
        if not pc.empty:
            app_total  = int(pc['applicants'].sum())
            conf_total = int(pc['confirmed'].sum())
            rev_total  = int(pc['revenue'].sum())
            cr = round(conf_total / app_total * 100, 1) if app_total > 0 else 0
            lines.append(
                f"강의 신청 **{app_total:,}명** 중 **{conf_total:,}명** 수강 확정 "
                f"(전환율 **{cr}%**), 매출 **{rev_total:,}원**."
            )

    return lines


# ── 탭: 경영진 보고 ───────────────────────────────────────────────

def tab_report():
    ROOMS = load_rooms()
    st.header("📋 경영진 보고")

    # 데이터 완성도 뱃지
    _df_all = load_all()
    if not _df_all.empty:
        _first = _df_all['date'].min()
        _days_total = (date.today() - _first).days + 1
        _days_in    = _df_all['date'].nunique()
        _comp_pct   = round(_days_in / _days_total * 100, 1)
        _color = "green" if _comp_pct >= 90 else ("orange" if _comp_pct >= 70 else "red")
        st.caption(
            f"데이터 완성도 :{_color}[**{_comp_pct}%**] "
            f"({_days_in}/{_days_total}일 입력) — 기준일: {_df_all['date'].max()}"
        )

    df = load_all()
    if df.empty:
        st.info("데이터가 없습니다. '오늘 입력' 탭에서 먼저 데이터를 입력해주세요.")
        return

    max_date = df['date'].max()
    min_date = df['date'].min()
    today    = date.today()

    # ── 기간 선택 ───────────────────────────────────────────────
    period = st.radio(
        "보고 기간",
        ["이번 주", "이번 달", "최근 3개월", "전체", "직접 설정"],
        horizontal=True,
        key="report_period",
    )

    if period == "이번 주":
        date_from = today - timedelta(days=today.weekday())
        date_to   = max_date
        period_label = "이번 주"
    elif period == "이번 달":
        date_from = date(today.year, today.month, 1)
        date_to   = max_date
        period_label = "이번 달"
    elif period == "최근 3개월":
        date_from = today - timedelta(days=90)
        date_to   = max_date
        period_label = "최근 3개월"
    elif period == "전체":
        date_from = min_date
        date_to   = max_date
        period_label = "전체 기간"
    else:
        rc1, rc2 = st.columns(2)
        with rc1:
            date_from = st.date_input("시작일", value=min_date,
                                      min_value=min_date, max_value=max_date,
                                      key="report_from")
        with rc2:
            date_to = st.date_input("종료일", value=max_date,
                                    min_value=min_date, max_value=max_date,
                                    key="report_to")
        period_label = f"{date_from} ~ {date_to}"

    df_period = df[(df['date'] >= date_from) & (df['date'] <= date_to)]

    if df_period.empty:
        st.warning("선택한 기간에 데이터가 없습니다.")
        return

    period_dates = sorted(df_period['date'].unique())
    first_date   = period_dates[0]
    last_date    = period_dates[-1]

    # ── KPI 4개 ─────────────────────────────────────────────────
    st.divider()
    last_snap  = df_period[df_period['date'] == last_date]
    first_snap = df_period[df_period['date'] == first_date]
    total_now  = int(last_snap['members'].sum())
    total_past = int(first_snap['members'].sum()) if len(period_dates) > 1 else total_now
    diff       = total_now - total_past
    pct        = round(diff / total_past * 100, 1) if total_past > 0 else 0

    # ── 총원 변동 원인 분해 (활성 방 자연증감 vs 종료 방 제외) ──────
    _active_nums = set(load_rooms().keys())
    _arch_df = load_archived_rooms()
    _arch_nums = {int(r['room_num']) for _, r in _arch_df.iterrows()} if not _arch_df.empty else set()
    _sb = first_snap.set_index('room_num')['members']
    _eb = last_snap.set_index('room_num')['members']
    _active_start = int(_sb[[rn for rn in _sb.index if rn in _active_nums]].sum())
    _active_end   = int(_eb[[rn for rn in _eb.index if rn in _active_nums]].sum())
    _arch_start   = int(_sb[[rn for rn in _sb.index if rn in _arch_nums]].sum())
    _active_change = _active_end - _active_start
    _change_breakdown = None
    _closed_in_period = []
    if _arch_start > 0 and len(period_dates) > 1:
        _closed_in_period = [
            {'room': r['room_name'], 'final': int(r['final_members']),
             'date': str(r.get('archived_date', '')), 'reason': str(r.get('archive_reason', '') or '운영 종료')}
            for _, r in _arch_df.sort_values('room_num').iterrows()
            if int(r['room_num']) in set(_sb.index)
        ]
        _active_pct = round(_active_change / _active_start * 100, 1) if _active_start else 0
        _change_breakdown = {
            'start_total': total_past, 'end_total': total_now,
            'active_start': _active_start, 'active_end': _active_end,
            'active_change': _active_change, 'active_pct': _active_pct,
            'archived_removed': -_arch_start, 'archived_count': len(_closed_in_period),
            'archived_detail': _closed_in_period,
        }
        # 화면 안내 배너
        st.info(
            f"📉 **총원 변동 원인** — 기간 총원 {diff:+,}명 중 **{-_arch_start:+,}명**은 "
            f"강의를 마친 **{len(_closed_in_period)}개 방의 정상 종료**로 빠진 구조적 감소이며, "
            f"계속 운영 중인 방은 **{_active_change:+,}명({_active_pct:+.1f}%)**으로 안정적입니다."
        )

    df_adspend = load_adspend()
    df_conv    = load_conversions()

    period_spend = 0
    if not df_adspend.empty:
        period_spend = int(df_adspend[
            (df_adspend['date'] >= first_date) & (df_adspend['date'] <= last_date)
        ]['spend'].sum())

    conv_rate = 0
    if not df_conv.empty:
        pc = df_conv[(df_conv['date'] >= first_date) & (df_conv['date'] <= last_date)]
        if not pc.empty:
            app_t  = int(pc['applicants'].sum())
            conf_t = int(pc['confirmed'].sum())
            conv_rate = round(conf_t / app_t * 100, 1) if app_t > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "현재 총 인원",
        f"{total_now:,}명",
        f"{diff:+,}명 ({pct:+.1f}%)" if len(period_dates) > 1 else None,
    )
    k2.metric(
        "기간 순증감",
        f"{diff:+,}명",
        f"{first_date} 기준" if len(period_dates) > 1 else "단일 날짜",
        delta_color="normal",
    )
    k3.metric(
        "광고비 집행",
        f"{period_spend:,}원" if period_spend > 0 else "없음",
        f"CPM {round(period_spend/diff):,}원/명" if period_spend > 0 and diff > 0 else None,
    )
    k4.metric(
        "수강 전환율",
        f"{conv_rate}%" if conv_rate > 0 else "데이터 없음",
    )

    # ── 전주/전월 비교 KPI ───────────────────────────────────────
    _period_len = (last_date - first_date).days if hasattr(last_date, '__sub__') else 0
    try:
        _period_len = int((pd.Timestamp(last_date) - pd.Timestamp(first_date)).days)
    except Exception:
        _period_len = 0

    # 직전 동일 길이 구간 총원 (가장 가까운 기록 날짜 사용)
    def _nearest_total(target_date):
        """target_date에 가장 가까운 실제 기록일의 총원 합계."""
        d = pd.Timestamp(target_date)
        cands = df[df['date'] <= d.date()].copy()
        if cands.empty:
            return None
        nearest = cands['date'].max()
        return int(df[df['date'] == nearest]['members'].sum()), nearest

    _wow_col, _mom_col, _qoq_col = st.columns(3)

    # WoW (전주 대비): 7일 전 같은 총원
    _wow_date = pd.Timestamp(last_date) - pd.Timedelta(days=7)
    _wow = _nearest_total(_wow_date.date())
    with _wow_col:
        if _wow and _wow[0] > 0:
            _wow_diff = total_now - _wow[0]
            _wow_pct  = round(_wow_diff / _wow[0] * 100, 1)
            st.metric("전주 대비 (7일)", f"{_wow_diff:+,}명",
                      f"{_wow_pct:+.1f}% · 기준 {_wow[1]}",
                      delta_color="normal")
        else:
            st.metric("전주 대비 (7일)", "—", "데이터 부족")

    # MoM (전월 대비): 30일 전
    _mom_date = pd.Timestamp(last_date) - pd.Timedelta(days=30)
    _mom = _nearest_total(_mom_date.date())
    with _mom_col:
        if _mom and _mom[0] > 0:
            _mom_diff = total_now - _mom[0]
            _mom_pct  = round(_mom_diff / _mom[0] * 100, 1)
            st.metric("전월 대비 (30일)", f"{_mom_diff:+,}명",
                      f"{_mom_pct:+.1f}% · 기준 {_mom[1]}",
                      delta_color="normal")
        else:
            st.metric("전월 대비 (30일)", "—", "데이터 부족")

    # QoQ (전분기 대비): 90일 전
    _qoq_date = pd.Timestamp(last_date) - pd.Timedelta(days=90)
    _qoq = _nearest_total(_qoq_date.date())
    with _qoq_col:
        if _qoq and _qoq[0] > 0:
            _qoq_diff = total_now - _qoq[0]
            _qoq_pct  = round(_qoq_diff / _qoq[0] * 100, 1)
            st.metric("전분기 대비 (90일)", f"{_qoq_diff:+,}명",
                      f"{_qoq_pct:+.1f}% · 기준 {_qoq[1]}",
                      delta_color="normal")
        else:
            st.metric("전분기 대비 (90일)", "—", "데이터 부족")

    # ── 자동 인사이트 ────────────────────────────────────────────
    st.divider()
    insight_lines = _generate_insight(
        df_period, ROOMS, period_label,
        df_adspend=df_adspend if not df_adspend.empty else None,
        df_conv=df_conv if not df_conv.empty else None,
        df_all=df,
    )
    # 총원 변동 원인 + 전략 시사점 (종료 방이 있을 때 맨 앞에 삽입)
    if _change_breakdown:
        _bd = _change_breakdown
        _closed_names = ", ".join(d['room'].split('(')[-1].rstrip(')') if '(' in d['room'] else d['room']
                                  for d in _bd['archived_detail'][:5])
        insight_lines.insert(0,
            f"**총원 변동 원인**: 기간 감소 {diff:+,}명 중 **{_bd['archived_removed']:+,}명**은 "
            f"강의를 마친 {_bd['archived_count']}개 방({_closed_names})의 정상 종료에 따른 구조적 감소이며, "
            f"**운영 중인 방은 {_bd['active_change']:+,}명({_bd['active_pct']:+.1f}%)**으로 안정적입니다. "
            f"헤드라인 감소율({pct:.1f}%)을 실제 운영 부진으로 오해하지 않도록 유의가 필요합니다.")
        # 전략 시사점 — 종료 기수 대비 신규 기수 전환 효율
        try:
            _fdf_i = cohort_funnel_data(df, load_campaigns(), load_enrollments())
            _fdf_i = _fdf_i[_fdf_i['conversion'].notna()]
            if not _fdf_i.empty:
                _best = _fdf_i.loc[_fdf_i['conversion'].idxmax()]
                _worst = _fdf_i.loc[_fdf_i['conversion'].idxmin()]
                insight_lines.insert(1,
                    f"**차기 전략 시사점**: 전환율은 **{_best['product']} {_best['cohort']} {_best['conversion']:.1f}%**로 최고, "
                    f"{_worst['product']} {_worst['cohort']} {_worst['conversion']:.1f}%로 최저입니다. "
                    f"방을 닫아 총원이 줄더라도 전환율 높은 상품(예: 타로)의 모객·연계를 강화하면 "
                    f"인원 대비 매출 효율을 높일 수 있습니다.")
        except Exception:
            pass
    with st.container(border=True):
        st.markdown("#### 💡 자동 분석 인사이트")
        for line in insight_lines:
            st.markdown(f"- {line}")

    # ── 차트: 기간 총원 추이 + 채팅방별 현황 ────────────────────
    st.divider()
    fig_trend = period_total_trend(df_period, date_from, date_to)
    fig_snap  = room_snapshot_chart(df_period, ROOMS)

    col_l, col_r = st.columns([3, 2])
    with col_l:
        if fig_trend:
            st.plotly_chart(fig_trend)
    with col_r:
        if fig_snap:
            st.plotly_chart(fig_snap)

    # ── 채팅방별 증감 성과표 ─────────────────────────────────────
    st.divider()
    st.markdown("#### 채팅방별 성과 요약")

    perf_rows = []
    for rn in sorted(ROOMS.keys()):
        rdf = df_period[df_period['room_num'] == rn].sort_values('date')
        if rdf.empty:
            continue
        cur = int(rdf.iloc[-1]['members'])
        prev = int(rdf.iloc[0]['members']) if len(rdf) > 1 else cur
        chg = cur - prev
        pct_r = round(chg / prev * 100, 1) if prev > 0 else 0
        perf_rows.append({
            '채팅방':    ROOMS.get(rn, f"채팅방 {rn}"),
            '현재 인원': f"{cur:,}명",
            '증감':      f"{chg:+,}명",
            '증감률':    f"{pct_r:+.1f}%",
            '평가':      "📈" if chg > 0 else ("📉" if chg < 0 else "➡️"),
            '_members':  cur,
            '_change':   chg,
        })

    if perf_rows:
        perf_df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith('_')} for r in perf_rows])
        st.dataframe(perf_df, hide_index=True)

    # ── 광고비 요약 (데이터 있을 때만) ──────────────────────────
    ad_rows = []
    if period_spend > 0 and not df_adspend.empty:
        st.divider()
        st.markdown("#### 광고비 집행 내역")
        pa = df_adspend[
            (df_adspend['date'] >= first_date) & (df_adspend['date'] <= last_date)
        ].copy()
        if not pa.empty:
            by_ch = pa.groupby('channel')['spend'].sum().reset_index()
            by_ch.columns = ['채널', '집행 금액(원)']
            by_ch['비중'] = (by_ch['집행 금액(원)'] / by_ch['집행 금액(원)'].sum() * 100).round(1).astype(str) + '%'
            for _, row in by_ch.iterrows():
                ad_rows.append({'채널': row['채널'], '집행 금액(원)': f"{int(row['집행 금액(원)']):,}", '비중': row['비중']})
            by_ch_disp = by_ch.copy()
            by_ch_disp['집행 금액(원)'] = by_ch_disp['집행 금액(원)'].apply(lambda x: f"{int(x):,}")
            st.dataframe(by_ch_disp, hide_index=True)

    # ── 운영 종료 채팅방 비교 (선택) ────────────────────────────
    st.divider()
    df_arch_rep = load_archived_rooms()
    archived_report_rows = []

    if not df_arch_rep.empty:
        include_archived = st.checkbox(
            "🗂️ 종료 채팅방 비교 데이터 보고서에 포함",
            value=False,
            help="비교 분석이 필요할 때만 체크하세요. 기본적으로는 현재 운영 중인 채팅방만 표시됩니다.",
            key="report_include_archived",
        )
        if include_archived:
            st.caption(f"종료 채팅방 {len(df_arch_rep)}개가 아래 보고서에 포함됩니다.")
            _rep_members_by_room = {
                rn_: grp for rn_, grp in df.groupby('room_num')
            } if not df.empty else {}

            for _, ar in df_arch_rep.sort_values('room_num').iterrows():
                rn = int(ar['room_num'])
                rname = ar['room_name']
                arch_dt = str(ar.get('archived_date', '') or '')
                _raw = ar.get('actual_close_date', '')
                actual_dt = '' if pd.isna(_raw) else str(_raw).strip()
                final_m = int(ar.get('final_members', 0))
                reason = str(ar.get('archive_reason', '운영 종료') or '운영 종료')

                rdf = _rep_members_by_room.get(rn, pd.DataFrame())
                if not rdf.empty:
                    rdf = rdf.sort_values('date')
                peak_m  = int(rdf['members'].max())   if not rdf.empty else final_m
                op_days = int((rdf['date'].max() - rdf['date'].min()).days) + 1 if len(rdf) > 1 else 1
                net     = final_m - (int(rdf.iloc[0]['members']) if not rdf.empty else final_m)
                close_display = actual_dt if actual_dt else arch_dt

                archived_report_rows.append({
                    '채팅방':     rname,
                    '실제 종료일': close_display,
                    '처리일':     arch_dt,
                    '최종 인원':  final_m,
                    '최고 인원':  peak_m,
                    '순증감':     net,
                    '운영 기간':  op_days,
                    '종료 사유':  reason,
                })

            arch_disp_df = pd.DataFrame(archived_report_rows)
            arch_disp_df['최종 인원'] = arch_disp_df['최종 인원'].apply(lambda x: f"{x:,}명")
            arch_disp_df['최고 인원'] = arch_disp_df['최고 인원'].apply(lambda x: f"{x:,}명")
            arch_disp_df['순증감']    = arch_disp_df['순증감'].apply(lambda x: f"{x:+,}명")
            arch_disp_df['운영 기간'] = arch_disp_df['운영 기간'].apply(lambda x: f"{x:,}일")
            st.dataframe(arch_disp_df, hide_index=True)

    # ── HTML 보고서 다운로드 ─────────────────────────────────────
    st.divider()
    from report_generator import generate_html_report
    import plotly.io as _pio

    def _fig_to_fragment(fig) -> str:
        """Plotly figure → HTML 조각 (plotly.js 외부 참조, div만 반환)."""
        if fig is None:
            return ""
        try:
            return _pio.to_html(
                fig,
                include_plotlyjs=False,
                full_html=False,
                config={"displayModeBar": False, "responsive": True},
            )
        except Exception:
            return ""

    _snap_fragment  = _fig_to_fragment(fig_snap)
    _trend_fragment = _fig_to_fragment(fig_trend)

    # 전주/전월/전분기 비교 데이터 (보고서용)
    def _ref_snap(delta_days: int):
        ref = pd.Timestamp(last_date) - pd.Timedelta(days=delta_days)
        cands = df[df['date'] <= ref.date()]
        if cands.empty:
            return None, None
        nearest = cands['date'].max()
        return int(df[df['date'] == nearest]['members'].sum()), str(nearest)

    _comparison_rows = []
    for _label, _days in [("전주 대비 (7일)", 7), ("전월 대비 (30일)", 30), ("전분기 대비 (90일)", 90)]:
        _ref_total, _ref_date = _ref_snap(_days)
        if _ref_total and _ref_total > 0:
            _cd = total_now - _ref_total
            _cp = round(_cd / _ref_total * 100, 1)
            _comparison_rows.append({'label': _label, 'diff': _cd, 'pct': _cp, 'ref_date': _ref_date})

    # 전환 퍼널 (등록 데이터가 있는 기수만 보고서에 포함)
    _funnel_rows = None
    try:
        _fdf = cohort_funnel_data(df, load_campaigns(), load_enrollments(), rooms=ROOMS)
        if not _fdf.empty:
            _fd = _fdf[_fdf['conversion'].notna()]
            if not _fd.empty:
                _funnel_rows = [{
                    'label': f"{r['product']} {r['cohort']}",
                    'webinar_peak': int(r['webinar_peak']),
                    'enrolled': int(r['enrolled']),
                    'conversion': float(r['conversion']),
                    'revenue': int(r['revenue']),
                } for _, r in _fd.iterrows()]
    except Exception:
        _funnel_rows = None

    report_html = generate_html_report(
        period_label=period_label,
        first_date=first_date,
        last_date=last_date,
        total_now=total_now,
        diff=diff,
        pct=pct,
        period_spend=period_spend,
        conv_rate=conv_rate,
        insight_lines=insight_lines,
        perf_rows=perf_rows,
        ad_rows=ad_rows if ad_rows else None,
        chart_snap_html=_snap_fragment  or None,
        chart_trend_html=_trend_fragment or None,
        comparison_rows=_comparison_rows or None,
        archived_rows=archived_report_rows or None,
        funnel_rows=_funnel_rows,
    )
    # PDF 보고서 (대기업 업무 보고서 양식) — 서버에서 직접 생성
    _pdf_bytes = None
    try:
        from pdf_report import generate_pdf_report
        # 기간 총원 추이 시리즈 (일자별 총원)
        _trend_series = [
            (str(d), int(df_period[df_period['date'] == d]['members'].sum()))
            for d in sorted(df_period['date'].unique())
        ]
        _mark = None
        if _change_breakdown and _change_breakdown['archived_detail']:
            _md = _change_breakdown['archived_detail'][0]['date']
            _mark = (_md, "방 종료")
        # 종합 전략 요약 (전략 브리핑 + 상품군 통합표) — PDF 자동 삽입
        _strategy_rows = [(_t, _b) for _ic, _t, _b in _strategy_briefing()]
        _pm = _product_master_table()
        _product_master = _pm.to_dict('records') if not _pm.empty else None
        # 고객·전망 지표
        _customer_forecast = None
        try:
            _rp = load_cust_repeat_dist()
            _prr = load_cust_product_repeat()
            _mnr = load_cust_monthly_new_repeat()
            _xs = load_cust_cross_sell()
            _perf2 = load_monthly_performance()
            if not _rp.empty:
                _tc = int(_rp['customers'].sum())
                _rc = int(_rp[_rp['bucket'] != '1회']['customers'].sum())
                _nr = int(_mnr['new_revenue'].sum()) if not _mnr.empty else 0
                _rr2 = int(_mnr['repeat_revenue'].sum()) if not _mnr.empty else 0
                _rrm = 0
                if not _perf2.empty:
                    _cpl = _perf2[_perf2['month'] < date.today().strftime('%Y-%m')]
                    _rrm = _cpl['revenue'].tail(3).mean() if len(_cpl) >= 3 else 0
                _customer_forecast = {
                    'repeat_rate': _rc / _tc * 100 if _tc else 0,
                    'repeat_rev_share': _rr2 / (_nr + _rr2) * 100 if (_nr + _rr2) else 0,
                    'avg_ltv': int(_prr['avg_ltv'].mean()) if not _prr.empty else 0,
                    'cross_sell': float(_xs['rate'].max()) if not _xs.empty else 0,
                    'runrate_month': _rrm,
                    'runrate_year': _rrm * 12,
                }
        except Exception:
            _customer_forecast = None
        _pdf_bytes = generate_pdf_report(
            period_label=period_label,
            first_date=str(first_date), last_date=str(last_date),
            total_now=total_now, diff=diff, pct=pct,
            period_spend=period_spend, conv_rate=conv_rate,
            insight_lines=insight_lines, perf_rows=perf_rows,
            comparison_rows=_comparison_rows or None,
            funnel_rows=_funnel_rows,
            archived_rows=archived_report_rows or None,
            trend_series=_trend_series,
            change_breakdown=_change_breakdown,
            trend_mark=_mark,
            strategy_rows=_strategy_rows or None,
            product_master=_product_master,
            customer_forecast=_customer_forecast,
        )
    except Exception as _e:
        _pdf_bytes = None
        _pdf_err = str(_e)

    _fname = f"채팅방_모객전환_보고서_{period_label.replace(' ', '_').replace('~', '-')}_{date.today()}"
    dc1, dc2 = st.columns(2)
    with dc1:
        if _pdf_bytes:
            st.download_button(
                label="📄 PDF 보고서 다운로드 (바로 출력용)",
                data=_pdf_bytes,
                file_name=f"{_fname}.pdf",
                mime="application/pdf",
                width='stretch',
                type="primary",
            )
        else:
            st.button("📄 PDF 생성 실패", disabled=True, width='stretch')
            st.caption(f"PDF 엔진 오류: {_pdf_err if '_pdf_err' in dir() else '알 수 없음'}")
    with dc2:
        st.download_button(
            label="🖨️ HTML 보고서 (인터랙티브 차트)",
            data=report_html.encode("utf-8"),
            file_name=f"{_fname}.html",
            mime="text/html",
            width='stretch',
        )


# ── 탭 4: 채팅방 설정 ────────────────────────────────────────────

def tab_campaign():
    ROOMS = load_rooms()
    ROOM_NUMBERS = sorted(ROOMS.keys())
    st.header("채팅방 설정")

    # ── 채팅방 관리 ────────────────────────────────────────────
    with st.expander("➕ 채팅방 추가 / 수정 / 삭제", expanded=not bool(ROOMS)):
        st.caption("채팅방 번호와 이름을 등록하세요. 번호가 같으면 이름이 수정됩니다.")

        with st.form("room_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_room_num = st.number_input("채팅방 번호", min_value=1, step=1, value=1)
            with col_b:
                new_room_name = st.text_input("채팅방 이름", placeholder="예) 황금후추 돈버는 사주방 1기")
            if st.form_submit_button("저장", type="primary", width='stretch'):
                if not new_room_name.strip():
                    st.error("채팅방 이름을 입력해주세요.")
                else:
                    save_room(int(new_room_num), new_room_name.strip())
                    st.success(f"채팅방 {int(new_room_num)} — '{new_room_name.strip()}' 저장 완료")
                    st.rerun()

        if ROOMS:
            st.divider()
            st.markdown("**현재 등록된 채팅방**")
            st.caption("✏️ 수정 — 번호·이름 모두 변경 가능 / 🗑️ — 즉시 삭제")

            for rn in sorted(ROOMS.keys()):
                editing = (st.session_state._editing_room == rn)

                if editing:
                    # ── 인라인 수정 폼 ────────────────────────────────
                    with st.container(border=True):
                        ec1, ec2, ec3, ec4 = st.columns([1, 1, 4, 2])
                        with ec1:
                            new_rn = st.number_input(
                                "번호", min_value=1, step=1, value=rn,
                                key=f"edit_num_{rn}", label_visibility="collapsed"
                            )
                        with ec2:
                            st.markdown(f"<small style='color:grey'>현재: {rn}</small>",
                                        unsafe_allow_html=True)
                        with ec3:
                            new_name = st.text_input(
                                "이름", value=ROOMS[rn],
                                key=f"edit_name_{rn}", label_visibility="collapsed"
                            )
                        with ec4:
                            cs, cc = st.columns(2)
                            with cs:
                                if st.button("✅", key=f"save_{rn}",
                                             help="저장", width='stretch'):
                                    name_to_save = new_name.strip() or ROOMS[rn]
                                    if int(new_rn) != rn:
                                        # 번호 변경: 기존 삭제 후 새 번호로 등록
                                        delete_room(rn)
                                        save_room(int(new_rn), name_to_save)
                                        st.toast(f"채팅방 {rn} → {int(new_rn)} 변경 완료",
                                                 icon="✅")
                                    else:
                                        save_room(rn, name_to_save)
                                        st.toast(f"채팅방 {rn} 이름 수정 완료", icon="✅")
                                    st.session_state._editing_room = None
                                    load_rooms.clear()
                                    st.rerun()
                            with cc:
                                if st.button("❌", key=f"cancel_{rn}",
                                             help="취소", width='stretch'):
                                    st.session_state._editing_room = None
                                    st.rerun()
                else:
                    # ── 일반 행 ───────────────────────────────────────
                    col_num, col_name, col_edit, col_del = st.columns([1, 5, 1, 1])
                    with col_num:
                        st.write(f"**{rn}**")
                    with col_name:
                        st.write(ROOMS[rn])
                    with col_edit:
                        if st.button("✏️", key=f"edit_{rn}",
                                     help=f"채팅방 {rn} 수정"):
                            st.session_state._editing_room = rn
                            st.rerun()
                    with col_del:
                        if st.button("🗑️", key=f"del_{rn}",
                                     help=f"채팅방 {rn} 삭제"):
                            delete_room(rn)
                            st.toast(f"채팅방 {rn} 삭제 완료", icon="🗑️")
                            st.rerun()

    if not ROOMS:
        st.info("위에서 채팅방을 먼저 추가해주세요.")
        return

    st.divider()
    st.caption("각 채팅방이 어떤 강의 모객을 위해 운영되는지 입력하고 이력을 관리해요.")

    # ── 신규 캠페인 등록 ───────────────────────────────────────
    st.subheader("강의 정보 등록 / 변경")

    campaigns = get_current_campaigns()

    with st.form("campaign_form"):
        col1, col2 = st.columns(2)

        with col1:
            room_num = st.selectbox(
                "채팅방",
                options=ROOM_NUMBERS,
                format_func=lambda x: f"{ROOMS.get(x, f'채팅방 {x}')} (현재: {campaigns.get(x, {}).get('campaign_name', '미등록')})",
            )
            campaign_name = st.text_input(
                "강의명",
                placeholder="예) 돈타공 5기",
            )
            product = st.selectbox("상품 구분", options=PRODUCT_OPTIONS)

        with col2:
            cohort = st.text_input(
                "기수 / 회차",
                placeholder="예) 5기, 3회차",
            )
            start_date = st.date_input("모객 시작일", value=date.today())
            lecture_start_input = st.date_input(
                "개강일 (선택)",
                value=None,
                help="개강일을 입력하면 🎓 강의 분석 탭에서 잔류율 분석이 활성화됩니다.",
            )
            target_count = st.number_input(
                "목표 인원",
                min_value=0,
                value=0,
                step=100,
                help="0이면 목표 미설정. 추이 그래프에 점선으로 표시됩니다.",
            )
            memo = st.text_area(
                "메모",
                placeholder="특이사항 등 자유롭게 입력",
                height=80,
            )

        submitted = st.form_submit_button("💾 저장하기", type="primary", width='stretch')

        if submitted:
            if not campaign_name.strip():
                st.error("강의명을 입력해주세요.")
            else:
                save_campaign(
                    room_num=room_num,
                    campaign_name=campaign_name.strip(),
                    product=product,
                    cohort=cohort.strip(),
                    start_date=str(start_date),
                    memo=memo.strip(),
                    target_count=int(target_count),
                    lecture_start_date=str(lecture_start_input) if lecture_start_input else "",
                )
                st.success(f"✅ {ROOMS.get(room_num)} — '{campaign_name}' 저장 완료")
                st.rerun()

    st.divider()

    # ── 현재 진행 중인 캠페인 목록 ────────────────────────────
    st.subheader("현재 진행 중인 강의 목록")
    campaigns = get_current_campaigns()

    if not campaigns:
        st.info("등록된 강의가 없습니다. 위 양식에서 등록해주세요.")
    else:
        camp_rows = []
        for rn, info in sorted(campaigns.items()):
            camp_rows.append({
                '방 번호': rn,
                '채팅방': ROOMS.get(rn, f'채팅방 {rn}'),
                '강의명': info.get('campaign_name', '-'),
                '상품': info.get('product', '-'),
                '기수': info.get('cohort', '-'),
                '시작일': info.get('start_date', '-'),
                '메모': info.get('memo', '-'),
            })
        st.dataframe(pd.DataFrame(camp_rows), hide_index=True)

        # ── 개강일 빠른 업데이트 ─────────────────────────────────
        with st.expander("📅 개강일 설정 (강의 분석 잔류율 활성화)", expanded=False):
            st.caption("개강일을 등록하면 🎓 강의 분석 탭에서 개강 후 잔류율 차트가 표시됩니다.")
            upd_room = st.selectbox(
                "채팅방 선택",
                options=list(sorted(campaigns.keys())),
                format_func=lambda x: f"{ROOMS.get(x, f'채팅방 {x}')} — {campaigns[x].get('campaign_name', '')}",
                key="upd_lsd_room",
            )
            _cur_lsd = campaigns.get(upd_room, {}).get('lecture_start_date', '')
            _lsd_val = st.date_input(
                "개강일",
                value=pd.to_datetime(_cur_lsd).date() if _cur_lsd and str(_cur_lsd).strip() else None,
                key="upd_lsd_date",
            )
            if st.button("개강일 저장", key="upd_lsd_btn", type="primary"):
                update_lecture_start_date(upd_room, str(_lsd_val) if _lsd_val else "")
                st.success(f"개강일 저장 완료: {_lsd_val}")
                st.rerun()

        # ── 강의 종료 처리 ────────────────────────────────────────
        with st.expander("🏁 강의 종료 처리 (캠페인만 종료, 채팅방 유지)", expanded=False):
            end_room = st.selectbox(
                "종료할 채팅방",
                options=list(sorted(campaigns.keys())),
                format_func=lambda x: f"{ROOMS.get(x, f'채팅방 {x}')} — {campaigns[x].get('campaign_name', '')}",
                key="end_room_select",
            )
            if st.button("강의 종료 처리", key="end_btn"):
                end_campaign(end_room)
                st.success(f"'{campaigns[end_room].get('campaign_name')}' 종료 처리 완료")
                st.rerun()

    # ── 채팅방 운영 종료 처리 ─────────────────────────────────
    st.divider()
    st.subheader("🚪 채팅방 운영 종료 처리")
    st.caption(
        "채팅방에서 나갈 때 사용하세요. 활성 목록에서 제거되지만 **인원 이력·강의 기록은 모두 보존**됩니다. "
        "🎓 강의 분석 탭에서 이후에도 확인 가능합니다."
    )

    if ROOMS:
        df_for_final = load_all()
        arch_room = st.selectbox(
            "운영 종료할 채팅방",
            options=sorted(ROOMS.keys()),
            format_func=lambda x: f"{ROOMS.get(x, f'채팅방 {x}')} (채팅방 {x})",
            key="arch_room_select",
        )
        arch_reason = st.text_input(
            "종료 사유 (선택)",
            placeholder="예) 강의 완료, 채팅방 통합, 운영 중단",
            key="arch_reason_input",
        )
        arch_actual_close = st.date_input(
            "실제 종료일 (선택) — 처리일과 다를 경우 입력",
            value=None,
            key="arch_actual_close_input",
            help="채팅방을 실제로 나간 날짜. 비워두면 오늘(처리일)이 기준이 됩니다.",
        )

        # 최종 인원 자동 조회
        _final_m = 0
        if not df_for_final.empty:
            _rdf = df_for_final[df_for_final['room_num'] == arch_room].sort_values('date')
            if not _rdf.empty:
                _final_m = int(_rdf.iloc[-1]['members'])
        st.caption(f"마지막 기록 인원: **{_final_m:,}명** (자동 저장됩니다)")

        if st.button("🚪 운영 종료 처리", type="primary", key="arch_btn"):
            st.session_state['_pending_archive'] = arch_room

        if st.session_state.get('_pending_archive') == arch_room:
            st.error(
                f"**{ROOMS.get(arch_room)} (채팅방 {arch_room})** 를 운영 종료 처리합니다. "
                "활성 채팅방 목록에서 제거되며 인원 입력 폼에서 사라집니다. 계속하시겠습니까?"
            )
            ca, cb = st.columns(2)
            if ca.button("✅ 확인", type="primary", width='stretch', key="arch_confirm"):
                archive_room(
                    room_num=arch_room,
                    room_name=ROOMS.get(arch_room, f"채팅방 {arch_room}"),
                    final_members=_final_m,
                    reason=arch_reason.strip() or "운영 종료",
                    actual_close_date=str(arch_actual_close) if arch_actual_close else "",
                )
                st.session_state['_pending_archive'] = None
                st.success(f"✅ {ROOMS.get(arch_room)} 운영 종료 처리 완료. 이력은 🎓 강의 분석 탭에서 확인하세요.")
                st.rerun()
            if cb.button("❌ 취소", width='stretch', key="arch_cancel"):
                st.session_state['_pending_archive'] = None
                st.rerun()
    else:
        st.info("등록된 채팅방이 없습니다.")

    st.divider()

    # ── 전체 이력 조회 ─────────────────────────────────────────
    st.subheader("모객 이력 전체 조회")

    all_rooms_for_hist = load_all_room_names()
    _hist_options = sorted(all_rooms_for_hist.keys())
    history_room = st.selectbox(
        "채팅방 선택 (종료 채팅방 포함)",
        options=_hist_options,
        format_func=lambda x: all_rooms_for_hist.get(x, f"채팅방 {x}"),
        key="history_room_select",
    )

    history_df = get_history(history_room)
    if history_df.empty:
        st.info("이력이 없습니다.")
    else:
        history_df['is_current'] = history_df['is_current'].apply(lambda x: '✅ 진행 중' if x else '종료')
        disp_cols = ['room_num', 'campaign_name', 'product', 'cohort',
                     'start_date', 'lecture_start_date', 'end_date', 'is_current', 'memo']
        history_df = history_df[[c for c in disp_cols if c in history_df.columns]]
        col_map = {'room_num': '방 번호', 'campaign_name': '강의명', 'product': '상품',
                   'cohort': '기수', 'start_date': '모객 시작', 'lecture_start_date': '개강일',
                   'end_date': '종료일', 'is_current': '상태', 'memo': '메모'}
        history_df = history_df.rename(columns=col_map)
        st.dataframe(history_df, hide_index=True)


# ── 탭 5: 데이터 관리 ─────────────────────────────────────────────

def tab_data():
    ROOMS = load_rooms()
    ROOM_NUMBERS = sorted(ROOMS.keys())
    st.header("데이터 관리")
    df = load_all()

    # ── 누락 날짜 소급 입력 ───────────────────────────────────
    if not df.empty:
        from datetime import timedelta as _td2
        _first = df['date'].min()
        _days_total = (date.today() - _first).days + 1
        _all_range  = set(str(_first + _td2(days=i)) for i in range(_days_total))
        _entered    = set(df['date'].astype(str).unique())
        _missing    = sorted(_all_range - _entered, reverse=True)

        if _missing:
            with st.expander(f"📅 누락 날짜 소급 입력 ({len(_missing)}일 누락)", expanded=True):
                st.caption("아래 날짜는 데이터가 입력되지 않았습니다. 날짜를 선택하여 바로 소급 입력하세요.")

                _sel_missing = st.selectbox(
                    "소급 입력할 날짜 선택",
                    options=_missing,
                    key="missing_date_select",
                )

                # 해당 날짜 전일의 인원을 기본값으로
                _prev_date_cands = df[df['date'].astype(str) < _sel_missing]
                _backfill_prev = {}
                if not _prev_date_cands.empty:
                    _prev_nearest = _prev_date_cands['date'].max()
                    _bp = _prev_date_cands[_prev_date_cands['date'] == _prev_nearest]
                    _backfill_prev = {int(r['room_num']): int(r['members']) for _, r in _bp.iterrows()}

                st.markdown(f"**{_sel_missing} 인원 입력** — 전일({_backfill_prev and _prev_date_cands['date'].max() or '없음'}) 값으로 초기화됨")
                _bf_rows = [
                    {'채팅방번호': rn, '채팅방명': ROOMS.get(rn, f"채팅방 {rn}"), '인원수': _backfill_prev.get(rn, 0)}
                    for rn in ROOM_NUMBERS
                ]
                _bf_edited = st.data_editor(
                    pd.DataFrame(_bf_rows),
                    column_config={
                        '채팅방번호': st.column_config.NumberColumn(disabled=True),
                        '채팅방명':   st.column_config.TextColumn(disabled=True),
                        '인원수':     st.column_config.NumberColumn(min_value=0, step=1, required=True),
                    },
                    hide_index=True,
                    key=f"backfill_editor_{_sel_missing}",
                )
                if st.button("💾 소급 입력 저장", type="primary", key="backfill_save"):
                    _bf_data = [
                        {'room_num': int(r['채팅방번호']), 'room_name': str(r['채팅방명']), 'members': int(r['인원수'])}
                        for _, r in _bf_edited.iterrows() if int(r['인원수']) > 0
                    ]
                    if _bf_data:
                        with st.spinner("저장 중..."):
                            save_daily(_sel_missing, _bf_data)
                        load_all.clear()
                        st.success(f"✅ {_sel_missing} 소급 입력 완료 — {len(_bf_data)}개 채팅방")
                        st.rerun()
                    else:
                        st.warning("입력된 인원이 없습니다.")
        else:
            st.success(f"✅ 누락 날짜 없음 — {_first}부터 오늘까지 모든 날짜 입력 완료")

    st.divider()

    # ── 날짜별 데이터 수정 ─────────────────────────────────────
    st.subheader("날짜별 데이터 수정")
    st.caption("OCR 오류 등으로 잘못 저장된 데이터를 날짜를 선택해 직접 수정할 수 있습니다.")

    existing_dates = sorted(df['date'].astype(str).unique().tolist(), reverse=True) if not df.empty else []

    edit_mode = st.radio(
        "날짜 선택 방식",
        ["기존 날짜 수정", "새 날짜 직접 입력"],
        horizontal=True,
        key="edit_mode_radio",
    )

    if edit_mode == "기존 날짜 수정" and existing_dates:
        edit_date_str = st.selectbox("수정할 날짜", options=existing_dates, key="edit_date_select")
    else:
        edit_date_input = st.date_input("날짜 입력", value=date.today(), key="edit_date_new")
        edit_date_str = str(edit_date_input)

    # 해당 날짜의 현재 데이터 로드
    if not df.empty:
        df_edit = df[df['date'].astype(str) == edit_date_str]
        current = {int(row['room_num']): int(row['members']) for _, row in df_edit.iterrows()}
    else:
        current = {}

    # st.data_editor 기반 인라인 편집
    st.markdown(f"**{edit_date_str} 인원 수정** — 셀을 직접 클릭해 수정 후 저장 버튼을 누르세요.")
    editor_rows = [
        {'채팅방번호': rn, '채팅방명': ROOMS.get(rn, f"채팅방 {rn}"), '인원수': current.get(rn, 0)}
        for rn in ROOM_NUMBERS
    ]
    editor_df = pd.DataFrame(editor_rows)
    edited = st.data_editor(
        editor_df,
        column_config={
            '채팅방번호': st.column_config.NumberColumn(disabled=True),
            '채팅방명':   st.column_config.TextColumn(disabled=True),
            '인원수':     st.column_config.NumberColumn(min_value=0, step=1, required=True),
        },
        hide_index=True,
        key=f"data_editor_{edit_date_str}",
    )
    if st.button("💾 수정 저장", type="primary", key="data_editor_save"):
        room_data = [
            {'room_num': int(row['채팅방번호']), 'room_name': str(row['채팅방명']), 'members': int(row['인원수'])}
            for _, row in edited.iterrows() if int(row['인원수']) > 0
        ]
        if room_data:
            with st.spinner("저장 중..."):
                save_daily(edit_date_str, room_data)
            st.success(f"✅ {edit_date_str} 데이터 수정 완료 — {len(room_data)}개 채팅방")
            st.rerun()
        else:
            st.warning("입력된 인원이 없습니다.")

    st.divider()

    if df.empty:
        st.info("데이터가 없습니다.")
        return

    # ── 전체 데이터 표시 (필터 포함) ──────────────────────────
    st.subheader("전체 데이터")
    _fcol1, _fcol2 = st.columns(2)
    with _fcol1:
        _date_opts = ['전체'] + sorted(df['date'].astype(str).unique().tolist(), reverse=True)
        _sel_date = st.selectbox("날짜 필터", options=_date_opts, key="data_filter_date")
    with _fcol2:
        _room_opts = ['전체'] + [f"{rn} — {nm}" for rn, nm in sorted(ROOMS.items())]
        _sel_room = st.selectbox("채팅방 필터", options=_room_opts, key="data_filter_room")

    show = df.copy()
    if _sel_date != '전체':
        show = show[show['date'].astype(str) == _sel_date]
    if _sel_room != '전체':
        _rn = int(_sel_room.split(' — ')[0])
        show = show[show['room_num'] == _rn]
    show = show.sort_values(['date', 'room_num'], ascending=[False, True]).reset_index(drop=True)
    st.dataframe(show, hide_index=True)
    st.caption(f"{len(show)}행 표시 중 (전체 {len(df)}행)")

    col_csv, col_excel, col_zip = st.columns(3)

    with col_csv:
        csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 CSV 다운로드",
            data=csv_bytes,
            file_name=f"채팅방_인원_{date.today()}.csv",
            mime='text/csv',
            width='stretch',
        )

    with col_excel:
        from excel_export import generate_excel
        _campaigns  = get_current_campaigns()
        _df_conv    = load_conversions()
        _df_adspend = load_adspend()
        _df_content = load_content()
        excel_bytes = generate_excel(
            df, _campaigns,
            df_conv=_df_conv,
            df_adspend=_df_adspend,
            df_content=_df_content,
            rooms=ROOMS,
        )
        st.download_button(
            "📊 Excel 보고서 다운로드",
            data=excel_bytes,
            file_name=f"채팅방_인원_보고서_{date.today()}.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            width='stretch',
        )

    with col_zip:
        import zipfile, io as _io
        _zip_buf = _io.BytesIO()
        with zipfile.ZipFile(_zip_buf, 'w', zipfile.ZIP_DEFLATED) as _zf:
            _zip_data = {
                '인원_members.csv':     df,
                '강의_campaigns.csv':   load_campaigns(),
                '전환_conversions.csv': _df_conv,
                '광고비_adspend.csv':   _df_adspend,
                '콘텐츠_content.csv':  _df_content,
                '날짜메모_notes.csv':   load_date_notes(),
            }
            for _fname, _ddf in _zip_data.items():
                if _ddf is not None and not _ddf.empty:
                    _zf.writestr(_fname, _ddf.to_csv(index=False, encoding='utf-8-sig'))
        st.download_button(
            "📦 전체 백업 ZIP",
            data=_zip_buf.getvalue(),
            file_name=f"채팅방_전체백업_{date.today()}.zip",
            mime='application/zip',
            width='stretch',
            help="모든 CSV 데이터를 하나의 ZIP 파일로 다운로드합니다",
        )

    # ── 날짜 데이터 삭제 (2단계 확인) ─────────────────────────
    st.divider()
    st.subheader("날짜 데이터 삭제")
    dates = sorted(df['date'].astype(str).unique().tolist(), reverse=True)
    del_date = st.selectbox("삭제할 날짜", options=dates, key="del_date_select")

    if st.button("🗑️ 삭제 요청", type="secondary"):
        st.session_state.pending_delete_date = del_date

    if st.session_state.pending_delete_date == del_date:
        st.error(
            f"'{del_date}' 데이터를 영구 삭제합니다. 되돌릴 수 없습니다. 계속하시겠습니까?"
        )
        col_yes, col_no = st.columns(2)
        if col_yes.button("✅ 확인 삭제", type="primary", width='stretch'):
            delete_date(del_date)
            st.session_state.pending_delete_date = None
            st.success(f"✅ {del_date} 데이터 삭제 완료")
            st.rerun()
        if col_no.button("❌ 취소", width='stretch'):
            st.session_state.pending_delete_date = None
            st.rerun()


if __name__ == '__main__':
    main()
