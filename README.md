# CrimeAlert

CrimeAlert is a Flask foundation for a crime location reporting system. The project uses an application factory, PostgreSQL via `DATABASE_URL`, Flask-SQLAlchemy, and Flask-Migrate.

## Prerequisites

- Python 3.11+
- A PostgreSQL database (Supabase PostgreSQL is supported for production)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set `DATABASE_URL`, `SECRET_KEY`, and the Cloudinary values if media uploads are needed.
4. Start the app: `python run.py`

The home page is available at `http://127.0.0.1:5000/`.

## Administrator access

The administrator sign-in page is available at `http://127.0.0.1:5000/admin/login`.
Create administrators only from a trusted terminal after applying the database migrations:

```powershell
flask --app run.py create-admin --name "Admin Name" --email admin@example.com
```

The command securely prompts for a password and creates an active account with the `admin` role. Administrators then sign in at `/admin/login` and are sent to `/admin/dashboard`.

## Database configuration

`DATABASE_URL` is the sole application database setting. Use a PostgreSQL URL such as:

`postgresql://user:password@host:5432/database`

The project includes its initial database migrations. Apply them to a configured
database with `flask --app run.py db upgrade`; the Render start command does
this automatically before Gunicorn starts the web service.

## Media uploads

Crime-report media is stored in Cloudinary, not on the application filesystem. Configure
`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET`. The maximum
file size and accepted image/video MIME types are configurable through the `REPORT_*`
variables shown in `.env.example`.

## Render deployment

This repository includes a `render.yaml` Blueprint that creates a Python web
service and a Render PostgreSQL database. It installs the production server,
runs pending database migrations, and starts the app with Gunicorn.

In the Render Dashboard, select **New > Blueprint**, connect this repository,
and deploy the detected `render.yaml`. Render creates `DATABASE_URL` from the
managed database connection and generates `SECRET_KEY` automatically. Do not
upload or commit your local `.env` file.

## Tests

Run `python -m pytest` to verify the application, versioned API validation/pagination, notification ownership, and server-side JWT logout revocation.
