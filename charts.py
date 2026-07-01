import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def trend_line_chart(df: pd.DataFrame, room_nums: list = None, targets: dict = None,
                     rooms: dict = None, ad_dates=None, content_dates=None):
    """방별 인원 추이 라인 차트.
    ad_dates: 광고 집행일 리스트 → 주황 점선 수직 오버레이
    content_dates: 콘텐츠 발행일 리스트 → 보라 점선 수직 오버레이
    """
    if df.empty:
        return None

    plot_df = df.copy()
    if room_nums:
        plot_df = plot_df[plot_df['room_num'].isin(room_nums)]

    plot_df = plot_df.sort_values('date')
    plot_df['label'] = plot_df['room_num'].apply(
        lambda x: (rooms or {}).get(int(x), f"채팅방 {x}")
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

    # 목표 인원 점선
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

    # 광고 집행일 수직선 (주황)
    if ad_dates:
        for d in sorted(set(str(d) for d in ad_dates)):
            fig.add_shape(
                type='line',
                x0=d, x1=d, y0=0, y1=1, yref='paper',
                line=dict(color='#ef6c00', dash='dash', width=1.2),
                opacity=0.45,
            )
        # 범례용 더미 트레이스
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='lines', name='광고 집행일',
            line=dict(color='#ef6c00', dash='dash', width=1.5),
            showlegend=True,
        ))

    # 콘텐츠 발행일 수직선 (보라)
    if content_dates:
        for d in sorted(set(str(d) for d in content_dates)):
            fig.add_shape(
                type='line',
                x0=d, x1=d, y0=0, y1=1, yref='paper',
                line=dict(color='#7b1fa2', dash='dot', width=1.2),
                opacity=0.45,
            )
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='lines', name='콘텐츠 발행일',
            line=dict(color='#7b1fa2', dash='dot', width=1.5),
            showlegend=True,
        ))

    fig.update_layout(
        hovermode='x unified',
        height=420,
        legend_title='채팅방',
        margin=dict(t=50, b=30, r=100),
    )
    return fig


