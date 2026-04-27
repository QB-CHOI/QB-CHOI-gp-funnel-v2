import streamlit as st
import pandas as pd
from datetime import date

from rooms_config import ROOMS, ROOM_NUMBERS
from sheets_store import (
    load_all, save_daily, delete_date,
    load_campaigns, get_current_campaigns,
    save_campaign, end_campaign, get_history,
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


# ── OCR 리더 캐싱 (앱 생명주기 동안 1회 로드) ─────────────────────

@st.cache_resource(show_spinner=False)
def load_ocr_reader():
    import easyocr
    return easyocr.Reader(['ko', 'en'], verbose=False)


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
    st.header("오늘의 인원 입력")

    input_date = st.date_input("📅 날짜", value=date.today())

    # ── OCR 업로드 ─────────────────────────────────────────────
    st.subheader("1단계 — 스크린샷 업로드")
    st.caption("카카오톡에서 '황금후추 돈버는'으로 검색한 채팅방 목록 화면을 캡처해서 올려주세요.")

    uploaded = st.file_uploader(
        "이미지 파일 선택 (PNG / JPG)",
        type=['png', 'jpg', 'jpeg'],
        key='screenshot_upload',
    )

    if uploaded:
        from PIL import Image
        img = Image.open(uploaded)

        col_img, col_status = st.columns([1, 1])
        with col_img:
            st.image(img, caption="업로드된 스크린샷", use_container_width=True)

        with col_status:
            if not st.session_state.ocr_done:
                with st.spinner("텍스트 인식 중...\n처음 실행 시 AI 모델 다운로드로 1~2분 소요될 수 있어요."):
                    try:
                        import numpy as np
                        reader = load_ocr_reader()
                        img_array = np.array(img.convert('RGB'))
                        raw = reader.readtext(img_array)

                        from ocr_parser import _group_by_row, _parse_rows
                        rows = _group_by_row(raw, y_threshold=25)
                        extracted = _parse_rows(rows)

                        st.session_state.ocr_results = {r['room_num']: r['members'] for r in extracted}
                        st.session_state.ocr_done = True

                        # 입력 칸에 OCR 결과를 직접 반영 (Streamlit key 우선 덮어쓰기)
                        for r in extracted:
                            st.session_state[f"inp_{r['room_num']}"] = r['members']

                        st.success(f"✅ {len(extracted)}개 채팅방 인식 완료")
                    except Exception as e:
                        st.error(f"OCR 오류: {e}")
                        st.info("아래 표에서 직접 숫자를 입력해도 됩니다.")
            else:
                st.success(f"✅ {len(st.session_state.ocr_results)}개 채팅방 인식 완료")
                if st.button("🔄 다시 인식"):
                    st.session_state.ocr_done = False
                    st.rerun()

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
            if room_data:
                with st.spinner("Google Sheets에 저장 중..."):
                    save_daily(str(input_date), room_data)
                st.success(f"✅ {input_date} 데이터 저장 완료 — {len(room_data)}개 채팅방")
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
    st.header("현황 대시보드")
    df = load_all()

    if df.empty:
        st.info("데이터가 없습니다. '오늘 입력' 탭에서 먼저 데이터를 입력해주세요.")
        return

    latest_date = df['date'].max()
    st.caption(f"기준: {latest_date}")

    df_today = df[df['date'] == latest_date].copy()
    campaigns = get_current_campaigns()

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
    st.header("인원 추이 그래프")
    df = load_all()

    if df.empty:
        st.info("데이터가 없습니다.")
        return

    all_rooms = sorted(df['room_num'].unique().tolist())

    selected = st.multiselect(
        "채팅방 선택 (비워두면 전체 표시)",
        options=all_rooms,
        format_func=lambda x: ROOMS.get(x, f"채팅방 {x}"),
    )

    filter_rooms = selected if selected else all_rooms

    # 라인 차트
    fig_line = trend_line_chart(df, filter_rooms)
    if fig_line:
        st.plotly_chart(fig_line, use_container_width=True)

    # 전체 합계 막대 차트
    fig_total = total_trend_bar(df)
    if fig_total:
        st.plotly_chart(fig_total, use_container_width=True)

    # ── 주간 비교 차트 ──────────────────────────────────────────
    fig_week = weekly_comparison_chart(df)
    if fig_week:
        st.plotly_chart(fig_week, use_container_width=True)
    else:
        st.info("주간 비교는 7일 이상의 데이터가 있으면 자동으로 표시돼요.")


# ── 탭 4: 채팅방 설정 ────────────────────────────────────────────

def tab_campaign():
    st.header("채팅방 설정")
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
            memo = st.text_area(
                "메모",
                placeholder="목표 인원, 특이사항 등 자유롭게 입력",
                height=100,
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
    st.header("데이터 관리")
    df = load_all()

    if df.empty:
        st.info("데이터가 없습니다.")
        return

    # 전체 데이터 표시
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
        del_date = st.selectbox("삭제할 날짜", options=dates)
        if st.button("🗑️ 삭제", type="secondary", use_container_width=True):
            delete_date(del_date)
            st.success(f"{del_date} 데이터 삭제 완료")
            st.rerun()


if __name__ == '__main__':
    main()
