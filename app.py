"""
US Economic Historical Dashboard (with caching, no descriptions, env port)

Description:
    - A Flask-based web application that fetches historical economic data from the FRED API.
    - Uses Plotly (Express and Graph Objects) to generate interactive charts.
    - Displays key metrics and charts for several U.S. economic indicators.
    - Provides a dual-axis comparison chart (GDP vs. CPI).
    - Implements an in-memory cache to reduce repeated FRED API calls.
    - Binds to a port from the PORT environment variable (or 5000 by default).
"""

import os
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

# ------------------------
# Caching Setup
# ------------------------
cached_data = {}  # Cache keyed by (series_id, start_date, end_date).

# Default start and end dates.
DEFAULT_START = "1900-01-01"
DEFAULT_END = datetime.today().strftime('%Y-%m-%d')

# Custom start dates for specific series.
CUSTOM_START_DATES = {
    "CPIAUCSL": "2006-01-01",  # Consumer Price Index starts Jan 2006.
    "INDPRO":   "1997-09-01"   # Industrial Production starts Sept 1997.
}

# Special start date for the dual-axis chart (GDP vs. CPI).
DUAL_START_DATE = "1947-04-01"  # April 1947.

def get_fred_data(series_id, start_date, end_date):
    """
    Fetch data from FRED for the given series_id between start_date and end_date,
    caching the results in-memory to reduce repeated calls.
    """
    cache_key = (series_id, start_date, end_date)
    if cache_key in cached_data:
        print(f"Using cached data for {series_id}")
        return cached_data[cache_key]

    today_str = datetime.today().strftime('%Y-%m-%d')
    today = datetime.strptime(today_str, '%Y-%m-%d')
    desired_end = datetime.strptime(end_date, '%Y-%m-%d')
    realtime_end = "9999-12-31" if desired_end >= today else today_str

    url = (
        f'https://api.stlouisfed.org/fred/series/observations?'
        f'series_id={series_id}&api_key=3baa2dc8f0187695b947741bb81a4673'
        f'&file_type=json&observation_start={start_date}&observation_end={end_date}'
        f'&realtime_start={start_date}&realtime_end={realtime_end}'
    )
    print(f"\nFetching data for {series_id}:\n{url}\n")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching {series_id}: {response.status_code} - {response.text}")
        df = pd.DataFrame()
        cached_data[cache_key] = df
        return df

    data = response.json()
    if "error_message" in data:
        print(f"Error in response for {series_id}: {data['error_message']}")
        df = pd.DataFrame()
        cached_data[cache_key] = df
        return df

    observations = data.get('observations', [])
    df = pd.DataFrame(observations)
    if df.empty:
        print(f"Warning: No data returned for {series_id}")
        cached_data[cache_key] = df
        return df

    df['date'] = pd.to_datetime(df['date'])
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df.dropna(subset=['value'], inplace=True)
    df = df.groupby('date', as_index=False)['value'].last().sort_values('date')
    print(f"{series_id} date range: {df['date'].min()} to {df['date'].max()} | Rows: {len(df)}")
    cached_data[cache_key] = df
    return df

