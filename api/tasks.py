# api/tasks.py

from datetime import datetime

from flask import request, jsonify, abort
from flask_login import login_required, current_user
from extensions import db
from models import Task, Lesson
from . import api_bp

from api.services.messages_service import MessageService
from api.services.profile_service import ProfileService
from api.services.attachment_service import AttachmentService
from api.utils.messages_helper import serialize_message
from api.utils.attachments_helper import serialize_attachment


@api_bp.post("/lessons/<int:lesson_id>/tasks")
@login_required
def create_task(lesson_id):
    """
    Crea una tarea para una lección.
    Body JSON:
    {
        "title": "Resolver ejercicios",
        "description": "Página 15 del cuaderno",
        "due_date": "2025-03-15",
        "attachments": [
            {
                "filename": "guia.pdf",
                "storage_path": "s3://bucket/guia.pdf",
                "mime_type": "application/pdf",
                "kind": "task_material"
            }
        ]
    }
    """
    profile = _require_current_profile()
    lesson = Lesson.query.get(lesson_id)

    if not lesson:
        return jsonify({"error": "la lección no existe"}), 404

    data = request.json or {}
    title = (data.get("title") or "").strip()

    if not title:
        return jsonify({"error": "title es obligatorio"}), 400

    try:
        due_date = _parse_date(data.get("due_date"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        ProfileService.ensure_institution_membership(profile, lesson.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    max_points = data.get("max_points")
    if max_points is not None:
        try:
            max_points = int(max_points)
        except (TypeError, ValueError):
            return jsonify({"error": "max_points debe ser numérico"}), 400
        if max_points < 0:
            return jsonify({"error": "max_points debe ser >= 0"}), 400

    task = Task(
        institution_id=lesson.institution_id,
        lesson_id=lesson.id,
        section_id=lesson.section_id,
        objective_id=lesson.objective_id,
        title=title,
        description=data.get("description"),
        due_date=due_date,
        max_points=max_points,
    )

    db.session.add(task)
    db.session.flush()  # Necesitamos el ID para adjuntos

    attachments_payload = data.get("attachments")
    created_attachments = AttachmentService.bulk_create_from_payloads(
        context_type="task",
        context_id=task.id,
        payloads=attachments_payload,
        uploaded_by_profile_id=profile.id,
        default_kind="task_material",
    )

    db.session.commit()

    return (
        jsonify(
            {
                "id": task.id,
                "status": "created",
                "attachments": [serialize_attachment(a) for a in created_attachments],
            }
        ),
        201,
    )


@api_bp.get("/lessons/<int:lesson_id>/tasks")
@login_required
def list_tasks(lesson_id):
    """Lista todas las tareas de una lección."""
    profile = _require_current_profile()
    lesson = Lesson.query.get(lesson_id)

    if not lesson:
        return jsonify({"error": "la lección no existe"}), 404

    try:
        ProfileService.ensure_institution_membership(profile, lesson.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    tasks = Task.query.filter_by(lesson_id=lesson_id).all()

    return jsonify([_serialize_task(t) for t in tasks])


# 🔹 THREAD DE MENSAJES ASOCIADO A UNA TAREA


@api_bp.get("/tasks/<int:task_id>/thread")
@login_required
def get_task_thread(task_id):
    """
    Obtiene (o crea si no existe) el thread de mensajes asociado a una tarea.
    Participantes:
      - usuario actual
      - profesor creador de la lección (si existe)
      - (futuro) alumnos de la sección asociada
    """
    current_profile = _require_current_profile()

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "la tarea no existe"}), 404

    try:
        ProfileService.ensure_institution_membership(current_profile, task.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    lesson = task.lesson  # relación definida en el modelo Task -> Lesson

    participants = ProfileService.normalize_participant_ids(
        [
            current_profile.id,
            getattr(lesson, "teacher_profile_id", None) if lesson else None,
        ]
    )

    thread = MessageService.get_or_create_thread(
        context_type="task",
        context_id=task_id,
        participant_ids=list(participants),
    )

    return jsonify({"thread_id": thread.id})


@api_bp.post("/tasks/<int:task_id>/message")
@login_required
def send_message_in_task(task_id):
    """
    Envía un mensaje dentro del contexto de una tarea.
    Body JSON:
    {
        "text": "Tengo una duda en el ejercicio 3"
    }
    """
    current_profile = _require_current_profile()

    data = request.json or {}
    text = data.get("text")

    if not text:
        return jsonify({"error": "mensaje vacío"}), 400

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "la tarea no existe"}), 404

    try:
        ProfileService.ensure_institution_membership(current_profile, task.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    lesson = task.lesson
    participants = ProfileService.normalize_participant_ids(
        [
            current_profile.id,
            getattr(lesson, "teacher_profile_id", None) if lesson else None,
        ]
    )

    msg = MessageService.send_message_to_context(
        context_type="task",
        context_id=task_id,
        sender_profile_id=current_profile.id,
        text=text,
        participant_ids=list(participants),
    )

    AttachmentService.bulk_create_from_payloads(
        context_type="message",
        context_id=msg.id,
        payloads=data.get("attachments"),
        uploaded_by_profile_id=current_profile.id,
        default_kind="task_message",
        commit=True,
    )

    return jsonify(
        {"message_id": msg.id, "status": "sent", "message": serialize_message(msg)}
    )


@api_bp.get("/tasks/<int:task_id>/messages")
@login_required
def list_task_messages(task_id):
    """
    Lista los mensajes del thread asociado a una tarea.
    Si el thread no existe aún, lo crea vacío.
    """
    current_profile = _require_current_profile()

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "la tarea no existe"}), 404

    try:
        ProfileService.ensure_institution_membership(current_profile, task.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    thread = MessageService.get_or_create_thread(
        context_type="task",
        context_id=task_id,
        participant_ids=[current_profile.id],
    )

    msgs = MessageService.list_thread_messages(thread.id, viewer_profile=current_profile)

    return jsonify([serialize_message(m) for m in msgs])


def _parse_date(raw_date: str | None):
    if not raw_date:
        return None
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("due_date debe tener formato YYYY-MM-DD") from exc


def _require_current_profile():
    try:
        return ProfileService.require_profile(current_user.id)
    except ValueError as exc:
        abort(403, description=str(exc))


def _serialize_task(task: Task) -> dict:
    return {
        "id": task.id,
        "lesson_id": task.lesson_id,
        "institution_id": task.institution_id,
        "section_id": task.section_id,
        "objective_id": task.objective_id,
        "title": task.title,
        "description": task.description,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "max_points": task.max_points,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "attachments": [serialize_attachment(att) for att in (task.attachments or [])],
        "submissions": len(task.submissions or []),
    }
