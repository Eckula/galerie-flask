# migrations/versions/****_add_kind_pinned.py — Alembic (si tu utilises flask-migrate)
from alembic import op
import sqlalchemy as sa

revision = 'add_kind_pinned'
down_revision = None  # remplace par ta dernière révision
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('folder') as b:
        b.add_column(sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('media') as b:
        b.add_column(sa.Column('kind', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('resource_type', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('format', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()))
        b.create_index('ix_media_kind', ['kind'])

def downgrade():
    with op.batch_alter_table('media') as b:
        b.drop_index('ix_media_kind')
        b.drop_column('created_at')
        b.drop_column('format')
        b.drop_column('resource_type')
        b.drop_column('kind')
    with op.batch_alter_table('folder') as b:
        b.drop_column('pinned')
