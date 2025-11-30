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

    if profile.role.name == "ADMIN":
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