def create_figures(end_date):
    figs = {}

    # 1. UNRATE: Unemployment Rate
    df_unrate = get_fred_data('UNRATE', DEFAULT_START, end_date)
    fig_unrate = px.line(
        df_unrate,
        x='date',
        y='value',
        title='US Unemployment Rate',
        labels={'date': 'Date', 'value': 'Unemployment Rate (%)'},
        markers=True,
        color_discrete_sequence=['#636EFA']
    )
    if not df_unrate.empty:
        fig_unrate.update_layout(xaxis=dict(range=[df_unrate['date'].min(), df_unrate['date'].max()]))
    figs['unrate'] = fig_unrate

    # 2. GDPC1: Real GDP (converted from billions to trillions)
    df_gdp = get_fred_data('GDPC1', DEFAULT_START, end_date)
    if not df_gdp.empty:
        df_gdp['value'] = df_gdp['value'] / 1000  # Now in trillions.
    fig_gdp = px.line(
        df_gdp,
        x='date',
        y='value',
        title='US Real GDP (Trillions)',
        labels={'date': 'Date', 'value': 'Real GDP (Trillions)'},
        markers=True,
        color_discrete_sequence=['#EF553B']
    )
    if not df_gdp.empty:
        fig_gdp.update_layout(xaxis=dict(range=[df_gdp['date'].min(), df_gdp['date'].max()]))
    figs['gdp'] = fig_gdp

    # 3. CPIAUCSL: Consumer Price Index (custom start: Jan 2006)
    cpi_start = CUSTOM_START_DATES.get("CPIAUCSL", DEFAULT_START)
    df_cpi = get_fred_data('CPIAUCSL', cpi_start, end_date)
    fig_cpi = px.area(
        df_cpi,
        x='date',
        y='value',
        title='US Consumer Price Index',
        labels={'date': 'Date', 'value': 'CPI (Index)'},
        color_discrete_sequence=['#00CC96']
    )
    if not df_cpi.empty:
        max_cpi = df_cpi['value'].max()
        fig_cpi.update_layout(
            xaxis=dict(range=[df_cpi['date'].min(), df_cpi['date'].max()]),
            yaxis=dict(range=[200, max_cpi + 10])
        )
    figs['cpi'] = fig_cpi

    # 4. FEDFUNDS: Federal Funds Rate
    df_fed = get_fred_data('FEDFUNDS', DEFAULT_START, end_date)
    fig_fed = px.line(
        df_fed,
        x='date',
        y='value',
        title='Federal Funds Rate',
        labels={'date': 'Date', 'value': 'Federal Funds Rate (%)'},
        markers=True,
        color_discrete_sequence=['#AB63FA']
    )
    if not df_fed.empty:
        fig_fed.update_layout(xaxis=dict(range=[df_fed['date'].min(), df_fed['date'].max()]))
    figs['fed'] = fig_fed

    # 5. INDPRO: Industrial Production (custom start: Sept 1997)
    indpro_start = CUSTOM_START_DATES.get("INDPRO", DEFAULT_START)
    df_indpro = get_fred_data('INDPRO', indpro_start, end_date)
    # Changed chart type to line chart for better mobile responsiveness and color updated
    fig_indpro = px.line(
        df_indpro,
        x='date',
        y='value',
        title='US Industrial Production Index',
        labels={'date': 'Date', 'value': 'Industrial Production Index'},
        markers=True,
        color_discrete_sequence=['#2F4F4F']  # Dark Slate Gray
    )
    if not df_indpro.empty:
        max_indpro = df_indpro['value'].max()
        fig_indpro.update_layout(
            xaxis=dict(range=[df_indpro['date'].min(), df_indpro['date'].max()]),
            yaxis=dict(range=[80, max_indpro + 5])
        )
    figs['indpro'] = fig_indpro

    # 6. PCE: Personal Consumption Expenditures
    df_pce = get_fred_data('PCE', DEFAULT_START, end_date)
    fig_pce = px.line(
        df_pce,
        x='date',
        y='value',
        title='US Personal Consumption Expenditures',
        labels={'date': 'Date', 'value': 'PCE (Billions)'},
        markers=True,
        color_discrete_sequence=['#19D3F3']
    )
    if not df_pce.empty:
        fig_pce.update_layout(xaxis=dict(range=[df_pce['date'].min(), df_pce['date'].max()]))
    figs['pce'] = fig_pce

    # 7. M2SL: M2 Money Stock
    df_m2 = get_fred_data('M2SL', DEFAULT_START, end_date)
    fig_m2 = px.scatter(
        df_m2,
        x='date',
        y='value',
        title='US M2 Money Stock',
        labels={'date': 'Date', 'value': 'M2 (Billions)'},
        trendline=None,
        color_discrete_sequence=['#FF6692']
    )
    if not df_m2.empty:
        fig_m2.update_layout(xaxis=dict(range=[df_m2['date'].min(), df_m2['date'].max()]))
    figs['m2'] = fig_m2

    # 8. Dual-Axis: GDP vs. CPI (custom start: April 1947)
    df_gdp_dual = get_fred_data('GDPC1', DUAL_START_DATE, end_date)
    df_cpi_dual = get_fred_data('CPIAUCSL', DUAL_START_DATE, end_date)
    df_gdp_q = df_gdp_dual.copy()
    df_gdp_q['quarter'] = df_gdp_q['date'].dt.to_period('Q')
    df_gdp_q = df_gdp_q.groupby('quarter', as_index=False)['value'].last()
    df_gdp_q['date'] = df_gdp_q['quarter'].dt.to_timestamp(how='end')
    df_gdp_q.drop(columns='quarter', inplace=True)
    df_gdp_q.rename(columns={'value': 'gdp'}, inplace=True)
    df_gdp_q['gdp'] = df_gdp_q['gdp'] / 1000  # Convert to trillions

    df_cpi_q = df_cpi_dual.copy()
    df_cpi_q['quarter'] = df_cpi_q['date'].dt.to_period('Q')
    df_cpi_q = df_cpi_q.groupby('quarter', as_index=False)['value'].mean()
    df_cpi_q['date'] = df_cpi_q['quarter'].dt.to_timestamp(how='end')
    df_cpi_q.drop(columns='quarter', inplace=True)
    df_cpi_q.rename(columns={'value': 'cpi'}, inplace=True)

    df_dual = pd.merge(df_gdp_q, df_cpi_q, on='date', how='outer')
    df_dual.dropna(subset=['gdp', 'cpi'], how='all', inplace=True)
    if df_dual.empty:
        fig_dual = go.Figure()
        fig_dual.update_layout(title='GDP vs. CPI: No Overlapping Data')
    else:
        fig_dual = go.Figure()
        fig_dual.add_trace(go.Scatter(
            x=df_dual['date'],
            y=df_dual['gdp'],
            mode='lines+markers',
            name='GDP',
            line=dict(color='#EF553B')
        ))
        fig_dual.add_trace(go.Scatter(
            x=df_dual['date'],
            y=df_dual['cpi'],
            mode='lines+markers',
            name='CPI',
            yaxis='y2',
            line=dict(color='#00CC96')
        ))
        fig_dual.update_layout(
            title='GDP vs. CPI',
            xaxis_title='Date',
            yaxis=dict(title='GDP (Trillions)'),
            yaxis2=dict(title='CPI (Index)', overlaying='y', side='right')
        )
    figs['dual'] = fig_dual

    return figs

