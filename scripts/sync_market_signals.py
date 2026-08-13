"""키워드 분석툴 → 강의 분석 사이트: 시장 신호 이관.

키워드 분석툴(로컬 Node 앱)이 매일 아침 수집해 두는 캐시를 읽어,
소재 기획에 바로 쓰이는 신호만 뽑아 private repo로 옮긴다.

왜 파일을 읽나:
  키워드툴은 127.0.0.1:8768 로컬 바인딩 + 세션 인증 + CORS 차단이라
  Streamlit Cloud에서 직접 호출할 수 없다. 또 유튜브 API 일일 쿼터가
  빠듯해(3주제 약 4,200u/10,000u) 추가 수집을 유발하면 안 된다.
  → 이미 저장된 캐시 파일만 읽는다. 서버가 꺼져 있어도 동작한다.

추출 신호 5종
  own_top    : 자사 유튜브 고성과 콘텐츠 제목 (후킹 문구의 원천)
  market_top : 시장 상위 영상 제목 (지금 먹히는 각도)
  age        : 키워드별 최고 반응 연령대 (타깃팅)
  ext_*      : 확장 주제(키워드툴에 직접 추가한 주제) 버전. 강의 상품군이 아니라
               주제명(건강운·재테크 등)이 product에 들어가므로, 상품군 기준으로
               읽는 기존 화면과 섞이지 않는다.

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

# 스테이징 폴더를 먼저 본다.
#   macOS TCC가 launchd 프로세스의 ~/Documents 접근을 막기 때문에,
#   권한이 있는 node(scripts/stage_keyword_cache.js)가 최신 캐시를 여기로
#   복사해 둔다. 원본을 직접 읽을 수 있는 환경(터미널)에서는 원본을 쓴다.
_STAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "inbox", "market")


def _pick_source():
    """(processed_dir, dataset_path) — 읽을 수 있는 쪽을 고른다."""
    orig_p = os.path.join(KEYWORD_TOOL_DIR, "data", "processed")
    orig_d = os.path.join(KEYWORD_TOOL_DIR, "data", "dataset.json")
    try:                       # 원본이 읽히면 원본 우선(항상 최신)
        if os.path.isdir(orig_p) and os.listdir(orig_p):
            return orig_p, orig_d
    except OSError:            # PermissionError 등 → 스테이징으로
        pass
    return _STAGE, os.path.join(_STAGE, "dataset.json")


PROCESSED, DATASET = _pick_source()

# 확장 주제 설정(키워드툴에서 사용자가 직접 추가·삭제하는 주제 목록).
# 지운 주제의 캐시 파일은 디스크에 남으므로, '지금 살아 있는 주제'는 이 파일로만 판별한다.
CUSTOM_CONFIG = [
    os.path.join(KEYWORD_TOOL_DIR, "data", "custom_topics.json"),
    os.path.join(_STAGE, "custom_topics.json"),
]

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


def _latest_by_slug(prefix):
    """{주제 슬러그: 최신 캐시 경로} — 확장 주제는 슬러그가 여러 개라 묶어서 고른다."""
    out = {}
    for p in glob.glob(os.path.join(PROCESSED, prefix + "*.json")):
        m = re.match(r"^(.*)_(\d{4}-\d{2}-\d{2})$", os.path.basename(p)[:-5])
        if not m:
            continue
        slug, day = m.group(1), m.group(2)
        if slug not in out or out[slug][0] < day:
            out[slug] = (day, p)
    return {s: v[1] for s, v in out.items()}


def _age_rows(d, product, sig, rank):
    """연령 신호 행 — '증가 신호'로만 쓴다.

    키워드툴은 연령대마다 네이버 데이터랩을 **따로** 호출하는데(server.mjs
    `ages: bracket.ages`), 데이터랩은 호출 단위로 최대값을 100으로 정규화한다.
    따라서 level·ratio는 연령대 간 비교가 불가능하고, hottestAge는 '가장 많이
    검색하는 층'이 아니라 '그 연령대 안에서 최근 상승폭이 가장 큰 연령'이다.
    → 상승폭을 함께 실어 보내고, 실제로 오른 것(+10% 이상)만 남긴다.
    """
    out = []
    for p in (d.get("profiles") or [])[:8]:
        age, delta = p.get("hottestAge"), int(p.get("hottestDelta") or 0)
        if not age or delta < 10:      # 하락·보합은 '뜨는 연령'이 아니다
            continue
        out.append({
            "product": product, "signal": sig, "rank_by": rank,
            "text": _clean_title(p.get("keyword"))[:40],
            "metric1": delta, "metric2": f"{age} +{delta}%",
        })
    return out


def _custom_topics():
    """살아 있는 확장 주제 이름 집합. 설정을 못 읽으면 None(=확장 주제 건너뜀)."""
    for path in CUSTOM_CONFIG:
        d = _load(path)
        if isinstance(d, list):
            names = {str(t.get("name")).strip() for t in d
                     if isinstance(t, dict) and t.get("name")}
            if names:
                return names
    return None


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


def build(notes=None) -> pd.DataFrame:
    """notes: 리스트를 주면 '건너뛴 주제' 같은 사람이 볼 메모를 담아 돌려준다."""
    rows = []
    notes = notes if notes is not None else []

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

    # ③ 연령대 — 관심이 빠르게 느는 연령(주 검색층 아님, _age_rows 주석 참조)
    for code, prod in TOPIC_MAP.items():
        d = _load(_latest(f"naver_age_{code}_*.json"))
        if d:
            rows.extend(_age_rows(d, prod, "age", "연령"))

    # ④ 확장 주제 — 키워드툴에 직접 추가한 주제(건강운·재테크 등)
    #
    # 상품군에 억지로 붙이지 않는다. '건강운'은 사주·타로 양쪽에 걸치고 '재테크'는
    # 부동산·빌딩·사주(재물운) 어디에도 붙일 수 있어, 한쪽에 귀속시키면 그 상품군의
    # 신호가 다른 의도로 모은 데이터에 오염된다. product에 주제명을 그대로 넣고
    # signal을 ext_* 로 구분해, 상품군 기준으로 읽는 기존 화면과 분리한다.
    live = _custom_topics()
    if live is None:
        notes.append("확장 주제 설정(custom_topics.json)을 읽지 못해 건너뜀")
    else:
        seen, skipped = [], []
        for kind, prefix, sig, rank in [
                ("video", "youtube_market_cu_", "ext_market_top", "조회"),
                ("age", "naver_age_cu_", "ext_age", "연령")]:
            for slug, path in sorted(_latest_by_slug(prefix).items()):
                d = _load(path)
                topic = str((d or {}).get("topic") or "").strip()
                if not topic:
                    continue
                if topic not in live:
                    # 사용자가 키워드툴에서 지운 주제 — 캐시 파일만 남아 있다.
                    # 조용히 버리면 '수집 실패'와 구분이 안 되므로 기록해 알린다.
                    if topic not in skipped:
                        skipped.append(topic)
                    continue
                if topic not in seen:
                    seen.append(topic)
                if kind == "video":
                    for v in (d.get("topScoredVideos") or d.get("topVideos") or [])[:8]:
                        t = _clean_title(v.get("title"))
                        if not t or NOISE.search(t):
                            continue
                        rows.append({
                            "product": topic, "signal": sig, "rank_by": rank,
                            "text": t[:80],
                            "metric1": int(v.get("viewCount") or 0),
                            "metric2": f"일 {int(v.get('viewsPerDay') or 0):,}회",
                        })
                else:
                    rows.extend(_age_rows(d, topic, sig, rank))
        if seen:
            notes.append(f"확장 주제 {len(seen)}개 반영 ({'·'.join(seen)})")
        if skipped:
            notes.append(f"확장 주제 {len(skipped)}개 무시 — 키워드툴에서 삭제된 주제"
                         f" ({'·'.join(skipped)})")

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

    notes = []
    df = build(notes)
    if df.empty:
        print("❌ 추출된 신호가 없습니다.")
        return 1

    print(f"수집일 {df['collected'].iloc[0]} · 신호 {len(df)}건")
    for n in notes:
        print(f"  · {n}")
    print()
    for sig, label in [("own_top", "자사 고성과 콘텐츠"), ("market_top", "시장 상위 영상"),
                       ("age", "연령대"),
                       ("ext_market_top", "확장 주제 · 시장 상위 영상"),
                       ("ext_age", "확장 주제 · 연령대")]:
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
