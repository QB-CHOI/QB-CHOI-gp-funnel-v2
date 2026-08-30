"""계산 로직 회귀 검사 — 네트워크 없이 1초 안에 끝난다.

실행: python3 verify_logic.py

`verify_app.py`는 **지금 데이터로** 화면이 그려지는지를 본다. 그래서 계산이
틀려도 예외만 안 나면 통과한다 — 실제로 지금까지 사이트를 조용히 망가뜨린 건
대부분 그런 종류였다(부분월을 완결월로 봐서 전망이 10% 낮게 나온 v4.70,
건수는 4인데 이름은 3개만 나오던 v4.75, 웨비나 대기를 입력 누락으로 경고하던
v4.75). 데이터가 바뀌면 재현되지도 않는다.

여기서는 **고쳤던 버그를 그대로 재현하는 입력**을 넣고 결과를 못 박는다.
같은 실수가 다시 들어오면 푸시가 막힌다. 각 검사에 어느 버전에서 왜 생겼는지
근거를 적어 둔다 — 나중에 이 단언이 걸리적거릴 때 지워도 되는 것인지
판단하려면 그 맥락이 있어야 한다.

원격 데이터를 읽지 않는다. 읽어야 하는 함수(order_asof)는 값을 갈아 끼운다.
"""
import logging
import sys
from datetime import date

import pandas as pd

# github_store가 streamlit을 끌어오는데 화면 없이 돌면 "No runtime found"를 매
# 호출마다 찍는다 — 검사 결과 7줄이 경고 46줄에 묻힌다(v4.79와 같은 처리).
try:
    import streamlit.logger as _st_logger
    _st_logger.set_log_level("error")
except Exception:
    logging.getLogger("streamlit").setLevel(logging.ERROR)

FAILS = []
PASSED = 0


def check(name, got, want, why):
    """got == want 를 확인. 어긋나면 무엇이 왜 중요한지와 함께 모아 둔다."""
    global PASSED
    ok = got == want
    if ok:
        PASSED += 1
    else:
        FAILS.append(f"{name}\n        기대 {want!r} / 실제 {got!r}\n        └ {why}")
    return ok


# ── 1) 부분월 판정 (v4.70) ────────────────────────────────────────
def test_complete_months():
    """주문 스냅샷이 달 중간에서 끊긴 달을 '완결월'로 세면 안 된다.

    v4.70: 원본이 7/19 export인데 2026-07을 완결월로 계산에 넣어 매출이
    6,744만원(6월은 9.4억)으로 찍히고, 런레이트가 4.47억(정상 4.94억)으로
    10% 낮게 나왔다. '오늘 날짜'가 아니라 '주문 원본의 마지막 날짜'가 기준이다.
    """
    import github_store as gs

    df = pd.DataFrame({'month': ['2026-05', '2026-06', '2026-07', '2026-08'],
                       'revenue': [1, 2, 3, 4]})
    _orig = gs.order_asof
    try:
        gs.order_asof = lambda: date(2026, 7, 19)      # 7/19까지만 담긴 스냅샷
        got = list(gs.complete_months(df)['month'])
        check("부분월 제외 (주문 스냅샷 7/19)", got, ['2026-05', '2026-06'],
              "7월은 19일치만 담긴 부분월 — 완결월로 세면 매출·런레이트가 낮게 나온다")

        gs.order_asof = lambda: None                   # 기준일을 모를 때
        got = list(gs.complete_months(df)['month'])
        want = [m for m in ['2026-05', '2026-06', '2026-07', '2026-08']
                if m < date.today().strftime('%Y-%m')]
        check("기준일 없으면 당월만 제외", got, want,
              "as_of를 못 읽어도 최소한 진행 중인 당월은 빠져야 한다")

        check("빈 입력은 그대로", len(gs.complete_months(pd.DataFrame())), 0,
              "데이터가 아직 없을 때 예외로 죽지 않아야 한다")
    finally:
        gs.order_asof = _orig


