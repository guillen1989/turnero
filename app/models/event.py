from datetime import datetime, timezone

from app.extensions import db


class Event(db.Model):
    __tablename__ = "event"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)
    entity_id  = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
