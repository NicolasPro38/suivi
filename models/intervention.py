from app import db
from datetime import datetime
import enum

class InterventionTypeEnum(enum.Enum):
    incendie_batiment = 'incendie_batiment'
    incendie_vehicule = 'incendie_vehicule'
    incendie_objet = 'incendie_objet'
    incendie_foret = 'incendie_foret'
    secours_personne = 'secours_personne'
    accident_route = 'accident_route'
    fuite_gaz = 'fuite_gaz'
    inondation = 'inondation'
    ouverture_porte = 'ouverture_porte'
    sauvetage_animal = 'sauvetage_animal'
    risque_chimique = 'risque_chimique'
    constat_deces = 'constat_deces'

class InterventionStatutEnum(enum.Enum):
    en_attente = 'en_attente'
    vehicule_envoye = 'vehicule_envoye'
    en_cours = 'en_cours'
    en_retour = 'en_retour'
    termine = 'termine'
    annule = 'annule'

class Intervention(db.Model):
    __tablename__ = 'interventions'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Enum(InterventionTypeEnum), nullable=False)
    statut = db.Column(db.Enum(InterventionStatutEnum), nullable=False, default=InterventionStatutEnum.en_attente)
    adresse = db.Column(db.String(200), nullable=True)
    geom = db.Column(db.String, nullable=False)
    caserne_id = db.Column(db.Integer, db.ForeignKey('casernes.id'), nullable=True)
    vehicule_id = db.Column(db.Integer, db.ForeignKey('vehicules.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    commentaire = db.Column(db.Text, nullable=True)
    # Position de départ réelle du véhicule (peut être différente de la caserne)
    depart_lat = db.Column(db.Float, nullable=True)
    depart_lon = db.Column(db.Float, nullable=True)
    prevu_sur_place_at = db.Column(db.DateTime, nullable=True)
    prevu_retour_at = db.Column(db.DateTime, nullable=True)
    retour_lat = db.Column(db.Float, nullable=True)
    retour_lon = db.Column(db.Float, nullable=True)
    waypoints_aller_json = db.Column(db.Text, nullable=True)
    waypoints_retour_json = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type.value,
            'statut': self.statut.value,
            'adresse': self.adresse,
            'geom': self.geom,
            'caserne_id': self.caserne_id,
            'vehicule_id': self.vehicule_id,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'commentaire': self.commentaire,
            'depart_lat': self.depart_lat,
            'depart_lon': self.depart_lon,
            'retour_lat': self.retour_lat,
            'retour_lon': self.retour_lon,
            'waypoints_aller_json': self.waypoints_aller_json,
            'waypoints_retour_json': self.waypoints_retour_json
        }