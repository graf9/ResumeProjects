from flask import Flask, request, jsonify, render_template, session
import requests
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure random secret key

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
# Reverse map for genre name lookup (all lower-case)
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
    # Expect three movie titles from user input
    movie_titles = preferences.get("movies", [])
    found_movies = []
    for title in movie_titles:
        movie = search_movie(title)
        if movie:
            found_movies.append(movie)
    if len(found_movies) < 3:
        return None

    computed_genre = get_common_genre_id(found_movies)
    computed_avg_year = get_average_release_year(found_movies)
    
    user_genre = preferences.get("genre", "").strip().lower()
    genre_filter = REVERSE_GENRE_MAP.get(user_genre, computed_genre) if user_genre else computed_genre

    min_year = preferences.get("min_year")
    max_year = preferences.get("max_year")
    if min_year and max_year:
        date_range = (f"{min_year}-01-01", f"{max_year}-12-31")
    elif computed_avg_year:
        yr_min, yr_max = get_year_range(computed_avg_year)
        date_range = (f"{yr_min}-01-01", f"{yr_max}-12-31")
    else:
        current_year = datetime.now().year
        date_range = (f"{current_year-40}-01-01", f"{current_year}-12-31")

    rating_threshold = float(preferences.get("rating_threshold", 6.5))
    
    runtime = preferences.get("runtime")
    if runtime:
        try:
            runtime = int(runtime)
            runtime_range = (runtime - 10, runtime + 10)
        except ValueError:
            runtime_range = None
    else:
        runtime_range = None

    results = discover_movie_advanced(genre_filter, rating_threshold, date_range, runtime_range, language_filter=True)
    exclude_ids = {movie["id"] for movie in found_movies}

    # Retrieve previously recommended movie IDs as a set from session
    all_rec_ids = set(session.get("all_rec_ids", []))
    filtered = [m for m in results if m["id"] not in exclude_ids and m["id"] not in all_rec_ids]

    current_year = datetime.now().year

    def score_movie(rec):
        s = 0
        rec_genres = rec.get("genre_ids", [])
        if user_genre:
            user_genre_id = REVERSE_GENRE_MAP.get(user_genre)
            if user_genre_id and user_genre_id in rec_genres:
                s += 10
            else:
                s -= 5
        else:
            if computed_genre and computed_genre in rec_genres:
                s += 5
        vote = rec.get("vote_average", 0)
        s += (vote - rating_threshold)
        r_date = rec.get("release_date", "")
        if r_date:
            try:
                year = int(r_date[:4])
                if min_year and max_year:
                    if min_year <= year <= max_year:
                        s += 2
                else:
                    if current_year - 40 <= year <= current_year:
                        s += 2
            except:
                pass
        return s

    recommendations = []
    if len(filtered) >= 2:
        filtered = sorted(filtered, key=score_movie, reverse=True)
        recommendations = filtered[:2]
    elif len(filtered) == 1:
        recommendations.append(filtered[0])
        rec_pool = []
        for movie in found_movies:
            rec_pool.extend(get_tmdb_recommendations(movie["id"]))
        rec_pool = [m for m in rec_pool if m["id"] not in exclude_ids and m["id"] not in all_rec_ids and m["id"] != recommendations[0]["id"]]
        if rec_pool:
            rec_pool = sorted(rec_pool, key=score_movie, reverse=True)
            recommendations.append(rec_pool[0])
    else:
        rec_pool = []
        for movie in found_movies:
            rec_pool.extend(get_tmdb_recommendations(movie["id"]))
        rec_pool = [m for m in rec_pool if m["id"] not in exclude_ids and m["id"] not in all_rec_ids]
        if len(rec_pool) >= 2:
            rec_pool = sorted(rec_pool, key=score_movie, reverse=True)
            recommendations = rec_pool[:2]
        elif len(rec_pool) == 1:
            recommendations = rec_pool

    if not recommendations or len(recommendations) < 1:
        return None

    formatted_recs = []
    for rec in recommendations:
        reasons = []
        rec_genres = rec.get("genre_ids", [])
        if user_genre:
            user_genre_id = REVERSE_GENRE_MAP.get(user_genre)
            if user_genre_id and user_genre_id in rec_genres:
                reasons.append(f"This movie strongly matches your preferred genre ({user_genre.title()}).")
            else:
                reasons.append(f"This movie does not match your preferred genre ({user_genre.title()}), but was chosen for its other merits.")
        else:
            if computed_genre and computed_genre in rec_genres:
                comp_genre_name = GENRE_MAP.get(computed_genre, "your taste")
                reasons.append(f"It reflects your common taste in {comp_genre_name} movies.")
        vote = rec.get("vote_average", 0)
        if vote:
            reasons.append(f"It has a high rating of {vote:.1f}, exceeding your minimum requirement.")
        r_date = rec.get("release_date", "")
        if r_date:
            try:
                year = int(r_date[:4])
                if min_year and max_year:
                    if min_year <= year <= max_year:
                        reasons.append(f"It was released in {year}, which is within your chosen timeframe.")
                else:
                    if current_year - 40 <= year <= current_year:
                        reasons.append(f"It was released in {year}, aligning with the last 40 years of movies you enjoy.")
            except:
                pass

        rec_reasons = " ".join(reasons)
        release_date = rec.get("release_date", "Unknown")
        poster_path = rec.get("poster_path")
        poster_url = f"{IMAGE_BASE_URL}{poster_path}" if poster_path else None
        formatted_recs.append({
            "title": rec.get("title", "No title"),
            "overview": rec.get("overview", "No overview available."),
            "release_date": release_date,
            "poster_url": poster_url,
            "reasons": rec_reasons
        })
    
    # Update the session to accumulate all recommended movie IDs as a list
    all_rec_ids.update(rec.get("id") for rec in recommendations)
    session["all_rec_ids"] = list(all_rec_ids)
    session.modified = True

    return formatted_recs

@app.route("/")
def home():
    # Reset all previously recommended movies on page refresh
    session.pop("all_rec_ids", None)
    return render_template("index.html")

@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json()
    if not data or "movies" not in data or len(data["movies"]) < 3:
        return jsonify({"error": "Please provide at least three movie titles."}), 400

    recommendations = recommend_movie(data)
    if not recommendations or len(recommendations) < 1:
        return jsonify({"error": "No recommendations could be made."}), 500
    return jsonify({"recommendations": recommendations})

if __name__ == "__main__":
    app.run(debug=True)
