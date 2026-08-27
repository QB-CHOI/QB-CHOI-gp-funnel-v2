"""알림 판정 — 화면과 자동 갱신이 같은 판정을 쓰도록 떼어낸 모듈.

이 판정은 원래 app.py 안에 있었다. 그런데 app.py는 Streamlit 스크립트라
사람이 브라우저로 사이트를 열어야만 실행된다 — 즉 **아무도 사이트를 안 열면
경고는 존재하지 않는 것과 같았다.** 실제로 '주문 명단 갱신 필요' 경고는
정확히 떠 있었는데도 명단이 27일 → 32일까지 밀렸다.

그래서 판정만 여기로 옮겨, 하루 3회 도는 scripts/auto_refresh.py가 같은
함수를 불러 슬랙으로 밀어줄 수 있게 했다. 화면과 자동 발송이 **같은 한 벌**을
써야 "사이트에는 떴는데 알림은 안 왔다"가 생기지 않는다.

Streamlit UI 호출(st.*)은 여기에 두지 않는다 — launchd에서 화면 없이 돈다.
"""
import calendar
from datetime import date, timedelta

import pandas as pd

import ganji
from github_store import (
    load_all, load_ad_spend_monthly, load_campaign_adspend, load_campaigns,
    load_monthly_performance, load_targets,
    complete_months, order_asof,
)


def lecture_date_split(cmp_df):
    """진행 중인 방 중 개강일이 빈 방을 (진짜 누락, 웨비나 대기)로 나눈다.

    개강일은 웨비나가 끝나야 정해진다. 모집만 하고 있는 방(원본 시트 참여코드
    '대기중')은 아직 값이 없는 게 정상인데, 예전에는 이것까지 '입력 누락'으로
    경고해 사람이 할 수 있는 일이 없는 알림이 계속 떠 있었다.
    시트 상태(status)를 함께 받아오므로 이제 둘을 구분한다.
    """
    empty = pd.DataFrame()
    if cmp_df.empty or 'is_current' not in cmp_df.columns:
        return empty, empty
    cur = cmp_df[cmp_df['is_current'].astype(str).str.lower().isin(['true', '1', 'yes'])]
    if cur.empty:
        return empty, empty
    nod = cur[cur['lecture_start_date'].isna() |
              (cur['lecture_start_date'].astype(str).str.strip() == '')]
    if nod.empty:
        return empty, empty
    if 'status' not in nod.columns:      # 동기화 전이면 예전처럼 전부 누락 취급
        return nod, empty
    _st = nod['status'].fillna('').astype(str)
    return nod[_st != '웨비나대기'], nod[_st == '웨비나대기']


def name_list(df, limit=3):
    """캠페인명 나열 — 넘치면 '외 N건'으로 접는다(건수와 이름 수가 어긋나지 않게)."""
    names = df['campaign_name'].astype(str).tolist()
    head = ', '.join(names[:limit])
    return head + (f" 외 {len(names) - limit}건" if len(names) > limit else "")


