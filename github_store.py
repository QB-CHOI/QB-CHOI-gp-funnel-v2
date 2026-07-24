import io
import base64
import requests
import pandas as pd
import streamlit as st
from datetime import date

REPO           = "QB-CHOI/QB-CHOI-gp-funnel-v2"   # 코드 저장소 (public, 배포용)
# 민감 데이터(매출·전환·인원)는 코드와 분리해 별도 private 저장소에 저장.
# → 코드 저장소는 public 유지(Streamlit 배포 안정), 데이터는 외부 비공개.
DATA_REPO      = "QB-CHOI/gp-funnel-data"
MEMBERS_PATH   = "data/members.csv"
CAMPAIGNS_PATH = "data/campaigns.csv"

MEMBERS_COLS   = ['date', 'room_num', 'room_name', 'members', 'prev_members', 'change']
CAMPAIGNS_COLS = ['room_num', 'campaign_name', 'product', 'cohort',
                  'start_date', 'lecture_start_date', 'end_date',
                  'is_current', 'memo', 'target_count']
ROOMS_PATH          = "data/rooms.csv"
ROOMS_COLS          = ['room_num', 'room_name']
ARCHIVED_ROOMS_PATH = "data/rooms_archived.csv"
ARCHIVED_ROOMS_COLS = ['room_num', 'room_name', 'archived_date', 'actual_close_date', 'final_members', 'archive_reason']
CONVERSIONS_PATH = "data/conversions.csv"
CONVERSIONS_COLS = ['date', 'room_num', 'applicants', 'confirmed', 'revenue', 'memo']

# 기수별 유료 등록 (웨비나 → 유료 전환 퍼널용). 개인정보 없이 집계만 저장.
ENROLLMENTS_PATH = "data/enrollments.csv"
ENROLLMENTS_COLS = ['product', 'cohort', 'enrolled', 'revenue', 'memo']

ADSPEND_PATH = "data/adspend.csv"
ADSPEND_COLS = ['date', 'room_num', 'channel', 'spend', 'impressions', 'clicks', 'memo']

PRODUCT_OPTIONS = ['사주', '타로', '부동산', '빌딩', '기타']
CHANNEL_OPTIONS = ['카카오모먼트', '네이버GFA', '메타(인스타)', '유튜브', '기타']

CONTENT_PATH = "data/content_logs.csv"
CONTENT_COLS = ['date', 'channel', 'content_type', 'title', 'url', 'memo']
CONTENT_TYPE_OPTIONS = ['영상(유튜브/릴스)', '카드뉴스', '블로그', '라이브', '광고소재', '기타']

# 마케팅 채널 metrics (일자별 채널별 광고비·세션·구매·매출) — 외부 시트 이관
MARKETING_PATH = "data/marketing_metrics.csv"
MARKETING_COLS = ['date', 'channel', 'ad_spend', 'sessions', 'purchases', 'revenue']

# 월별 성과 (주문 명단 집계: 무료 신청·유료 구매·매출) — 전 기간
MONTHLY_PERF_PATH = "data/monthly_performance.csv"
MONTHLY_PERF_COLS = ['month', 'free_signups', 'paid_orders', 'revenue', 'conv_rate']

# 월별 광고비 입력 (전 기간 ROAS·CPA 산출용)
AD_MONTHLY_PATH = "data/ad_spend_monthly.csv"
AD_MONTHLY_COLS = ['month', 'channel', 'spend', 'memo']
AD_CHANNEL_OPTIONS = ['전체', '메타', '구글', '네이버', '카카오', '유튜브', '기타']

# 경쟁사 강의 가격/포지셔닝 (경쟁사 조사 시트 이관)
COMPETITOR_PATH = "data/competitor_courses.csv"
COMPETITOR_COLS = ['category', 'company', 'product', 'price_min', 'price_max', 'free']

# 강의 집계 보고서 이관 (아임웹 강의별 집계 · 세트합계 기준)
COHORT_REV_PATH = "data/cohort_revenue.csv"
COHORT_REV_COLS = ['product', 'cohort', 'students', 'revenue']
COURSE_SUM_PATH = "data/course_summary.csv"
# paid=유료 결제 건수(헤더), students=세트 수강생(멤버십 제외, 매출과 동일 기준)
COURSE_SUM_COLS = ['product', 'paid', 'free', 'revenue', 'students']

