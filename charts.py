import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def trend_line_chart(df: pd.DataFrame, room_nums: list = None, targets: dict = None):
    """방별 인원 추이 라인 차트. targets: {room_num: target_count}"""
    if df.empty:
        return None

    plot_df = df.copy()
    if room_nums:
        plot_df = plot_df[plot_df['room_num'].isin(room_nums)]

    plot_df = plot_df.sort_values('date')
    plot_df['label'] = plot_df['room_num'].apply(
        lambda x: str(x)
    )

    fig = px.line(
        plot_df,
        x='date',
        y='members',
        color='label',
        markers=True,
        labels={'date': '날짜', 'members': '인원 수', 'label': '채팅방'},
        title='채팅방별 인원 추이',
    )

    # 목표 인원 점선 추가
    if targets:
        for room_num, target in targets.items():
            if target and target > 0:
                fig.add_hline(
                    y=target,
                    line_dash='dot',
                    line_color='#e53935',
                    opacity=0.6,
                    annotation_text=f"목표 {target:,}명",
                    annotation_position='right',
                )

    fig.update_layout(
        hovermode='x unified',
        height=420,
        legend_title='채팅방',
        margin=dict(t=50, b=30, r=100),
    )
    return fig


def change_bar_chart(df_today: pd.DataFrame):
    """전일 대비 증감 막대 차트."""
    if df_today.empty:
        return None

    df = df_today.dropna(subset=['change']).copy()
    if df.empty:
        return None

    df = df.sort_values('room_num')
    colors = df['change'].apply(
        lambda x: '#2e7d32' if x > 0 else ('#c62828' if x < 0 else '#9e9e9e')
    )
    text_labels = df['change'].apply(lambda x: f'+{int(x)}' if x > 0 else str(int(x)))

    fig = go.Figure(go.Bar(
        x=df['room_num'].astype(str),
        y=df['change'],
        marker_color=colors,
        text=text_labels,
        textposition='outside',
    ))
    fig.update_layout(
        title='전일 대비 증감',
        xaxis_title='채팅방',
        yaxis_title='인원 증감',
        height=320,
        margin=dict(t=50, b=30),
        showlegend=False,
    )
    fig.add_hline(y=0, line_dash='dash', line_color='#bdbdbd', line_width=1)
    return fig


def total_trend_bar(df: pd.DataFrame):
    """날짜별 전체 총원 합계 막대 차트 — carry-forward 적용."""
    if df.empty:
        return None

    # 날짜 × 방 전체 조합으로 pivot 후 누락된 방은 직전값으로 채움
    df_pivot = (
        df.pivot_table(index='date', columns='room_num', values='members', aggfunc='last')
          .sort_index()
          .ffill()
    )
    daily = df_pivot.sum(axis=1).reset_index()
    daily.columns = ['date', 'total']
    daily = daily.sort_values('date')

    fig = px.bar(
        daily,
        x='date',
        y='total',
        text='total',
        labels={'date': '날짜', 'total': '전체 인원'},
        title='전체 총원 합계 추이',
        color_discrete_sequence=['#1565c0'],
    )
    fig.update_traces(texttemplate='%{text:,}', textposition='outside')
    fig.update_layout(height=320, margin=dict(t=50, b=30))
    return fig


def product_bar_chart(df: pd.DataFrame, campaigns: dict):
    """상품별(사주·타로·부동산·빌딩) 총원 합계 비교 막대 차트."""
    if df.empty or not campaigns:
        return None

    latest_date = df['date'].max()
    df_today = df[df['date'] == latest_date].copy()

    df_today['product'] = df_today['room_num'].apply(
        lambda rn: campaigns.get(int(rn), {}).get('product', '미분류')
    )

    by_product = df_today.groupby('product')['members'].sum().reset_index()
    by_product.columns = ['상품', '총원']
    by_product = by_product.sort_values('총원', ascending=False)

    color_map = {
        '사주':   '#5c6bc0',
        '타로':   '#ec407a',
        '부동산': '#26a69a',
        '빌딩':   '#ff7043',
        '기타':   '#9e9e9e',
        '미분류': '#bdbdbd',
    }
    colors = [color_map.get(p, '#90a4ae') for p in by_product['상품']]

    fig = go.Figure(go.Bar(
        x=by_product['상품'],
        y=by_product['총원'],
        marker_color=colors,
        text=by_product['총원'].apply(lambda x: f'{int(x):,}'),
        textposition='outside',
    ))
    fig.update_layout(
        title=f'상품별 총원 현황 ({latest_date})',
        xaxis_title='상품',
        yaxis_title='총원',
        height=320,
        margin=dict(t=50, b=30),
        showlegend=False,
    )
    return fig


