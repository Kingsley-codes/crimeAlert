"""Versioned REST API for mobile clients and first-party AJAX consumers."""
from datetime import datetime, timezone
from functools import wraps
from uuid import UUID

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from flask_wtf.csrf import ValidationError, validate_csrf

from app.extensions import db
from app.models.admin_log import AdminLog
from app.models.crime_report import CrimeReport
from app.models.crime_type import CrimeType
from app.models.notification import Notification
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.services.auth_service import authenticate_user
from app.services.report_service import change_report, create_report

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
MAX_PAGE_SIZE = 100

def ok(data=None, status=200): return jsonify({"ok": True, "data": data}), status
def fail(message, status=400): return jsonify({"ok": False, "error": {"message": message}}), status
def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict): raise ValueError("A JSON object request body is required.")
    return data

def _identity_user():
    """Use a verified bearer token, or a signed-in same-origin web session."""
    identity = get_jwt_identity()
    if identity:
        try: return db.session.get(User, UUID(identity))
        except (ValueError, TypeError): return None
    return current_user if current_user.is_authenticated else None

def api_role(role=None):
    def decorator(view):
        @wraps(view)
        @jwt_required(optional=True)
        def wrapped(*args, **kwargs):
            user = _identity_user()
            if not user or not user.can_authenticate or (role and user.role != role):
                return fail("Administrator authentication required." if role == "admin" else "User authentication required.", 403)
            if not get_jwt_identity() and request.method not in {"GET", "HEAD", "OPTIONS"}:
                try: validate_csrf(request.headers.get("X-CSRFToken"))
                except ValidationError: return fail("CSRF validation failed.", 400)
            return view(user, *args, **kwargs)
        return wrapped
    return decorator

def _page_args():
    try:
        page, per_page = max(1, int(request.args.get("page", 1))), min(MAX_PAGE_SIZE, max(1, int(request.args.get("per_page", 25))))
    except ValueError: raise ValueError("page and per_page must be positive integers.")
    return page, per_page

def _pagination(statement, page, per_page):
    total = db.session.scalar(db.select(db.func.count()).select_from(statement.subquery())) or 0
    return statement.offset((page - 1) * per_page).limit(per_page), {"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}

def _filters(statement):
    crime_type, risk_level = request.args.get("crime_type", "").strip().lower(), request.args.get("risk_level", "").strip().lower()
    date_from, date_to = request.args.get("date_from", "").strip(), request.args.get("date_to", "").strip()
    if crime_type: statement = statement.where(CrimeReport.crime_type == crime_type)
    if risk_level:
        if risk_level not in {"high", "medium", "low"}: raise ValueError("risk_level must be high, medium, or low.")
        statement = statement.where(CrimeReport.risk_level == risk_level)
    try:
        if date_from: statement = statement.where(CrimeReport.incident_datetime >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
        if date_to: statement = statement.where(CrimeReport.incident_datetime < datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc).replace(hour=23, minute=59, second=59, microsecond=999999))
    except ValueError: raise ValueError("date_from and date_to must be ISO dates (YYYY-MM-DD).")
    return statement

def serialize(report, public=False, detail=False):
    if public: return {"crime_type": report.crime_type, "incident_datetime": report.incident_datetime.isoformat(), "latitude": round(float(report.latitude), 2), "longitude": round(float(report.longitude), 2), "risk_level": report.risk_level}
    data = {"id": str(report.id), "reference_code": report.reference_code, "crime_type": report.crime_type, "title": report.title, "incident_datetime": report.incident_datetime.isoformat(), "risk_level": report.risk_level, "status": report.status, "created_at": report.created_at.isoformat(), "latitude": float(report.latitude), "longitude": float(report.longitude), "is_anonymous": bool(report.is_anonymous)}
    if detail:
        data["description"] = report.description
        data["reporter"] = None if report.reporter is None or report.is_anonymous else {"name": report.reporter.name, "email": report.reporter.email}
    return data

@api_bp.post("/auth/login")
def login():
    try: payload = json_body()
    except ValueError as exc: return fail(str(exc))
    user = authenticate_user(email=str(payload.get("email", "")), password=str(payload.get("password", "")))
    if not user: return fail("Invalid credentials or inactive account.", 401)
    return ok({"access_token": create_access_token(identity=str(user.id), additional_claims={"role": user.role}), "user": {"id": str(user.id), "name": user.name, "role": user.role}})

@api_bp.post("/auth/logout")
@jwt_required()
def logout():
    claims = get_jwt()
    db.session.merge(RevokedToken(jti=claims["jti"], expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)))
    db.session.commit()
    return ok({"message": "Access token revoked."})

