"""명리학 간지(干支) 변환 — 양력 연·월 → 년주·월주(천간지지).

월별 데이터 라벨을 '2026-06' 같은 ISO 표기에서 '2026년 6월' + 사주 구조
(丙午年 甲午月)로 바꾸기 위한 헬퍼.

규칙(만세력 기준):
- 년주: 60갑자. 단, 명리 년은 입춘(~2/4)에 바뀌므로 **양력 1월은 전년 간지**로 본다.
- 월주(월지): 절기(節) 기준. 양력 월의 대표(다수일) 절기월로 매핑.
    입춘~ 寅(2월) · 경칩~ 卯(3월) · 청명~ 辰(4월) · 입하~ 巳(5월) ·
    망종~ 午(6월) · 소서~ 未(7월) · 입추~ 申(8월) · 백로~ 酉(9월) ·
    한로~ 戌(10월) · 입동~ 亥(11월) · 대설~ 子(12월) · 소한~ 丑(1월)
- 월간: 오호둔(五虎遁) — 년간에 따라 寅월 천간이 정해지고 순행.

한계: 양력 월 단위 근사이므로 각 달 초의 며칠(절기 이전)은 전월 간지에 속함.
정밀 일주·시주는 정확한 날짜/시각이 필요해 여기서는 다루지 않는다(년주·월주만).
"""

# ── 오행(五行) ────────────────────────────────────────────────
# 천간·지지가 각각 어느 오행에 속하는지. 색상은 전통 오방색(청·적·황·백·흑)을
# 화면 가독성에 맞춰 조정: 금(백)→은회, 수(흑)→청람. 라이트/다크 양쪽에서 읽힌다.
ELEMENT_OF = {
    '甲': '목', '乙': '목', '丙': '화', '丁': '화', '戊': '토',
    '己': '토', '庚': '금', '辛': '금', '壬': '수', '癸': '수',
    '寅': '목', '卯': '목', '巳': '화', '午': '화', '辰': '토',
    '戌': '토', '丑': '토', '未': '토', '申': '금', '酉': '금',
    '亥': '수', '子': '수',
}
ELEMENT_COLORS = {
    '목': '#2E9E5B',   # 청(靑) → 초록
    '화': '#E0483E',   # 적(赤)
    '토': '#C8901A',   # 황(黃)
    '금': '#8E9BA8',   # 백(白) → 은회(가독성)
    '수': '#3B82F6',   # 흑(黑) → 청람(가독성)
}
ELEMENT_HANJA = {'목': '木', '화': '火', '토': '土', '금': '金', '수': '水'}


def element_of(ch: str) -> str:
    """한 글자(천간 또는 지지)의 오행. 예: '甲'→'목'."""
    return ELEMENT_OF.get(ch, '')


def color_of(ch: str) -> str:
    """한 글자의 오행 색상 hex. 모르는 글자는 회색."""
    return ELEMENT_COLORS.get(ELEMENT_OF.get(ch, ''), '#9AA0A6')


def colorize(s: str, bold: bool = True) -> str:
    """간지 문자열의 각 글자를 오행 색으로 감싼 HTML.

    plotly 눈금·st.markdown 모두 <span style="color:..."> 를 지원한다.
    간지가 아닌 글자(공백·年月 등)는 그대로 둔다.
    """
    out = []
    for ch in str(s):
        if ch in ELEMENT_OF:
            w = 'font-weight:700;' if bold else ''
            out.append(f'<span style="color:{color_of(ch)};{w}">{ch}</span>')
        else:
            out.append(ch)
    return ''.join(out)


def element_legend_html() -> str:
    """오행 색상 범례 HTML."""
    items = []
    for el, col in ELEMENT_COLORS.items():
        items.append(
            f'<span style="display:inline-block;margin-right:14px;white-space:nowrap">'
            f'<span style="color:{col};font-weight:700;font-size:15px">'
            f'{ELEMENT_HANJA[el]}</span> '
            f'<span style="opacity:.75;font-size:12px">{el}</span></span>')
    return ('<div style="margin:2px 0 6px">' + ''.join(items) +
            '<span style="opacity:.55;font-size:11px">'
            '· 전통 오방색 기준(금=백→은회, 수=흑→청람으로 가독성 조정)</span></div>')


