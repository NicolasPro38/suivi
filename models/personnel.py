from app import db
import enum

class PersonnelStatutEnum(enum.Enum):
    disponible = 'disponible'
    en_intervention = 'en_intervention'
    en_repos = 'en_repos'
    absent = 'absent'

class PersonnelGradeEnum(enum.Enum):
    sapeur = 'sapeur'
    caporal = 'caporal'
    sergent = 'sergent'
    adjudant = 'adjudant'
    lieutenant = 'lieutenant'
    capitaine = 'capitaine'

class Personnel(db.Model):
    __tablename__ = 'personnel'

    id = db.Column(db.Integer, primary_key=True)
    caserne_id = db.Column(db.Integer, db.ForeignKey('casernes.id'), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Enum(PersonnelGradeEnum), nullable=False, default=PersonnelGradeEnum.sapeur)
    statut = db.Column(db.Enum(PersonnelStatutEnum), nullable=False, default=PersonnelStatutEnum.disponible)

    def to_dict(self):
        return {
            'id': self.id,
            'caserne_id': self.caserne_id,
            'nom': self.nom,
            'prenom': self.prenom,
            'grade': self.grade.value,
            'statut': self.statut.value
        }
