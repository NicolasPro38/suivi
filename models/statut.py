from app import db
from datetime import datetime
import enum

class StatutEnum(enum.Enum):
    non_fait = 'non_fait'
    en_cours = 'en_cours'
    fait = 'fait'
    probleme = 'probleme'

class Statut(db.Model):
    __tablename__ = 'statuts'

    id = db.Column(db.Integer, primary_key=True)
    objet_id = db.Column(db.Integer, db.ForeignKey('objets.id'), nullable=False)
    statut = db.Column(db.Enum(StatutEnum), nullable=False, default=StatutEnum.non_fait)
    commentaire = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'objet_id': self.objet_id,
            'statut': self.statut.value,
            'commentaire': self.commentaire,
            'created_at': self.created_at.isoformat()
        }
