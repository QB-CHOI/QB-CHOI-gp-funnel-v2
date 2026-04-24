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
