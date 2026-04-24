import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def trend_line_chart(df: pd.DataFrame, room_nums: list = None):
    """방별 인원 추이 라인 차트."""
    if df.empty:
        return None

    plot_df = df.copy()
    if room_nums:
        plot_df = plot_df[plot_df['room_num'].isin(room_nums)]

    plot_df = plot_df.sort_values('date')
    plot_df['label'] = plot_df['room_num'].astype(str)

    fig = px.line(
        plot_df,
        x='date',
        y='members',
        color='label',
        markers=True,
        labels={'date': '날짜', 'members': '인원 수', 'label': '채팅방'},
        title='채팅방별 인원 추이',
    )
    fig.update_layout(
        hovermode='x unified',
        height=420,
        legend_title='채팅방',
        margin=dict(t=50, b=30),
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
    """날짜별 전체 총원 합계 막대 차트."""
    if df.empty:
        return None

    daily = df.groupby('date')['members'].sum().reset_index()
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
