"""feat: ajout tables casernes, vehicules, personnel
Revision ID: 023643a2cf30
Revises: 54f956966e24
Create Date: 2026-04-09 19:34:57.110566
"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision = '023643a2cf30'
down_revision = '54f956966e24'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('casernes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nom', sa.String(length=100), nullable=False),
    sa.Column('adresse', sa.String(length=200), nullable=True),
    sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('actif', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('personnel',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('caserne_id', sa.Integer(), nullable=False),
    sa.Column('nom', sa.String(length=100), nullable=False),
    sa.Column('prenom', sa.String(length=100), nullable=False),
    sa.Column('grade', sa.Enum('sapeur', 'caporal', 'sergent', 'adjudant', 'lieutenant', 'capitaine', name='personnelgradeenum'), nullable=False),
    sa.Column('statut', sa.Enum('disponible', 'en_intervention', 'en_repos', 'absent', name='personnelstatutenum'), nullable=False),
    sa.ForeignKeyConstraint(['caserne_id'], ['casernes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('vehicules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('caserne_id', sa.Integer(), nullable=False),
    sa.Column('nom', sa.String(length=100), nullable=False),
    sa.Column('type', sa.Enum('vsav', 'fpt', 'epa', 'vtu', 'ccu', 'vlhr', name='vehiculetypeenum'), nullable=False),
    sa.Column('statut', sa.Enum('disponible', 'en_intervention', 'en_maintenance', 'hors_service', name='vehiculestatutenum'), nullable=False),
    sa.Column('immatriculation', sa.String(length=20), nullable=True),
    sa.ForeignKeyConstraint(['caserne_id'], ['casernes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('vehicules')
    op.drop_table('personnel')
    op.drop_table('casernes')
