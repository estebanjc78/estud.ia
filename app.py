# app.py
from flask import Flask, render_template, redirect, url_for
from flask_migrate import Migrate
from flask_login import current_user, login_required

from config import Config
from extensions import db, login_manager


def create_app() -> Flask:
    """
    App factory.
    - Carga configuración
    - Inicializa extensiones
    - Registra blueprints
    - Conecta migraciones
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # Extensiones
    db.init_app(app)
    login_manager.init_app(app)

    # User loader para Flask-Login
    from models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Blueprints de la capa API / UI
    from api import api_bp
    from api.auth import auth_bp
    from api.admin import admin_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    # Migraciones (Alembic/Flask-Migrate)
    Migrate(app, db)

    # Config visual básica disponible en todos los templates
    @app.context_processor
    def inject_ui_config():
        """
        Expone en los templates:
          config.school_name
          config.school_logo

        Si el usuario tiene institución asociada, usa esos datos.
        Si no, deja None (los templates pueden manejar el fallback).
        """
        school_name = None
        school_logo = None

        if current_user.is_authenticated:
            from models import Profile
            profile = Profile.query.filter_by(user_id=current_user.id).first()
            inst = getattr(profile, "institution", None)
            if inst:
                school_name = inst.name
                school_logo = inst.logo_url

        return {"config": {"school_name": school_name, "school_logo": school_logo}}

    return app


app = create_app()


@app.get("/")
def home():
    """
    Entrada principal:
    - Si no está logueado → pantalla de login
    - Si está logueado → redirige según rol (profesor / alumno)
    """
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login_form"))

    from models import Profile, RoleEnum

    profile = Profile.query.filter_by(user_id=current_user.id).first()

    if profile:
        if profile.role == RoleEnum.PROFESOR:
            return redirect(url_for("profe"))
        if profile.role == RoleEnum.ALUMNO:
            return redirect(url_for("alumno_portal"))

    # Otros roles o sin perfil: por ahora van al dashboard de profesor
    return redirect(url_for("profe"))


@app.get("/profe")
@login_required
def profe():
    """
    Vista principal del profesor.
    La lógica de datos (actividades, métricas, etc.) se cargará más adelante.
    """
    return render_template("profe_dashboard.html", resumen=[])


@app.get("/alumno/portal")
@login_required
def alumno_portal():
    """
    Vista principal del alumno.
    Muestra un resumen de actividades, puntos, etc.
    """
    from models import Profile

    profile = Profile.query.filter_by(user_id=current_user.id).first()
    alumno_name = profile.full_name if profile else None

    return render_template("alumno_portal.html", alumno=alumno_name, resumen=[])


@app.get("/tareas")
@login_required
def tareas():
    """
    Punto de entrada para la vista de tareas.
    La implementación real de listado/gestión de tareas
    se conectará cuando tengamos modelo + API + template definidos.
    """
    # Si ya tienes templates/tareas.html, usamos ese.
    # Si no existe aún, puedes dejar un stub simple:
    #   return "Tareas - pendiente de implementación", 200
    return render_template("tareas.html")
    # return "Tareas - pendiente de implementación", 200


if __name__ == "__main__":
    app.run(debug=True)