from datetime import datetime

from app import create_app
from app.extensions import db
from app.models.crime_report import CrimeReport
from app.models.crime_type import CrimeType
from app.models.admin_log import AdminLog
from app.models.notification import Notification
from app.models.user import User
from app.models.revoked_token import RevokedToken
from werkzeug.security import generate_password_hash


def test_factory_uses_database_url_configuration():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})

    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert "migrate" in app.extensions


def test_home_page_loads():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"A clearer way to report what matters" in response.data


def test_public_map_api_returns_only_approved_privacy_minimised_reports():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
    with app.app_context():
        db.create_all()
        db.session.add(CrimeType(name="theft"))
        db.session.add_all(
            [
                CrimeReport(
                    crime_type="theft",
                    description="Approved report description must not be public.",
                    latitude=6.524456,
                    longitude=3.379234,
                    incident_datetime=datetime(2026, 8, 20, 10, 0),
                    status="approved",
                    risk_level="high",
                ),
                CrimeReport(
                    crime_type="theft",
                    description="Pending reports must never appear on the public map.",
                    latitude=6.500001,
                    longitude=3.300001,
                    incident_datetime=datetime(2026, 8, 21, 10, 0),
                    status="pending",
                    risk_level="low",
                ),
            ]
        )
        db.session.commit()

        response = app.test_client().get("/api/public-reports?risk_level=high")

        assert response.status_code == 200
        assert len(response.json["reports"]) == 1
        assert response.json["reports"][0] == {
                "title": "Untitled report",
            "crime_type": "theft",
            "incident_datetime": "2026-08-20T10:00:00",
            "latitude": 6.52,
            "longitude": 3.38,
            "risk_level": "high",
        }


def test_my_reports_only_shows_owned_reports_in_newest_first_order():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        db.session.add(CrimeType(name="theft"))
        owner = User(name="Owner", email="owner@example.com", password_hash="hash")
        other_user = User(name="Other", email="other@example.com", password_hash="hash")
        db.session.add_all([owner, other_user])
        db.session.flush()
        older = CrimeReport(
            reporter_id=owner.id,
            is_anonymous=True,
            crime_type="theft",
            description="Owner's older report",
            latitude=6.5,
            longitude=3.3,
            incident_datetime=datetime(2026, 8, 1, 9, 0),
            created_at=datetime(2026, 8, 1, 9, 0),
        )
        newer = CrimeReport(
            reporter_id=owner.id,
            is_anonymous=False,
            crime_type="theft",
            description="Owner's newest report",
            latitude=6.5,
            longitude=3.3,
            incident_datetime=datetime(2026, 8, 2, 9, 0),
            created_at=datetime(2026, 8, 2, 9, 0),
        )
        other = CrimeReport(
            reporter_id=other_user.id,
            is_anonymous=True,
            crime_type="theft",
            description="Other user's private report",
            latitude=6.5,
            longitude=3.3,
            incident_datetime=datetime(2026, 8, 3, 9, 0),
            created_at=datetime(2026, 8, 3, 9, 0),
        )
        db.session.add_all([older, newer, other])
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(owner.id)
            session["_fresh"] = True

        response = client.get("/dashboard/reports")

        assert response.status_code == 200
        assert b"Owner&#39;s newest report" in response.data
        assert b"Owner&#39;s older report" in response.data
        assert response.data.index(b"Owner&#39;s newest report") < response.data.index(b"Owner&#39;s older report")
        assert b"Other user&#39;s private report" not in response.data
        assert b"owner@example.com" not in response.data
        assert client.get(f"/dashboard/reports/{newer.id}").status_code == 200
        assert client.get(f"/dashboard/reports/{other.id}").status_code == 404


