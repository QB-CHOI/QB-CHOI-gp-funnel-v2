"""키워드 분석툴 → 강의 분석 사이트: 시장 신호 이관.

키워드 분석툴(로컬 Node 앱)이 매일 아침 수집해 두는 캐시를 읽어,
소재 기획에 바로 쓰이는 신호만 뽑아 private repo로 옮긴다.

왜 파일을 읽나:
  키워드툴은 127.0.0.1:8768 로컬 바인딩 + 세션 인증 + CORS 차단이라
  Streamlit Cloud에서 직접 호출할 수 없다. 또 유튜브 API 일일 쿼터가
  빠듯해(3주제 약 4,200u/10,000u) 추가 수집을 유발하면 안 된다.
  → 이미 저장된 캐시 파일만 읽는다. 서버가 꺼져 있어도 동작한다.

추출 신호 3종
  own_top    : 자사 유튜브 고성과 콘텐츠 제목 (후킹 문구의 원천)
  market_top : 시장 상위 영상 제목 (지금 먹히는 각도)
  age        : 키워드별 최고 반응 연령대 (타깃팅)

실행:
    python3 scripts/sync_market_signals.py           # 미리보기
    python3 scripts/sync_market_signals.py --write   # private repo 반영
"""
import argparse
import glob
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KEYWORD_TOOL_DIR = os.path.expanduser(
    "~/Documents/📌 콘텐츠 자동화 제작 프로그램/키워드 분석툴")
PROCESSED = os.path.join(KEYWORD_TOOL_DIR, "data", "processed")
DATASET = os.path.join(KEYWORD_TOOL_DIR, "data", "dataset.json")

# 키워드툴 주제 코드 → 강의 상품군
TOPIC_MAP = {"saju": "사주", "tarot": "타로", "realestate": "부동산"}

# 수집 데이터에 섞여 드는 무관한 주제(사건사고·분양광고 등) 차단.
# 실제로 부동산 수집분에 '여성 살해', '강아지분양'이 상위 문구로 올라온 적 있음.
NOISE = re.compile(
    r"살해|사망|피의자|검거|성폭|마약|음주운전|화재|실종|"
    r"강아지분양|고양이분양|펫|로또|주식리딩|코인|도박")

# 제목 앞 대괄호 태그로 실제 주제를 판별 ("[타로] …"가 사주 수집분에 섞임)
TAG_TO_PRODUCT = {"타로": "타로", "사주": "사주", "부동산": "부동산", "애정": "타로"}


def _retag(title, default):
    """제목의 [태그]가 다른 주제를 가리키면 그쪽으로 재분류."""
    m = re.match(r"^\s*\[([^\]]+)\]", str(title))
    if m:
        for part in re.split(r"[|/·,]", m.group(1)):
            p = TAG_TO_PRODUCT.get(part.strip())
            if p:
                return p
    return default


def _latest(pattern):
    fs = sorted(glob.glob(os.path.join(PROCESSED, pattern)))
    return fs[-1] if fs else None


