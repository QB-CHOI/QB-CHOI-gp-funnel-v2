"""오행(五行) 시기별 모객·전환 집계 생성.

명리학에서 한 달의 성격은 **월주(천간+지지)**로 드러나고, 각 글자는 오행에
속한다(갑·을=목, 병·정=화 … / 인·묘=목, 사·오=화 …). 이 스크립트는 주문
원본을 **절기 기준 명리월**로 다시 묶어 오행별 모객·전환을 집계한다.

핵심: 양력 1일이 아니라 **절입일**에 월이 바뀐다(예: 2026-06-03은 아직
癸巳月). 달력월로 묶으면 매월 앞 5일 정도가 다른 오행에 잘못 들어간다.

실행:
    python3 scripts/build_ohaeng_period.py            # 미리보기
    python3 scripts/build_ohaeng_period.py --write    # private repo 반영

출력: data/ohaeng_period.csv
    saju_year·saju_month·year_pillar·month_pillar·stem·branch·
    stem_element·branch_element·free_signups·paid_orders·revenue
"""
import argparse
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ganji  # noqa: E402
from scripts.refresh_order_aggregates import load_orders  # noqa: E402


def build(o: pd.DataFrame) -> pd.DataFrame:
    d = o[o["d"].notna()].copy()
    d = d[d["product"] != "기타"]
    # 절기 기준 명리월로 재배정 (달력월이 아님)
    sm = d["d"].dt.date.map(ganji.saju_month_of)
    d = d[sm.notna()].copy()
    d["sy"] = [x[0] for x in sm[sm.notna()]]
    d["sm"] = [x[1] for x in sm[sm.notna()]]

    rows = []
    # product='전체' 행 + 상품군별 행을 함께 생성 → 강의별 오행 분석 가능
    for (y, m), gm in d.groupby(["sy", "sm"]):
        yp = ganji.year_ganji(y, m)
        mp = ganji.month_ganji(y, m)
        base = {
            "saju_year": int(y), "saju_month": int(m),
            "year_pillar": yp, "month_pillar": mp,
            "stem": mp[0], "branch": mp[1],
            "stem_element": ganji.element_of(mp[0]),
            "branch_element": ganji.element_of(mp[1]),
        }
        for prod, g in [("전체", gm)] + list(gm.groupby("product")):
            rows.append({**base, "product": prod,
                         "free_signups": int((g["pay"] == 0).sum()),
                         "paid_orders": int((g["pay"] > 0).sum()),
                         "revenue": int(g.loc[g["pay"] > 0, "pay"].sum())})
    df = pd.DataFrame(rows).sort_values(["product", "saju_year", "saju_month"])
    cols = ["product", "saju_year", "saju_month", "year_pillar", "month_pillar",
            "stem", "branch", "stem_element", "branch_element",
            "free_signups", "paid_orders", "revenue"]
    return df[cols].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="강의별_리스트*.xlsx")
    ap.add_argument("--write", action="store_true", help="private repo에 반영")
    a = ap.parse_args()

    path = a.path
    if not path:
        cands = sorted(glob.glob(os.path.expanduser("~/Downloads/강의별_리스트*.xlsx")))
        if not cands:
            print("❌ 주문 엑셀을 찾지 못했습니다 (~/Downloads/강의별_리스트*.xlsx)")
            return 1
        path = cands[-1]
    print(f"📖 {os.path.basename(path)}")

    o = load_orders(path)
    df = build(o)

    print(f"\n명리월 {len(df)}개 · 모객 {df['free_signups'].sum():,} · "
          f"유료 {df['paid_orders'].sum():,} · 매출 {df['revenue'].sum()/1e8:.2f}억\n")
    for el in ["목", "화", "토", "금", "수"]:
        s = df[df["stem_element"] == el]
        b = df[df["branch_element"] == el]
        print(f"  {el}: 천간 {len(s):>2}개월 모객 {s['free_signups'].sum():>6,} · "
              f"지지 {len(b):>2}개월 모객 {b['free_signups'].sum():>6,}")

    if a.write:
        from github_store import _write_csv
        _write_csv("data/ohaeng_period.csv", df,
                   "data: 오행 시기별 모객·전환 집계 (절기 기준 명리월)")
        print("\n✅ private repo 반영 완료")
    else:
        print("\n(미리보기 — 반영하려면 --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
