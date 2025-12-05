from datetime import datetime

from extensions import db


class CurriculumDocument(db.Model):
    __tablename__ = "curriculum_document"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=True)
    uploaded_by_profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    jurisdiction = db.Column(db.String(120), nullable=True)
    year = db.Column(db.Integer, nullable=True)

    source_filename = db.Column(db.String(255), nullable=True)
    storage_path = db.Column(db.String(512), nullable=True)
    mime_type = db.Column(db.String(120), nullable=True)

    raw_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="processing")
    error_message = db.Column(db.Text, nullable=True)

    grade_min = db.Column(db.String(20), nullable=True)
    grade_max = db.Column(db.String(20), nullable=True)
    segment_count = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    institution = db.relationship("Institution")
    uploaded_by = db.relationship("Profile")
    segments = db.relationship(
        "CurriculumSegment",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class CurriculumSegment(db.Model):
    __tablename__ = "curriculum_segment"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("curriculum_document.id"), nullable=False)

    grade_label = db.Column(db.String(20), nullable=True)
    area = db.Column(db.String(120), nullable=True)
    section_title = db.Column(db.String(255), nullable=True)
    content_text = db.Column(db.Text, nullable=False)

    start_line = db.Column(db.Integer, nullable=True)
    end_line = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship("CurriculumDocument", back_populates="segments")
