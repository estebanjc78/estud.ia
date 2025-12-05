"""add platform theme table

Revision ID: df4f6b8f9a9a
Revises: c7b8f9d9fa31
Create Date: 2025-12-05 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df4f6b8f9a9a'
down_revision = 'c7b8f9d9fa31'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'platform_theme',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('subtitle', sa.String(length=255), nullable=True),
        sa.Column('logo_url', sa.String(length=512), nullable=True),
        sa.Column('primary_color', sa.String(length=7), nullable=True),
        sa.Column('secondary_color', sa.String(length=7), nullable=True),
        sa.Column('sidebar_color', sa.String(length=7), nullable=True),
        sa.Column('sidebar_text_color', sa.String(length=7), nullable=True),
        sa.Column('background_color', sa.String(length=7), nullable=True),
        sa.Column('login_background', sa.String(length=7), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('platform_theme')
