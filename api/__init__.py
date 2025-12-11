from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from . import (
    auth,
    institution,
    profiles,
    activation,
    lessons,
    tasks,
    bitacora,
    messages,
    submissions,
    study_plan,
    planes,
)
