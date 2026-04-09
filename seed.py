import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from wsgi import app
from app import db
from models.caserne import Caserne
from models.vehicule import Vehicule, VehiculeTypeEnum, VehiculeStatutEnum
from models.personnel import Personnel, PersonnelGradeEnum, PersonnelStatutEnum
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

def seed():
    with app.app_context():

        # ── CASERNES ──────────────────────────────────────────────
        casernes_data = [
            {
                'nom': 'Lyon-Corneille',
                'adresse': '78 rue Pierre Corneille, 69003 Lyon',
                'lon': 4.8380, 'lat': 45.7570
            },
            {
                'nom': 'Lyon-Laennec',
                'adresse': '8 rue Laennec, 69008 Lyon',
                'lon': 4.8520, 'lat': 45.7390
            },
            {
                'nom': 'Lyon-Vaise',
                'adresse': '120 rue Philippe de Lasalle, 69004 Lyon',
                'lon': 4.8070, 'lat': 45.7720
            },
            {
                'nom': 'Lyon-Croix-Rousse',
                'adresse': '2 rue Denfert-Rochereau, 69004 Lyon',
                'lon': 4.8270, 'lat': 45.7750
            },
            {
                'nom': 'Lyon-Mermoz',
                'adresse': '247 rue Vendôme, 69003 Lyon',
                'lon': 4.8620, 'lat': 45.7480
            },
        ]

        casernes = []
        for c in casernes_data:
            caserne = Caserne(
                nom=c['nom'],
                adresse=c['adresse'],
                geom=from_shape(Point(c['lon'], c['lat']), srid=4326),
                actif=True
            )
            db.session.add(caserne)
            casernes.append(caserne)

        db.session.flush()

        # ── VÉHICULES (par caserne) ───────────────────────────────
        vehicules_data = {
            'Lyon-Corneille': [
                ('VSAV-1', VehiculeTypeEnum.vsav, 'AA-001-AA'),
                ('VSAV-2', VehiculeTypeEnum.vsav, 'AA-002-AA'),
                ('FPT-1',  VehiculeTypeEnum.fpt,  'AA-003-AA'),
                ('EPA-1',  VehiculeTypeEnum.epa,  'AA-004-AA'),
                ('VTU-1',  VehiculeTypeEnum.vtu,  'AA-005-AA'),
            ],
            'Lyon-Laennec': [
                ('VSAV-1', VehiculeTypeEnum.vsav, 'BB-001-BB'),
                ('VSAV-2', VehiculeTypeEnum.vsav, 'BB-002-BB'),
                ('FPT-1',  VehiculeTypeEnum.fpt,  'BB-003-BB'),
                ('VTU-1',  VehiculeTypeEnum.vtu,  'BB-004-BB'),
            ],
            'Lyon-Vaise': [
                ('VSAV-1', VehiculeTypeEnum.vsav, 'CC-001-CC'),
                ('FPT-1',  VehiculeTypeEnum.fpt,  'CC-002-CC'),
                ('FPT-2',  VehiculeTypeEnum.fpt,  'CC-003-CC'),
                ('VTU-1',  VehiculeTypeEnum.vtu,  'CC-004-CC'),
            ],
            'Lyon-Croix-Rousse': [
                ('VSAV-1', VehiculeTypeEnum.vsav, 'DD-001-DD'),
                ('FPT-1',  VehiculeTypeEnum.fpt,  'DD-002-DD'),
                ('VTU-1',  VehiculeTypeEnum.vtu,  'DD-003-DD'),
            ],
            'Lyon-Mermoz': [
                ('VSAV-1', VehiculeTypeEnum.vsav, 'EE-001-EE'),
                ('VSAV-2', VehiculeTypeEnum.vsav, 'EE-002-EE'),
                ('FPT-1',  VehiculeTypeEnum.fpt,  'EE-003-EE'),
                ('EPA-1',  VehiculeTypeEnum.epa,  'EE-004-EE'),
            ],
        }

        for caserne in casernes:
            for nom, type_, immat in vehicules_data.get(caserne.nom, []):
                v = Vehicule(
                    caserne_id=caserne.id,
                    nom=nom,
                    type=type_,
                    statut=VehiculeStatutEnum.disponible,
                    immatriculation=immat
                )
                db.session.add(v)

        # ── PERSONNEL (par caserne) ───────────────────────────────
        personnel_data = {
            'Lyon-Corneille': [
                ('Martin',   'Pierre',   PersonnelGradeEnum.capitaine),
                ('Dupont',   'Jean',     PersonnelGradeEnum.lieutenant),
                ('Bernard',  'Marc',     PersonnelGradeEnum.sergent),
                ('Leroy',    'Thomas',   PersonnelGradeEnum.caporal),
                ('Moreau',   'Lucas',    PersonnelGradeEnum.sapeur),
                ('Simon',    'Antoine',  PersonnelGradeEnum.sapeur),
                ('Laurent',  'Nicolas',  PersonnelGradeEnum.sapeur),
                ('Michel',   'Romain',   PersonnelGradeEnum.sapeur),
            ],
            'Lyon-Laennec': [
                ('Petit',    'David',    PersonnelGradeEnum.lieutenant),
                ('Robert',   'Julien',   PersonnelGradeEnum.adjudant),
                ('Richard',  'Kevin',    PersonnelGradeEnum.caporal),
                ('Garcia',   'Alexis',   PersonnelGradeEnum.sapeur),
                ('Lefebvre', 'Mathieu',  PersonnelGradeEnum.sapeur),
                ('Martinez', 'Clément',  PersonnelGradeEnum.sapeur),
            ],
            'Lyon-Vaise': [
                ('Thomas',   'François', PersonnelGradeEnum.lieutenant),
                ('Roux',     'Baptiste', PersonnelGradeEnum.sergent),
                ('Fournier', 'Sébastien',PersonnelGradeEnum.caporal),
                ('Morel',    'Florian',  PersonnelGradeEnum.sapeur),
                ('Girard',   'Quentin',  PersonnelGradeEnum.sapeur),
                ('André',    'Maxime',   PersonnelGradeEnum.sapeur),
            ],
            'Lyon-Croix-Rousse': [
                ('Lefevre',  'Stéphane', PersonnelGradeEnum.adjudant),
                ('Robin',    'Yannick',  PersonnelGradeEnum.sergent),
                ('Lambert',  'Damien',   PersonnelGradeEnum.sapeur),
                ('Bonnet',   'Adrien',   PersonnelGradeEnum.sapeur),
                ('François', 'Rémi',     PersonnelGradeEnum.sapeur),
            ],
            'Lyon-Mermoz': [
                ('Mercier',  'Olivier',  PersonnelGradeEnum.lieutenant),
                ('Dupuis',   'Vincent',  PersonnelGradeEnum.sergent),
                ('Fontaine', 'Guillaume',PersonnelGradeEnum.caporal),
                ('Rousseau', 'Théo',     PersonnelGradeEnum.sapeur),
                ('Vincent',  'Hugo',     PersonnelGradeEnum.sapeur),
                ('Muller',   'Enzo',     PersonnelGradeEnum.sapeur),
            ],
        }

        for caserne in casernes:
            for nom, prenom, grade in personnel_data.get(caserne.nom, []):
                p = Personnel(
                    caserne_id=caserne.id,
                    nom=nom,
                    prenom=prenom,
                    grade=grade,
                    statut=PersonnelStatutEnum.disponible
                )
                db.session.add(p)

        db.session.commit()
        print("✅ Seed terminé !")
        print(f"   {len(casernes)} casernes créées")

        total_v = sum(len(v) for v in vehicules_data.values())
        total_p = sum(len(p) for p in personnel_data.values())
        print(f"   {total_v} véhicules créés")
        print(f"   {total_p} personnels créés")

if __name__ == '__main__':
    seed()
