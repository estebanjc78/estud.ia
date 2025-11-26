from flask import request, jsonify
from flask_login import login_required
from extensions import db
from models import Lesson, Objective
from . import api_bp


@api_bp.post("/institutions/<int:inst_id>/lessons")
@login_required
def create_lesson(inst_id):
    """
    Crea una clase (lesson) dentro de una institución.

    JSON esperado:
    {
      "objective_id": 1,          # opcional pero recomendado
      "section_id": 2,            # sección / grupo
      "teacher_profile_id": 3,    # perfil PROFESOR
      "title": "Suma sin llevar",
      "description": "Repaso de sumas de 2 cifras",
      "class_date": "2025-03-10",
      "start_time": "08:00",
      "end_time": "09:00"
    }
    """
    data = request.json or {}

    title = data.get("title")
    class_date = data.get("class_date")

    if not title or not class_date:
        return jsonify({"error": "title y class_date son obligatorios"}), 400

    lesson = Lesson(
        institution_id=inst_id,
        section_id=data.get("section_id"),
        teacher_profile_id=data.get("teacher_profile_id"),
        objective_id=data.get("objective_id"),
        title=title,
        description=data.get("description"),
        class_date=data.get("class_date"),
        start_time=data.get("start_time"),
        end_time=data.get("end_time"),
    )

    db.session.add(lesson)
    db.session.commit()

    return jsonify({"id": lesson.id, "status": "created"}), 201


@api_bp.get("/institutions/<int:inst_id>/lessons")
@login_required
def list_lessons(inst_id):
    """
    Lista todas las clases de una institución.
    (Más adelante se puede filtrar por sección, profesor, fecha, etc.)
    """
    lessons = Lesson.query.filter_by(institution_id=inst_id).all()

    return jsonify([
        {
            "id": l.id,
            "title": l.title,
            "description": l.description,
            "class_date": str(l.class_date),
            "start_time": str(l.start_time) if l.start_time else None,
            "end_time": str(l.end_time) if l.end_time else None,
            "section_id": l.section_id,
            "teacher_profile_id": l.teacher_profile_id,
            "objective_id": l.objective_id,
        }
        for l in lessons
    ])


@api_bp.get("/objectives/<int:objective_id>/lessons")
@login_required
def list_lessons_by_objective(objective_id):
    """
    Lista todas las clases asociadas a un objetivo.
    Esto es útil para que el profe vea qué clases ya programó
    para un objetivo concreto.
    """
    lessons = Lesson.query.filter_by(objective_id=objective_id).all()

    return jsonify([
        {
            "id": l.id,
            "title": l.title,
            "description": l.description,
            "class_date": str(l.class_date),
            "start_time": str(l.start_time) if l.start_time else None,
            "end_time": str(l.end_time) if l.end_time else None,
            "section_id": l.section_id,
            "teacher_profile_id": l.teacher_profile_id,
        }
        for l in lessons
    ])

from . import api_bp

@api_bp.get("/debug/lessons")
def debug_lessons():
    return {"lessons": "ok"}