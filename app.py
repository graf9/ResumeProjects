"""
US Economic Historical Dashboard (with caching, nowcasting GDP, distinct chart types, and data recency notes)

- Fetches historical data from the FRED API.
- Plots key economic indicators with Plotly using different chart types.
- Displays single-value metrics with the last observation date in small text ("as of MM-DD-YYYY").
- Includes optional Atlanta Fed GDPNow scraping.
- Binds to a port from the PORT environment variable (or 5000 by default).
"""

import os
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from flask import Flask, render_template
from datetime import datetime
from bs4 import BeautifulSoup  # For optional GDPNow nowcasting

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
    "CPIAUCSL": "2006-01-01",  # CPI starts Jan 2006.
    "INDPRO":   "1997-09-01"   # Industrial Production starts Sept 1997.
}

# Special start date for GDP and dual-axis chart.
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
        f"https://api.stlouisfed.org/fred/series/observations?"
        f"series_id={series_id}&api_key=3baa2dc8f0187695b947741bb81a4673"
        f"&file_type=json&observation_start={start_date}&observation_end={end_date}"
        f"&realtime_start={start_date}&realtime_end={realtime_end}"
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

    observations = data.get("observations", [])
    df = pd.DataFrame(observations)
    if df.empty:
        print(f"Warning: No data returned for {series_id}")
        cached_data[cache_key] = df
        return df

    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df.dropna(subset=["value"], inplace=True)
    df = df.groupby("date", as_index=False)["value"].last().sort_values("date")
    print(f"{series_id} date range: {df['date'].min()} to {df['date'].max()} | Rows: {len(df)}")
    cached_data[cache_key] = df
    return df

def get_gdp_now():
    """
    Scrape the latest GDPNow forecast from the Atlanta Fed website.
    Note: The scraping logic is dependent on the site structure; may need adjustments.
    """
    url = "https://www.atlantafed.org/cqer/research/gdpnow"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        # EXAMPLE: Update this selector after inspecting the new page structure.
        forecast_elem = soup.select_one("span.forecast-value")
        if forecast_elem:
            forecast = forecast_elem.get_text(strip=True)
            print(f"GDPNow forecast: {forecast}")
            return forecast
        else:
            print("GDPNow forecast element not found on the new page.")
            return None
    except Exception as e:
        print("Error fetching GDPNow data:", e)
        return None

