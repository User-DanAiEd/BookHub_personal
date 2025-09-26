import firebase_admin
from firebase_admin import credentials, firestore
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer


class FirebaseRecommender:
    def __init__(self, service_account_path: str):
        self._initialize_firebase(service_account_path)
        self.db = firestore.client()

    # ---------------- Firebase Init ---------------- #
    def _initialize_firebase(self, service_account_path: str):
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)

    # ---------------- Save Functions ---------------- #
    def save_custom_tags(self, user_id: str, book_id: str, tags: List[str]) -> bool:
        """Save or update user’s custom tags for a tracked book."""
        try:
            ref = self.db.collection("users").document(user_id).collection("tracked_books").document(book_id)
            ref.set({"customTags": tags}, merge=True)
            return True
        except Exception as e:
            print(f"Error saving custom tags: {e}")
            return False

    def save_user_rating(
        self, user_id: str, book_id: str, rating: int,
        cover_url: Optional[str] = None, rated_by: Optional[str] = None
    ) -> bool:
        """Save or update user’s rating for a tracked book."""
        try:
            ref = self.db.collection("users").document(user_id).collection("tracked_books").document(book_id)
            data = {
                "rating": rating,
                "ratedBy": rated_by,
            }
            if cover_url:
                data["coverUrl"] = cover_url
            ref.set(data, merge=True)
            return True
        except Exception as e:
            print(f"Error saving rating: {e}")
            return False

    # ---------------- Utility Functions ---------------- #
    def _build_tag_matrix(self) -> (List[str], np.ndarray):
        """Build a co-occurrence matrix of all tags across users/books."""
        tags_corpus = []
        books_ref = self.db.collection_group("tracked_books").stream()
        for book in books_ref:
            data = book.to_dict()
            if "customTags" in data and data["customTags"]:
                tags_corpus.append(" ".join(data["customTags"]))

        if not tags_corpus:
            return [], np.array([])

        vectorizer = CountVectorizer()
        tag_matrix = vectorizer.fit_transform(tags_corpus).toarray()
        return vectorizer.get_feature_names_out(), tag_matrix

    def expand_tags_with_cosine(self, input_tags: List[str], top_n: int = 5) -> List[str]:
        """Expand input tags using cosine similarity on co-occurrence matrix."""
        vocab, tag_matrix = self._build_tag_matrix()
        if not vocab or tag_matrix.size == 0:
            return input_tags

        cosine_sim = cosine_similarity(tag_matrix.T)
        tag_index = {tag: i for i, tag in enumerate(vocab)}

        expanded_tags = set(input_tags)
        for tag in input_tags:
            if tag in tag_index:
                idx = tag_index[tag]
                sim_scores = list(enumerate(cosine_sim[idx]))
                sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
                for j, score in sim_scores[:top_n]:
                    expanded_tags.add(vocab[j])
        return list(expanded_tags)

    # ---------------- Recommendations ---------------- #
    def get_recommendations_by_tags(self, user_id: str, tags: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """Get hybrid recommendations using expanded tags + collaborative ratings."""
        expanded_tags = self.expand_tags_with_cosine(tags)

        # Step 1: Fetch all the books with any matching tags
        books = []
        books_ref = self.db.collection_group("tracked_books").stream()
        for book in books_ref:
            data = book.to_dict()
            data["bookId"] = book.id
            if "customTags" in data:
                if any(tag in data["customTags"] for tag in expanded_tags):
                    books.append(data)

        if not books:
            return []

        # Step 2: Aggregate all the ratings across all users
        rating_map = defaultdict(list)
        for book in books:
            if "rating" in book:
                rating_map[book["bookId"]].append(book["rating"])

        recommendations = []
        for book in books:
            avg_rating = None
            if book["bookId"] in rating_map:
                avg_rating = np.mean(rating_map[book["bookId"]])

            recommendations.append({
                "bookId": book.get("bookId"),
                "title": book.get("title"),
                "author": book.get("author"),
                "coverUrl": book.get("coverUrl"),
                "isbn10": book.get("isbn10"),
                "isbn13": book.get("isbn13"),
                "genres": book.get("genres"),
                "description": book.get("description"),
                "avgRating": avg_rating,
                "customTags": book.get("customTags", []),
            })

        # Step 3: Sort them by average rating, fallback to addedAt if needed
        recommendations = sorted(
            recommendations,
            key=lambda x: (x["avgRating"] if x["avgRating"] else 0),
            reverse=True
        )

        return recommendations[:limit]

    def get_all_user_tags(self, user_id: str) -> List[str]:
        """Fetch all unique custom tags the user has created."""
        tags = set()
        ref = self.db.collection("users").document(user_id).collection("tracked_books").stream()
        for book in ref:
            data = book.to_dict()
            if "customTags" in data:
                tags.update(data["customTags"])
        return list(tags)
