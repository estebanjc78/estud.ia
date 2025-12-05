# app.py
import os
from datetime import date, datetime
from pathlib import Path

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    abort,
    flash,
    current_app,
    Response,
    jsonify,
    send_from_directory,
)
from flask_migrate import Migrate
from flask_login import current_user, login_required

from config import Config
from extensions import db, login_manager
from services import (
    ViewDataService,
    InsightsService,
    AIInsightsService,
    HelpUsageService,
    CurriculumService,
    save_logo,
)
from sqlalchemy.exc import OperationalError


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
          config.school_name / config.school_logo / colores / recompensas
          current_profile (para conocer rol)
        """
        from api.services.ui_config_service import UIConfigService
        from models import Profile

        profile = None
        if current_user.is_authenticated:
            profile = Profile.query.filter_by(user_id=current_user.id).first()

        config_data = UIConfigService.get_ui_config_for_user(current_user)
        display_name = _build_display_name(current_user, profile)
        return {
            "config": config_data,
            "current_profile": profile,
            "current_display_name": display_name,
        }

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
        if profile.role == RoleEnum.PSICOPEDAGOGIA:
            return redirect(url_for("psico_panel"))
        if profile.role == RoleEnum.ADMIN_COLEGIO:
            return redirect(url_for("admin.admin_structure"))
        if getattr(RoleEnum, "ADMIN", None) and profile.role == RoleEnum.ADMIN:
            return redirect(url_for("owner_institutions"))

    # Otros roles o sin perfil: por ahora van al dashboard de profesor
    return redirect(url_for("profe"))


@app.get("/profe")
@login_required
def profe():
    """
    Vista principal del profesor con datos reales de clases, tareas y submissions.
    """
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import RoleEnum

    allowed_roles = (
        RoleEnum.PROFESOR,
        getattr(RoleEnum, "ADMIN_COLEGIO", None),
        getattr(RoleEnum, "RECTOR", None),
        getattr(RoleEnum, "PSICOPEDAGOGIA", None),
    )
    if profile.role not in allowed_roles:
        abort(403)

    data = ViewDataService.teacher_dashboard(profile)
    can_edit = profile.role in (
        RoleEnum.PROFESOR,
        getattr(RoleEnum, "ADMIN_COLEGIO", RoleEnum.PROFESOR),
        getattr(RoleEnum, "RECTOR", RoleEnum.PROFESOR),
    )

    resumen = [
        {
            "actividad_tema": submission.task.title if submission.task else "Tarea",
            "alumno": submission.student.full_name if submission.student else "Alumno",
            "cant_ayudas": submission.help_count or 0,
            "cant_respuestas": len(submission.evidences or []),
            "puntos_total": submission.points_awarded,
        }
        for submission in data["submissions"]
    ]

    return render_template(
        "profe_dashboard.html",
        clases_hoy=data["clases_hoy"],
        resumen=resumen,
        lessons=data["lessons"],
        students=data["students"],
        tasks=data["tasks"],
        bitacora_entries=data["bitacora_entries"],
        recent_messages=data["recent_messages"],
        can_edit=can_edit,
        is_admin=_has_admin_role(profile),
        recipient_groups=_build_recipient_groups(profile),
    )


@app.get("/alumno/portal")
@login_required
def alumno_portal():
    """
    Vista principal del alumno con sus tareas y entregas.
    """
    profile = _get_current_profile()
    if not profile:
        abort(403)

    data = ViewDataService.student_portal(profile)

    return render_template(
        "alumno_portal.html",
        alumno=profile.full_name,
        tasks=data["tasks"],
        activities=data["tasks"],
        submissions=data["submissions"],
        bitacora_entries=data["bitacora_entries"],
        is_admin=_has_admin_role(profile),
    )


@app.get("/alumno/tarea/<int:task_id>")
@login_required
def alumno_resolver(task_id: int):
    """
    Vista detallada para que el alumno consulte la consigna y suba evidencia.
    """
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import Task, TaskSubmission

    task = Task.query.get_or_404(task_id)
    if task.institution_id != profile.institution_id:
        abort(404)

    if profile.section_id and task.section_id and task.section_id != profile.section_id:
        abort(403)

    last_submission = (
        TaskSubmission.query.filter_by(task_id=task.id, student_profile_id=profile.id)
        .order_by(TaskSubmission.submitted_at.desc())
        .first()
    )

    help_summary = HelpUsageService.get_summary(task=task, student_profile=profile)

    return render_template(
        "alumno_resolver.html",
        task=task,
        last_submission=last_submission,
        alumno=profile.full_name,
        help_summary=help_summary,
        is_admin=_has_admin_role(profile),
    )


@app.route("/alumno/tarea/<int:task_id>/help", methods=["GET", "POST"])
@login_required
def alumno_help_summary(task_id: int):
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import Task

    task = Task.query.get_or_404(task_id)
    if task.institution_id != profile.institution_id:
        abort(404)
    if profile.section_id and task.section_id and task.section_id != profile.section_id:
        abort(403)

    if request.method == "GET":
        summary = HelpUsageService.get_summary(task=task, student_profile=profile)
        return jsonify(summary)

    data = request.get_json(silent=True) or {}
    help_level = data.get("help_level")
    learning_style = data.get("learning_style")

    if not help_level and not learning_style:
        return jsonify({"error": "Debes indicar un tipo de ayuda o un estilo."}), 400

    try:
        if help_level:
            summary = HelpUsageService.increment_usage(
                task=task,
                student_profile=profile,
                help_level=help_level,
                learning_style=learning_style,
            )
        else:
            summary = HelpUsageService.update_style(
                task=task,
                student_profile=profile,
                learning_style=learning_style,
            )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(summary)


@app.route("/tareas", methods=["GET", "POST"])
@login_required
def tareas():
    """
    Gestión simple de tareas: listado y formulario para crear nuevas con adjuntos.
    """
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import Lesson, Task
    from api.services.attachment_service import AttachmentService

    overview = ViewDataService.tasks_overview(profile)
    lessons = overview["lessons"]
    tasks = overview["tasks"]
    can_create_tasks = overview["can_create_tasks"]

    if request.method == "POST":
        if not can_create_tasks:
            flash("Solo el equipo docente puede crear tareas.", "error")
            return redirect(url_for("tareas"))
        lesson_id = request.form.get("lesson_id")
        title = (request.form.get("title") or "").strip()
        description = request.form.get("description")
        due_date_raw = request.form.get("due_date")
        max_points = request.form.get("max_points")

        lesson = Lesson.query.get(int(lesson_id)) if lesson_id else None
        if not lesson or lesson.institution_id != profile.institution_id or not title:
            flash("Completa los datos obligatorios.", "error")
            return redirect(url_for("tareas"))

        due_date = _safe_parse_date(due_date_raw)
        try:
            max_points_val = int(max_points) if max_points else 100
        except ValueError:
            flash("max_points debe ser numérico.", "error")
            return redirect(url_for("tareas"))

        task = Task(
            institution_id=lesson.institution_id,
            lesson_id=lesson.id,
            section_id=lesson.section_id,
            objective_id=lesson.objective_id,
            title=title,
            description=description,
            due_date=due_date,
            max_points=max_points_val,
        )
        db.session.add(task)
        db.session.flush()

        upload = _save_uploaded_file("task_attachment")
        if upload:
            AttachmentService.create_attachment(
                context_type="task",
                context_id=task.id,
                filename=upload["filename"],
                storage_path=upload["storage_path"],
                mime_type=upload["mime_type"],
                file_size=upload["file_size"],
                kind="task_material",
                uploaded_by_profile_id=profile.id,
                commit=False,
            )

        db.session.commit()
        flash("Tarea creada correctamente.", "success")
        return redirect(url_for("tareas"))

    return render_template(
        "tareas.html",
        tasks=tasks,
        lessons=lessons,
        can_create_tasks=can_create_tasks,
        is_admin=_has_admin_role(profile),
    )


@app.route("/mensajes")
@login_required
def mensajes():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import (
        MessageThread,
        MessageThreadParticipant,
        Message,
        Lesson,
        RoleEnum,
    )

    allowed_roles = (
        RoleEnum.PROFESOR,
        getattr(RoleEnum, "ADMIN_COLEGIO", None),
        getattr(RoleEnum, "PSICOPEDAGOGIA", None),
        getattr(RoleEnum, "RECTOR", None),
    )
    if profile.role not in allowed_roles:
        abort(403)

    threads = (
        MessageThread.query.join(MessageThreadParticipant)
        .filter(MessageThreadParticipant.profile_id == profile.id)
        .order_by(MessageThread.updated_at.desc().nullslast())
        .limit(20)
        .all()
    )

    thread_cards = []
    for thread in threads:
        last_message = thread.messages.order_by(Message.created_at.desc()).first()
        participants = [
            participant.profile.full_name
            for participant in thread.participants
            if participant.profile and participant.profile.id != profile.id
        ]
        thread_cards.append(
            {
                "id": thread.id,
                "subject": thread.subject or "Conversación sin título",
                "updated_at": thread.updated_at,
                "context": thread.context_type,
                "last_message": last_message,
                "participants": participants,
            }
        )

    lessons_query = Lesson.query.filter_by(institution_id=profile.institution_id)
    if profile.role == RoleEnum.PROFESOR:
        lessons_query = lessons_query.filter_by(teacher_profile_id=profile.id)
    lessons = lessons_query.order_by(Lesson.class_date.desc()).limit(20).all()

    return render_template(
        "mensajes.html",
        threads=thread_cards,
        lessons=lessons,
        recipient_groups=_build_recipient_groups(profile),
        is_admin=_has_admin_role(profile),
    )


@app.route("/insights")
@login_required
def insights():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import RoleEnum, Lesson, Profile as ProfileModel, InsightReport

    allowed_roles = (
        RoleEnum.PROFESOR,
        getattr(RoleEnum, "PSICOPEDAGOGIA", None),
        getattr(RoleEnum, "ADMIN_COLEGIO", None),
        getattr(RoleEnum, "RECTOR", None),
    )
    if profile.role not in allowed_roles:
        abort(403)

    metrics = _default_insights_metrics()
    ai_brief = "Aún no generamos KPIs para este perfil."
    try:
        metrics = InsightsService.collect_for_profile(profile)
        ai_brief = InsightsService.generate_ai_brief(metrics)
    except Exception as exc:  # pragma: no cover - fallback para instancias sin datos
        current_app.logger.exception("No se pudieron calcular los Insights: %s", exc)
        flash("No pudimos actualizar los KPIs de Insights. Mostramos datos vacíos.", "warning")

    lessons_query = Lesson.query.filter_by(institution_id=profile.institution_id).order_by(
        Lesson.class_date.desc()
    )
    if profile.role == RoleEnum.PROFESOR:
        lessons_query = lessons_query.filter_by(teacher_profile_id=profile.id)
    lessons = lessons_query.limit(30).all()

    students = (
        ProfileModel.query.filter_by(institution_id=profile.institution_id, role=RoleEnum.ALUMNO)
        .order_by(ProfileModel.full_name.asc())
        .limit(100)
        .all()
    )

    reports_own: list[InsightReport] = []
    reports_shared: list[InsightReport] = []
    try:
        base_query = InsightReport.query.filter_by(institution_id=profile.institution_id)
        own_query = base_query.filter(InsightReport.author_profile_id == profile.id)
        reports_own = own_query.order_by(InsightReport.updated_at.desc()).limit(5).all()

        shared_query = base_query.filter(InsightReport.author_profile_id != profile.id)
        if not _has_admin_role(profile):
            shared_query = shared_query.filter(InsightReport.status == "ready")
        reports_shared = shared_query.order_by(InsightReport.updated_at.desc()).limit(10).all()
    except OperationalError as exc:
        current_app.logger.warning("Tabla insight_report no disponible: %s", exc)
        flash("Aún no habilitaste los reportes IA en la base de datos. Corré las migraciones para ver el historial.", "info")
        reports_own = []
        reports_shared = []

    return render_template(
        "insights.html",
        metrics=metrics,
        ai_brief=ai_brief,
        lessons=lessons,
        students=students,
        reports_own=reports_own,
        reports_shared=reports_shared,
        report_flavors=AIInsightsService.available_flavors(),
        recipient_groups=_build_recipient_groups(profile),
        is_admin=_has_admin_role(profile),
        current_profile_id=profile.id,
    )


@app.post("/insights/report")
@login_required
def create_insight_report():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import ReportScope

    scope_raw = (request.form.get("scope") or "global").lower()
    target_id = request.form.get("target_id")
    flavor = (request.form.get("report_flavor") or "standard").strip().lower()
    custom_prompt = (request.form.get("custom_prompt") or "").strip()
    scope_map = {
        "global": ReportScope.GLOBAL,
        "class": ReportScope.CLASS,
        "student": ReportScope.STUDENT,
    }
    scope = scope_map.get(scope_raw)
    if not scope:
        flash("Tipo de reporte inválido.", "error")
        return redirect(url_for("insights"))

    target_value = int(target_id) if target_id else None
    try:
        report = AIInsightsService.generate_report(
            author=profile,
            scope=scope,
            target_id=target_value,
            flavor=flavor,
            custom_prompt=custom_prompt,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("insights"))
    except OperationalError as exc:
        current_app.logger.exception("No se pudo guardar el reporte IA: %s", exc)
        flash("Necesitás aplicar las migraciones (tabla insight_report) antes de generar reportes con IA.", "error")
        return redirect(url_for("insights"))
    except Exception as exc:
        current_app.logger.exception("Error generando reporte IA: %s", exc)
        flash("El motor de IA no está disponible en este momento. Intenta nuevamente.", "error")
        return redirect(url_for("insights"))

    flash("Reporte generado correctamente.", "success")
    return redirect(url_for("insights", report_id=report.id))


@app.post("/insights/report/<int:report_id>/save")
@login_required
def save_insight_report(report_id: int):
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import InsightReport

    report = InsightReport.query.get_or_404(report_id)
    if report.institution_id != profile.institution_id:
        abort(403)
    if report.author_profile_id != profile.id and not _has_admin_role(profile):
        abort(403)

    final_text = (request.form.get("final_text") or "").strip()
    status = request.form.get("status") or "draft"

    report.final_text = final_text
    report.status = status
    db.session.commit()

    flash("Reporte actualizado.", "success")
    return redirect(url_for("insights", report_id=report.id))


@app.get("/insights/report/<int:report_id>/download")
@login_required
def download_insight_report(report_id: int):
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import InsightReport
    from flask import Response

    report = InsightReport.query.get_or_404(report_id)
    if report.institution_id != profile.institution_id:
        abort(403)

    filename = f"reporte_{report.scope.value}_{report.id}.txt"
    text = report.final_text or report.ai_draft or ""
    return Response(
        text,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/insights/report/<int:report_id>/send")
@login_required
def send_insight_report(report_id: int):
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import InsightReport
    from api.services.messages_service import MessageService

    report = InsightReport.query.get_or_404(report_id)
    if report.institution_id != profile.institution_id:
        abort(403)

    recipient_ids = request.form.getlist("recipient_profile_ids")
    filtered = _filter_recipient_ids(profile, recipient_ids)
    if not filtered:
        flash("Selecciona al menos un destinatario.", "error")
        return redirect(url_for("insights", report_id=report.id))

    subject = (request.form.get("subject") or f"Reporte {report.target_label or report.scope.value}").strip()
    body = report.final_text or report.ai_draft or ""
    if not body:
        flash("El reporte no tiene contenido para enviar.", "error")
        return redirect(url_for("insights", report_id=report.id))

    MessageService.send_message_to_context(
        context_type="report",
        context_id=report.id,
        sender_profile_id=profile.id,
        text=body,
        participant_ids=filtered,
        thread_options={"subject": subject, "force_new": True},
        visibility={"student": True, "parent": True, "teacher": True},
    )

    flash("Reporte enviado por Mensajes.", "success")
    return redirect(url_for("insights", report_id=report.id))


@app.post("/insights/report/<int:report_id>/clone")
@login_required
def clone_insight_report(report_id: int):
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import InsightReport

    report = InsightReport.query.get_or_404(report_id)
    if report.institution_id != profile.institution_id:
        abort(403)

    duplicate = InsightReport(
        institution_id=report.institution_id,
        author_profile_id=profile.id,
        scope=report.scope,
        target_id=report.target_id,
        target_label=report.target_label,
        ai_model=report.ai_model,
        prompt_snapshot=report.prompt_snapshot,
        context_snapshot=report.context_snapshot,
        ai_draft=report.final_text or report.ai_draft,
        final_text=report.final_text or report.ai_draft,
        status="draft",
    )

    db.session.add(duplicate)
    db.session.commit()

    flash("Duplicamos el reporte para que lo edites.", "success")
    return redirect(url_for("insights", report_id=duplicate.id))


@app.route("/owner/institutions", methods=["GET", "POST"])
@login_required
def owner_institutions():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import Institution, Profile as ProfileModel, RoleEnum, User, PlatformTheme
    from api.institution import _normalize_hex_color

    owner_role = getattr(RoleEnum, "ADMIN", None)
    if not owner_role or profile.role != owner_role:
        abort(403)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_institution":
            name = (request.form.get("name") or "").strip()
            short_code = (request.form.get("short_code") or "").strip() or None
            primary_color = request.form.get("primary_color")
            secondary_color = request.form.get("secondary_color")
            logo_file = request.files.get("logo_file")

            if not name:
                flash("El nombre del colegio es obligatorio.", "error")
                return redirect(url_for("owner_institutions"))

            if short_code and Institution.query.filter_by(short_code=short_code).first():
                flash("Ya existe una institución con ese código.", "error")
                return redirect(url_for("owner_institutions"))

            try:
                normalized_primary = _normalize_hex_color(primary_color) or "#1F4B99"
                normalized_secondary = _normalize_hex_color(secondary_color) or "#9AB3FF"
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("owner_institutions"))

            institution = Institution(
                name=name,
                short_code=short_code,
                primary_color=normalized_primary,
                secondary_color=normalized_secondary,
                logo_url=save_logo(logo_file),
            )
            db.session.add(institution)
            db.session.commit()
            flash("Institución creada correctamente.", "success")
            return redirect(url_for("owner_institutions"))

        if action == "update_institution":
            inst_id = request.form.get("institution_id")
            institution = Institution.query.get(inst_id)
            if not institution:
                flash("Institución no encontrada.", "error")
                return redirect(url_for("owner_institutions"))

            name = (request.form.get("name") or institution.name).strip()
            short_code = (request.form.get("short_code") or "").strip() or None
            primary_color = request.form.get("primary_color")
            secondary_color = request.form.get("secondary_color")
            logo_file = request.files.get("logo_file")

            if not name:
                flash("El nombre del colegio es obligatorio.", "error")
                return redirect(url_for("owner_institutions"))

            if short_code and short_code != institution.short_code:
                if Institution.query.filter_by(short_code=short_code).first():
                    flash("Ya existe una institución con ese código.", "error")
                    return redirect(url_for("owner_institutions"))

            try:
                normalized_primary = _normalize_hex_color(primary_color) or institution.primary_color
                normalized_secondary = _normalize_hex_color(secondary_color) or institution.secondary_color
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("owner_institutions"))

            institution.name = name
            institution.short_code = short_code
            saved_logo = save_logo(logo_file)
            institution.logo_url = saved_logo or institution.logo_url
            institution.primary_color = normalized_primary
            institution.secondary_color = normalized_secondary
            db.session.commit()
            flash("Institución actualizada.", "success")
            return redirect(url_for("owner_institutions"))

        if action == "delete_institution":
            inst_id = request.form.get("institution_id")
            institution = Institution.query.get(inst_id)
            if not institution:
                flash("Institución no encontrada.", "error")
                return redirect(url_for("owner_institutions"))
            db.session.delete(institution)
            db.session.commit()
            flash("Institución eliminada.", "success")
            return redirect(url_for("owner_institutions"))

        if action == "update_platform_theme":
            theme = PlatformTheme.current()
            theme.name = (request.form.get("platform_name") or theme.name or "estud.ia").strip()
            theme.subtitle = (request.form.get("platform_subtitle") or theme.subtitle)
            theme.logo_url = (request.form.get("platform_logo") or theme.logo_url)
            theme.primary_color = (_normalize_hex_color(request.form.get("platform_primary")) or theme.primary_color)
            theme.secondary_color = (_normalize_hex_color(request.form.get("platform_secondary")) or theme.secondary_color)
            theme.sidebar_color = (_normalize_hex_color(request.form.get("platform_sidebar")) or theme.sidebar_color)
            theme.sidebar_text_color = (_normalize_hex_color(request.form.get("platform_sidebar_text")) or theme.sidebar_text_color)
            theme.background_color = (_normalize_hex_color(request.form.get("platform_background")) or theme.background_color)
            theme.login_background = (_normalize_hex_color(request.form.get("platform_login_background")) or theme.login_background)
            db.session.commit()
            flash("Tema global actualizado.", "success")
            return redirect(url_for("owner_institutions"))

        if action == "assign_admin":
            inst_id = request.form.get("institution_id")
            email = (request.form.get("admin_email") or "").strip().lower()
            password = (request.form.get("admin_password") or "").strip()
            full_name = (request.form.get("admin_name") or "").strip()

            institution = Institution.query.get(inst_id)
            if not institution:
                flash("Institución no encontrada.", "error")
                return redirect(url_for("owner_institutions"))

            if not email or not password or not full_name:
                flash("Completa nombre, email y contraseña.", "error")
                return redirect(url_for("owner_institutions"))

            if User.query.filter_by(email=email).first():
                flash("Ya existe un usuario con ese email.", "error")
                return redirect(url_for("owner_institutions"))

            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            admin_role = getattr(RoleEnum, "ADMIN_COLEGIO", None)
            if not admin_role:
                flash("Rol ADMIN_COLEGIO no disponible.", "error")
                return redirect(url_for("owner_institutions"))

            profile_admin = ProfileModel(
                user_id=user.id,
                institution_id=institution.id,
                role=admin_role,
                full_name=full_name,
            )
            db.session.add(profile_admin)
            db.session.commit()
            flash("Administrador del colegio creado.", "success")
            return redirect(url_for("owner_institutions"))

        flash("Acción inválida.", "error")
        return redirect(url_for("owner_institutions"))

    institutions = Institution.query.order_by(Institution.name.asc()).all()
    admins_by_institution: dict[int, list] = {}
    inst_ids = [inst.id for inst in institutions]
    if inst_ids:
        admin_role = getattr(RoleEnum, "ADMIN_COLEGIO", None)
        admin_profiles = (
            ProfileModel.query.filter(
                ProfileModel.institution_id.in_(inst_ids),
                ProfileModel.role == admin_role,
            )
            .order_by(ProfileModel.full_name.asc())
            .all()
        )
        for admin in admin_profiles:
            admins_by_institution.setdefault(admin.institution_id, []).append(admin)

    return render_template(
        "owner_institutions.html",
        institutions=institutions,
        admins_by_institution=admins_by_institution,
        platform_theme=PlatformTheme.current(),
        is_admin=True,
    )


@app.get("/uploads/logos/<path:filename>")
def serve_logo(filename: str):
    directory = Path(current_app.instance_path) / "uploads" / "logos"
    return send_from_directory(directory, filename)


@app.route("/plan", methods=["GET", "POST"])
@login_required
def plan_view():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import (
        StudyPlan,
        Objective,
        Lesson,
        Grade,
        Section,
        RoleEnum,
        CurriculumDocument,
    )

    editable_roles = (
        RoleEnum.PROFESOR,
        getattr(RoleEnum, "ADMIN_COLEGIO", RoleEnum.PROFESOR),
        getattr(RoleEnum, "RECTOR", RoleEnum.PROFESOR),
    )
    can_edit = profile.role in editable_roles

    grades = (
        Grade.query.filter_by(institution_id=profile.institution_id)
        .order_by(Grade.name.asc())
        .all()
    )
    sections = (
        Section.query.join(Grade)
        .filter(Grade.institution_id == profile.institution_id)
        .order_by(Section.name.asc())
        .all()
    )

    curriculum_documents = (
        CurriculumService.documents_for_institution(profile.institution_id)
        if can_edit
        else []
    )

    if request.method == "POST" and can_edit:
        action = request.form.get("action")
        if action == "upload_curriculum":
            file = request.files.get("curriculum_file")
            title = (request.form.get("curriculum_title") or (file.filename if file else "")).strip()
            jurisdiction = (request.form.get("curriculum_jurisdiction") or "").strip()
            year_raw = request.form.get("curriculum_year")
            grade_min = CurriculumService.normalize_grade_label(request.form.get("curriculum_grade_min"))
            grade_max = CurriculumService.normalize_grade_label(request.form.get("curriculum_grade_max"))
            if not file or not file.filename:
                flash("Selecciona un archivo PDF o TXT.", "error")
                return redirect(url_for("plan_view"))
            try:
                year_val = int(year_raw) if year_raw else None
            except ValueError:
                year_val = None
            try:
                CurriculumService.ingest_from_file(
                    profile=profile,
                    file_storage=file,
                    title=title or "Currículum",
                    jurisdiction=jurisdiction,
                    year=year_val,
                    grade_min=grade_min,
                    grade_max=grade_max,
                )
                flash("Currículum cargado. Estamos procesando el archivo.", "success")
            except Exception as exc:
                flash(f"No pudimos cargar el archivo: {exc}", "error")
            return redirect(url_for("plan_view"))

        if action == "paste_curriculum":
            raw_text = (request.form.get("curriculum_text") or "").strip()
            title = (request.form.get("curriculum_title") or "Currículum pegado").strip()
            jurisdiction = (request.form.get("curriculum_jurisdiction") or "").strip()
            year_raw = request.form.get("curriculum_year")
            grade_min = CurriculumService.normalize_grade_label(request.form.get("curriculum_grade_min"))
            grade_max = CurriculumService.normalize_grade_label(request.form.get("curriculum_grade_max"))
            if not raw_text:
                flash("Pegá al menos un capítulo del plan oficial.", "error")
                return redirect(url_for("plan_view"))
            try:
                year_val = int(year_raw) if year_raw else None
            except ValueError:
                year_val = None
            CurriculumService.ingest_from_text(
                profile=profile,
                title=title,
                raw_text=raw_text,
                jurisdiction=jurisdiction,
                year=year_val,
                grade_min=grade_min,
                grade_max=grade_max,
            )
            flash("Texto curricular guardado y procesado.", "success")
            return redirect(url_for("plan_view"))

        if action == "create_plan":
            grade_id = request.form.get("grade_id")
            name = (request.form.get("plan_name") or "").strip()
            description = (request.form.get("plan_description") or "").strip()
            year_raw = request.form.get("plan_year")
            curriculum_doc_id = request.form.get("curriculum_document_id")
            use_curriculum_ai = request.form.get("curriculum_use_ai") == "on"
            auto_objectives = request.form.get("curriculum_create_objectives") == "on"

            try:
                grade_id_int = int(grade_id)
            except (TypeError, ValueError):
                grade_id_int = None

            grade = (
                Grade.query.filter_by(id=grade_id_int, institution_id=profile.institution_id).first()
                if grade_id_int
                else None
            )
            if not grade or not name:
                flash("Selecciona un grado y completa el nombre del plan.", "error")
                return redirect(url_for("plan_view"))

            try:
                year_val = int(year_raw) if year_raw else None
            except ValueError:
                year_val = None

            plan = StudyPlan(
                institution_id=profile.institution_id,
                grade_id=grade.id,
                name=name,
                year=year_val,
                description=description,
                is_active=True,
            )
            db.session.add(plan)
            db.session.flush()

            if curriculum_doc_id and (use_curriculum_ai or auto_objectives):
                document = CurriculumDocument.query.get(curriculum_doc_id)
                if document and (
                    document.institution_id is None or document.institution_id == profile.institution_id
                ):
                    grade_label = CurriculumService.normalize_grade_label(grade.name)
                    segments = CurriculumService.segments_for_grade(
                        documents=[document],
                        grade_label=grade_label,
                        limit_per_doc=6,
                    ) if grade_label else []
                    if segments:
                        enrichment = CurriculumService.build_plan_enrichment(
                            plan=plan,
                            grade=grade,
                            segments=segments,
                            include_objectives=auto_objectives,
                        )
                        if use_curriculum_ai and enrichment.get("description"):
                            if plan.description:
                                plan.description = f"{plan.description}\n\n{enrichment['description']}"
                            else:
                                plan.description = enrichment["description"]
                        if auto_objectives and enrichment.get("objectives"):
                            for obj_data in enrichment["objectives"]:
                                obj = Objective(
                                    study_plan_id=plan.id,
                                    title=obj_data.get("title")[:255],
                                    description=obj_data.get("description"),
                                )
                                db.session.add(obj)

            db.session.commit()
            flash("Plan creado correctamente.", "success")
            return redirect(url_for("plan_view"))

        if action == "create_objective":
            plan_id = request.form.get("plan_id")
            title = (request.form.get("objective_title") or "").strip()
            description = (request.form.get("objective_description") or "").strip()
            period_label = (request.form.get("period_label") or "").strip()
            start_date = _safe_parse_date(request.form.get("objective_start"))
            end_date = _safe_parse_date(request.form.get("objective_end"))
            order_raw = request.form.get("objective_order")

            plan = StudyPlan.query.get(plan_id)
            if not plan or plan.institution_id != profile.institution_id or not title:
                flash("Selecciona un plan válido y completa el título del objetivo.", "error")
                return redirect(url_for("plan_view"))

            try:
                order_index = int(order_raw) if order_raw else None
            except ValueError:
                order_index = None

            objective = Objective(
                study_plan_id=plan.id,
                title=title,
                description=description,
                period_label=period_label or None,
                start_date=start_date,
                end_date=end_date,
                order_index=order_index,
            )
            db.session.add(objective)
            db.session.commit()
            flash("Objetivo agregado correctamente.", "success")
            return redirect(url_for("plan_view"))

        if action == "create_lesson":
            objective_id = request.form.get("objective_id")
            lesson_title = (request.form.get("lesson_title") or "").strip()
            lesson_description = (request.form.get("lesson_description") or "").strip()
            class_date = _safe_parse_date(request.form.get("lesson_date"))
            start_time = _safe_parse_time(request.form.get("lesson_start_time"))
            end_time = _safe_parse_time(request.form.get("lesson_end_time"))
            section_id = request.form.get("section_id")

            objective = Objective.query.get(objective_id)
            if (
                not objective
                or not objective.study_plan
                or objective.study_plan.institution_id != profile.institution_id
                or not lesson_title
                or not class_date
            ):
                flash("Completa los datos obligatorios de la clase.", "error")
                return redirect(url_for("plan_view"))

            try:
                section_id_int = int(section_id) if section_id else None
            except ValueError:
                section_id_int = None

            lesson = Lesson(
                institution_id=objective.study_plan.institution_id,
                section_id=section_id_int,
                teacher_profile_id=profile.id,
                objective_id=objective.id,
                title=lesson_title,
                description=lesson_description,
                class_date=class_date,
                start_time=start_time,
                end_time=end_time,
            )
            db.session.add(lesson)
            db.session.commit()
            flash("Clase programada correctamente.", "success")
            return redirect(url_for("plan_view"))

        flash("Acción no permitida.", "error")
        return redirect(url_for("plan_view"))

    plans = (
        StudyPlan.query.filter_by(institution_id=profile.institution_id)
        .order_by(StudyPlan.year.desc().nullslast())
        .all()
    )

    plan_cards = []
    for plan in plans:
        periods = {}
        for obj in plan.objectives:
            label = obj.period_label or "Objetivos generales"
            periods.setdefault(label, []).append(obj)

        period_list = []
        for label, objectives in periods.items():
            objectives_sorted = sorted(
                objectives,
                key=lambda o: (
                    o.start_date or date.max,
                    o.order_index or 0,
                    o.title.lower(),
                ),
            )
            period_list.append({"label": label, "objectives": objectives_sorted})
        period_list.sort(key=lambda p: p["label"])

        timeline = _build_plan_timeline(plan)

        plan_cards.append({"plan": plan, "periods": period_list, "timeline": timeline})

    objective_choices = (
        Objective.query.join(StudyPlan)
        .filter(StudyPlan.institution_id == profile.institution_id)
        .order_by(Objective.title.asc())
        .all()
    )

    return render_template(
        "plan.html",
        plans=plan_cards,
        plan_options=plans,
        objective_choices=objective_choices,
        grades=grades,
        sections=sections,
        can_edit=can_edit,
        is_admin=_has_admin_role(profile),
        curriculum_documents=curriculum_documents,
    )


def _default_insights_metrics():
    return {
        "tasks_total": 0,
        "submissions_total": 0,
        "average_points": None,
        "help_usage": {"BAJA": 0, "MEDIA": 0, "ALTA": 0},
        "students_flagged": [],
        "bitacora_summary": [],
        "lessons_upcoming": [],
        "ai_payload": {},
    }


def _build_plan_timeline(plan):
    """
    Prepara datos para una vista tipo calendario (grid) basada en los objetivos del plan.
    """
    spans = []
    for obj in plan.objectives:
        start = obj.start_date or obj.end_date
        end = obj.end_date or obj.start_date
        if not start and not end:
            continue
        if not start:
            start = end
        if not end:
            end = start
        spans.append({"objective": obj, "start": start, "end": end})

    if not spans:
        return None

    timeline_start = min(item["start"] for item in spans)
    timeline_end = max(item["end"] for item in spans)
    total_days = max((timeline_end - timeline_start).days + 1, 1)

    entries = []
    for item in spans:
        left = ((item["start"] - timeline_start).days / total_days) * 100
        width = ((item["end"] - item["start"]).days + 1) / total_days * 100
        entries.append(
            {
                "title": item["objective"].title,
                "start": item["start"],
                "end": item["end"],
                "left": round(left, 2),
                "width": round(max(width, 1), 2),
                "period": item["objective"].period_label or "",
            }
        )

    return {
        "start": timeline_start,
        "end": timeline_end,
        "total_days": total_days,
        "entries": entries,
    }


@app.get("/psico")
@login_required
def psico_panel():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import RoleEnum, Lesson

    if profile.role not in (
        RoleEnum.PSICOPEDAGOGIA,
        getattr(RoleEnum, "ADMIN_COLEGIO", None),
    ):
        abort(403)

    data = ViewDataService.psico_dashboard(profile)
    lessons = (
        Lesson.query.filter_by(institution_id=profile.institution_id)
        .order_by(Lesson.class_date.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "psico_dashboard.html",
        students=data["students"],
        student_choices=data["student_choices"],
        lessons=lessons,
        is_admin=_has_admin_role(profile),
    )


# 🔹 PERFIL DEL USUARIO LOGUEADO (datos + cambio de contraseña)
@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    from models import Profile

    profile = Profile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        abort(404)

    profile_error = None
    password_error = None
    success = None

    if request.method == "POST":
        action = request.form.get("action")

        # Actualizar datos básicos del perfil
        if action == "update_profile":
            full_name = request.form.get("full_name", "").strip()

            if not full_name:
                profile_error = "El nombre no puede estar vacío."
            else:
                profile.full_name = full_name
                db.session.commit()
                success = "Perfil actualizado correctamente."

        # Cambiar contraseña del usuario actual
        elif action == "change_password":
            current_password = request.form.get("current_password", "") or ""
            new_password = request.form.get("new_password", "") or ""
            confirm_password = request.form.get("confirm_password", "") or ""

            if not new_password or len(new_password) < 8:
                password_error = "La nueva contraseña debe tener al menos 8 caracteres."
            elif new_password != confirm_password:
                password_error = "La confirmación no coincide."
            else:
                # Verificar contraseña actual
                if not current_user.check_password(current_password):
                    password_error = "La contraseña actual no es correcta."
                else:
                    current_user.set_password(new_password)
                    db.session.commit()
                    success = "Contraseña actualizada correctamente."

    return render_template(
        "profile.html",
        user=current_user,
        profile=profile,
        success=success,
        profile_error=profile_error,
        password_error=password_error,
        is_admin=_has_admin_role(profile),
    )


@app.post("/profe/bitacora")
@login_required
def crear_bitacora():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    return _handle_bitacora_submission(profile, "profe")


@app.post("/psico/bitacora")
@login_required
def crear_bitacora_psico():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import RoleEnum

    if profile.role not in (
        getattr(RoleEnum, "PSICOPEDAGOGIA", None),
        getattr(RoleEnum, "ADMIN_COLEGIO", None),
    ):
        abort(403)

    return _handle_bitacora_submission(profile, "psico_panel")


@app.post("/profe/mensaje")
@login_required
def enviar_mensaje_manual():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import Lesson
    from api.services.messages_service import MessageService
    from api.services.profile_service import ProfileService
    from api.services.attachment_service import AttachmentService

    lesson_id = request.form.get("lesson_id")
    text = (request.form.get("mensaje_texto") or "").strip()
    subject = (request.form.get("mensaje_asunto") or "").strip()
    recipient_ids = request.form.getlist("recipient_profile_ids")
    legacy_recipient = request.form.get("recipient_profile_id")
    if legacy_recipient and not recipient_ids:
        recipient_ids = [legacy_recipient]

    if not text:
        flash("Escribe un mensaje antes de enviarlo.", "error")
        return redirect(url_for("profe"))

    lesson = Lesson.query.get(int(lesson_id)) if lesson_id else None
    if lesson_id and (
        not lesson or lesson.institution_id != profile.institution_id
    ):
        flash("Clase inválida.", "error")
        return redirect(url_for("profe"))

    if lesson and not subject:
        subject = f"Clase · {lesson.title}"

    if not lesson and not subject:
        flash("Agrega un asunto para el mensaje.", "error")
        return redirect(url_for("profe"))

    filtered_recipient_ids = _filter_recipient_ids(profile, recipient_ids)
    if lesson and lesson.teacher_profile_id:
        filtered_recipient_ids.append(lesson.teacher_profile_id)

    participant_ids = ProfileService.normalize_participant_ids(filtered_recipient_ids)
    if not participant_ids and lesson and lesson.section_id:
        from models import Profile as ProfileModel, RoleEnum

        section_students = (
            ProfileModel.query.filter_by(
                institution_id=profile.institution_id,
                section_id=lesson.section_id,
                role=RoleEnum.ALUMNO,
            ).all()
        )
        participant_ids = [stu.id for stu in section_students]

    if not participant_ids:
        flash("Selecciona al menos un destinatario válido.", "error")
        return redirect(url_for("profe"))

    visibility = {
        "student": _get_form_bool("visible_student", True),
        "parent": _get_form_bool("visible_parent", True),
        "teacher": _get_form_bool("visible_teacher", True),
    }

    msg = MessageService.send_message_to_context(
        context_type="lesson" if lesson else "manual",
        context_id=lesson.id if lesson else None,
        sender_profile_id=profile.id,
        text=text,
        participant_ids=participant_ids,
        visibility=visibility,
        thread_options={
            "subject": subject,
            "force_new": not lesson,
        },
    )

    upload = _save_uploaded_file("mensaje_attachment")
    if upload:
        AttachmentService.create_attachment(
            context_type="message",
            context_id=msg.id,
            filename=upload["filename"],
            storage_path=upload["storage_path"],
            mime_type=upload["mime_type"],
            file_size=upload["file_size"],
            kind="lesson_message",
            uploaded_by_profile_id=profile.id,
            commit=True,
        )

    flash("Mensaje enviado.", "success")
    return redirect(url_for("profe"))


@app.post("/alumno/entregar")
@login_required
def alumno_entregar():
    profile = _get_current_profile()
    if not profile:
        abort(403)

    from models import Task
    from api.services.submission_service import SubmissionService

    task_id = request.form.get("task_id")
    task = Task.query.get(int(task_id)) if task_id else None
    if not task or task.institution_id != profile.institution_id:
        flash("Selecciona una tarea válida.", "error")
        return redirect(url_for("alumno_portal"))

    help_usage = HelpUsageService.get_summary(task=task, student_profile=profile)

    payload = {
        "comment": request.form.get("comment"),
        "help_level": help_usage.get("dominant_level"),
        "help_count": help_usage.get("total_count", 0),
        "help_breakdown": help_usage.get("breakdown"),
        "evidences": [],
    }

    upload = _save_uploaded_file("evidence_file")
    evidence_type = (request.form.get("evidence_type") or "").strip().upper()
    if upload and evidence_type:
        payload["evidences"].append(
            {
                "evidence_type": evidence_type,
                "attachment": {
                    "filename": upload["filename"],
                    "storage_path": upload["storage_path"],
                    "mime_type": upload["mime_type"],
                    "file_size": upload["file_size"],
                },
            }
        )

    try:
        SubmissionService.create_submission(task=task, student_profile=profile, payload=payload)
        HelpUsageService.clear_usage(task=task, student_profile=profile)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("alumno_portal"))

    flash("Entrega enviada correctamente.", "success")
    return redirect(url_for("alumno_portal"))


if __name__ == "__main__":
    app.run(debug=True)


def _handle_bitacora_submission(author_profile, redirect_endpoint):
    from models import BitacoraEntrada, Profile, Lesson
    from api.services.attachment_service import AttachmentService

    student_id = request.form.get("student_profile_id")
    note = (request.form.get("nota") or "").strip()
    categoria = (request.form.get("categoria") or "APRENDIZAJE").upper()
    lesson_id = request.form.get("lesson_id") or None

    student = Profile.query.get(int(student_id)) if student_id else None
    if not student or student.institution_id != author_profile.institution_id:
        flash("Selecciona un alumno válido.", "error")
        return redirect(url_for(redirect_endpoint))

    lesson = Lesson.query.get(int(lesson_id)) if lesson_id else None
    entry = BitacoraEntrada(
        institution_id=author_profile.institution_id,
        student_profile_id=student.id,
        author_profile_id=author_profile.id,
        lesson_id=lesson.id if lesson else None,
        categoria=categoria,
        nota=note,
        visible_para_padres=bool(request.form.get("visible_para_padres")),
        visible_para_alumno=bool(request.form.get("visible_para_alumno")),
    )
    db.session.add(entry)
    db.session.flush()

    upload = _save_uploaded_file("bitacora_attachment")
    if upload:
        AttachmentService.create_attachment(
            context_type="bitacora",
            context_id=entry.id,
            filename=upload["filename"],
            storage_path=upload["storage_path"],
            mime_type=upload["mime_type"],
            file_size=upload["file_size"],
            kind="bitacora_evidence",
            uploaded_by_profile_id=author_profile.id,
            commit=False,
        )

    db.session.commit()
    flash("Entrada de bitácora guardada.", "success")
    return redirect(url_for(redirect_endpoint))


def _build_display_name(user, profile):
    if profile and profile.full_name:
        return profile.full_name
    if user and getattr(user, "email", None):
        local = user.email.split("@")[0]
        friendly = local.replace(".", " ").replace("_", " ").strip()
        return friendly.title() or user.email
    return "Usuario"


def _get_current_profile():
    from models import Profile

    if not current_user.is_authenticated:
        return None
    return Profile.query.filter_by(user_id=current_user.id).first()


def _safe_parse_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_parse_time(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        return None


def _has_admin_role(profile) -> bool:
    from models import RoleEnum

    return bool(
        profile
        and profile.role
        and profile.role
        in (
            getattr(RoleEnum, "ADMIN_COLEGIO", None),
            getattr(RoleEnum, "RECTOR", None),
        )
    )


def _filter_recipient_ids(author_profile, raw_ids):
    from models import Profile, RoleEnum

    if not raw_ids:
        return []
    if not getattr(author_profile, "institution_id", None):
        return []

    explicit_ids: list[int] = []
    group_tokens: set[str] = set()
    for raw in raw_ids:
        if not raw:
            continue
        if isinstance(raw, str) and raw.startswith("group:"):
            token = raw.split(":", 1)[1]
            if token:
                group_tokens.add(token)
            continue
        try:
            explicit_ids.append(int(raw))
        except (TypeError, ValueError):
            continue

    resolved_ids: set[int] = set()
    if explicit_ids:
        profiles = (
            Profile.query.filter(Profile.id.in_(explicit_ids))
            .filter_by(institution_id=author_profile.institution_id)
            .all()
        )
        resolved_ids.update(p.id for p in profiles)

    if group_tokens:
        base_query = Profile.query.filter_by(institution_id=author_profile.institution_id)
        if "students" in group_tokens:
            resolved_ids.update(
                p.id
                for p in base_query.filter(Profile.role == RoleEnum.ALUMNO).all()
            )
        if "parents" in group_tokens or "families" in group_tokens:
            resolved_ids.update(
                p.id
                for p in base_query.filter(Profile.role == RoleEnum.PADRE).all()
            )
        if "staff" in group_tokens:
            staff_roles = [
                RoleEnum.PROFESOR,
                RoleEnum.PSICOPEDAGOGIA,
                getattr(RoleEnum, "ADMIN_COLEGIO", None),
                getattr(RoleEnum, "RECTOR", None),
            ]
            staff_roles = [role for role in staff_roles if role is not None]
            resolved_ids.update(
                p.id
                for p in base_query.filter(Profile.role.in_(staff_roles)).all()
            )

    return list(resolved_ids)


def _build_recipient_groups(profile):
    from models import Profile as ProfileModel, RoleEnum

    if not getattr(profile, "institution_id", None):
        return []

    base_query = ProfileModel.query.filter_by(
        institution_id=profile.institution_id
    ).filter(ProfileModel.id != profile.id)

    students = (
        base_query.filter(ProfileModel.role == RoleEnum.ALUMNO)
        .order_by(ProfileModel.full_name.asc())
        .all()
    )
    parents = (
        base_query.filter(ProfileModel.role == RoleEnum.PADRE)
        .order_by(ProfileModel.full_name.asc())
        .all()
    )
    staff_roles = [
        RoleEnum.PROFESOR,
        RoleEnum.PSICOPEDAGOGIA,
        getattr(RoleEnum, "ADMIN_COLEGIO", None),
        getattr(RoleEnum, "RECTOR", None),
    ]
    staff_roles = [r for r in staff_roles if r is not None]
    staff = (
        base_query.filter(ProfileModel.role.in_(staff_roles))
        .order_by(ProfileModel.full_name.asc())
        .all()
    )

    groups = []
    if students:
        groups.append({"label": "Alumnos", "profiles": students})
    if parents:
        groups.append({"label": "Familias", "profiles": parents})
    if staff:
        groups.append({"label": "Equipo", "profiles": staff})
    return groups


def _get_form_bool(field_name: str, default: bool = True) -> bool:
    """
    Lee un boolean desde el form.
    Si existe un campo auxiliar <name>_present entendemos que el usuario pudo editarlo.
    """
    present_flag = request.form.get(f"{field_name}_present")
    raw = request.form.get(field_name)

    if present_flag is None and raw is None:
        return default
    if raw is None:
        return False
    return str(raw).lower() in ("1", "true", "on", "sí", "si", "yes")


def _save_uploaded_file(field_name: str):
    """
    Guarda un archivo del form y devuelve metadata para AttachmentService.
    """
    file = request.files.get(field_name)
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        upload_folder = os.path.join(current_app.root_path, "static", "uploads")
        current_app.config["UPLOAD_FOLDER"] = upload_folder

    os.makedirs(upload_folder, exist_ok=True)

    basename, ext = os.path.splitext(filename)
    final_name = f"{basename}_{int(datetime.utcnow().timestamp())}{ext}"
    file_path = os.path.join(upload_folder, final_name)
    file.save(file_path)

    rel_path = os.path.relpath(file_path, current_app.root_path)
    storage_path = f"/{rel_path}".replace("\\", "/")

    return {
        "filename": final_name,
        "storage_path": storage_path,
        "mime_type": file.mimetype,
        "file_size": os.path.getsize(file_path),
    }
