# api/services/submission_service.py

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from extensions import db
from models import (
    Task,
    TaskSubmission,
    SubmissionEvidence,
    EvidenceTypeEnum,
    Profile,
)
from api.services.attachment_service import AttachmentService
from services.help_rules import HELP_PENALTIES, DEFAULT_MAX_POINTS, HELP_LEVEL_PRIORITY


class SubmissionService:
    """
    Lógica centralizada para crear entregas y calcular puntajes.
    """

    DEFAULT_MAX_POINTS = DEFAULT_MAX_POINTS
    HELP_PENALTIES = HELP_PENALTIES
    HELP_LEVEL_PRIORITY = HELP_LEVEL_PRIORITY

    @staticmethod
    def create_submission(
        *,
        task: Task,
        student_profile: Profile,
        payload: Mapping,
    ) -> TaskSubmission:
        help_breakdown = SubmissionService._normalize_breakdown(payload.get("help_breakdown"))

        help_level_raw = (payload.get("help_level") or "").upper() or None
        help_count = payload.get("help_count") or 0

        if help_breakdown:
            help_level_raw = SubmissionService._dominant_level(help_breakdown) or help_level_raw
            help_count = sum(help_breakdown.values())
        else:
            if help_level_raw and help_level_raw not in SubmissionService.HELP_PENALTIES:
                raise ValueError("help_level inválido. Usa BAJA, MEDIA o ALTA.")
            try:
                help_count = int(help_count)
            except (TypeError, ValueError):
                raise ValueError("help_count debe ser numérico.")
            if help_count < 0:
                raise ValueError("help_count debe ser >= 0.")

        base_points = payload.get("max_points")
        if base_points is not None:
            try:
                base_points = int(base_points)
            except (TypeError, ValueError):
                raise ValueError("max_points debe ser numérico.")
        base_points = base_points or task.max_points or SubmissionService.DEFAULT_MAX_POINTS

        penalty_points = (
            SubmissionService._penalty_from_breakdown(help_breakdown)
            if help_breakdown
            else SubmissionService.HELP_PENALTIES.get(help_level_raw, 0) * help_count
        )
        points_awarded = max(base_points - penalty_points, 0)

        submission = TaskSubmission(
            task_id=task.id,
            student_profile_id=student_profile.id,
            comment=payload.get("comment"),
            help_level=help_level_raw,
            help_count=help_count,
            help_breakdown=help_breakdown or None,
            max_points=base_points,
            points_awarded=points_awarded,
            submitted_at=datetime.utcnow(),
        )

        db.session.add(submission)
        db.session.flush()

        evidences_payload = payload.get("evidences") or []
        SubmissionService._attach_evidences(
            submission=submission,
            evidences_payload=evidences_payload,
            uploaded_by=student_profile,
        )

        db.session.commit()
        db.session.refresh(submission)
        return submission

    @staticmethod
    def _attach_evidences(
        *,
        submission: TaskSubmission,
        evidences_payload: Sequence[Mapping] | None,
        uploaded_by: Profile,
    ) -> None:
        if not evidences_payload:
            return

        for payload in evidences_payload:
            evidence_type_raw = (payload.get("evidence_type") or "").upper()
            if not evidence_type_raw:
                continue

            try:
                evidence_type = EvidenceTypeEnum(evidence_type_raw)
            except ValueError:
                continue

            attachment_data = payload.get("attachment") or {}
            filename = (attachment_data.get("filename") or "").strip()
            storage_path = (attachment_data.get("storage_path") or "").strip()
            if not filename or not storage_path:
                continue

            attachment = AttachmentService.create_attachment(
                context_type="submission",
                context_id=submission.id,
                filename=filename,
                storage_path=storage_path,
                kind=payload.get("kind") or "submission_evidence",
                mime_type=attachment_data.get("mime_type"),
                file_size=attachment_data.get("file_size"),
                uploaded_by_profile_id=uploaded_by.id,
                visibility=attachment_data.get("visibility"),
            )
            db.session.flush()  # asegurar attachment.id

            db.session.add(
                SubmissionEvidence(
                    submission_id=submission.id,
                    attachment_id=attachment.id,
                    evidence_type=evidence_type,
                )
            )

    @staticmethod
    def _normalize_breakdown(raw_breakdown) -> dict[str, int]:
        if not raw_breakdown:
            return {}
        normalized: dict[str, int] = {}
        for level, count in raw_breakdown.items():
            if level is None:
                continue
            level_key = str(level).upper()
            if level_key not in SubmissionService.HELP_PENALTIES:
                continue
            try:
                value = int(count)
            except (TypeError, ValueError):
                continue
            if value > 0:
                normalized[level_key] = normalized.get(level_key, 0) + value
        return normalized

    @staticmethod
    def _dominant_level(breakdown: dict[str, int]) -> str | None:
        for level in SubmissionService.HELP_LEVEL_PRIORITY:
            if breakdown.get(level):
                return level
        return None

    @staticmethod
    def _penalty_from_breakdown(breakdown: dict[str, int]) -> int:
        return sum(SubmissionService.HELP_PENALTIES[level] * count for level, count in breakdown.items())
