# ==========================================
# BookHub - Book Tracking and Recommendation System
# ==========================================
# This is the main backend server for BookHub, built with Flask.
# It handles book searches, user data, and recommendations.

# Import required libraries
import os  # For file system operations
from flask import Flask, render_template, jsonify, send_from_directory, request  # Flask web framework
import traceback  # For detailed error reporting
from collections import defaultdict
import requests  # For making HTTP requests to external APIs
from flask_cors import CORS  # To handle cross-origin requests (important for web apps)
##from firebase_recommendations import FirebaseRecommendations  # Our custom Firebase service
from optimized_firebase import OptimizedFirebaseService  # Optimized Firebase service
import firebase_admin  # Firebase Admin SDK for Python
from firebase_admin import credentials, firestore, auth  # For Firebase credentials and Firestore database
# ------------------------------
# Flask Setup
# ------------------------------
# __name__ tells Flask where to find templates and static files
app = Flask(__name__, template_folder='templates')

# Enable CORS (Cross-Origin Resource Sharing)
# This allows our frontend (running on different ports) to communicate with this backend
CORS(app)

# Path to local book database (optional - for storing books locally)
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), 'book_details.csv')

SERVICE_ACCOUNT_PATH = os.path.join(os.path.dirname(__file__), 'bookhub-80381-firebase-adminsdk-fbsvc-b3e2365f77.json')

if os.path.exists(SERVICE_ACCOUNT_PATH):
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {
        'projectId': 'bookhub-80381'
    })
    db = firestore.client()
    # Initialize optimized Firebase service
    optimized_firebase = OptimizedFirebaseService('bookhub-80381', SERVICE_ACCOUNT_PATH)
else:
    # For testing or when credentials are not available
    db = None
    optimized_firebase = None

# Function to verify Firebase ID token
def verify_firebase_token(id_token):
    """
    Verifies the Firebase ID token and returns the decoded token if valid.
    Returns None if invalid.
    """
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None

# ==========================================
# EXTERNAL API CONFIGURATION
# ==========================================
# These are the keys and settings for connecting to external book databases
# Google Books API provides comprehensive book information
GOOGLE_BOOKS_API_KEY = "AIzaSyCOP27ymhGqjdwBBjKoeUK53ihZg4xzCzo"

# --- External Book Search Functions ---

def search_google_books(query):
    """Searches Google Books API for the given query."""
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=20"
    if GOOGLE_BOOKS_API_KEY:
        url += f"&key={GOOGLE_BOOKS_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        
        books = []
        if 'items' in data:
            for item in data['items']:
                volume_info = item.get('volumeInfo', {})
                
                # Extract ISBNs
                isbns = {}
                for identifier in volume_info.get('industryIdentifiers', []):
                    if identifier['type'] == 'ISBN_13':
                        isbns['isbn_13'] = identifier['identifier']
                    elif identifier['type'] == 'ISBN_10':
                        isbns['isbn_10'] = identifier['identifier']

                # Normalize genres
                genres = volume_info.get('categories', [])
                normalized_genres = []
                for genre in genres:
                    normalized_genres.extend([g.strip() for g in genre.split('/')])
                normalized_genres = list(set(normalized_genres)) # Remove duplicates

                book = {
                    'id': item.get('id'), # Google Books ID
                    'title': volume_info.get('title'),
                    'author': ', '.join(volume_info.get('authors', [])),
                    'description': volume_info.get('description'),
                    'genres': normalized_genres,
                    'coverUrl': volume_info.get('imageLinks', {}).get('thumbnail'),
                    'published_date': volume_info.get('publishedDate'),
                    'page_count': volume_info.get('pageCount'),
                    'average_rating': volume_info.get('averageRating'),
                    'ratings_count': volume_info.get('ratingsCount'),
                    'isbn_13': isbns.get('isbn_13'),
                    'isbn_10': isbns.get('isbn_10'),
                    'source': 'Google Books'
                }
                # Filter out books with no title or author
                if book['title'] and book['author']:
                    books.append(book)
        return books
    except requests.exceptions.RequestException as e:
        print(f"Error searching Google Books: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during Google Books search: {e}")
        traceback.print_exc()
        return []

