from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from models import (
    Task,
    TaskSubmission,
    Profile,
    Lesson,
    BitacoraEntrada,
    RoleEnum,
    ReportScope,
)


class InsightsService:
    """
    Genera métricas para dashboards y prepara los contextos que alimentan los reportes con IA.
    """

    # -------------------------
    # DASHBOARD METRICS
    # -------------------------

    @staticmethod
    def collect_for_profile(profile: Profile) -> dict:
        """
        Devuelve KPIs contextualizados según el rol:
          - Profesor: solo sus clases/alumnos.
          - Staff/Admin: toda la institución.
        """
        tasks_query = Task.query.filter_by(institution_id=profile.institution_id)
        submissions_query = TaskSubmission.query.join(Task).filter(
            Task.institution_id == profile.institution_id
        )
        lessons_query = Lesson.query.filter_by(institution_id=profile.institution_id)

        if profile.role == RoleEnum.PROFESOR:
            tasks_query = tasks_query.join(Lesson).filter(
                Lesson.teacher_profile_id == profile.id
            )
            submissions_query = submissions_query.filter(
                Task.lesson.has(teacher_profile_id=profile.id)
            )
            lessons_query = lessons_query.filter_by(teacher_profile_id=profile.id)

        tasks_total = tasks_query.count()
        submissions = submissions_query.all()
        submissions_total = len(submissions)

        avg_points = None
        if submissions_total:
            total_points = sum(s.points_awarded or 0 for s in submissions)
            avg_points = round(total_points / submissions_total, 1)

        help_usage = {"BAJA": 0, "MEDIA": 0, "ALTA": 0}
        student_stats: dict[int, dict] = {}
        for submission in submissions:
            help_used = InsightsService._record_help_usage(help_usage, submission)
            stats = student_stats.setdefault(
                submission.student_profile_id,
                {
                    "profile": submission.student,
                    "submissions": 0,
                    "points": 0,
                    "help_count": 0,
                },
            )
            stats["submissions"] += 1
            stats["points"] += submission.points_awarded or 0
            stats["help_count"] += help_used

        for data in student_stats.values():
            data["avg_points"] = (
                round(data["points"] / data["submissions"], 1)
                if data["submissions"]
                else None
            )

        students_flagged = sorted(
            student_stats.values(),
            key=lambda item: (item["avg_points"] or 0, -item["help_count"]),
        )[:5]
        for item in students_flagged:
            suggestions = []
            if (item["avg_points"] or 0) < 70:
                suggestions.append("Reforzar contenidos base")
            if item["help_count"] >= 3:
                suggestions.append("Revisar estrategias de ayuda personalizadas")
            if not suggestions:
                suggestions.append("Monitorear evolución")
            item["suggestions"] = suggestions

        bitacora_summary = InsightsService._bitacora_trends(profile)

        metrics = {
            "tasks_total": tasks_total,
            "submissions_total": submissions_total,
            "average_points": avg_points,
            "help_usage": help_usage,
            "students_flagged": students_flagged,
            "bitacora_summary": bitacora_summary,
            "lessons_upcoming": lessons_query.order_by(
                Lesson.class_date.asc()
            ).limit(5).all(),
        }
        metrics["ai_payload"] = InsightsService._build_ai_payload(profile, metrics)
        return metrics

    @staticmethod
    def generate_ai_brief(metrics: dict) -> str:
        """
        Resumen heurístico (se muestra mientras se genera un texto con IA real).
        """
        parts: list[str] = []
        avg_points = metrics.get("average_points")
        if avg_points is not None:
            if avg_points >= 85:
                parts.append(
                    f"Los puntajes promedian {avg_points} pts: el curso mantiene un muy buen rendimiento."
                )
            elif avg_points >= 70:
                parts.append(
                    f"El promedio es de {avg_points} pts; conviene reforzar a los alumnos con más ayudas."
                )
            else:
                parts.append(
                    f"Promedio general {avg_points} pts: activar plan de repaso antes de la próxima evaluación."
                )

        help_usage = metrics.get("help_usage") or {}
        most_used_help = (
            max(help_usage.items(), key=lambda item: item[1])[0] if help_usage else None
        )
        if most_used_help and help_usage.get(most_used_help):
            parts.append(
                f"Las ayudas más utilizadas fueron de nivel {most_used_help.lower()}, con {help_usage[most_used_help]} solicitudes."
            )

        flagged = metrics.get("students_flagged") or []
        if flagged:
            nombres = ", ".join(
                (item["profile"].full_name if item["profile"] else "Alumno")
                for item in flagged[:3]
            )
            parts.append(
                f"Recomendamos seguimiento personalizado para: {nombres}."
            )

        if not parts:
            parts.append("No hay alertas relevantes; seguí monitoreando el progreso semanal.")

        return " ".join(parts)

    # -------------------------
    # REPORT CONTEXTS
    # -------------------------

    @staticmethod
    def build_report_context(profile: Profile, scope: ReportScope, target_id: int | None) -> tuple[dict, str | None]:
        tasks_query = Task.query.filter_by(institution_id=profile.institution_id)
        submissions_query = TaskSubmission.query.join(Task).filter(
            Task.institution_id == profile.institution_id
        )
        bitacora_query = BitacoraEntrada.query.filter_by(institution_id=profile.institution_id)

        target_label = None

        if scope == ReportScope.CLASS:
            lesson = Lesson.query.get(target_id)
            if not lesson or lesson.institution_id != profile.institution_id:
                raise ValueError("La clase seleccionada no existe o no pertenece a tu institución.")
            tasks_query = tasks_query.filter_by(lesson_id=lesson.id)
            submissions_query = submissions_query.filter(Task.lesson_id == lesson.id)
            bitacora_query = bitacora_query.filter(BitacoraEntrada.lesson_id == lesson.id)
            target_label = f"{lesson.title} ({lesson.class_date})"
        elif scope == ReportScope.STUDENT:
            student = Profile.query.get(target_id)
            if not student or student.institution_id != profile.institution_id:
                raise ValueError("El alumno seleccionado no existe en tu institución.")
            submissions_query = submissions_query.filter(
                TaskSubmission.student_profile_id == student.id
            )
            bitacora_query = bitacora_query.filter(BitacoraEntrada.student_profile_id == student.id)
            tasks_query = tasks_query.join(Task.submissions).filter(
                TaskSubmission.student_profile_id == student.id
            )
            target_label = student.full_name
        else:
            # Global: si es profesor, sólo sus grupos
            if profile.role == RoleEnum.PROFESOR:
                tasks_query = tasks_query.join(Task.lesson).filter(
                    Lesson.teacher_profile_id == profile.id
                )
                submissions_query = submissions_query.filter(
                    Task.lesson.has(teacher_profile_id=profile.id)
                )
            target_label = profile.institution.name if profile.institution else "Institución"

        tasks = tasks_query.all()
        submissions = submissions_query.all()
        approvals, approval_rate = InsightsService._approvals_stats(submissions)
        late_submissions = InsightsService._late_submissions(submissions)
        no_help_rate = InsightsService._no_help_rate(submissions)

        highlights = InsightsService._highlights(tasks, submissions, approvals, approval_rate, no_help_rate)
        followups = InsightsService._psy_followups(bitacora_query.all())

        context = {
            "scope": scope.value,
            "target_id": target_id,
            "metrics": {
                "tasks_total": len(tasks),
                "approvals": approvals,
                "approval_rate": approval_rate,
                "late_submissions": late_submissions,
            },
            "learning": {
                "no_help_rate": no_help_rate,
                "actions": InsightsService._recommended_actions(approval_rate, no_help_rate, followups),
            },
            "highlights": highlights,
            "followups": followups,
        }
        return context, target_label

    # -------------------------
    # HELPERS
    # -------------------------

    @staticmethod
    def _approvals_stats(submissions):
        if not submissions:
            return 0, 0
        approvals = 0
        for submission in submissions:
            task = submission.task
            max_points = submission.max_points or (task.max_points if task else 100) or 100
            if (submission.points_awarded or 0) >= 0.7 * max_points:
                approvals += 1
        approval_rate = round((approvals / len(submissions)) * 100, 1) if submissions else 0
        return approvals, approval_rate

    @staticmethod
    def _no_help_rate(submissions):
        if not submissions:
            return 0
        zero_help = len([s for s in submissions if (s.help_count or 0) == 0])
        return round((zero_help / len(submissions)) * 100, 1)

    @staticmethod
    def _late_submissions(submissions):
        count = 0
        for submission in submissions:
            task = submission.task
            if task and task.due_date and submission.submitted_at:
                if submission.submitted_at.date() > task.due_date:
                    count += 1
        return count

    @staticmethod
    def _highlights(tasks, submissions, approvals, approval_rate, no_help_rate):
        lines = []
        if tasks:
            lines.append(f"Se analizaron {len(tasks)} tareas.")
        if approvals:
            lines.append(f"{approvals} entregas alcanzaron la nota mínima. Tasa: {approval_rate}%.")
        if submissions:
            lines.append(f"{no_help_rate}% de las entregas se realizaron sin ayudas.")
        if not tasks:
            lines.append("No hay tareas registradas en el período analizado.")
        return lines

    @staticmethod
    def _psy_followups(bitacora_entries):
        followups = []
        for entry in bitacora_entries:
            if entry.author_profile and entry.author_profile.role == RoleEnum.PSICOPEDAGOGIA:
                note = entry.nota or ""
                student = entry.student_profile.full_name if entry.student_profile else "Alumno"
                followups.append(f"{student}: {note[:140]}{'...' if len(note) > 140 else ''}")
        return followups

    @staticmethod
    def _recommended_actions(approval_rate, no_help_rate, followups):
        actions = []
        if approval_rate < 70:
            actions.append("Planificar un refuerzo antes de la próxima evaluación.")
        if no_help_rate < 50:
            actions.append("Reforzar estrategias de estudio autónomo para reducir la dependencia de ayudas.")
        if followups:
            actions.append("Coordinar reunión con psicopedagogía para revisar los casos abiertos.")
        if not actions:
            actions.append("Mantener el acompañamiento actual y monitorear semanalmente.")
        return actions

    @staticmethod
    def _record_help_usage(counter: dict[str, int], submission) -> int:
        """
        Actualiza el contador global de ayudas y devuelve el total utilizado en la entrega.
        Prefiere los datos granulares (help_breakdown) y cae al esquema antiguo si no existe.
        """
        breakdown = submission.help_breakdown or {}
        total = 0
        if isinstance(breakdown, dict) and breakdown:
            for level, raw_value in breakdown.items():
                level_key = (level or "").upper()
                try:
                    value = int(raw_value)
                except (TypeError, ValueError):
                    continue
                if level_key in counter:
                    counter[level_key] += value
                total += value
            if total:
                return total

        level = (submission.help_level or "").upper()
        value = submission.help_count or 0
        if level in counter:
            counter[level] += value
        return value

    @staticmethod
    def _bitacora_trends(profile: Profile) -> list[dict]:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        entries = (
            BitacoraEntrada.query.filter_by(institution_id=profile.institution_id)
            .filter(BitacoraEntrada.created_at >= thirty_days_ago)
            .all()
        )
        counter = Counter(entry.categoria for entry in entries if entry.categoria)
        summary = []
        for categoria, total in counter.most_common(5):
            label = categoria.value if hasattr(categoria, "value") else str(categoria)
            summary.append({"categoria": label, "total": total})
        return summary

    @staticmethod
    def _build_ai_payload(profile: Profile, metrics: dict) -> dict:
        """
        Estructura recomendada para enviar a un modelo de IA.
        """
        students_payload = []
        for item in metrics.get("students_flagged") or []:
            student = item.get("profile")
            students_payload.append(
                {
                    "name": student.full_name if student else "Alumno",
                    "avg_points": item.get("avg_points"),
                    "help_count": item.get("help_count"),
                    "suggestions": item.get("suggestions"),
                }
            )

        return {
            "context": {
                "institution_id": profile.institution_id,
                "profile_id": profile.id,
                "role": profile.role.name if profile.role else None,
            },
            "kpis": {
                "tasks_total": metrics.get("tasks_total"),
                "submissions_total": metrics.get("submissions_total"),
                "average_points": metrics.get("average_points"),
                "help_usage": metrics.get("help_usage"),
            },
            "students_of_interest": students_payload,
            "bitacora_summary": metrics.get("bitacora_summary"),
        }
