import requests
import pandas as pd
import plotly.graph_objects as go
from flask import Flask, render_template
from datetime import datetime, timedelta
from statsmodels.tsa.holtwinters import ExponentialSmoothing

app = Flask(__name__)

# Define FRED series IDs
FRED_SERIES = {
    "GDP": "GDPC1",
    "CPI": "CPIAUCSL",
    "Unemployment Rate": "UNRATE",
    "PCE": "PCE"
}

FRED_API_KEY = '3baa2dc8f0187695b947741bb81a4673'

# Function to fetch data from FRED API
def get_fred_data(series_id, start_date=None, end_date=datetime.today().strftime('%Y-%m-%d')):
    if not start_date:
        start_date = (datetime.today() - timedelta(days=5 * 365)).strftime('%Y-%m-%d')  # Last 15 years

    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&observation_start={start_date}&observation_end={end_date}"
    response = requests.get(url)
    if response.status_code != 200:
        return pd.DataFrame()
    data = response.json()
    observations = data.get("observations", [])
    df = pd.DataFrame(observations)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df.dropna(inplace=True)
    return df

# Function to forecast using Exponential Smoothing
def forecast_series(df, steps=12):
    df = df.set_index("date")
    model = ExponentialSmoothing(df["value"], trend="add", seasonal=None, damped_trend=True)
    fit = model.fit()
    future_dates = [df.index[-1] + timedelta(days=30 * i) for i in range(1, steps + 1)]
    forecast = fit.forecast(steps=steps)
    return future_dates, forecast

# Function to format numbers
def format_number(value, metric):
    if metric in ["GDP", "PCE"]:
        return f"${value:,.2f}"  # Dollar formatting
    elif metric == "Unemployment Rate":
        return f"{value:.2f}%"  # Percentage formatting
    else:
        return f"{value:,.2f}"  # Default formatting for CPI

# Function to generate charts and formatted metrics
def generate_charts():
    charts = {}
    metrics = {}
    for metric, series_id in FRED_SERIES.items():
        df = get_fred_data(series_id)
        if df.empty:
            continue
        
        future_dates, forecast = forecast_series(df, steps=12)
        df_future = pd.DataFrame({"date": future_dates, "value": forecast})
        df_combined = pd.concat([df, df_future], ignore_index=False)
        
        # Store formatted latest and forecasted values
        metrics[metric] = {
            "latest": format_number(df.iloc[-1]["value"], metric),
            "forecast": format_number(forecast.iloc[-1], metric)
        }
        
        # Create plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["date"], y=df["value"], mode="lines", name="Historical", line=dict(color="blue")))
        fig.add_trace(go.Scatter(x=df_future["date"], y=df_future["value"], mode="lines", name="Forecast", line=dict(color="red", dash="dash")))
        fig.update_layout(title=f"{metric} Forecast", xaxis_title="Date", yaxis_title=f"{metric} Value")
        charts[metric] = fig.to_html(full_html=False, include_plotlyjs="cdn")
    
    return metrics, charts

@app.route("/predictive")
def predictive():
    metrics, charts = generate_charts()
    return render_template("predictive.html", metrics=metrics, charts=charts)

if __name__ == "__main__":
    print("Running Predictive Analytics Dashboard...")
    app.run(debug=True, port=5001)
