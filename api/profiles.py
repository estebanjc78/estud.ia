from flask import request, jsonify
from flask_login import login_required
from extensions import db
from models import Profile, User, RoleEnum
from . import api_bp
from datetime import datetime, timedelta
import uuid

@api_bp.post("/institutions/<int:inst_id>/profiles")
@login_required
def create_profile(inst_id):
    data = request.json or {}
    
    email = data["email"]
    full_name = data["full_name"]
    role = RoleEnum(data["role"])

    # Buscar usuario existente
    user = User.query.filter_by(email=email).first()

    # Si el usuario no existe, crearlo
    if not user:
        user = User(email=email)

        # 🔹 Caso especial: Padre — no tiene contraseña inicial
        if role == RoleEnum.PADRE:
            user.password_hash = None  
        else:
            user.set_password(data.get("password", "cambiar123"))

        db.session.add(user)
        db.session.flush()

    # Crear perfil
    profile = Profile(
        user_id=user.id,
        institution_id=inst_id,
        role=role,
        full_name=full_name,
    )
    db.session.add(profile)
    db.session.flush()

    # 🔹 Caso Padre: generar magic link + token + expiración
    if role == RoleEnum.PADRE:
        token = str(uuid.uuid4())
        expires = datetime.utcnow() + timedelta(hours=72)

        profile.activation_token = token
        profile.activation_expires = expires
        db.session.commit()

        magic_link = f"http://localhost:5000/api/activate/{token}"

        # Log temporal hasta implementar envío real
        print(f"[MAGIC LINK PADRE] {magic_link}")

        return jsonify({
            "id": profile.id,
            "status": "pending_activation",
            "magic_link": magic_link
        })

    # 🔹 Otros roles siguen flujo normal
    db.session.commit()

    return jsonify({"id": profile.id, "status": "created"})