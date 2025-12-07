from flask import request, jsonify
from flask_login import login_required
from extensions import db
from models import StudyPlan, Objective, Grade, CurriculumDocument
from . import api_bp


@api_bp.post("/institutions/<int:inst_id>/study_plans")
@login_required
def create_study_plan(inst_id):
    """
    Crea un plan de estudio institucional. Si solo aplica a un grado, podés enviar grade_id.
    body JSON esperado:
    {
      "grade_id": 1,
      "name": "Matemática 3° primaria 2025",
      "year": 2025,
      "description": "Programa anual de matemática",
      "jurisdiction": "CABA"
    }
    """
    data = request.json or {}

    grade_id_raw = data.get("grade_id")
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "name es obligatorio"}), 400

    try:
        grade_id = int(grade_id_raw) if grade_id_raw is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "grade_id debe ser numérico"}), 400

    if grade_id:
        grade = Grade.query.filter_by(id=grade_id, institution_id=inst_id).first()
        if not grade:
            return jsonify({"error": "grade_id no pertenece a la institución"}), 400
    else:
        grade = None

    curriculum_document_id = data.get("curriculum_document_id")
    document = None
    if curriculum_document_id:
        document = CurriculumDocument.query.get(curriculum_document_id)
        if not document or (
            document.institution_id not in (None, inst_id)
        ):
            return jsonify({"error": "curriculum_document_id inválido"}), 400

    plan = StudyPlan(
        institution_id=inst_id,
        grade_id=grade.id if grade else None,
        name=name,
        year=data.get("year"),
        description=data.get("description"),
        curriculum_document_id=document.id if document else None,
        jurisdiction=data.get("jurisdiction"),
    )

    db.session.add(plan)
    db.session.commit()

    return jsonify({"id": plan.id, "status": "created"}), 201


@api_bp.post("/study_plans/<int:plan_id>/objectives")
@login_required
def create_objective(plan_id):
    """
    Crea un objetivo dentro de un plan de estudio, ligado a un grado concreto.
    body JSON esperado:
    {
      "title": "Sumar y restar hasta 1000",
      "description": "Que el alumno pueda...",
      "order_index": 1,
      "start_date": "2025-03-01",
      "end_date": "2025-03-31",
      "grade_id": 3,
      "period_label": "Trimestre 1",
      "subject_label": "Matemática",
      "class_ideas": "Clase sumas\nClase restas"
    }
    """
    data = request.json or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title es obligatorio"}), 400

    plan = StudyPlan.query.get(plan_id)
    if not plan:
        return jsonify({"error": "plan inexistente"}), 404

    grade_id_raw = data.get("grade_id")
    try:
        grade_id = int(grade_id_raw) if grade_id_raw is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "grade_id debe ser numérico"}), 400
    if not grade_id:
        return jsonify({"error": "grade_id es obligatorio para el objetivo"}), 400

    grade = Grade.query.filter_by(id=grade_id, institution_id=plan.institution_id).first()
    if not grade:
        return jsonify({"error": "grade_id no pertenece a la institución"}), 400

    obj = Objective(
        study_plan_id=plan_id,
        grade_id=grade.id,
        title=title,
        description=data.get("description"),
        order_index=data.get("order_index"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        period_label=data.get("period_label"),
        subject_label=data.get("subject_label"),
        class_ideas=data.get("class_ideas"),
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
            "description": p.description,
            "curriculum_document_id": p.curriculum_document_id,
            "jurisdiction": p.jurisdiction,
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
            "period_label": o.period_label,
            "grade_id": o.grade_id,
            "subject_label": o.subject_label,
            "class_ideas": o.class_ideas,
        }
        for o in objs
    ])