# 캠페인(라이브)별 광고비·매출 — 상품군별 광고 ROI 산출용 (통합시트 이관)
CAMPAIGN_AD_PATH = "data/campaign_adspend.csv"
CAMPAIGN_AD_COLS = ['live_date', 'product', 'cohort', 'ad_spend', 'live_revenue']

# 월별×강의별 집계 (주문 원본 기준) — 기간별 시계열 분석용
MONTHLY_COURSE_PATH = "data/monthly_by_course.csv"
MONTHLY_COURSE_COLS = ['month', 'product', 'paid_revenue', 'paid_orders', 'free_signups']

# 유료 단계 전환 (기초→심화→전문가→해석/창업) — 강의별 유료 퍼널 (사주/타로)
COHORT_STAGE_PATH = "data/cohort_stage.csv"
COHORT_STAGE_COLS = ['product', 'cohort', '기초', '심화', '전문가', '해석창업']
STAGE_ORDER = ['기초', '심화', '전문가', '해석창업']

# 고객 분석 (LTV·재구매·교차판매) — 주문 원본 집계, 개인정보 미보관
CUST_REPEAT_PATH = "data/cust_repeat_dist.csv"
CUST_LTV_PATH = "data/cust_ltv_dist.csv"
CUST_PRODUCT_PATH = "data/cust_product_repeat.csv"
CUST_CROSS_PATH = "data/cust_cross_sell.csv"
CUST_MONTHLY_PATH = "data/cust_monthly_new_repeat.csv"

# 지역별 모객 (돈사공 초급반 9~12기 배송지 기준)
REGION_PATH = "data/region_signups.csv"
REGION_COLS = ['region', 'signups', 'pct']
REGION_COHORT_PATH = "data/region_cohort.csv"
REGION_COHORT_COLS = ['cohort', 'start', 'end', 'days', 'total', 'capital', 'capital_pct']
REGION_CITY_PATH = "data/region_city.csv"
REGION_CITY_COLS = ['city', 'count']
# 수도권 3개 시도 (광고 집중 판단용)
CAPITAL_REGIONS = ['서울', '경기', '인천']


def _token() -> str:
    token = st.secrets.get("github_token", "")
    if not token:
        st.error(
            "❌ **GitHub 토큰 미설정**\n\n"
            "Streamlit Cloud → 앱 우하단 ⋮ → Settings → Secrets 에서\n"
            "`github_token = \"ghp_...\"` 을 추가하세요.",
            icon="🔑",
        )
        st.stop()
    return token


def _headers() -> dict:
    return {"Authorization": f"token {_token()}", "Accept": "application/vnd.github.v3+json"}


# ── GitHub 파일 읽기/쓰기 ────────────────────────────────────────

def _read_csv(path: str, columns: list) -> pd.DataFrame:
    url = f"https://api.github.com/repos/{DATA_REPO}/contents/{path}"
    try:
        res = requests.get(url, headers=_headers(), timeout=20)
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ GitHub 연결 오류: {e}", icon="🔌")
        return pd.DataFrame(columns=columns)

    if res.status_code == 404:
        return pd.DataFrame(columns=columns)

    if res.status_code == 401:
        st.error(
            "❌ GitHub 토큰 인증 실패 (401). 토큰이 만료되었을 수 있습니다.\n\n"
            "**해결 방법:** Streamlit Cloud → Settings → Secrets에서 `github_token` 값을 새 토큰으로 교체하세요.",
            icon="🔑",
        )
        return pd.DataFrame(columns=columns)

    if res.status_code == 403:
        st.error(
            "❌ GitHub API 권한 오류 (403). 토큰 권한 또는 API 호출 한도를 확인하세요.",
            icon="🚫",
        )
        return pd.DataFrame(columns=columns)

    if not res.ok:
        st.warning(f"⚠️ GitHub API 오류 [{res.status_code}] — 경로: {path}", icon="⚠️")
        return pd.DataFrame(columns=columns)

    content = base64.b64decode(res.json()["content"]).decode("utf-8")
    return pd.read_csv(io.StringIO(content))


