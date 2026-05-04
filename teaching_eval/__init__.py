from flask import Flask
from .db import init_db
from .routes_public import public_bp
from .routes_admin import admin_bp


def create_app() -> Flask:
    from config import BaseConfig

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(BaseConfig)

    init_db(app.config["DB_PATH"])

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    return app
