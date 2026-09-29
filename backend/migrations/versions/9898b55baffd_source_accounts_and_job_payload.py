"""source accounts and job payload

Revision ID: 9898b55baffd
Revises: c692cb14a9fc
Create Date: 2026-09-29 22:04:13.328319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9898b55baffd'
down_revision: Union[str, Sequence[str], None] = 'c692cb14a9fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('source_accounts',
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('username_encrypted', sa.Text(), nullable=False),
    sa.Column('password_encrypted', sa.Text(), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('source')
    )
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payload', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('payload')

    op.drop_table('source_accounts')
