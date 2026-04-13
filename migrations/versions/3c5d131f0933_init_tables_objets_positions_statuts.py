"""init: tables objets, positions, statuts
Revision ID: 3c5d131f0933
Revises: 
Create Date: 2026-04-09 17:49:22.610310
"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision = '3c5d131f0933'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('objets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nom', sa.String(length=100), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('actif', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('positions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('objet_id', sa.Integer(), nullable=False),
    sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('vitesse', sa.Float(), nullable=True),
    sa.Column('cap', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['objet_id'], ['objets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('statuts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('objet_id', sa.Integer(), nullable=False),
    sa.Column('statut', sa.Enum('non_fait', 'en_cours', 'fait', 'probleme', name='statutenum'), nullable=False),
    sa.Column('commentaire', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['objet_id'], ['objets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('statuts')
    op.drop_table('positions')
    op.drop_table('objets')
