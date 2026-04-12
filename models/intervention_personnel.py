from app import db
from datetime import datetime

class InterventionPersonnel(db.Model):
    __tablename__ = 'intervention_personnel'

    id = db.Column(db.Integer, primary_key=True)
    intervention_id = db.Column(db.Integer, db.ForeignKey('interventions.id'), nullable=False)
    personnel_id = db.Column(db.Integer, db.ForeignKey('personnel.id'), nullable=False)
    vehicule_id = db.Column(db.Integer, db.ForeignKey('vehicules.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'intervention_id': self.intervention_id,
            'personnel_id': self.personnel_id,
            'vehicule_id': self.vehicule_id,
            'created_at': self.created_at.isoformat()
        }