# ── 2) 웨비나 대기 분리 (v4.75) ───────────────────────────────────
def test_lecture_date_split():
    """개강일이 비어 있어도 '웨비나 전'이면 정상이다.

    v4.75: 웨비나 전이라 개강일이 아직 존재하지도 않는 방 4개를 '입력 누락'으로
    2주 넘게 경고했다. 사람이 할 수 있는 일이 없는 알림은 다른 알림까지
    무시하게 만든다.
    """
    from alerts import lecture_date_split

    df = pd.DataFrame([
        {'campaign_name': '돈사공 13기', 'lecture_start_date': '', 'is_current': True,
         'status': '웨비나대기'},
        {'campaign_name': '돈빌공 6기', 'lecture_start_date': '', 'is_current': True,
         'status': '모집중'},
        {'campaign_name': '돈타공 4기', 'lecture_start_date': '2026-03-24',
         'is_current': True, 'status': '모집중'},
        {'campaign_name': '옛날 방', 'lecture_start_date': '', 'is_current': False,
         'status': '모집중'},
    ])
    miss, wait = lecture_date_split(df)
    check("진짜 누락만 경고", list(miss['campaign_name']), ['돈빌공 6기'],
          "웨비나 대기(개강일이 아직 없는 게 정상)와 종료된 방은 빠져야 한다")
    check("웨비나 대기는 따로", list(wait['campaign_name']), ['돈사공 13기'],
          "경고가 아니라 '개강 대기'로 보여 주는 대상")

    # status 열이 생기기 전 CSV로도 동작해야 한다(동기화 전 하위호환)
    old = df.drop(columns=['status'])
    miss2, wait2 = lecture_date_split(old)
    check("status 없으면 예전처럼 전부 누락", len(miss2), 2,
          "열이 없다고 빈 결과를 내면 경고가 통째로 잠든다")
    check("status 없으면 대기는 0건", len(wait2), 0, "구분할 근거가 없을 때의 안전한 기본값")


# ── 3) 이름 나열 (v4.75) ──────────────────────────────────────────
def test_name_list():
    """건수와 실제로 적힌 이름 수가 어긋나면 안 된다.

    v4.75: '4건'이라 써 놓고 이름은 3개만 나와, 나머지 하나를 찾을 방법이 없었다.
    """
    from alerts import name_list

    df = pd.DataFrame({'campaign_name': ['가', '나', '다', '라']})
    check("넘치면 '외 N건'", name_list(df), "가, 나, 다 외 1건",
          "이름을 자를 거면 몇 개를 잘랐는지 반드시 밝혀야 한다")
    check("한도 이하면 전부", name_list(df.head(2)), "가, 나",
          "3개 이하는 접지 않는다")


# ── 4) 기준선 계산 (v4.78) ────────────────────────────────────────
def test_open_to_live_days():
    """'얼마나 오래 대기하면 이상한가'를 손으로 정하지 않고 실적에서 뽑는다."""
    from alerts import open_to_live_days

    cmp_df = pd.DataFrame([{'product': 'p', 'cohort': f'{i}기',
                            'start_date': '2026-01-01'} for i in range(6)])
    live = ['2026-01-11', '2026-01-21', '2026-01-31',
            '2026-02-10', '2026-02-20', '2026-05-01']
    ad = pd.DataFrame([{'product': 'p', 'cohort': f'{i}기', 'live_date': live[i]}
                       for i in range(6)])
    got = open_to_live_days(cmp_df, ad, q=0.9)
    check("90분위 기준선", got, 85,
          "10·20·30·40·50·120일 → 선형보간 90분위 = 50+0.5*(120-50) = 85일. "
          "대부분이 끝낸 기간을 선으로 쓰되 최장(120)에 끌려가지 않는다")

    check("표본 부족하면 None", open_to_live_days(cmp_df.head(3), ad.head(3)), None,
          "몇 건 안 되는 이력으로 기준선을 만들면 근거가 아니라 착시다")
    check("빈 입력은 None", open_to_live_days(pd.DataFrame(), pd.DataFrame()), None,
          "데이터가 없으면 조용히 기본값으로 넘어가야 한다")


