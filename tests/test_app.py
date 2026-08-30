from datetime import datetime

from app import create_app
from app.extensions import db
from app.models.crime_report import CrimeReport
from app.models.crime_type import CrimeType
from app.models.user import User
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
