from __future__ import annotations

import json
from typing import Iterator, Sequence

from flask import current_app
from werkzeug.datastructures import FileStorage

from extensions import db
from models import Plan, PlanDocument, PlanItem, StudyPlan
from services.ai_client import AIClient
from services.curriculum_service import CurriculumService

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - fallback only when dependency missing
    PdfReader = None


class PlanParserService:
    """
    Servicio encargado de:
    - extraer texto desde archivos PDF o TXT
    - trocear el contenido y pedirle a un LLM que devuelva (grado, área, descripción)
    - persistir los PlanItem asociados
    """

    MAX_CHARS = 6000
    OVERLAP = 400

    LLM_INSTRUCTION = """
Actúas como un parser semántico de documentos educativos (planes de estudio, diseños curriculares, programas, bibliografías).
Recibirás un FRAGMENTO de texto en español perteneciente a un plan de estudio.
Debes devolver EXCLUSIVAMENTE un JSON válido (sin comentarios ni texto extra) con una lista de ítems, donde cada ítem tiene:
- "grado": string con el número de grado (por ejemplo "1", "2", "3") o null si no se especifica en este fragmento.
- "area": nombre de la materia/área (por ejemplo Lengua, Matemática, Ciencias Sociales, Ciencias Naturales, Educación Artística, Inglés, etc.). Si el fragmento es más bien bibliográfico, puedes usar áreas temáticas como "Educación intercultural", "Alfabetización inicial", etc.
- "descripcion": un resumen corto (2–4 frases máximo) con los contenidos u objetivos asociados a ese grado y área en este fragmento. No pegues bloques largos de texto literal: sintetiza.
Si el fragmento no tiene información aprovechable, devuelve [].
    """.strip()

    @staticmethod
    def extract_text_from_upload(file_storage: FileStorage) -> str:
        filename = (file_storage.filename or "").lower()
        mimetype = (file_storage.mimetype or "").lower()
        if filename.endswith(".pdf") or "pdf" in mimetype:
            return PlanParserService.extract_text_from_pdf(file_storage)
        file_storage.stream.seek(0)
        raw = file_storage.read()
        text = raw.decode("utf-8", errors="ignore")
        return text.strip()

    @staticmethod
    def extract_text_from_pdf(file_storage: FileStorage) -> str:
        if PdfReader is None:
            raise RuntimeError("Instala 'pypdf' para poder leer archivos PDF.")
        file_storage.stream.seek(0)
        reader = PdfReader(file_storage.stream)
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text:
                pages.append(text)
        content = "\n".join(pages).strip()
        if not content:
            raise RuntimeError("El PDF no contiene texto legible.")
        return content

    @classmethod
    def persist_plan_document(
        cls,
        *,
        study_plan: StudyPlan | None,
        plan_document: PlanDocument,
        institution_id: int,
        nombre: str,
        anio_lectivo: str | None,
        jurisdiccion: str | None,
        descripcion_general: str | None,
        raw_text: str,
        client: AIClient | None = None,
    ) -> tuple[Plan, int]:
        """
        Procesa un documento curricular asociado a un StudyPlan.
        """
        text = (raw_text or plan_document.curriculum_document.raw_text or "").strip()
        if not text:
            raise ValueError("El contenido del plan está vacío.")

        items_payload = cls._collect_llm_items(
            text=text,
            institution_id=institution_id,
            plan_document=plan_document,
            client=client,
        )

        plan = cls._ensure_plan(
            study_plan=study_plan,
            institution_id=institution_id,
            nombre=nombre,
            anio_lectivo=anio_lectivo,
            jurisdiccion=jurisdiccion,
            descripcion_general=descripcion_general,
            contenido=text,
        )

        created = cls._persist_plan_items(
            plan=plan,
            plan_document=plan_document,
            items_payload=items_payload,
            delete_existing=True,
        )
        return plan, created

    @classmethod
    def parse_plan_with_llm(
        cls,
        plan: Plan,
        *,
        client: AIClient | None = None,
        chunk_size: int | None = None,
        reset_previous: bool = False,
    ) -> int:
        """
        Procesa plan.contenido_bruto en fragmentos y genera PlanItem persistidos.
        Devuelve la cantidad de items creados.
        """
        text = (plan.contenido_bruto or "").strip()
        if not text:
            return 0

        items_payload = cls._collect_llm_items(
            text=text,
            institution_id=plan.institution_id,
            plan_document=None,
            client=client,
            chunk_size=chunk_size,
        )
        return cls._persist_plan_items(
            plan=plan,
            plan_document=None,
            items_payload=items_payload,
            delete_existing=reset_previous,
        )

    @classmethod
    def _ensure_plan(
        cls,
        *,
        study_plan: StudyPlan | None,
        institution_id: int,
        nombre: str,
        anio_lectivo: str | None,
        jurisdiccion: str | None,
        descripcion_general: str | None,
        contenido: str,
    ) -> Plan:
        plan = study_plan.parsed_plan if study_plan and study_plan.parsed_plan else None
        if not plan:
            plan = Plan(
                institution_id=institution_id,
                study_plan_id=study_plan.id if study_plan else None,
            )
        else:
            if study_plan and plan.study_plan_id != study_plan.id:
                plan.study_plan_id = study_plan.id

        plan.nombre = nombre.strip() or plan.nombre or "Plan"
        plan.anio_lectivo = (anio_lectivo or "").strip() or None
        plan.jurisdiccion = (jurisdiccion or "").strip() or None
        plan.descripcion_general = (descripcion_general or "").strip() or None
        plan.contenido_bruto = contenido

        db.session.add(plan)
        db.session.flush()
        return plan

    @classmethod
    def _collect_llm_items(
        cls,
        *,
        text: str,
        institution_id: int,
        plan_document: PlanDocument | None,
        client: AIClient | None,
        chunk_size: int | None = None,
    ) -> list[dict]:
        client = client or AIClient()
        max_chars = chunk_size or cls.MAX_CHARS
        collected: list[dict] = []

        for fragment_index, fragment in enumerate(cls._chunk_text(text, max_chars, cls.OVERLAP)):
            prompt = cls._build_prompt(fragment, fragment_index)
            try:
                result = client.generate(
                    prompt=prompt,
                    context={
                        "fragment_index": fragment_index,
                        "plan_document_id": plan_document.id if plan_document else None,
                    },
                )
            except Exception as exc:  # pragma: no cover - depends on external provider
                current_app.logger.warning("LLM parse falló en fragmento %s: %s", fragment_index, exc)
                continue

            items = cls._parse_llm_payload(result.get("text", ""))
            if not items:
                continue

            for payload in items:
                description = (payload.get("descripcion") or "").strip()
                if not description:
                    continue
                area = (payload.get("area") or "").strip() or "General"
                grade = cls._coerce_grade(payload.get("grado"))

                normalized_grade = None
                if grade:
                    normalized_grade = CurriculumService.normalize_grade_label(grade, institution_id)

                collected.append(
                    {
                        "grado": grade,
                        "grado_normalizado": normalized_grade,
                        "area": area[:255],
                        "descripcion": description,
                        "metadata": cls._merge_metadata(payload, fragment_index),
                    }
                )

        return collected

    @classmethod
    def _persist_plan_items(
        cls,
        *,
        plan: Plan,
        plan_document: PlanDocument | None,
        items_payload: list[dict],
        delete_existing: bool,
    ) -> int:
        if delete_existing:
            query = PlanItem.query.filter(PlanItem.plan_id == plan.id)
            if plan_document:
                query = query.filter(PlanItem.plan_document_id == plan_document.id)
            query.delete(synchronize_session=False)
            db.session.flush()

        for payload in items_payload:
            plan_item = PlanItem(
                plan_id=plan.id,
                plan_document_id=plan_document.id if plan_document else None,
                grado=payload.get("grado"),
                grado_normalizado=payload.get("grado_normalizado"),
                area=payload.get("area"),
                descripcion=payload.get("descripcion"),
            )
            plan_item.metadata_dict = payload.get("metadata") or {}
            db.session.add(plan_item)

        return len(items_payload)

    @staticmethod
    def _chunk_text(text: str, max_chars: int, overlap: int) -> Iterator[str]:
        clean = text.strip()
        if not clean:
            return
        overlap = min(overlap, max_chars // 2)
        start = 0
        length = len(clean)
        while start < length:
            end = min(length, start + max_chars)
            chunk = clean[start:end]
            if end < length:
                newline_break = chunk.rfind("\n")
                if newline_break > max_chars * 0.5:
                    end = start + newline_break
                    chunk = clean[start:end]
            chunk = chunk.strip()
            if not chunk:
                break
            yield chunk
            if end >= length:
                break
            start = max(end - overlap, start + max_chars)

    @classmethod
    def _build_prompt(cls, fragment: str, index: int) -> str:
        return (
            f"{cls.LLM_INSTRUCTION}\n\n"
            f"Fragmento #{index + 1}:\n<<<\n{fragment}\n>>>\n"
            "Devuelve solo el JSON.\n"
        ).strip()

    @staticmethod
    def _parse_llm_payload(raw_text: str) -> list[dict]:
        candidate = PlanParserService._extract_json_candidate(raw_text)
        if not candidate:
            return []
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            possible_lists: Sequence[str] = ("items", "plan_items", "data")
            for key in possible_lists:
                if isinstance(data.get(key), list):
                    return [item for item in data[key] if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_json_candidate(text: str) -> str | None:
        if not text:
            return None
        start = text.find("[")
        alt_start = text.find("{")
        if start == -1 and alt_start != -1:
            start = alt_start
        elif start != -1 and alt_start != -1:
            start = min(start, alt_start)
        if start == -1:
            return None
        end_curly = text.rfind("}")
        end_bracket = text.rfind("]")
        end = max(end_curly, end_bracket)
        if end == -1 or end <= start:
            return None
        return text[start : end + 1]

    @staticmethod
    def _coerce_grade(value) -> str | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return str(int(value))
        value = str(value).strip()
        return value or None

    @staticmethod
    def _merge_metadata(payload: dict, fragment_index: int) -> dict:
        user_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        class_ideas_raw = payload.get("class_ideas") or payload.get("ideas") or payload.get("actividades")
        if isinstance(class_ideas_raw, str):
            class_ideas = [
                line.strip("•- ").strip()
                for line in class_ideas_raw.splitlines()
                if line.strip()
            ]
        elif isinstance(class_ideas_raw, list):
            class_ideas = [str(item).strip() for item in class_ideas_raw if str(item).strip()]
        else:
            class_ideas = []

        metadata = {
            **user_metadata,
            "fragment_index": fragment_index,
            "source": "llm_plan_parser",
        }
        if class_ideas:
            metadata["class_ideas"] = class_ideas
        title = payload.get("title") or payload.get("titulo") or payload.get("nombre")
        if title:
            metadata["title"] = str(title).strip()
        period = payload.get("period") or payload.get("periodo")
        if period:
            metadata["period"] = str(period).strip()
        return metadata