def _write_csv(path: str, df: pd.DataFrame, message: str, _retries: int = 3):
    """CSV를 GitHub에 저장. SHA 충돌(409) 시 최대 3회 자동 재시도."""
    import time
    url       = f"https://api.github.com/repos/{DATA_REPO}/contents/{path}"
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    content   = base64.b64encode(csv_bytes).decode("utf-8")

    for attempt in range(_retries):
        # 매 시도마다 최신 SHA를 가져와야 409 충돌을 피할 수 있음
        res_get = requests.get(url, headers=_headers(), timeout=20)
        sha = res_get.json().get("sha", "") if res_get.status_code == 200 else ""

        payload = {"message": message, "content": content}
        if sha:
            payload["sha"] = sha

        res = requests.put(url, headers=_headers(), json=payload, timeout=30)
        if res.ok:
            return

        if res.status_code == 409 and attempt < _retries - 1:
            time.sleep(1.5 * (attempt + 1))  # 점진적 대기 후 재시도
            continue

        try:
            err_msg = res.json().get("message", res.text[:200])
        except Exception:
            err_msg = res.text[:200]
        raise RuntimeError(f"GitHub 저장 실패 [{res.status_code}]: {err_msg}")


# ── 인원 데이터 ───────────────────────────────────────────────────

@st.cache_data(ttl=120)
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

@st.cache_data(ttl=3600)
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
                  cohort: str, start_date: str, memo: str,
                  target_count: int = 0, lecture_start_date: str = ""):
    df = load_campaigns()
    if not df.empty:
        mask = (df["room_num"] == room_num) & (df["is_current"] == True)
        df.loc[mask, "is_current"] = False
        df.loc[mask, "end_date"]   = str(date.today())

    new_row = pd.DataFrame([{
        "room_num": room_num, "campaign_name": campaign_name,
        "product": product, "cohort": cohort,
        "start_date": start_date, "lecture_start_date": lecture_start_date,
        "end_date": "", "is_current": True,
        "memo": memo, "target_count": int(target_count),
    }])
    combined = pd.concat([df, new_row], ignore_index=True)
    _write_csv(CAMPAIGNS_PATH, combined, f"캠페인 등록: 채팅방 {room_num} — {campaign_name}")
    load_campaigns.clear()


def update_lecture_start_date(room_num: int, lecture_start_date: str):
    df = load_campaigns()
    if df.empty:
        return
    mask = (df["room_num"] == room_num) & (df["is_current"] == True)
    df.loc[mask, "lecture_start_date"] = lecture_start_date
    _write_csv(CAMPAIGNS_PATH, df, f"개강일 업데이트: 채팅방 {room_num} → {lecture_start_date}")
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


# ── 기수별 유료 등록 (전환 퍼널) ─────────────────────────────────

@st.cache_data(ttl=3600)
def load_enrollments() -> pd.DataFrame:
    """상품·기수별 유료 등록 집계 반환 (개인정보 없음)."""
    df = _read_csv(ENROLLMENTS_PATH, ENROLLMENTS_COLS)
    if df.empty:
        return df
    df['enrolled'] = pd.to_numeric(df['enrolled'], errors='coerce').fillna(0).astype(int)
    df['revenue']  = pd.to_numeric(df['revenue'], errors='coerce').fillna(0).astype(int)
    return df


def save_enrollment(product: str, cohort: str, enrolled: int,
                    revenue: int = 0, memo: str = ""):
    """상품·기수 키로 유료 등록 수·매출 저장(있으면 갱신)."""
    df = _read_csv(ENROLLMENTS_PATH, ENROLLMENTS_COLS)
    if not df.empty:
        mask = (df['product'].astype(str) == str(product)) & \
               (df['cohort'].astype(str) == str(cohort))
        df = df[~mask]
    new_row = pd.DataFrame([{
        'product': product, 'cohort': cohort,
        'enrolled': int(enrolled), 'revenue': int(revenue), 'memo': memo,
    }])
    combined = pd.concat([df, new_row], ignore_index=True)
    _write_csv(ENROLLMENTS_PATH, combined, f"유료 등록 저장: {product} {cohort} — {enrolled}명")
    load_enrollments.clear()


