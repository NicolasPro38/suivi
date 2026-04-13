"""feat: nouveaux statuts vehicules
Revision ID: a7df3c2ca366
Revises: fedf3e0b93d1
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = 'a7df3c2ca366'
down_revision = 'fedf3e0b93d1'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TYPE vehiculestatutenum ADD VALUE IF NOT EXISTS 'en_route'")
    op.execute("ALTER TYPE vehiculestatutenum ADD VALUE IF NOT EXISTS 'sur_place'")
    op.execute("ALTER TYPE vehiculestatutenum ADD VALUE IF NOT EXISTS 'en_retour'")

def downgrade():
    pass