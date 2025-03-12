from flask import Flask, request, jsonify, render_template
import requests
import random

app = Flask(__name__)

# Replace with your own TMDB API key from https://www.themoviedb.org
TMDB_API_KEY = "61b80bde4829bb9a4632e96e4085be79"

# Map TMDB genre IDs to human-readable names
GENRE_MAP = {
    28: "Action",       12: "Adventure",    16: "Animation",
    35: "Comedy",       80: "Crime",        99: "Documentary",
    18: "Drama",        10751: "Family",      14: "Fantasy",
    36: "History",      27: "Horror",       10402: "Music",
    9648: "Mystery",    10749: "Romance",     878: "Science Fiction",
    10770: "TV Movie",  53: "Thriller",     10752: "War",
    37: "Western"
}

# Reverse map for genre name lookup (all lower-case for case-insensitive matching)
REVERSE_GENRE_MAP = {name.lower(): gid for gid, name in GENRE_MAP.items()}

# Base URL for poster images (w500 size)
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

def search_movie(movie_title):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": movie_title}
    response = requests.get(url, params=params)
    results = response.json().get("results", [])
    return results[0] if results else None

def get_common_genre_id(movies):
    genre_count = {}
    for movie in movies:
        for gid in movie.get("genre_ids", []):
            genre_count[gid] = genre_count.get(gid, 0) + 1
    return max(genre_count, key=genre_count.get) if genre_count else None

def get_average_release_year(movies):
    total, count = 0, 0
    for movie in movies:
        date = movie.get("release_date", "")
        if date and len(date) >= 4:
            total += int(date[:4])
            count += 1
    return total // count if count else None

def get_year_range(avg_year):
    # Changed default delta to 40 years
    delta = 40
    return avg_year - delta, avg_year + delta

def discover_movie_advanced(genre_filter, rating_threshold, date_range, runtime_range, language_filter=True):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "sort_by": "popularity.desc",
        "vote_average.gte": rating_threshold,
    }
    if genre_filter is not None:
        params["with_genres"] = genre_filter
    if date_range:
        params["primary_release_date.gte"] = date_range[0]
        params["primary_release_date.lte"] = date_range[1]
    if runtime_range:
        params["with_runtime.gte"] = runtime_range[0]
        params["with_runtime.lte"] = runtime_range[1]
    if language_filter:
        params["with_original_language"] = "en"
    response = requests.get(url, params=params)
    return response.json().get("results", [])

def get_tmdb_recommendations(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    return response.json().get("results", [])

def recommend_movie(preferences):
    # Retrieve two movies from user input
    movie_titles = preferences.get("movies", [])
    found_movies = []
    for title in movie_titles:
        movie = search_movie(title)
        if movie:
            found_movies.append(movie)
    # Require two valid movies; otherwise, return error.
    if len(found_movies) < 2:
        return None

    # Compute common genre and average release year from the two movies
    computed_genre = get_common_genre_id(found_movies)
    computed_avg_year = get_average_release_year(found_movies)
    
    # Allow user to override computed genre and year range if provided
    user_genre = preferences.get("genre", "").strip().lower()
    if user_genre:
        genre_filter = REVERSE_GENRE_MAP.get(user_genre)
    else:
        genre_filter = computed_genre

    min_year = preferences.get("min_year")
    max_year = preferences.get("max_year")
    if min_year and max_year:
        date_range = (f"{min_year}-01-01", f"{max_year}-12-31")
    elif computed_avg_year:
        yr_min, yr_max = get_year_range(computed_avg_year)
        date_range = (f"{yr_min}-01-01", f"{yr_max}-12-31")
    else:
        date_range = None

    # Retrieve minimum rating threshold from user (default to 7.0)
    rating_threshold = float(preferences.get("rating_threshold", 7.0))

    # Retrieve runtime preference if provided
    runtime = preferences.get("runtime")
    if runtime:
        try:
            runtime = int(runtime)
            # Set a range of ±10 minutes
            runtime_range = (runtime - 10, runtime + 10)
        except ValueError:
            runtime_range = None
    else:
        runtime_range = None

    # First, try the discover endpoint based on combined preferences.
    results = discover_movie_advanced(genre_filter, rating_threshold, date_range, runtime_range, language_filter=True)
    # Exclude the movies the user provided
    exclude_ids = {movie["id"] for movie in found_movies}
    filtered = [m for m in results if m["id"] not in exclude_ids]

    if filtered:
        random.shuffle(filtered)
        recommended = filtered[0]
    else:
        # Fallback strategy: aggregate TMDB recommendations from each movie.
        rec_pool = []
        for movie in found_movies:
            rec_pool.extend(get_tmdb_recommendations(movie["id"]))
        if rec_pool:
            # Exclude movies the user already provided.
            rec_pool = [m for m in rec_pool if m["id"] not in exclude_ids]
            if rec_pool:
                random.shuffle(rec_pool)
                recommended = rec_pool[0]
            else:
                recommended = None
        else:
            recommended = None

    if not recommended:
        return None

    release_date = recommended.get("release_date", "Unknown")
    poster_path = recommended.get("poster_path")
    poster_url = f"{IMAGE_BASE_URL}{poster_path}" if poster_path else None

    return {
        "title": recommended.get("title", "No title"),
        "overview": recommended.get("overview", "No overview available."),
        "release_date": release_date,
        "poster_url": poster_url
    }

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json()
    if not data or "movies" not in data or len(data["movies"]) < 2:
        return jsonify({"error": "Please provide two movie titles."}), 400

    recommendation = recommend_movie(data)
    if not recommendation:
        return jsonify({"error": "No recommendation could be made."}), 500
    return jsonify(recommendation)

if __name__ == "__main__":
    app.run(debug=True)
