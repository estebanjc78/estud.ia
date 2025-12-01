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
from models import User, Profile, Institution, RoleEnum, Grade, Section
from api.utils.permissions import require_roles, get_current_profile
from api.institution import _normalize_hex_color, _normalize_rewards

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

    usuarios = User.query.all()
    perfiles = Profile.query.all()
    roles = list(RoleEnum)

    perfiles_por_user = {}
    for p in perfiles:
        perfiles_por_user.setdefault(p.user_id, []).append(p)

    return render_template(
        "admin_config.html",
        usuarios=usuarios,
        perfiles_por_user=perfiles_por_user,
        instituciones=instituciones,
        has_institutions=bool(instituciones),
        roles=roles,
        is_admin=True,
    )


@admin_bp.post("/usuarios/nuevo")
@login_required
@require_roles("ADMIN", "ADMIN_COLEGIO")
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
@require_roles("ADMIN", "ADMIN_COLEGIO")
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


@admin_bp.route("/estructura", methods=["GET", "POST"])
@login_required
@require_roles("ADMIN", "ADMIN_COLEGIO")
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

    can_create_institution = bool(
        profile
        and profile.role
        and (profile.role.name == "ADMIN" or not institutions)
    )

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
            )
            db.session.add(institution)
            db.session.commit()

            if profile and not profile.institution_id:
                profile.institution_id = institution.id
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
        profile=profile,
        is_admin=True,
    )


@admin_bp.route("/cms", methods=["GET", "POST"])
@login_required
@require_roles("ADMIN", "ADMIN_COLEGIO")
def cms():
    profile = get_current_profile()
    institutions = _institutions_for_profile(profile)

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
        logo_url = (request.form.get("logo_url") or "").strip() or inst.logo_url
        primary_color = request.form.get("primary_color")
        secondary_color = request.form.get("secondary_color")

        inst.name = name
        inst.logo_url = logo_url

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

        db.session.commit()
        flash("Configuración guardada.", "success")
        return redirect(url_for("admin.cms", institution_id=inst.id))

    return render_template(
        "admin_cms.html",
        institution=inst,
        institutions=institutions,
        recompensas=inst.rewards_config or [],
        is_admin=True,
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
