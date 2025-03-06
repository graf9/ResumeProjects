"""
AI-Powered Economic Forecast Dashboard

Description:
    This Flask app demonstrates a multi-indicator economic forecast using:
      - FRED for data retrieval
      - Prophet for time-series modeling (monthly frequency, 5-year horizon)
      - Plotly for interactive visualizations
      - Inline HTML + minimal CSS for a polished presentation

Ideal for portfolio or resume showcases.
"""

from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.graph_objects as go
from prophet import Prophet
import requests
from sklearn.metrics import mean_absolute_error, mean_squared_error

app = Flask(__name__)

# ----------------------------
# Configuration / Constants
# ----------------------------
API_KEY = "3baa2dc8f0187695b947741bb81a4673"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES_MAP = {
    "GDP": "GDP",               # Gross Domestic Product
    "CPI": "CPIAUCSL",          # Consumer Price Index
    "Unemployment": "UNRATE",   # Unemployment Rate
    "PCE": "PCE"                # Personal Consumption Expenditures
}

# ------------------------------------------------
# Data Retrieval and Forecasting Helper Functions
# ------------------------------------------------
def get_fred_data(series_id):
    """
    Fetch monthly data from the FRED API for a given 'series_id'.
    Returns a DataFrame with columns ['date', 'value'], sorted by date.
    """
    params = {
        "series_id": series_id,
        "api_key": API_KEY,
        "file_type": "json"
    }
    response = requests.get(FRED_URL, params=params).json()

    if 'observations' in response:
        df = pd.DataFrame(response['observations'])
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df[['date', 'value']].dropna().sort_values('date')
        return df
    else:
        return pd.DataFrame()

def train_model(data):
    """
    Trains a Prophet model (monthly data, 5-year horizon).
    Disables daily/weekly seasonality for a smoother trend.
    Returns a forecast DataFrame with ['ds', 'yhat', 'yhat_lower', 'yhat_upper'].
    """
    df = data.rename(columns={"date": "ds", "value": "y"})
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=True
    )
    model.fit(df)

    # 5-year forecast, monthly frequency
    future = model.make_future_dataframe(periods=60, freq='M')
    forecast = model.predict(future)

    # Calculate MAE and RMSE
    y_true = df['y'].values  # Actual values
    y_pred = forecast['yhat'][:len(y_true)].values  # Prophet predictions
    mae = mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred) ** 0.5  # Compute RMSE manually

    print(f"MAE: {mae:.4f}, RMSE: {rmse:.4f}")
    
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], mae, rmse

@app.route('/all_forecasts', methods=['GET'])
def all_forecasts():
    """
    Returns a JSON object containing forecasts for ALL indicators + MAE/RMSE scores:
    {
      "GDP": { "dates": [...], "forecast": [...], "lower": [...], "upper": [...], "MAE": value, "RMSE": value },
      "CPI": { ... },
      "Unemployment": { ... },
      "PCE": { ... }
    }
    """
    results = {}
    for name, fred_id in SERIES_MAP.items():
        data = get_fred_data(fred_id)
        if data.empty:
            results[name] = {"error": f"No data available for {name}"}
        else:
            forecast_data, mae, rmse = train_model(data)
            results[name] = {
                "dates": forecast_data["ds"].astype(str).tolist(),
                "forecast": forecast_data["yhat"].tolist(),
                "lower": forecast_data["yhat_lower"].tolist(),
                "upper": forecast_data["yhat_upper"].tolist(),
                "MAE": round(mae, 4),
                "RMSE": round(rmse, 4)
            }
    return jsonify(results)

@app.route('/dashboard')
def dashboard():
    descriptions = {
        "GDP": "Gross Domestic Product measures the total monetary or market value of all the finished goods and services produced within a country's borders in a specific time period.",
        "CPI": "The Consumer Price Index is a measure that examines the weighted average of prices of a basket of consumer goods and services.",
        "Unemployment": "The unemployment rate represents the percentage of the labor force that is jobless but actively seeking employment.",
        "PCE": "Personal Consumption Expenditures (PCE) tracks consumer spending on goods and services, reflecting changes in consumer behavior and inflationary pressures."
    }
    
    return render_template('dashboard2.html', descriptions=descriptions)


if __name__ == '__main__':
    app.run(debug=True)