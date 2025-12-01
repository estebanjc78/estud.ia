from __future__ import annotations

from typing import TYPE_CHECKING

from extensions import db
from models import TaskHelpUsage
from services.help_rules import (
    HELP_PENALTIES,
    HELP_LEVEL_PRIORITY,
    VALID_LEARNING_STYLES,
    DEFAULT_MAX_POINTS,
)
from sqlalchemy.exc import OperationalError

if TYPE_CHECKING:
    from models import Task, Profile


class HelpUsageService:
    """
    Gestiona el registro temporal de ayudas utilizadas por el alumno
    y ofrece resúmenes listos para mostrar en la UI o descontar puntos.
    """

    LEVEL_TO_COLUMN = {
        "BAJA": "count_baja",
        "MEDIA": "count_media",
        "ALTA": "count_alta",
    }

    @staticmethod
    def get_summary(*, task: "Task", student_profile: "Profile") -> dict:
        try:
            usage = HelpUsageService._get_usage(task_id=task.id, student_id=student_profile.id)
            return HelpUsageService._build_summary(task, usage)
        except OperationalError as exc:  # pragma: no cover - fallback para entornos sin migraciones
            if HelpUsageService._handle_db_error(exc):
                return HelpUsageService._empty_summary(task)
            raise

    @staticmethod
    def increment_usage(
        *,
        task: "Task",
        student_profile: "Profile",
        help_level: str,
        learning_style: str | None = None,
    ) -> dict:
        level = HelpUsageService._normalize_level(help_level)
        if not level:
            raise ValueError("Tipo de ayuda inválido. Usa BAJA, MEDIA o ALTA.")

        try:
            usage = HelpUsageService._get_or_create_usage(task, student_profile)
            column = HelpUsageService.LEVEL_TO_COLUMN[level]
            setattr(usage, column, getattr(usage, column) + 1)

            if learning_style:
                style = HelpUsageService._normalize_style(learning_style)
                if style:
                    usage.learning_style = style

            db.session.commit()
            return HelpUsageService._build_summary(task, usage)
        except OperationalError as exc:  # pragma: no cover
            if HelpUsageService._handle_db_error(exc):
                return HelpUsageService._empty_summary(task)
            raise

    @staticmethod
    def update_style(*, task: "Task", student_profile: "Profile", learning_style: str) -> dict:
        style = HelpUsageService._normalize_style(learning_style)
        if not style:
            raise ValueError("Estilo inválido. Usa VISUAL, ANALITICA o AUDIO.")

        try:
            usage = HelpUsageService._get_or_create_usage(task, student_profile)
            usage.learning_style = style
            db.session.commit()
            return HelpUsageService._build_summary(task, usage)
        except OperationalError as exc:  # pragma: no cover
            if HelpUsageService._handle_db_error(exc):
                return HelpUsageService._empty_summary(task)
            raise

    @staticmethod
    def clear_usage(*, task: "Task", student_profile: "Profile") -> None:
        try:
            usage = HelpUsageService._get_usage(task_id=task.id, student_id=student_profile.id)
            if usage:
                db.session.delete(usage)
                db.session.commit()
        except OperationalError as exc:  # pragma: no cover
            if HelpUsageService._handle_db_error(exc):
                return
            raise

    # -----------------
    # Helpers internos
    # -----------------

    @staticmethod
    def _get_usage(*, task_id: int, student_id: int) -> TaskHelpUsage | None:
        return TaskHelpUsage.query.filter_by(task_id=task_id, student_profile_id=student_id).first()

    @staticmethod
    def _get_or_create_usage(task: "Task", student_profile: "Profile") -> TaskHelpUsage:
        usage = HelpUsageService._get_usage(task_id=task.id, student_id=student_profile.id)
        if usage:
            return usage

        usage = TaskHelpUsage(
            institution_id=task.institution_id,
            task_id=task.id,
            student_profile_id=student_profile.id,
        )
        db.session.add(usage)
        db.session.commit()
        return usage

    @staticmethod
    def _build_summary(task: "Task", usage: TaskHelpUsage | None) -> dict:
        counts = {
            "BAJA": (usage.count_baja if usage else 0) or 0,
            "MEDIA": (usage.count_media if usage else 0) or 0,
            "ALTA": (usage.count_alta if usage else 0) or 0,
        }
        total_penalty = sum(HELP_PENALTIES[level] * counts[level] for level in counts)
        max_points = task.max_points or DEFAULT_MAX_POINTS

        summary = {
            "counts": counts,
            "total_count": sum(counts.values()),
            "dominant_level": HelpUsageService._dominant_level(counts),
            "total_penalty": total_penalty,
            "max_points": max_points,
            "remaining_points": max(max_points - total_penalty, 0),
            "preferred_style": usage.learning_style if usage else None,
        }
        summary["breakdown"] = dict(counts)
        return summary

    @staticmethod
    def _empty_summary(task: "Task") -> dict:
        counts = {"BAJA": 0, "MEDIA": 0, "ALTA": 0}
        max_points = task.max_points or DEFAULT_MAX_POINTS
        return {
            "counts": counts,
            "total_count": 0,
            "dominant_level": None,
            "total_penalty": 0,
            "max_points": max_points,
            "remaining_points": max_points,
            "preferred_style": None,
            "breakdown": counts,
        }

    @staticmethod
    def _handle_db_error(exc: OperationalError) -> bool:
        """
        Devuelve True si debemos ocultar el error (p. ej., tabla inexistente en entornos sin migraciones).
        """
        db.session.rollback()
        message = str(getattr(exc, "orig", exc)).lower()
        if "no such table" in message or "does not exist" in message:
            return True
        return False

    @staticmethod
    def _dominant_level(counts: dict[str, int]) -> str | None:
        for level in HELP_LEVEL_PRIORITY:
            if counts.get(level):
                return level
        return None

    @staticmethod
    def _normalize_level(level: str | None) -> str | None:
        if not level:
            return None
        normalized = level.strip().upper()
        return normalized if normalized in HELP_PENALTIES else None

    @staticmethod
    def _normalize_style(style: str | None) -> str | None:
        if not style:
            return None
        normalized = style.strip().upper()
        return normalized if normalized in VALID_LEARNING_STYLES else None