def test_login_redirects_each_role_to_its_dashboard():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                User(name="Member", email="member@example.com", password_hash=generate_password_hash("password"), role="user"),
                User(name="Admin", email="admin@example.com", password_hash=generate_password_hash("password"), role="admin"),
            ]
        )
        db.session.commit()

    user_client = app.test_client()
    user_response = user_client.post("/login", data={"email": "member@example.com", "password": "password"})
    assert user_response.status_code == 302
    assert user_response.headers["Location"].endswith("/dashboard")
    assert user_client.get("/dashboard").status_code == 200

    admin_client = app.test_client()
    admin_response = admin_client.post("/admin/login", data={"email": "admin@example.com", "password": "password"})
    assert admin_response.status_code == 302
    assert admin_response.headers["Location"].endswith("/admin/dashboard")
    assert admin_client.get("/admin/dashboard").status_code == 200

    wrong_user_portal = app.test_client().post("/login", data={"email": "admin@example.com", "password": "password"})
    assert wrong_user_portal.status_code == 200
    assert b"incorrect sign-in portal" in wrong_user_portal.data

    wrong_admin_portal = app.test_client().post("/admin/login", data={"email": "member@example.com", "password": "password"})
    assert wrong_admin_portal.status_code == 200
    assert b"Invalid credentials or account access" in wrong_admin_portal.data


def test_public_and_dashboard_reporting_pages_are_separate():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        user = User(name="Member", email="member@example.com", password_hash="hash", role="user")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get("/dashboard/report-crime")
    assert response.status_code == 200
    assert b"Report anonymously" in response.data
    public_client = app.test_client()
    public_response = public_client.get("/report-crime")
    assert public_response.status_code == 200
    assert b"Anonymous public report" in public_response.data


def test_public_report_is_anonymous_and_has_no_owner():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        db.session.add(CrimeType(name="theft"))
        db.session.commit()

    response = app.test_client().post(
        "/report-crime",
        data={"crime_type": "theft", "title": "Public theft report", "description": "A public anonymous report.", "incident_datetime": "2026-08-20T10:00", "latitude": "6.5244", "longitude": "3.3792"},
    )
    assert response.status_code == 302
    with app.app_context():
        report = db.session.scalar(db.select(CrimeReport))
        assert report is not None
        assert report.reporter_id is None
        assert report.is_anonymous is True


def test_reference_codes_use_user_and_crime_prefixes():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
    with app.app_context():
        db.create_all()
        db.session.add(CrimeType(name="theft"))
        user = User(name="Member", email="member@example.com", password_hash="hash")
        db.session.add(user)
        db.session.flush()
        report = CrimeReport(reporter_id=user.id, crime_type="theft", description="A prefixed report code.", latitude=6.5, longitude=3.3, incident_datetime=datetime(2026, 8, 1, 9, 0))
        db.session.add(report)
        db.session.flush()
        assert user.reference_code.startswith("USR-")
        assert report.reference_code.startswith("CR-")


def test_admin_report_action_creates_audit_log_and_notification():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        db.session.add(CrimeType(name="theft"))
        admin = User(name="Admin", email="admin@example.com", password_hash="hash", role="admin")
        reporter = User(name="Reporter", email="reporter@example.com", password_hash="hash", role="user")
        db.session.add_all([admin, reporter])
        db.session.flush()
        report = CrimeReport(
            reporter_id=reporter.id,
            crime_type="theft",
            description="A report that needs review.",
            latitude=6.5,
            longitude=3.3,
            incident_datetime=datetime(2026, 8, 1, 9, 0),
        )
        db.session.add(report)
        db.session.commit()
        admin_id, report_id = admin.id, report.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True

    response = client.post(f"/admin/reports/{report_id}/actions", json={"action": "approve"})
    assert response.status_code == 200
    assert response.json["ok"] is True
    assert response.json["report"]["status"] == "approved"
    with app.app_context():
        assert db.session.scalar(db.select(AdminLog).where(AdminLog.target_report_id == report_id)) is not None
        assert db.session.scalar(db.select(Notification).where(Notification.report_id == report_id)) is not None


