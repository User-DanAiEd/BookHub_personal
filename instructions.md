# BookHub Hybrid Recommender - Quick Start Guide

## 🎯 What This Guide Covers
This guide shows you how to set up and use BookHub's hybrid recommendation system that combines:
- **Content-based filtering** (based on your custom tags)
- **Collaborative filtering** (based on what similar users like)

## 🚀 Quick Setup (5 minutes)

### 1. Install Dependencies
```bash
cd server
pip install -r requirements.txt
```

### 2. Start the Server
```bash
python app.py
```
Server runs at: http://localhost:8000

### 3. Open BookHub
Go to http://localhost:8000 in your browser

## 📚 How to Use the Recommender

### Step 1: Add Books to Your Library
1. Click "Search Books" from the homepage
2. Search for books you like
3. Click "Add to Library" on books you want to track

### Step 2: Add Tags to Your Books
1. Go to your book library (Book Tracking page)
2. Click on any book to open its details
3. Add custom tags like "mystery", "romance", "sci-fi"
4. Save your tags

### Step 3: Rate Your Books (For Better Recommendations)
1. On each book's detail page, you'll see a star rating (1-5 stars)
2. Click the stars to rate books you've read
3. Higher ratings = better recommendations

### Step 4: Get Recommendations
1. Go to the Recommendations page
2. Choose a tag (like "mystery") or let the system pick your top tags
3. The system will show books you might like!

## 🔧 How the Hybrid System Works

### Content-Based (Your Tags)
- Recommends books with similar tags to what you like
- Example: If you like "mystery" books, it suggests other mystery books

### Collaborative (What Others Like)
- Finds users with similar tastes to you
- Recommends books that those similar users enjoyed
- Example: "People who liked the same books as you also liked these"

### Hybrid Magic
- Combines both methods for better results
- Adjusts automatically based on available data
- Falls back to content-based if collaborative data is limited

## 🎛️ Advanced Settings

### Adjust Recommendation Balance
You can control how much weight each method gets:
- **More Content-Based**: Focus on your tags (good for new users)
- **More Collaborative**: Focus on similar users (better with more ratings)

### API Endpoints (For Developers)

#### Save a Rating
```bash
POST /api/rating/save
{
  "user_id": "your_user_id",
  "book_id": "book_id",
  "rating": 5
}
```

#### Get Hybrid Recommendations
```bash
GET /api/recommendations/hybrid?user_id=your_user_id&tags=mystery,thriller&alpha=0.5&limit=10
```

## 🐛 Troubleshooting

### "No recommendations found"
- Make sure you've added tags to at least 2 books
- Try different tags
- Rate more books for better collaborative recommendations

### "Server not starting"
- Check if port 8000 is available
- Make sure all dependencies are installed
- Check for error messages in the console

### "Firebase errors"
- Make sure Firebase project is set up correctly
- Check that Firestore is enabled
- Verify authentication settings

## 📊 Understanding Your Recommendations

### Why These Books?
Each recommendation shows:
- Books similar to what you tagged
- Books that users with similar tastes enjoyed
- A mix of both for the best results

### Improving Recommendations
- Rate more books (1-5 stars)
- Add more specific tags
- The more you use it, the better it gets!

## 🔄 System Flow

1. **You add books** → System learns your preferences
2. **You add tags** → System understands your interests
3. **You rate books** → System finds similar users
4. **System recommends** → Based on your tags + similar users' preferences

---

## ⚠️ Common Firebase Authentication Issue After Adding Google Cloud CLI

### Problem

Before adding Google Cloud CLI with your `.json` service account, users were correctly detected (registered vs. guest). After integrating the CLI credentials, your app treats everyone as anonymous. No user ID or email shows, meaning authentication is broken somewhere in the flow.

### Why This Happens

- You’re mixing service account authentication with user authentication.
- A `.json` file from Google Cloud (service account) is used for server-to-server communication, **not** for authenticating individual users.
- If you use that `.json` everywhere, your app might only authenticate as the service account, ignoring actual users.
- Initializing Firebase Admin SDK (with the `.json`) inside your app’s frontend logic overrides client-side auth state, so everyone looks “anonymous”.
- Missing token exchange: your backend no longer verifies user tokens and defaults to "no user".
- Database writes happen under service account, not user, so no UID/email shows.

### How to Fix This — Step by Step

1. **Separate Service Account Usage from User Authentication**

   - Use the `.json` service account **only** on your backend/server for server-to-server communication.
   - Do **not** initialize Firebase Admin SDK or use the `.json` file in your frontend or client-side code.

2. **Keep User Authentication on the Client Side**

   - Use Firebase Authentication SDK on the client side to handle user sign-in/sign-up.
   - This maintains the user’s auth state (`firebase.auth().currentUser`).

3. **Pass User ID Token to Backend**

   - After user signs in, get their ID token from Firebase Auth.
   - Send this token with requests to your backend (e.g., in HTTP headers).

4. **Verify ID Token on Backend**

   - On your backend, verify the ID token using Firebase Admin SDK initialized with the `.json` service account.
   - This confirms the user’s identity and allows you to associate requests with the correct user.

5. **Use Verified User Info for Database Operations**

   - Perform database reads/writes using the verified user’s UID/email.
   - Avoid using the service account identity for user-specific operations.

---

### Step-by-Step Instructions for Teens

1. **Use the `.json` file only on your server**

   - Keep the `.json` file on your backend server.
   - Do not put it in your website or app code that runs on users’ devices.

2. **Let users log in on their devices**

   - Use Firebase Authentication SDK in your website or app.
   - This lets users sign in with email, Google, or other methods.

3. **Get a secret token after login**

   - When a user logs in, get their ID token from Firebase Auth.
   - This token proves who they are.

4. **Send the token to your server**

   - When your app talks to your server, send the ID token along.
   - Usually, this is done in the HTTP request headers.

5. **Check the token on your server**

   - Your server uses the `.json` file to check if the token is real.
   - This makes sure the user is who they say they are.

6. **Use the user’s info for database stuff**

   - When saving or reading data, use the user’s ID from the token.
   - Don’t use the `.json` service account identity for this.

---

## 🎉 You're Done!

Your app now knows who is who and won’t treat everyone like a guest.

If you want, I can help you check your current code to make sure this is set up correctly.

---
