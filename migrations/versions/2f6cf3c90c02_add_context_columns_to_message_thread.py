"""add context columns to message_thread

Revision ID: 2f6cf3c90c02
Revises: 1b66e5e2991b
Create Date: 2025-11-30 12:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '2f6cf3c90c02'
down_revision = '1b66e5e2991b'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    table_names = inspector.get_table_names()
    if "message_context" in table_names:
        op.drop_table("message_context")

    if "message_thread" in table_names:
        columns = [col["name"] for col in inspector.get_columns("message_thread")]
        if "context_type" not in columns:
            op.add_column(
                "message_thread",
                sa.Column("context_type", sa.String(length=50), nullable=True),
            )
        if "context_id" not in columns:
            op.add_column(
                "message_thread",
                sa.Column("context_id", sa.Integer(), nullable=True),
            )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = inspector.get_columns("message_thread")
    column_names = [col["name"] for col in columns]

    if "context_type" in column_names:
        op.drop_column("message_thread", "context_type")
    if "context_id" in column_names:
        op.drop_column("message_thread", "context_id")

    op.create_table(
        "message_context",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column(
            "context_type",
            sa.Enum(
                "ALUMNO",
                "TAREA",
                "LECCION",
                "BITACORA",
                "INSIGHT",
                name="message_context_type",
            ),
            nullable=False,
        ),
        sa.Column("context_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["message_thread.id"]),
    )
