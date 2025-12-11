# models/__init__.py
from .roles import RoleEnum
from .institution import Institution, Grade, Section
from .user import User, Profile
from .bitacora import BitacoraEntrada, BitacoraCategoria
from .lesson import Lesson
from .messages import Message, MessageThread, MessageThreadParticipant
from .study_plan import StudyPlan, Objective
from .plan import Plan, PlanItem, PlanDocument
from .task import Task
from .attachment import Attachment
from .task_submission import (
    TaskSubmission,
    SubmissionEvidence,
    EvidenceTypeEnum,
)
from .insight_report import InsightReport, ReportScope
from .help_usage import TaskHelpUsage
from .curriculum import CurriculumDocument, CurriculumSegment
from .curriculum_config import (
    CurriculumPrompt,
    CurriculumGradeAlias,
    CurriculumAreaKeyword,
)
from .platform_theme import PlatformTheme

__all__ = [
    "RoleEnum",
    "Institution",
    "Grade",
    "Section",
    "User",
    "Profile",
    "BitacoraEntrada",
    "BitacoraCategoria",
    "Lesson",
    "Attachment",
    "Message",
    "MessageThread",
    "MessageThreadParticipant",
    "StudyPlan",
    "Plan",
    "PlanDocument",
    "PlanItem",
    "Objective",
    "Task",
    "TaskSubmission",
    "SubmissionEvidence",
    "EvidenceTypeEnum",
    "InsightReport",
    "ReportScope",
    "TaskHelpUsage",
    "CurriculumDocument",
    "CurriculumSegment",
    "PlatformTheme",
    "CurriculumPrompt",
    "CurriculumGradeAlias",
    "CurriculumAreaKeyword",
]
