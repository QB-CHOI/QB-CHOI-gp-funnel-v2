"""오카방 레지스트리 동기화 — "오카방의 모든 것.xlsx" → data/campaigns.csv.

원본은 hyems3@gmail.com 소유 구글 드라이브 파일로 거의 매일 갱신된다.
launchd는 구글 드라이브에 직접 접근할 수단이 없으므로(서비스 계정·rclone·
드라이브 데스크톱 전부 없음), **로컬에 내려온 사본**을 읽는 방식으로 붙인다.
찾는 위치는 SHEET_PATTERNS 참고 — 드라이브 데스크톱을 깔면 그 경로가,
아니면 inbox/에 떨궈둔 사본이 자동으로 잡힌다.

동기화 범위(의도적으로 좁게):
  · 방 번호가 **숫자**인 행만 = 오카방(웨비나 모집방). 아래쪽 수강생방
    블록은 '통합방'·'초급반'처럼 방 번호가 문자라 자연히 걸러진다.
  · **'삭제' 표시된 방은 새로 추가하지 않는다.** 이미 campaigns.csv에 있는
    방이면 is_current만 False로 내린다. 추적 이전에 사라진 방(18~22 등)까지
    끌어오면 캠페인 목록만 지저분해지고 인원 데이터도 없다.
  · end_date·memo·target_count는 **기존 값을 그대로 보존한다.** 시트의
    '다시보기 기한'은 재시청 만료일이지 캠페인 종료일이 아니다. 이걸
    end_date에 넣으면 차트의 캠페인 구간(_campaign_end_date)이 틀어진다.

실행:
    python3 scripts/sync_rooms_from_drive.py --dry-run   # 차이만 출력
    python3 scripts/sync_rooms_from_drive.py             # private repo에 반영
"""
import argparse
import os
import re
import sys
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

INBOX = os.path.join(ROOT, "inbox")
SHEET_NAME = "오카방&수강생방"

# 찾는 순서 = 신뢰도 순. 드라이브 데스크톱 경로가 있으면 항상 최신이다.
SHEET_PATTERNS = [
    os.path.expanduser("~/Library/CloudStorage/GoogleDrive-*/*/오카방의 모든 것*.xlsx"),
    os.path.expanduser("~/Library/CloudStorage/GoogleDrive-*/*/*/오카방의 모든 것*.xlsx"),
    os.path.join(INBOX, "오카방의 모든 것*.xlsx"),
    os.path.expanduser("~/Downloads/오카방의 모든 것*.xlsx"),
]

# 강의 코드 → 상품. 돈초부공·돈부공·돈초공이 모두 부동산이라 '부/초'를 함께 본다.
PRODUCT_CODES = [
    ("돈사공", "사주"),
    ("돈타공", "타로"),
    ("돈빌공", "빌딩"),
    ("돈초부공", "부동산"),
    ("돈부공", "부동산"),
    ("돈초공", "부동산"),
]

CAMPAIGNS_COLS = ["room_num", "campaign_name", "product", "cohort", "start_date",
                  "lecture_start_date", "end_date", "is_current", "memo", "target_count"]
# 시트가 권위값인 컬럼. 나머지(end_date·memo·target_count)는 앱 쪽이 권위값이라 보존.
SYNCED_COLS = ["campaign_name", "product", "cohort",
               "start_date", "lecture_start_date", "is_current"]


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def find_sheet(patterns=None):
    """마스터 시트 찾기 — auto_refresh의 NFD/NFC 대응 글롭을 그대로 쓴다."""
    from scripts.auto_refresh import find_order_files
    hits = find_order_files(patterns or SHEET_PATTERNS)
    return hits[-1] if hits else None


