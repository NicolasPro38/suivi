"""feat: statut en_retour intervention
Revision ID: d06eb059e57c
Revises: 78435ca08486
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'd06eb059e57c'
down_revision = '78435ca08486'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TYPE interventionstatutenum ADD VALUE IF NOT EXISTS 'en_retour'")

def downgrade():
    pass