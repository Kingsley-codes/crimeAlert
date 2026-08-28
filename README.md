# CrimeAlert

CrimeAlert is a Flask foundation for a crime location reporting system. The project uses an application factory, PostgreSQL via `DATABASE_URL`, Flask-SQLAlchemy, and Flask-Migrate.

## Prerequisites

- Python 3.11+
- A PostgreSQL database (Supabase PostgreSQL is supported for production)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set `DATABASE_URL` and `SECRET_KEY`.
4. Start the app: `python run.py`

The home page is available at `http://127.0.0.1:5000/`.

## Database configuration

`DATABASE_URL` is the sole application database setting. Use a PostgreSQL URL such as:

`postgresql://user:password@host:5432/database`

No database models or migrations have been created yet. Once the connection test succeeds, initialise Flask-Migrate with `flask --app run.py db init` and then create models deliberately.

## Tests

Run `python -m pytest` to verify the application factory and home page.
