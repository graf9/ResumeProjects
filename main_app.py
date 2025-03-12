from flask import Flask
from economic_history_bp import economic_history_bp
from movie_blueprint import movie_bp
from economic_forecast_bp import economic_forecast_bp

app = Flask(__name__)

# Register each blueprint with a unique URL prefix
app.register_blueprint(economic_history_bp, url_prefix='/history')
app.register_blueprint(movie_bp, url_prefix='/movies')
app.register_blueprint(economic_forecast_bp, url_prefix='/forecast')

@app.route('/')
def index():
    return """
    <h1>Data Analytics Dashboards</h1>
    <ul>
      <li><a href="/history">US Economic Historical Dashboard</a></li>
      <li><a href="/movies">Movie Recommendation App</a></li>
      <li><a href="/forecast">Economic Forecast Dashboard</a></li>
    </ul>
    """

if __name__ == '__main__':
    app.run(debug=True)
