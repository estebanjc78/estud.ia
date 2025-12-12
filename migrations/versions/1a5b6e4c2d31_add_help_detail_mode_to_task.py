"""add help_detail_mode to task

Revision ID: 1a5b6e4c2d31
Revises: f1b583e26677
Create Date: 2025-01-15 21:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1a5b6e4c2d31"
down_revision = "f1b583e26677"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("task") as batch_op:
        batch_op.add_column(
            sa.Column(
                "help_detail_mode",
                sa.String(length=20),
                nullable=True,
                server_default="GUIADA",
            )
        )

    op.execute("UPDATE task SET help_detail_mode = 'GUIADA' WHERE help_detail_mode IS NULL")

    with op.batch_alter_table("task") as batch_op:
        batch_op.alter_column("help_detail_mode", server_default=None)


def downgrade():
    with op.batch_alter_table("task") as batch_op:
        batch_op.drop_column("help_detail_mode")
