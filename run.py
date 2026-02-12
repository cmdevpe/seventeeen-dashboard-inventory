from app import create_app
import os

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

if __name__ == '__main__':
    print("Servidor iniciando en http://localhost:5000")
    app.run(port=5000)
