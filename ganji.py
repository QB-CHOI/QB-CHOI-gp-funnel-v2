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


def ym_tick(ym, lines: bool = True) -> str:
    """차트 축용 짧은 라벨. '2026년 6월\\n丙午 甲午' (년주·월주 한자, 年/月 생략)."""
    p = _parse_ym(ym)
    if p is None:
        return str(ym)
    y, mo = p
    yg = year_ganji(y, mo)
    mg = month_ganji(y, mo)
    if lines:
        return f"{y}년 {mo}월<br>{yg} {mg}"
    return f"{y}년 {mo}월 ({yg} {mg})"
