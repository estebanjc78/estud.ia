# api/admin.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_login import login_required

from extensions import db
from models import User, Profile, Institution, RoleEnum
from api.utils.permissions import require_roles

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/usuarios")
@login_required
@require_roles("ADMIN")
def admin_usuarios():
    """
    Pantalla de administración básica de usuarios:
    - Lista usuarios + perfiles
    - Formulario para crear nuevo usuario
    """
    usuarios = User.query.all()
    perfiles = Profile.query.all()
    instituciones = Institution.query.all()
    roles = list(RoleEnum)

    perfiles_por_user = {}
    for p in perfiles:
        perfiles_por_user.setdefault(p.user_id, []).append(p)

    return render_template(
        "admin_config.html",
        usuarios=usuarios,
        perfiles_por_user=perfiles_por_user,
        instituciones=instituciones,
        roles=roles,
    )


@admin_bp.post("/usuarios/nuevo")
@login_required
@require_roles("ADMIN")
def admin_crear_usuario():
    """
    Crea un usuario + perfil asociado.
    Espera por POST (form HTML):
      - email
      - password
      - full_name
      - role (nombre del enum, ej: 'PROFESOR', 'ALUMNO', 'ADMIN' si existe)
      - institution_id
    """
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    full_name = request.form.get("full_name", "").strip()
    role_name = request.form.get("role", "").strip()
    institution_id = request.form.get("institution_id", "").strip()

    if not email or not password or not full_name or not role_name or not institution_id:
        flash("Todos los campos son obligatorios.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    # Validar role
    try:
        role = RoleEnum[role_name]
    except KeyError:
        flash("Rol inválido.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    # Validar institución
    institution = Institution.query.get(int(institution_id))
    if not institution:
        flash("Institución inválida.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    # ¿Ya existe usuario con ese email?
    existing = User.query.filter_by(email=email).first()
    if existing:
        flash("Ya existe un usuario con ese email.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    # Crear usuario
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # para tener user.id

    # Crear perfil
    profile = Profile(
        user_id=user.id,
        institution_id=institution.id,
        role=role,
        full_name=full_name,
    )
    db.session.add(profile)

    db.session.commit()

    flash("Usuario creado correctamente.", "success")
    return redirect(url_for("admin.admin_usuarios"))


@admin_bp.post("/usuarios/<int:user_id>/reset_password")
@login_required
@require_roles("ADMIN")
def admin_reset_password(user_id):
    """
    Resetea la contraseña de un usuario.
    Espera:
      - new_password (POST form)
    """
    new_password = request.form.get("new_password", "").strip()
    if not new_password:
        flash("La nueva contraseña no puede estar vacía.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    user = User.query.get(user_id)
    if not user:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    user.set_password(new_password)
    db.session.commit()

    flash("Contraseña actualizada.", "success")
    return redirect(url_for("admin.admin_usuarios"))