def _load(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _clean_title(s):
    """제목에서 이모지·과잉 기호를 덜어내 읽기 좋게."""
    s = re.sub(r"[\U00010000-\U0010ffff]", "", str(s))
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build() -> pd.DataFrame:
    rows = []

    # ① 자사 유튜브 고성과 콘텐츠 (dataset.json)
    ds = _load(DATASET)
    if ds and ds.get("keywords"):
        df = pd.DataFrame(ds["keywords"])
        if "contentViews" in df.columns:
            df["contentViews"] = pd.to_numeric(df["contentViews"], errors="coerce")
            df["contentCtr"] = pd.to_numeric(df.get("contentCtr"), errors="coerce")
            for cat, g in df.dropna(subset=["contentViews"]).groupby("category"):
                if cat not in TOPIC_MAP.values():
                    continue
                # 조회수 상위 + CTR 상위를 함께 (많이 본 것 / 잘 눌린 것)
                for key, label in [("contentViews", "조회"), ("contentCtr", "CTR")]:
                    if key not in g.columns:
                        continue
                    top = g.dropna(subset=[key]).sort_values(key, ascending=False).head(5)
                    for _, r in top.iterrows():
                        t = _clean_title(r.get("ownedContentTitle") or "")
                        if not t or NOISE.search(t):
                            continue
                        rows.append({
                            "product": cat, "signal": "own_top", "rank_by": label,
                            "text": t[:80],
                            "metric1": int(r["contentViews"]) if pd.notna(r["contentViews"]) else 0,
                            "metric2": (f"CTR {r['contentCtr']:.2f}%"
                                        if pd.notna(r.get("contentCtr")) else ""),
                        })

    # ② 시장 상위 영상
    for code, prod in TOPIC_MAP.items():
        d = _load(_latest(f"youtube_market_{code}_*.json"))
        if not d:
            continue
        vids = (d.get("topScoredVideos") or d.get("topVideos") or [])[:8]
        for v in vids:
            t = _clean_title(v.get("title"))
            if not t or NOISE.search(t):
                continue
            rows.append({
                # 사주 검색에 타로 영상이 섞여 들어오므로 제목 태그로 재분류
                "product": _retag(t, prod), "signal": "market_top", "rank_by": "조회",
                "text": t[:80],
                "metric1": int(v.get("viewCount") or 0),
                "metric2": f"일 {int(v.get('viewsPerDay') or 0):,}회",
            })
        # topPhrases(반복 n-gram)는 쓰지 않는다 — 실제로 뽑아 보니 "7월 31일 금요일",
        # "이재명 사주를", "도와 수백억"처럼 날짜·인명·문장 조각이 대부분이라
        # 후킹 아이디어로 쓸 수 없었다. 영상 '제목' 전체가 훨씬 나은 소재다.

    # ③ 연령대
    for code, prod in TOPIC_MAP.items():
        d = _load(_latest(f"naver_age_{code}_*.json"))
        if not d:
            continue
        for p in (d.get("profiles") or [])[:8]:
            age = p.get("hottestAge")
            if not age:
                continue
            rows.append({
                "product": prod, "signal": "age", "rank_by": "연령",
                "text": _clean_title(p.get("keyword"))[:40],
                "metric1": int(p.get("hottestDelta") or 0),
                "metric2": str(age),
            })

    if not rows:
        return pd.DataFrame(columns=["product", "signal", "rank_by", "text",
                                     "metric1", "metric2", "collected"])
    df = pd.DataFrame(rows).drop_duplicates(subset=["product", "signal", "text"])
    # 수집일 = 가장 최신 캐시 날짜
    latest = _latest("youtube_market_saju_*.json") or ""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(latest))
    df["collected"] = m.group(1) if m else ""
    return df.reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="private repo에 반영")
    a = ap.parse_args()

    if not os.path.isdir(PROCESSED):
        print(f"❌ 키워드 분석툴 데이터를 찾지 못했습니다: {PROCESSED}")
        return 1

    df = build()
    if df.empty:
        print("❌ 추출된 신호가 없습니다.")
        return 1

    print(f"수집일 {df['collected'].iloc[0]} · 신호 {len(df)}건\n")
    for sig, label in [("own_top", "자사 고성과 콘텐츠"), ("market_top", "시장 상위 영상"),
                       ("age", "연령대")]:
        g = df[df["signal"] == sig]
        print(f"[{label}] {len(g)}건")
        for _, r in g.head(4).iterrows():
            print(f"   {r['product']:<4} {r['text'][:46]:<48} {r['metric2']}")
        print()

    if a.write:
        from github_store import _write_csv
        _write_csv("data/market_signals.csv", df,
                   f"data: 시장 신호 이관 (키워드 분석툴 {df['collected'].iloc[0]})")
        print("✅ private repo 반영 완료")
    else:
        print("(미리보기 — 반영하려면 --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
