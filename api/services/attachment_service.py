# api/services/attachment_service.py

from __future__ import annotations

from typing import Mapping, Sequence

from extensions import db
from models import Attachment


class AttachmentService:
    """
    Servicio centralizado para registrar metadatos de archivos adjuntos.
    Los archivos reales viven en almacenamiento externo; aquí solo guardamos referencias.
    """

    @staticmethod
    def create_attachment(
        *,
        context_type: str,
        context_id: int,
        filename: str,
        storage_path: str,
        kind: str = "generic",
        mime_type: str | None = None,
        file_size: int | None = None,
        uploaded_by_profile_id: int | None = None,
        visibility: str | None = None,
        commit: bool = False,
    ) -> Attachment:
        attachment = Attachment(
            context_type=context_type,
            context_id=context_id,
            kind=kind,
            filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            uploaded_by_profile_id=uploaded_by_profile_id,
            visibility=visibility,
        )

        db.session.add(attachment)
        if commit:
            db.session.commit()

        return attachment

    @staticmethod
    def bulk_create_from_payloads(
        *,
        context_type: str,
        context_id: int,
        payloads: Sequence[Mapping] | None,
        uploaded_by_profile_id: int | None = None,
        default_kind: str = "generic",
        commit: bool = False,
    ) -> list[Attachment]:
        created: list[Attachment] = []

        if not payloads:
            return created

        for payload in payloads:
            data = dict(payload or {})
            filename = (data.get("filename") or "").strip()
            storage_path = (data.get("storage_path") or "").strip()

            if not filename or not storage_path:
                # Ignoramos payloads incompletos para no romper el flujo.
                continue

            attachment = Attachment(
                context_type=context_type,
                context_id=context_id,
                kind=(data.get("kind") or default_kind),
                filename=filename,
                storage_path=storage_path,
                mime_type=data.get("mime_type"),
                file_size=data.get("file_size"),
                uploaded_by_profile_id=uploaded_by_profile_id,
                visibility=data.get("visibility"),
            )
            db.session.add(attachment)
            created.append(attachment)

        if commit and created:
            db.session.commit()

        return created