def search_open_library(query):
    """Searches Open Library API for the given query."""
    url = f"https://openlibrary.org/search.json?q={query}&limit=20"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        books = [] #pass this list of books into cosine similarity , it will return list of similar books, 
        if 'docs' in data:
            for doc in data['docs']:
                # Open Library often provides ISBNs in a list
                isbn_13 = next((isbn for isbn in doc.get('isbn', []) if len(isbn) == 13), None)
                isbn_10 = next((isbn for isbn in doc.get('isbn', []) if len(isbn) == 10), None)

                # Open Library cover URLs are based on OLID or ISBN
                coverUrl= None
                if doc.get('cover_i'):
                    coverUrl= f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg"
                elif isbn_13:
                    coverUrl= f"https://covers.openlibrary.org/b/isbn/{isbn_13}-M.jpg"
                elif isbn_10:
                    coverUrl= f"https://covers.openlibrary.org/b/isbn/{isbn_10}-M.jpg"

                book = {
                    'id': doc.get('key'), # Open Library key (e.g., /works/OL...)
                    'title': doc.get('title'),
                    'author': ', '.join(doc.get('author_name', [])),
                    'description': doc.get('first_sentence', [''])[0], # Often a first sentence
                    'genres': doc.get('subject', []), # Subjects can act as genres
                    'coverUrl': coverUrl,
                    'published_date': doc.get('first_publish_year'), # Year only
                    'page_count': doc.get('number_of_pages_median'),
                    'average_rating': doc.get('ratings_average'),
                    'ratings_count': doc.get('ratings_count'),
                    'isbn_13': isbn_13,
                    'isbn_10': isbn_10,
                    'source': 'Open Library'
                }
                # Filter out books with no title or author
                if book['title'] and book['author']:
                    books.append(book)
        return books
    except requests.exceptions.RequestException as e:
        print(f"Error searching Open Library: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during Open Library search: {e}")
        traceback.print_exc()
        return []

def normalize_and_deduplicate_books(google_books_results, open_library_results):
    """
    Combines, normalizes, and deduplicates search results from multiple sources.
    Prioritizes Google Books data if ISBN matches.
    """
    unified_books = {} # Use a dictionary for deduplication by ISBN or title+author

    # Add Google Books results
    for book in google_books_results:
        key = book.get('isbn_13') or book.get('isbn_10')
        if not key:
            # Fallback key for books without ISBNs
            key = f"{book['title'].lower()}-{book['author'].lower()}"
        
        unified_books[key] = book # Google Books takes precedence if key clashes

    # Add Open Library results, merging or adding new ones
    for ol_book in open_library_results:
        key = ol_book.get('isbn_13') or ol_book.get('isbn_10')
        if not key:
            key = f"{ol_book['title'].lower()}-{ol_book['author'].lower()}"

        if key not in unified_books:
            # If not already present, add the Open Library book
            unified_books[key] = ol_book
        else:
            # If already present (from Google Books), try to merge missing info
            # Google Books is generally more comprehensive for description/rating
            # but Open Library might have a better cover or different genres.
            existing_book = unified_books[key]
            if not existing_book.get('description') and ol_book.get('description'):
                existing_book['description'] = ol_book['description']
            if not existing_book.get('coverUrl') and ol_book.get('coverUrl'):
                existing_book['coverUrl'] = ol_book['coverUrl']
            if not existing_book.get('page_count') and ol_book.get('page_count'):
                existing_book['page_count'] = ol_book['page_count']
            if not existing_book.get('average_rating') and ol_book.get('average_rating'):
                existing_book['average_rating'] = ol_book['average_rating']
            
            # Merge existing genres
            existing_genres = set(existing_book.get('genres', []))
            ol_genres = set(ol_book.get('genres', []))
            existing_book['genres'] = list(existing_genres.union(ol_genres))

    return list(unified_books.values())

# --- Flask Routes ---

@app.route('/')
def homepage():
    """
    Renders the homepage (homepage.html).
    This is the landing page users see when they first visit the site.
    """
    return render_template('homepage.html')

@app.route('/api/user-info', methods=['POST'])
def user_info():
    """
    API endpoint to receive authenticated user info from frontend and store in Firestore.
    Expects JSON payload with 'user_id' and 'email'.
    """
    user = request.headers.get("Authorization")
    return jsonify({"user": user or "anonymous"}), 200

@app.route('/bookTracking')
def tracking_page():
    """
    Renders the book tracking page (bookTracking.html).
    This page will display the user's cart, fetched from Firebase.
    """
    return render_template('bookTracking.html')

