"""feat: ajout tables trajets et taches
Revision ID: 54f956966e24
Revises: 3c5d131f0933
Create Date: 2026-04-09 19:13:57.965621
"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision = '54f956966e24'
down_revision = '3c5d131f0933'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('trajets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('objet_id', sa.Integer(), nullable=False),
    sa.Column('nom', sa.String(length=100), nullable=False),
    sa.Column('statut', sa.Enum('planifie', 'en_cours', 'termine', 'annule', name='trajetstatutenum'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['objet_id'], ['objets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('taches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trajet_id', sa.Integer(), nullable=False),
    sa.Column('nom', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('ordre', sa.Integer(), nullable=False),
    sa.Column('statut', sa.Enum('planifie', 'en_route', 'en_cours', 'fait', 'probleme', 'annule', name='tachestatutenum'), nullable=False),
    sa.Column('est_mission', sa.Boolean(), nullable=True),
    sa.Column('heure_prevue', sa.DateTime(), nullable=True),
    sa.Column('heure_reelle', sa.DateTime(), nullable=True),
    sa.Column('commentaire', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['trajet_id'], ['trajets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('taches')
    op.drop_table('trajets')
