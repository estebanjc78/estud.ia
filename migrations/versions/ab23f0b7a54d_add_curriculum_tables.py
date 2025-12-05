"""add curriculum document tables

Revision ID: ab23f0b7a54d
Revises: 67af3a3c3c3e
Create Date: 2025-02-28 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab23f0b7a54d'
down_revision = '67af3a3c3c3e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'curriculum_document',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('institution_id', sa.Integer(), sa.ForeignKey('institution.id'), nullable=True),
        sa.Column('uploaded_by_profile_id', sa.Integer(), sa.ForeignKey('profile.id'), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('jurisdiction', sa.String(length=120), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('source_filename', sa.String(length=255), nullable=True),
        sa.Column('storage_path', sa.String(length=512), nullable=True),
        sa.Column('mime_type', sa.String(length=120), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='processing'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('grade_min', sa.String(length=20), nullable=True),
        sa.Column('grade_max', sa.String(length=20), nullable=True),
        sa.Column('segment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'curriculum_segment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('curriculum_document.id'), nullable=False),
        sa.Column('grade_label', sa.String(length=20), nullable=True),
        sa.Column('area', sa.String(length=120), nullable=True),
        sa.Column('section_title', sa.String(length=255), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=True),
        sa.Column('end_line', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('curriculum_segment')
    op.drop_table('curriculum_document')
