from flask import Flask, request, jsonify, render_template
import requests
import random
from collections import Counter

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

# Default threshold functions
def get_rating_threshold():
    return 7.0

def get_vote_threshold():
    return 500

def get_year_range(avg_year):
    delta = 5
    return avg_year - delta, avg_year + delta

def get_popularity_threshold():
    return 30

def discover_movie_advanced(genre_filter, rating_threshold, vote_threshold,
                            date_range, popularity_threshold, language_filter=True):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "sort_by": "popularity.desc",
        "vote_average.gte": rating_threshold,
        "vote_count.gte": vote_threshold,
        "popularity.gte": popularity_threshold
    }
    if genre_filter is not None:
        params["with_genres"] = genre_filter
    if date_range:
        params["primary_release_date.gte"] = date_range[0]
        params["primary_release_date.lte"] = date_range[1]
    if language_filter:
        params["with_original_language"] = "en"
    response = requests.get(url, params=params)
    return response.json().get("results", [])

def get_tmdb_recommendations(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    return response.json().get("results", [])

def recommend_movie(movie_titles):
    # Search for the two movies provided by the user.
    found_movies = []
    exclude_ids = []
    for title in movie_titles:
        movie = search_movie(title)
        if movie:
            found_movies.append(movie)
            exclude_ids.append(movie["id"])
    if len(found_movies) < 2:
        return None

    # Determine common genre and average release year.
    common_genre = get_common_genre_id(found_movies)
    avg_year = get_average_release_year(found_movies)
    genre_filter = common_genre  # enforce common genre by default

    rating_threshold = get_rating_threshold()
    vote_threshold = get_vote_threshold()
    popularity_threshold = get_popularity_threshold()

    if avg_year:
        yr_min, yr_max = get_year_range(avg_year)
        date_range = (f"{yr_min}-01-01", f"{yr_max}-12-31")
    else:
        date_range = None

    # Query TMDB's Discover endpoint.
    results = discover_movie_advanced(
        genre_filter, rating_threshold, vote_threshold,
        date_range, popularity_threshold, language_filter=True
    )
    filtered = [m for m in results if m["id"] not in exclude_ids]
    
    if filtered:
        # Shuffle entire filtered list for more variety.
        random.shuffle(filtered)
        recommended = filtered[0]
    else:
        # Fallback: use aggregated TMDB recommendations.
        rec_pool = []
        for movie in found_movies:
            rec_pool.extend(get_tmdb_recommendations(movie["id"]))
        if rec_pool:
            random.shuffle(rec_pool)
            recommended = rec_pool[0]
        else:
            recommended = None

    if not recommended:
        return None

    release_date = recommended.get("release_date", "Unknown")
    poster_path = recommended.get("poster_path")
    poster_url = f"{IMAGE_BASE_URL}{poster_path}" if poster_path else None

    return {
        "title": recommended["title"],
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
    if not data or "movies" not in data:
        return jsonify({"error": "No movies provided."}), 400

    movie_titles = data["movies"]
    if len(movie_titles) < 2:
        return jsonify({"error": "Please provide two movie titles."}), 400

    recommendation = recommend_movie(movie_titles)
    if not recommendation:
        return jsonify({"error": "No recommendation could be made."}), 500
    return jsonify(recommendation)

if __name__ == "__main__":
    app.run(debug=True)
