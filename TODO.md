# TODO - Implement Hybrid Filtering in BookHub

## Overview
This TODO list outlines the tasks required to extend the current BookHub recommendation system from content-based filtering to a hybrid filtering system by incorporating collaborative filtering.

## Tasks

### 1. Data Model Enhancements
- [x] Update Firestore data model to store user ratings (1-5 stars) for tracked books.
- [x] Implement API endpoint to save user ratings (`/api/rating/save`).
- [x] Add required dependencies (scikit-learn, numpy, pandas) to requirements.txt.

### 2. Collaborative Filtering Implementation
- [x] Implement methods in `FirebaseRecommendations` class:
  - [x] Build user-item rating matrix from Firestore data.
  - [x] Compute item-item similarity matrix using cosine similarity.
  - [x] Generate collaborative filtering recommendations based on user ratings.

### 3. Hybrid Recommendation Logic
- [x] Implement method to combine content-based and collaborative recommendations with adjustable weighting (alpha parameter).
- [x] Update backend API to provide hybrid recommendations endpoint (`/api/recommendations/hybrid`).

### 4. Frontend Updates
- [x] Add rating UI component (1-5 stars) on book summary pages.
  - [x] Create star rating widget in HTML/CSS/JS.
  - [x] Integrate with Firebase to save ratings on user interaction.
  - [x] Update book summary page template to include rating input.
- [x] Modify recommendation page to call hybrid recommendation API and display combined results.
  - [x] Update recommendationPage.html to use new hybrid endpoint.
  - [x] Add parameters for alpha weighting and tags in API call.
  - [x] Handle API response and display hybrid recommendations.
- [ ] Optionally, display contribution of content-based vs collaborative scores.
  - [ ] Modify recommendation cards to show score breakdown.
  - [ ] Add UI toggle to switch between content-only and hybrid modes.

### 5. Testing and Validation
- [ ] Create test users and seed Firestore with sample ratings data.
  - [ ] Create 5-10 test user accounts in Firebase.
  - [ ] Add 20+ books to each user's tracked list.
  - [ ] Assign ratings (1-5) to create overlapping rating patterns.
- [ ] Test API endpoints for saving ratings and fetching hybrid recommendations.
  - [ ] Test `/api/rating/save` with valid and invalid data.
  - [ ] Test `/api/recommendations/hybrid` with different alpha values and tag combinations.
  - [ ] Verify error handling for missing users/books.
- [ ] Perform UI testing for rating input and recommendation display.
  - [ ] Test star rating widget on book summary pages.
  - [ ] Verify ratings save correctly to Firebase.
  - [ ] Test recommendation page with hybrid results.
  - [ ] Check responsive design on different screen sizes.
- [ ] Tune alpha parameter for best recommendation quality.
  - [ ] Experiment with alpha values (0.0 to 1.0) and measure recommendation relevance.
  - [ ] Compare hybrid vs content-only recommendations.
  - [ ] Gather user feedback on recommendation quality.

### 6. Documentation
- [x] Update `instructions.md` with hybrid filtering setup and usage instructions.
- [x] Document API endpoints and data model changes.

## Notes
- Start with content-based filtering as fallback when collaborative data is insufficient.
- Consider cold start and sparsity challenges during implementation.
- Plan for scalability and privacy compliance.

---

This TODO list will guide the incremental implementation of hybrid filtering in BookHub.
