# api/messages.py

from flask import request, jsonify, abort
from flask_login import login_required, current_user

from . import api_bp

from models import Lesson, Profile
from api.services.messages_service import MessageService
from api.services.profile_service import ProfileService
from api.services.attachment_service import AttachmentService
from api.utils.messages_helper import serialize_message


# 🔹 CREAR / OBTENER THREAD PARA LECCIÓN
@api_bp.get("/lessons/<int:lesson_id>/messages/thread")
@login_required
def get_lesson_thread(lesson_id):
    """
    Obtiene o crea el thread de mensajes asociado a una lección.
    Participantes:
      - profesor creador
      - usuario actual
      - (futuro) alumnos
    """
    profile = _require_current_profile()
    lesson = Lesson.query.get(lesson_id)

    if not lesson:
        return jsonify({"error": "la lección no existe"}), 404

    try:
        ProfileService.ensure_institution_membership(profile, lesson.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    participant_ids = ProfileService.normalize_participant_ids(
        [profile.id, lesson.teacher_profile_id]
    )

    thread = MessageService.get_or_create_thread(
        context_type="lesson",
        context_id=lesson_id,
        participant_ids=participant_ids,
        subject=f"Clase · {lesson.title}",
    )

    return jsonify({"thread_id": thread.id})


# 🔹 ENVIAR MENSAJE EN LECCIÓN
@api_bp.post("/lessons/<int:lesson_id>/messages")
@login_required
def send_message_in_lesson(lesson_id):
    data = request.json or {}
    text = data.get("text")

    if not text:
        return jsonify({"error": "mensaje vacío"}), 400

    profile = _require_current_profile()
    lesson = Lesson.query.get(lesson_id)

    if not lesson:
        return jsonify({"error": "la lección no existe"}), 404

    try:
        ProfileService.ensure_institution_membership(profile, lesson.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    extra_participants = _sanitize_participants_ids(
        profile, data.get("participant_profile_ids")
    )
    participant_ids = ProfileService.normalize_participant_ids(
        [profile.id, lesson.teacher_profile_id, *extra_participants]
    )

    visibility = _normalize_visibility_flags(data.get("visibility"))
    subject = data.get("subject") or f"Clase · {lesson.title}"

    msg = MessageService.send_message_to_context(
        context_type="lesson",
        context_id=lesson_id,
        sender_profile_id=profile.id,
        text=text,
        participant_ids=participant_ids,
        visibility=visibility,
        thread_options={"subject": subject},
    )

    AttachmentService.bulk_create_from_payloads(
        context_type="message",
        context_id=msg.id,
        payloads=data.get("attachments"),
        uploaded_by_profile_id=profile.id,
        default_kind="lesson_message",
        commit=True,
    )

    return jsonify({
        "message_id": msg.id,
        "message": serialize_message(msg),
        "status": "sent"
    })


# 🔹 LISTAR MENSAJES DE UNA LECCIÓN
@api_bp.get("/lessons/<int:lesson_id>/messages")
@login_required
def list_lesson_messages(lesson_id):
    profile = _require_current_profile()

    thread = MessageService.get_or_create_thread(
        context_type="lesson",
        context_id=lesson_id,
        participant_ids=[profile.id],
        subject=None,
    )

    msgs = MessageService.list_thread_messages(thread.id, viewer_profile=profile)

    return jsonify([serialize_message(m) for m in msgs])


def _require_current_profile():
    try:
        return ProfileService.require_profile(current_user.id)
    except ValueError as exc:
        abort(403, description=str(exc))


def _sanitize_participants_ids(author_profile: Profile, raw_ids):
    if not raw_ids:
        return []
    clean_ids: list[int] = []
    for raw in raw_ids:
        try:
            clean_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not clean_ids:
        return []

    profiles = (
        Profile.query.filter(Profile.id.in_(clean_ids))
        .filter_by(institution_id=author_profile.institution_id)
        .all()
    )
    return [p.id for p in profiles]


def _normalize_visibility_flags(payload):
    payload = payload or {}
    # Por defecto todo visible salvo que se indique lo contrario
    return {
        "student": bool(payload.get("student", True)),
        "parent": bool(payload.get("parent", True)),
        "teacher": bool(payload.get("teacher", True)),
    }
