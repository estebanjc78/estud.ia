# api/tasks.py

from flask import request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Task
from . import api_bp

from api.services.messages_service import MessageService
from api.utils.messages_helper import serialize_message


@api_bp.post("/lessons/<int:lesson_id>/tasks")
@login_required
def create_task(lesson_id):
    """
    Crea una tarea para una lección.
    Body JSON:
    {
        "title": "Resolver ejercicios",
        "description": "Página 15 del cuaderno",
        "due_date": "2025-03-15"
    }
    """
    data = request.json or {}
    title = data.get("title")

    if not title:
        return jsonify({"error": "title es obligatorio"}), 400

    task = Task(
        lesson_id=lesson_id,
        title=title,
        description=data.get("description"),
        due_date=data.get("due_date"),
    )

    db.session.add(task)
    db.session.commit()

    return jsonify({"id": task.id, "status": "created"}), 201


@api_bp.get("/lessons/<int:lesson_id>/tasks")
@login_required
def list_tasks(lesson_id):
    """Lista todas las tareas de una lección."""
    tasks = Task.query.filter_by(lesson_id=lesson_id).all()

    return jsonify(
        [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "due_date": str(t.due_date) if t.due_date else None,
                "completed": t.completed,
                "created_at": str(t.created_at),
            }
            for t in tasks
        ]
    )


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
    from models import Lesson  # por si hace falta la relación

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "la tarea no existe"}), 404

    lesson = task.lesson  # relación definida en el modelo Task -> Lesson

    participants = {current_user.id}

    if lesson and getattr(lesson, "created_by", None):
        participants.add(lesson.created_by)

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
    data = request.json or {}
    text = data.get("text")

    if not text:
        return jsonify({"error": "mensaje vacío"}), 400

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "la tarea no existe"}), 404

    lesson = task.lesson
    participants = {current_user.id}

    if lesson and getattr(lesson, "created_by", None):
        participants.add(lesson.created_by)

    msg = MessageService.send_message_to_context(
        context_type="task",
        context_id=task_id,
        sender_profile_id=current_user.id,
        text=text,
        participant_ids=list(participants),
    )

    return jsonify({"message_id": msg.id, "status": "sent", "message": serialize_message(msg)})


@api_bp.get("/tasks/<int:task_id>/messages")
@login_required
def list_task_messages(task_id):
    """
    Lista los mensajes del thread asociado a una tarea.
    Si el thread no existe aún, lo crea vacío.
    """
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "la tarea no existe"}), 404

    thread = MessageService.get_or_create_thread(
        context_type="task",
        context_id=task_id,
        participant_ids=[current_user.id],
    )

    msgs = MessageService.list_thread_messages(thread.id)

    return jsonify([serialize_message(m) for m in msgs])