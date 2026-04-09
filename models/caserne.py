from app import db
from geoalchemy2 import Geometry

class Caserne(db.Model):
    __tablename__ = 'casernes'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    adresse = db.Column(db.String(200), nullable=True)
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326), nullable=False)
    actif = db.Column(db.Boolean, default=True)

    vehicules = db.relationship('Vehicule', backref='caserne', lazy=True)
    personnels = db.relationship('Personnel', backref='caserne', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'adresse': self.adresse,
            'actif': self.actif
        }
