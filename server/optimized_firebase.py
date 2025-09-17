import firebase_admin
from firebase_admin import credentials, firestore
import json
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
import pandas as pd
import time
from functools import lru_cache
import threading

class OptimizedFirebaseService:
    def __init__(self, project_id: str, credentials_path: str = None):
        """Initialize optimized Firebase service with caching and read monitoring"""
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.db = None
        self._initialize_firebase()
        
        # Advanced caching with TTL
        self._cache = {}
        self._cache_ttl = {}
        self._cache_lock = threading.Lock()
        self._default_ttl = 300  # 5 minutes
        
        # Read monitoring
        self._read_count = 0
        self._read_limit_warning = 1000  # Warn at 1000 reads per session
        
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            if not firebase_admin._apps:
                if self.credentials_path:
                    cred = credentials.Certificate(self.credentials_path)
                else:
                    cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {
                    'projectId': self.project_id
                })
            self.db = firestore.client()
        except Exception as e:
            print(f"Error initializing Firebase: {e}")

    def _increment_read_count(self, count: int = 1):
        """Monitor Firebase read operations"""
        self._read_count += count
        if self._read_count >= self._read_limit_warning:
            print(f"WARNING: High Firebase read count: {self._read_count}")

    def _get_cache_key(self, *args) -> str:
        """Generate cache key from arguments"""
        return ":".join(str(arg) for arg in args)

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self._cache_lock:
            if key in self._cache:
                if time.time() < self._cache_ttl.get(key, 0):
                    return self._cache[key]
                else:
                    # Expired, remove from cache
                    del self._cache[key]
                    if key in self._cache_ttl:
                        del self._cache_ttl[key]
        return None

    def _set_cache(self, key: str, value: Any, ttl: int = None):
        """Set value in cache with TTL"""
        if ttl is None:
            ttl = self._default_ttl
        with self._cache_lock:
            self._cache[key] = value
            self._cache_ttl[key] = time.time() + ttl

    def get_user_tracked_books_optimized(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's tracked books with caching and limits"""
        cache_key = self._get_cache_key("user_books", user_id, limit)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # Use limit to prevent excessive reads
            tracked_books_ref = (self.db.collection('artifacts')
                               .document(self.project_id)
                               .collection('users')
                               .document(user_id)
                               .collection('tracked_books')
                               .limit(limit))
            
            books = []
            docs = tracked_books_ref.stream()
            read_count = 0
            
            for doc in docs:
                books.append({
                    'id': doc.id,
                    **doc.to_dict()
                })
                read_count += 1
            
            self._increment_read_count(read_count)
            self._set_cache(cache_key, books, ttl=600)  # Cache for 10 minutes
            return books
            
        except Exception as e:
            print(f"Error getting user tracked books: {e}")
            return []

    def get_recommendations_by_tags_optimized(self, tags: List[str], limit: int = 10, user_id: str = None) -> List[Dict[str, Any]]:
        """Optimized tag-based recommendations with caching"""
        if not tags:
            return []
            
        cache_key = self._get_cache_key("tag_recs", sorted(tags), limit, user_id)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # Limit tags to prevent query complexity
            filter_tags = list(set(tags))[:10]
            
            recommendations = []
            seen_books = set()
            
            # Use collection group query with limit
            query = (self.db.collection_group('tracked_books')
                    .where('customTags', 'array_contains_any', filter_tags)
                    .limit(limit * 2))  # Get more than needed for deduplication
            
            docs = query.stream()
            read_count = 0
            
            for doc in docs:
                if len(recommendations) >= limit:
                    break
                    
                data = doc.to_dict() or {}
                book_id = data.get('id') or doc.id
                
                if book_id in seen_books:
                    continue
                seen_books.add(book_id)
                
                # Skip user's own books if user_id provided
                try:
                    owner_id = doc.reference.parent.parent.id if doc.reference.parent and doc.reference.parent.parent else None
                    if user_id and owner_id == user_id:
                        continue
                except:
                    pass
                
                recommendations.append({
                    'id': book_id,
                    'title': data.get('title', 'Unknown'),
                    'author': data.get('author', 'Unknown'),
                    'coverUrl': data.get('coverUrl', ''),
                    'customTags': data.get('customTags', []),
                    'rating': data.get('rating', 0),
                    'owner': owner_id
                })
                read_count += 1
            
            self._increment_read_count(read_count)
            self._set_cache(cache_key, recommendations, ttl=300)  # Cache for 5 minutes
            return recommendations
            
        except Exception as e:
            print(f"Error getting recommendations by tags: {e}")
            return []

    def get_user_ratings_optimized(self, user_id: str) -> Dict[str, int]:
        """Get user's ratings with caching"""
        cache_key = self._get_cache_key("user_ratings", user_id)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            ratings = {}
            # Query only books with ratings
            query = (self.db.collection('artifacts')
                    .document(self.project_id)
                    .collection('users')
                    .document(user_id)
                    .collection('tracked_books')
                    .where('rating', '>', 0)
                    .limit(100))  # Reasonable limit
            
            docs = query.stream()
            read_count = 0
            
            for doc in docs:
                data = doc.to_dict()
                rating = data.get('rating')
                if rating:
                    ratings[doc.id] = rating
                read_count += 1
            
            self._increment_read_count(read_count)
            self._set_cache(cache_key, ratings, ttl=600)  # Cache for 10 minutes
            return ratings
            
        except Exception as e:
            print(f"Error getting user ratings: {e}")
            return {}

    def get_collaborative_data_optimized(self, limit_users: int = 50) -> Dict[str, Dict[str, int]]:
        """Get collaborative filtering data with strict limits"""
        cache_key = self._get_cache_key("collab_data", limit_users)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            user_ratings = {}
            
            # Limit number of users to process
            users_query = (self.db.collection('artifacts')
                          .document(self.project_id)
                          .collection('users')
                          .limit(limit_users))
            
            users = users_query.stream()
            read_count = 1  # Count the users query
            
            for user_doc in users:
                user_id = user_doc.id
                
                # Get only rated books for this user
                ratings_query = (user_doc.reference
                               .collection('tracked_books')
                               .where('rating', '>', 0)
                               .limit(50))  # Limit books per user
                
                user_book_ratings = {}
                books = ratings_query.stream()
                
                for book_doc in books:
                    data = book_doc.to_dict()
                    rating = data.get('rating')
                    if rating:
                        user_book_ratings[book_doc.id] = rating
                    read_count += 1
                
                if user_book_ratings:
                    user_ratings[user_id] = user_book_ratings
            
            self._increment_read_count(read_count)
            self._set_cache(cache_key, user_ratings, ttl=1800)  # Cache for 30 minutes
            return user_ratings
            
        except Exception as e:
            print(f"Error getting collaborative data: {e}")
            return {}

    def hybrid_recommendation_optimized(self, user_id: str, tags: List[str], alpha: float = 0.5, limit: int = 10) -> List[Dict[str, Any]]:
        """Optimized hybrid recommendations with minimal Firebase reads"""
        try:
            recommendations = {}
            
            # 1. Content-based recommendations (cached)
            if tags:
                content_recs = self.get_recommendations_by_tags_optimized(tags, limit * 2, user_id)
                for rec in content_recs:
                    book_id = rec['id']
                    recommendations[book_id] = {
                        **rec,
                        'content_score': len(set(tags) & set(rec.get('customTags', []))) / len(tags) if tags else 0,
                        'collab_score': 0,
                        'source': 'content'
                    }
            
            # 2. Collaborative filtering (cached, limited)
            if alpha > 0:
                user_ratings = self.get_user_ratings_optimized(user_id)
                if user_ratings:
                    # Get limited collaborative data
                    collab_data = self.get_collaborative_data_optimized(limit_users=30)
                    
                    # Simple collaborative scoring
                    for other_user_id, other_ratings in collab_data.items():
                        if other_user_id == user_id:
                            continue
                            
                        # Find common books
                        common_books = set(user_ratings.keys()) & set(other_ratings.keys())
                        if len(common_books) >= 2:  # Need some overlap
                            # Calculate similarity (simplified)
                            similarity = len(common_books) / (len(user_ratings) + len(other_ratings) - len(common_books))
                            
                            # Recommend books this similar user liked
                            for book_id, rating in other_ratings.items():
                                if book_id not in user_ratings and rating >= 4:  # Only high-rated books
                                    if book_id not in recommendations:
                                        recommendations[book_id] = {
                                            'id': book_id,
                                            'title': f'Book {book_id}',
                                            'author': 'Unknown',
                                            'coverUrl': '',
                                            'content_score': 0,
                                            'collab_score': 0,
                                            'source': 'collaborative'
                                        }
                                    recommendations[book_id]['collab_score'] += similarity * (rating / 5.0)
            
            # 3. Calculate hybrid scores
            final_recs = []
            for book_id, rec in recommendations.items():
                hybrid_score = (1 - alpha) * rec['content_score'] + alpha * rec['collab_score']
                rec['hybrid_score'] = round(hybrid_score, 3)
                final_recs.append(rec)
            
            # Sort by hybrid score
            final_recs.sort(key=lambda x: x['hybrid_score'], reverse=True)
            return final_recs[:limit]
            
        except Exception as e:
            print(f"Error in optimized hybrid recommendations: {e}")
            return []

    def save_custom_tags_optimized(self, user_id: str, book_id: str, tags: List[str]) -> bool:
        """Save custom tags with minimal reads"""
        try:
            book_ref = (self.db.collection('artifacts')
                       .document(self.project_id)
                       .collection('users')
                       .document(user_id)
                       .collection('tracked_books')
                       .document(book_id))
            
            # Use set with merge to avoid reading first
            book_ref.set({'customTags': tags}, merge=True)
            
            # Clear related caches
            self._clear_user_cache(user_id)
            return True
            
        except Exception as e:
            print(f"Error saving custom tags: {e}")
            return False

    def save_user_rating_optimized(self, user_id: str, book_id: str, rating: int, 
                                 coverUrl: str = None, rated_by: str = None) -> bool:
        """Save user rating with optimized aggregation"""
        try:
            # Save user's rating
            user_book_ref = (self.db.collection('artifacts')
                           .document(self.project_id)
                           .collection('users')
                           .document(user_id)
                           .collection('tracked_books')
                           .document(book_id))
            
            update_data = {'rating': rating}
            if coverUrl:
                update_data['coverUrl'] = coverUrl
            if rated_by:
                update_data['rated_by'] = rated_by
                
            user_book_ref.set(update_data, merge=True)
            
            # Update global book stats using transaction (atomic)
            self._update_book_rating_stats(book_id, rating)
            
            # Clear related caches
            self._clear_user_cache(user_id)
            return True
            
        except Exception as e:
            print(f"Error saving user rating: {e}")
            return False

    def _update_book_rating_stats(self, book_id: str, new_rating: int):
        """Update book rating statistics atomically"""
        try:
            book_stats_ref = self.db.collection('book_stats').document(book_id)
            
            @firestore.transactional
            def update_stats(transaction):
                doc = book_stats_ref.get(transaction=transaction)
                self._increment_read_count(1)
                
                if doc.exists:
                    data = doc.to_dict()
                    total_rating = data.get('total_rating', 0)
                    rating_count = data.get('rating_count', 0)
                    
                    new_total = total_rating + new_rating
                    new_count = rating_count + 1
                    avg_rating = new_total / new_count
                    
                    transaction.set(book_stats_ref, {
                        'total_rating': new_total,
                        'rating_count': new_count,
                        'avg_rating': round(avg_rating, 2)
                    })
                else:
                    transaction.set(book_stats_ref, {
                        'total_rating': new_rating,
                        'rating_count': 1,
                        'avg_rating': new_rating
                    })
            
            transaction = self.db.transaction()
            update_stats(transaction)
            
        except Exception as e:
            print(f"Error updating book rating stats: {e}")

    def get_user_tags_optimized(self, user_id: str) -> List[str]:
        """Get all user's tags with caching"""
        cache_key = self._get_cache_key("user_tags", user_id)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # Query only books with customTags
            query = (self.db.collection('artifacts')
                    .document(self.project_id)
                    .collection('users')
                    .document(user_id)
                    .collection('tracked_books')
                    .where('customTags', '!=', [])
                    .limit(100))
            
            all_tags = set()
            docs = query.stream()
            read_count = 0
            
            for doc in docs:
                data = doc.to_dict()
                tags = data.get('customTags', [])
                all_tags.update(tags)
                read_count += 1
            
            self._increment_read_count(read_count)
            result = list(all_tags)
            self._set_cache(cache_key, result, ttl=900)  # Cache for 15 minutes
            return result
            
        except Exception as e:
            print(f"Error getting user tags: {e}")
            return []

    def get_popular_books_optimized(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get popular books based on aggregated stats"""
        cache_key = self._get_cache_key("popular_books", limit)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # Query book stats ordered by rating
            query = (self.db.collection('book_stats')
                    .where('rating_count', '>=', 2)  # At least 2 ratings
                    .order_by('avg_rating', direction=firestore.Query.DESCENDING)
                    .limit(limit))
            
            popular_books = []
            docs = query.stream()
            read_count = 0
            
            for doc in docs:
                data = doc.to_dict()
                popular_books.append({
                    'id': doc.id,
                    'avg_rating': data.get('avg_rating', 0),
                    'rating_count': data.get('rating_count', 0),
                    'title': data.get('title', f'Book {doc.id}'),
                    'author': data.get('author', 'Unknown'),
                    'coverUrl': data.get('coverUrl', '')
                })
                read_count += 1
            
            self._increment_read_count(read_count)
            self._set_cache(cache_key, popular_books, ttl=1800)  # Cache for 30 minutes
            return popular_books
            
        except Exception as e:
            print(f"Error getting popular books: {e}")
            return []

    def get_similar_books_optimized(self, user_id: str, book_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get similar books based on tags with optimization"""
        try:
            # First get the book's tags
            book_ref = (self.db.collection('artifacts')
                       .document(self.project_id)
                       .collection('users')
                       .document(user_id)
                       .collection('tracked_books')
                       .document(book_id))
            
            book_doc = book_ref.get()
            self._increment_read_count(1)
            
            if not book_doc.exists:
                return []
            
            book_data = book_doc.to_dict()
            book_tags = book_data.get('customTags', [])
            
            if not book_tags:
                return []
            
            # Get recommendations based on these tags
            similar_books = self.get_recommendations_by_tags_optimized(book_tags, limit, user_id)
            return similar_books
            
        except Exception as e:
            print(f"Error getting similar books: {e}")
            return []

    def _clear_user_cache(self, user_id: str):
        """Clear cache entries related to a specific user"""
        with self._cache_lock:
            keys_to_remove = []
            for key in self._cache.keys():
                if f":{user_id}:" in key or key.endswith(f":{user_id}"):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
                if key in self._cache_ttl:
                    del self._cache_ttl[key]

    def clear_all_cache(self):
        """Clear all cache (useful for testing)"""
        with self._cache_lock:
            self._cache.clear()
            self._cache_ttl.clear()

    def get_read_count(self) -> int:
        """Get current read count for monitoring"""
        return self._read_count

    def reset_read_count(self):
        """Reset read count (useful for testing)"""
        self._read_count = 0

    def batch_get_book_details(self, book_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get multiple book details in a single optimized operation"""
        if not book_ids:
            return {}
            
        cache_key = self._get_cache_key("batch_books", sorted(book_ids))
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            book_details = {}
            
            # Use collection group query to find books across all users
            # Limit to prevent excessive reads
            query = (self.db.collection_group('tracked_books')
                    .where(firestore.FieldPath.document_id(), 'in', book_ids[:10])  # Firestore 'in' limit is 10
                    .limit(20))
            
            docs = query.stream()
            read_count = 0
            
            for doc in docs:
                data = doc.to_dict()
                book_details[doc.id] = {
                    'id': doc.id,
                    'title': data.get('title', 'Unknown'),
                    'author': data.get('author', 'Unknown'),
                    'coverUrl': data.get('coverUrl', ''),
                    'customTags': data.get('customTags', []),
                    'rating': data.get('rating', 0)
                }
                read_count += 1
            
            self._increment_read_count(read_count)
            self._set_cache(cache_key, book_details, ttl=600)
            return book_details
            
        except Exception as e:
            print(f"Error batch getting book details: {e}")
            return {}

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        with self._cache_lock:
            active_entries = sum(1 for key in self._cache_ttl.keys() 
                               if time.time() < self._cache_ttl[key])
            return {
                'total_entries': len(self._cache),
                'active_entries': active_entries,
                'expired_entries': len(self._cache) - active_entries,
                'read_count': self._read_count
            }
