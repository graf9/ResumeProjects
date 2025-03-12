from flask import Blueprint, render_template, jsonify
import pandas as pd
from prophet import Prophet
import requests
from sklearn.metrics import mean_absolute_error, mean_squared_error
import datetime
import os

economic_forecast_bp = Blueprint('economic_forecast', __name__, template_folder='templates')

API_KEY = "3baa2dc8f0187695b947741bb81a4673"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES_MAP = {
    "GDP": "GDP",
    "CPI": "CPIAUCSL",
    "Unemployment": "UNRATE",
    "PCE": "PCE"
}

cached_forecasts = {}

def get_fred_data(series_id):
    params = {"series_id": series_id, "api_key": API_KEY, "file_type": "json"}
    response = requests.get(FRED_URL, params=params).json()
    if 'observations' in response:
        df = pd.DataFrame(response['observations'])
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        if series_id in ["GDP", "PCE"]:
            df['value'] = df['value'] / 1000.0
        return df[['date', 'value']].dropna().sort_values('date')
    return pd.DataFrame()

def train_model(data):
    df = data.rename(columns={"date": "ds", "value": "y"})
    model = Prophet(daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=True)
    model.fit(df)
    future = model.make_future_dataframe(periods=60, freq='M')
    forecast = model.predict(future)
    y_true = df['y'].values
    y_pred = forecast['yhat'][:len(y_true)].values
    mae = mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred) ** 0.5
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], mae, rmse

@economic_forecast_bp.route('/all_forecasts', methods=['GET'])
def all_forecasts():
    global cached_forecasts
    today = datetime.date.today().isoformat()
    if cached_forecasts and cached_forecasts.get('date') == today:
        return jsonify(cached_forecasts["data"])
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
    cached_forecasts = {"date": today, "data": results}
    return jsonify(results)

@economic_forecast_bp.route('/')
def home():
    return render_template('dashboard2.html')

@economic_forecast_bp.route('/favicon.ico')
def favicon():
    return "", 204
