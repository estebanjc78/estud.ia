from models import TaskSubmission
from api.utils.attachments_helper import serialize_attachment


def serialize_submission(submission: TaskSubmission) -> dict:
    return {
        "id": submission.id,
        "task_id": submission.task_id,
        "student_profile_id": submission.student_profile_id,
        "comment": submission.comment,
        "help_level": submission.help_level,
        "help_count": submission.help_count,
        "help_breakdown": submission.help_breakdown,
        "max_points": submission.max_points,
        "points_awarded": submission.points_awarded,
        "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        "evidences": [
            {
                "id": evidence.id,
                "evidence_type": evidence.evidence_type.value if evidence.evidence_type else None,
                "attachment": serialize_attachment(evidence.attachment) if evidence.attachment else None,
            }
            for evidence in submission.evidences
        ],
    }