@app.route('/')
def dashboard():
    figs = create_figures(DEFAULT_END)
    figs_html = {name: fig.to_html(full_html=False, include_plotlyjs='cdn')
                 for name, fig in figs.items()}

    # Pull fresh data for single-value metrics
    df_unrate = get_fred_data('UNRATE', DEFAULT_START, DEFAULT_END)
    df_gdp    = get_fred_data('GDPC1', DEFAULT_START, DEFAULT_END)
    df_cpi    = get_fred_data('CPIAUCSL', CUSTOM_START_DATES.get("CPIAUCSL", DEFAULT_START), DEFAULT_END)
    df_fed    = get_fred_data('FEDFUNDS', DEFAULT_START, DEFAULT_END)
    df_m2     = get_fred_data('M2SL', DEFAULT_START, DEFAULT_END)
    df_indpro = get_fred_data('INDPRO', CUSTOM_START_DATES.get("INDPRO", DEFAULT_START), DEFAULT_END)

    metrics = {}

    if not df_unrate.empty:
        metrics['Unemployment Rate'] = f"{df_unrate.iloc[-1]['value']:.1f}%"

    if not df_gdp.empty:
        # GDP is already scaled to trillions in create_figures()
        metrics['Real GDP'] = f"${df_gdp.iloc[-1]['value']:,.1f}T"

    if not df_cpi.empty:
        metrics['CPI'] = f"{df_cpi.iloc[-1]['value']:.1f}"

    if not df_fed.empty:
        metrics['Fed Funds Rate'] = f"{df_fed.iloc[-1]['value']:.2f}%"

    if not df_m2.empty:
        # Convert M2 from billions to trillions for display
        metrics['M2 Money Stock'] = f"${df_m2.iloc[-1]['value'] / 1000:,.1f}T"

    if not df_indpro.empty:
        metrics['Industrial Production'] = f"{df_indpro.iloc[-1]['value']:.1f}"

    return render_template('dashboard.html', figs_html=figs_html, metrics=metrics)

# In production, run with a WSGI server like Gunicorn (e.g., gunicorn app:app)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Turn off debug mode for production
    app.run(host='0.0.0.0', port=port)
