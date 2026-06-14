import io
import base64
import requests
import pandas as pd
import streamlit as st
from datetime import date

REPO           = "QB-CHOI/gp-funnel-v2"
MEMBERS_PATH   = "data/members.csv"
CAMPAIGNS_PATH = "data/campaigns.csv"

MEMBERS_COLS   = ['date', 'room_num', 'room_name', 'members', 'prev_members', 'change']
CAMPAIGNS_COLS = ['room_num', 'campaign_name', 'product', 'cohort',
                  'start_date', 'end_date', 'is_current', 'memo', 'target_count']
ROOMS_PATH       = "data/rooms.csv"
ROOMS_COLS       = ['room_num', 'room_name']
CONVERSIONS_PATH = "data/conversions.csv"
CONVERSIONS_COLS = ['date', 'room_num', 'applicants', 'confirmed', 'revenue', 'memo']

ADSPEND_PATH = "data/adspend.csv"
ADSPEND_COLS = ['date', 'room_num', 'channel', 'spend', 'impressions', 'clicks', 'memo']

PRODUCT_OPTIONS = ['사주', '타로', '부동산', '빌딩', '기타']
CHANNEL_OPTIONS = ['카카오모먼트', '네이버GFA', '메타(인스타)', '유튜브', '기타']

CONTENT_PATH = "data/content_logs.csv"
CONTENT_COLS = ['date', 'channel', 'content_type', 'title', 'url', 'memo']
CONTENT_TYPE_OPTIONS = ['영상(유튜브/릴스)', '카드뉴스', '블로그', '라이브', '광고소재', '기타']


def _token() -> str:
    return st.secrets["github_token"]


def _headers() -> dict:
    return {"Authorization": f"token {_token()}", "Accept": "application/vnd.github.v3+json"}


# ── GitHub 파일 읽기/쓰기 ────────────────────────────────────────

def _read_csv(path: str, columns: list) -> pd.DataFrame:
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    res = requests.get(url, headers=_headers())
    if res.status_code == 404:
        return pd.DataFrame(columns=columns)
    res.raise_for_status()
    content = base64.b64decode(res.json()["content"]).decode("utf-8")
    return pd.read_csv(io.StringIO(content))


def _write_csv(path: str, df: pd.DataFrame, message: str):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    res = requests.get(url, headers=_headers())
    sha = res.json().get("sha", "") if res.status_code == 200 else ""

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    content   = base64.b64encode(csv_bytes).decode("utf-8")

    payload = {"message": message, "content": content}
    if sha:
        payload["sha"] = sha

    res = requests.put(url, headers=_headers(), json=payload)
    res.raise_for_status()


# ── 인원 데이터 ───────────────────────────────────────────────────

