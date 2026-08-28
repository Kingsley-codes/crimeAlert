"""Crime category persistence model."""

from app.extensions import db


class CrimeType(db.Model):
    __tablename__ = "crime_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, server_default=db.true())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    reports = db.relationship("CrimeReport", back_populates="crime_type_definition")

    def __repr__(self) -> str:
        return f"<CrimeType id={self.id} name={self.name!r}>"
