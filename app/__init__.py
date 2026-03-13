"""Flask application factory for the Medicaid Provider Spending dashboard."""

from flask import Flask

from app.config import Config


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.models import db
    db.init_app(app)

    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.providers import bp as providers_bp
    from app.routes.spending import bp as spending_bp
    from app.routes.addresses import bp as addresses_bp
    from app.routes.analysis import bp as analysis_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(providers_bp)
    app.register_blueprint(spending_bp)
    app.register_blueprint(addresses_bp)
    app.register_blueprint(analysis_bp)

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    return app