def weekly_comparison_chart(df: pd.DataFrame):
    """이번 주 vs 지난 주 채팅방별 인원 비교 막대 차트."""
    if df.empty:
        return None

    import datetime
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    latest = df['date'].max()
    week_ago = latest - datetime.timedelta(days=7)

    df_now = df[df['date'] == latest][['room_num', 'members']].rename(columns={'members': '이번'})
    df_prev = df[df['date'] == week_ago][['room_num', 'members']].rename(columns={'members': '지난주'})

    merged = pd.merge(df_now, df_prev, on='room_num', how='inner')
    if merged.empty:
        return None

    merged['diff'] = merged['이번'] - merged['지난주']
    merged = merged.sort_values('room_num')
    x_labels = merged['room_num'].astype(str)

    fig = go.Figure()
    fig.add_trace(go.Bar(name='지난주', x=x_labels, y=merged['지난주'],
                         marker_color='#b0bec5'))
    fig.add_trace(go.Bar(name='이번주', x=x_labels, y=merged['이번'],
                         marker_color='#1565c0'))
    fig.update_layout(
        title=f'주간 비교 ({week_ago.date()} vs {latest.date()})',
        barmode='group',
        xaxis_title='채팅방',
        yaxis_title='인원 수',
        height=360,
        margin=dict(t=50, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    return fig


def funnel_chart(df_members: pd.DataFrame, df_conv: pd.DataFrame,
                 campaigns: dict, rooms: dict = None):
    """강의별 모객 퍼널 — 채팅방 인원 → 신청자 → 수강 확정."""
    if df_members.empty or not campaigns:
        return None

    latest_date = df_members['date'].max()
    df_today = df_members[df_members['date'] == latest_date]

    rows = []
    for room_num, info in sorted(campaigns.items()):
        label = (rooms or {}).get(room_num, f"채팅방 {room_num}")
        members_row = df_today[df_today['room_num'] == room_num]
        members = int(members_row['members'].values[0]) if not members_row.empty else 0

        if not df_conv.empty:
            conv_row = df_conv[df_conv['room_num'] == room_num].sort_values('date')
            applicants = int(conv_row['applicants'].values[-1]) if not conv_row.empty else 0
            confirmed  = int(conv_row['confirmed'].values[-1])  if not conv_row.empty else 0
        else:
            applicants, confirmed = 0, 0

        if members == 0 and applicants == 0:
            continue
        rows.append({'label': label, 'members': members,
                     'applicants': applicants, 'confirmed': confirmed})

    if not rows:
        return None

    colors = ['#1565c0', '#2e7d32', '#e65100']
    stages = [('채팅방 인원', 'members'), ('신청자', 'applicants'), ('수강 확정', 'confirmed')]

    fig = go.Figure()
    for (stage_name, key), color in zip(stages, colors):
        fig.add_trace(go.Bar(
            name=stage_name,
            x=[r['label'] for r in rows],
            y=[r[key] for r in rows],
            marker_color=color,
            text=[f"{r[key]:,}" if r[key] > 0 else '-' for r in rows],
            textposition='outside',
        ))

    fig.update_layout(
        title='강의별 모객 퍼널 (채팅방 인원 → 신청 → 수강)',
        barmode='group',
        xaxis_title='채팅방',
        yaxis_title='인원',
        height=400,
        margin=dict(t=50, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    return fig


def conversion_rate_chart(df_conv: pd.DataFrame, campaigns: dict, rooms: dict = None):
    """강의별 수강 전환율 비교 차트 (신청자 vs 수강확정 + 전환율%)."""
    if df_conv.empty or not campaigns:
        return None

    rows = []
    for room_num in sorted(campaigns.keys()):
        label = (rooms or {}).get(room_num, f"채팅방 {room_num}")
        conv_row = df_conv[df_conv['room_num'] == room_num]
        if conv_row.empty:
            continue
        last = conv_row.sort_values('date').iloc[-1]
        applicants = int(last['applicants'])
        confirmed  = int(last['confirmed'])
        conv_rate  = round(confirmed / applicants * 100, 1) if applicants > 0 else 0
        rows.append({'label': label, '신청자': applicants,
                     '수강확정': confirmed, '수강전환율(%)': conv_rate})

    if not rows:
        return None

    df = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='신청자', x=df['label'], y=df['신청자'],
        marker_color='#1976d2',
        text=df['신청자'].apply(lambda x: f"{x:,}"),
        textposition='outside',
    ))
    fig.add_trace(go.Bar(
        name='수강 확정', x=df['label'], y=df['수강확정'],
        marker_color='#388e3c',
        text=df['수강확정'].apply(lambda x: f"{x:,}"),
        textposition='outside',
    ))
    fig.add_trace(go.Scatter(
        name='수강전환율(%)', x=df['label'], y=df['수강전환율(%)'],
        mode='lines+markers+text',
        text=df['수강전환율(%)'].apply(lambda x: f"{x}%"),
        textposition='top center',
        yaxis='y2',
        line=dict(color='#e65100', width=2),
        marker=dict(size=8),
    ))
    fig.update_layout(
        title='강의별 신청·수강 전환 현황',
        barmode='group',
        height=380,
        margin=dict(t=50, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        yaxis=dict(title='인원'),
        yaxis2=dict(title='수강전환율(%)', overlaying='y', side='right',
                    range=[0, 100], showgrid=False),
    )
    return fig


def cohort_trend_chart(df: pd.DataFrame, campaigns: dict, rooms: dict = None, mode: str = '절대값'):
    """강의 시작일(D+0) 기준 모객 곡선 비교 차트.
    mode: '절대값' | '순증감' — D+0 대비 증감 인원
    """
    if df.empty or not campaigns:
        return None

    import datetime
    df = df.copy()
    df['date'] = pd.to_datetime(df['date']).dt.date

    traces = []
    for room_num, info in sorted(campaigns.items()):
        start_str = info.get('start_date', '')
        if not start_str:
            continue
        try:
            start = pd.to_datetime(start_str).date()
        except Exception:
            continue

        room_df = df[df['room_num'] == room_num].copy()
        room_df = room_df[room_df['date'] >= start].sort_values('date')
        if room_df.empty:
            continue

        room_df['day'] = room_df['date'].apply(lambda d: (d - start).days)

        label = info.get('campaign_name', f'채팅방 {room_num}')
        if rooms:
            label = f"{rooms.get(room_num, f'채팅방 {room_num}')} · {info.get('campaign_name', '')}"

        if mode == '순증감':
            base = room_df['members'].iloc[0]
            room_df['y'] = room_df['members'] - base
        else:
            room_df['y'] = room_df['members']

        traces.append(go.Scatter(
            x=room_df['day'],
            y=room_df['y'],
            mode='lines+markers',
            name=label,
            hovertemplate=f'<b>{label}</b><br>D+%{{x}}일<br>{"인원" if mode == "절대값" else "증감"}: %{{y:,}}명<extra></extra>',
        ))

    if not traces:
        return None

    y_title = '인원 수' if mode == '절대값' else 'D+0 대비 증감 인원'
    fig = go.Figure(traces)
    fig.update_layout(
        title=f'강의별 모객 곡선 비교 (D+N일 기준) — {mode}',
        xaxis_title='모객 시작 후 경과일 (D+N)',
        yaxis_title=y_title,
        hovermode='x unified',
        height=420,
        margin=dict(t=50, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    fig.add_vline(x=0, line_dash='dash', line_color='#bdbdbd', line_width=1)
    return fig
