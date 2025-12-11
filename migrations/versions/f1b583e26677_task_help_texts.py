"""Add help text fields to task

Revision ID: f1b583e26677
Revises: 09390c6e0c9b
Create Date: 2025-02-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1b583e26677"
down_revision = "09390c6e0c9b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.add_column(sa.Column("help_text_low", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("help_text_medium", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("help_text_high", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.drop_column("help_text_high")
        batch_op.drop_column("help_text_medium")
        batch_op.drop_column("help_text_low")