def create_figures(end_date):
    figs = {}

    # 1. UNRATE: Unemployment Rate as a standard line chart.
    df_unrate = get_fred_data("UNRATE", DEFAULT_START, end_date)
    fig_unrate = px.line(
        df_unrate,
        x="date",
        y="value",
        title="US Unemployment Rate",
        labels={"date": "Date", "value": "Unemployment Rate (%)"},
        markers=True,
        color_discrete_sequence=["#636EFA"]
    )
    if not df_unrate.empty:
        fig_unrate.update_layout(xaxis=dict(range=[df_unrate["date"].min(), df_unrate["date"].max()]))
    figs["unrate"] = fig_unrate

    # 2. GDPC1: Real GDP as a scatter plot (markers only).
    df_gdp = get_fred_data("GDPC1", DUAL_START_DATE, end_date)
    if not df_gdp.empty:
        df_gdp["quarter"] = df_gdp["date"].dt.to_period("Q")
        df_gdp = df_gdp.groupby("quarter", as_index=False)["value"].last()
        df_gdp["date"] = df_gdp["quarter"].dt.to_timestamp(how="end")
        df_gdp.drop(columns="quarter", inplace=True)
        df_gdp["value"] = df_gdp["value"] / 1000.0  # Convert billions to trillions
    fig_gdp = px.scatter(
        df_gdp,
        x="date",
        y="value",
        title="US Real GDP (Trillions)",
        labels={"date": "Date", "value": "Real GDP (Trillions)"},
        color_discrete_sequence=["#EF553B"]
    )
    if not df_gdp.empty:
        fig_gdp.update_layout(xaxis=dict(range=[df_gdp["date"].min(), df_gdp["date"].max()]))
    figs["gdp"] = fig_gdp

    # 3. CPIAUCSL: Consumer Price Index as an area chart.
    cpi_start = CUSTOM_START_DATES.get("CPIAUCSL", DEFAULT_START)
    df_cpi = get_fred_data("CPIAUCSL", cpi_start, end_date)
    fig_cpi = px.area(
        df_cpi,
        x="date",
        y="value",
        title="US Consumer Price Index",
        labels={"date": "Date", "value": "CPI (Index)"},
        color_discrete_sequence=["#00CC96"]
    )
    if not df_cpi.empty:
        max_cpi = df_cpi["value"].max()
        fig_cpi.update_layout(
            xaxis=dict(range=[df_cpi["date"].min(), df_cpi["date"].max()]),
            yaxis=dict(range=[200, max_cpi + 10])
        )
    figs["cpi"] = fig_cpi

    # 4. FEDFUNDS: Federal Funds Rate as a spline line chart.
    df_fed = get_fred_data("FEDFUNDS", DEFAULT_START, end_date)
    fig_fed = px.line(
        df_fed,
        x="date",
        y="value",
        title="Federal Funds Rate",
        labels={"date": "Date", "value": "Federal Funds Rate (%)"},
        markers=True,
        line_shape="spline",
        color_discrete_sequence=["#AB63FA"]
    )
    if not df_fed.empty:
        fig_fed.update_layout(xaxis=dict(range=[df_fed["date"].min(), df_fed["date"].max()]))
    figs["fed"] = fig_fed

    # 5. INDPRO: Industrial Production as a step chart.
    indpro_start = CUSTOM_START_DATES.get("INDPRO", DEFAULT_START)
    df_indpro = get_fred_data("INDPRO", indpro_start, end_date)
    fig_indpro = px.line(
        df_indpro,
        x="date",
        y="value",
        title="US Industrial Production Index",
        labels={"date": "Date", "value": "Industrial Production Index"},
        line_shape="hv",
        markers=True,
        color_discrete_sequence=["#2F4F4F"]
    )
    if not df_indpro.empty:
        fig_indpro.update_layout(xaxis=dict(range=[df_indpro["date"].min(), df_indpro["date"].max()]))
    figs["indpro"] = fig_indpro

    # 6. PCE: Personal Consumption Expenditures as a dashed line chart.
    df_pce = get_fred_data("PCE", DEFAULT_START, end_date)
    # Use line_dash_sequence (a list) to set a constant dash style.
    fig_pce = px.line(
        df_pce,
        x="date",
        y="value",
        title="US Personal Consumption Expenditures",
        labels={"date": "Date", "value": "PCE (Billions)"},
        markers=True,
        line_dash_sequence=["dash"],
        color_discrete_sequence=["#19D3F3"]
    )
    if not df_pce.empty:
        fig_pce.update_layout(xaxis=dict(range=[df_pce["date"].min(), df_pce["date"].max()]))
    figs["pce"] = fig_pce

    # 7. M2SL: M2 Money Stock as a dotted line chart.
    df_m2 = get_fred_data("M2SL", DEFAULT_START, end_date)
    fig_m2 = px.line(
        df_m2,
        x="date",
        y="value",
        title="US M2 Money Stock",
        labels={"date": "Date", "value": "M2 (Billions)"},
        markers=True,
        line_dash_sequence=["dot"],
        color_discrete_sequence=["#FF6692"]
    )
    if not df_m2.empty:
        fig_m2.update_layout(xaxis=dict(range=[df_m2["date"].min(), df_m2["date"].max()]))
    figs["m2"] = fig_m2

    # 8. Dual-Axis: GDP vs. CPI (using Graph Objects, unchanged)
    df_gdp_dual = get_fred_data("GDPC1", DUAL_START_DATE, end_date)
    df_cpi_dual = get_fred_data("CPIAUCSL", DUAL_START_DATE, end_date)
    df_gdp_q = df_gdp_dual.copy()
    df_gdp_q["quarter"] = df_gdp_q["date"].dt.to_period("Q")
    df_gdp_q = df_gdp_q.groupby("quarter", as_index=False)["value"].last()
    df_gdp_q["date"] = df_gdp_q["quarter"].dt.to_timestamp(how="end")
    df_gdp_q.drop(columns="quarter", inplace=True)
    df_gdp_q.rename(columns={"value": "gdp"}, inplace=True)
    df_gdp_q["gdp"] = df_gdp_q["gdp"] / 1000.0  # Convert to trillions

    df_cpi_q = df_cpi_dual.copy()
    df_cpi_q["quarter"] = df_cpi_q["date"].dt.to_period("Q")
    df_cpi_q = df_cpi_q.groupby("quarter", as_index=False)["value"].mean()
    df_cpi_q["date"] = df_cpi_q["quarter"].dt.to_timestamp(how="end")
    df_cpi_q.drop(columns="quarter", inplace=True)
    df_cpi_q.rename(columns={"value": "cpi"}, inplace=True)

    df_dual = pd.merge(df_gdp_q, df_cpi_q, on="date", how="outer")
    df_dual.dropna(subset=["gdp", "cpi"], how="all", inplace=True)
    if df_dual.empty:
        fig_dual = go.Figure()
        fig_dual.update_layout(title="GDP vs. CPI: No Overlapping Data")
    else:
        fig_dual = go.Figure()
        fig_dual.add_trace(go.Scatter(
            x=df_dual["date"],
            y=df_dual["gdp"],
            mode="lines+markers",
            name="GDP",
            line=dict(color="#EF553B")
        ))
        fig_dual.add_trace(go.Scatter(
            x=df_dual["date"],
            y=df_dual["cpi"],
            mode="lines+markers",
            name="CPI",
            yaxis="y2",
            line=dict(color="#00CC96")
        ))
        fig_dual.update_layout(
            title="GDP vs. CPI",
            xaxis_title="Date",
            yaxis=dict(title="GDP (Trillions)"),
            yaxis2=dict(title="CPI (Index)", overlaying="y", side="right")
        )
    figs["dual"] = fig_dual

    return figs