def delete_enrollment(product: str, cohort: str):
    df = _read_csv(ENROLLMENTS_PATH, ENROLLMENTS_COLS)
    if df.empty:
        return
    mask = (df['product'].astype(str) == str(product)) & \
           (df['cohort'].astype(str) == str(cohort))
    df = df[~mask]
    _write_csv(ENROLLMENTS_PATH, df, f"유료 등록 삭제: {product} {cohort}")
    load_enrollments.clear()


# ── 채팅방 목록 ───────────────────────────────────────────────────

@st.cache_data(ttl=3600)
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


def save_rooms_batch(new_rooms: dict):
    """신규 채팅방 여러 개를 API 1회 호출로 일괄 등록."""
    df = _read_csv(ROOMS_PATH, ROOMS_COLS)
    if not df.empty:
        df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
        df = df[~df['room_num'].isin(new_rooms.keys())]
    new_rows = pd.DataFrame([{'room_num': rn, 'room_name': name}
                              for rn, name in new_rooms.items()])
    combined = pd.concat([df, new_rows], ignore_index=True).sort_values('room_num')
    room_list = ", ".join(f"채팅방{rn}" for rn in sorted(new_rooms.keys()))
    _write_csv(ROOMS_PATH, combined, f"신규 채팅방 자동 등록: {room_list}")
    load_rooms.clear()


def delete_room(room_num: int):
    df = _read_csv(ROOMS_PATH, ROOMS_COLS)
    if df.empty:
        return
    df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    df = df[df['room_num'] != room_num]
    _write_csv(ROOMS_PATH, df, f"채팅방 {room_num} 삭제")
    load_rooms.clear()


@st.cache_data(ttl=3600)
def load_archived_rooms() -> pd.DataFrame:
    """운영 종료된 채팅방 목록 반환."""
    df = _read_csv(ARCHIVED_ROOMS_PATH, ARCHIVED_ROOMS_COLS)
    if df.empty:
        return df
    df['room_num']      = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    df['final_members'] = pd.to_numeric(df['final_members'], errors='coerce').fillna(0).astype(int)
    return df


def archive_room(room_num: int, room_name: str, final_members: int,
                 reason: str = "운영 종료", actual_close_date: str = ""):
    """채팅방을 운영 종료 처리: rooms.csv에서 제거 → rooms_archived.csv에 기록."""
    # 1) 보관 파일에 추가
    df_arch = _read_csv(ARCHIVED_ROOMS_PATH, ARCHIVED_ROOMS_COLS)
    if not df_arch.empty:
        df_arch['room_num'] = pd.to_numeric(df_arch['room_num'], errors='coerce').astype('Int64')
        df_arch = df_arch[df_arch['room_num'] != room_num]
    new_row = pd.DataFrame([{
        'room_num': room_num, 'room_name': room_name,
        'archived_date': str(date.today()),
        'actual_close_date': actual_close_date or "",
        'final_members': int(final_members),
        'archive_reason': reason,
    }])
    combined = pd.concat([df_arch, new_row], ignore_index=True).sort_values('room_num')
    _write_csv(ARCHIVED_ROOMS_PATH, combined, f"채팅방 {room_num} 운영 종료 보관")

    # 2) 활성 목록에서 제거
    df_rooms = _read_csv(ROOMS_PATH, ROOMS_COLS)
    if not df_rooms.empty:
        df_rooms['room_num'] = pd.to_numeric(df_rooms['room_num'], errors='coerce').astype('Int64')
        df_rooms = df_rooms[df_rooms['room_num'] != room_num]
        _write_csv(ROOMS_PATH, df_rooms, f"채팅방 {room_num} 활성 목록 제거")

    load_rooms.clear()
    load_archived_rooms.clear()


