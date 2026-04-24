import pandas as pd
import os
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CAMPAIGN_FILE = os.path.join(DATA_DIR, 'campaigns.csv')

COLUMNS = [
    'room_num', 'campaign_name', 'product',
    'cohort', 'start_date', 'end_date', 'is_current', 'memo'
]

PRODUCT_OPTIONS = ['사주', '타로', '부동산', '빌딩', '기타']


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_all() -> pd.DataFrame:
    _ensure_dir()
    if not os.path.exists(CAMPAIGN_FILE):
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(CAMPAIGN_FILE, dtype={'room_num': int})
    df['is_current'] = df['is_current'].astype(bool)
    return df


def get_current_campaigns() -> dict:
    """방 번호 → 현재 진행 중인 캠페인 정보 dict 반환."""
    df = load_all()
    if df.empty:
        return {}
    current = df[df['is_current'] == True]
    result = {}
    for _, row in current.iterrows():
        result[int(row['room_num'])] = row.to_dict()
    return result


def save_campaign(room_num: int, campaign_name: str, product: str,
                  cohort: str, start_date: str, memo: str):
    """
    신규 캠페인 저장.
    같은 방의 기존 현재 캠페인은 종료 처리(is_current=False, end_date=오늘).
    """
    _ensure_dir()
    df = load_all()

    # 기존 현재 캠페인 종료 처리
    mask = (df['room_num'] == room_num) & (df['is_current'] == True)
    df.loc[mask, 'is_current'] = False
    df.loc[mask, 'end_date'] = str(date.today())

    new_row = pd.DataFrame([{
        'room_num': room_num,
        'campaign_name': campaign_name,
        'product': product,
        'cohort': cohort,
        'start_date': start_date,
        'end_date': '',
        'is_current': True,
        'memo': memo,
    }])

    combined = pd.concat([df, new_row], ignore_index=True)
    combined.to_csv(CAMPAIGN_FILE, index=False)


def end_campaign(room_num: int):
    """해당 방의 현재 캠페인을 종료 처리."""
    df = load_all()
    mask = (df['room_num'] == room_num) & (df['is_current'] == True)
    df.loc[mask, 'is_current'] = False
    df.loc[mask, 'end_date'] = str(date.today())
    df.to_csv(CAMPAIGN_FILE, index=False)


def get_history(room_num: int) -> pd.DataFrame:
    """특정 방의 전체 캠페인 이력 반환 (최신순)."""
    df = load_all()
    room_df = df[df['room_num'] == room_num].copy()
    return room_df.sort_values('start_date', ascending=False).reset_index(drop=True)