def change_bar_chart(df_today: pd.DataFrame, rooms: dict = None):
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
    x_labels = df['room_num'].apply(lambda x: (rooms or {}).get(int(x), f"채팅방 {x}"))

    fig = go.Figure(go.Bar(
        x=x_labels,
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


def weekly_comparison_chart(df: pd.DataFrame, rooms: dict = None):
    """이번 주 vs 지난 주 채팅방별 인원 비교 막대 차트.
    정확히 7일 전 데이터가 없어도 5~9일 범위 내 가장 가까운 날짜를 사용한다."""
    if df.empty:
        return None

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    latest = df['date'].max()

    # 5~9일 전 범위에서 가장 최근 날짜를 기준일로 사용
    candidates = df['date'].unique()
    week_cands = [d for d in candidates
                  if pd.Timedelta('5 days') <= (latest - d) <= pd.Timedelta('9 days')]
    if not week_cands:
        return None
    week_ago = max(week_cands)

    df_now  = df[df['date'] == latest][['room_num', 'members']].rename(columns={'members': '이번'})
    df_prev = df[df['date'] == week_ago][['room_num', 'members']].rename(columns={'members': '지난주'})

    merged = pd.merge(df_now, df_prev, on='room_num', how='inner')
    if merged.empty:
        return None

    merged['diff'] = merged['이번'] - merged['지난주']
    merged = merged.sort_values('room_num')
    x_labels = merged['room_num'].apply(
        lambda x: (rooms or {}).get(int(x), f"채팅방 {x}")
    )

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


def churn_rate_chart(df: pd.DataFrame, rooms: dict = None, threshold: int = 5):
    """주간 채팅방별 이탈률 막대 차트. threshold 이상이면 빨간색.
    정확히 7일 전 데이터가 없어도 5~9일 범위 내 가장 가까운 날짜를 사용한다."""
    if df.empty:
        return None

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    latest = df['date'].max()

    candidates = df['date'].unique()
    week_cands = [d for d in candidates
                  if pd.Timedelta('5 days') <= (latest - d) <= pd.Timedelta('9 days')]
    if not week_cands:
        return None
    week_ago = max(week_cands)

    df_now  = df[df['date'] == latest][['room_num', 'members']].rename(columns={'members': 'now'})
    df_prev = df[df['date'] == week_ago][['room_num', 'members']].rename(columns={'members': 'prev'})
    merged  = pd.merge(df_now, df_prev, on='room_num', how='inner')
    if merged.empty:
        return None

    merged['churn'] = (merged['prev'] - merged['now']) / merged['prev'] * 100
    merged = merged[merged['churn'] > 0].sort_values('churn', ascending=False)
    if merged.empty:
        return None

    merged['label'] = merged['room_num'].apply(
        lambda x: (rooms or {}).get(int(x), f"채팅방 {x}")
    )
    colors = merged['churn'].apply(lambda x: '#c62828' if x >= threshold else '#ef6c00')

    fig = go.Figure(go.Bar(
        x=merged['label'],
        y=merged['churn'].round(1),
        marker_color=colors,
        text=merged['churn'].apply(lambda x: f"{x:.1f}%"),
        textposition='outside',
    ))
    fig.update_layout(
        title=f'주간 이탈률 ({week_ago.date()} → {latest.date()})',
        yaxis_title='이탈률 (%)',
        height=320,
        margin=dict(t=50, b=30),
        showlegend=False,
    )
    fig.add_hline(y=threshold, line_dash='dash', line_color='#c62828', opacity=0.5,
                  annotation_text=f'경고 기준 {threshold}%', annotation_position='right')
    return fig


def roi_chart(df_adspend: pd.DataFrame, df_conv: pd.DataFrame,
              campaigns: dict, rooms: dict = None):
    """채널별 ROAS·CPA 비교 차트."""
    if df_adspend.empty:
        return None

    # 채널별 광고비 합산
    by_channel = df_adspend.groupby('channel')['spend'].sum().reset_index()

    # 총 매출·수강확정 합산 (전환 데이터)
    total_revenue   = int(df_conv['revenue'].sum())   if not df_conv.empty else 0
    total_confirmed = int(df_conv['confirmed'].sum()) if not df_conv.empty else 0

    rows = []
    for _, row in by_channel.iterrows():
        spend = int(row['spend'])
        if spend == 0:
            continue
        # 채널별 매출 분리가 없으므로 전체 매출을 광고비 비율로 배분
        total_spend = int(by_channel['spend'].sum())
        alloc_rev   = round(total_revenue * spend / total_spend) if total_spend else 0
        alloc_conf  = round(total_confirmed * spend / total_spend) if total_spend else 0
        roas = round(alloc_rev / spend, 2) if spend else 0
        cpa  = round(spend / alloc_conf)   if alloc_conf else 0
        rows.append({'채널': row['channel'], '광고비': spend,
                     'ROAS': roas, 'CPA(원)': cpa})

    if not rows:
        return None

    df_r = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='광고비(원)', x=df_r['채널'], y=df_r['광고비'],
        marker_color='#78909c',
        text=df_r['광고비'].apply(lambda x: f"{x:,}"),
        textposition='outside',
        yaxis='y',
    ))
    fig.add_trace(go.Scatter(
        name='ROAS', x=df_r['채널'], y=df_r['ROAS'],
        mode='lines+markers+text',
        text=df_r['ROAS'].apply(lambda x: f"{x:.2f}x"),
        textposition='top center',
        yaxis='y2',
        line=dict(color='#1565c0', width=2),
        marker=dict(size=9),
    ))
    fig.update_layout(
        title='채널별 광고비 및 ROAS',
        barmode='group',
        height=360,
        margin=dict(t=50, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        yaxis=dict(title='광고비(원)'),
        yaxis2=dict(title='ROAS', overlaying='y', side='right', showgrid=False),
    )
    return fig


def cohort_conversion_chart(df_conv: pd.DataFrame, campaigns: dict, rooms: dict = None):
    """강의별(기수별) 신청자·수강확정·전환율 비교 차트.
    데이터가 있는 강의만 표시하며, 같은 상품끼리 정렬한다."""
    if df_conv.empty or not campaigns:
        return None

    rows = []
    for room_num, info in campaigns.items():
        sub = df_conv[df_conv['room_num'] == room_num]
        if sub.empty:
            continue
        latest = sub.sort_values('date').iloc[-1]
        applicants = int(latest['applicants'])
        confirmed  = int(latest['confirmed'])
        conv_rate  = round(confirmed / applicants * 100, 1) if applicants > 0 else 0
        product = info.get('product', '기타')
        cohort  = info.get('cohort', '-')
        label   = f"{product} {cohort}" if cohort not in ('-', '', None) \
                  else info.get('campaign_name', f'채팅방 {room_num}')
        rows.append({
            'label': label,
            'sort_key': f"{product}_{cohort}",
            '신청자': applicants,
            '수강확정': confirmed,
            '전환율': conv_rate,
        })

    if not rows:
        return None

    df_r = (pd.DataFrame(rows)
            .sort_values('sort_key')
            .drop(columns='sort_key')
            .reset_index(drop=True))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='신청자', x=df_r['label'], y=df_r['신청자'],
        marker_color='#b0bec5',
        text=df_r['신청자'], textposition='outside',
    ))
    fig.add_trace(go.Bar(
        name='수강확정', x=df_r['label'], y=df_r['수강확정'],
        marker_color='#1565c0',
        text=df_r['수강확정'], textposition='outside',
    ))
    fig.add_trace(go.Scatter(
        name='전환율(%)',
        x=df_r['label'], y=df_r['전환율'],
        mode='lines+markers+text',
        text=df_r['전환율'].apply(lambda v: f"{v:.1f}%"),
        textposition='top center',
        marker=dict(size=10, color='#e65100'),
        line=dict(color='#e65100', width=2, dash='dot'),
        yaxis='y2',
    ))
    fig.update_layout(
        title='강의별 신청·수강확정·전환율 비교',
        barmode='group',
        xaxis_title='강의',
        yaxis=dict(title='인원 수'),
        yaxis2=dict(
            title='전환율 (%)', overlaying='y', side='right',
            showgrid=False, range=[0, 115],
        ),
        height=380,
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


# ── 신규 분석 차트 ────────────────────────────────────────────────


def ranking_chart(df: pd.DataFrame, rooms: dict = None):
    """주간 TOP3 성장 / TOP3 감소 채팅방 랭킹 차트 (fig_top, fig_bot) 반환."""
    if df.empty:
        return None, None

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    latest = df['date'].max()

    candidates = df['date'].unique()
    week_cands = [d for d in candidates
                  if pd.Timedelta('5 days') <= (latest - d) <= pd.Timedelta('9 days')]
    if not week_cands:
        return None, None
    week_ago = max(week_cands)

    df_now  = df[df['date'] == latest][['room_num', 'members']].rename(columns={'members': 'now'})
    df_prev = df[df['date'] == week_ago][['room_num', 'members']].rename(columns={'members': 'prev'})
    merged  = pd.merge(df_now, df_prev, on='room_num', how='inner')
    if merged.empty:
        return None, None

    merged['diff'] = merged['now'] - merged['prev']
    merged['label'] = merged['room_num'].apply(
        lambda x: (rooms or {}).get(int(x), f"채팅방 {x}")
    )

    top3 = merged.nlargest(3, 'diff')
    top3 = top3[top3['diff'] != 0]
    fig_top = None
    if not top3.empty:
        fig_top = go.Figure(go.Bar(
            x=top3['label'],
            y=top3['diff'],
            text=top3['diff'].apply(lambda x: f'+{int(x):,}명' if x > 0 else f'{int(x):,}명'),
            textposition='outside',
            marker_color='#2e7d32',
        ))
        fig_top.update_layout(
            title=f'📈 주간 인원 증가 TOP 3 ({week_ago.date()} → {latest.date()})',
            yaxis_title='증가 인원',
            height=280, margin=dict(t=50, b=30), showlegend=False,
        )

    bot3 = merged.nsmallest(3, 'diff')
    bot3 = bot3[bot3['diff'] < 0]
    fig_bot = None
    if not bot3.empty:
        fig_bot = go.Figure(go.Bar(
            x=bot3['label'],
            y=bot3['diff'],
            text=bot3['diff'].apply(lambda x: f'{int(x):,}명'),
            textposition='outside',
            marker_color='#c62828',
        ))
        fig_bot.update_layout(
            title=f'📉 주간 인원 감소 TOP 3 ({week_ago.date()} → {latest.date()})',
            yaxis_title='감소 인원',
            height=280, margin=dict(t=50, b=30), showlegend=False,
        )

    return fig_top, fig_bot


def weekly_aggregate_chart(df: pd.DataFrame, rooms: dict = None):
    """주차별 채팅방 평균 인원 라인 차트."""
    if df.empty:
        return None

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['week'] = df['date'].dt.to_period('W').apply(lambda x: str(x.start_time.date()))
    df['room_num'] = df['room_num'].apply(lambda x: int(x))

    weekly = (df.groupby(['week', 'room_num'])['members']
                .mean()
                .round(0)
                .reset_index())
    weekly.columns = ['주차', 'room_num', '평균인원']
    weekly['채팅방'] = weekly['room_num'].apply(
        lambda x: (rooms or {}).get(x, f"채팅방 {x}")
    )

    fig = px.line(
        weekly, x='주차', y='평균인원', color='채팅방',
        markers=True,
        title='주차별 채팅방 평균 인원 추이',
        labels={'주차': '주차(시작일)', '평균인원': '평균 인원 수'},
    )
    fig.update_layout(
        height=400, hovermode='x unified',
        legend_title='채팅방',
        margin=dict(t=50, b=30, r=120),
    )
    return fig


def monthly_aggregate_chart(df: pd.DataFrame, rooms: dict = None):
    """월별 채팅방 인원 순증감 막대 차트."""
    if df.empty:
        return None

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M').astype(str)
    df['room_num'] = df['room_num'].apply(lambda x: int(x))

    monthly = (df.groupby(['month', 'room_num'])
                 .agg(first=('members', 'first'), last=('members', 'last'))
                 .reset_index())
    monthly['순증감'] = (monthly['last'] - monthly['first']).astype(int)
    monthly['채팅방'] = monthly['room_num'].apply(
        lambda x: (rooms or {}).get(x, f"채팅방 {x}")
    )

    fig = px.bar(
        monthly, x='month', y='순증감', color='채팅방',
        barmode='group',
        title='월별 채팅방 인원 순증감 (월 첫날 → 마지막날)',
        labels={'month': '월', '순증감': '인원 순증감'},
    )
    fig.add_hline(y=0, line_dash='dash', line_color='#bdbdbd', line_width=1)
    fig.update_layout(
        height=380,
        legend_title='채팅방',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        margin=dict(t=50, b=30),
    )
    return fig


def cpm_chart(df_members: pd.DataFrame, df_adspend: pd.DataFrame, rooms: dict = None):
    """채팅방별 인원 획득 단가 CPM 분석 차트 (광고비 ÷ 인원 순증가)."""
    if df_adspend.empty or df_members.empty:
        return None

    df_adspend = df_adspend.copy()
    df_members = df_members.copy()
    df_members['date'] = pd.to_datetime(df_members['date'])

    # 채팅방별 총 광고비
    if 'room_num' not in df_adspend.columns:
        return None
    room_spend = (df_adspend.groupby('room_num')['spend']
                             .sum()
                             .to_dict())
    if not room_spend:
        return None

    rows = []
    for rn, spend in room_spend.items():
        if spend <= 0:
            continue
        room_df = df_members[df_members['room_num'] == int(rn)].sort_values('date')
        if len(room_df) < 2:
            continue
        first_m = int(room_df['members'].iloc[0])
        last_m  = int(room_df['members'].iloc[-1])
        gain = last_m - first_m
        cpm  = round(spend / gain) if gain > 0 else None
        label = (rooms or {}).get(int(rn), f"채팅방 {rn}")
        rows.append({
            '채팅방': label,
            '광고비(원)': int(spend),
            '인원증가': gain,
            'CPM(원/명)': cpm,
        })

    if not rows:
        return None

    df_r = pd.DataFrame(rows)
    df_r = df_r[df_r['CPM(원/명)'].notna()].sort_values('CPM(원/명)')
    if df_r.empty:
        return None

    colors = df_r['CPM(원/명)'].apply(
        lambda x: '#2e7d32' if x <= 20000 else ('#ff8f00' if x <= 50000 else '#c62828')
    )

    fig = go.Figure(go.Bar(
        x=df_r['채팅방'],
        y=df_r['CPM(원/명)'],
        marker_color=colors,
        text=df_r['CPM(원/명)'].apply(lambda x: f'{int(x):,}원'),
        textposition='outside',
        customdata=df_r[['광고비(원)', '인원증가']].values,
        hovertemplate=(
            '<b>%{x}</b><br>'
            'CPM: %{y:,}원/명<br>'
            '광고비: %{customdata[0]:,}원<br>'
            '인원증가: %{customdata[1]:,}명<extra></extra>'
        ),
    ))
    fig.add_hline(y=20000, line_dash='dot', line_color='#2e7d32', opacity=0.5,
                  annotation_text='우수 기준 2만원', annotation_position='right')
    fig.add_hline(y=50000, line_dash='dot', line_color='#c62828', opacity=0.5,
                  annotation_text='주의 기준 5만원', annotation_position='right')
    fig.update_layout(
        title='채팅방별 인원 획득 단가 (CPM = 광고비 ÷ 인원 순증가)',
        yaxis_title='1인당 획득 단가 (원)',
        height=340,
        margin=dict(t=50, b=30, r=130),
        showlegend=False,
    )
    return fig


def content_impact_table(df_members: pd.DataFrame,
                          df_content: pd.DataFrame) -> pd.DataFrame:
    """콘텐츠 발행 후 전체 총원 변화 상관관계 테이블 반환."""
    if df_content.empty or df_members.empty:
        return pd.DataFrame()

    df_m = df_members.copy()
    df_m['date'] = pd.to_datetime(df_m['date']).dt.date
    daily_total = df_m.groupby('date')['members'].sum().to_dict()

    rows = []
    for _, row in df_content.iterrows():
        try:
            pub_date = pd.to_datetime(row['date']).date()
        except Exception:
            continue
        t0 = daily_total.get(pub_date)

        changes = {}
        for days in [1, 3, 7]:
            import datetime
            target = pub_date + datetime.timedelta(days=days)
            t_val = daily_total.get(target)
            changes[f'+{days}일'] = (int(t_val - t0) if t0 is not None and t_val is not None else None)

        rows.append({
            '발행일': str(pub_date),
            '채널': str(row.get('channel', '-')),
            '유형': str(row.get('content_type', '-')),
            '제목': str(row.get('title', '-'))[:30],
            '+1일 총원변화': changes['+1일'],
            '+3일 총원변화': changes['+3일'],
            '+7일 총원변화': changes['+7일'],
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values('발행일', ascending=False).reset_index(drop=True)


def trend_forecast_chart(df: pd.DataFrame, room_nums: list = None,
                          rooms: dict = None, forecast_days: int = 7):
    """최근 21일 데이터 기반 선형 회귀 인원 예측 차트."""
    import numpy as np

    if df.empty:
        return None

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])

    if room_nums:
        df = df[df['room_num'].isin(room_nums)]

    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    has_data = False

    for idx, rn in enumerate(sorted(df['room_num'].unique())):
        room_df = df[df['room_num'] == rn].sort_values('date').tail(21)
        if len(room_df) < 5:
            continue

        label = (rooms or {}).get(int(rn), f"채팅방 {rn}")
        color = colors[idx % len(colors)]

        dates   = room_df['date'].values
        members = room_df['members'].values.astype(float)
        x_num   = np.arange(len(dates))

        try:
            coeffs = np.polyfit(x_num, members, 1)
        except Exception:
            continue

        future_x     = np.arange(len(dates), len(dates) + forecast_days)
        last_date    = room_df['date'].max()
        future_dates = [last_date + pd.Timedelta(days=i + 1) for i in range(forecast_days)]
        future_y     = np.polyval(coeffs, future_x).clip(0).round(0).astype(int)

        fig.add_trace(go.Scatter(
            x=room_df['date'], y=room_df['members'].astype(int),
            name=label, mode='lines+markers',
            line=dict(color=color),
            hovertemplate=f'<b>{label}</b><br>%{{x|%Y-%m-%d}}<br>%{{y:,}}명<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=[last_date] + future_dates,
            y=[int(members[-1])] + list(future_y),
            name=f'{label} 예측',
            mode='lines',
            line=dict(color=color, dash='dot', width=2),
            showlegend=True,
            hovertemplate=f'<b>{label} 예측</b><br>%{{x|%Y-%m-%d}}<br>%{{y:,}}명<extra></extra>',
        ))
        has_data = True

    if not has_data:
        return None

    fig.add_vline(
        x=str(df['date'].max().date()),
        line_dash='dash', line_color='#9e9e9e', line_width=1.5,
        annotation_text='오늘', annotation_position='top left',
    )
    fig.update_layout(
        title=f'인원 예측 — 최근 21일 추세 기반 {forecast_days}일 예측 (선형 회귀)',
        xaxis_title='날짜',
        yaxis_title='인원 수',
        hovermode='x unified',
        height=440,
        margin=dict(t=55, b=30, r=120),
        legend_title='채팅방',
        legend=dict(orientation='v'),
    )
    return fig
