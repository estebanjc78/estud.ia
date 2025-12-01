# api/auth.py

from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User, Profile
from extensions import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ----------------------------------------------
# GET: FORMULARIO DE LOGIN
# ----------------------------------------------
@auth_bp.get("/login")
def login_form():
    # Si ya está logueado → lo enviamos al home para no romper flujo
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    return render_template("login.html")


# ----------------------------------------------
# POST: PROCESAR LOGIN
# ----------------------------------------------
@auth_bp.post("/login")
def login_submit():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        flash("Email y contraseña son obligatorios.", "error")
        return redirect(url_for("auth.login_form"))

    # Buscar usuario
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        flash("Credenciales inválidas.", "error")
        return redirect(url_for("auth.login_form"))

    # Verificar que tenga perfil asociado (obligatorio en la arquitectura)
    profile = Profile.query.filter_by(user_id=user.id).first()
    if not profile:
        flash("El usuario no tiene un perfil asignado.", "error")
        return redirect(url_for("auth.login_form"))

    # Login OK
    login_user(user)

    # Redirigir según rol
    if profile.role.name == "PROFESOR":
        return redirect(url_for("profe"))

    if profile.role.name == "ALUMNO":
        return redirect(url_for("alumno_portal"))

    if profile.role.name in ("ADMIN", "ADMIN_COLEGIO"):
        return redirect(url_for("admin.admin_usuarios"))

    # Fallback
    return redirect(url_for("home"))


# ----------------------------------------------
# LOGOUT
# ----------------------------------------------
@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_form"))


# ----------------------------------------------
# PERFIL DEL USUARIO (VER / EDITAR)
# ----------------------------------------------
@auth_bp.get("/profile")
@login_required
def profile():
    """
    Muestra la pantalla de perfil del usuario:
    - email (User)
    - nombre completo, rol, institución (Profile)
    """
    profile = Profile.query.filter_by(user_id=current_user.id).first()

    return render_template(
        "profile.html",
        user=current_user,
        profile=profile,
    )


@auth_bp.post("/profile")
@login_required
def update_profile():
    """
    Actualiza datos básicos del perfil (por ahora solo full_name).
    """
    profile = Profile.query.filter_by(user_id=current_user.id).first()

    if not profile:
        flash("No se encontró un perfil asociado al usuario.", "error")
        return redirect(url_for("auth.profile"))

    full_name = (request.form.get("full_name") or "").strip()

    if not full_name:
        flash("El nombre no puede estar vacío.", "error")
        return redirect(url_for("auth.profile"))

    profile.full_name = full_name
    db.session.commit()

    flash("Perfil actualizado correctamente.", "success")
    return redirect(url_for("auth.profile"))


# ----------------------------------------------
# CAMBIO DE CONTRASEÑA PROPIO
# ----------------------------------------------
@auth_bp.post("/change_password")
@login_required
def change_password():
    """
    Permite al usuario cambiar su propia contraseña.

    Espera por POST (form HTML):
      - current_password
      - new_password
      - confirm_password
    """
    current_password = (request.form.get("current_password") or "").strip()
    new_password = (request.form.get("new_password") or "").strip()
    confirm_password = (request.form.get("confirm_password") or "").strip()

    if not current_password or not new_password or not confirm_password:
        flash("Todos los campos de contraseña son obligatorios.", "error")
        return redirect(url_for("auth.profile"))

    # Validar contraseña actual
    if not current_user.check_password(current_password):
        flash("La contraseña actual no es correcta.", "error")
        return redirect(url_for("auth.profile"))

    # Validar coincidencia
    if new_password != confirm_password:
        flash("La nueva contraseña y su confirmación no coinciden.", "error")
        return redirect(url_for("auth.profile"))

    # Validar longitud mínima básica
    if len(new_password) < 8:
        flash("La nueva contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("auth.profile"))

    # Actualizar
    current_user.set_password(new_password)
    db.session.commit()

    flash("Contraseña actualizada correctamente.", "success")
    return redirect(url_for("auth.profile"))
