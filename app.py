import streamlit as st
import pandas as pd
from datetime import date

from github_store import (
    load_all, save_daily, delete_date,
    load_campaigns, get_current_campaigns,
    save_campaign, end_campaign, get_history,
    load_rooms, save_room, delete_room,
    PRODUCT_OPTIONS,
)
from charts import trend_line_chart, change_bar_chart, total_trend_bar, product_bar_chart, weekly_comparison_chart

st.set_page_config(
    page_title="채팅방 인원 분석",
    page_icon="💬",
    layout="wide",
)

# ── 세션 상태 초기화 ──────────────────────────────────────────────

if 'ocr_results' not in st.session_state:
    st.session_state.ocr_results = {}
if 'ocr_done' not in st.session_state:
    st.session_state.ocr_done = False
if 'uploaded_file_names' not in st.session_state:
    st.session_state.uploaded_file_names = []



# ── 메인 ─────────────────────────────────────────────────────────

def main():
    st.title("💬 황금후추 채팅방 인원 분석")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📸 오늘 입력", "📊 현황", "📈 추이 그래프", "⚙️ 채팅방 설정", "🗂️ 데이터 관리"
    ])

    with tab1:
        tab_input()
    with tab2:
        tab_dashboard()
    with tab3:
        tab_trend()
    with tab4:
        tab_campaign()
    with tab5:
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

    # ── OCR 업로드 ─────────────────────────────────────────────
    st.subheader("1단계 — 스크린샷 업로드")
    st.caption("채팅방 목록 화면을 캡처해서 올려주세요. 스크롤이 필요하면 여러 장을 한 번에 올려도 됩니다.")

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

        # 파일을 한 번만 읽어서 재사용 (파일 포인터 소진 방지)
        images = []
        for f in uploaded_files:
            f.seek(0)
            images.append((f.name, Image.open(f).copy()))

        # 미리보기
        img_cols = st.columns(min(len(images), 3))
        for i, (name, img) in enumerate(images):
            with img_cols[i % 3]:
                st.image(img, caption=name, use_container_width=True)

        if not st.session_state.ocr_done:
            with st.spinner(f"{len(images)}장 인식 중..."):
                try:
                    merged = {}
                    for _, img in images:
                        extracted = extract_from_image(img)
                        for r in extracted:
                            merged[r['room_num']] = r['members']

                    st.session_state.ocr_results = merged
                    st.session_state.ocr_done = True

                    for rn, val in merged.items():
                        st.session_state[f"inp_{rn}"] = val

                    st.success(f"✅ {len(merged)}개 채팅방 인식 완료 ({len(images)}장 처리)")
                except Exception as e:
                    st.error(f"OCR 오류: {e}")
                    st.info("아래 표에서 직접 숫자를 입력해도 됩니다.")
        else:
            st.success(f"✅ {len(st.session_state.ocr_results)}개 채팅방 인식 완료 ({len(images)}장)")
            if st.button("🔄 다시 인식"):
                st.session_state.ocr_done = False
                st.rerun()

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

    # ── 인원 확인 및 수정 ──────────────────────────────────────
    st.subheader("2단계 — 인원 확인 및 수정")
    st.caption("OCR이 잘못 읽은 숫자가 있으면 직접 수정하세요. 0은 미입력으로 처리됩니다.")

    df_all = load_all()
    prev = {}
    if not df_all.empty:
        today_str = str(input_date)
        df_prev = df_all[df_all['date'].astype(str) != today_str]
        if not df_prev.empty:
            prev = df_prev.sort_values('date').groupby('room_num').last()['members'].to_dict()

    edited = {}
    cols = st.columns(3)

    for idx, room_num in enumerate(ROOM_NUMBERS):
        col = cols[idx % 3]
        with col:
            default = st.session_state.ocr_results.get(room_num, 0)
            prev_val = prev.get(room_num)
            help_msg = f"전일: {int(prev_val):,}명" if prev_val is not None else "이전 데이터 없음"

            val = st.number_input(
                ROOMS[room_num],
                min_value=0,
                value=int(default),
                step=1,
                help=help_msg,
                key=f"inp_{room_num}",
            )
            edited[room_num] = val

    # ── 저장 ──────────────────────────────────────────────────
    st.subheader("3단계 — 저장")
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
    ROOMS = load_rooms()
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 총원", f"{total:,}명")
    c2.metric("전일 대비 순증감", f"{net:+,}명")
    c3.metric("인원 증가 채팅방", f"{up}개")
    c4.metric("인원 감소 채팅방", f"{down}개")

    # ── 증감 차트 + 상품별 분석 ───────────────────────────────
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        fig_bar = change_bar_chart(df_today)
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
    display = display.sort_values('방 번호').reset_index(drop=True)

    # 증감 컬럼 포맷
    def fmt_change(val):
        if pd.isna(val):
            return '-'
        return f'+{int(val)}' if val > 0 else str(int(val))

    display['증감'] = display['증감'].apply(fmt_change)
    display['총원'] = display['총원'].apply(lambda x: f"{int(x):,}")
    display['전일'] = display['전일'].apply(lambda x: f"{int(x):,}" if not pd.isna(x) else '-')

    # 캠페인 정보 컬럼 추가
    display['진행 중인 강의'] = display['방 번호'].apply(
        lambda n: campaigns.get(int(n), {}).get('campaign_name', '-')
    )
    display['상품'] = display['방 번호'].apply(
        lambda n: campaigns.get(int(n), {}).get('product', '-')
    )

    st.dataframe(display, use_container_width=True, hide_index=True)

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

    # ── 현재 진행 중인 강의 목록 ───────────────────────────────
    if campaigns:
        st.subheader("현재 진행 중인 강의")
        camp_rows = []
        for room_num, info in sorted(campaigns.items()):
            camp_rows.append({
                '방 번호': room_num,
                '채팅방': ROOMS.get(room_num, f'채팅방 {room_num}'),
                '강의명': info.get('campaign_name', '-'),
                '상품': info.get('product', '-'),
                '기수': info.get('cohort', '-'),
                '시작일': info.get('start_date', '-'),
                '메모': info.get('memo', '-'),
            })
        st.dataframe(pd.DataFrame(camp_rows), use_container_width=True, hide_index=True)


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

    # 라인 차트 (목표 인원 점선 포함)
    fig_line = trend_line_chart(df_filtered, filter_rooms, targets=targets)
    if fig_line:
        st.plotly_chart(fig_line, use_container_width=True)

    # 전체 합계 막대 차트
    fig_total = total_trend_bar(df_filtered)
    if fig_total:
        st.plotly_chart(fig_total, use_container_width=True)

    # ── 주간 비교 차트 ──────────────────────────────────────────
    fig_week = weekly_comparison_chart(df_filtered)
    if fig_week:
        st.plotly_chart(fig_week, use_container_width=True)
    else:
        st.info("주간 비교는 7일 이상의 데이터가 있으면 자동으로 표시돼요.")


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

    # ── 전체 데이터 표시 ───────────────────────────────────────
    st.subheader("전체 데이터")
    show = df.sort_values(['date', 'room_num'], ascending=[False, True]).reset_index(drop=True)
    st.dataframe(show, use_container_width=True, hide_index=True)

    col_csv, col_excel, col_del = st.columns([2, 2, 1])

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
        campaigns = get_current_campaigns()
        excel_bytes = generate_excel(df, campaigns)
        st.download_button(
            "📊 Excel 보고서 다운로드",
            data=excel_bytes,
            file_name=f"채팅방_인원_보고서_{date.today()}.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            use_container_width=True,
        )

    with col_del:
        st.subheader("날짜 데이터 삭제")
        dates = sorted(df['date'].astype(str).unique().tolist(), reverse=True)
        del_date = st.selectbox("삭제할 날짜", options=dates, key="del_date_select")
        if st.button("🗑️ 삭제", type="secondary", use_container_width=True):
            delete_date(del_date)
            st.success(f"{del_date} 데이터 삭제 완료")
            st.rerun()


if __name__ == '__main__':
    main()
