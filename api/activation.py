from flask import request, render_template, redirect, url_for
from datetime import datetime
from werkzeug.security import generate_password_hash
from extensions import db
from models import Profile
from . import api_bp

@api_bp.get("/activate/<token>")
def activate_form(token):
    profile = Profile.query.filter_by(activation_token=token).first()

    if not profile:
        return "Token inválido", 400

    if profile.activation_expires and profile.activation_expires < datetime.utcnow():
        return "El enlace expiró", 400

    return render_template("activate_account.html", token=token)


@api_bp.post("/activate/<token>")
def activate_submit(token):
    profile = Profile.query.filter_by(activation_token=token).first()

    if not profile:
        return "Token inválido", 400

    if profile.activation_expires and profile.activation_expires < datetime.utcnow():
        return "El enlace expiró", 400

    password = request.form.get("password")
    if not password:
        return "Debes ingresar una contraseña", 400

    user = profile.user
    user.password_hash = generate_password_hash(password)

    profile.activation_token = None
    profile.activation_expires = None

    db.session.commit()

    return redirect(url_for("auth.login_form"))