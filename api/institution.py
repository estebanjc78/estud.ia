from flask import request, jsonify
from flask_login import login_required
from extensions import db
from models import Institution
from . import api_bp
import re

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
        "rewards_config": inst.rewards_config or [],
    })

@api_bp.put("/institutions/<int:inst_id>")
@login_required
def update_institution(inst_id):
    inst = Institution.query.get_or_404(inst_id)
    data = request.json or {}

    if "name" in data:
        inst.name = (data.get("name") or inst.name).strip() or inst.name

    if "logo_url" in data:
        inst.logo_url = (data.get("logo_url") or "").strip() or None

    if "primary_color" in data:
        inst.primary_color = _normalize_hex_color(data.get("primary_color"))

    if "secondary_color" in data:
        inst.secondary_color = _normalize_hex_color(data.get("secondary_color"))

    if "rewards_config" in data:
        try:
            inst.rewards_config = _normalize_rewards(data.get("rewards_config"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify({
        "status": "ok",
        "institution": {
            "id": inst.id,
            "name": inst.name,
            "logo_url": inst.logo_url,
            "primary_color": inst.primary_color,
            "secondary_color": inst.secondary_color,
            "rewards_config": inst.rewards_config or [],
        }
    })


HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")


def _normalize_hex_color(raw):
    if not raw:
        return None
    raw = raw.strip()
    if not HEX_COLOR_RE.match(raw):
        raise ValueError("Los colores deben estar en formato HEX (#RRGGBB).")
    return raw.upper()


def _normalize_rewards(rewards_payload):
    if rewards_payload is None:
        return None

    if not isinstance(rewards_payload, list):
        raise ValueError("rewards_config debe ser una lista.")

    cleaned = []
    for item in rewards_payload:
        if not isinstance(item, dict):
            raise ValueError("Cada recompensa debe ser un objeto con nombre y puntos.")
        nombre = (item.get("nombre") or "").strip()
        puntos = item.get("puntos")
        if not nombre:
            raise ValueError("Cada recompensa necesita 'nombre'.")
        try:
            puntos = int(puntos)
        except (TypeError, ValueError):
            raise ValueError("El campo 'puntos' debe ser numérico.")
        if puntos < 0:
            raise ValueError("El campo 'puntos' debe ser >= 0.")
        cleaned.append({"nombre": nombre, "puntos": puntos})

    return cleaned