@api_bp.post("/reports")
def submit():
    try:
        payload = json_body()
        if request.headers.get("Authorization"): return fail("Use the authenticated /me endpoint with a valid token; public reports are anonymous.", 401)
        report = create_report(payload); db.session.commit(); return ok({"report": serialize(report)}, 201)
    except ValueError as exc: db.session.rollback(); return fail(str(exc))

@api_bp.get("/reports")
def public_reports():
    try:
        page, per_page = _page_args()
        statement, pagination = _pagination(_filters(db.select(CrimeReport).where(CrimeReport.status == "approved")).order_by(CrimeReport.incident_datetime.desc()), page, per_page)
        reports = [serialize(report, public=True) for report in db.session.scalars(statement)]
        return jsonify({"ok": True, "data": {"reports": reports, "pagination": pagination}, "reports": reports})
    except ValueError as exc: return fail(str(exc))

@api_bp.get("/reports/<uuid:report_id>")
def public_one(report_id):
    report = db.session.scalar(db.select(CrimeReport).where(CrimeReport.id == report_id, CrimeReport.status == "approved"))
    return ok({"report": serialize(report, public=True)}) if report else fail("Approved report not found.", 404)

@api_bp.get("/me/reports")
@api_role("user")
def mine(user):
    try:
        page, per_page = _page_args(); statement, pagination = _pagination(db.select(CrimeReport).where(CrimeReport.reporter_id == user.id).order_by(CrimeReport.created_at.desc()), page, per_page)
        return ok({"reports": [serialize(r) for r in db.session.scalars(statement)], "pagination": pagination})
    except ValueError as exc: return fail(str(exc))

@api_bp.get("/me/reports/<uuid:report_id>")
@api_role("user")
def mine_one(user, report_id):
    report = db.session.scalar(db.select(CrimeReport).where(CrimeReport.id == report_id, CrimeReport.reporter_id == user.id))
    return ok({"report": serialize(report, detail=True)}) if report else fail("Report not found.", 404)

@api_bp.get("/notifications")
@api_role()
def notifications(user):
    statement = db.select(Notification).where(Notification.recipient_id == user.id)
    if request.args.get("unread", "").lower() in {"1", "true"}: statement = statement.where(Notification.is_read.is_(False))
    notices = db.session.scalars(statement.order_by(Notification.created_at.desc())).all()
    return ok({"notifications": [{"id": n.id, "title": n.title, "message": n.message, "type": n.notification_type, "is_read": n.is_read, "created_at": n.created_at.isoformat(), "report_id": str(n.report_id) if n.report_id else None} for n in notices]})

@api_bp.post("/notifications/<int:notification_id>/read")
@api_role()
def read_notification(user, notification_id):
    notice = db.session.scalar(db.select(Notification).where(Notification.id == notification_id, Notification.recipient_id == user.id))
    if not notice: return fail("Notification not found.", 404)
    notice.is_read = True; db.session.commit(); return ok({"notification": {"id": notice.id, "is_read": True}})

