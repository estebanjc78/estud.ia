# api/messages.py

from flask import request, jsonify
from flask_login import login_required, current_user
from . import api_bp

from api.services.messages_service import MessageService
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
    participant_ids = {current_user.id}

    # En el futuro: lesson.created_by, alumnos asignados, etc.
    # Por ahora el usuario actual es suficiente.

    thread = MessageService.get_or_create_thread(
        context_type="lesson",
        context_id=lesson_id,
        participant_ids=list(participant_ids)
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

    participant_ids = {current_user.id}

    msg = MessageService.send_message_to_context(
        context_type="lesson",
        context_id=lesson_id,
        sender_profile_id=current_user.id,
        text=text,
        participant_ids=list(participant_ids)
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
    thread = MessageService.get_or_create_thread(
        context_type="lesson",
        context_id=lesson_id,
        participant_ids=[current_user.id]
    )

    msgs = MessageService.list_thread_messages(thread.id)

    return jsonify([serialize_message(m) for m in msgs])