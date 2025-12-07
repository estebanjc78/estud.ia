# api/admin.py

import os

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)
from flask_login import login_required, current_user

from extensions import db
from models import User, Profile, Institution, RoleEnum, Grade, Section
from api.utils.permissions import require_roles, get_current_profile
from api.institution import _normalize_hex_color, _normalize_rewards
from services import save_logo

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/usuarios")
@login_required
@require_roles("ADMIN", "ADMIN_COLEGIO")
def admin_usuarios():
    """
    Pantalla de administración básica de usuarios:
    - Lista usuarios + perfiles
    - Formulario para crear nuevo usuario
    """
    profile = get_current_profile()
    instituciones = _institutions_for_profile(profile)
    if not instituciones:
        flash("Crea una institución desde 'Estructura escolar' antes de agregar usuarios.", "info")

    if profile and profile.role and profile.role.name == "ADMIN":
        return redirect(url_for("owner_institutions"))

    if profile and profile.role and profile.role.name != "ADMIN":
        usuarios = (
            User.query.join(User.profiles)
            .filter(Profile.institution_id == profile.institution_id)
            .distinct()
            .order_by(User.email.asc())
            .all()
        )
        perfiles = (
            Profile.query.filter_by(institution_id=profile.institution_id)
            .order_by(Profile.full_name.asc())
            .all()
        )
    else:
        usuarios = User.query.order_by(User.email.asc()).all()
        perfiles = Profile.query.order_by(Profile.full_name.asc()).all()
    roles = list(RoleEnum)

    perfiles_por_user = {}
    for p in perfiles:
        perfiles_por_user.setdefault(p.user_id, []).append(p)

    perfiles_visible: dict[int, list] = {}
    usuarios_visibles: list[User] = []
    manageable_users: dict[int, bool] = {}
    viewer_is_owner = bool(profile and profile.role and profile.role.name == "ADMIN")

    for usuario in usuarios:
        perfiles_usuario = perfiles_por_user.get(usuario.id, [])
        if not viewer_is_owner:
            perfiles_usuario = [
                p for p in perfiles_usuario if getattr(p.role, "name", None) != "ADMIN"
            ]
        if not perfiles_usuario:
            continue
        perfiles_visible[usuario.id] = perfiles_usuario
        usuarios_visibles.append(usuario)
        manageable_users[usuario.id] = _can_manage_user(profile, usuario)

    return render_template(
        "admin_config.html",
        usuarios=usuarios_visibles,
        perfiles_por_user=perfiles_visible,
        instituciones=instituciones,
        has_institutions=bool(instituciones),
        roles=roles,
        manageable_users=manageable_users,
        can_manage_all=viewer_is_owner,
        is_admin=True,
    )


@admin_bp.post("/usuarios/nuevo")
@login_required
@require_roles("ADMIN_COLEGIO")
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
@require_roles("ADMIN_COLEGIO")
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