@app.route("/")
def dashboard():
    figs = create_figures(DEFAULT_END)
    figs_html = {name: fig.to_html(full_html=False, include_plotlyjs="cdn")
                 for name, fig in figs.items()}

    # Pull fresh data for single-value metrics
    df_unrate = get_fred_data("UNRATE", DEFAULT_START, DEFAULT_END)
    df_gdp    = get_fred_data("GDPC1", DUAL_START_DATE, DEFAULT_END)
    df_cpi    = get_fred_data("CPIAUCSL", CUSTOM_START_DATES.get("CPIAUCSL", DEFAULT_START), DEFAULT_END)
    df_fed    = get_fred_data("FEDFUNDS", DEFAULT_START, DEFAULT_END)
    df_m2     = get_fred_data("M2SL", DEFAULT_START, DEFAULT_END)
    df_indpro = get_fred_data("INDPRO", CUSTOM_START_DATES.get("INDPRO", DEFAULT_START), DEFAULT_END)

    metrics = {}

    # Unemployment Rate
    if not df_unrate.empty:
        last_date_unrate = df_unrate.iloc[-1]["date"].strftime("%m-%d-%Y")
        metrics["Unemployment Rate"] = (
            f"{df_unrate.iloc[-1]['value']:.1f}%"
            f"<br><small style='font-size:0.6em;'>(as of {last_date_unrate})</small>"
        )

    # Real GDP
    if not df_gdp.empty:
        df_gdp["quarter"] = df_gdp["date"].dt.to_period("Q")
        df_gdp = df_gdp.groupby("quarter", as_index=False)["value"].last()
        df_gdp["date"] = df_gdp["quarter"].dt.to_timestamp(how="end")
        df_gdp.drop(columns="quarter", inplace=True)
        latest_gdp_value = df_gdp.iloc[-1]["value"] / 1000.0  # billions -> trillions
        last_date_gdp = df_gdp.iloc[-1]["date"].strftime("%m-%d-%Y")
        metrics["Real GDP"] = (
            f"${latest_gdp_value:.1f}T"
            f"<br><small style='font-size:0.6em;'>(as of {last_date_gdp})</small>"
        )

    # CPI
    if not df_cpi.empty:
        last_date_cpi = df_cpi.iloc[-1]["date"].strftime("%m-%d-%Y")
        metrics["CPI"] = (
            f"{df_cpi.iloc[-1]['value']:.1f}"
            f"<br><small style='font-size:0.6em;'>(as of {last_date_cpi})</small>"
        )

    # Fed Funds Rate
    if not df_fed.empty:
        last_date_fed = df_fed.iloc[-1]["date"].strftime("%m-%d-%Y")
        metrics["Fed Funds Rate"] = (
            f"{df_fed.iloc[-1]['value']:.2f}%"
            f"<br><small style='font-size:0.6em;'>(as of {last_date_fed})</small>"
        )

    # M2 Money Stock
    if not df_m2.empty:
        last_date_m2 = df_m2.iloc[-1]["date"].strftime("%m-%d-%Y")
        metrics["M2 Money Stock"] = (
            f"${df_m2.iloc[-1]['value'] / 1000.0:.1f}T"
            f"<br><small style='font-size:0.6em;'>(as of {last_date_m2})</small>"
        )

    # Industrial Production
    if not df_indpro.empty:
        last_date_indpro = df_indpro.iloc[-1]["date"].strftime("%m-%d-%Y")
        metrics["Industrial Production"] = (
            f"{df_indpro.iloc[-1]['value']:.1f}"
            f"<br><small style='font-size:0.6em;'>(as of {last_date_indpro})</small>"
        )

    # Optionally, fetch the GDPNow nowcasting estimate
    gdp_now = get_gdp_now()
    if gdp_now:
        metrics["GDPNow Estimate"] = gdp_now

    print("DEBUG metrics:", metrics)
    return render_template("dashboard.html", figs_html=figs_html, metrics=metrics)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
