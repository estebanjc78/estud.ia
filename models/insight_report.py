import enum
from datetime import datetime

from extensions import db


class ReportScope(enum.Enum):
    GLOBAL = "global"
    CLASS = "class"
    STUDENT = "student"


class InsightReport(db.Model):
    __tablename__ = "insight_report"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False)
    author_profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)

    scope = db.Column(db.Enum(ReportScope), nullable=False, default=ReportScope.GLOBAL)
    target_id = db.Column(db.Integer, nullable=True)
    target_label = db.Column(db.String(255), nullable=True)

    ai_model = db.Column(db.String(100), nullable=True)
    prompt_snapshot = db.Column(db.Text, nullable=True)
    context_snapshot = db.Column(db.Text, nullable=True)

    ai_draft = db.Column(db.Text, nullable=True)
    final_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default="draft")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = db.relationship("Profile")
    institution = db.relationship("Institution")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "scope": self.scope.value if self.scope else None,
            "target_id": self.target_id,
            "target_label": self.target_label,
            "status": self.status,
            "ai_model": self.ai_model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "final_text": self.final_text or self.ai_draft,
        }
