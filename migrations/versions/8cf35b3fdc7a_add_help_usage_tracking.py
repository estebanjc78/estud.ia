"""add help usage tracking

Revision ID: 8cf35b3fdc7a
Revises: 7b1a2c4a8f1b
Create Date: 2025-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8cf35b3fdc7a"
down_revision = "7b1a2c4a8f1b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_help_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institution.id"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("task.id"), nullable=False),
        sa.Column("student_profile_id", sa.Integer(), sa.ForeignKey("profile.id"), nullable=False),
        sa.Column("count_baja", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("count_media", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("count_alta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("learning_style", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("task_id", "student_profile_id", name="uq_task_help_usage"),
    )
    op.add_column("task_submission", sa.Column("help_breakdown", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("task_submission", "help_breakdown")
    op.drop_table("task_help_usage")