# ── 5) 알림 발송 억제 (v4.76) ─────────────────────────────────────
def test_alert_signature():
    """하루 3회 도는 자동 갱신이 같은 알림을 세 번 보내지 않게 하는 값.

    본문에는 '40일 경과'처럼 매일 변하는 숫자가 들어 있다. 지문이 본문까지
    보면 매번 달라져 억제가 통째로 풀린다 — 심각도와 제목만 봐야 한다.
    """
    from alerts import alert_signature, slack_message

    a = [{'sev': 'critical', 'title': '주문 명단 갱신 필요', 'msg': '40일 경과'},
         {'sev': 'warning', 'title': '광고 저효율 기수', 'msg': 'ROAS 1.5배'}]
    b = [{'sev': 'warning', 'title': '광고 저효율 기수', 'msg': 'ROAS 1.4배'},
         {'sev': 'critical', 'title': '주문 명단 갱신 필요', 'msg': '41일 경과'}]
    check("순서·본문이 달라도 같은 지문", alert_signature(a), alert_signature(b),
          "매일 바뀌는 일수 때문에 같은 알림이 새 알림으로 보이면 안 된다")

    c = [{'sev': 'critical', 'title': '총원 급락', 'msg': ''}] + a
    check("구성이 바뀌면 다른 지문", alert_signature(c) != alert_signature(a), True,
          "새 경고가 생기면 억제를 뚫고 즉시 알려야 한다")
    check("빈 목록은 빈 지문", alert_signature([]), "",
          "보낼 게 없는 상태를 저장해 둬야 다음에 생겼을 때 '변경'으로 잡힌다")

    msg = slack_message(a)
    check("슬랙 볼드 변환", "*주문 명단 갱신 필요*" in msg and "**" not in msg, True,
          "슬랙은 별 하나가 볼드 — 마크다운 그대로 보내면 별이 그대로 보인다")
    check("심각도 아이콘", msg.count("🔴") == 1 and msg.count("🟡") == 1, True,
          "위험과 주의를 한눈에 가를 수 있어야 한다")


# ── 6) 절기 기준 월주 (v4.49) ─────────────────────────────────────
def test_ganji_jeolgi():
    """월주는 양력 1일이 아니라 절입일에 바뀐다.

    v4.49: 달력월로 집계하면 매월 앞 5일(전체 18%)이 다른 오행에 배정된다.
    절기표를 코드에 심어 런타임 의존성 없이 처리한다.
    """
    import ganji

    check("절입 전은 지난달 (2026-06-03)", ganji.saju_month_of(date(2026, 6, 3)),
          (2026, 5), "6월이지만 망종 전이라 아직 癸巳月 — 달력월로 자르면 오배정된다")
    check("절입일부터 이번 달 (2026-06-06)", ganji.saju_month_of(date(2026, 6, 6)),
          (2026, 6), "절입일 당일부터 새 월주")
    check("2026-06 절입일", ganji.jeolgi_day(2026, 6), 6, "내장 절기표가 바뀌면 즉시 드러나야 한다")
    check("2026-05 월주", ganji.month_ganji(2026, 5), '癸巳', "v4.49 검증 당시 값")
    check("2026 년주", ganji.year_ganji(2026), '丙午', "년주는 입춘 기준")


