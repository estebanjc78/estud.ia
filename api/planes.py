from __future__ import annotations

from flask import jsonify, request, current_app
from flask_login import login_required
from sqlalchemy import func, or_

from extensions import db
from models import Plan, PlanItem, Grade, StudyPlan
from services.plan_parser_service import PlanParserService
from services.curriculum_service import CurriculumService
from api.utils.permissions import get_current_profile

from . import api_bp


@api_bp.post("/planes")
@login_required
def create_plan():
    """
    Crea un plan de estudio a partir de texto plano o un archivo PDF/TXT.
    """
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        data = request.form
    else:
        data = request.get_json(silent=True) or request.form or {}

    profile = get_current_profile()
    if not profile:
        return jsonify({"error": "No autenticado"}), 401
    if not profile.institution_id:
        return jsonify({"error": "El perfil no tiene institución asociada"}), 400

    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        return jsonify({"error": "nombre es obligatorio"}), 400

    texto = (data.get("texto") or "").strip()
    file_storage = request.files.get("archivo") or request.files.get("file")

    if file_storage:
        try:
            texto = PlanParserService.extract_text_from_upload(file_storage)
        except Exception as exc:
            current_app.logger.warning("No se pudo leer el archivo subido: %s", exc)
            return jsonify({"error": "No pudimos leer el archivo. Usa PDF/TXT válido."}), 400

    if not texto:
        return jsonify({"error": "Debes enviar texto o adjuntar un PDF/TXT."}), 400

    anio_raw = data.get("anio_lectivo")
    anio_lectivo = str(anio_raw).strip() if anio_raw is not None else None

    study_plan_id = data.get("study_plan_id")
    study_plan = None
    if study_plan_id:
        try:
            study_plan_id = int(study_plan_id)
        except (TypeError, ValueError):
            return jsonify({"error": "study_plan_id inválido"}), 400
        study_plan = StudyPlan.query.filter_by(
            id=study_plan_id,
            institution_id=profile.institution_id,
        ).first()
        if not study_plan:
            return jsonify({"error": "study_plan_id no pertenece a tu institución"}), 404

    plan = Plan(
        institution_id=profile.institution_id,
        study_plan_id=study_plan.id if study_plan else None,
        nombre=nombre,
        anio_lectivo=anio_lectivo or None,
        jurisdiccion=(data.get("jurisdiccion") or "").strip() or None,
        descripcion_general=(data.get("descripcion_general") or "").strip() or None,
        contenido_bruto=texto,
    )

    db.session.add(plan)
    db.session.flush()

    try:
        items_created = PlanParserService.parse_plan_with_llm(plan)
        db.session.commit()
    except Exception as exc:  # pragma: no cover - depends on external provider
        current_app.logger.exception("No se pudo parsear el plan: %s", exc)
        db.session.rollback()
        return jsonify({"error": "No se pudo procesar el plan. Intenta nuevamente."}), 500

    payload = plan.to_dict()
    payload["items_generados"] = items_created

    return jsonify(payload), 201


def _require_plan(plan_id: int):
    profile = get_current_profile()
    if not profile:
        return None, jsonify({"error": "No autenticado"}), 401
    plan = Plan.query.filter_by(id=plan_id, institution_id=profile.institution_id).first()
    if not plan:
        return None, jsonify({"error": "plan no encontrado"}), 404
    return plan, profile, None


def _grade_filters(plan: Plan, grade_label_raw: str | None, grade_id_raw: str | None):
    grade_label = (grade_label_raw or "").strip()
    normalized = None
    grade_obj = None
    if grade_id_raw:
        try:
            grade_id = int(grade_id_raw)
        except (TypeError, ValueError):
            return None, None, ("grade_id inválido", 400)
        grade_obj = Grade.query.filter_by(
            id=grade_id,
            institution_id=plan.institution_id,
        ).first()
        if not grade_obj:
            return None, None, ("grado no encontrado", 404)
        grade_label = grade_obj.name
    if grade_label:
        normalized = CurriculumService.normalize_grade_label(grade_label, plan.institution_id)
    return grade_label, normalized, None


