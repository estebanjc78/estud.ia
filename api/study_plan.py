from flask import request, jsonify
from flask_login import login_required
from extensions import db
from models import StudyPlan, Objective
from . import api_bp


@api_bp.post("/institutions/<int:inst_id>/study_plans")
@login_required
def create_study_plan(inst_id):
    """
    Crea un plan de estudio para un grado dentro de una institución.
    body JSON esperado:
    {
      "grade_id": 1,
      "name": "Matemática 3° primaria 2025",
      "year": 2025,
      "description": "Programa anual de matemática"
    }
    """
    data = request.json or {}

    grade_id = data.get("grade_id")
    name = data.get("name")

    if not grade_id or not name:
        return jsonify({"error": "grade_id y name son obligatorios"}), 400

    plan = StudyPlan(
        institution_id=inst_id,
        grade_id=grade_id,
        name=name,
        year=data.get("year"),
        description=data.get("description"),
    )

    db.session.add(plan)
    db.session.commit()

    return jsonify({"id": plan.id, "status": "created"}), 201


@api_bp.post("/study_plans/<int:plan_id>/objectives")
@login_required
def create_objective(plan_id):
    """
    Crea un objetivo dentro de un plan de estudio.
    body JSON esperado:
    {
      "title": "Sumar y restar hasta 1000",
      "description": "Que el alumno pueda...",
      "order_index": 1,
      "start_date": "2025-03-01",
      "end_date": "2025-03-31"
    }
    """
    data = request.json or {}

    title = data.get("title")
    if not title:
        return jsonify({"error": "title es obligatorio"}), 400

    obj = Objective(
        study_plan_id=plan_id,
        title=title,
        description=data.get("description"),
        order_index=data.get("order_index"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
    )

    db.session.add(obj)
    db.session.commit()

    return jsonify({"id": obj.id, "status": "created"}), 201

@api_bp.get("/institutions/<int:inst_id>/study_plans")
@login_required
def list_study_plans(inst_id):
    """Retorna todos los planes de estudio de una institución."""
    plans = StudyPlan.query.filter_by(institution_id=inst_id).all()

    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "year": p.year,
            "grade_id": p.grade_id,
            "description": p.description
        }
        for p in plans
    ])


@api_bp.get("/study_plans/<int:plan_id>/objectives")
@login_required
def list_objectives(plan_id):
    """Retorna los objetivos de un plan de estudio."""
    objs = Objective.query.filter_by(study_plan_id=plan_id).order_by(Objective.order_index).all()

    return jsonify([
        {
            "id": o.id,
            "title": o.title,
            "description": o.description,
            "order_index": o.order_index,
            "start_date": str(o.start_date) if o.start_date else None,
            "end_date": str(o.end_date) if o.end_date else None,
        }
        for o in objs
    ])