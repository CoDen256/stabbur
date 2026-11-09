"""captures provenance and promote

Revision ID: 8589dc3d360d
Revises: a1c3f7e9b2d4
Create Date: 2026-11-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8589dc3d360d'
down_revision: Union[str, None] = 'a1c3f7e9b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'captures',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('selected_text', sa.Text(), nullable=False),
        sa.Column('context_text', sa.Text(), nullable=True),
        sa.Column('translations', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('source', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('audio_blob', sa.Text(), nullable=True),
        sa.Column('audio_sel_ms', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("source ? 'web' OR source ? 'youtube'", name='ck_captures_source_shape'),
    )

    # design.md D7/task 1.4: nothing could have legitimately written a
    # non-null capture_id before this change (no table, route, or writer
    # could produce one) — assert that and fail loudly rather than add a
    # FK that silently coexists with orphaned references.
    conn = op.get_bind()
    orphaned = conn.execute(sa.text("SELECT count(*) FROM notes WHERE capture_id IS NOT NULL")).scalar()
    if orphaned:
        raise RuntimeError(
            f"cannot add notes.capture_id -> captures.id FK: {orphaned} note(s) already "
            "carry a non-null capture_id with no captures table to validate it against"
        )

    op.create_foreign_key(
        'fk_notes_capture_id_captures', 'notes', 'captures', ['capture_id'], ['id'], ondelete='RESTRICT'
    )


def downgrade() -> None:
    # FK before table, in that order, or dropping the table first fails on
    # a populated database (task 1.5).
    op.drop_constraint('fk_notes_capture_id_captures', 'notes', type_='foreignkey')
    op.drop_table('captures')
