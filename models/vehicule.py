from app import db
import enum

class VehiculeTypeEnum(enum.Enum):
    vsav = 'vsav'           # Véhicule de Secours et d'Assistance aux Victimes
    fpt = 'fpt'             # Fourgon Pompe Tonne
    epa = 'epa'             # Echelle Pivotante Automatique
    vtu = 'vtu'             # Véhicule Tout Usage
    ccu = 'ccu'             # Cellule Combustible
    vlhr = 'vlhr'           # Véhicule Léger Hors Route

class VehiculeStatutEnum(enum.Enum):
    disponible = 'disponible'
    en_route = 'en_route'
    sur_place = 'sur_place'
    en_retour = 'en_retour'
    en_maintenance = 'en_maintenance'
    hors_service = 'hors_service'

class Vehicule(db.Model):
    __tablename__ = 'vehicules'

    id = db.Column(db.Integer, primary_key=True)
    caserne_id = db.Column(db.Integer, db.ForeignKey('casernes.id'), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum(VehiculeTypeEnum), nullable=False)
    statut = db.Column(db.Enum(VehiculeStatutEnum), nullable=False, default=VehiculeStatutEnum.disponible)
    immatriculation = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'caserne_id': self.caserne_id,
            'nom': self.nom,
            'type': self.type.value,
            'statut': self.statut.value,
            'immatriculation': self.immatriculation
        }