def _iso(v):
    """'25.07.21' 또는 엑셀 날짜 → 'YYYY-MM-DD'. 해석 불가면 빈 문자열."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return ""
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.date().isoformat()
    s = str(v).strip()
    m = re.match(r"^(\d{2})\.(\d{1,2})\.(\d{1,2})$", s)
    if m:
        yy, mm, dd = (int(x) for x in m.groups())
        return f"20{yy:02d}-{mm:02d}-{dd:02d}"
    try:
        return pd.to_datetime(s).date().isoformat()
    except Exception:
        return ""


def _product(name):
    for code, product in PRODUCT_CODES:
        if code in name:
            return product
    return ""


def _cohort(name):
    m = re.search(r"(\d+)\s*기", name)
    return f"{m.group(1)}기" if m else ""


def parse_rooms(path):
    """시트 상단 오카방 블록 → DataFrame(room_num 기준)."""
    raw = pd.read_excel(path, sheet_name=SHEET_NAME, header=0)
    cols = {str(c).strip(): c for c in raw.columns}
    need = ["방 번호", "모집 강의", "개설일", "강의 시작일"]
    missing = [c for c in need if c not in cols]
    if missing:
        raise ValueError(f"시트 컬럼 누락: {missing} — 원본 구조가 바뀐 듯합니다")

    rows = []
    for _, r in raw.iterrows():
        num = pd.to_numeric(r[cols["방 번호"]], errors="coerce")
        if pd.isna(num):          # 수강생방 블록('통합방'·'초급반' 등)
            continue
        name = str(r[cols["모집 강의"]] or "").strip()
        if not name or name == "nan":
            continue
        deleted = str(r[cols.get("구분", "구분")] if "구분" in cols else "").strip() == "삭제"
        rows.append({
            "room_num": int(num),
            "campaign_name": name,
            "product": _product(name),
            "cohort": _cohort(name),
            "start_date": _iso(r[cols["개설일"]]),
            "lecture_start_date": _iso(r[cols["강의 시작일"]]),
            "is_current": not deleted,
        })
    return pd.DataFrame(rows).drop_duplicates(subset="room_num", keep="last")


def merge(sheet_df, current_df):
    """시트 → campaigns.csv 병합. (결과 df, 변경내역 리스트) 반환."""
    changes = []
    out = current_df.copy()
    if out.empty:
        out = pd.DataFrame(columns=CAMPAIGNS_COLS)
    out["room_num"] = pd.to_numeric(out["room_num"], errors="coerce").astype("Int64")

    known = set(out["room_num"].dropna().astype(int))
    for _, s in sheet_df.iterrows():
        rn = int(s["room_num"])
        if rn in known:
            idx = out.index[out["room_num"] == rn][0]
            for c in SYNCED_COLS:
                old, new = out.at[idx, c], s[c]
                # 시트가 비어 있으면 기존 값을 지우지 않는다(부분 입력 대비).
                if c in ("start_date", "lecture_start_date") and not new:
                    continue
                if c == "is_current":
                    old = str(old).upper() in ("TRUE", "1", "YES")
                elif pd.isna(old):
                    old = ""
                if old != new:
                    out.at[idx, c] = new
                    changes.append(f"{rn}번 {c}: {old!r} → {new!r}")
        elif s["is_current"]:      # '삭제'된 미추적 방은 새로 끌어오지 않는다
            new_row = {c: "" for c in CAMPAIGNS_COLS}
            new_row.update(s.to_dict())
            new_row["target_count"] = 0
            out = pd.concat([out, pd.DataFrame([new_row])], ignore_index=True)
            changes.append(f"{rn}번 신규 추가: {s['campaign_name']} ({s['product']})")

    out = out.sort_values("room_num").reset_index(drop=True)
    return out[CAMPAIGNS_COLS], changes


def run(dry=False):
    """auto_refresh에서 호출하는 진입점. 변경이 있었으면 True."""
    path = find_sheet()
    if not path:
        log("  · 오카방 마스터 시트 없음 — 건너뜀 (드라이브 데스크톱 또는 inbox/)")
        return False
    log(f"  · 시트: {os.path.basename(path)}")

    from github_store import load_campaigns, _write_csv
    sheet_df = parse_rooms(path)
    merged, changes = merge(sheet_df, load_campaigns())

    if not changes:
        log(f"  · 오카방 {len(sheet_df)}개 — 변경 없음")
        return False
    for c in changes:
        log(f"    · {c}")
    if dry:
        log(f"  · [dry-run] campaigns.csv {len(changes)}건 반영 예정")
        return True
    _write_csv("data/campaigns.csv", merged,
               f"data: 오카방 레지스트리 자동 동기화 ({len(changes)}건)")
    load_campaigns.clear()
    log(f"  ✅ campaigns.csv 갱신 ({len(changes)}건, {len(merged)}행)")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="확인만, 쓰지 않음")
    a = ap.parse_args()
    raise SystemExit(0 if run(a.dry_run) is not None else 1)
