from app.extensions import db
from app.models.event import Event


def registrar_evento(user_id, event_type, entity_id=None):
    """Registra un evento de funnel. Silencioso: nunca propaga excepciones."""
    try:
        db.session.add(Event(user_id=user_id, event_type=event_type, entity_id=entity_id))
        db.session.flush()
    except Exception:
        pass
