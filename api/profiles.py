from flask import request, jsonify, url_for
from flask_login import login_required
from extensions import db
from models import Profile, User, RoleEnum
from . import api_bp
from datetime import datetime, timedelta
import uuid


@api_bp.post("/institutions/<int:inst_id>/profiles")
@login_required
def create_profile(inst_id):
    """
    Crea un usuario + perfil asociado dentro de una institución.
    Flujo:
      - Si el usuario no existe → se crea
      - Si el rol es PADRE → se genera un magic link (sin contraseña inicial)
      - Otros roles → se asigna contraseña inicial
    """
    data = request.json or {}

    # Campos mínimos obligatorios
    email = data.get("email", "").strip().lower()
    full_name = data.get("full_name", "").strip()
    role_raw = data.get("role")

    if not email or not full_name or not role_raw:
        return jsonify({"error": "email, full_name y role son obligatorios"}), 400

    try:
        role = RoleEnum(role_raw)
    except ValueError:
        return jsonify({"error": "Role inválido"}), 400

    # Buscar usuario ya existente
    user = User.query.filter_by(email=email).first()

    # Si no existe, crear usuario
    if not user:
        user = User(email=email)

        if role == RoleEnum.PADRE:
            # Padres no tienen contraseña inicial → deberán activarse
            user.password_hash = None
        else:
            # Para profesores/alumnos/otros
            user.set_password(data.get("password", "cambiar123"))

        db.session.add(user)
        db.session.flush()  # obtener user.id

    # Crear perfil asociado
    profile = Profile(
        user_id=user.id,
        institution_id=inst_id,
        role=role,
        full_name=full_name,
    )

    db.session.add(profile)
    db.session.flush()

    # -------------------------------
    # 🔹 Caso PADRE: Magic Link
    # -------------------------------
    if role == RoleEnum.PADRE:
        token = str(uuid.uuid4())
        expires = datetime.utcnow() + timedelta(hours=72)

        profile.activation_token = token
        profile.activation_expires = expires
        db.session.commit()

        # Endpoint real definido en activation.py
        magic_link = url_for(
            "api.activate_form",
            token=token,
            _external=True  # construye http://host:puerto
        )

        # TEMPORAL → hasta implementar email real
        print(f"[MAGIC LINK PADRE] {magic_link}")

        return jsonify({
            "id": profile.id,
            "status": "pending_activation",
            "magic_link": magic_link
        }), 201

    # -------------------------------
    # Otros roles → creación normal
    # -------------------------------
    db.session.commit()

    return jsonify({
        "id": profile.id,
        "status": "created"
    }), 201