"""
fetch_data.py

Fetch a single FRED series (e.g. UNRATE) and store it in an SQLite database.
"""
import requests
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine

# --- Configuration ---
API_KEY = '3baa2dc8f0187695b947741bb81a4673'  # Your FRED API key
series_id = 'UNRATE'  # Example: Unemployment Rate
start_date = '2010-01-01'
end_date = datetime.today().strftime('%Y-%m-%d')

# --- Construct the API URL ---
url = (
    f'https://api.stlouisfed.org/fred/series/observations?'
    f'series_id={series_id}&api_key={API_KEY}&file_type=json&'
    f'observation_start={start_date}&observation_end={end_date}'
)

# --- Fetch Data from FRED ---
response = requests.get(url)
data = response.json()

# --- Convert JSON Data to a Pandas DataFrame ---
observations = data.get('observations', [])
df = pd.DataFrame(observations)

# --- Data Cleaning ---
if not df.empty:
    df['date'] = pd.to_datetime(df['date'])
    df['value'] = pd.to_numeric(df['value'], errors='coerce')

# --- Check the data by printing the first few rows ---
print("First 5 rows of data:")
print(df.head())

# --- Store Data in a SQL Database ---
engine = create_engine('sqlite:///fred_data.db')
df.to_sql('unemployment', engine, if_exists='replace', index=False)

print("Data successfully stored in the SQL database (fred_data.db).")