# ── 7) 읽기 실패를 쓰기로 흘려보내지 않기 (v4.83) ────────────────
def test_read_write_guard():
    """원격 CSV를 **못 읽은 것**을 '비어 있다'로 보면 원본이 통째로 날아간다.

    v4.83: 저장 경로 27곳이 모두 '읽고 → 합치고 → 통째로 쓰기'인데,
    _read_csv가 연결 오류·401·403·5xx를 전부 404(빈 파일)와 같은 빈 표로
    돌려주고 있었다. 실제로 두 번 터졌다 — 2026-08-22 rooms.csv의 사람이 붙인
    별칭 8개가 기본값으로 되돌아갔고, 2026-08-29 campaigns.csv가 16행에서
    11행으로 줄어 종료된 방 5개(돈빌공 5기·돈사공 11기 계열)가 사라졌다.
    화면 없는 자동 갱신이라 st.error()는 아무 데도 안 찍혀 흔적조차 없었다.
    """
    import base64
    import requests
    import github_store as gs

    class Res:
        def __init__(self, code, payload=None):
            self.status_code = code; self._p = payload or {}
        @property
        def ok(self): return 200 <= self.status_code < 300
        def json(self): return self._p

    _get, _put, _read = gs._SESSION.get, gs._SESSION.put, gs._read_csv
    gs._RETRY_WAIT = 0          # 실패를 일부러 만들어 내는 검사 — 기다릴 이유가 없다
    try:
        # 실패와 '아직 없는 파일'은 반드시 달라야 한다
        gs._SESSION.get = lambda *a, **k: Res(404)
        check("404는 빈 표", gs._read_csv("x.csv", ["a"]).empty, True,
              "아직 만들어지지 않은 파일 — 이건 정상이라 빈 표가 맞다")

        for code in (500, 403, 401):
            gs._SESSION.get = lambda *a, _c=code, **k: Res(_c)
            raised = False
            try:
                gs._read_csv("x.csv", ["a"])
            except gs.RemoteReadError:
                raised = True
            check(f"HTTP {code}는 예외", raised, True,
                  "못 읽은 것을 빈 표로 돌려주면 그 위에 덮어써져 원본이 사라진다")

        def boom(*a, **k): raise requests.exceptions.ConnectionError("끊김")
        gs._SESSION.get = boom
        raised = False
        try:
            gs._read_csv("x.csv", ["a"])
        except gs.RemoteReadError:
            raised = True
        check("연결 끊김은 예외", raised, True, "위와 같은 이유")

        # 행이 줄어드는 저장은 의도를 밝힌 경우에만
        cur = base64.b64encode(b"room_num,room_name\n1,a\n2,b\n3,c\n").decode()
        gs._SESSION.get = lambda *a, **k: Res(200, {"sha": "x", "content": cur})
        puts = []
        gs._SESSION.put = lambda *a, **k: (puts.append(1), Res(200))[1]

        shrunk = pd.DataFrame([{"room_num": 1, "room_name": "a"}])
        blocked = False
        try:
            gs._write_csv("data/rooms.csv", shrunk, "축소")
        except RuntimeError:
            blocked = True
        check("3행 → 1행 저장은 거부", blocked, True,
              "campaigns.csv가 16행에서 11행으로 줄어든 그 경로")
        check("거부되면 PUT을 보내지 않는다", puts, [],
              "막았다면서 실제로 보내면 아무 의미가 없다")

        puts.clear()
        gs._write_csv("data/rooms.csv", shrunk, "의도된 삭제", allow_shrink=True)
        check("allow_shrink면 삭제는 그대로", len(puts), 1,
              "사고는 막되 사람이 지우는 기능은 살아 있어야 한다")

        puts.clear()
        grown = pd.DataFrame([{"room_num": i, "room_name": "x"} for i in range(1, 5)])
        gs._write_csv("data/rooms.csv", grown, "추가")
        check("행이 늘면 통과", len(puts), 1, "정상 저장까지 막으면 안 된다")

        # 자동 등록이 사람이 붙인 별칭을 덮어쓰면 안 된다
        gs._read_csv = lambda p, c: pd.DataFrame(
            [{"room_num": 37, "room_name": "채팅방 37 (부동산2)"}])
        puts.clear()
        gs.save_rooms_batch({37: "채팅방 37"})
        check("이미 있는 방은 저장 자체를 안 한다", puts, [],
              "들어오는 이름은 기본값 — 별칭 8개가 이렇게 날아갔다")
    finally:
        gs._SESSION.get, gs._SESSION.put, gs._read_csv = _get, _put, _read
        gs._RETRY_WAIT = 1.5


TESTS = [
    ("부분월 판정 (v4.70)", test_complete_months),
    ("웨비나 대기 분리 (v4.75)", test_lecture_date_split),
    ("이름 나열 (v4.75)", test_name_list),
    ("대기 기준선 (v4.78)", test_open_to_live_days),
    ("알림 억제 (v4.76)", test_alert_signature),
    ("절기 기준 월주 (v4.49)", test_ganji_jeolgi),
    ("읽기 실패 → 쓰기 차단 (v4.83)", test_read_write_guard),
]


def main() -> int:
    print("계산 로직 회귀 검사")
    for label, fn in TESTS:
        before = len(FAILS)
        try:
            fn()
        except Exception as e:                 # 검사 자체가 터진 것도 실패다
            FAILS.append(f"{label} — 검사 실행 중 예외: {type(e).__name__}: {e}")
        mark = "✅" if len(FAILS) == before else "🚨"
        print(f"   {mark} {label}")

    print()
    if FAILS:
        print(f"❌ 실패 {len(FAILS)}건 / 통과 {PASSED}건")
        for f in FAILS:
            print(f"   🚨 {f}")
        print("\n고친 버그가 되돌아왔거나, 의도적으로 바꿨다면 이 검사도 함께 고치세요.")
        return 1
    print(f"✅ 통과 — {PASSED}개 단언 모두 정상")
    return 0


if __name__ == "__main__":
    sys.exit(main())
