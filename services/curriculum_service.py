from __future__ import annotations
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from flask import current_app

from extensions import db
from models import CurriculumDocument, CurriculumSegment, Grade, StudyPlan
from services.ai_client import AIClient


class CurriculumService:
    GRADE_MAP = {
        "primero": "1",
        "primer": "1",
        "1": "1",
        "segundo": "2",
        "2": "2",
        "tercero": "3",
        "3": "3",
        "cuarto": "4",
        "4": "4",
        "quinto": "5",
        "5": "5",
        "sexto": "6",
        "6": "6",
        "séptimo": "7",
        "septimo": "7",
        "7": "7",
    }

    AREA_KEYWORDS = {
        "Prácticas del Lenguaje": r"pr[aá]cticas?\s+del\s+lenguaje",
        "Matemática": r"matem[aá]tica",
        "Ciencias Naturales": r"ciencias?\s+naturales?",
        "Ciencias Sociales": r"ciencias?\s+sociales?",
        "Educación Física": r"educaci[oó]n\s+f[ií]sica",
        "Educación Tecnológica": r"educaci[oó]n\s+tecnol[oó]gica",
        "Formación Ética y Ciudadana": r"formaci[oó]n\s+[eé]tica\s+y\s+ciudadana",
        "Informática": r"inform[aá]tica",
        "Artes": r"artes?",
        "Música": r"m[uú]sica",
        "Plástica": r"pl[aá]stica",
        "Teatro": r"teatro",
    }

    STORAGE_DIR = "curricula"

    @staticmethod
    def normalize_grade_label(raw: str | None) -> str | None:
        if not raw:
            return None
        lowered = raw.lower().strip()
        lowered = lowered.replace("°", "").replace("º", "").replace("er", "").strip()
        for key, label in CurriculumService.GRADE_MAP.items():
            if key in lowered.split():
                return label
        digits = re.findall(r"\d+", lowered)
        if digits:
            return digits[0]
        return None

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
            segments = CurriculumService._segment_text(raw_text)
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
        storage_dir = Path(current_app.instance_path) / CurriculumService.STORAGE_DIR
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_path = storage_dir / safe_name
        file_storage.save(storage_path)

        mime_type = file_storage.mimetype or ""
        text = CurriculumService._extract_text_from_file(storage_path, mime_type)

        document = CurriculumDocument(
            institution_id=profile.institution_id,
            uploaded_by_profile_id=profile.id,
            title=title.strip() or safe_name,
            jurisdiction=(jurisdiction or "").strip() or None,
            year=year,
            source_filename=filename,
            storage_path=str(storage_path),
            mime_type=mime_type,
            raw_text=text,
            status="processing",
            grade_min=grade_min,
            grade_max=grade_max,
        )
        db.session.add(document)
        db.session.flush()

        try:
            segments = CurriculumService._segment_text(text)
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
        grade_label: str,
        limit_per_doc: int | None = None,
    ) -> list[CurriculumSegment]:
        doc_ids = [doc.id for doc in documents if doc.status == "ready"]
        if not doc_ids:
            return []
        query = CurriculumSegment.query.filter(
            CurriculumSegment.document_id.in_(doc_ids),
            CurriculumSegment.grade_label == grade_label,
        ).order_by(CurriculumSegment.document_id.asc(), CurriculumSegment.area.asc().nullslast())
        segments = query.all()
        if limit_per_doc:
            trimmed = []
            per_doc = {}
            for seg in segments:
                per_doc.setdefault(seg.document_id, 0)
                if per_doc[seg.document_id] >= limit_per_doc:
                    continue
                trimmed.append(seg)
                per_doc[seg.document_id] += 1
            return trimmed
        return segments

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
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"No se pudo leer el PDF: {result.stderr.decode('utf-8', errors='ignore')}")
        return result.stdout.decode("utf-8", errors="ignore")

    @staticmethod
    def _segment_text(raw_text: str) -> list['SegmentRecord']:
        lines = raw_text.splitlines()
        grade_breaks = []
        grade_regex = re.compile(
            r"^\s*((primer|primero|segundo|tercero|cuarto|quinto|sexto|séptimo|septimo)\s+grado)",
            re.IGNORECASE,
        )
        for idx, line in enumerate(lines):
            match = grade_regex.search(line)
            if not match:
                continue
            grade_label = CurriculumService.normalize_grade_label(match.group(1))
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
            area_segments = CurriculumService._split_by_area(chunk_lines, start_idx)
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
    def _split_by_area(lines: Sequence[str], absolute_start: int) -> list[tuple[str, int, int]]:
        indices: list[tuple[int, str]] = []
        for idx, line in enumerate(lines):
            clean = line.strip()
            if not clean:
                continue
            if CurriculumService._looks_like_area_heading(clean):
                area_name = CurriculumService._normalize_area_name(clean)
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
    def _looks_like_area_heading(text: str) -> bool:
        if len(text) < 3 or len(text) > 80:
            return False
        normalized = re.sub(r"[\s\W]+", " ", text).strip()
        if normalized.isupper():
            return True
        for pattern in CurriculumService.AREA_KEYWORDS.values():
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _normalize_area_name(text: str) -> str:
        for label, pattern in CurriculumService.AREA_KEYWORDS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return label
        return text.title()


@dataclass
class SegmentRecord:
    grade_label: str | None
    area: str | None
    section_title: str | None
    content_text: str
    start_line: int | None
    end_line: int | None