def update_actual_close_date(room_num: int, actual_close_date: str):
    """운영 종료된 채팅방의 실제 종료일을 수정."""
    df = _read_csv(ARCHIVED_ROOMS_PATH, ARCHIVED_ROOMS_COLS)
    if df.empty:
        return
    df['room_num'] = pd.to_numeric(df['room_num'], errors='coerce').astype('Int64')
    df.loc[df['room_num'] == room_num, 'actual_close_date'] = actual_close_date
    _write_csv(ARCHIVED_ROOMS_PATH, df, f"채팅방 {room_num} 실제 종료일 수정 → {actual_close_date}")
    load_archived_rooms.clear()


def restore_room(room_num: int):
    """종료된 채팅방을 활성 목록으로 복원."""
    df_arch = _read_csv(ARCHIVED_ROOMS_PATH, ARCHIVED_ROOMS_COLS)
    if df_arch.empty:
        return
    df_arch['room_num'] = pd.to_numeric(df_arch['room_num'], errors='coerce').astype('Int64')
    row = df_arch[df_arch['room_num'] == room_num]
    if row.empty:
        return
    room_name = str(row.iloc[0]['room_name'])
    save_room(int(room_num), room_name)
    df_arch = df_arch[df_arch['room_num'] != room_num]
    _write_csv(ARCHIVED_ROOMS_PATH, df_arch, f"채팅방 {room_num} 복원")
    load_rooms.clear()
    load_archived_rooms.clear()


def load_all_room_names() -> dict:
    """활성 + 종료 채팅방 이름 통합 반환 (이력 조회·차트 레이블용)."""
    names = load_rooms().copy()
    df_arch = load_archived_rooms()
    if not df_arch.empty:
        for _, r in df_arch.iterrows():
            rn = int(r['room_num'])
            if rn not in names:
                names[rn] = f"{r['room_name']} (종료)"
    return names


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

@st.cache_data(ttl=600)
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


def delete_conversion_row(row_idx: int):
    """최신순 정렬 기준 인덱스로 전환 데이터 행 삭제."""
    df = load_conversions()
    sorted_df = df.sort_values('date', ascending=False).reset_index()
    if row_idx < 0 or row_idx >= len(sorted_df):
        return
    real_idx = int(sorted_df.iloc[row_idx]['index'])
    df = df.drop(index=real_idx).reset_index(drop=True)
    _write_csv(CONVERSIONS_PATH, df, f"전환 데이터 삭제 (row {row_idx})")
    load_conversions.clear()
    get_latest_conversions.clear()


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

@st.cache_data(ttl=600)
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


def delete_adspend_row(row_idx: int):
    """최신순 정렬 기준 인덱스로 광고비 데이터 행 삭제."""
    df = load_adspend()
    sorted_df = df.sort_values('date', ascending=False).reset_index()
    if row_idx < 0 or row_idx >= len(sorted_df):
        return
    real_idx = int(sorted_df.iloc[row_idx]['index'])
    df = df.drop(index=real_idx).reset_index(drop=True)
    _write_csv(ADSPEND_PATH, df, f"광고비 데이터 삭제 (row {row_idx})")
    load_adspend.clear()


# ── 콘텐츠 기록 ───────────────────────────────────────────────────

@st.cache_data(ttl=600)
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


# ── 마케팅 채널 metrics ───────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_marketing() -> pd.DataFrame:
    """일자별 채널별 광고비·세션·구매·매출 (외부 마케팅 시트 이관분)."""
    df = _read_csv(MARKETING_PATH, MARKETING_COLS)
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
    for c in ['ad_spend', 'sessions', 'purchases', 'revenue']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    return df.dropna(subset=['date'])


@st.cache_data(ttl=3600)
def load_monthly_performance() -> pd.DataFrame:
    """월별 무료 신청·유료 구매·매출·전환율 (주문 명단 집계, 전 기간)."""
    df = _read_csv(MONTHLY_PERF_PATH, MONTHLY_PERF_COLS)
    if df.empty:
        return df
    for c in ['free_signups', 'paid_orders', 'revenue']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    df['conv_rate'] = pd.to_numeric(df['conv_rate'], errors='coerce').fillna(0.0)
    return df.sort_values('month').reset_index(drop=True)


