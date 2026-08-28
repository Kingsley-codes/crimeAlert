from app import create_app


def test_factory_uses_database_url_configuration():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})

    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert "migrate" in app.extensions


def test_home_page_loads():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"Crime Reporting System" in response.data

