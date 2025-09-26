import pandas as pd

# Loads the dataset (update the filename if different) This is a local feature
data = pd.read_csv('book_details.csv')

# Search function
def search_books(title_keyword):
    results = data[data['title'].str.contains(title_keyword, case=False, na=False)]
    if results.empty:
        print("No books found.")
    else:
        print(results[['title', 'url', 'description', 'genres']])

# Example search
search_term = input("Enter book title to search: ")
search_books(search_term)