@admin_bp.post("/perfiles/<int:profile_id>/update")
@login_required
@require_roles("ADMIN", "ADMIN_COLEGIO")
def admin_update_profile(profile_id):
    current_profile = get_current_profile()
    if not current_profile:
        abort(403)

    profile = Profile.query.get_or_404(profile_id)
    if not _can_manage_profile(current_profile, profile):
        flash("No tenés permisos para editar este perfil.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    full_name = (request.form.get("full_name") or "").strip()
    role_name = (request.form.get("role") or "").strip()
    institution_raw = request.form.get("institution_id")

    if not full_name or not role_name:
        flash("Nombre y rol son obligatorios.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    try:
        new_role = RoleEnum[role_name]
    except KeyError:
        flash("Rol inválido.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    if current_profile.role.name != "ADMIN" and new_role.name == "ADMIN":
        flash("Solo un administrador global puede asignar el rol ADMIN.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    if current_profile.role.name == "ADMIN":
        try:
            institution_id = int(institution_raw) if institution_raw else None
        except (TypeError, ValueError):
            institution_id = None
        institution = Institution.query.get(institution_id) if institution_id else None
        if not institution:
            flash("Selecciona una institución válida.", "error")
            return redirect(url_for("admin.admin_usuarios"))
    else:
        institution_id = current_profile.institution_id

    profile.full_name = full_name
    profile.role = new_role
    profile.institution_id = institution_id
    db.session.commit()

    flash("Perfil actualizado correctamente.", "success")
    return redirect(url_for("admin.admin_usuarios"))


@admin_bp.post("/usuarios/<int:user_id>/delete")
@login_required
@require_roles("ADMIN", "ADMIN_COLEGIO")
def admin_delete_user(user_id):
    profile = get_current_profile()
    if not profile:
        abort(403)

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("No podés eliminar tu propia cuenta.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    if not _can_manage_user(profile, user):
        flash("No tenés permisos para eliminar este usuario.", "error")
        return redirect(url_for("admin.admin_usuarios"))

    db.session.delete(user)
    db.session.commit()

    flash("Usuario eliminado.", "success")
    return redirect(url_for("admin.admin_usuarios"))


@admin_bp.route("/estructura", methods=["GET", "POST"])
@login_required
@require_roles("ADMIN_COLEGIO", "ADMIN")
def admin_structure():
    profile = get_current_profile()
    institutions = _institutions_for_profile(profile)
    selected_id = (
        request.args.get("institution_id")
        or request.form.get("target_institution_id")
        or (profile.institution_id if profile and profile.institution_id else None)
    )
    selected_institution = None
    if selected_id:
        try:
            selected_int = int(selected_id)
        except (TypeError, ValueError):
            selected_int = None
        if selected_int:
            selected_institution = next(
                (inst for inst in institutions if inst.id == selected_int),
                None,
            )
    if not selected_institution and institutions:
        selected_institution = institutions[0]

    allow_ai_config = bool(profile and profile.role and profile.role.name == "ADMIN")
    can_create_institution = bool(
        profile
        and profile.role
        and (profile.role.name == "ADMIN" or not institutions)
    )
    ai_provider_options = [
        {"value": "", "label": "Config. global (según entorno)"},
        {"value": "openai", "label": "OpenAI (usa API global)"},
        {"value": "heuristic", "label": "Heurístico local"},
    ]
    ai_model_default_hint = os.getenv("AI_MODEL") or "gpt-4o-mini"

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_institution":
            if not can_create_institution:
                flash("No tienes permisos para crear instituciones.", "error")
                return redirect(url_for("admin.admin_structure"))

            name = (request.form.get("name") or "").strip()
            short_code = (request.form.get("short_code") or "").strip().upper() or None
            primary_color = request.form.get("primary_color")
            secondary_color = request.form.get("secondary_color")
            logo_url = (request.form.get("logo_url") or "").strip() or None
            ai_provider = None
            ai_model = None
            if allow_ai_config:
                ai_provider = (request.form.get("ai_provider") or "").strip().lower() or None
                ai_model = (request.form.get("ai_model") or "").strip() or None
                if ai_provider and ai_provider not in {"openai", "heuristic"}:
                    flash("Proveedor de IA inválido.", "error")
                    return redirect(url_for("admin.admin_structure"))

            if not name:
                flash("El nombre del colegio es obligatorio.", "error")
                return redirect(url_for("admin.admin_structure"))

            if short_code and Institution.query.filter_by(short_code=short_code).first():
                flash("Ya existe una institución con ese código.", "error")
                return redirect(url_for("admin.admin_structure"))

            try:
                normalized_primary = _normalize_hex_color(primary_color) or "#1F4B99"
                normalized_secondary = _normalize_hex_color(secondary_color) or "#9AB3FF"
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("admin.admin_structure"))
            institution = Institution(
                name=name,
                short_code=short_code,
                primary_color=normalized_primary,
                secondary_color=normalized_secondary,
                logo_url=logo_url,
                ai_provider=ai_provider if allow_ai_config else None,
                ai_model=ai_model or None if allow_ai_config else None,
            )
            db.session.add(institution)
            db.session.commit()

            flash("Institución creada correctamente.", "success")
            return redirect(
                url_for("admin.admin_structure", institution_id=institution.id)
            )

        if action == "create_grade":
            if not selected_institution:
                flash("Selecciona una institución antes de crear grados.", "error")
                return redirect(url_for("admin.admin_structure"))

            name = (request.form.get("grade_name") or "").strip()
            level = (request.form.get("grade_level") or "").strip() or None
            order_raw = request.form.get("grade_order")

            if not name:
                flash("El nombre del grado es obligatorio.", "error")
                return redirect(
                    url_for(
                        "admin.admin_structure", institution_id=selected_institution.id
                    )
                )

            try:
                order_index = int(order_raw) if order_raw else None
            except ValueError:
                order_index = None

            grade = Grade(
                institution_id=selected_institution.id,
                name=name,
                level=level,
                order_index=order_index,
            )
            db.session.add(grade)
            db.session.commit()

            flash("Grado creado correctamente.", "success")
            return redirect(
                url_for("admin.admin_structure", institution_id=selected_institution.id)
            )

        if action == "create_section":
            if not selected_institution:
                flash("Selecciona una institución para agregar secciones.", "error")
                return redirect(url_for("admin.admin_structure"))

            section_name = (request.form.get("section_name") or "").strip()
            grade_id_raw = request.form.get("grade_id")
            try:
                grade_id = int(grade_id_raw)
            except (TypeError, ValueError):
                grade_id = None

            grade = (
                Grade.query.filter_by(
                    id=grade_id, institution_id=selected_institution.id
                ).first()
                if grade_id
                else None
            )

            if not grade or not section_name:
                flash("Selecciona un grado válido e ingresa el nombre de la sección.", "error")
                return redirect(
                    url_for("admin.admin_structure", institution_id=selected_institution.id)
                )

            section = Section(grade_id=grade.id, name=section_name)
            db.session.add(section)
            db.session.commit()

            flash("Sección creada correctamente.", "success")
            return redirect(
                url_for("admin.admin_structure", institution_id=selected_institution.id)
            )

        flash("Acción inválida.", "error")
        return redirect(
            url_for(
                "admin.admin_structure",
                institution_id=selected_institution.id if selected_institution else None,
            )
        )

    grades = (
        Grade.query.filter_by(institution_id=selected_institution.id)
        .order_by(Grade.order_index.asc().nullslast(), Grade.name.asc())
        .all()
        if selected_institution
        else []
    )

    return render_template(
        "admin_structure.html",
        institutions=institutions,
        selected_institution=selected_institution,
        grades=grades,
        can_create_institution=can_create_institution,
        ai_provider_options=ai_provider_options,
        ai_model_default_hint=ai_model_default_hint,
        allow_ai_config=allow_ai_config,
        profile=profile,
        is_admin=True,
    )


@admin_bp.route("/cms", methods=["GET", "POST"])
@login_required
@require_roles("ADMIN_COLEGIO")
def cms():
    profile = get_current_profile()
    institutions = _institutions_for_profile(profile)
    can_edit_ai = bool(profile and profile.role and profile.role.name == "ADMIN")
    ai_provider_options = [
        {"value": "", "label": "Config. global (según entorno)"},
        {"value": "openai", "label": "OpenAI (usa API global)"},
        {"value": "heuristic", "label": "Heurístico local"},
    ]
    ai_model_default_hint = os.getenv("AI_MODEL") or "gpt-4o-mini"

    inst = None
    requested_id = request.args.get("institution_id") or request.form.get("institution_id")
    if requested_id:
        try:
            requested_int = int(requested_id)
        except (TypeError, ValueError):
            requested_int = None
        if requested_int:
            inst = next((i for i in institutions if i.id == requested_int), None)

    if not inst and institutions:
        inst = institutions[0]

    if not inst:
        flash("Aún no hay institución configurada. Usá 'Estructura escolar' para crearla.", "error")
        return redirect(url_for("admin.admin_structure"))

    if request.method == "POST":
        name = (request.form.get("name") or inst.name).strip()
        logo_file = request.files.get("logo_file")
        primary_color = request.form.get("primary_color")
        secondary_color = request.form.get("secondary_color")

        inst.name = name
        saved_logo = save_logo(logo_file)
        inst.logo_url = saved_logo or inst.logo_url

        try:
            normalized_primary = _normalize_hex_color(primary_color)
            normalized_secondary = _normalize_hex_color(secondary_color)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.cms", institution_id=inst.id))

        inst.primary_color = normalized_primary or inst.primary_color
        inst.secondary_color = normalized_secondary or inst.secondary_color

        rewards_payload = []
        for idx in range(1, 4):
            nombre = (request.form.get(f"reward_{idx}_name") or "").strip()
            puntos = request.form.get(f"reward_{idx}_points")
            if not nombre or not puntos:
                continue
            rewards_payload.append({"nombre": nombre, "puntos": puntos})

        try:
            inst.rewards_config = _normalize_rewards(rewards_payload) if rewards_payload else None
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.cms", institution_id=inst.id))

        if can_edit_ai:
            provider_value = (request.form.get("ai_provider") or "").strip().lower()
            if provider_value not in ("", "openai", "heuristic"):
                flash("Proveedor de IA inválido.", "error")
                return redirect(url_for("admin.cms", institution_id=inst.id))
            inst.ai_provider = provider_value or None

            model_value = (request.form.get("ai_model") or "").strip()
            inst.ai_model = model_value or None

        db.session.commit()
        flash("Configuración guardada.", "success")
        return redirect(url_for("admin.cms", institution_id=inst.id))

    return render_template(
        "admin_cms.html",
        institution=inst,
        institutions=institutions,
        recompensas=inst.rewards_config or [],
        ai_provider_options=ai_provider_options,
        ai_model_default_hint=ai_model_default_hint,
        can_edit_ai=can_edit_ai,
        is_admin=True,
    )


def _can_manage_profile(manager_profile, target_profile: Profile) -> bool:
    if not manager_profile or not manager_profile.role:
        return False
    if manager_profile.role.name == "ADMIN":
        return True
    return (
        manager_profile.institution_id
        and target_profile.institution_id == manager_profile.institution_id
    )


def _can_manage_user(manager_profile, user: User) -> bool:
    if not manager_profile or not manager_profile.role:
        return False
    if manager_profile.role.name == "ADMIN":
        return True
    managed_institution = manager_profile.institution_id
    if not managed_institution:
        return False
    return all(
        profile.institution_id == managed_institution
        for profile in user.profiles
    )


def _institutions_for_profile(profile):
    query = Institution.query.order_by(Institution.name.asc())
    if not profile or not profile.role:
        return query.all()
    if profile.role.name == "ADMIN":
        return query.all()
    if profile.institution_id:
        return query.filter_by(id=profile.institution_id).all()
    return []
