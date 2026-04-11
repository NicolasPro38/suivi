import random
import threading
import time
from datetime import datetime
from app import db
from models.caserne import Caserne
from models.vehicule import Vehicule, VehiculeStatutEnum
from models.intervention import Intervention, InterventionTypeEnum, InterventionStatutEnum

LYON_BOUNDS = {
    'lat_min': 45.720, 'lat_max': 45.800,
    'lon_min': 4.780,  'lon_max': 4.900
}

TYPES_INTERVENTION = [
    (InterventionTypeEnum.secours_personne,   30, 20),
    (InterventionTypeEnum.accident_route,     15, 30),
    (InterventionTypeEnum.incendie_batiment,  10, 60),
    (InterventionTypeEnum.incendie_vehicule,  10, 25),
    (InterventionTypeEnum.incendie_objet,      8, 15),
    (InterventionTypeEnum.ouverture_porte,     8, 10),
    (InterventionTypeEnum.fuite_gaz,           6, 40),
    (InterventionTypeEnum.inondation,          5, 45),
    (InterventionTypeEnum.sauvetage_animal,    4, 20),
    (InterventionTypeEnum.incendie_foret,      2, 90),
    (InterventionTypeEnum.risque_chimique,     1, 120),
    (InterventionTypeEnum.constat_deces,       1, 15),
]

# Durées de trajet simulées (minutes)
DUREE_TRAJET = 5  # minutes pour aller/retour caserne -> intervention

def point_aleatoire_lyon():
    lat = random.uniform(LYON_BOUNDS['lat_min'], LYON_BOUNDS['lat_max'])
    lon = random.uniform(LYON_BOUNDS['lon_min'], LYON_BOUNDS['lon_max'])
    return lat, lon

def type_aleatoire():
    types = [t[0] for t in TYPES_INTERVENTION]
    poids = [t[1] for t in TYPES_INTERVENTION]
    return random.choices(types, weights=poids, k=1)[0]

def duree_pour_type(type_intervention):
    for t, _, duree in TYPES_INTERVENTION:
        if t == type_intervention:
            return duree + random.randint(-5, 10)
    return 20

def caserne_la_plus_proche(lat, lon):
    casernes = Caserne.query.filter_by(actif=True).all()
    min_dist = float('inf')
    best = None
    for c in casernes:
        from geoalchemy2.shape import to_shape
        pt = to_shape(c.geom)
        dist = ((pt.y - lat)**2 + (pt.x - lon)**2)**0.5
        if dist < min_dist:
            min_dist = dist
            best = c
    return best

def vehicule_disponible(caserne_id):
    return Vehicule.query.filter_by(
        caserne_id=caserne_id,
        statut=VehiculeStatutEnum.disponible
    ).first()

def passer_en_retour(intervention_id, app):
    """Intervention terminée sur place, véhicule rentre à la caserne"""
    with app.app_context():
        intervention = Intervention.query.get(intervention_id)
        if not intervention:
            return
        if intervention.vehicule_id:
            vehicule = Vehicule.query.get(intervention.vehicule_id)
            if vehicule:
                vehicule.statut = VehiculeStatutEnum.en_retour
        intervention.statut = InterventionStatutEnum.termine
        intervention.ended_at = datetime.utcnow()
        db.session.commit()

        intervention_id_local = intervention_id
        vehicule_id = intervention.vehicule_id

    # Après le trajet retour, le véhicule est de nouveau disponible
    threading.Timer(
        DUREE_TRAJET * 60,
        vehicule_disponible_apres_retour,
        args=[vehicule_id, app]
    ).start()

def vehicule_disponible_apres_retour(vehicule_id, app):
    """Véhicule arrivé à la caserne, de nouveau disponible"""
    with app.app_context():
        vehicule = Vehicule.query.get(vehicule_id)
        if vehicule and vehicule.statut == VehiculeStatutEnum.en_retour:
            vehicule.statut = VehiculeStatutEnum.disponible
            db.session.commit()

def creer_intervention(app):
    with app.app_context():
        lat, lon = point_aleatoire_lyon()
        type_i = type_aleatoire()
        caserne = caserne_la_plus_proche(lat, lon)
        vehicule = vehicule_disponible(caserne.id) if caserne else None

        intervention = Intervention(
            type=type_i,
            statut=InterventionStatutEnum.en_attente,
            adresse=f"Lyon ({lat:.4f}, {lon:.4f})",
            geom=f"{lat},{lon}",
            caserne_id=caserne.id if caserne else None,
            vehicule_id=vehicule.id if vehicule else None,
            created_at=datetime.utcnow()
        )
        db.session.add(intervention)

        if vehicule:
            # Phase 1 : en_route
            vehicule.statut = VehiculeStatutEnum.en_route
            intervention.statut = InterventionStatutEnum.vehicule_envoye
            intervention.started_at = datetime.utcnow()

        db.session.commit()

        intervention_id = intervention.id
        type_value = intervention.type
        duree_sur_place = duree_pour_type(type_value)

        if vehicule:
            # Après trajet aller → sur_place
            threading.Timer(
                DUREE_TRAJET * 60,
                passer_sur_place,
                args=[intervention_id, vehicule.id, app]
            ).start()

            # Après trajet aller + durée sur place → en_retour
            threading.Timer(
                (DUREE_TRAJET + duree_sur_place) * 60,
                passer_en_retour,
                args=[intervention_id, app]
            ).start()

        return intervention_id, duree_sur_place

def passer_sur_place(intervention_id, vehicule_id, app):
    """Véhicule arrivé sur place"""
    with app.app_context():
        vehicule = Vehicule.query.get(vehicule_id)
        if vehicule and vehicule.statut == VehiculeStatutEnum.en_route:
            vehicule.statut = VehiculeStatutEnum.sur_place
        intervention = Intervention.query.get(intervention_id)
        if intervention:
            intervention.statut = InterventionStatutEnum.en_cours
        db.session.commit()

def boucle_simulation(app):
    while True:
        try:
            time.sleep(random.randint(600, 1800))  # 10 à 30 minutes
            creer_intervention(app)
        except Exception as e:
            print(f"Erreur simulateur: {e}")

def demarrer_simulateur(app):
    thread = threading.Thread(target=boucle_simulation, args=[app], daemon=True)
    thread.start()
    print("✅ Simulateur démarré")