"""ORM models package.

Importing this package registers every table on ``Base.metadata`` — alembic
and the test fixtures rely on that (``import smena_api.db.models``).
"""

from smena_api.db.models.assessment import Assessment, AssessmentQuestion
from smena_api.db.models.assignment import Assignment
from smena_api.db.models.lesson_plan import LessonPlan
from smena_api.db.models.material import Material
from smena_api.db.models.report import Report
from smena_api.db.models.report_chat import (
    ReportMessage,
    ReportRoom,
    ReportRoomMember,
)
from smena_api.db.models.safe_passkey import SafePasskey
from smena_api.db.models.template import Template
from smena_api.db.models.uploaded_file import UploadedFile
from smena_api.db.models.user import User

__all__ = [
    "Assessment",
    "AssessmentQuestion",
    "Assignment",
    "LessonPlan",
    "Material",
    "Report",
    "ReportMessage",
    "ReportRoom",
    "ReportRoomMember",
    "SafePasskey",
    "Template",
    "UploadedFile",
    "User",
]
