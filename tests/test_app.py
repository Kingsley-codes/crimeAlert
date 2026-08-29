from datetime import datetime

from app import create_app
from app.extensions import db
from app.models.crime_report import CrimeReport
from app.models.crime_type import CrimeType
from app.models.user import User


def test_factory_uses_database_url_configuration():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})

    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert "migrate" in app.extensions


def test_home_page_loads():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"Crime Reporting System" in response.data


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

        response = client.get("/my-reports")

        assert response.status_code == 200
        assert b"Owner&#39;s newest report" in response.data
        assert b"Owner&#39;s older report" in response.data
        assert response.data.index(b"Owner&#39;s newest report") < response.data.index(b"Owner&#39;s older report")
        assert b"Other user&#39;s private report" not in response.data
        assert b"owner@example.com" not in response.data
        assert client.get(f"/my-reports/{newer.id}").status_code == 200
        assert client.get(f"/my-reports/{other.id}").status_code == 404
