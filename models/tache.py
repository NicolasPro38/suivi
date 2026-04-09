from app import db
from datetime import datetime
from geoalchemy2 import Geometry
import enum

class TacheStatutEnum(enum.Enum):
    planifie = 'planifie'
    en_route = 'en_route'
    en_cours = 'en_cours'
    fait = 'fait'
    probleme = 'probleme'
    annule = 'annule'

class Tache(db.Model):
    __tablename__ = 'taches'

    id = db.Column(db.Integer, primary_key=True)
    trajet_id = db.Column(db.Integer, db.ForeignKey('trajets.id'), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326), nullable=False)
    ordre = db.Column(db.Integer, nullable=False, default=0)
    statut = db.Column(db.Enum(TacheStatutEnum), nullable=False, default=TacheStatutEnum.planifie)
    est_mission = db.Column(db.Boolean, default=False)
    heure_prevue = db.Column(db.DateTime, nullable=True)
    heure_reelle = db.Column(db.DateTime, nullable=True)
    commentaire = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'trajet_id': self.trajet_id,
            'nom': self.nom,
            'description': self.description,
            'ordre': self.ordre,
            'statut': self.statut.value,
            'est_mission': self.est_mission,
            'heure_prevue': self.heure_prevue.isoformat() if self.heure_prevue else None,
            'heure_reelle': self.heure_reelle.isoformat() if self.heure_reelle else None,
            'commentaire': self.commentaire,
            'created_at': self.created_at.isoformat()
        }
