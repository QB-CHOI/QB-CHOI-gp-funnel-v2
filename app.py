import streamlit as st
import pandas as pd
from datetime import date

from github_store import (
    load_all, save_daily, delete_date,
    load_campaigns, get_current_campaigns,
    save_campaign, end_campaign, get_history,
    load_rooms, save_room, delete_room,
    load_conversions, save_conversion, get_latest_conversions,
    load_adspend, save_adspend,
    load_content, save_content, delete_content_row,
    load_date_notes, save_date_note,
    PRODUCT_OPTIONS, CHANNEL_OPTIONS, CONTENT_TYPE_OPTIONS,
)
from charts import (
    trend_line_chart, change_bar_chart, total_trend_bar,
    product_bar_chart, weekly_comparison_chart, cohort_trend_chart,
    funnel_chart, conversion_rate_chart, cohort_conversion_chart,
    churn_rate_chart, roi_chart,
)

st.set_page_config(
    page_title="채팅방 인원 분석",
    page_icon="💬",
    layout="wide",
)

# ── 사이드바 — 캐시 새로고침 ─────────────────────────────────────

with st.sidebar:
    st.markdown("### 💬 채팅방 인원 분석")
    st.divider()

    # 오늘 입력 상태
    _df_check = load_all()
    _today_str = str(date.today())
    if _df_check.empty or _today_str not in _df_check['date'].astype(str).values:
        st.error(f"⚠️ 오늘({_today_str}) 데이터 미입력", icon="🚨")
    else:
        _n_today = len(_df_check[_df_check['date'].astype(str) == _today_str])
        st.success(f"✅ 오늘 {_n_today}개 방 입력 완료")

    st.divider()
    if st.button("🔄 데이터 새로고침", use_container_width=True,
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
            pct = abs(diff / prev_val * 100) if prev_val else 0
            if pct > 50 or abs(diff) > 500:
                status = "🚨 확인 필요"
                has_warning = True
            elif pct > 20 or abs(diff) > 200:
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
        use_container_width=True,
        hide_index=True,
        column_config={
            "인식값": st.column_config.NumberColumn(format="%d명"),
            "전일": st.column_config.NumberColumn(format="%d명"),
            "증감": st.column_config.NumberColumn(format="%+d명"),
        },
    )


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    st.title("💬 황금후추 채팅방 인원 분석")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📸 오늘 입력", "📊 현황", "📋 전환 분석", "📈 추이 그래프", "⚙️ 채팅방 설정", "🗂️ 데이터 관리"
    ])

    with tab1:
        tab_input()
    with tab2:
        tab_dashboard()
    with tab3:
        tab_conversion()
    with tab4:
        tab_trend()
    with tab5:
        tab_campaign()
    with tab6:
        tab_data()


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
        from ocr_parser import extract_from_image

        images = []
        for f in uploaded_files:
            f.seek(0)
            images.append((f.name, Image.open(f).copy()))

        img_cols = st.columns(min(len(images), 3))
        for i, (name, img) in enumerate(images):
            with img_cols[i % 3]:
                st.image(img, caption=name, use_container_width=True)

        if not st.session_state.ocr_done:
            with st.spinner(f"{len(images)}장 인식 중..."):
                merged = {}
                try:
                    for _, img in images:
                        for r in extract_from_image(img, ROOMS):
                            if r['room_num'] not in merged:
                                merged[r['room_num']] = r['members']
                except Exception:
                    pass

                st.session_state.ocr_results = merged
                st.session_state.ocr_done = True
                for rn in ROOMS:
                    if rn in merged:
                        st.session_state[f"inp_{rn}"] = merged[rn]
                    elif prev.get(rn) is not None:
                        st.session_state[f"inp_{rn}"] = int(prev[rn])
                    else:
                        st.session_state[f"inp_{rn}"] = 0

                if merged:
                    st.success(f"✅ {len(merged)}개 채팅방 인식 — 아래에서 숫자 확인 후 저장하세요.")
                else:
                    st.info("자동 인식에 실패했습니다. 아래 2단계에서 어제 값을 확인하고 수정해 저장하세요.")
        else:
            st.success(f"✅ {len(st.session_state.ocr_results)}개 채팅방 인식 완료")
            if st.button("🔄 다시 인식"):
                st.session_state.ocr_done = False
                st.rerun()

        # ── 인식 결과 검토 테이블 (미인식 방 포함 전체 표시) ─────
        if st.session_state.ocr_done:
            _show_ocr_review(st.session_state.ocr_results, ROOMS, prev)

    # ── 채팅방 이름 수정 ───────────────────────────────────────
    with st.expander("✏️ 채팅방 이름 수정"):
        st.caption("이름을 바꾸면 GitHub에 바로 저장됩니다.")
        with st.form("room_name_edit_form"):
            name_inputs = {}
            name_cols = st.columns(3)
            for idx, rn in enumerate(ROOM_NUMBERS):
                with name_cols[idx % 3]:
                    name_inputs[rn] = st.text_input(
                        f"채팅방 {rn}",
                        value=ROOMS[rn],
                        key=f"name_edit_{rn}",
                    )
            if st.form_submit_button("이름 저장", type="primary", use_container_width=True):
                changed = [(rn, name_inputs[rn].strip()) for rn in ROOM_NUMBERS
                           if name_inputs[rn].strip() and name_inputs[rn].strip() != ROOMS[rn]]
                if changed:
                    for rn, new_name in changed:
                        save_room(rn, new_name)
                    st.success(f"✅ {len(changed)}개 채팅방 이름 저장 완료")
                    st.rerun()
                else:
                    st.info("변경된 이름이 없습니다.")

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

            if ocr_val is not None and prev_val is not None:
                diff = int(ocr_val) - int(prev_val)
                sign = "+" if diff >= 0 else ""
                help_msg = f"전일: {int(prev_val):,}명  ({sign}{diff:,})"
            elif prev_val is not None:
                help_msg = f"어제: {int(prev_val):,}명"
            else:
                help_msg = "이전 데이터 없음"

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
        if st.button("💾 저장하기", type="primary", use_container_width=True):
            room_data = [
                {'room_num': rn, 'room_name': ROOMS[rn], 'members': v}
                for rn, v in edited.items()
                if v > 0
            ]
            missing_rooms = [ROOMS[rn] for rn, v in edited.items() if v == 0]
            if room_data:
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
            else:
                st.warning("입력된 인원이 없습니다. 숫자를 확인해주세요.")

    with col_reset:
        if st.button("초기화", use_container_width=True):
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
    st.caption(f"기준: {latest_date}")

    df_today = df[df['date'] == latest_date].copy()
    campaigns = get_current_campaigns()

    # ── 입력 완성도 경고 ───────────────────────────────────────
    total_rooms = len(ROOMS)
    entered_rooms = len(df_today)
    if entered_rooms < total_rooms:
        missing_names = [ROOMS[rn] for rn in sorted(ROOMS.keys())
                         if rn not in df_today['room_num'].values]
        st.warning(
            f"⚠️ 오늘({latest_date}) {total_rooms - entered_rooms}개 채팅방 미입력: " +
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

    # ── 증감 차트 + 상품별 분석 ───────────────────────────────
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        fig_bar = change_bar_chart(df_today, rooms=ROOMS)
        if fig_bar:
            st.plotly_chart(fig_bar, use_container_width=True)
    with col_c2:
        fig_prod = product_bar_chart(df, campaigns)
        if fig_prod:
            st.plotly_chart(fig_prod, use_container_width=True)
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
        use_container_width=True,
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
                st.plotly_chart(fig_churn, use_container_width=True)

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
        st.dataframe(pd.DataFrame(camp_rows), use_container_width=True, hide_index=True)

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
    st.caption("채팅방 인원 → 강의 신청 → 수강 확정까지 전환 흐름을 기록하고 분석합니다.")

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
        st.plotly_chart(fig_funnel, use_container_width=True)

    # ── 전환율 차트 ────────────────────────────────────────────
    fig_conv = conversion_rate_chart(df_conv, campaigns, rooms=ROOMS)
    if fig_conv:
        st.plotly_chart(fig_conv, use_container_width=True)

    # ── 기수별 전환율 비교 ─────────────────────────────────────
    fig_cohort_conv = cohort_conversion_chart(df_conv, campaigns, rooms=ROOMS)
    if fig_cohort_conv:
        st.plotly_chart(fig_cohort_conv, use_container_width=True)
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

        if st.form_submit_button("💾 저장", type="primary", use_container_width=True):
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
        st.dataframe(disp, use_container_width=True, hide_index=True)

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
        st.plotly_chart(fig_roi, use_container_width=True)

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

            if st.form_submit_button("💾 광고비 저장", type="primary", use_container_width=True):
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
            st.dataframe(ad_disp, use_container_width=True, hide_index=True)

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

            if st.form_submit_button("💾 콘텐츠 저장", type="primary", use_container_width=True):
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
                use_container_width=True, hide_index=True,
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
            st.dataframe(pd.DataFrame(effect_rows), use_container_width=True, hide_index=True)
        else:
            st.info("발행일 전후 3일 내 인원 데이터가 충분하지 않아 분석할 수 없습니다.")


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
        st.plotly_chart(fig_line, use_container_width=True)

    # 전체 합계 막대 차트
    fig_total = total_trend_bar(df_filtered)
    if fig_total:
        st.plotly_chart(fig_total, use_container_width=True)

    # ── 주간 비교 차트 ──────────────────────────────────────────
    fig_week = weekly_comparison_chart(df_filtered, rooms=ROOMS)
    if fig_week:
        st.plotly_chart(fig_week, use_container_width=True)
    else:
        st.info("주간 비교는 5일 이상 간격의 데이터가 있으면 자동으로 표시됩니다.")

    # ── D+N 모객 곡선 ───────────────────────────────────────────
    st.subheader("강의별 모객 곡선 비교 (D+N일 기준)")
    cohort_mode = st.radio("표시 방식", ["절대값", "순증감"], horizontal=True, key="cohort_mode")
    fig_cohort = cohort_trend_chart(df, campaigns, rooms=ROOMS, mode=cohort_mode)
    if fig_cohort:
        st.plotly_chart(fig_cohort, use_container_width=True)
    else:
        st.info("⚙️ 채팅방 설정 탭에서 강의를 등록하면 모객 곡선이 표시됩니다.")

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
                st.dataframe(_tn_disp, use_container_width=True, hide_index=True)


# ── 탭 4: 채팅방 설정 ────────────────────────────────────────────

def tab_campaign():
    ROOMS = load_rooms()
    ROOM_NUMBERS = sorted(ROOMS.keys())
    st.header("채팅방 설정")

    # ── Gemini API 진단 (항상 표시) ────────────────────────────
    with st.expander("🔍 Gemini API 진단", expanded=True):
        import requests as _req2
        _key = st.secrets.get("gemini_api_key", "")

        if not _key:
            st.error("❌ gemini_api_key 가 Streamlit Secrets에 없습니다.")
            st.markdown(
                "**설정 방법:**\n"
                "1. [share.streamlit.io](https://share.streamlit.io) → 앱 → ⋮ → Settings → Secrets\n"
                "2. 아래를 정확히 입력 후 **Save**:\n"
                "```toml\ngemini_api_key = \"AIzaSy...\"\n```"
            )
        else:
            masked = _key[:8] + "..." + _key[-4:] if len(_key) > 12 else "***"
            st.info(f"등록된 키: `{masked}` (길이: {len(_key)}자)")

            if st.button("🔍 API 연결 테스트 실행", key="diag_test"):
                with st.spinner("테스트 중..."):
                    try:
                        r = _req2.get(
                            f"https://generativelanguage.googleapis.com/v1beta/models?key={_key}",
                            timeout=15
                        )
                        st.write(f"HTTP 상태 코드: **{r.status_code}**")
                        if r.status_code == 200:
                            models = [m["name"] for m in r.json().get("models", [])]
                            vision = [m for m in models if "flash" in m or "pro" in m]
                            st.success(f"✅ 키 정상 — 전체 모델 {len(models)}개, 비전 모델 {len(vision)}개")
                            st.write("사용 가능한 모델:", vision[:8])
                        elif r.status_code == 400:
                            st.error(f"❌ 키 오류 (400): {r.json().get('error',{}).get('message','')}")
                            st.warning("→ Streamlit Secrets에서 키를 삭제하고 새 키로 교체하세요.")
                        elif r.status_code == 403:
                            st.error("❌ 권한 오류 (403): Generative Language API가 비활성화 상태")
                            st.warning("→ console.cloud.google.com에서 'Generative Language API' 활성화")
                        else:
                            st.error(f"❌ 오류 {r.status_code}: {r.text[:300]}")
                    except Exception as e:
                        st.error(f"연결 실패: {e}")

    # ── 채팅방 관리 ────────────────────────────────────────────
    with st.expander("➕ 채팅방 추가 / 수정 / 삭제", expanded=not bool(ROOMS)):
        st.caption("채팅방 번호와 이름을 등록하세요. 번호가 같으면 이름이 수정됩니다.")

        with st.form("room_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_room_num = st.number_input("채팅방 번호", min_value=1, step=1, value=1)
            with col_b:
                new_room_name = st.text_input("채팅방 이름", placeholder="예) 황금후추 돈버는 사주방 1기")
            if st.form_submit_button("저장", type="primary", use_container_width=True):
                if not new_room_name.strip():
                    st.error("채팅방 이름을 입력해주세요.")
                else:
                    save_room(int(new_room_num), new_room_name.strip())
                    st.success(f"채팅방 {int(new_room_num)} — '{new_room_name.strip()}' 저장 완료")
                    st.rerun()

        if ROOMS:
            st.divider()
            st.markdown("**현재 등록된 채팅방**")
            rooms_df = pd.DataFrame(
                [{"번호": k, "이름": v} for k, v in sorted(ROOMS.items())]
            )
            st.dataframe(rooms_df, use_container_width=True, hide_index=True)

            with st.form("room_delete_form"):
                del_room = st.selectbox(
                    "삭제할 채팅방",
                    options=ROOM_NUMBERS,
                    format_func=lambda x: f"{x} — {ROOMS.get(x, '')}",
                )
                if st.form_submit_button("삭제", type="secondary", use_container_width=True):
                    delete_room(del_room)
                    st.success(f"채팅방 {del_room} 삭제 완료")
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

        submitted = st.form_submit_button("💾 저장하기", type="primary", use_container_width=True)

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
        st.dataframe(pd.DataFrame(camp_rows), use_container_width=True, hide_index=True)

        # 종료 처리
        with st.expander("강의 종료 처리"):
            end_room = st.selectbox(
                "종료할 채팅방",
                options=list(sorted(campaigns.keys())),
                format_func=lambda x: f"{ROOMS.get(x, f'채팅방 {x}')} — {campaigns[x].get('campaign_name', '')}",
                key="end_room_select",
            )
            if st.button("종료 처리", key="end_btn"):
                end_campaign(end_room)
                st.success(f"'{campaigns[end_room].get('campaign_name')}' 종료 처리 완료")
                st.rerun()

    st.divider()

    # ── 전체 이력 조회 ─────────────────────────────────────────
    st.subheader("모객 이력 전체 조회")

    history_room = st.selectbox(
        "채팅방 선택",
        options=ROOM_NUMBERS,
        format_func=lambda x: ROOMS.get(x, f"채팅방 {x}"),
        key="history_room_select",
    )

    history_df = get_history(history_room)
    if history_df.empty:
        st.info("이력이 없습니다.")
    else:
        history_df['is_current'] = history_df['is_current'].apply(lambda x: '✅ 진행 중' if x else '종료')
        disp_cols = ['room_num', 'campaign_name', 'product', 'cohort',
                     'start_date', 'end_date', 'is_current', 'memo']
        history_df = history_df[[c for c in disp_cols if c in history_df.columns]]
        history_df.columns = ['방 번호', '강의명', '상품', '기수', '시작일', '종료일', '상태', '메모']
        st.dataframe(history_df, use_container_width=True, hide_index=True)


# ── 탭 5: 데이터 관리 ─────────────────────────────────────────────

def tab_data():
    ROOMS = load_rooms()
    ROOM_NUMBERS = sorted(ROOMS.keys())
    st.header("데이터 관리")
    df = load_all()

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

    with st.form("data_edit_form"):
        st.markdown(f"**{edit_date_str} 인원 수정** — 0은 미입력으로 처리")
        edit_cols = st.columns(3)
        edit_vals = {}
        for idx, rn in enumerate(ROOM_NUMBERS):
            with edit_cols[idx % 3]:
                edit_vals[rn] = st.number_input(
                    ROOMS.get(rn, f"채팅방 {rn}"),
                    min_value=0,
                    value=current.get(rn, 0),
                    step=1,
                    key=f"edit_{rn}",
                )

        if st.form_submit_button("💾 수정 저장", type="primary", use_container_width=True):
            room_data = [
                {'room_num': rn, 'room_name': ROOMS.get(rn, f'채팅방 {rn}'), 'members': v}
                for rn, v in edit_vals.items() if v > 0
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
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.caption(f"{len(show)}행 표시 중 (전체 {len(df)}행)")

    col_csv, col_excel, col_zip = st.columns(3)

    with col_csv:
        csv_bytes = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 CSV 다운로드",
            data=csv_bytes,
            file_name=f"채팅방_인원_{date.today()}.csv",
            mime='text/csv',
            use_container_width=True,
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
        )
        st.download_button(
            "📊 Excel 보고서 다운로드",
            data=excel_bytes,
            file_name=f"채팅방_인원_보고서_{date.today()}.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            use_container_width=True,
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
            use_container_width=True,
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
        if col_yes.button("✅ 확인 삭제", type="primary", use_container_width=True):
            delete_date(del_date)
            st.session_state.pending_delete_date = None
            st.success(f"✅ {del_date} 데이터 삭제 완료")
            st.rerun()
        if col_no.button("❌ 취소", use_container_width=True):
            st.session_state.pending_delete_date = None
            st.rerun()


if __name__ == '__main__':
    main()
