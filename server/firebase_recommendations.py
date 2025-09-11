import firebase_admin
from firebase_admin import credentials, firestore
import json
from typing import List, Dict, Any
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
import pandas as pd

class FirebaseRecommendations:
    def __init__(self, project_id: str, credentials_path: str = None):
        """Initialize Firebase Admin SDK for recommendations"""
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.db = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            print(f"Initializing Firebase with credentials_path: {self.credentials_path}")
            # Check if already initialized
            if not firebase_admin._apps:
                if self.credentials_path:
                    print(f"Loading credentials from file: {self.credentials_path}")
                    cred = credentials.Certificate(self.credentials_path)
                else:
                    print("Loading Application Default Credentials")
                    cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {
                    'projectId': self.project_id
                })
            self.db = firestore.client()
            print("Firebase initialized successfully.")
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
    
    def save_custom_tags(self, user_id: str, book_id: str, tags: List[str]) -> bool:
        """Save custom tags for a book to Firebase"""
        try:
            book_ref = self.db.collection('artifacts').document(self.project_id).collection('users').document(user_id).collection('tracked_books').document(book_id)
            book_ref.update({'customTags': tags})
            return True
        except Exception as e:
            print(f"Error saving custom tags: {e}")
            return False
    
    def get_recommendations_by_tags(self, user_id: str, tags: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """Get book recommendations based on custom tags"""
        try:
            books_ref = self.db.collection('artifacts').document(self.project_id).collection('users').document(user_id).collection('tracked_books')
            
            # Query books that contain any of the specified tags
            recommendations = []
            for tag in tags:
                query = books_ref.where('customTags', 'array_contains', tag).limit(limit)
                docs = query.stream()
                
                for doc in docs:
                    book_data = doc.to_dict()
                    book_data['id'] = doc.id
                    if book_data not in recommendations:
                        recommendations.append(book_data)
            
            return recommendations
        except Exception as e:
            print(f"Error getting recommendations by tags: {e}")
            return []
    
    def get_similar_books_by_tags(self, user_id: str, book_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get similar books based on tags from a specific book"""
        try:
            # Get the book's tags
            book_ref = self.db.collection('artifacts').document(self.project_id).collection('users').document(user_id).collection('tracked_books').document(book_id)
            book_doc = book_ref.get()
            
            if not book_doc.exists:
                return []
            
            book_data = book_doc.to_dict()
            tags = book_data.get('customTags', [])
            
            if not tags:
                return []
            
            # Get recommendations based on these tags
            return self.get_recommendations_by_tags(user_id, tags, limit)
        except Exception as e:
            print(f"Error getting similar books: {e}")
            return []
    
    def get_all_user_tags(self, user_id: str) -> List[str]:
        """Get all unique custom tags from user's books"""
        try:
            books_ref = self.db.collection('artifacts').document(self.project_id).collection('users').document(user_id).collection('tracked_books')
            docs = books_ref.stream()

            all_tags = set()
            for doc in docs:
                book_data = doc.to_dict()
                tags = book_data.get('customTags', [])
                all_tags.update(tags)

            return list(all_tags)
        except Exception as e:
            print(f"Error getting all user tags: {e}")
            return []

    def save_user_rating(self, user_id: str, book_id: str, rating: int) -> bool:
        """Save user rating for a book to Firebase"""
        try:
            if not (1 <= rating <= 5):
                print(f"Invalid rating: {rating}. Must be between 1 and 5.")
                return False

            book_ref = self.db.collection('artifacts').document(self.project_id).collection('users').document(user_id).collection('tracked_books').document(book_id)
            book_ref.update({'rating': rating})
            return True
        except Exception as e:
            print(f"Error saving user rating: {e}")
            return False

    def get_user_item_matrix(self) -> pd.DataFrame:
        """Build user-item matrix from ratings"""
        try:
            users_ref = self.db.collection('artifacts').document(self.project_id).collection('users')
            users = users_ref.stream()

            data = []
            for user_doc in users:
                user_id = user_doc.id
                books_ref = user_doc.reference.collection('tracked_books')
                books = books_ref.stream()

                for book_doc in books:
                    rating = book_doc.to_dict().get('rating', 0)
                    if rating > 0:
                        data.append({'user_id': user_id, 'book_id': book_doc.id, 'rating': rating})

            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame()

            return df.pivot(index='user_id', columns='book_id', values='rating').fillna(0)
        except Exception as e:
            print(f"Error building user-item matrix: {e}")
            return pd.DataFrame()

    def get_item_similarity_matrix(self, user_item_matrix: pd.DataFrame) -> np.ndarray:
        """Calculate item-item similarity using cosine similarity"""
        try:
            if user_item_matrix.empty:
                return np.array([])

            # Transpose for item-item similarity
            item_user_matrix = user_item_matrix.T
            similarity = cosine_similarity(item_user_matrix)
            return similarity
        except Exception as e:
            print(f"Error calculating similarity matrix: {e}")
            return np.array([])

    def get_collaborative_recommendations(self, user_id: str, user_item_matrix: pd.DataFrame, similarity_matrix: np.ndarray, top_n: int = 10) -> List[str]:
        """Get collaborative recommendations for a user"""
        try:
            if user_id not in user_item_matrix.index or similarity_matrix.size == 0:
                return []

            user_ratings = user_item_matrix.loc[user_id]
            rated_items = user_ratings[user_ratings > 0].index

            scores = defaultdict(float)
            for item in rated_items:
                item_idx = user_item_matrix.columns.get_loc(item)
                similar_items = np.argsort(similarity_matrix[item_idx])[::-1][1:top_n+1]  # Exclude self

                for sim_idx in similar_items:
                    sim_item = user_item_matrix.columns[sim_idx]
                    if sim_item not in rated_items:
                        scores[sim_item] += similarity_matrix[item_idx, sim_idx] * user_ratings[item]

            # Sort by score and return top recommendations
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            return [item for item, score in sorted_scores[:top_n]]
        except Exception as e:
            print(f"Error getting collaborative recommendations: {e}")
            return []

    def get_hybrid_recommendations(self, user_id: str, content_tags: List[str], alpha: float = 0.5, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get hybrid recommendations combining content-based and collaborative filtering
        alpha: weight for collaborative (1-alpha for content-based)
        """
        try:
            # Get content-based recommendations
            content_recs = self.get_recommendations_by_tags(user_id, content_tags, limit * 2)

            # Get collaborative recommendations
            user_item_matrix = self.get_user_item_matrix()
            if not user_item_matrix.empty:
                similarity_matrix = self.get_item_similarity_matrix(user_item_matrix)
                collab_book_ids = self.get_collaborative_recommendations(user_id, user_item_matrix, similarity_matrix, limit * 2)

                # Fetch book details for collaborative recs
                collab_recs = []
                for book_id in collab_book_ids:
                    try:
                        book_ref = self.db.collection('artifacts').document(self.project_id).collection('users').document(user_id).collection('tracked_books').document(book_id)
                        book_doc = book_ref.get()
                        if book_doc.exists:
                            book_data = book_doc.to_dict()
                            book_data['id'] = book_id
                            collab_recs.append(book_data)
                    except:
                        continue
            else:
                collab_recs = []

            # Combine and rank
            combined = {}
            for rec in content_recs:
                combined[rec['id']] = {'book': rec, 'content_score': 1, 'collab_score': 0}

            for rec in collab_recs:
                if rec['id'] in combined:
                    combined[rec['id']]['collab_score'] = 1
                else:
                    combined[rec['id']] = {'book': rec, 'content_score': 0, 'collab_score': 1}

            # Calculate hybrid scores
            for book_id, data in combined.items():
                data['hybrid_score'] = alpha * data['collab_score'] + (1 - alpha) * data['content_score']

            # Sort by hybrid score and return top recommendations
            sorted_recs = sorted(combined.values(), key=lambda x: x['hybrid_score'], reverse=True)
            return [item['book'] for item in sorted_recs[:limit]]
        except Exception as e:
            print(f"Error getting hybrid recommendations: {e}")
            # Fallback to content-based only
            return self.get_recommendations_by_tags(user_id, content_tags, limit)
