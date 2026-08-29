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

The project includes its initial database migrations. Apply them to a configured
database with `flask --app run.py db upgrade`; the Render start command does
this automatically before Gunicorn starts the web service.

## Render deployment

This repository includes a `render.yaml` Blueprint that creates a Python web
service and a Render PostgreSQL database. It installs the production server,
runs pending database migrations, and starts the app with Gunicorn.

In the Render Dashboard, select **New > Blueprint**, connect this repository,
and deploy the detected `render.yaml`. Render creates `DATABASE_URL` from the
managed database connection and generates `SECRET_KEY` automatically. Do not
upload or commit your local `.env` file.

## Tests

Run `python -m pytest` to verify the application factory and home page.
