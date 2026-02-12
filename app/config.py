import os

class Config:
    """Configuración base de la aplicación."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'seventeen_secret_key_2024'
    MAX_CONTENT_LENGTH = 250 * 1024 * 1024  # 250MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or '/tmp'
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
