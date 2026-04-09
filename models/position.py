from app import db
from datetime import datetime
from geoalchemy2 import Geometry

class Position(db.Model):
    __tablename__ = 'positions'

    id = db.Column(db.Integer, primary_key=True)
    objet_id = db.Column(db.Integer, db.ForeignKey('objets.id'), nullable=False)
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    vitesse = db.Column(db.Float, nullable=True)
    cap = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'objet_id': self.objet_id,
            'timestamp': self.timestamp.isoformat(),
            'vitesse': self.vitesse,
            'cap': self.cap
        }
