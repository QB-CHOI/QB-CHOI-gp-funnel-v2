import io
import pandas as pd
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, LineChart, Reference

# ── 색상 팔레트 ───────────────────────────────────────────────────
COLOR = {
    'header_bg':   'FF37474F',
    'header_font': 'FFFFFFFF',
    'pos':         'FF2E7D32',  # 증가 (초록)
    'neg':         'FFC62828',  # 감소 (빨강)
    'neutral':     'FF9E9E9E',
    'row_even':    'FFF5F5F5',
    'row_odd':     'FFFFFFFF',
    'border':      'FFDDDDDD',
}

_thin = Side(style='thin', color=COLOR['border'])
_border = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def _header_style(cell, text):
    cell.value = text
    cell.font = Font(bold=True, color=COLOR['header_font'], size=10)
    cell.fill = PatternFill('solid', fgColor=COLOR['header_bg'])
    cell.alignment = Alignment(horizontal='center', vertical='center')
    cell.border = _border


def _num_fmt(cell, value, fmt='#,##0'):
    cell.value = value
    cell.number_format = fmt
    cell.alignment = Alignment(horizontal='right')
    cell.border = _border


def _change_style(cell, value):
    _num_fmt(cell, value, '+#,##0;-#,##0;0')
    if value is None or pd.isna(value):
        cell.value = None
        return
    if value > 0:
        cell.font = Font(color=COLOR['pos'], bold=True)
    elif value < 0:
        cell.font = Font(color=COLOR['neg'], bold=True)
    else:
        cell.font = Font(color=COLOR['neutral'])


def generate_excel(df: pd.DataFrame, campaigns: dict = None) -> bytes:
    """
    전체 인원 데이터를 받아 포맷된 Excel 파일을 bytes로 반환.
    campaigns: get_current_campaigns() 결과 dict (선택)
    """
    wb = Workbook()

    _build_daily_sheet(wb, df, campaigns)
    _build_summary_sheet(wb, df, campaigns)
    _build_trend_sheet(wb, df)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── 시트 1: 일별 상세 ──────────────────────────────────────────────

def _build_daily_sheet(wb, df, campaigns):
    ws = wb.active
    ws.title = '일별 상세'

    headers = ['날짜', '방 번호', '채팅방', '강의명', '상품', '총원', '전일', '증감']
    for col, h in enumerate(headers, 1):
        _header_style(ws.cell(row=1, column=col), h)

    ws.row_dimensions[1].height = 22
    ws.freeze_panes = 'A2'

    sorted_df = df.sort_values(['date', 'room_num'], ascending=[False, True])

    for r_idx, (_, row) in enumerate(sorted_df.iterrows(), 2):
        rn = int(row['room_num'])
        camp = (campaigns or {}).get(rn, {})
        fill = PatternFill('solid', fgColor=COLOR['row_even'] if r_idx % 2 == 0 else COLOR['row_odd'])

        def cell(col):
            c = ws.cell(row=r_idx, column=col)
            c.fill = fill
            return c

        c = cell(1); c.value = str(row['date']); c.alignment = Alignment(horizontal='center'); c.border = _border
        c = cell(2); c.value = rn; c.alignment = Alignment(horizontal='center'); c.border = _border
        c = cell(3); c.value = str(row['room_name']); c.alignment = Alignment(horizontal='left'); c.border = _border
        c = cell(4); c.value = camp.get('campaign_name', '-'); c.alignment = Alignment(horizontal='left'); c.border = _border
        c = cell(5); c.value = camp.get('product', '-'); c.alignment = Alignment(horizontal='center'); c.border = _border
        _num_fmt(cell(6), int(row['members']))
        prev = row['prev_members']
        _num_fmt(cell(7), int(prev) if not pd.isna(prev) else None)
        chg = row['change']
        _change_style(cell(8), int(chg) if not pd.isna(chg) else None)

    col_widths = [12, 8, 20, 20, 10, 10, 10, 10]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ── 시트 2: 날짜별 요약 ────────────────────────────────────────────

def _build_summary_sheet(wb, df, campaigns):
    ws = wb.create_sheet('날짜별 요약')

    if df.empty:
        ws.cell(row=1, column=1).value = '데이터 없음'
        return

    # 날짜별 총원 합계·증감 합계
    summary = (
        df.groupby('date')
        .agg(total_members=('members', 'sum'), net_change=('change', 'sum'))
        .reset_index()
        .sort_values('date', ascending=False)
    )

    headers = ['날짜', '전체 총원', '전일 대비 순증감']
    for col, h in enumerate(headers, 1):
        _header_style(ws.cell(row=1, column=col), h)

    ws.freeze_panes = 'A2'

    for r_idx, (_, row) in enumerate(summary.iterrows(), 2):
        ws.cell(row=r_idx, column=1).value = str(row['date'])
        ws.cell(row=r_idx, column=1).alignment = Alignment(horizontal='center')
        ws.cell(row=r_idx, column=1).border = _border
        _num_fmt(ws.cell(row=r_idx, column=2), int(row['total_members']))
        chg = row['net_change']
        _change_style(ws.cell(row=r_idx, column=3), int(chg) if not pd.isna(chg) else None)

    for i, w in enumerate([12, 14, 16], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # 막대 차트 삽입
    if len(summary) >= 2:
        chart = BarChart()
        chart.title = '날짜별 전체 총원'
        chart.style = 10
        chart.height = 12
        chart.width = 20

        data_ref = Reference(ws, min_col=2, min_row=1, max_row=len(summary) + 1)
        cats_ref = Reference(ws, min_col=1, min_row=2, max_row=len(summary) + 1)
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        ws.add_chart(chart, 'E2')


# ── 시트 3: 채팅방별 추이 ─────────────────────────────────────────

def _build_trend_sheet(wb, df):
    ws = wb.create_sheet('채팅방별 추이')

    if df.empty:
        ws.cell(row=1, column=1).value = '데이터 없음'
        return

    # 날짜 × 채팅방 피벗
    pivot = df.pivot_table(index='date', columns='room_num', values='members', aggfunc='first')
    pivot = pivot.sort_index(ascending=False)
    pivot.reset_index(inplace=True)

    # 헤더
    _header_style(ws.cell(row=1, column=1), '날짜')
    for col_idx, col_name in enumerate(pivot.columns[1:], 2):
        _header_style(ws.cell(row=1, column=col_idx), f'채팅방 {int(col_name)}')

    ws.freeze_panes = 'A2'

    for r_idx, (_, row) in enumerate(pivot.iterrows(), 2):
        ws.cell(row=r_idx, column=1).value = str(row['date'])
        ws.cell(row=r_idx, column=1).alignment = Alignment(horizontal='center')
        ws.cell(row=r_idx, column=1).border = _border
        for col_idx, col_name in enumerate(pivot.columns[1:], 2):
            val = row[col_name]
            _num_fmt(ws.cell(row=r_idx, column=col_idx),
                     int(val) if not pd.isna(val) else None)

    for i in range(1, len(pivot.columns) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 12
