from flask import Flask, jsonify
from flask_cors import CORS
from app.config import config

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    CORS(app, supports_credentials=True)

    # Error handler global para excepciones no capturadas
    @app.errorhandler(Exception)
    def handle_exception(e):
        print(f"Unhandled error: {type(e).__name__}: {e}")
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    # Registro de Blueprints
    from app.routes.api import api_bp
    from app.routes.views import views_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    return app