def generate_alerts() -> list:
    """기존 데이터를 종합 판정해 이상 신호를 반환. {sev, title, msg}."""
    alerts = []
    today = date.today()
    this_m = today.strftime('%Y-%m')

    # 1) 총원 급락 (동일 방 자연 감소, 방 종료 착시 제거)
    df = load_all()
    if not df.empty:
        _dates = sorted(df['date'].astype(str).unique())
        if len(_dates) >= 2:
            _latest = _dates[-1]
            _target = str((pd.Timestamp(_latest) - pd.Timedelta(days=7)).date())
            _cand = [d for d in _dates if d <= _target]
            if _cand:
                _prev = _cand[-1]
                _ls = df[df['date'].astype(str) == _latest].set_index('room_num')['members']
                _ps = df[df['date'].astype(str) == _prev].set_index('room_num')['members']
                _common = _ls.index.intersection(_ps.index)
                if len(_common):
                    _pv = int(_ps[_common].sum())
                    _ch = int(_ls[_common].sum()) - _pv
                    _pct = _ch / _pv * 100 if _pv else 0
                    if _pct <= -10:
                        alerts.append({'sev': 'critical', 'title': '총원 급락',
                                       'msg': f"최근 7일 동일 방 총원이 **{_pct:.1f}%({_ch:,}명)** 감소. "
                                              "콘텐츠·소통 점검과 이탈 원인 진단이 필요합니다."})
                    elif _pct <= -5:
                        alerts.append({'sev': 'warning', 'title': '총원 감소',
                                       'msg': f"최근 7일 동일 방 총원 **{_pct:.1f}%({_ch:,}명)** 감소 추세."})

    # 2) 매출 둔화 (최근 완료월 vs 직전 3개월 평균)
    perf = load_monthly_performance()
    _pidx = perf.set_index('month') if not perf.empty else pd.DataFrame()
    if not perf.empty:
        _p = perf.sort_values('month')
        # 부분월(주문 스냅샷이 중간에 끊긴 달)을 '완료월'로 보면 매출이 폭락한 것처럼
        # 보여 없는 문제를 경고한다 — 실제로 2026-07이 그 상태였다.
        _comp = complete_months(_p)
        if len(_comp) >= 4:
            _last = _comp.iloc[-1]
            _rr = _comp['revenue'].iloc[-4:-1].mean()
            if _rr and int(_last['revenue']) < _rr * 0.6:
                alerts.append({'sev': 'warning', 'title': '매출 둔화',
                               'msg': f"최근 완료월({ganji.ym_label(_last['month'], with_ganji=False)}) 매출 **{_last['revenue']/1e8:.2f}억**이 "
                                      f"직전 3개월 평균({_rr/1e8:.2f}억)의 60% 미만입니다. "
                                      "개강 공백인지 실적 저하인지 확인하세요."})

    # 2-1) 주문 명단이 오래됨 — 매출·전환·고객·전망이 통째로 옛날 값이 된다.
    # 다른 데이터와 달리 이건 '조금 오래됨'이 아니라 '최근 실적이 아예 안 보임'이다.
    _ao_al = order_asof()
    if _ao_al:
        _gap = (today - _ao_al).days
        if _gap >= 14:
            _sev = 'critical' if _gap >= 30 else 'warning'
            alerts.append({'sev': _sev, 'title': '주문 명단 갱신 필요',
                           'msg': f"주문 데이터가 **{_ao_al}까지**입니다(**{_gap}일 경과**). "
                                  f"{ganji.ym_label(_ao_al.strftime('%Y-%m'), with_ganji=False)} 이후 "
                                  "매출·유료 전환·고객·지역 분석이 비어 있습니다. "
                                  "쇼핑몰에서 최신 주문 명단을 내려받아 갱신하세요."})

    # 3) 목표 진행 지연 (이번 달)
    tgt = load_targets()
    if not tgt.empty and not _pidx.empty:
        _tm = tgt[tgt['month'].astype(str) == this_m]
        if not _tm.empty and this_m in _pidx.index:
            _t = _tm.iloc[0]
            if int(_t['revenue_target']) > 0:
                _act = int(_pidx.loc[this_m, 'revenue'])
                _dim = calendar.monthrange(today.year, today.month)[1]
                _elapsed = today.day / _dim
                _prog = _act / int(_t['revenue_target'])
                if _prog < _elapsed - 0.15:
                    alerts.append({'sev': 'warning', 'title': '목표 진행 지연',
                                   'msg': f"{this_m} 매출 목표 진행률 **{_prog*100:.0f}%**가 "
                                          f"경과일({_elapsed*100:.0f}%)보다 뒤처집니다. "
                                          "남은 기간 프로모션·광고 조정을 검토하세요."})

    # 4) 광고 저효율 기수 (3천만+ 집행, ROAS<2)
    camp = load_campaign_adspend()
    if not camp.empty:
        _g = camp.groupby(['product', 'cohort']).agg(
            ad=('ad_spend', 'sum'), rev=('live_revenue', 'sum')).reset_index()
        _g = _g[_g['ad'] >= 3e7].copy()
        if not _g.empty:
            _g['roas'] = _g['rev'] / _g['ad']
            _low = _g[_g['roas'] < 2].sort_values('roas')
            if not _low.empty:
                _r = _low.iloc[0]
                alerts.append({'sev': 'warning', 'title': '광고 저효율 기수',
                               'msg': f"**{_r['product']} {_r['cohort']}** 광고 ROAS **{_r['roas']:.1f}배**"
                                      f"(광고비 {_r['ad']/1e8:.2f}억)로 낮습니다. 소재·타깃·랜딩 재점검 대상."})

    # 5) 데이터 미입력 (최근 3일)
    if not df.empty:
        _recent3 = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(3)]
        _entered = set(df['date'].astype(str))
        _missing = [d for d in _recent3 if d not in _entered]
        if len(_missing) >= 2:
            alerts.append({'sev': 'info', 'title': '데이터 미입력',
                           'msg': f"최근 3일 중 **{len(_missing)}일** 인원이 미입력입니다. "
                                  "정확한 추세·전망을 위해 입력을 권장합니다."})

    # 6) 진행 중인데 개강일이 비어 있는 강의
    #    개강일이 없으면 개강 효과·기간별 분석에서 그 기수가 통째로 빠진다.
    #    단 웨비나 전(모집만 하는 방)은 개강일이 없는 게 정상이라 제외한다.
    _nod, _ = lecture_date_split(load_campaigns())
    if not _nod.empty:
        alerts.append({
            'sev': 'warning', 'title': '개강일 미입력',
            'msg': f"진행 중인 강의 **{len(_nod)}건**({name_list(_nod)})의 "
                   "개강일이 비어 있습니다. 개강 효과·기간별 분석에서 제외되므로 "
                   "**⚙️ 채팅방 설정**에서 입력하세요."})

    # 7) 이번 달 광고비 미입력 — ROAS·CPL 판정이 통째로 지난달에 멈춘다.
    #    광고는 지금 돌고 있는데 사이트는 그 사실을 모르는 상태가 된다.
    _adm = load_ad_spend_monthly()
    if not _adm.empty:
        _mon = set(_adm['month'].astype(str))
        if this_m not in _mon:
            _last_m = max(_mon)
            _gap_m = ((today.year - int(_last_m[:4])) * 12 +
                      (today.month - int(_last_m[5:7])))
            alerts.append({
                'sev': 'warning' if _gap_m >= 2 else 'info', 'title': '이번 달 광고비 미입력',
                'msg': f"월별 광고비가 **{ganji.ym_label(_last_m, with_ganji=False)}까지**입니다. "
                       f"{ganji.ym_label(this_m, with_ganji=False)} 광고비가 없으면 ROAS·CPL 판정과 "
                       "예산 조언이 지난달 기준으로 남습니다. "
                       "**📢 마케팅 분석 → 월별 광고비**에서 이번 달 총액을 입력하세요."})
    return alerts


SEV_ICON = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}


def slack_message(alerts, header=None) -> str:
    """알림 목록 → 슬랙 본문.

    화면의 '슬랙으로 전송' 버튼과 자동 갱신이 **같은 문구**를 쓰게 한다.
    따로 만들면 한쪽만 고쳐져 "사이트에서 본 것과 알림이 다르다"가 된다.
    """
    lines = [f"{SEV_ICON.get(a['sev'], '•')} *{a['title']}* — {a['msg'].replace('**', '*')}"
             for a in alerts]
    head = header or f"📊 *황금후추 강의 분석 — 이상 알림* ({date.today()})"
    return head + "\n" + "\n".join(lines)


def alert_signature(alerts) -> str:
    """알림 '구성'의 지문.

    하루 세 번 도는 자동 갱신이 같은 내용을 세 번 보내지 않도록 비교하는 값.
    본문(경과 일수 등)은 매일 조금씩 변하므로 심각도와 제목만 본다.
    """
    return "|".join(sorted(f"{a['sev']}:{a['title']}" for a in alerts))