@st.cache_data(ttl=600)
def load_ad_spend_monthly() -> pd.DataFrame:
    """월별 광고비 입력값."""
    df = _read_csv(AD_MONTHLY_PATH, AD_MONTHLY_COLS)
    if df.empty:
        return df
    df['spend'] = pd.to_numeric(df['spend'], errors='coerce').fillna(0).astype(int)
    return df


def save_ad_spend_monthly(month: str, channel: str, spend: int, memo: str = ""):
    """월별 광고비 저장(같은 월+채널이면 갱신)."""
    df = _read_csv(AD_MONTHLY_PATH, AD_MONTHLY_COLS)
    if not df.empty:
        mask = (df['month'].astype(str) == str(month)) & (df['channel'].astype(str) == str(channel))
        df = df[~mask]
    new_row = pd.DataFrame([{'month': month, 'channel': channel, 'spend': int(spend), 'memo': memo}])
    combined = pd.concat([df, new_row], ignore_index=True).sort_values(['month', 'channel'])
    _write_csv(AD_MONTHLY_PATH, combined, f"월별 광고비 저장: {month} {channel} {spend:,}원")
    load_ad_spend_monthly.clear()


@st.cache_data(ttl=3600)
def load_competitor_courses() -> pd.DataFrame:
    """경쟁사 강의 가격/포지셔닝 (황금후추 자사 대표가 포함)."""
    df = _read_csv(COMPETITOR_PATH, COMPETITOR_COLS)
    if df.empty:
        return df
    for c in ['price_min', 'price_max']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    df['free'] = pd.to_numeric(df['free'], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_cohort_revenue() -> pd.DataFrame:
    """강의별 기수별 매출/수강생 (세트합계·멤버십 제외)."""
    df = _read_csv(COHORT_REV_PATH, COHORT_REV_COLS)
    if df.empty:
        return df
    for c in ['students', 'revenue']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_course_summary() -> pd.DataFrame:
    """상품군 top-line (유료 건수·무료 신청·총매출·세트 수강생).

    - paid: 유료 결제 건수(리포트 헤더, 거래 기준)
    - students: 세트 수강생(기초+심화+패키지·멤버십 제외) = 매출과 동일 기준.
      객단가·전환율은 매출과 정합을 위해 students를 분모로 사용한다.
    """
    df = _read_csv(COURSE_SUM_PATH, COURSE_SUM_COLS)
    if df.empty:
        return df
    for c in ['paid', 'free', 'revenue', 'students']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    # students 누락(구버전 데이터) 시 paid로 대체
    if 'students' not in df.columns or (df['students'] == 0).all():
        df['students'] = df['paid']
    return df


@st.cache_data(ttl=3600)
def load_campaign_adspend() -> pd.DataFrame:
    """캠페인(라이브)별 광고비·매출 (상품군별 광고 ROI 산출용)."""
    df = _read_csv(CAMPAIGN_AD_PATH, CAMPAIGN_AD_COLS)
    if df.empty:
        return df
    for c in ['ad_spend', 'live_revenue']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_monthly_by_course() -> pd.DataFrame:
    """월별×강의별 집계 (주문 원본 기준: 매출·유료건·무료신청)."""
    df = _read_csv(MONTHLY_COURSE_PATH, MONTHLY_COURSE_COLS)
    if df.empty:
        return df
    for c in ['paid_revenue', 'paid_orders', 'free_signups']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_cohort_stage() -> pd.DataFrame:
    """유료 단계 전환 인원 (기초→심화→전문가→해석/창업, 사주·타로)."""
    df = _read_csv(COHORT_STAGE_PATH, COHORT_STAGE_COLS)
    if df.empty:
        return df
    for c in STAGE_ORDER:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_cust_repeat_dist() -> pd.DataFrame:
    """고객 재구매 횟수 분포 (1회/2회/3~4회/5회+)."""
    df = _read_csv(CUST_REPEAT_PATH, ['bucket', 'customers'])
    if not df.empty:
        df['customers'] = pd.to_numeric(df['customers'], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_cust_ltv_dist() -> pd.DataFrame:
    """고객 누적결제(LTV) 구간 분포."""
    df = _read_csv(CUST_LTV_PATH, ['bucket', 'customers'])
    if not df.empty:
        df['customers'] = pd.to_numeric(df['customers'], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_cust_product_repeat() -> pd.DataFrame:
    """상품군별 구매자·재구매율·평균 LTV."""
    df = _read_csv(CUST_PRODUCT_PATH, ['product', 'buyers', 'repeat_buyers', 'repeat_rate', 'avg_ltv'])
    if df.empty:
        return df
    for c in ['buyers', 'repeat_buyers', 'avg_ltv']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    df['repeat_rate'] = pd.to_numeric(df['repeat_rate'], errors='coerce').fillna(0.0)
    return df


@st.cache_data(ttl=3600)
def load_cust_cross_sell() -> pd.DataFrame:
    """교차판매 매트릭스 (from 구매자 중 to 구매 비율)."""
    df = _read_csv(CUST_CROSS_PATH, ['from', 'to', 'rate', 'count'])
    if df.empty:
        return df
    df['rate'] = pd.to_numeric(df['rate'], errors='coerce').fillna(0.0)
    df['count'] = pd.to_numeric(df['count'], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_cust_monthly_new_repeat() -> pd.DataFrame:
    """월별 신규/재구매 고객·매출."""
    df = _read_csv(CUST_MONTHLY_PATH, ['month', 'new_customers', 'repeat_orders', 'new_revenue', 'repeat_revenue'])
    if df.empty:
        return df
    for c in ['new_customers', 'repeat_orders', 'new_revenue', 'repeat_revenue']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    return df


@st.cache_data(ttl=3600)
def load_region_signups() -> pd.DataFrame:
    """지역별 신청 분포 (돈사공 초급반 9~12기 배송지)."""
    df = _read_csv(REGION_PATH, REGION_COLS)
    if df.empty:
        return df
    df['signups'] = pd.to_numeric(df['signups'], errors='coerce').fillna(0).astype(int)
    df['pct'] = pd.to_numeric(df['pct'], errors='coerce').fillna(0.0)
    return df


@st.cache_data(ttl=3600)
def load_region_cohort() -> pd.DataFrame:
    """기수별 수도권 비중·모집 기간."""
    df = _read_csv(REGION_COHORT_PATH, REGION_COHORT_COLS)
    if df.empty:
        return df
    for c in ['days', 'total', 'capital']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    df['capital_pct'] = pd.to_numeric(df['capital_pct'], errors='coerce').fillna(0.0)
    return df


@st.cache_data(ttl=3600)
def load_region_city() -> pd.DataFrame:
    """도시/구 단위 상위 신청 분포."""
    df = _read_csv(REGION_CITY_PATH, REGION_CITY_COLS)
    if df.empty:
        return df
    df['count'] = pd.to_numeric(df['count'], errors='coerce').fillna(0).astype(int)
    return df


# ── 날짜별 메모 ───────────────────────────────────────────────────

DATE_NOTES_PATH = "data/date_notes.csv"
DATE_NOTES_COLS = ['date', 'memo']


@st.cache_data(ttl=300)  # 당일 메모 수정 가능성 고려
def load_date_notes() -> pd.DataFrame:
    df = _read_csv(DATE_NOTES_PATH, DATE_NOTES_COLS)
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df


def send_slack_alert(webhook_url: str, message: str):
    """Slack Incoming Webhook 알림 전송. 실패해도 조용히 무시."""
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"text": message}, timeout=5)
    except Exception:
        pass


def save_date_note(date_str: str, memo: str):
    """날짜별 메모 저장(upsert). 빈 문자열이면 해당 날짜 메모 삭제."""
    df = load_date_notes()
    if not df.empty:
        df = df[df['date'].astype(str) != date_str]
    if memo.strip():
        new_row = pd.DataFrame([{'date': date_str, 'memo': memo.strip()}])
        combined = pd.concat([df, new_row], ignore_index=True).sort_values('date').reset_index(drop=True)
    else:
        combined = df
    _write_csv(DATE_NOTES_PATH, combined, f"날짜 메모: {date_str}")
    load_date_notes.clear()
