from datetime import datetime

from . import db


class SearchHistory(db.Model):
    __tablename__ = "search_history"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048), nullable=False, index=True)
    marketplace = db.Column(db.String(32), nullable=False, index=True)
    source = db.Column(db.String(64), nullable=False, default="buyhatke")
    detected_price = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(16), nullable=False, index=True)
    error_message = db.Column(db.String(1024), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
