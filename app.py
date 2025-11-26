# app.py
from flask import Flask
from flask_migrate import Migrate
from config import Config
from extensions import db, login_manager

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)

    # 🔹 1. USER LOADER — DEBE IR AQUÍ (justo después de init_app)
    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 🔹 2. Importar modelos (para que SQLAlchemy registre las tablas)
    from models import Institution, Grade, Section, User, Profile

    # 🔹 3. Registrar blueprints del API
    from api import api_bp
    app.register_blueprint(api_bp)
  
    # 🔹 Registrar auth
    from api.auth import auth_bp
    app.register_blueprint(auth_bp)

    # 🔹 4. Migraciones (DESPUÉS de registrar db + modelos)
    Migrate(app, db)

    return app


app = create_app()

from flask_login import current_user

@app.get("/")
def home():
    if current_user.is_authenticated:
        return f"<h2>Bienvenido {current_user.email}</h2><p><a href='/auth/logout'>Salir</a></p>"
    else:
        return "<h2>No estás logueado</h2><p><a href='/auth/login'>Entrar</a></p>"

if __name__ == "__main__":
    app.run(debug=True)