from __future__ import annotations

from typing import Optional

from extensions import db
from models import InsightReport, ReportScope, Profile, Lesson
from services.ai_client import AIClient
from services.insights_service import InsightsService


class AIInsightsService:
    """
    Orquesta la generación de reportes IA a partir del contexto de InsightsService.
    """

    REPORT_FLAVORS = {
        "standard": {
            "label": "Clásico",
            "description": "Balance entre datos y acciones.",
            "prompt": "Mantén un tono profesional y equilibrado, combinando datos duros con recomendaciones claras.",
        },
        "families": {
            "label": "Enfoque familias",
            "description": "Lenguaje cercano para comunicar avances y pendientes.",
            "prompt": "Usa un lenguaje cercano y sencillo orientado a familias. Explica logros y próximos pasos evitando tecnicismos.",
        },
        "executive": {
            "label": "Directivo",
            "description": "Insights para la dirección académica.",
            "prompt": "Prioriza KPIs y decisiones estratégicas para directivos. Sé conciso y orientado a acciones.",
        },
        "wellbeing": {
            "label": "Socioemocional",
            "description": "Resalta alertas y apoyos psicoemocionales.",
            "prompt": "Pon foco en bienestar y acompañamiento socioemocional. Señala alertas tempranas y recursos de apoyo.",
        },
    }

    @staticmethod
    def generate_report(
        *,
        author: Profile,
        scope: ReportScope,
        target_id: Optional[int] = None,
        flavor: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ) -> InsightReport:
        context, target_label = InsightsService.build_report_context(
            profile=author,
            scope=scope,
            target_id=target_id,
        )

        prompt = AIInsightsService._prompt_for_scope(
            scope=scope,
            target_label=target_label,
            flavor=flavor,
            custom_instructions=custom_prompt,
        )
        institution = getattr(author, "institution", None)
        institution_provider = institution.ai_provider if institution else None
        institution_model = institution.ai_model if institution else None

        client = AIClient(
            provider_override=institution_provider,
            model_override=institution_model,
        )
        ai_result = client.generate(prompt=prompt, context=context)

        report = InsightReport(
            institution_id=author.institution_id,
            author_profile_id=author.id,
            scope=scope,
            target_id=target_id,
            target_label=target_label,
            ai_model=ai_result.get("model"),
            prompt_snapshot=prompt,
            context_snapshot=ai_result.get("context_snapshot"),
            ai_draft=ai_result.get("text"),
            final_text=ai_result.get("text"),
            status="draft",
        )

        db.session.add(report)
        db.session.commit()
        return report

    @staticmethod
    def available_flavors() -> list[dict]:
        return [
            {"value": key, "label": data["label"], "description": data["description"]}
            for key, data in AIInsightsService.REPORT_FLAVORS.items()
        ]

    @staticmethod
    def _prompt_for_scope(
        *,
        scope: ReportScope,
        target_label: Optional[str],
        flavor: Optional[str],
        custom_instructions: Optional[str],
    ) -> str:
        label = target_label or "la institución"
        base_prompt: str
        if scope == ReportScope.STUDENT:
            base_prompt = (
                f"Eres un asesor pedagógico. Redacta un reporte individual para {label} "
                "destacando el desempeño académico, uso de ayudas y acciones sugeridas para familias y docentes. "
                "Sé empático, evita juicios absolutos y ofrece próximos pasos concretos."
            )
        elif scope == ReportScope.CLASS:
            base_prompt = (
                f"Eres un coach docente. Crea un informe ejecutivo para la clase {label}, "
                "resumiendo aprobaciones, dificultades y necesidades de intervención psicopedagógica. "
                "Incluye acciones recomendadas para el profesor y mensajes clave para las familias."
            )
        else:
            base_prompt = (
                "Eres un director académico. Resume el estado global del curso/institución, "
                "indicando logros, riesgos y decisiones sugeridas para el próximo ciclo."
            )

        flavor_key = (flavor or "standard").lower()
        flavor_prompt = AIInsightsService.REPORT_FLAVORS.get(flavor_key, {}).get("prompt")

        custom = (custom_instructions or "").strip()

        parts = [base_prompt]
        if flavor_prompt:
            parts.append(flavor_prompt)
        if custom:
            parts.append(f"Instrucciones personalizadas: {custom}")

        return "\n".join(parts)
