from app import db
from datetime import datetime
import enum

class TrajetStatutEnum(enum.Enum):
    planifie = 'planifie'
    en_cours = 'en_cours'
    termine = 'termine'
    annule = 'annule'

class Trajet(db.Model):
    __tablename__ = 'trajets'

    id = db.Column(db.Integer, primary_key=True)
    objet_id = db.Column(db.Integer, db.ForeignKey('objets.id'), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    statut = db.Column(db.Enum(TrajetStatutEnum), nullable=False, default=TrajetStatutEnum.planifie)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    taches = db.relationship('Tache', backref='trajet', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'objet_id': self.objet_id,
            'nom': self.nom,
            'statut': self.statut.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None
        }
