"""similar notes pg_trgm

Revision ID: 88c04d15a436
Revises: a1c3f7e9b2d4
Create Date: 2026-11-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '88c04d15a436'
down_revision: Union[str, None] = 'a1c3f7e9b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match similarity.py's normalized_text_expr() exactly — the index
# only helps if the query's expression is textually identical to this one
# (design D2). Strips a leading "å " infinitive marker and a leading
# en/et/ei article, lowercased, so "å oppleve" and "oppleve" compare as
# the same string.
_NORMALIZED_TEXT_EXPR = (
    "lower(regexp_replace(regexp_replace(text, '^å\\s+', ''), '^(en|et|ei)\\s+', ''))"
)


def upgrade() -> None:
    # similar-notes-merge design D2: verified present in the running
    # postgres:17-alpine image's contrib set before writing anything
    # around its absence (tasks.md 1.1).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        f"CREATE INDEX ix_notes_text_trgm ON notes USING gin (({_NORMALIZED_TEXT_EXPR}) gin_trgm_ops)"
    )


def downgrade() -> None:
    # Drop only the index — dropping a shared extension on downgrade is
    # more dangerous than leaving it installed and unused (tasks.md 2.4).
    op.execute("DROP INDEX IF EXISTS ix_notes_text_trgm")
