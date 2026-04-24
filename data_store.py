import pandas as pd
import os
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DATA_FILE = os.path.join(DATA_DIR, 'members.csv')

COLUMNS = ['date', 'room_num', 'room_name', 'members', 'prev_members', 'change']


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_all() -> pd.DataFrame:
    _ensure_dir()
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(DATA_FILE, dtype={'room_num': int})
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df


def get_latest_per_room() -> dict:
    df = load_all()
    if df.empty:
        return {}
    latest = df.sort_values('date').groupby('room_num').last()
    return latest['members'].to_dict()


def save_daily(date_str: str, room_data: list) -> pd.DataFrame:
    """
    room_data: list of {'room_num': int, 'room_name': str, 'members': int}
    같은 날짜 데이터가 있으면 덮어씀.
    """
    _ensure_dir()
    df = load_all()
    prev = get_latest_per_room()

    new_rows = []
    for r in room_data:
        room_num = int(r['room_num'])
        members = int(r['members'])

        # 오늘 날짜 데이터가 이미 있으면 prev에서 제외 (이전 날짜 기준으로 계산)
        df_prev = df[df['date'].astype(str) != date_str]
        prev_today = df_prev.sort_values('date').groupby('room_num').last()
        prev_val = prev_today['members'].to_dict().get(room_num)

        change = (members - int(prev_val)) if prev_val is not None else None

        new_rows.append({
            'date': date_str,
            'room_num': room_num,
            'room_name': r.get('room_name', f'채팅방 {room_num}'),
            'members': members,
            'prev_members': int(prev_val) if prev_val is not None else None,
            'change': int(change) if change is not None else None,
        })

    # 해당 날짜 기존 데이터 제거 후 신규 삽입
    df = df[df['date'].astype(str) != date_str]
    new_df = pd.DataFrame(new_rows)
    combined = pd.concat([df, new_df], ignore_index=True)
    combined.to_csv(DATA_FILE, index=False)
    return new_df


def delete_date(date_str: str):
    df = load_all()
    df = df[df['date'].astype(str) != date_str]
    df.to_csv(DATA_FILE, index=False)
