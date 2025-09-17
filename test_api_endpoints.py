import unittest
import json
from server.app import app

class TestBookHubAPI(unittest.TestCase):
    def setUp(self):
        # Set up test client
        self.app = app.test_client()
        self.app.testing = True

        # Sample test data
        self.user_id = "test_user_123"
        self.book_id = "test_book_456"
        self.valid_rating = 4
        self.invalid_rating = 6  # Invalid rating (out of 1-5 range)
        self.tags = "mystery,thriller"
        self.alpha = 0.5
        self.limit = 5

    def test_save_rating_success(self):
        # Test saving a valid rating
        payload = {
            "user_id": self.user_id,
            "book_id": self.book_id,
            "rating": self.valid_rating
        }
        response = self.app.post('/api/rating/save', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        self.assertIn("Rating saved successfully", data.get("message", ""))

    def test_save_rating_missing_params(self):
        # Test saving rating with missing parameters
        payload = {
            "user_id": self.user_id,
            "book_id": self.book_id
            # Missing rating
        }
        response = self.app.post('/api/rating/save', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)

    def test_save_rating_invalid_rating(self):
        # Test saving rating with invalid rating value
        payload = {
            "user_id": self.user_id,
            "book_id": self.book_id,
            "rating": self.invalid_rating
        }
        response = self.app.post('/api/rating/save', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertIn("Rating must be an integer between 1 and 5", data.get("error", ""))

    def test_hybrid_recommendations_success(self):
        # Test fetching hybrid recommendations with valid parameters
        params = {
            "user_id": self.user_id,
            "tags": self.tags,
            "alpha": self.alpha,
            "limit": self.limit
        }
        response = self.app.get('/api/recommendations/hybrid', query_string=params)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("recommendations", data)
        self.assertIsInstance(data["recommendations"], list)

    def test_hybrid_recommendations_missing_params(self):
        # Test fetching hybrid recommendations with missing parameters
        params = {
            "user_id": self.user_id,
            # Missing tags
            "alpha": self.alpha,
            "limit": self.limit
        }
        response = self.app.get('/api/recommendations/hybrid', query_string=params)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)

    def test_hybrid_recommendations_invalid_alpha(self):
        # Test fetching hybrid recommendations with invalid alpha value
        params = {
            "user_id": self.user_id,
            "tags": self.tags,
            "alpha": 1.5,  # Invalid alpha > 1
            "limit": self.limit
        }
        response = self.app.get('/api/recommendations/hybrid', query_string=params)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertIn("Alpha must be between 0 and 1", data.get("error", ""))

if __name__ == '__main__':
    unittest.main()
