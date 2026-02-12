from flask import Blueprint, render_template, session, send_from_directory, current_app
from app.services.inventory_service import InventoryService
import os

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
def index():
    """Ruta principal."""
    # Asegurar sesión
    InventoryService.get_user_session()
    return render_template('index.html')

@views_bp.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'img'),
        'logo.png',
        mimetype='image/png'
    )
