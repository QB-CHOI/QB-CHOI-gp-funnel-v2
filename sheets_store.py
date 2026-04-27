import os
import gspread
import pandas as pd
import streamlit as st
from datetime import date

SPREADSHEET_NAME = "GP-Funnel 채팅방 인원 분석"
MEMBERS_WS     = "members"
CAMPAIGNS_WS   = "campaigns"

MEMBERS_COLS   = ['date', 'room_num', 'room_name', 'members', 'prev_members', 'change']
CAMPAIGNS_COLS = ['room_num', 'campaign_name', 'product', 'cohort',
                  'start_date', 'end_date', 'is_current', 'memo']

PRODUCT_OPTIONS = ['사주', '타로', '부동산', '빌딩', '기타']


# ── 인증 ──────────────────────────────────────────────────────────

@st.cache_resource
def _client():
    """Streamlit secrets 또는 로컬 credentials.json으로 인증."""
    try:
        creds = dict(st.secrets["gcp_service_account"])
        return gspread.service_account_from_dict(creds)
    except Exception:
        cred_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        if os.path.exists(cred_path):
            return gspread.service_account(filename=cred_path)
        raise RuntimeError(
            "Google Sheets 인증 정보가 없습니다.\n"
            "credentials.json 파일을 앱 폴더에 넣거나 "
            "Streamlit secrets에 gcp_service_account를 설정해주세요."
        )


def _ws(sheet_name: str, headers: list):
    """워크시트를 가져오거나 없으면 헤더와 함께 생성."""
    ss = _client().open(SPREADSHEET_NAME)
    try:
        return ss.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=sheet_name, rows=2000, cols=len(headers))
        ws.append_row(headers)
        return ws


# ── 인원 데이터 ───────────────────────────────────────────────────

@st.cache_data(ttl=180)
def load_all() -> pd.DataFrame:
    ws = _ws(MEMBERS_WS, MEMBERS_COLS)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=MEMBERS_COLS)
    df = pd.DataFrame(records)
    df['date']     = pd.to_datetime(df['date']).dt.date
    df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    for col in ['members', 'prev_members', 'change']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def get_latest_per_room() -> dict:
    df = load_all()
    if df.empty:
        return {}
    return df.sort_values('date').groupby('room_num').last()['members'].to_dict()


def save_daily(date_str: str, room_data: list):
    ws = _ws(MEMBERS_WS, MEMBERS_COLS)
    df = load_all()

    # 오늘 제외한 이전 데이터로 전일 값 계산
    df_prev = df[df['date'].astype(str) != date_str]
    prev = {}
    if not df_prev.empty:
        prev = df_prev.sort_values('date').groupby('room_num').last()['members'].to_dict()

    # 오늘 날짜 기존 행 삭제
    all_rows = ws.get_all_values()
    to_delete = [
        i + 2 for i, row in enumerate(all_rows[1:])
        if row and row[0] == date_str
    ]
    for idx in sorted(to_delete, reverse=True):
        ws.delete_rows(idx)

    # 새 행 추가
    new_rows = []
    for r in room_data:
        rn       = int(r['room_num'])
        members  = int(r['members'])
        prev_val = prev.get(rn)
        change   = int(members - prev_val) if prev_val is not None else ''
        new_rows.append([
            date_str, rn,
            r.get('room_name', f'채팅방 {rn}'),
            members,
            int(prev_val) if prev_val is not None else '',
            change,
        ])

    if new_rows:
        ws.append_rows(new_rows, value_input_option='RAW')

    load_all.clear()  # 캐시 초기화


def delete_date(date_str: str):
    ws = _ws(MEMBERS_WS, MEMBERS_COLS)
    all_rows = ws.get_all_values()
    to_delete = [
        i + 2 for i, row in enumerate(all_rows[1:])
        if row and row[0] == date_str
    ]
    for idx in sorted(to_delete, reverse=True):
        ws.delete_rows(idx)
    load_all.clear()


# ── 캠페인 데이터 ─────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_campaigns() -> pd.DataFrame:
    ws = _ws(CAMPAIGNS_WS, CAMPAIGNS_COLS)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=CAMPAIGNS_COLS)
    df = pd.DataFrame(records)
    df['room_num']   = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    df['is_current'] = df['is_current'].astype(str).str.upper().isin(['TRUE', '1', 'YES'])
    return df


def get_current_campaigns() -> dict:
    df = load_campaigns()
    if df.empty:
        return {}
    return {
        int(row['room_num']): row.to_dict()
        for _, row in df[df['is_current']].iterrows()
    }


def save_campaign(room_num: int, campaign_name: str, product: str,
                  cohort: str, start_date: str, memo: str):
    ws = _ws(CAMPAIGNS_WS, CAMPAIGNS_COLS)

    # 기존 현재 캠페인 종료 처리
    all_rows = ws.get_all_values()
    for i, row in enumerate(all_rows[1:], 2):
        if row and str(row[0]) == str(room_num) and row[6].upper() in ('TRUE', '1', 'YES'):
            ws.update_cell(i, 7, 'FALSE')
            ws.update_cell(i, 6, str(date.today()))

    # 신규 캠페인 추가
    ws.append_row(
        [room_num, campaign_name, product, cohort, start_date, '', 'TRUE', memo],
        value_input_option='RAW'
    )
    load_campaigns.clear()


def end_campaign(room_num: int):
    ws = _ws(CAMPAIGNS_WS, CAMPAIGNS_COLS)
    all_rows = ws.get_all_values()
    for i, row in enumerate(all_rows[1:], 2):
        if row and str(row[0]) == str(room_num) and row[6].upper() in ('TRUE', '1', 'YES'):
            ws.update_cell(i, 7, 'FALSE')
            ws.update_cell(i, 6, str(date.today()))
    load_campaigns.clear()


def get_history(room_num: int) -> pd.DataFrame:
    df = load_campaigns()
    if df.empty:
        return pd.DataFrame(columns=CAMPAIGNS_COLS)
    return (
        df[df['room_num'] == room_num]
        .sort_values('start_date', ascending=False)
        .reset_index(drop=True)
    )
