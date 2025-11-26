from flask import Blueprint, request, render_template, redirect, url_for
from flask_login import login_user, logout_user, login_required
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.get("/login")
def login_form():
    # Más adelante haremos un template lindo.
    # Por ahora, algo mínimo.
    return render_template("login.html")


@auth_bp.post("/login")
def login_submit():
    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return "Email y contraseña son obligatorios", 400

    user = User.query.filter_by(email=email).first()

    if not user or not hasattr(user, "check_password") or not user.check_password(password):
        # Si tu modelo no tiene check_password, después lo ajustamos.
        return "Credenciales inválidas", 401

    login_user(user)
    return redirect("/")


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_form"))