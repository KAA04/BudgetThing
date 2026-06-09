# Reminders

A simple Flask reminders app with custom categories and category-specific reminder lists.

## Features

- Create custom categories
- Add reminders inside each category
- Browse categories from the home screen
- Local SQLite storage only

## Run

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start the app:
   - `python app.py`
3. Open `http://127.0.0.1:5000` in your browser.

## Data Shape

- Category: id, name, created_at
- Reminder: id, category_id, title, created_at