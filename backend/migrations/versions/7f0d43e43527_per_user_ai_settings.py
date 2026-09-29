"""per-user AI settings

Revision ID: 7f0d43e43527
Revises: 5e12a8016d6e
Create Date: 2026-09-29 20:13:47.958300

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f0d43e43527'
down_revision: Union[str, Sequence[str], None] = '5e12a8016d6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_ai_settings',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('api_key_encrypted', sa.Text(), nullable=True),
    sa.Column('key_last4', sa.String(length=4), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('requested_by', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_jobs_requested_by_users', 'users', ['requested_by'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_jobs_requested_by_users', type_='foreignkey')
        batch_op.drop_column('requested_by')

    op.drop_table('user_ai_settings')
