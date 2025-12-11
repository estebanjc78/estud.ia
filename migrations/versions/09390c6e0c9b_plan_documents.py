"""plan documents and plan item linkage

Revision ID: 09390c6e0c9b
Revises: 3de0be1f5cc2
Create Date: 2025-02-02 05:00:00.000000

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '09390c6e0c9b'
down_revision = '3de0be1f5cc2'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    plan_document_exists = 'plan_document' in inspector.get_table_names()
    created_plan_document_table = False

    if not plan_document_exists:
        op.create_table(
            'plan_document',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('study_plan_id', sa.Integer(), nullable=False),
            sa.Column('institution_id', sa.Integer(), nullable=False),
            sa.Column('curriculum_document_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('original_filename', sa.String(length=255), nullable=True),
            sa.Column('subject_hint', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['curriculum_document_id'], ['curriculum_document.id']),
            sa.ForeignKeyConstraint(['institution_id'], ['institution.id']),
            sa.ForeignKeyConstraint(['study_plan_id'], ['study_plan.id']),
            sa.PrimaryKeyConstraint('id')
        )
        created_plan_document_table = True

    inspector = sa.inspect(bind)
    if 'plan_document' in inspector.get_table_names():
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('plan_document')}
        if 'ix_plan_document_study_plan_id' not in existing_indexes:
            op.create_index('ix_plan_document_study_plan_id', 'plan_document', ['study_plan_id'])
        if 'ix_plan_document_institution_id' not in existing_indexes:
            op.create_index('ix_plan_document_institution_id', 'plan_document', ['institution_id'])

    inspector = sa.inspect(bind)
    plan_item_columns = {col['name'] for col in inspector.get_columns('plan_item')}
    plan_item_indexes = {idx['name'] for idx in inspector.get_indexes('plan_item')}
    plan_item_fks = inspector.get_foreign_keys('plan_item')
    has_plan_document_fk = any(
        fk.get('referred_table') == 'plan_document' and fk.get('constrained_columns') == ['plan_document_id']
        for fk in plan_item_fks
    )

    needs_plan_document_id = 'plan_document_id' not in plan_item_columns
    needs_plan_document_index = 'ix_plan_item_plan_document_id' not in plan_item_indexes
    needs_plan_document_fk = not has_plan_document_fk

    if needs_plan_document_id or needs_plan_document_index or needs_plan_document_fk:
        with op.batch_alter_table('plan_item', schema=None, recreate='always') as batch_op:
            if needs_plan_document_id:
                batch_op.add_column(sa.Column('plan_document_id', sa.Integer(), nullable=True))
            if needs_plan_document_index:
                batch_op.create_index('ix_plan_item_plan_document_id', ['plan_document_id'])
            if needs_plan_document_fk:
                batch_op.create_foreign_key(
                    'plan_item_plan_document_id_fkey',
                    'plan_document',
                    ['plan_document_id'],
                    ['id'],
                    ondelete='CASCADE',
                )

    if created_plan_document_table:
        connection = op.get_bind()
        now = datetime.utcnow()
        result = connection.execute(
            sa.text(
                """
                SELECT study_plan.id AS plan_id,
                       study_plan.institution_id AS institution_id,
                       curriculum_document.id AS document_id,
                       curriculum_document.title AS title,
                       curriculum_document.source_filename AS filename
                FROM study_plan
                JOIN curriculum_document ON curriculum_document.id = study_plan.curriculum_document_id
                """
            )
        )
        rows = result.fetchall()
        for row in rows:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO plan_document
                    (study_plan_id, institution_id, curriculum_document_id, title, original_filename, subject_hint, created_at, updated_at)
                    VALUES (:study_plan_id, :institution_id, :curriculum_document_id, :title, :original_filename, NULL, :created_at, :updated_at)
                    """
                ),
                {
                    "study_plan_id": row.plan_id,
                    "institution_id": row.institution_id,
                    "curriculum_document_id": row.document_id,
                    "title": row.title or "Documento curricular",
                    "original_filename": row.filename,
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'plan_item' in inspector.get_table_names():
        plan_item_columns = {col['name'] for col in inspector.get_columns('plan_item')}
        plan_item_indexes = {idx['name'] for idx in inspector.get_indexes('plan_item')}
        plan_item_fks = inspector.get_foreign_keys('plan_item')
        has_plan_document_fk = any(
            fk.get('referred_table') == 'plan_document' and fk.get('constrained_columns') == ['plan_document_id']
            for fk in plan_item_fks
        )

        needs_drop_column = 'plan_document_id' in plan_item_columns
        needs_drop_index = 'ix_plan_item_plan_document_id' in plan_item_indexes

        if needs_drop_column or needs_drop_index or has_plan_document_fk:
            with op.batch_alter_table('plan_item', schema=None, recreate='always') as batch_op:
                if has_plan_document_fk:
                    batch_op.drop_constraint('plan_item_plan_document_id_fkey', type_='foreignkey')
                if needs_drop_index:
                    batch_op.drop_index('ix_plan_item_plan_document_id')
                if needs_drop_column:
                    batch_op.drop_column('plan_document_id')

    inspector = sa.inspect(bind)
    if 'plan_document' in inspector.get_table_names():
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('plan_document')}
        if 'ix_plan_document_institution_id' in existing_indexes:
            op.drop_index('ix_plan_document_institution_id', table_name='plan_document')
        if 'ix_plan_document_study_plan_id' in existing_indexes:
            op.drop_index('ix_plan_document_study_plan_id', table_name='plan_document')
        op.drop_table('plan_document')
