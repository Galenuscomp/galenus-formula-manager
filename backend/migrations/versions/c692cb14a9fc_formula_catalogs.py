"""formula catalogs

Revision ID: c692cb14a9fc
Revises: c96a29efbfde
Create Date: 2026-09-29 20:53:15.282082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c692cb14a9fc'
down_revision: Union[str, Sequence[str], None] = 'c96a29efbfde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('catalog_entries',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('source_formula_id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=1000), nullable=False),
    sa.Column('route', sa.String(length=100), nullable=False),
    sa.Column('base', sa.String(length=500), nullable=False),
    sa.Column('url', sa.String(length=2000), nullable=False),
    sa.Column('active_ingredient', sa.String(length=1000), nullable=False),
    sa.Column('strength', sa.String(length=500), nullable=False),
    sa.Column('dosage_form', sa.String(length=200), nullable=False),
    sa.Column('final_quantity', sa.String(length=200), nullable=False),
    sa.Column('search_text', sa.Text(), nullable=False),
    sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('catalog_entries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_catalog_entries_source'), ['source'], unique=False)

    with op.batch_alter_table('search_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('catalog_ref', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('search_requests', schema=None) as batch_op:
        batch_op.drop_column('catalog_ref')

    with op.batch_alter_table('catalog_entries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_catalog_entries_source'))

    op.drop_table('catalog_entries')
