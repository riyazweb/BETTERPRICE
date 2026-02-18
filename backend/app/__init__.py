import json
import logging
from datetime import datetime

from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "context") and isinstance(record.context, dict):
            payload["context"] = record.context
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(app: Flask) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(app.config.get("LOG_LEVEL", "INFO"))
    app.logger.propagate = False


def create_app(config_object: str = "config.DevelopmentConfig") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    if (
        not app.config.get("DEBUG", False)
        and not app.config.get("TESTING", False)
        and app.config.get("SECRET_KEY") == "dev-secret-key"
    ):
        raise RuntimeError("SECRET_KEY must be set in production environment")

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    db.init_app(app)
    configure_logging(app)

    from .routes import api_blueprint

    app.register_blueprint(api_blueprint, url_prefix="/api/v1")

    with app.app_context():
        from . import models

        db.create_all()

    return app