def _filter_items_by_grade(plan: Plan, grade_label: str | None, normalized: str | None):
    query = PlanItem.query.filter_by(plan_id=plan.id)
    if normalized:
        query = query.filter(
            or_(
                PlanItem.grado_normalizado == normalized,
                func.lower(PlanItem.grado) == func.lower(grade_label),
            )
        )
    elif grade_label:
        query = query.filter(func.lower(PlanItem.grado) == func.lower(grade_label))
    return query.order_by(PlanItem.area.asc(), PlanItem.created_at.asc()).all()


def _serialize_suggestion(item: PlanItem) -> dict:
    metadata = item.metadata_dict
    class_ideas = metadata.get("class_ideas") if isinstance(metadata.get("class_ideas"), list) else []
    title = (
        metadata.get("title")
        or metadata.get("titulo")
        or metadata.get("name")
        or metadata.get("nombre")
        or f"{item.area} · Objetivo"
    )
    return {
        "id": item.id,
        "grado": item.grado,
        "area": item.area,
        "title": title,
        "descripcion": item.descripcion,
        "description": item.descripcion,
        "class_ideas": class_ideas,
        "period": metadata.get("period") or metadata.get("periodo"),
        "metadata": metadata,
    }


@api_bp.get("/planes/<int:plan_id>/grados")
@login_required
def plan_grados(plan_id: int):
    plan, _profile, error = _require_plan(plan_id)
    if error:
        return error
    rows = (
        db.session.query(PlanItem.grado)
        .filter(PlanItem.plan_id == plan.id, PlanItem.grado.isnot(None))
        .distinct()
        .order_by(PlanItem.grado.asc())
        .all()
    )
    grados = [row[0] for row in rows if row[0]]
    return jsonify({"grados": grados})


@api_bp.get("/planes/<int:plan_id>/areas")
@login_required
def plan_areas(plan_id: int):
    plan, _profile, error = _require_plan(plan_id)
    if error:
        return error

    grade_label_raw = request.args.get("grado")
    grade_id_raw = request.args.get("grade_id")
    if not grade_label_raw and not grade_id_raw:
        return jsonify({"error": "Debes enviar grado o grade_id"}), 400

    grade_label, normalized, grade_error = _grade_filters(plan, grade_label_raw, grade_id_raw)
    if grade_error:
        message, status = grade_error
        return jsonify({"error": message}), status

    items = _filter_items_by_grade(plan, grade_label, normalized)
    areas = sorted({item.area for item in items if item.area})
    return jsonify({"areas": areas})


@api_bp.get("/planes/<int:plan_id>/sugerencias")
@login_required
def plan_sugerencias(plan_id: int):
    plan, _profile, error = _require_plan(plan_id)
    if error:
        return error

    area_param = (request.args.get("area") or "").strip()
    grade_label_raw = request.args.get("grado")
    grade_id_raw = request.args.get("grade_id")
    if not grade_label_raw and not grade_id_raw:
        return jsonify({"error": "Debes enviar grado o grade_id"}), 400

    grade_label, normalized, grade_error = _grade_filters(plan, grade_label_raw, grade_id_raw)
    if grade_error:
        message, status = grade_error
        return jsonify({"error": message}), status

    items = _filter_items_by_grade(plan, grade_label, normalized)
    if not items:
        return jsonify({"areas": [], "message": "No encontramos contenidos para ese grado."}), 404

    if area_param:
        filtered = [item for item in items if item.area == area_param]
        return jsonify([_serialize_suggestion(item) for item in filtered])

    grouped: dict[str, list[PlanItem]] = {}
    for item in items:
        grouped.setdefault(item.area, []).append(item)

    payload = []
    for area_name, area_items in sorted(grouped.items(), key=lambda entry: entry[0].lower()):
        payload.append(
            {
                "area": area_name,
                "suggestions": [_serialize_suggestion(item) for item in area_items],
            }
        )

    return jsonify({"areas": payload})
