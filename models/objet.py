from app import db
from datetime import datetime

class Objet(db.Model):
    __tablename__ = 'objets'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False, default='generique')
    description = db.Column(db.Text, nullable=True)
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    positions = db.relationship('Position', backref='objet', lazy=True)
    statuts = db.relationship('Statut', backref='objet', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'type': self.type,
            'description': self.description,
            'actif': self.actif,
            'created_at': self.created_at.isoformat()
        }
