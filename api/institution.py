from flask import request, jsonify
from flask_login import login_required
from extensions import db
from models import Institution
from . import api_bp

@api_bp.get("/institutions/<int:inst_id>")
@login_required
def get_institution(inst_id):
    inst = Institution.query.get_or_404(inst_id)
    return jsonify({
        "id": inst.id,
        "name": inst.name,
        "short_code": inst.short_code,
        "logo_url": inst.logo_url,
        "primary_color": inst.primary_color,
        "secondary_color": inst.secondary_color,
    })

@api_bp.put("/institutions/<int:inst_id>")
@login_required
def update_institution(inst_id):
    inst = Institution.query.get_or_404(inst_id)
    data = request.json or {}

    inst.name = data.get("name", inst.name)
    inst.logo_url = data.get("logo_url", inst.logo_url)
    inst.primary_color = data.get("primary_color", inst.primary_color)
    inst.secondary_color = data.get("secondary_color", inst.secondary_color)

    db.session.commit()
    return jsonify({"status": "ok"})