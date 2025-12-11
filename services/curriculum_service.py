from __future__ import annotations
import json
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from flask import current_app

from extensions import db
from models import (
    CurriculumDocument,
    CurriculumSegment,
    Grade,
    StudyPlan,
    CurriculumPrompt,
    CurriculumGradeAlias,
    CurriculumAreaKeyword,
)
from services.ai_client import AIClient

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - fallback only when dependency missing
    PdfReader = None


class CurriculumService:
    PROMPT_CONTEXT = "curriculum_parser"
    DEFAULT_PROMPT = (
        "Analiza el documento curricular sin asumir un formato fijo. Detecta grados/cursos, materias/áreas "
        "y objetivos de aprendizaje (competencias, propósitos o resultados esperados) usando títulos y secciones "
        "del texto sin inventar información. Devuelve JSON con jerarquía grado → materia → objetivos."
    )

    @staticmethod
    def clear_caches():
        CurriculumService._grade_alias_map.cache_clear()
        CurriculumService._area_keyword_list.cache_clear()
        CurriculumService._prompt_text.cache_clear()

    @staticmethod
    def normalize_grade_label(raw: str | None, institution_id: int | None = None) -> str | None:
        if not raw:
            return None
        lowered = raw.lower().strip()
        lowered = lowered.replace("°", "").replace("º", "").replace("er", "").strip()
        alias_map = CurriculumService._grade_alias_map(institution_id)
        for key, label in alias_map.items():
            if key in lowered.split():
                return label
        digits = re.findall(r"\d+", lowered)
        if digits:
            return digits[0]
        return None

    @staticmethod
    @lru_cache(maxsize=128)
    def _grade_alias_map(institution_id: int | None) -> dict[str, str]:
        entries: dict[str, str] = {}
        global_rows = CurriculumGradeAlias.query.filter(
            CurriculumGradeAlias.institution_id.is_(None)
        ).all()
        for row in global_rows:
            entries[row.alias.lower()] = row.normalized_value
        if institution_id:
            inst_rows = CurriculumGradeAlias.query.filter_by(institution_id=institution_id).all()
            for row in inst_rows:
                entries[row.alias.lower()] = row.normalized_value
        return entries

    @staticmethod
    @lru_cache(maxsize=128)
    def _area_keyword_list(institution_id: int | None) -> list[tuple[str, str]]:
        patterns: list[tuple[str, str]] = []
        global_rows = CurriculumAreaKeyword.query.filter(
            CurriculumAreaKeyword.institution_id.is_(None)
        ).all()
        patterns.extend((row.label, row.pattern) for row in global_rows)
        if institution_id:
            inst_rows = CurriculumAreaKeyword.query.filter_by(institution_id=institution_id).all()
            patterns.extend((row.label, row.pattern) for row in inst_rows)
        return patterns

    @staticmethod
    @lru_cache(maxsize=128)
    def _prompt_text(context: str, institution_id: int | None) -> str:
        query = CurriculumPrompt.query.filter(
            CurriculumPrompt.context == context,
            CurriculumPrompt.is_active.is_(True),
        )
        if institution_id:
            prompt = query.filter(CurriculumPrompt.institution_id == institution_id).order_by(
                CurriculumPrompt.updated_at.desc().nullslast()
            ).first()
            if prompt:
                return prompt.prompt_text
        prompt = query.filter(CurriculumPrompt.institution_id.is_(None)).order_by(
            CurriculumPrompt.updated_at.desc().nullslast()
        ).first()
        if prompt:
            return prompt.prompt_text
        return CurriculumService.DEFAULT_PROMPT

    # -----------------------
    # INGEST
    # -----------------------

    @staticmethod
    def ingest_from_text(
        *,
        profile,
        title: str,
        raw_text: str,
        jurisdiction: str | None = None,
        year: int | None = None,
        grade_min: str | None = None,
        grade_max: str | None = None,
    ) -> CurriculumDocument:
        document = CurriculumDocument(
            institution_id=profile.institution_id,
            uploaded_by_profile_id=profile.id,
            title=title.strip() or "Currículum",
            jurisdiction=(jurisdiction or "").strip() or None,
            year=year,
            raw_text=raw_text,
            status="processing",
            grade_min=grade_min,
            grade_max=grade_max,
        )
        db.session.add(document)
        db.session.flush()

        try:
            segments = CurriculumService._segment_text(raw_text, profile.institution_id)
            for payload in segments:
                segment = CurriculumSegment(
                    document_id=document.id,
                    grade_label=payload.grade_label,
                    area=payload.area,
                    section_title=payload.section_title,
                    content_text=payload.content_text,
                    start_line=payload.start_line,
                    end_line=payload.end_line,
                )
                db.session.add(segment)
            document.segment_count = len(segments)
            document.status = "ready"
        except Exception as exc:
            current_app.logger.exception("No se pudo procesar el currículum: %s", exc)
            document.status = "error"
            document.error_message = str(exc)

        db.session.commit()
        return document

    @staticmethod
    def ingest_from_file(
        *,
        profile,
        file_storage,
        title: str,
        jurisdiction: str | None = None,
        year: int | None = None,
        grade_min: str | None = None,
        grade_max: str | None = None,
    ) -> CurriculumDocument:
        filename = file_storage.filename or "curriculum"
        safe_name = re.sub(r"[^\w._-]", "_", filename)
        tmp_suffix = Path(safe_name).suffix or ".tmp"
        mime_type = file_storage.mimetype or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=tmp_suffix) as tmp_file:
            file_storage.save(tmp_file)
            tmp_path = Path(tmp_file.name)
        try:
            text = CurriculumService._extract_text_from_file(tmp_path, mime_type)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                current_app.logger.warning("No pudimos borrar el archivo temporal %s", tmp_path)

        document = CurriculumDocument(
            institution_id=profile.institution_id,
            uploaded_by_profile_id=profile.id,
            title=title.strip() or safe_name,
            jurisdiction=(jurisdiction or "").strip() or None,
            year=year,
            source_filename=filename,
            storage_path=None,
            mime_type=mime_type,
            raw_text=text,
            status="processing",
            grade_min=grade_min,
            grade_max=grade_max,
        )
        db.session.add(document)
        db.session.flush()

        try:
            segments = CurriculumService._segment_text(text, profile.institution_id)
            for payload in segments:
                segment = CurriculumSegment(
                    document_id=document.id,
                    grade_label=payload.grade_label,
                    area=payload.area,
                    section_title=payload.section_title,
                    content_text=payload.content_text,
                    start_line=payload.start_line,
                    end_line=payload.end_line,
                )
                db.session.add(segment)
            document.segment_count = len(segments)
            document.status = "ready"
        except Exception as exc:
            current_app.logger.exception("No se pudo procesar el archivo curricular: %s", exc)
            document.status = "error"
            document.error_message = str(exc)

        db.session.commit()
        return document
    @staticmethod
    def delete_document(document):
        if not document:
            return
        db.session.delete(document)
        db.session.flush()

    # -----------------------
    # QUERIES
    # -----------------------

    @staticmethod
    def documents_for_institution(institution_id: int) -> list[CurriculumDocument]:
        return (
            CurriculumDocument.query.filter(
                (CurriculumDocument.institution_id == institution_id)
                | (CurriculumDocument.institution_id.is_(None))
            )
            .order_by(CurriculumDocument.created_at.desc())
            .all()
        )

    @staticmethod
    def segments_for_grade(
        *,
        documents: Sequence[CurriculumDocument],
        grade_label: str | None,
        limit_per_doc: int | None = None,
        fallback_to_general: bool = True,
    ) -> list[CurriculumSegment]:
        doc_ids = [doc.id for doc in documents if doc.status == "ready"]
        if not doc_ids:
            return []

        base_query = CurriculumSegment.query.filter(
            CurriculumSegment.document_id.in_(doc_ids)
        )
        order_columns = (
            CurriculumSegment.document_id.asc(),
            CurriculumSegment.area.asc().nullslast(),
            CurriculumSegment.start_line.asc().nullslast(),
        )

        def _apply_limit(rows: list[CurriculumSegment]) -> list[CurriculumSegment]:
            if not limit_per_doc:
                return rows
            trimmed: list[CurriculumSegment] = []
            per_doc: dict[int, int] = {}
            for seg in rows:
                count = per_doc.get(seg.document_id, 0)
                if count >= limit_per_doc:
                    continue
                trimmed.append(seg)
                per_doc[seg.document_id] = count + 1
            return trimmed

        def _fetch(query):
            rows = query.order_by(*order_columns).all()
            return _apply_limit(rows)

        if grade_label:
            specific = _fetch(
                base_query.filter(CurriculumSegment.grade_label == grade_label)
            )
            if specific:
                return specific

        if fallback_to_general:
            general = _fetch(
                base_query.filter(CurriculumSegment.grade_label.is_(None))
            )
            if general:
                return general

        return _fetch(base_query)

    # -----------------------
    # AI ASSIST
    # -----------------------

    @staticmethod
    def build_plan_enrichment(
        *,
        plan: StudyPlan,
        grade: Grade,
        segments: Sequence[CurriculumSegment],
        include_objectives: bool = False,
    ) -> dict:
        if not segments:
            return {}
        grade_label = grade.name or f"{grade.id}"
        plan_name = plan.name

        summarized_segments = []
        for seg in segments[:8]:
            text = seg.content_text.strip()
            summarized_segments.append(
                {
                    "area": seg.area or "General",
                    "excerpt": text[:1200],
                }
            )

        prompt = (
            "Eres un asesor curricular. Redacta un resumen del plan de estudios para el grado indicado, "
            "usando exclusivamente la información provista en los segmentos.\n"
            f"Grado: {grade_label}\n"
            f"Plan: {plan_name}\n"
            "Incluye un párrafo que describa los ejes prioritarios y otra nota con sugerencias."
        )
        context = {"segments": summarized_segments}
        client = AIClient()
        ai_result = client.generate(prompt=prompt, context=context)

        objectives = []
        if include_objectives:
            grouped: dict[str, list[str]] = {}
            for seg in segments:
                grouped.setdefault(seg.area or "Contenidos", []).append(seg.content_text.strip())
            for area, texts in grouped.items():
                snippet = " ".join(texts)[:800]
                objectives.append(
                    {
                        "title": f"{area} · {grade_label}",
                        "description": snippet,
                    }
                )

        return {
            "description": ai_result.get("text"),
            "objectives": objectives,
        }

    # -----------------------
    # HELPERS
    # -----------------------

    @staticmethod
    def _extract_text_from_file(path: Path, mime_type: str) -> str:
        lower = path.suffix.lower()
        if lower == ".pdf" or "pdf" in mime_type:
            return CurriculumService._extract_pdf_text(path)
        if lower in {".txt", ".text"} or "text" in mime_type:
            return path.read_text(encoding="utf-8", errors="ignore")
        raise ValueError("Formato de archivo no soportado. Usa PDF o TXT.")

    @staticmethod
    def _extract_pdf_text(path: Path) -> str:
        pdftotext_bin = shutil.which("pdftotext")
        if pdftotext_bin:
            result = subprocess.run(
                [pdftotext_bin, str(path), "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.decode("utf-8", errors="ignore")
            current_app.logger.warning(
                "pdftotext falló con código %s: %s",
                result.returncode,
                result.stderr.decode("utf-8", errors="ignore"),
            )
        else:
            current_app.logger.info("pdftotext no está instalado, usamos fallback pypdf.")

        return CurriculumService._extract_pdf_text_pure(path)

    @staticmethod
    def _extract_pdf_text_pure(path: Path) -> str:
        if PdfReader is None:
            raise RuntimeError("Instala 'pdftotext' o el paquete pypdf para leer archivos PDF.")
        try:
            reader = PdfReader(str(path))
            pieces: list[str] = []
            for page in reader.pages:
                text = page.extract_text() or ""
                if text:
                    pieces.append(text)
            content = "\n".join(pieces).strip()
            if not content:
                raise RuntimeError("El PDF no contiene texto legible.")
            return content
        except Exception as exc:
            message = str(exc)
            if "cryptography" in message.lower():
                raise RuntimeError(
                    "No se pudo leer el PDF sin pdftotext: falta la dependencia 'cryptography'. "
                    "Instala 'cryptography>=3.1' o ejecuta 'pip install pypdf[crypto]'."
                ) from exc
            raise RuntimeError(f"No se pudo leer el PDF sin pdftotext: {exc}") from exc

    @staticmethod
    def _segment_text(raw_text: str, institution_id: int | None = None) -> list['SegmentRecord']:
        lines = raw_text.splitlines()
        grade_breaks = []
        grade_regex = re.compile(
            r"^\s*((primer|primero|segundo|tercero|cuarto|quinto|sexto|séptimo|septimo)\s+grado)",
            re.IGNORECASE,
        )
        for idx, line in enumerate(lines):
            line_for_match = CurriculumService._clean_heading_prefix(line)
            match = grade_regex.search(line_for_match)
            if not match:
                continue
            grade_label = CurriculumService.normalize_grade_label(match.group(1), institution_id)
            grade_breaks.append((idx, grade_label, line.strip()))

        segments: list[SegmentRecord] = []
        if not grade_breaks:
            grade_breaks.append((0, None, "General"))

        for i, (start_idx, grade_label, heading) in enumerate(grade_breaks):
            end_idx = grade_breaks[i + 1][0] if i + 1 < len(grade_breaks) else len(lines)
            chunk_lines = lines[start_idx:end_idx]
            chunk_text = "\n".join(chunk_lines).strip()
            if not chunk_text:
                continue
            area_segments = CurriculumService._split_by_area(chunk_lines, start_idx, institution_id)
            if not area_segments:
                segments.append(
                    SegmentRecord(
                        grade_label=grade_label,
                        area="General",
                        section_title=heading,
                        content_text=chunk_text,
                        start_line=start_idx,
                        end_line=end_idx,
                    )
                )
                continue
            for area_title, start_line, end_line in area_segments:
                text = "\n".join(lines[start_line:end_line]).strip()
                if not text:
                    continue
                segments.append(
                    SegmentRecord(
                        grade_label=grade_label,
                        area=area_title,
                        section_title=area_title,
                        content_text=text,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )

        return segments

    @staticmethod
    def _split_by_area(lines: Sequence[str], absolute_start: int, institution_id: int | None) -> list[tuple[str, int, int]]:
        indices: list[tuple[int, str]] = []
        for idx, line in enumerate(lines):
            clean = line.strip()
            if not clean:
                continue
            normalized_line = CurriculumService._clean_heading_prefix(clean)
            if CurriculumService._looks_like_area_heading(normalized_line, institution_id):
                area_name = CurriculumService._normalize_area_name(normalized_line, institution_id)
                if not area_name:
                    area_name = CurriculumService._fallback_area_label(normalized_line)
                if area_name:
                    indices.append((idx, area_name))
        if not indices:
            return []
        segments = []
        for i, (rel_idx, area_name) in enumerate(indices):
            abs_start = absolute_start + rel_idx
            abs_end = absolute_start + (indices[i + 1][0] if i + 1 < len(indices) else len(lines))
            segments.append((area_name, abs_start, abs_end))
        return segments

    @staticmethod
    def _looks_like_area_heading(text: str, institution_id: int | None) -> bool:
        if len(text) < 3 or len(text) > 80:
            return False
        normalized = re.sub(r"[\s\W]+", " ", text).strip()
        if normalized.isupper():
            return True
        for _, pattern in CurriculumService._area_keyword_list(institution_id):
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _normalize_area_name(text: str, institution_id: int | None) -> str | None:
        for label, pattern in CurriculumService._area_keyword_list(institution_id):
            if re.search(pattern, text, re.IGNORECASE):
                return label
        return None

    @staticmethod
    def _fallback_area_label(text: str) -> str | None:
        stripped = text.strip().strip(":.-").strip()
        stripped = re.sub(r"\s+", " ", stripped)
        if len(stripped) < 3:
            return None
        # preserve original casing so admins can verify what heading was parsed
        return stripped[:80]

    @staticmethod
    def _clean_heading_prefix(text: str) -> str:
        """
        Elimina números de página, viñetas y separadores antes de evaluar si la línea representa un grado o un área.
        """
        if not text:
            return ""
        cleaned = re.sub(r"^[\s\d\.\-–—•·]+\s*", "", text)
        return cleaned.strip()

    # -----------------------
    # AI STRUCTURED PARSING
    # -----------------------

    @staticmethod
    def ai_grade_suggestions(*, document: CurriculumDocument, grade: Grade) -> list[dict]:
        structure = CurriculumService._ai_structure_from_document(document)
        if not structure:
            return []

        normalized_grade = CurriculumService.normalize_grade_label(grade.name, grade.institution_id)
        grade_matches = CurriculumService._match_ai_grade(structure, normalized_grade, grade.name)
        if not grade_matches:
            return []

        areas: list[dict] = []
        for subject in grade_matches:
            suggestions = []
            for obj in subject.get("objectives") or []:
                title = obj.get("title") or f"{subject['name']} · objetivo"
                description = obj.get("description") or obj.get("detalle") or ""
                page_hint = obj.get("pages") or obj.get("page") or obj.get("referencia")
                notes = obj.get("notes") or obj.get("notas") or ""
                if page_hint:
                    description = f"[Pág. {page_hint}] {description}".strip()
                if notes:
                    description = f"{description}\nNotas: {notes}".strip()
                class_ideas = obj.get("class_ideas") or obj.get("actividades") or obj.get("ideas")
                if isinstance(class_ideas, str):
                    ideas_list = [line.strip("•- ").strip() for line in class_ideas.split("\n") if line.strip()]
                elif isinstance(class_ideas, list):
                    ideas_list = [str(item).strip() for item in class_ideas if str(item).strip()]
                else:
                    ideas_list = []
                suggestions.append(
                    {
                        "title": title.strip(),
                        "description": description.strip(),
                        "class_ideas": ideas_list,
                    }
                )
            if suggestions:
                areas.append({"area": subject["name"], "suggestions": suggestions})
        return areas

    @staticmethod
    def _ai_structure_from_document(document: CurriculumDocument, *, max_chars: int = 60000) -> list[dict]:
        raw_text = (document.raw_text or "").strip()
        if not raw_text:
            return []
        snippet = raw_text[:max_chars]

        institution = document.institution
        client = AIClient(
            provider_override=institution.ai_provider if institution else None,
            model_override=institution.ai_model if institution else None,
        )
        prompt = CurriculumService._prompt_text(CurriculumService.PROMPT_CONTEXT, document.institution_id)
        context = {
            "document_excerpt": snippet,
            "language_hint": "es",
            "document_title": document.title,
        }

        try:
            ai_result = client.generate(prompt=prompt, context=context)
        except Exception as exc:
            current_app.logger.warning("AI curriculum parsing failed: %s", exc)
            return []

        return CurriculumService._parse_ai_structure(
            ai_result.get("text", ""),
            institution_id=document.institution_id,
        )

    @staticmethod
    def _parse_ai_structure(raw_text: str, institution_id: int | None = None) -> list[dict]:
        if not raw_text:
            return []
        candidate = CurriculumService._extract_json_candidate(raw_text)
        if not candidate:
            return []
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            return []

        if isinstance(data, dict):
            grade_entries = (
                data.get("grades")
                or data.get("grados")
                or data.get("courses")
                or data.get("cursos")
                or []
            )
        elif isinstance(data, list):
            grade_entries = data
        else:
            grade_entries = []

        structured: list[dict] = []
        for entry in grade_entries:
            if not isinstance(entry, dict):
                continue
            grade_name = (entry.get("name") or entry.get("grado") or entry.get("grade") or "").strip()
            if not grade_name:
                continue
            subjects_raw = (
                entry.get("subjects")
                or entry.get("materias")
                or entry.get("areas")
                or entry.get("subjectsAreas")
                or []
            )
            subjects: list[dict] = []
            for subject in subjects_raw:
                if isinstance(subject, str):
                    subject_name = subject.strip()
                    objectives_raw = []
                elif isinstance(subject, dict):
                    subject_name = (
                        subject.get("name")
                        or subject.get("materia")
                        or subject.get("area")
                        or subject.get("subject")
                        or ""
                    ).strip()
                    objectives_raw = (
                        subject.get("objectives")
                        or subject.get("objetivos")
                        or subject.get("competencias")
                        or subject.get("temas")
                        or []
                    )
                else:
                    continue
                if not subject_name:
                    continue
                parsed_objectives = []
                if isinstance(objectives_raw, list):
                    for obj in objectives_raw:
                        if isinstance(obj, str):
                            parsed_objectives.append({"title": obj.strip(), "description": ""})
                        elif isinstance(obj, dict):
                            parsed_objectives.append(
                                {
                                    "title": (obj.get("title") or obj.get("nombre") or obj.get("tema") or "").strip(),
                                    "description": (obj.get("description") or obj.get("detalle") or obj.get("explicacion") or "").strip(),
                                    "pages": (obj.get("pages") or obj.get("pagina") or obj.get("paginas") or obj.get("referencia")),
                                    "notes": obj.get("notes") or obj.get("notas"),
                                    "class_ideas": obj.get("class_ideas") or obj.get("actividades") or obj.get("ideas"),
                                }
                            )
                elif isinstance(objectives_raw, dict):
                    # a dict grouping headings to descriptions
                    for key, value in objectives_raw.items():
                        parsed_objectives.append(
                            {
                                "title": str(key).strip(),
                                "description": str(value).strip(),
                            }
                        )
                subjects.append({"name": subject_name, "objectives": parsed_objectives})
            structured.append(
                {
                    "name": grade_name,
                    "normalized": CurriculumService.normalize_grade_label(grade_name, institution_id),
                    "subjects": subjects,
                }
            )
        return structured

    @staticmethod
    def _match_ai_grade(structure: list[dict], normalized_grade: str | None, grade_name: str) -> list[dict]:
        if not structure:
            return []
        fallback_matches = []
        for entry in structure:
            if normalized_grade and entry.get("normalized") == normalized_grade:
                return entry.get("subjects", [])
            if entry.get("name", "").lower().strip() == grade_name.lower().strip():
                fallback_matches = entry.get("subjects", [])
        return fallback_matches

    @staticmethod
    def _extract_json_candidate(text: str) -> str | None:
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


@dataclass
class SegmentRecord:
    grade_label: str | None
    area: str | None
    section_title: str | None
    content_text: str
    start_line: int | None
    end_line: int | None
