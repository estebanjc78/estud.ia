from __future__ import annotations

import json
from typing import Any, Iterable

from flask import current_app
from sqlalchemy import or_

from models import Objective, Lesson, Task, PlanItem, Institution
from services.ai_client import AIClient
from services.curriculum_service import CurriculumService


class AuthoringService:
    """
    Generador centralizado de textos para clases y tareas utilizando IA (o heurísticas).
    Devuelve siempre estructuras simples para integrar directamente en la UI.
    """

    LESSON_PROMPT = """
Actúas como coordinador pedagógico. A partir de los datos provistos, redacta la descripción oficial
de una clase y su agenda (3 a 4 momentos clave). Usa un tono profesional y breve.
Devuelve EXCLUSIVAMENTE JSON con la forma:
{
  "description": "texto en 3-4 frases",
  "agenda": ["momento 1", "momento 2", "momento 3"]
}
    """.strip()

    TASK_PROMPT = """
Eres asesor pedagógico. Con los datos de clase/objetivo, redacta la consigna de una tarea y las ayudas
que el profesor podrá ofrecer. Devuelve únicamente JSON:
{
  "description": "consigna de la tarea",
  "helps": {
     "BAJA": "pista breve",
     "MEDIA": "guía paso a paso",
     "ALTA": "explicación completa"
  }
}
    """.strip()

    @classmethod
    def generate_lesson_brief(
        cls,
        *,
        lesson: Lesson | None = None,
        objective: Objective | None = None,
        section_label: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        institution = cls._resolve_institution(objective, lesson)
        plan_context = cls._plan_context(objective)
        grade_label = objective.grade.name if objective and objective.grade else None
        subject = cls._subject_name(objective)

        payload = {
            "title": title or getattr(lesson, "title", None),
            "grade": grade_label or section_label,
            "section": section_label,
            "subject": subject,
            "objective_title": getattr(objective, "title", None),
            "objective_description": getattr(objective, "description", None),
            "plan_snippets": plan_context,
        }

        client = cls._client_for_institution(institution)
        result = client.generate(cls.LESSON_PROMPT, {"scope": "lesson_brief", **payload})
        parsed = cls._safe_parse(result.get("text", ""))
        if isinstance(parsed, dict):
            return {
                "description": parsed.get("description") or cls._lesson_fallback_description(payload),
                "agenda": cls._normalize_list(parsed.get("agenda")),
            }
        return {
            "description": cls._lesson_fallback_description(payload),
            "agenda": cls._default_agenda(subject),
        }

    @classmethod
    def generate_task_brief(
        cls,
        *,
        task: Task | None = None,
        lesson: Lesson | None = None,
        objective: Objective | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        objective = objective or (lesson.objective if lesson else None)
        institution = cls._resolve_institution(objective, lesson, task)
        plan_context = cls._plan_context(objective)
        subject = cls._subject_name(objective)
        lesson_title = getattr(lesson, "title", None) or getattr(task, "title", None)

        payload = {
            "task_title": getattr(task, "title", None),
            "lesson_title": lesson_title,
            "subject": subject,
            "grade": objective.grade.name if objective and objective.grade else None,
            "objective_title": getattr(objective, "title", None),
            "objective_description": getattr(objective, "description", None),
            "lesson_description": getattr(lesson, "description", None),
            "due_date": due_date,
            "plan_snippets": plan_context,
        }

        client = cls._client_for_institution(institution)
        result = client.generate(cls.TASK_PROMPT, {"scope": "task_brief", **payload})
        parsed = cls._safe_parse(result.get("text", ""))
        if isinstance(parsed, dict):
            helps = parsed.get("helps") or {}
            return {
                "description": parsed.get("description") or cls._task_fallback_description(payload),
                "helps": cls._normalize_helps(helps, subject),
            }
        return {
            "description": cls._task_fallback_description(payload),
            "helps": cls._default_helps(subject),
        }

    # -----------------
    # Helpers internos
    # -----------------

    @staticmethod
    def _client_for_institution(institution: Institution | None) -> AIClient:
        if not institution:
            return AIClient()
        return AIClient(
            provider_override=institution.ai_provider,
            model_override=institution.ai_model,
        )

    @staticmethod
    def _resolve_institution(
        objective: Objective | None,
        lesson: Lesson | None = None,
        task: Task | None = None,
    ) -> Institution | None:
        institution_id = None
        if objective and objective.study_plan:
            institution_id = objective.study_plan.institution_id
        if not institution_id and lesson:
            institution_id = lesson.institution_id
        if not institution_id and task:
            institution_id = task.institution_id
        if not institution_id:
            return None
        return Institution.query.get(institution_id)

    @staticmethod
    def _subject_name(obj: Objective | None) -> str | None:
        if not obj:
            return None
        if obj.subject_label:
            return obj.subject_label
        if obj.study_plan and obj.study_plan.name:
            return obj.study_plan.name
        return None

    @staticmethod
    def _plan_context(objective: Objective | None, limit: int = 5) -> list[str]:
        if not objective or not objective.study_plan or not objective.study_plan.parsed_plan:
            return []
        plan = objective.study_plan.parsed_plan
        query = PlanItem.query.filter(PlanItem.plan_id == plan.id)
        grade_label = None
        if objective.grade:
            grade_label = CurriculumService.normalize_grade_label(objective.grade.name, plan.institution_id)
            query = query.filter(
                or_(
                    PlanItem.grado == objective.grade.name,
                    PlanItem.grado_normalizado == grade_label,
                )
            )
        items = query.order_by(PlanItem.area.asc()).limit(limit).all()
        return [f"{item.area}: {item.descripcion}" for item in items if item.descripcion]

    @staticmethod
    def _safe_parse(raw_text: str) -> Any:
        candidate = AuthoringService._extract_json_candidate(raw_text)
        if not candidate:
            return None
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_json_candidate(text: str) -> str | None:
        if not text:
            return None
        start = text.find("{")
        alt_start = text.find("[")
        if alt_start != -1 and (start == -1 or alt_start < start):
            start = alt_start
        if start == -1:
            return None
        end_curly = text.rfind("}")
        end_bracket = text.rfind("]")
        end = max(end_curly, end_bracket)
        if end == -1 or end <= start:
            return None
        return text[start : end + 1]

    @staticmethod
    def _normalize_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @staticmethod
    def _normalize_helps(raw: Any, subject: str | None) -> dict[str, str]:
        helps = {"BAJA": "", "MEDIA": "", "ALTA": ""}
        if isinstance(raw, dict):
            for level in helps:
                text = raw.get(level) or raw.get(level.capitalize())
                if text:
                    helps[level] = str(text).strip()
        for level, default in AuthoringService._default_helps(subject).items():
            if not helps[level]:
                helps[level] = default
        return helps

    @staticmethod
    def _lesson_fallback_description(payload: dict[str, Any]) -> str:
        title = payload.get("title") or "Clase planificada"
        objective = payload.get("objective_title") or "el objetivo pedagógico seleccionado"
        subject = payload.get("subject") or "el área correspondiente"
        grade = payload.get("grade")
        base = f"{title}: abordaremos {subject.lower()} para reforzar {objective.lower()}."
        if grade:
            base += f" Enfocado en {grade}."
        snippets: Iterable[str] = payload.get("plan_snippets") or []
        if snippets:
            base += f" Referencia de contenidos: {snippets[0][:120]}."
        return base

    @staticmethod
    def _task_fallback_description(payload: dict[str, Any]) -> str:
        subject = payload.get("subject") or "la asignatura"
        objective = payload.get("objective_title") or "el objetivo trabajado en clase"
        lesson_title = payload.get("lesson_title") or "la última clase"
        due = payload.get("due_date")
        base = (
            f"Desarrollo de {subject.lower()} para consolidar {objective.lower()} a partir de «{lesson_title}». "
            "Incluye consignas de aplicación y reflexión."
        )
        if due:
            base += f" Entrega pactada para {due}."
        return base

    @staticmethod
    def _default_agenda(subject: str | None) -> list[str]:
        area = subject or "el tema"
        return [
            f"Apertura y activación de saberes previos sobre {area.lower()}",
            "Exploración guiada con ejemplos y preguntas",
            "Trabajo colaborativo y socialización de hallazgos",
            "Cierre con evaluación rápida y asignación de tarea",
        ]

    @staticmethod
    def _default_helps(subject: str | None) -> dict[str, str]:
        area = subject or "el contenido"
        return {
            "BAJA": f"Relee la consigna y subraya los datos clave vinculados a {area.lower()}. ¿Qué te pide demostrar?",
            "MEDIA": f"Divide la consigna en pasos: 1) identifica conceptos de {area.lower()}, 2) relaciona con el ejemplo visto, 3) arma tu respuesta.",
            "ALTA": f"Repasa el ejemplo trabajado en clase sobre {area.lower()} y replica el procedimiento: describe el contexto, explica la estrategia y justifica el resultado.",
        }
