"""align message table with current models

Revision ID: 3c9ad3ccfbd1
Revises: 2f6cf3c90c02
Create Date: 2025-11-30 12:33:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = '3c9ad3ccfbd1'
down_revision = '2f6cf3c90c02'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if "message" not in inspector.get_table_names():
        return

    columns = [col["name"] for col in inspector.get_columns("message")]
    if "sender_profile_id" in columns and "text" in columns:
        # Already aligned
        return

    op.create_table(
        "message_tmp",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("message_thread.id"), nullable=False),
        sa.Column("sender_profile_id", sa.Integer(), sa.ForeignKey("profile.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("visible_for_student", sa.Boolean(), default=True),
        sa.Column("visible_for_parent", sa.Boolean(), default=True),
        sa.Column("visible_for_teacher", sa.Boolean(), default=True),
    )

    insert_stmt = text(
        """
        INSERT INTO message_tmp (id, thread_id, sender_profile_id, text, created_at,
                                 visible_for_student, visible_for_parent, visible_for_teacher)
        SELECT id,
               thread_id,
               author_profile_id,
               COALESCE(body, ''),
               created_at,
               1,
               1,
               1
        FROM message
        """
    )
    bind.execute(insert_stmt)

    op.drop_table("message")
    op.rename_table("message_tmp", "message")


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if "message" not in inspector.get_table_names():
        return

    columns = [col["name"] for col in inspector.get_columns("message")]
    if "author_profile_id" in columns:
        return

    op.create_table(
        "message_old",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("message_thread.id"), nullable=False),
        sa.Column("author_profile_id", sa.Integer(), sa.ForeignKey("profile.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("is_system", sa.Boolean(), default=False),
    )

    insert_stmt = text(
        """
        INSERT INTO message_old (id, thread_id, author_profile_id, body, created_at)
        SELECT id,
               thread_id,
               sender_profile_id,
               text,
               created_at
        FROM message
        """
    )
    bind.execute(insert_stmt)

    op.drop_table("message")
    op.rename_table("message_old", "message")