@st.cache_data(ttl=180)
def load_all() -> pd.DataFrame:
    df = _read_csv(MEMBERS_PATH, MEMBERS_COLS)
    if df.empty:
        return df
    df["date"]     = pd.to_datetime(df["date"]).dt.date
    df["room_num"] = pd.to_numeric(df["room_num"], errors="coerce").astype("Int64")
    for col in ["members", "prev_members", "change"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_latest_per_room() -> dict:
    df = load_all()
    if df.empty:
        return {}
    return df.sort_values("date").groupby("room_num").last()["members"].to_dict()


def save_daily(date_str: str, room_data: list):
    df = load_all()
    df_prev = df[df["date"].astype(str) != date_str]
    prev = {}
    if not df_prev.empty:
        prev = df_prev.sort_values("date").groupby("room_num").last()["members"].to_dict()

    df = df[df["date"].astype(str) != date_str]

    new_rows = []
    for r in room_data:
        rn       = int(r["room_num"])
        members  = int(r["members"])
        prev_val = prev.get(rn)
        change   = int(members - prev_val) if prev_val is not None else None
        new_rows.append({
            "date": date_str, "room_num": rn,
            "room_name": r.get("room_name", f"채팅방 {rn}"),
            "members": members,
            "prev_members": int(prev_val) if prev_val is not None else None,
            "change": change,
        })

    combined = (pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                .sort_values(['date', 'room_num'])
                .reset_index(drop=True))
    _write_csv(MEMBERS_PATH, combined, f"{date_str} 인원 업데이트")
    load_all.clear()


def delete_date(date_str: str):
    df = load_all()
    df = df[df["date"].astype(str) != date_str]
    _write_csv(MEMBERS_PATH, df, f"{date_str} 데이터 삭제")
    load_all.clear()


# ── 캠페인 데이터 ─────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_campaigns() -> pd.DataFrame:
    df = _read_csv(CAMPAIGNS_PATH, CAMPAIGNS_COLS)
    if df.empty:
        return df
    df["room_num"]   = pd.to_numeric(df["room_num"], errors="coerce").astype("Int64")
    df["is_current"] = df["is_current"].astype(str).str.upper().isin(["TRUE", "1", "YES"])
    return df


def get_current_campaigns() -> dict:
    df = load_campaigns()
    if df.empty:
        return {}
    return {
        int(row["room_num"]): row.to_dict()
        for _, row in df[df["is_current"]].iterrows()
    }


def save_campaign(room_num: int, campaign_name: str, product: str,
                  cohort: str, start_date: str, memo: str, target_count: int = 0):
    df = load_campaigns()
    if not df.empty:
        mask = (df["room_num"] == room_num) & (df["is_current"] == True)
        df.loc[mask, "is_current"] = False
        df.loc[mask, "end_date"]   = str(date.today())

    new_row = pd.DataFrame([{
        "room_num": room_num, "campaign_name": campaign_name,
        "product": product, "cohort": cohort,
        "start_date": start_date, "end_date": "",
        "is_current": True, "memo": memo,
        "target_count": int(target_count),
    }])
    combined = pd.concat([df, new_row], ignore_index=True)
    _write_csv(CAMPAIGNS_PATH, combined, f"캠페인 등록: 채팅방 {room_num} — {campaign_name}")
    load_campaigns.clear()


def end_campaign(room_num: int):
    df = load_campaigns()
    if df.empty:
        return
    mask = (df["room_num"] == room_num) & (df["is_current"] == True)
    df.loc[mask, "is_current"] = False
    df.loc[mask, "end_date"]   = str(date.today())
    _write_csv(CAMPAIGNS_PATH, df, f"캠페인 종료: 채팅방 {room_num}")
    load_campaigns.clear()


# ── 채팅방 목록 ───────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_rooms() -> dict:
    df = _read_csv(ROOMS_PATH, ROOMS_COLS)
    if df.empty:
        return {}
    df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    return {int(row['room_num']): row['room_name'] for _, row in df.iterrows()}


def save_room(room_num: int, room_name: str):
    df = _read_csv(ROOMS_PATH, ROOMS_COLS)
    if not df.empty:
        df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
        df = df[df['room_num'] != room_num]
    new_row = pd.DataFrame([{'room_num': room_num, 'room_name': room_name}])
    combined = pd.concat([df, new_row], ignore_index=True).sort_values('room_num')
    _write_csv(ROOMS_PATH, combined, f"채팅방 {room_num} 추가/수정")
    load_rooms.clear()


def delete_room(room_num: int):
    df = _read_csv(ROOMS_PATH, ROOMS_COLS)
    if df.empty:
        return
    df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    df = df[df['room_num'] != room_num]
    _write_csv(ROOMS_PATH, df, f"채팅방 {room_num} 삭제")
    load_rooms.clear()


def get_history(room_num: int) -> pd.DataFrame:
    df = load_campaigns()
    if df.empty:
        return pd.DataFrame(columns=CAMPAIGNS_COLS)
    return (
        df[df["room_num"] == room_num]
        .sort_values("start_date", ascending=False)
        .reset_index(drop=True)
    )


# ── 전환 데이터 ───────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_conversions() -> pd.DataFrame:
    df = _read_csv(CONVERSIONS_PATH, CONVERSIONS_COLS)
    if df.empty:
        return df
    df['date']     = pd.to_datetime(df['date']).dt.date
    df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    for col in ['applicants', 'confirmed', 'revenue']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


def save_conversion(room_num: int, date_str: str, applicants: int,
                    confirmed: int, revenue: int, memo: str):
    df = load_conversions()
    if not df.empty:
        df = df[~((df['room_num'] == room_num) & (df['date'].astype(str) == date_str))]
    new_row = pd.DataFrame([{
        'date': date_str, 'room_num': room_num,
        'applicants': applicants, 'confirmed': confirmed,
        'revenue': revenue, 'memo': memo,
    }])
    combined = pd.concat([df, new_row], ignore_index=True).sort_values(['date', 'room_num'])
    _write_csv(CONVERSIONS_PATH, combined, f"전환 데이터 저장: 채팅방 {room_num} {date_str}")
    load_conversions.clear()


def get_latest_conversions() -> pd.DataFrame:
    """방별 가장 최근 전환 데이터 1행씩 반환."""
    df = load_conversions()
    if df.empty:
        return df
    return (
        df.sort_values('date')
          .groupby('room_num', as_index=False)
          .last()
    )


# ── 광고비 데이터 ─────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_adspend() -> pd.DataFrame:
    df = _read_csv(ADSPEND_PATH, ADSPEND_COLS)
    if df.empty:
        return df
    df['date']     = pd.to_datetime(df['date']).dt.date
    df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    for col in ['spend', 'impressions', 'clicks']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


def save_adspend(room_num: int, date_str: str, channel: str,
                 spend: int, impressions: int, clicks: int, memo: str):
    df = load_adspend()
    if not df.empty:
        df = df[~(
            (df['room_num'] == room_num) &
            (df['date'].astype(str) == date_str) &
            (df['channel'] == channel)
        )]
    new_row = pd.DataFrame([{
        'date': date_str, 'room_num': room_num, 'channel': channel,
        'spend': spend, 'impressions': impressions, 'clicks': clicks, 'memo': memo,
    }])
    combined = pd.concat([df, new_row], ignore_index=True).sort_values(['date', 'room_num'])
    _write_csv(ADSPEND_PATH, combined, f"광고비 저장: 채팅방 {room_num} {channel} {date_str}")
    load_adspend.clear()


# ── 콘텐츠 기록 ───────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_content() -> pd.DataFrame:
    df = _read_csv(CONTENT_PATH, CONTENT_COLS)
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df


def save_content(date_str: str, channel: str, content_type: str,
                 title: str, url: str, memo: str):
    df = load_content()
    new_row = pd.DataFrame([{
        'date': date_str, 'channel': channel, 'content_type': content_type,
        'title': title, 'url': url, 'memo': memo,
    }])
    combined = pd.concat([df, new_row], ignore_index=True).sort_values('date').reset_index(drop=True)
    _write_csv(CONTENT_PATH, combined, f"콘텐츠 기록: {channel} {date_str}")
    load_content.clear()


def delete_content_row(row_idx: int):
    """정렬 기준 인덱스로 콘텐츠 행 삭제."""
    df = load_content()
    if df.empty or row_idx < 0 or row_idx >= len(df):
        return
    df = df.drop(index=row_idx).reset_index(drop=True)
    _write_csv(CONTENT_PATH, df, f"콘텐츠 기록 삭제 (row {row_idx})")
    load_content.clear()
