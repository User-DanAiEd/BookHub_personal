# ==========================================
# BookHub - Book Tracking and Recommendation System
# ==========================================
# This is the main backend server for BookHub, built with Flask.
# It handles book searches, user data, and recommendations.

# Import required libraries
import os  # For file system operations
import pandas as pd  # For data manipulation (reading CSV files)
from flask import Flask, render_template, jsonify, send_from_directory, request  # Flask web framework
import ast  # For safely evaluating string representations of Python objects
import traceback  # For detailed error reporting
import requests  # For making HTTP requests to external APIs
from flask_cors import CORS  # To handle cross-origin requests (important for web apps)
from firebase_recommendations import FirebaseRecommendations  # Our custom Firebase service
import firebase_admin  # Firebase Admin SDK for Python
from firebase_admin import credentials, firestore  # For Firebase credentials and Firestore database

# Create the Flask application
# __name__ tells Flask where to find templates and static files
app = Flask(__name__, template_folder='templates')

# Enable CORS (Cross-Origin Resource Sharing)
# This allows our frontend (running on different ports) to communicate with this backend
CORS(app)

# Path to local book database (optional - for storing books locally)
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), 'book_details.csv')

cred = credentials.Certificate("bookhub-80381-firebase-adminsdk-fbsvc-b3e2365f77.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ==========================================
# EXTERNAL API CONFIGURATION
# ==========================================
# These are the keys and settings for connecting to external book databases
# Google Books API provides comprehensive book information
GOOGLE_BOOKS_API_KEY = "AIzaSyCOP27ymhGqjdwBBjKoeUK53ihZg4xzCzo"

# --- Data Loading from CSV (for existing collection and local search) ---
def load_book_data():
    """
    Loads book data from the book_details.csv file using pandas.
    Returns a list of dictionaries, suitable for JSON serialization.
    Assumes columns: 'title', 'url', 'description', 'genres', 'author', 'price'.
    Parses the 'genres' string column into a Python list.
    """
    try:
        df = pd.read_csv(CSV_FILE_PATH)

        if 'id' not in df.columns:
            df['id'] = 'b' + (df.index + 1).astype(str)

        for col in ['title', 'url', 'description', 'genres', 'author', 'price']:
            if col not in df.columns:
                if col == 'price':
                    df[col] = 0.0
                else:
                    df[col] = ''

        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)

        if 'genres' in df.columns:
            df['genres'] = df['genres'].apply(lambda x: ast.literal_eval(x) if pd.notna(x) and x.strip() else [])
            df['genres'] = df['genres'].apply(lambda x: x if isinstance(x, list) else [])

        return df.to_dict(orient='records')
    except FileNotFoundError:
        print(f"Error: book_details.csv not found at {CSV_FILE_PATH}. Please ensure the file exists at this location.")
        return []
    except pd.errors.EmptyDataError:
        print(f"Warning: book_details.csv at {CSV_FILE_PATH} is empty.")
        return []
    except Exception as e:
        print(f"Error loading book data from CSV: {e}")
        traceback.print_exc()
        return []

