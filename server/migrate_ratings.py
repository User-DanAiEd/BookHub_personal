import firebase_admin
from firebase_admin import credentials, firestore
import numpy as np
from collections import defaultdict
import time

class RatingMigrationService:
    def __init__(self, service_account_path: str):
        self.service_account_path = service_account_path
        self._initialize_firebase()
        self.db = firestore.client()

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.service_account_path)
            firebase_admin.initialize_app(cred, {
                'projectId': 'bookhub-80381'
            })

    def migrate_ratings_to_stats(self):
        """Migrate existing user ratings to book_stats collection"""
        print("Starting rating migration...")

        # Get all users
        users_ref = self.db.collection('users')
        users = users_ref.stream()

        total_books = 0
        migrated_books = 0

        for user_doc in users:
            user_id = user_doc.id
            print(f"Processing user: {user_id}")

            # Get all books for this user
            books_ref = self.db.collection('users').document(user_id).collection('tracked_books')
            books = books_ref.stream()

            for book_doc in books:
                book_data = book_doc.to_dict()
                book_id = book_doc.id

                if 'rating' in book_data and book_data['rating'] > 0:
                    rating = book_data['rating']
                    total_books += 1

                    # Update book stats atomically
                    self._update_book_stats(book_id, rating)
                    migrated_books += 1

                    if migrated_books % 100 == 0:
                        print(f"Migrated {migrated_books} books so far...")

        print(f"Migration complete! Processed {total_books} total ratings, migrated {migrated_books} books.")

    def _update_book_stats(self, book_id: str, new_rating: int):
        """Update book rating statistics atomically"""
        try:
            book_stats_ref = self.db.collection('book_stats').document(book_id)

            @firestore.transactional
            def update_stats(transaction):
                doc = book_stats_ref.get(transaction=transaction)

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
                        'avg_rating': round(avg_rating, 2),
                        'last_updated': firestore.SERVER_TIMESTAMP
                    })
                else:
                    transaction.set(book_stats_ref, {
                        'total_rating': new_rating,
                        'rating_count': 1,
                        'avg_rating': new_rating,
                        'last_updated': firestore.SERVER_TIMESTAMP
                    })

            transaction = self.db.transaction()
            update_stats(transaction)

        except Exception as e:
            print(f"Error updating book stats for {book_id}: {e}")

    def verify_migration(self):
        """Verify the migration by checking book_stats collection"""
        print("Verifying migration...")

        stats_ref = self.db.collection('book_stats')
        stats = stats_ref.stream()

        total_books = 0
        total_ratings = 0

        for stat_doc in stats:
            data = stat_doc.to_dict()
            total_books += 1
            total_ratings += data.get('rating_count', 0)

            if total_books <= 5:  # Show first 5 as examples
                print(f"Book {stat_doc.id}: {data.get('rating_count')} ratings, avg {data.get('avg_rating')}")

        print(f"Total books with ratings: {total_books}")
        print(f"Total ratings aggregated: {total_ratings}")

if __name__ == "__main__":
    import os

    # Path to your Firebase service account key
    SERVICE_ACCOUNT_PATH = os.path.join(os.path.dirname(__file__), 'bookhub-80381-firebase-adminsdk-fbsvc-b3e2365f77.json')

    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        print(f"Service account file not found at: {SERVICE_ACCOUNT_PATH}")
        exit(1)

    migration_service = RatingMigrationService(SERVICE_ACCOUNT_PATH)

    print("Choose an option:")
    print("1. Run migration (populate book_stats)")
    print("2. Verify migration results")
    print("3. Run both")

    choice = input("Enter your choice (1-3): ").strip()

    if choice in ['1', '3']:
        migration_service.migrate_ratings_to_stats()

    if choice in ['2', '3']:
        migration_service.verify_migration()
