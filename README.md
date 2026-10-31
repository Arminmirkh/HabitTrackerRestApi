# Habit Tracker API

REST API for a habit-tracking mobile app, built as my bachelor project. It handles user accounts with JWT authentication, goals, habits, daily check-ins, streak tracking, and AI-generated habit suggestions.

## Features

- **Authentication:** register, login, logout, and token refresh using JWT (access and refresh tokens, with refresh-token blacklisting on logout).
- **Goals and habits:** full CRUD for goals and habits, with filtering and pagination. Every user can only access their own data.
- **Daily check-ins:** mark a habit done or not done for today, with optional mood, energy and notes.
- **Streaks:** current and longest streaks are calculated from the record history (daily, weekly and monthly habits), plus an overall streak across all habits.
- **Bulk create:** create many habits in one request, all-or-nothing.
- **AI habit suggestions:** turns a goal such as "run a 10k" into 3-5 suggested habits using an LLM via the Groq API. The response is validated and cleaned before it is returned, and nothing is saved until the client chooses to keep a suggestion.
- **API docs:** interactive Swagger UI and ReDoc, generated from the code.
- **Tests:** 49 automated tests covering authentication, data ownership, streak logic and the AI integration (external API calls are mocked).

## Tech stack

Python, Django 5.2, Django REST Framework, Simple JWT, drf-spectacular, Groq API, SQLite.

## Getting started

### 1. Clone and install

```bash
git clone https://github.com/Arminmirkh/HabitTrackerRestApi.git
cd HabitTrackerRestApi
python -m venv venv
venv\Scripts\activate        # on macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in the values:

```
GROQ_API_KEY=your-groq-api-key-here
DJANGO_SECRET_KEY=your-django-secret-key-here
```

Generate a secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

You can get a Groq API key from the [Groq console](https://console.groq.com/). Without it, everything works except the AI suggestions endpoint.

### 3. Set up the database and run

```bash
python manage.py migrate
python manage.py runserver
```

The API is now available at `http://localhost:8000/api/`.

### Optional: demo data

```bash
python manage.py seed_data
```

Creates a few demo users with goals, habits and weeks of check-in history. Options: `--days 90`, `--flush` (wipe previous demo data), `--seed 42` (reproducible output).

## API documentation

With the server running:

- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- OpenAPI schema: `http://localhost:8000/api/schema/`

### Main endpoints

All routes are prefixed with `/api/`. Authenticated routes need the header `Authorization: Bearer <access_token>`.

| Area | Endpoints |
| --- | --- |
| Accounts | `POST /register/`, `POST /login/`, `POST /logout/`, `POST /token/refresh/`, `GET/PATCH /me/` |
| Goals | `/goals/` (list, create), `/goals/{id}/` (retrieve, update, delete) |
| Habits | `/habits/`, `/habits/{id}/`, `POST /habits/bulk-create/`, `POST /habits/{id}/check-in/`, `GET /habits/overall-streak/` |
| Records | `/habit-records/` and `/habit-records/{id}/` |
| AI | `POST /ai/generate-habits/` with body `{"goal": "run a 10k"}` |

See `API_URLS.txt` or the Swagger UI for the full list, including filters.

### Example

```bash
# Register
curl -X POST http://localhost:8000/api/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "a-strong-password"}'

# Generate habit suggestions (use the access token from the response above)
curl -X POST http://localhost:8000/api/ai/generate-habits/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"goal": "run a 10k"}'
```

## Running the tests

```bash
python manage.py test
```

The tests use a temporary database and mock the Groq client, so they don't need an API key or an internet connection.

## Project structure

```
accounts/   custom user model, registration, login, profile
habits/     goals, habits, records, streak logic, check-in endpoint
ai/         Groq integration and the habit-suggestion endpoint
habit_tracker/   project settings and URL configuration
```

## Notes

- Access tokens last 15 minutes and refresh tokens last 7 days. Refresh tokens rotate, and logout blacklists the token.
- The project currently uses SQLite for simplicity.