@app.route('/login')
def login_page():
    """
    Renders the login page for user authentication.
    """
    return render_template('login.html')

@app.route('/register')
def register_page():
    """
    Renders the registration page for new users.
    """
    return render_template('register.html')

@app.route('/searchResult')
@app.route('/search')
def search_page():
    """
    Renders the book search page (searchResult.html).
    This page will now primarily use the combined online search API.
    """
    return render_template('searchResult.html')

@app.route('/read')
def reading_session_page():
    """
    Renders the reading session page (readingSession.html).
    This page will receive a book ID via query parameter to load the session context.
    """
    return render_template('readingSession.html')

@app.route('/faq')
def faq_page():
    """
    Renders the FAQ page.
    """
    return render_template('faq.html')

@app.route('/summary')
def summary_page():
    """
    Renders the summary/edit page (summaryPage.html).
    This page will receive a book ID via query parameter to load book details.
    """
    book_id = request.args.get('bookId')
    return render_template('summaryPage.html', book_id=book_id)

@app.route('/api/online-book-search')
def online_book_search():
    """
    Unified API endpoint to search for books from multiple online sources (Google Books, Open Library).
    Combines, normalizes, and deduplicates results.
    """
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search query is required."}), 400

    google_results = search_google_books(query)
    open_library_results = search_open_library(query)

    combined_results = normalize_and_deduplicate_books(google_results, open_library_results)
    
    # We sort the results by average_rating
    # combined_results.sort(key=lambda x: x.get('average_rating', 0), reverse=True)

    return jsonify(combined_results)

# --- New API Endpoints for Custom Tags and Recommendations ---

