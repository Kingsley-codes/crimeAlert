"""Persisted JWT revocations so an API logout invalidates the token server-side."""

from app.extensions import db


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    jti = db.Column(db.String(36), primary_key=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
