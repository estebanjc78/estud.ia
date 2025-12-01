from flask import request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import BitacoraEntrada, Profile, Lesson
from . import api_bp
from datetime import datetime

from api.services.attachment_service import AttachmentService
from api.utils.attachments_helper import serialize_attachment


def _can_write(author_profile: Profile):
    """
    Verifica si el rol del autor permite escribir en la bitácora.
    Por simplicidad: PROFESOR y PSICOPEDAGOGO.
    """
    return author_profile.role.name in ["PROFESOR", "PSICOPEDAGOGIA", "ADMIN", "PSICOPEDAGOGO"]


@api_bp.post("/bitacora")
@login_required
def bitacora_create():
    """
    Crea una nueva entrada de bitácora.
    Body JSON requerido:
    {
      "institution_id": 1,
      "student_profile_id": 22,
      "lesson_id": 14,   (opcional)
      "categoria": "Conducta",
      "nota": "Se peleó en clase con otro alumno",
      "visible_para_padres": true,
      "visible_para_alumno": false
    }
    """

    data = request.json or {}

    # 1. Autor → perfil activo del usuario
    author_profile = Profile.query.filter_by(user_id=current_user.id).first()

    if not author_profile:
        return jsonify({"error": "No tenés un perfil activo"}), 403

    if not _can_write(author_profile):
        return jsonify({"error": "No tenés permisos para escribir en la bitácora"}), 403

    # 2. Validar campos obligatorios
    for field in ["institution_id", "student_profile_id", "categoria", "nota"]:
        if field not in data:
            return jsonify({"error": f"'{field}' es obligatorio"}), 400

    # 3. Validar institución
    if author_profile.institution_id != data["institution_id"]:
        return jsonify({"error": "El docente no pertenece a esta institución"}), 403

    # 4. Validar alumno pertenece a institución
    student = Profile.query.get(data["student_profile_id"])
    if not student or student.institution_id != data["institution_id"]:
        return jsonify({"error": "Alumno inválido"}), 400

    # 5. Validar lesson (si viene)
    lesson_id = data.get("lesson_id")
    if lesson_id:
        lesson = Lesson.query.get(lesson_id)
        if not lesson:
            return jsonify({"error": "La lesson_id no existe"}), 400

    # 6. Crear entrada
    entry = BitacoraEntrada(
        institution_id=data["institution_id"],
        student_profile_id=data["student_profile_id"],
        author_profile_id=author_profile.id,
        lesson_id=lesson_id,
        categoria=data["categoria"],
        nota=data["nota"],
        visible_para_padres=data.get("visible_para_padres", True),
        visible_para_alumno=data.get("visible_para_alumno", False),
        created_at=datetime.utcnow(),
    )

    db.session.add(entry)
    db.session.flush()

    attachments_payload = data.get("attachments")
    created_attachments = AttachmentService.bulk_create_from_payloads(
        context_type="bitacora",
        context_id=entry.id,
        payloads=attachments_payload,
        uploaded_by_profile_id=author_profile.id,
        default_kind="bitacora_evidence",
    )

    db.session.commit()

    return (
        jsonify(
            {
                "status": "created",
                "bitacora_id": entry.id,
                "attachments": [serialize_attachment(a) for a in created_attachments],
            }
        ),
        201,
    )


@api_bp.get("/bitacora/<int:student_profile_id>")
@login_required
def bitacora_list(student_profile_id):
    """
    Lista entradas de bitácora por alumno.
    Respeta visibilidad según rol:
    - Padre → visible_para_padres = True
    - Alumno → visible_para_alumno = True
    - Profesor/Psicopedagogo/Admin → todo
    """

    author_profile = Profile.query.filter_by(user_id=current_user.id).first()

    if not author_profile:
        return jsonify({"error": "Perfil no encontrado"}), 403

    # Ver permisos/visibilidad
    is_parent = author_profile.role.name == "PADRE"
    is_student = author_profile.role.name == "ALUMNO"

    query = BitacoraEntrada.query.filter_by(student_profile_id=student_profile_id)

    if is_parent:
        query = query.filter_by(visible_para_padres=True)

    if is_student:
        query = query.filter_by(visible_para_alumno=True)

    entries = query.order_by(BitacoraEntrada.created_at.desc()).all()

    return jsonify([_serialize_entry(e) for e in entries])


def _serialize_entry(entry: BitacoraEntrada) -> dict:
    return {
        "id": entry.id,
        "categoria": entry.categoria,
        "nota": entry.nota,
        "lesson_id": entry.lesson_id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "visible_para_padres": entry.visible_para_padres,
        "visible_para_alumno": entry.visible_para_alumno,
        "author_profile_id": entry.author_profile_id,
        "attachments": [serialize_attachment(att) for att in (entry.attachments or [])],
    }