STEMS_HAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
STEMS_KOR = ['갑', '을', '병', '정', '무', '기', '경', '신', '임', '계']
BRANCHES_HAN = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
BRANCHES_KOR = ['자', '축', '인', '묘', '진', '사', '오', '미', '신', '유', '술', '해']


def _pillars(cal_year: int, cal_month: int):
    """(년간, 년지, 월간, 월지) 인덱스 반환. 년간=甲기준0, 년지=子기준0."""
    # 입춘 경계 근사: 양력 1월은 전년(명리 년)
    my = cal_year - 1 if cal_month == 1 else cal_year
    ys = (my - 4) % 10           # 년간
    yb = (my - 4) % 12           # 년지 (子=0)
    mb = cal_month % 12          # 월지 (子=0): 6월→午(6), 7월→未(7), 12월→子(0)
    # 오호둔: 寅월 천간 = ((년간%5)*2+2)%10, 이후 寅기준 순서만큼 순행
    yin_stem = ((ys % 5) * 2 + 2) % 10
    order = (mb - 2) % 12        # 寅(index2)을 0으로 하는 순서
    ms = (yin_stem + order) % 10  # 월간
    return ys, yb, ms, mb


def year_ganji(cal_year: int, cal_month: int = 6, han: bool = True) -> str:
    """년주 간지. 예: 2026,6 → '丙午'(han) / '병오'(kor)."""
    ys, yb, _, _ = _pillars(cal_year, cal_month)
    if han:
        return STEMS_HAN[ys] + BRANCHES_HAN[yb]
    return STEMS_KOR[ys] + BRANCHES_KOR[yb]


def month_ganji(cal_year: int, cal_month: int, han: bool = True) -> str:
    """월주 간지. 예: 2026,6 → '甲午'(han) / '갑오'(kor)."""
    _, _, ms, mb = _pillars(cal_year, cal_month)
    if han:
        return STEMS_HAN[ms] + BRANCHES_HAN[mb]
    return STEMS_KOR[ms] + BRANCHES_KOR[mb]


def saju_han(cal_year: int, cal_month: int) -> str:
    """사주 구조(년주·월주) 한자. 예: '丙午年 甲午月'."""
    return f"{year_ganji(cal_year, cal_month)}年 {month_ganji(cal_year, cal_month)}月"


def saju_kor(cal_year: int, cal_month: int) -> str:
    """사주 구조 한글 독음. 예: '병오년 갑오월'."""
    return f"{year_ganji(cal_year, cal_month, han=False)}년 {month_ganji(cal_year, cal_month, han=False)}월"


def ym_korean(cal_year: int, cal_month: int) -> str:
    """'2026년 6월'."""
    return f"{cal_year}년 {cal_month}월"


def _parse_ym(ym):
    """'2026-06', '2026-06-01', '2026.6', (2026,6) 등 → (year, month) 또는 None."""
    if ym is None:
        return None
    if isinstance(ym, (tuple, list)) and len(ym) >= 2:
        try:
            return int(ym[0]), int(ym[1])
        except (TypeError, ValueError):
            return None
    s = str(ym).strip()
    import re
    m = re.match(r'^(\d{4})[-./년\s]+(\d{1,2})', s)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    if not (1 <= mo <= 12):
        return None
    return y, mo


def ym_label(ym, with_ganji: bool = True, sep: str = ' · ', han: bool = True) -> str:
    """'2026-06' → '2026년 6월 · 丙午年 甲午月'. 파싱 불가 시 원본 반환."""
    p = _parse_ym(ym)
    if p is None:
        return str(ym)
    y, mo = p
    base = ym_korean(y, mo)
    if not with_ganji:
        return base
    return f"{base}{sep}{saju_han(y, mo) if han else saju_kor(y, mo)}"