@app.route('/api/recommendations/by-tags', methods=['GET'])
def get_recommendations_by_tags():
    """
    API endpoint to get book recommendations based on custom tags (optimized).
    """
    try:
        user_id = request.args.get('user_id')
        tags = request.args.get('tags', '').split(',')
        limit = int(request.args.get('limit', 10))
        
        if not user_id or not tags or tags == ['']:
            return jsonify({"error": "Missing required parameters"}), 400
        
        if not optimized_firebase:
            return jsonify({"error": "Firebase service not available"}), 503
        
        # Use optimized Firebase service
        recommendations = optimized_firebase.get_recommendations_by_tags_optimized(tags, limit, user_id)
        
        return jsonify({"recommendations": recommendations})
        
    except Exception as e:
        print(f"Error in get_recommendations_by_tags: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendations/similar/<book_id>', methods=['GET'])
def get_similar_books(book_id):
    """
    API endpoint to get similar books based on tags from a specific book (optimized).
    """
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 5))
        
        if not user_id or not book_id:
            return jsonify({"error": "Missing required parameters"}), 400
        
        if not optimized_firebase:
            return jsonify({"error": "Firebase service not available"}), 503
        
        # Use optimized Firebase service
        similar_books = optimized_firebase.get_similar_books_optimized(user_id, book_id, limit)
        
        return jsonify({"similar_books": similar_books})
        
    except Exception as e:
        print(f"Error in get_similar_books: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

#@app.route('/recommendations')
#def recommendation_page():
    #"""
    #Renders the recommendation page (recommendationPage.html).
    #"""
    #return render_template('recommendationPage.html')

# --- New Optimized API Endpoints ---

@app.route('/api/popular-books', methods=['GET'])
def get_popular_books():
    """
    API endpoint to get popular books based on aggregated ratings (optimized).
    """
    try:
        limit = int(request.args.get('limit', 20))
        
        if not optimized_firebase:
            return jsonify({"error": "Firebase service not available"}), 503
        
        # Use optimized Firebase service
        popular_books = optimized_firebase.get_popular_books_optimized(limit)
        
        return jsonify({"popular_books": popular_books})
        
    except Exception as e:
        print(f"Error in get_popular_books: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/firebase/stats', methods=['GET'])
def get_firebase_stats():
    """
    API endpoint to monitor Firebase usage and cache statistics.
    """
    try:
        if not optimized_firebase:
            return jsonify({"error": "Firebase service not available"}), 503
        
        stats = optimized_firebase.get_cache_stats()
        
        return jsonify({
            "firebase_stats": stats,
            "warning": "High read count detected" if stats['read_count'] > 1000 else None
        })
        
    except Exception as e:
        print(f"Error in get_firebase_stats: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/firebase/reset-stats', methods=['POST'])
def reset_firebase_stats():
    """
    API endpoint to reset Firebase read count (for testing/monitoring).
    """
    try:
        if not optimized_firebase:
            return jsonify({"error": "Firebase service not available"}), 503
        
        optimized_firebase.reset_read_count()
        
        return jsonify({"success": True, "message": "Firebase stats reset"})
        
    except Exception as e:
        print(f"Error in reset_firebase_stats: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """
    API endpoint to clear all Firebase cache (for testing).
    """
    try:
        if not optimized_firebase:
            return jsonify({"error": "Firebase service not available"}), 503
        
        optimized_firebase.clear_all_cache()
        
        return jsonify({"success": True, "message": "Cache cleared"})
        
    except Exception as e:
        print(f"Error in clear_cache: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ----------------- Save Functions ----------------- #
@app.route("/api/tags/save", methods=["POST"])
def save_custom_tags():
    try:
        data = request.json
        user_id = data.get("user_id")
        book_id = data.get("book_id")
        tags = data.get("tags")

        if not user_id or not book_id or not tags:
            return jsonify({"error": "Missing required fields"}), 400

        success = optimized_firebase.save_custom_tags(user_id, book_id, tags)
        return jsonify({"success": success})
    except Exception as e:
        logging.error(f"Error saving custom tags: {e}")
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Ratings
# ----------------------------
@app.route("/api/rating/save", methods=["POST"])
def save_rating_api():
    try:
        data = request.json
        user_id = data.get("user_id")
        book_id = data.get("book_id")
        rating = data.get("rating")
        cover_url = data.get("coverUrl")
        rated_by = data.get("rated_by")

        if not user_id or not book_id or rating is None:
            return jsonify({"error": "Missing required fields"}), 400

        success = optimized_firebase.save_user_rating(
            user_id=user_id,
            book_id=book_id,
            rating=rating,
            cover_url=cover_url,
            rated_by=rated_by
        )
        return jsonify({"success": success})
    except Exception as e:
        logging.error(f"Error saving rating: {e}")
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Custom Tags
# ----------------------------
@app.route("/api/tags/save", methods=["POST"])
def save_custom_tags_api():
    try:
        data = request.json
        user_id = data.get("user_id")
        book_id = data.get("book_id")
        tags = data.get("tags")

        if not user_id or not book_id or not tags:
            return jsonify({"error": "Missing required fields"}), 400

        success = optimized_firebase.save_custom_tags(user_id, book_id, tags)
        return jsonify({"success": success})
    except Exception as e:
        logging.error(f"Error saving custom tags: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/tags/user/<user_id>", methods=["GET"])
def get_user_tags_api(user_id):
    try:
        tags = optimized_firebase.get_all_user_tags(user_id)
        return jsonify({"tags": tags})
    except Exception as e:
        logging.error(f"Error fetching user tags: {e}")
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Recommendations
# ----------------------------
@app.route("/api/recommendations/tags", methods=["POST"])
def recommendations_by_tags():
    try:
        data = request.json
        user_id = data.get("user_id", "anonymous")
        tags = data.get("tags", [])
        limit = data.get("limit", 10)

        recs = optimized_firebase.get_recommendations_by_tags(user_id, tags, limit=limit)
        return jsonify({"recommendations": recs})
    except Exception as e:
        logging.error(f"Error getting tag recommendations: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/recommendations/hybrid", methods=["POST"])
def recommendations_hybrid():
    try:
        data = request.json
        user_id = data.get("user_id", "anonymous")
        tags = data.get("tags", [])
        alpha = float(data.get("alpha", 0.5))
        limit = data.get("limit", 10)

        recs = optimized_firebase.hybrid_recommendation_optimized(user_id, tags, alpha=alpha, limit=limit)
        return jsonify({"recommendations": recs})
    except Exception as e:
        logging.error(f"Error getting hybrid recommendations: {e}")
        return jsonify({"error": str(e)}), 500
    
# ----------------------------
# Recommendation Page (Frontend)
# ----------------------------
from flask import render_template, request

@app.route('/recommendations')
def recommendation_page():
    tag = request.args.get('tag', None)
    return render_template('recommendationPage.html', tag=tag)

# ----------------- Static File Serving ----------------- #
@app.route("/", defaults={"filename": "recommendationpage.html"})
@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(app.root_path, "../client"), filename)

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True, port=8000)