def test_admin_can_suspend_and_reactivate_user_without_removing_reports():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        db.session.add(CrimeType(name="theft"))
        admin = User(name="Admin", email="admin@example.com", password_hash="hash", role="admin")
        user = User(name="Member", email="member@example.com", password_hash=generate_password_hash("password"), role="user")
        db.session.add_all([admin, user])
        db.session.flush()
        report = CrimeReport(reporter_id=user.id, crime_type="theft", description="Retained report", latitude=6.5, longitude=3.3, incident_datetime=datetime(2026, 8, 1, 9, 0))
        db.session.add(report)
        db.session.commit()
        admin_id, user_id = admin.id, user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True
    assert client.get("/admin/users").status_code == 200
    assert client.get("/admin/map-analytics").status_code == 200
    assert len(client.get("/admin/map-analytics/data").json["reports"]) == 1
    response = client.post(f"/admin/users/{user_id}/status", json={"action": "suspend"})
    assert response.status_code == 200
    assert response.json["is_active"] is False
    with app.app_context():
        assert db.session.get(User, user_id).is_active is False
        assert db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.reporter_id == user_id)) == 1
        assert db.session.scalar(db.select(AdminLog).where(AdminLog.action == f"user.suspend:{user_id}")) is not None

    suspended_client = app.test_client()
    assert suspended_client.post("/login", data={"email": "member@example.com", "password": "password"}).status_code == 200
    response = client.post(f"/admin/users/{user_id}/status", json={"action": "reactivate"})
    assert response.status_code == 200
    assert response.json["is_active"] is True


def test_versioned_api_filters_paginates_and_keeps_public_reports_private():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "JWT_SECRET_KEY": "test-secret-that-is-at-least-32-bytes"})
    with app.app_context():
        db.create_all()
        db.session.add(CrimeType(name="theft"))
        for index in range(3):
            db.session.add(CrimeReport(crime_type="theft", title=f"Theft report {index}", description="Private detail must never be exposed.", latitude=6.5244, longitude=3.3792, incident_datetime=datetime(2026, 8, 20 + index, 10, 0), status="approved", risk_level="high"))
        db.session.commit()
    response = app.test_client().get("/api/v1/reports?crime_type=theft&risk_level=high&page=2&per_page=2")
    assert response.status_code == 200
    assert response.json["data"]["pagination"] == {"page": 2, "per_page": 2, "total": 3, "pages": 2}
    assert len(response.json["data"]["reports"]) == 1
    assert "description" not in response.json["data"]["reports"][0]
    assert app.test_client().get("/api/v1/reports?risk_level=invalid").status_code == 400


def test_api_logout_revokes_token_server_side():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "JWT_SECRET_KEY": "test-secret-that-is-at-least-32-bytes"})
    with app.app_context():
        db.create_all()
        user = User(name="Member", email="member@example.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
    client = app.test_client()
    login = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "password"})
    token = login.json["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/me/reports", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    with app.app_context():
        assert db.session.scalar(db.select(RevokedToken)) is not None
    assert client.get("/api/v1/me/reports", headers=headers).status_code == 401


def test_notifications_api_marks_only_the_recipient_notification_read():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "JWT_SECRET_KEY": "test-secret-that-is-at-least-32-bytes"})
    with app.app_context():
        db.create_all()
        user = User(name="Member", email="member@example.com", password_hash=generate_password_hash("password"))
        other = User(name="Other", email="other@example.com", password_hash="hash")
        db.session.add_all([user, other]); db.session.flush()
        notification = Notification(recipient_id=user.id, notification_type="report_approved", title="Approved", message="Your report was approved.")
        foreign = Notification(recipient_id=other.id, notification_type="report_approved", title="Approved", message="Other user's update.")
        db.session.add_all([notification, foreign]); db.session.commit(); notification_id, foreign_id = notification.id, foreign.id
    client = app.test_client(); token = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "password"}).json["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert len(client.get("/api/v1/notifications", headers=headers).json["data"]["notifications"]) == 1
    assert client.post(f"/api/v1/notifications/{foreign_id}/read", headers=headers).status_code == 404
    assert client.post(f"/api/v1/notifications/{notification_id}/read", headers=headers).json["data"]["notification"]["is_read"] is True
