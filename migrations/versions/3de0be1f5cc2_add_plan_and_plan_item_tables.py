"""add plan and plan_item tables

Revision ID: 3de0be1f5cc2
Revises: 7e79bfe8c7c3
Create Date: 2025-02-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3de0be1f5cc2'
down_revision = '7e79bfe8c7c3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'plan',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution_id', sa.Integer(), nullable=False),
        sa.Column('study_plan_id', sa.Integer(), nullable=True),
        sa.Column('nombre', sa.String(length=255), nullable=False),
        sa.Column('anio_lectivo', sa.String(length=16), nullable=True),
        sa.Column('jurisdiccion', sa.String(length=120), nullable=True),
        sa.Column('descripcion_general', sa.Text(), nullable=True),
        sa.Column('contenido_bruto', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['institution_id'], ['institution.id']),
        sa.ForeignKeyConstraint(['study_plan_id'], ['study_plan.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('study_plan_id'),
    )
    op.create_index('ix_plan_institution_id', 'plan', ['institution_id'])

    op.create_table(
        'plan_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('grado', sa.String(length=32), nullable=True),
        sa.Column('grado_normalizado', sa.String(length=32), nullable=True),
        sa.Column('area', sa.String(length=255), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plan.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_plan_item_plan_id', 'plan_item', ['plan_id'])
    op.create_index('ix_plan_item_grado_normalizado', 'plan_item', ['grado_normalizado'])


def downgrade():
    op.drop_index('ix_plan_item_grado_normalizado', table_name='plan_item')
    op.drop_index('ix_plan_item_plan_id', table_name='plan_item')
    op.drop_table('plan_item')
    op.drop_index('ix_plan_institution_id', table_name='plan')
    op.drop_table('plan')
