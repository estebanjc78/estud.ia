from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest


logger = logging.getLogger(__name__)


class AIClient:
    """
    Cliente de IA genérico. Por defecto funciona en modo heurístico, pero puede utilizar un
    proveedor real (p. ej. OpenAI) configurando AI_PROVIDER/AI_API_KEY.
    """

    def __init__(self, *, provider_override: str | None = None, model_override: str | None = None):
        self.api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")

        provider_override_norm = (provider_override or "").strip().lower() or None
        if provider_override_norm and provider_override_norm not in {"openai", "heuristic"}:
            logger.warning("Proveedor de IA '%s' no soportado. Usamos configuración global.", provider_override)
            provider_override_norm = None

        provider = os.getenv("AI_PROVIDER")
        if provider_override_norm:
            self.provider = provider_override_norm
        elif provider:
            self.provider = provider.lower()
        elif self.api_key:
            # Si hay clave pero no se configuró proveedor, asumimos OpenAI.
            self.provider = "openai"
        else:
            self.provider = "heuristic"

        default_model = os.getenv("AI_MODEL") or "gpt-4o-mini"
        override_model = (model_override or "").strip()
        self.model = override_model or default_model
        self.temperature = self._float_env("AI_TEMPERATURE", default=0.2)
        self.max_tokens = int(os.getenv("AI_MAX_TOKENS", "700") or 700)
        self.timeout = self._float_env("AI_TIMEOUT", default=20.0)
        self.api_base = os.getenv("AI_API_BASE", "https://api.openai.com/v1").rstrip("/")

    @staticmethod
    def _float_env(var_name: str, default: float) -> float:
        raw = os.getenv(var_name)
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            logger.warning("Valor inválido para %s=%s. Se usa %s por defecto.", var_name, raw, default)
            return default

    def generate(self, prompt: str, context: dict) -> dict:
        """
        Devuelve un dict con texto generado y metadata básica.
        """
        if self.provider == "openai" and self.api_key:
            try:
                return self._openai_response(prompt, context)
            except Exception as exc:  # pragma: no cover - sólo se usa cuando OpenAI falla
                logger.warning("Fallo al invocar OpenAI, se usa fallback heurístico: %s", exc)

        # Si no hay proveedor real o falló, lo resolvemos in-memory.
        return self._heuristic_response(prompt, context, provider_override="heuristic")

    def _openai_response(self, prompt: str, context: dict) -> dict:
        """
        Llama a la API de chat completions para generar el informe.
        """
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Actúas como asesor pedagógico senior. Redactas informes claros, empáticos y accionables "
                        "basados estrictamente en los datos provistos. Menciona hallazgos, alertas y próximos pasos."
                    ),
                },
                {"role": "user", "content": prompt},
                {
                    "role": "user",
                    "content": "Contexto estructurado:\n{}".format(
                        json.dumps(context, ensure_ascii=False, indent=2)
                    ),
                },
            ],
        }

        request = urlrequest.Request(
            f"{self.api_base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urlrequest.urlopen(request, timeout=self.timeout) as response:
                data = response.read().decode("utf-8")
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        except urlerror.URLError as exc:
            raise RuntimeError(f"OpenAI request error: {exc.reason}") from exc

        payload = json.loads(data)
        choice: dict[str, Any] = (payload.get("choices") or [{}])[0]
        message = (choice.get("message") or {}).get("content", "").strip()
        if not message:
            raise RuntimeError("OpenAI devolvió una respuesta vacía.")

        return {
            "text": message,
            "model": payload.get("model") or self.model,
            "provider": "openai",
            "context_snapshot": json.dumps(context, ensure_ascii=False),
        }

    def _heuristic_response(self, prompt: str, context: dict, provider_override: str | None = None) -> dict:
        scope = context.get("scope", "global")
        metrics = context.get("metrics", {})
        highlights = context.get("highlights", [])
        followups = context.get("followups", [])
        learning = context.get("learning", {})

        lines = [
            f"Reporte {scope.upper()} — generado automáticamente ({datetime.utcnow():%d/%m %H:%M} UTC).",
            "",
        ]

        if metrics:
            lines.append("Resumen de métricas:")
            if "tasks_total" in metrics:
                lines.append(f"- Tareas evaluadas: {metrics['tasks_total']}")
            if "approvals" in metrics:
                lines.append(f"- Aprobaciones: {metrics['approvals']} · {metrics.get('approval_rate', 0)}%")
            if "no_help_rate" in learning:
                lines.append(f"- % de entregas sin ayudas: {learning['no_help_rate']}%")
            if "late_submissions" in metrics:
                lines.append(f"- Entregas tardías: {metrics['late_submissions']}")
            lines.append("")

        if highlights:
            lines.append("Hallazgos relevantes:")
            for item in highlights:
                lines.append(f"- {item}")
            lines.append("")

        if followups:
            lines.append("Seguimientos psicopedagógicos:")
            for item in followups:
                lines.append(f"- {item}")
            lines.append("")

        lines.append("Recomendaciones sugeridas:")
        if learning.get("actions"):
            for action in learning["actions"]:
                lines.append(f"- {action}")
        else:
            lines.append("- Mantener el monitoreo semanal y reforzar en grupos reducidos.")

        body = "\n".join(lines).strip()
        return {
            "text": body,
            "model": "heuristic",
            "provider": provider_override or self.provider,
            "context_snapshot": json.dumps(context, ensure_ascii=False),
        }
