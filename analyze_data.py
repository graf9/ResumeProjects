"""
analyze_data.py

Fetch multiple FRED series directly from the API and generate local Plotly charts.
This does NOT use the SQLite database; it just downloads data on the fly.
"""
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

API_KEY = '3baa2dc8f0187695b947741bb81a4673'
start_date = '2010-01-01'
end_date = datetime.today().strftime('%Y-%m-%d')

def get_fred_data(series_id):
    """Fetch raw data from FRED (no extra frequency/aggregation)."""
    url = (
        f'https://api.stlouisfed.org/fred/series/observations?'
        f'series_id={series_id}&api_key={API_KEY}&file_type=json&'
        f'observation_start={start_date}&observation_end={end_date}'
    )
    response = requests.get(url)
    data = response.json()
    observations = data.get('observations', [])
    df = pd.DataFrame(observations)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
    return df

# 1. Unemployment Rate (UNRATE)
df_unrate = get_fred_data('UNRATE')
fig1 = px.line(df_unrate, x='date', y='value',
               title='US Unemployment Rate Over Time',
               labels={'date': 'Date', 'value': 'Unemployment Rate (%)'})
fig1.show()

# 2. Real GDP (GDPC1)
df_gdp = get_fred_data('GDPC1')
fig2 = px.line(df_gdp, x='date', y='value',
               title='US Real GDP Over Time',
               labels={'date': 'Date', 'value': 'Real GDP (Billions of Chained 2012 Dollars)'},
               markers=True)
fig2.show()

# 3. Consumer Price Index (CPIAUCSL)
df_cpi = get_fred_data('CPIAUCSL')
fig3 = px.area(df_cpi, x='date', y='value',
               title='US Consumer Price Index Over Time',
               labels={'date': 'Date', 'value': 'CPI (Index)'})
fig3.show()

# 4. Federal Funds Rate (FEDFUNDS)
df_fed = get_fred_data('FEDFUNDS')
fig4 = px.line(df_fed, x='date', y='value',
               title='Federal Funds Rate Over Time',
               labels={'date': 'Date', 'value': 'Federal Funds Rate (%)'},
               markers=True)
fig4.show()

# 5. Industrial Production Index (INDPRO)
df_indpro = get_fred_data('INDPRO')
fig5 = px.bar(df_indpro, x='date', y='value',
              title='US Industrial Production Index Over Time',
              labels={'date': 'Date', 'value': 'Industrial Production Index'})
fig5.show()

# 6. Personal Consumption Expenditures (PCE)
df_pce = get_fred_data('PCE')
fig6 = px.line(df_pce, x='date', y='value',
               title='US Personal Consumption Expenditures Over Time',
               labels={'date': 'Date', 'value': 'PCE (Billions of Dollars)'},
               markers=True)
fig6.show()

# 7. M2 Money Stock (M2SL)
df_m2 = get_fred_data('M2SL')
fig7 = px.scatter(df_m2, x='date', y='value',
                  title='US M2 Money Stock Over Time with Trendline',
                  labels={'date': 'Date', 'value': 'M2 Money Stock (Billions)'},
                  trendline='ols')
fig7.show()

# 8. Dual-Axis Chart: GDP vs. CPI
df_gdp_subset = df_gdp[['date', 'value']].rename(columns={'value':'gdp'})
df_cpi_subset = df_cpi[['date', 'value']].rename(columns={'value':'cpi'})
df_combined = pd.merge(df_gdp_subset, df_cpi_subset, on='date', how='inner')

fig8 = go.Figure()
fig8.add_trace(go.Scatter(
    x=df_combined['date'],
    y=df_combined['gdp'],
    mode='lines',
    name='Real GDP'
))
fig8.add_trace(go.Scatter(
    x=df_combined['date'],
    y=df_combined['cpi'],
    mode='lines',
    name='CPI',
    yaxis='y2'
))
fig8.update_layout(
    title="Comparison of US Real GDP and CPI Over Time",
    xaxis_title="Date",
    yaxis=dict(title="Real GDP (Billions)"),
    yaxis2=dict(title="CPI (Index)", overlaying='y', side='right')
)
fig8.show()