# ── 절기(節氣) 절입일 ─────────────────────────────────────────
# 월주는 매월 1일이 아니라 절기(입춘·경칩·청명…)에 바뀐다. 아래는 각 달에서
# **새 월주가 시작되는 날짜(일)**. 만세력 라이브러리 sajupy(MIT)로 오프라인
# 생성·검증했으며, 런타임 의존성을 만들지 않으려고 표로 embed했다.
# (전체 기간 일별 대조 결과 이 표 적용 시 sajupy와 100% 일치)
_JEOLGI_DAY = {
    2023: [6, 4, 6, 5, 6, 6, 8, 8, 8, 9, 8, 8],
    2024: [6, 5, 5, 5, 5, 6, 7, 7, 8, 8, 7, 6],
    2025: [5, 4, 6, 5, 6, 6, 7, 8, 8, 8, 8, 7],
    2026: [6, 4, 6, 5, 6, 6, 7, 8, 7, 9, 8, 7],
    2027: [6, 4, 6, 5, 6, 6, 8, 8, 8, 9, 7, 8],
    2028: [6, 5, 5, 5, 5, 6, 7, 7, 7, 8, 7, 7],
}
_JEOLGI_FALLBACK = [6, 4, 6, 5, 6, 6, 7, 8, 8, 8, 8, 7]  # 표 밖 연도용 평균 절입일


def jeolgi_day(year: int, month: int) -> int:
    """그 달에 새 월주가 시작되는 날짜(일). 표에 없으면 평년 근사치."""
    row = _JEOLGI_DAY.get(year)
    return (row or _JEOLGI_FALLBACK)[month - 1]


def saju_month_of(d):
    """날짜 → 그 날이 실제로 속한 **명리 월**(year, month) — 절기 기준.

    절입일 이전이면 전월에 속한다. 예: 2026-06-03은 절입(6/6) 전이므로
    2026년 5월(癸巳月)에 속한다.
    """
    import datetime as _dt
    if isinstance(d, str):
        try:
            d = _dt.date.fromisoformat(str(d)[:10])
        except ValueError:
            return None
    if isinstance(d, _dt.datetime):
        d = d.date()
    if not isinstance(d, _dt.date):
        return None
    y, m = d.year, d.month
    if d.day < jeolgi_day(y, m):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return y, m


def day_ganji(d, han: bool = True) -> str:
    """일주(日柱) 간지. 60갑자 연속 순환 — 2000-01-07(甲子日) 기준.

    d: date/datetime 또는 'YYYY-MM-DD' 문자열.
    """
    import datetime as _dt
    if isinstance(d, str):
        try:
            d = _dt.date.fromisoformat(d[:10])
        except ValueError:
            return ''
    if isinstance(d, _dt.datetime):
        d = d.date()
    if not isinstance(d, _dt.date):
        return ''
    n = (d - _dt.date(2000, 1, 7)).days   # 甲子일 기준 경과일
    if han:
        return STEMS_HAN[n % 10] + BRANCHES_HAN[n % 12]
    return STEMS_KOR[n % 10] + BRANCHES_KOR[n % 12]


def date_tick(d, lines: bool = True, color: bool = True) -> str:
    """일자 축용 라벨. '6월 15일<br>丙午 甲午' (년주·월주만 — 일주는 표기하지 않음)."""
    import datetime as _dt
    s = str(d)[:10]
    try:
        dd = _dt.date.fromisoformat(s)
    except ValueError:
        return str(d)
    gj = f"{year_ganji(dd.year, dd.month)} {month_ganji(dd.year, dd.month)}"
    if color:
        gj = colorize(gj)
    head = f"{dd.month}월 {dd.day}일"
    return f"{head}<br>{gj}" if lines else f"{head} ({gj})"


def ym_tick(ym, lines: bool = True, color: bool = True) -> str:
    """차트 축용 짧은 라벨. '2026년 6월\\n丙午 甲午' (년주·월주, 오행 색상)."""
    p = _parse_ym(ym)
    if p is None:
        return str(ym)
    y, mo = p
    gj = f"{year_ganji(y, mo)} {month_ganji(y, mo)}"
    if color:
        gj = colorize(gj)
    if lines:
        return f"{y}년 {mo}월<br>{gj}"
    return f"{y}년 {mo}월 ({gj})"
