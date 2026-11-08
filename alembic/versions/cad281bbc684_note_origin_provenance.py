"""note origin provenance

Revision ID: cad281bbc684
Revises: f254ab80b2e6
Create Date: 2026-11-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cad281bbc684'
down_revision: Union[str, None] = 'f254ab80b2e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: add both columns nullable — a NOT NULL column with no default
    # cannot be added to a populated table in one step (design.md D7).
    op.add_column('notes', sa.Column('origin', sa.Text(), nullable=True))
    op.add_column('notes', sa.Column('import_ref', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Step 2: backfill — mirrors create_note's derivation rule (D6), so
    # existing rows get exactly the treatment a caller omitting `origin`
    # would have gotten.
    op.execute(
        "UPDATE notes SET origin = CASE WHEN capture_id IS NOT NULL THEN 'capture' ELSE 'manual' END"
    )

    # Step 3: now that every row has a value, enforce NOT NULL.
    op.alter_column('notes', 'origin', nullable=False)

    # Step 4: constraints last, after the data already satisfies them, so
    # the migration cannot fail halfway with constraints applied to
    # unbackfilled rows.
    op.create_check_constraint(
        'ck_notes_origin', 'notes', "origin IN ('manual', 'capture', 'import')"
    )
    op.create_check_constraint(
        'ck_notes_capture_origin_requires_capture_id', 'notes',
        "origin <> 'capture' OR capture_id IS NOT NULL",
    )
    op.create_check_constraint(
        'ck_notes_import_origin_requires_import_ref', 'notes',
        "origin <> 'import' OR import_ref IS NOT NULL",
    )
    op.create_check_constraint(
        'ck_notes_manual_origin_has_no_provenance', 'notes',
        "origin <> 'manual' OR (capture_id IS NULL AND import_ref IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint('ck_notes_manual_origin_has_no_provenance', 'notes', type_='check')
    op.drop_constraint('ck_notes_import_origin_requires_import_ref', 'notes', type_='check')
    op.drop_constraint('ck_notes_capture_origin_requires_capture_id', 'notes', type_='check')
    op.drop_constraint('ck_notes_origin', 'notes', type_='check')
    op.drop_column('notes', 'import_ref')
    op.drop_column('notes', 'origin')
