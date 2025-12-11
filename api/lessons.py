from flask import request, jsonify, abort
from flask_login import login_required, current_user
from extensions import db
from models import Lesson, Objective, Section
from services.authoring_service import AuthoringService
from api.services.profile_service import ProfileService
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


@api_bp.post("/lessons/ai/brief")
@login_required
def lesson_ai_brief():
    profile = _require_profile()
    data = request.json or {}
    lesson_id = data.get("lesson_id")
    objective_id = data.get("objective_id")
    section_id = data.get("section_id")
    title = (data.get("title") or "").strip() or None

    lesson = Lesson.query.get(lesson_id) if lesson_id else None
    if lesson and lesson.institution_id != profile.institution_id:
        return jsonify({"error": "Clase inválida para este perfil."}), 403

    objective = Objective.query.get(objective_id) if objective_id else None
    if objective and objective.study_plan.institution_id != profile.institution_id:
        return jsonify({"error": "Objetivo inválido."}), 403

    section_label = None
    if section_id:
        section = Section.query.get(section_id)
        if not section or section.grade.institution_id != profile.institution_id:
            return jsonify({"error": "Sección inválida."}), 403
        grade_name = section.grade.name if section.grade else None
        section_label = f"{grade_name or 'Grupo'} · {section.name}"

    brief = AuthoringService.generate_lesson_brief(
        lesson=lesson,
        objective=objective,
        section_label=section_label,
        title=title,
    )
    return jsonify(brief)

from . import api_bp

@api_bp.get("/debug/lessons")
def debug_lessons():
    return {"lessons": "ok"}


def _require_profile():
    try:
        return ProfileService.require_profile(current_user.id)
    except ValueError as exc:
        abort(403, description=str(exc))