def _admin_reports():
    statement = _filters(db.select(CrimeReport)); status = request.args.get("status", "").strip().lower()
    if status:
        if status not in {"pending", "approved", "rejected"}: raise ValueError("status must be pending, approved, or rejected.")
        statement = statement.where(CrimeReport.status == status)
    return statement.order_by(CrimeReport.created_at.desc())

@api_bp.get("/admin/reports")
@api_role("admin")
def admin_list(user):
    try:
        page, per_page = _page_args(); statement, pagination = _pagination(_admin_reports(), page, per_page)
        return ok({"reports": [serialize(r) for r in db.session.scalars(statement)], "pagination": pagination})
    except ValueError as exc: return fail(str(exc))

@api_bp.get("/admin/reports/table")
@api_role("admin")
def admin_table(user):
    try:
        page, per_page = _page_args(); statement, _ = _pagination(_admin_reports(), page, per_page)
        types = db.session.scalars(db.select(CrimeType).where(CrimeType.is_active.is_(True)).order_by(CrimeType.name)).all()
        return render_template("admin/_report_table.html", reports=db.session.scalars(statement).all(), crime_types=types)
    except ValueError as exc: return fail(str(exc))

@api_bp.get("/admin/reports/<uuid:report_id>")
@api_role("admin")
def admin_one(user, report_id):
    report = db.session.get(CrimeReport, report_id)
    return ok({"report": serialize(report, detail=True)}) if report else fail("Report not found.", 404)

def _act(user, report_id, action):
    report = db.session.get(CrimeReport, report_id)
    if not report: return fail("Report not found.", 404)
    try:
        payload = json_body() if action in {"classification", "risk_level"} else {}
        change_report(report, action, user.id, payload.get("crime_type") if action == "classification" else payload.get("risk_level")); db.session.commit(); return ok({"report": serialize(report)})
    except ValueError as exc: db.session.rollback(); return fail(str(exc))

@api_bp.post("/admin/reports/<uuid:report_id>/approve")
@api_role("admin")
def approve(user, report_id): return _act(user, report_id, "approve")
@api_bp.post("/admin/reports/<uuid:report_id>/reject")
@api_role("admin")
def reject(user, report_id): return _act(user, report_id, "reject")
@api_bp.patch("/admin/reports/<uuid:report_id>/classification")
@api_role("admin")
def classify(user, report_id): return _act(user, report_id, "classification")
@api_bp.patch("/admin/reports/<uuid:report_id>/risk-level")
@api_role("admin")
def risk(user, report_id): return _act(user, report_id, "risk_level")

@api_bp.get("/admin/map-analytics")
@api_role("admin")
def admin_map(user):
    reports = db.session.scalars(db.select(CrimeReport).order_by(CrimeReport.incident_datetime.desc())).all(); cells = {}
    for report in reports:
        key = (int(float(report.latitude) // .05), int(float(report.longitude) // .05)); cells[key] = cells.get(key, 0) + 1
    hotspots = [{"zone": f"Grid {lat * .05:.2f}, {lng * .05:.2f}", "count": count} for (lat, lng), count in sorted(cells.items(), key=lambda item: -item[1])[:5]]
    return ok({"reports": [serialize(r) for r in reports], "hotspots": hotspots})

@api_bp.post("/admin/users/<uuid:user_id>/status")
@api_role("admin")
def update_user(user, user_id):
    try: action = str(json_body().get("action", "")).lower()
    except ValueError as exc: return fail(str(exc))
    target = db.session.scalar(db.select(User).where(User.id == user_id, User.role == "user"))
    if not target: return fail("User not found.", 404)
    if action not in {"suspend", "reactivate"}: return fail("Choose suspend or reactivate.")
    target.is_active = action == "reactivate"; db.session.add(AdminLog(admin_id=user.id, action=f"user.{action}:{target.id}")); db.session.commit()
    return ok({"message": f"{target.name}'s account was {'reactivated' if target.is_active else 'suspended'}.", "is_active": target.is_active})
