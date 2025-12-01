# api/submissions.py

from flask import request, jsonify, abort
from flask_login import login_required, current_user

from . import api_bp
from models import Task, TaskSubmission
from api.services.profile_service import ProfileService
from api.services.submission_service import SubmissionService
from api.utils.submissions_helper import serialize_submission


@api_bp.post("/tasks/<int:task_id>/submissions")
@login_required
def create_task_submission(task_id):
    profile = _require_current_profile()
    task = Task.query.get(task_id)

    if not task:
        return jsonify({"error": "la tarea no existe"}), 404

    try:
        ProfileService.ensure_institution_membership(profile, task.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    try:
        ProfileService.require_role(profile, "ALUMNO")
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    data = request.json or {}

    try:
        submission = SubmissionService.create_submission(
            task=task,
            student_profile=profile,
            payload=data,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "submitted", "submission": serialize_submission(submission)}), 201


@api_bp.get("/tasks/<int:task_id>/submissions")
@login_required
def list_task_submissions(task_id):
    profile = _require_current_profile()
    task = Task.query.get(task_id)

    if not task:
        return jsonify({"error": "la tarea no existe"}), 404

    try:
        ProfileService.ensure_institution_membership(profile, task.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    query = TaskSubmission.query.filter_by(task_id=task_id).order_by(TaskSubmission.submitted_at.desc())

    if profile.role and profile.role.name == "ALUMNO":
        query = query.filter_by(student_profile_id=profile.id)

    submissions = query.all()
    return jsonify([serialize_submission(s) for s in submissions])


@api_bp.get("/submissions/<int:submission_id>")
@login_required
def get_submission_detail(submission_id):
    profile = _require_current_profile()
    submission = TaskSubmission.query.get(submission_id)

    if not submission:
        return jsonify({"error": "submission no encontrada"}), 404

    task = submission.task
    if not task:
        return jsonify({"error": "tarea asociada no encontrada"}), 404

    try:
        ProfileService.ensure_institution_membership(profile, task.institution_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403

    if profile.role and profile.role.name == "ALUMNO" and submission.student_profile_id != profile.id:
        return jsonify({"error": "No tenés acceso a esta entrega."}), 403

    return jsonify(serialize_submission(submission))


def _require_current_profile():
    try:
        return ProfileService.require_profile(current_user.id)
    except ValueError as exc:
        abort(403, description=str(exc))