# Load all books once when the application starts
all_books_from_csv = load_book_data()

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
                    'cover_url': volume_info.get('imageLinks', {}).get('thumbnail'),
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

        books = []
        if 'docs' in data:
            for doc in data['docs']:
                # Open Library often provides ISBNs in a list
                isbn_13 = next((isbn for isbn in doc.get('isbn', []) if len(isbn) == 13), None)
                isbn_10 = next((isbn for isbn in doc.get('isbn', []) if len(isbn) == 10), None)

                # Open Library cover URLs are based on OLID or ISBN
                cover_url = None
                if doc.get('cover_i'):
                    cover_url = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg"
                elif isbn_13:
                    cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn_13}-M.jpg"
                elif isbn_10:
                    cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn_10}-M.jpg"

                book = {
                    'id': doc.get('key'), # Open Library key (e.g., /works/OL...)
                    'title': doc.get('title'),
                    'author': ', '.join(doc.get('author_name', [])),
                    'description': doc.get('first_sentence', [''])[0], # Often a first sentence
                    'genres': doc.get('subject', []), # Subjects can act as genres
                    'cover_url': cover_url,
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
            if not existing_book.get('cover_url') and ol_book.get('cover_url'):
                existing_book['cover_url'] = ol_book['cover_url']
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
    try:
        data = request.json
        user_id = data.get('user_id')
        email = data.get('email')

        if not user_id or not email:
            return jsonify({"error": "Missing user_id or email"}), 400

        # Store or update user info in Firestore
        user_ref = db.collection('users').document(user_id)
        user_ref.set({
            'email': email
        }, merge=True)

        return jsonify({"success": True, "message": "User info saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

# --- New Route for Recommendations ---
@app.route('/api/recommendations', methods=['POST'])
def recommendations_endpoint():
    """
    API endpoint to receive user books and return recommendations.
    """
    user_books = request.json.get('userBooks', [])

    if not user_books:
        return jsonify({"error": "No user books provided"}), 400
    
    # We will dynamically create candidate_books by searching for books
    # that match the tags from the user's books.
    user_tags = set()
    for book in user_books:
      user_tags.update(book.get('tags', []))
      
    candidate_books = []
    for tag in user_tags:
        # Search external APIs for books with the user's custom tags as a query
        google_results = search_google_books(tag)
        open_library_results = search_open_library(tag)
        combined = normalize_and_deduplicate_books(google_results, open_library_results)
        # Add a new 'tags' field to the candidate books using the fetched genres
        for book in combined:
            book['tags'] = book.get('genres', []) # Use 'genres' as 'tags' for consistency
        candidate_books.extend(combined)

    # Now, run the recommender with the user's books and the dynamically generated candidate books
    recommendations = FirebaseRecommendations(user_books, candidate_books)
    
    # Return the recommendations as a JSON response
    return jsonify(recommendations)

@app.route('/books')
def get_books_json():
    """
    API endpoint to return the list of all books loaded from the local CSV.
    This is primarily for internal use or if you want to display local CSV books
    separately from online search results.
    """
    if not all_books_from_csv:
        print("Warning: Attempted to serve books, but all_books_from_csv is empty. Check CSV loading at startup.")
        return jsonify({"error": "No book data available. Check server logs."}), 500
    return jsonify(all_books_from_csv)

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
    
    # Optionally, you can sort the results, e.g., by average_rating or title
    # combined_results.sort(key=lambda x: x.get('average_rating', 0), reverse=True)

    return jsonify(combined_results)

# --- New API Endpoints for Custom Tags and Recommendations ---

@app.route('/api/tags/save', methods=['POST'])
def save_custom_tags():
    """
    API endpoint to save custom tags for a book to Firebase.
    """
    try:
        data = request.json
        user_id = data.get('user_id')
        book_id = data.get('book_id')
        tags = data.get('tags', [])
        
        if not user_id or not book_id or not tags:
            return jsonify({"error": "Missing required parameters"}), 400
        
        # Path to your Firebase service account JSON key file
        SERVICE_ACCOUNT_PATH = "server/admin_credentials.json"

        # Initialize Firebase recommendations service
        firebase_rec = FirebaseRecommendations(project_id='bookhub-80381', credentials_path=SERVICE_ACCOUNT_PATH)
        
        # Save tags to Firebase
        success = firebase_rec.save_custom_tags(user_id, book_id, tags)
        
        if success:
            return jsonify({"success": True, "message": "Tags saved successfully"})
        else:
            return jsonify({"error": "Failed to save tags"}), 500
            
    except Exception as e:
        print(f"Error in save_custom_tags: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendations/by-tags', methods=['GET'])
def get_recommendations_by_tags():
    """
    API endpoint to get book recommendations based on custom tags.
    """
    try:
        user_id = request.args.get('user_id')
        tags = request.args.get('tags', '').split(',')
        limit = int(request.args.get('limit', 10))
        
        if not user_id or not tags or tags == ['']:
            return jsonify({"error": "Missing required parameters"}), 400
        
        # Initialize Firebase recommendations service
        firebase_rec = FirebaseRecommendations('bookhub-80381')
        
        # Get recommendations based on tags
        recommendations = firebase_rec.get_recommendations_by_tags(user_id, tags, limit)
        
        return jsonify({"recommendations": recommendations})
        
    except Exception as e:
        print(f"Error in get_recommendations_by_tags: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendations/similar/<book_id>', methods=['GET'])
def get_similar_books(book_id):
    """
    API endpoint to get similar books based on tags from a specific book.
    """
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 5))
        
        if not user_id or not book_id:
            return jsonify({"error": "Missing required parameters"}), 400
        
        # Initialize Firebase recommendations service
        firebase_rec = FirebaseRecommendations('bookhub-80381')
        
        # Get similar books based on tags
        similar_books = firebase_rec.get_similar_books_by_tags(user_id, book_id, limit)
        
        return jsonify({"similar_books": similar_books})
        
    except Exception as e:
        print(f"Error in get_similar_books: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/tags/user/<user_id>', methods=['GET'])
def get_user_tags(user_id):
    """
    API endpoint to get all unique custom tags from a user's books.
    """
    try:
        if not user_id:
            return jsonify({"error": "Missing user_id parameter"}), 400

        # Initialize Firebase recommendations service
        firebase_rec = FirebaseRecommendations('bookhub-80381')

        # Get all user tags
        tags = firebase_rec.get_all_user_tags(user_id)

        return jsonify({"tags": tags})

    except Exception as e:
        print(f"Error in get_user_tags: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/rating/save', methods=['POST'])
def save_rating():
    """
    API endpoint to save user rating for a book.
    """
    try:
        data = request.json
        user_id = data.get('user_id')
        book_id = data.get('book_id')
        rating = data.get('rating')

        if not user_id or not book_id or rating is None:
            return jsonify({"error": "Missing required parameters"}), 400

        if not isinstance(rating, int) or not (1 <= rating <= 5):
            return jsonify({"error": "Rating must be an integer between 1 and 5"}), 400

        # Initialize Firebase recommendations service
        firebase_rec = FirebaseRecommendations('bookhub-80381')

        # Save rating to Firebase
        success = firebase_rec.save_user_rating(user_id, book_id, rating)

        if success:
            return jsonify({"success": True, "message": "Rating saved successfully"})
        else:
            return jsonify({"error": "Failed to save rating"}), 500

    except Exception as e:
        print(f"Error in save_rating: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendations/hybrid', methods=['GET'])
def hybrid_recommendations():
    """
    API endpoint to get hybrid recommendations combining content-based and collaborative filtering.
    """
    try:
        user_id = request.args.get('user_id')
        tags = request.args.get('tags', '').split(',')
        alpha = float(request.args.get('alpha', 0.5))
        limit = int(request.args.get('limit', 10))

        if not user_id or not tags or tags == ['']:
            return jsonify({"error": "Missing required parameters"}), 400

        if not (0 <= alpha <= 1):
            return jsonify({"error": "Alpha must be between 0 and 1"}), 400

        # Initialize Firebase recommendations service
        firebase_rec = FirebaseRecommendations('bookhub-80381')

        # Get hybrid recommendations
        recommendations = firebase_rec.get_hybrid_recommendations(user_id, tags, alpha, limit)

        return jsonify({"recommendations": recommendations})

    except Exception as e:
        print(f"Error in hybrid_recommendations: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/<path:filename>')
def serve_static(filename):
    """
    Serves static files (like CSS, JS, images) from the root directory.
    This is a fallback and generally, static files are served from a 'static' folder.
    However, if your HTML refers to files directly in the root, this will serve them.
    """
    return send_from_directory('.', filename)

if __name__ == '__main__':
    app.run(debug=True, port=8000)
