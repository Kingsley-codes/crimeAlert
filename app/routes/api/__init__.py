"""Versioned JSON API. All responses use {ok, data|error}."""
from uuid import UUID
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from app.extensions import db
from app.models.crime_report import CrimeReport
from app.models.user import User
from app.services.auth_service import authenticate_user
from app.services.report_service import change_report, create_report

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
def ok(data=None, status=200): return jsonify({"ok": True, "data": data}), status
def fail(message, status=400): return jsonify({"ok": False, "error": {"message": message}}), status
def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict): raise ValueError("A JSON object request body is required.")
    return data
def actor(role=None):
    try: user = db.session.get(User, UUID(get_jwt_identity()))
    except (ValueError, TypeError): user = None
    return user if user and user.can_authenticate and (role is None or user.role == role) else None
def serialize(report, public=False):
    data={"id":str(report.id),"reference_code":report.reference_code,"crime_type":report.crime_type,"title":report.title,"description":report.description,"incident_datetime":report.incident_datetime.isoformat(),"risk_level":report.risk_level,"status":report.status,"created_at":report.created_at.isoformat()}
    data.update(latitude=round(float(report.latitude),2) if public else float(report.latitude), longitude=round(float(report.longitude),2) if public else float(report.longitude))
    if not public: data["is_anonymous"] = bool(report.is_anonymous)
    return data

@api_bp.post("/auth/login")
def login():
    try: payload=json_body()
    except ValueError as exc: return fail(str(exc))
    user=authenticate_user(email=str(payload.get("email","")),password=str(payload.get("password","")))
    if not user: return fail("Invalid credentials or inactive account.",401)
    return ok({"access_token":create_access_token(identity=str(user.id),additional_claims={"role":user.role}),"user":{"id":str(user.id),"name":user.name,"role":user.role}})
@api_bp.post("/auth/logout")
@jwt_required()
def logout(): return ok({"message":"Discard the access token to sign out."})

@api_bp.post("/reports")
def submit():
    try:
        payload=json_body(); user=None
        if request.headers.get("Authorization"):
            # Optional identity is intentionally not accepted without a verified JWT.
            return fail("Use /me endpoints with a valid token; public reports are anonymous.",401)
        report=create_report(payload); db.session.commit(); return ok({"report":serialize(report)},201)
    except ValueError as exc: db.session.rollback(); return fail(str(exc))
@api_bp.get("/reports")
def public_reports():
    reports=db.session.scalars(db.select(CrimeReport).where(CrimeReport.status=="approved").order_by(CrimeReport.incident_datetime.desc())).all()
    items=[serialize(r,True) for r in reports]
    # `reports` is retained temporarily for the existing public-map client.
    return jsonify({"ok":True,"data":{"reports":items},"reports":items})
@api_bp.get("/reports/<uuid:report_id>")
def public_one(report_id):
    report=db.session.scalar(db.select(CrimeReport).where(CrimeReport.id==report_id,CrimeReport.status=="approved"))
    return ok({"report":serialize(report,True)}) if report else fail("Approved report not found.",404)
@api_bp.get("/me/reports")
@jwt_required()
def mine():
    user=actor("user")
    if not user:return fail("User authentication required.",403)
    reports=db.session.scalars(db.select(CrimeReport).where(CrimeReport.reporter_id==user.id).order_by(CrimeReport.created_at.desc())).all()
    return ok({"reports":[serialize(r) for r in reports]})
@api_bp.get("/me/reports/<uuid:report_id>")
@jwt_required()
def mine_one(report_id):
    user=actor("user")
    if not user:return fail("User authentication required.",403)
    report=db.session.scalar(db.select(CrimeReport).where(CrimeReport.id==report_id,CrimeReport.reporter_id==user.id))
    return ok({"report":serialize(report)}) if report else fail("Report not found.",404)
@api_bp.get("/admin/reports")
@jwt_required()
def admin_list():
    if not actor("admin"):return fail("Administrator authentication required.",403)
    return ok({"reports":[serialize(r) for r in db.session.scalars(db.select(CrimeReport).order_by(CrimeReport.created_at.desc())).all()]})
def act(report_id,action):
    user=actor("admin")
    if not user:return fail("Administrator authentication required.",403)
    report=db.session.get(CrimeReport,report_id)
    if not report:return fail("Report not found.",404)
    try:
        payload=json_body() if action in {"classification","risk_level"} else {}
        change_report(report,action,user.id,payload.get("crime_type") if action=="classification" else payload.get("risk_level")); db.session.commit(); return ok({"report":serialize(report)})
    except ValueError as exc: db.session.rollback(); return fail(str(exc))
@api_bp.post("/admin/reports/<uuid:report_id>/approve")
@jwt_required()
def approve(report_id):return act(report_id,"approve")
@api_bp.post("/admin/reports/<uuid:report_id>/reject")
@jwt_required()
def reject(report_id):return act(report_id,"reject")
@api_bp.patch("/admin/reports/<uuid:report_id>/classification")
@jwt_required()
def classify(report_id):return act(report_id,"classification")
@api_bp.patch("/admin/reports/<uuid:report_id>/risk-level")
@jwt_required()
def risk(report_id):return act(report_id,"risk_level")
