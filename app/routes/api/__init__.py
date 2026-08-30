"""Public, privacy-preserving API routes."""

from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.forms.report import CRIME_TYPES
from app.models.crime_report import CrimeReport


api_bp = Blueprint("api", __name__, url_prefix="/api")

RISK_LEVELS = {"high", "medium", "low"}


def _parse_date(value: str | None) -> date | None:
    """Parse an optional ISO date without raising a server error for bad filters."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@api_bp.get("/public-reports")
def public_reports():  # type: ignore[no-untyped-def]
    """Return only privacy-minimised, approved reports for the public map."""
    crime_type = request.args.get("crime_type", "").strip().lower()
    risk_level = request.args.get("risk_level", "").strip().lower()
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    statement = db.select(CrimeReport).where(CrimeReport.status == "approved")
    if crime_type in CRIME_TYPES:
        statement = statement.where(CrimeReport.crime_type == crime_type)
    if risk_level in RISK_LEVELS:
        statement = statement.where(CrimeReport.risk_level == risk_level)
    if date_from:
        statement = statement.where(CrimeReport.incident_datetime >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        statement = statement.where(
            CrimeReport.incident_datetime < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    reports = db.session.scalars(statement.order_by(CrimeReport.incident_datetime.desc())).all()
    return jsonify(
        {
            "reports": [
                {
                    "crime_type": report.crime_type,
                    "incident_datetime": report.incident_datetime.isoformat(),
                    "risk_level": report.risk_level,
                    # Approximate to about kilometre-level precision; never return the exact stored point.
                    "latitude": round(float(report.latitude), 2),
                    "longitude": round(float(report.longitude), 2),
                }
                for report in reports
            ]
        }
    )
