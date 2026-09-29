"""pharmacies

Revision ID: faca12b135c0
Revises: 9898b55baffd
Create Date: 2026-09-29 23:00:57.682123

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'faca12b135c0'
down_revision: Union[str, Sequence[str], None] = '9898b55baffd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('pharmacies',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('owner_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=False),
    sa.Column('phone', sa.String(length=50), nullable=False),
    sa.Column('logo_sha256', sa.String(length=64), nullable=True),
    sa.Column('logo_type', sa.String(length=10), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pharmacies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pharmacies_owner_id'), ['owner_id'], unique=False)

    with op.batch_alter_table('decisions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pharmacy', sa.JSON(), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_pharmacies', sa.Integer(), server_default='1', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('max_pharmacies')

    with op.batch_alter_table('decisions', schema=None) as batch_op:
        batch_op.drop_column('pharmacy')

    with op.batch_alter_table('pharmacies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pharmacies_owner_id'))

    op.drop_table('pharmacies')
