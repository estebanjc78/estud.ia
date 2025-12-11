from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import asc, desc

from models import (
    Lesson,
    Task,
    TaskSubmission,
    Profile,
    RoleEnum,
    BitacoraEntrada,
    Message,
    MessageThreadParticipant,
)


class ViewDataService:
    """
    Servicios de consulta para las vistas HTML.
    Centraliza queries y evita repetir lógica en app.py.
    """

    @staticmethod
    def teacher_dashboard(profile: Profile) -> dict:
        lessons_query = Lesson.query.filter_by(teacher_profile_id=profile.id)
        today = date.today()
        week_limit = today + timedelta(days=7)

        clases_hoy = (
            lessons_query.filter(Lesson.class_date == date.today())
            .order_by(asc(Lesson.start_time))
            .limit(5)
            .all()
        )
        todas_las_clases = lessons_query.order_by(desc(Lesson.class_date)).all()
        lessons_upcoming = (
            lessons_query.filter(Lesson.class_date >= today)
            .order_by(asc(Lesson.class_date), asc(Lesson.start_time))
            .limit(5)
            .all()
        )
        lessons_week = (
            lessons_query.filter(Lesson.class_date.between(today, week_limit)).count()
        )

        tasks = (
            Task.query.join(Lesson)
            .filter(Lesson.teacher_profile_id == profile.id)
            .order_by(asc(Task.due_date))
            .all()
        )
        tasks_upcoming = sorted(
            tasks,
            key=lambda task: ((task.due_date or date.max)),
        )[:5]
        tasks_active = sum(
            1
            for task in tasks
            if task.due_date is None or task.due_date >= today
        )

        submissions = (
            TaskSubmission.query.join(Task)
            .filter(Task.lesson.has(teacher_profile_id=profile.id))
            .order_by(TaskSubmission.submitted_at.desc())
            .limit(10)
            .all()
        )
        submissions_pending = (
            TaskSubmission.query.join(Task)
            .join(Lesson, Lesson.id == Task.lesson_id)
            .filter(
                Lesson.teacher_profile_id == profile.id,
                TaskSubmission.points_awarded.is_(None),
            )
            .count()
        )

        students = (
            Profile.query.filter_by(
                institution_id=profile.institution_id, role=RoleEnum.ALUMNO
            )
            .order_by(Profile.full_name.asc())
            .all()
        )

        bitacora_entries = (
            BitacoraEntrada.query.filter_by(institution_id=profile.institution_id)
            .order_by(BitacoraEntrada.created_at.desc())
            .limit(5)
            .all()
        )

        recent_messages = (
            Message.query.join(
                MessageThreadParticipant,
                MessageThreadParticipant.thread_id == Message.thread_id,
            )
            .filter(MessageThreadParticipant.profile_id == profile.id)
            .distinct()
            .order_by(Message.created_at.desc())
            .limit(5)
            .all()
        )

        overdue_tasks = (
            Task.query.join(Lesson)
            .filter(
                Lesson.teacher_profile_id == profile.id,
                Task.due_date.isnot(None),
                Task.due_date < today,
            )
            .count()
        )
        alerts = []
        if overdue_tasks:
            alerts.append(f"{overdue_tasks} tareas vencidas pendientes de cierre.")
        if submissions_pending:
            alerts.append(f"{submissions_pending} entregas esperan corrección.")
        if not alerts:
            alerts = ["Sin alertas críticas para hoy."]

        return {
            "clases_hoy": clases_hoy,
            "lessons": todas_las_clases,
            "lessons_upcoming": lessons_upcoming,
            "tasks": tasks,
            "tasks_upcoming": tasks_upcoming,
            "submissions": submissions,
            "students": students,
            "bitacora_entries": bitacora_entries,
            "recent_messages": recent_messages,
            "metrics": {
                "lessons_today": len(clases_hoy),
                "lessons_week": lessons_week,
                "tasks_active": tasks_active,
                "pending_reviews": submissions_pending,
            },
            "alerts": alerts,
        }

    @staticmethod
    def student_portal(profile: Profile) -> dict:
        tasks_query = Task.query.filter_by(institution_id=profile.institution_id)
        if profile.section_id:
            tasks_query = tasks_query.filter(
                (Task.section_id == profile.section_id) | (Task.section_id.is_(None))
            )

        tasks = tasks_query.order_by(asc(Task.due_date)).limit(10).all()
        submissions = (
            TaskSubmission.query.filter_by(student_profile_id=profile.id)
            .order_by(TaskSubmission.submitted_at.desc())
            .all()
        )

        bitacora_entries = (
            BitacoraEntrada.query.filter_by(student_profile_id=profile.id)
            .order_by(BitacoraEntrada.created_at.desc())
            .limit(5)
            .all()
        )

        return {
            "tasks": tasks,
            "submissions": submissions,
            "bitacora_entries": bitacora_entries,
        }

    @staticmethod
    def tasks_overview(profile: Profile) -> dict:
        lessons_query = Lesson.query.filter_by(institution_id=profile.institution_id)
        tasks_query = Task.query.filter_by(institution_id=profile.institution_id)

        if profile.role == RoleEnum.PROFESOR:
            lessons_query = lessons_query.filter_by(teacher_profile_id=profile.id)
            tasks_query = tasks_query.join(Lesson).filter(Lesson.teacher_profile_id == profile.id)
        elif profile.role == RoleEnum.ALUMNO and profile.section_id:
            tasks_query = tasks_query.filter(
                (Task.section_id == profile.section_id) | (Task.section_id.is_(None))
            )

        lessons = lessons_query.order_by(desc(Lesson.class_date)).all()
        tasks = tasks_query.order_by(asc(Task.due_date)).all()

        can_create = profile.role in (
            RoleEnum.PROFESOR,
            getattr(RoleEnum, "ADMIN", RoleEnum.PROFESOR),
            getattr(RoleEnum, "ADMIN_COLEGIO", RoleEnum.PROFESOR),
            getattr(RoleEnum, "RECTOR", RoleEnum.PROFESOR),
            getattr(RoleEnum, "PSICOPEDAGOGIA", RoleEnum.PROFESOR),
        )

        return {
            "lessons": lessons,
            "tasks": tasks,
            "can_create_tasks": can_create,
        }

    @staticmethod
    def psico_dashboard(profile: Profile) -> dict:
        students = (
            Profile.query.filter_by(institution_id=profile.institution_id, role=RoleEnum.ALUMNO)
            .order_by(Profile.full_name.asc())
            .all()
        )

        student_cards = []
        for student in students:
            submissions = (
                TaskSubmission.query.filter_by(student_profile_id=student.id)
                .order_by(TaskSubmission.submitted_at.desc())
                .limit(3)
                .all()
            )
            all_submissions = TaskSubmission.query.filter_by(student_profile_id=student.id).all()
            bitacora_entries = (
                BitacoraEntrada.query.filter_by(student_profile_id=student.id)
                .order_by(BitacoraEntrada.created_at.desc())
                .limit(3)
                .all()
            )

            section_tasks = (
                Task.query.filter_by(institution_id=profile.institution_id)
                .filter((Task.section_id == student.section_id) | (Task.section_id.is_(None)))
                .all()
            )
            submitted_task_ids = {s.task_id for s in all_submissions}
            pending_tasks = len([t for t in section_tasks if t.id not in submitted_task_ids])

            student_cards.append(
                {
                    "profile": student,
                    "submissions": submissions,
                    "bitacora_entries": bitacora_entries,
                    "last_submission": submissions[0] if submissions else None,
                    "last_bitacora": bitacora_entries[0] if bitacora_entries else None,
                    "pending_tasks": pending_tasks,
                }
            )

        return {"students": student_cards, "student_choices": students}
