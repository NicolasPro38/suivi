import json
import random
import threading
import time
from datetime import datetime, timedelta
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

def point_aleatoire_lyon():
    lat = random.uniform(LYON_BOUNDS['lat_min'], LYON_BOUNDS['lat_max'])
    lon = random.uniform(LYON_BOUNDS['lon_min'], LYON_BOUNDS['lon_max'])
    return lat, lon

def type_aleatoire():
    types = [t[0] for t in TYPES_INTERVENTION]
    poids = [t[1] for t in TYPES_INTERVENTION]
    return random.choices(types, weights=poids, k=1)[0]

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

def calculer_osrm_complet(lon1, lat1, lon2, lat2, fallback_duree=300):
    """Retourne (duree_secondes, waypoints_liste) depuis OSRM."""
    try:
        import requests
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        r = requests.get(url, params={'overview': 'full', 'geometries': 'geojson'}, timeout=5)
        data = r.json()
        route = data['routes'][0]
        duree = route['duration']
        coords = route['geometry']['coordinates']
        waypoints = [[c[1], c[0]] for c in coords]  # [lon,lat] → [lat,lon]
        return duree, waypoints
    except:
        return fallback_duree, [[lat1, lon1], [lat2, lon2]]

def calculer_duree_osrm(lon1, lat1, lon2, lat2, fallback=300):
    """Retourne uniquement la durée."""
    duree, _ = calculer_osrm_complet(lon1, lat1, lon2, lat2, fallback)
    return duree

def interpoler_sur_waypoints(waypoints, progress):
    """Interpole une position sur une liste de waypoints selon la progression (0-1)."""
    if not waypoints or len(waypoints) < 2:
        return None
    progress = max(0.0, min(1.0, progress))
    total = len(waypoints) - 1
    idx = int(progress * total)
    frac = (progress * total) - idx
    if idx >= total:
        return waypoints[-1]
    p1, p2 = waypoints[idx], waypoints[idx + 1]
    return [p1[0] + (p2[0] - p1[0]) * frac, p1[1] + (p2[1] - p1[1]) * frac]

def get_position_sur_waypoints(intervention, now):
    """
    Calcule la position exacte du véhicule en interpolant sur les vrais waypoints OSRM.
    Retourne (lat, lon) ou None.
    """
    statut = intervention.statut

    if statut == InterventionStatutEnum.vehicule_envoye:
        if not intervention.started_at or not intervention.prevu_sur_place_at:
            return None
        waypoints = json.loads(intervention.waypoints_aller_json) if intervention.waypoints_aller_json else None
        if not waypoints:
            return None
        duree = (intervention.prevu_sur_place_at - intervention.started_at).total_seconds()
        elapsed = (now - intervention.started_at).total_seconds()
        progress = min(elapsed / duree, 1.0) if duree > 0 else 1.0
        return interpoler_sur_waypoints(waypoints, progress)

    elif statut == InterventionStatutEnum.en_cours:
        parts = intervention.geom.split(',')
        return float(parts[0]), float(parts[1])

    elif statut == InterventionStatutEnum.en_retour:
        if not intervention.ended_at or not intervention.prevu_retour_at:
            return None
        waypoints = json.loads(intervention.waypoints_retour_json) if intervention.waypoints_retour_json else None
        if not waypoints:
            return None
        duree = (intervention.prevu_retour_at - intervention.ended_at).total_seconds()
        elapsed = (now - intervention.ended_at).total_seconds()
        progress = min(elapsed / duree, 1.0) if duree > 0 else 1.0
        return interpoler_sur_waypoints(waypoints, progress)

    return None

def to_shape_lat(caserne):
    from geoalchemy2.shape import to_shape
    return to_shape(caserne.geom).y

def to_shape_lon(caserne):
    from geoalchemy2.shape import to_shape
    return to_shape(caserne.geom).x

def progresser_interventions(app):
    with app.app_context():
        from models.personnel import Personnel, PersonnelStatutEnum
        from models.intervention_personnel import InterventionPersonnel
        from geoalchemy2.shape import to_shape
        now = datetime.utcnow()

        # 1. vehicule_envoye → sur_place + en_cours
        for i in Intervention.query.filter(
            Intervention.statut == InterventionStatutEnum.vehicule_envoye,
            Intervention.prevu_sur_place_at != None,
            Intervention.prevu_sur_place_at <= now
        ).all():
            v = Vehicule.query.get(i.vehicule_id)
            if v:
                v.statut = VehiculeStatutEnum.sur_place
            i.statut = InterventionStatutEnum.en_cours
            db.session.commit()

        # 2. en_cours → en_retour
        for i in Intervention.query.filter(
            Intervention.statut == InterventionStatutEnum.en_cours,
            Intervention.prevu_retour_at != None,
            Intervention.prevu_retour_at <= now
        ).all():
            v = Vehicule.query.get(i.vehicule_id) if i.vehicule_id else None
            if v:
                v.statut = VehiculeStatutEnum.en_retour
            i.statut = InterventionStatutEnum.en_retour
            i.ended_at = now

            parts = i.geom.split(',')
            lat_int, lon_int = float(parts[0]), float(parts[1])
            i.retour_lat = lat_int
            i.retour_lon = lon_int

            if i.caserne_id:
                caserne = Caserne.query.get(i.caserne_id)
                if caserne:
                    pt = to_shape(caserne.geom)
                    duree_retour, waypoints_retour = calculer_osrm_complet(
                        lon_int, lat_int, pt.x, pt.y
                    )
                    i.prevu_retour_at = now + timedelta(seconds=duree_retour)
                    i.waypoints_retour_json = json.dumps(waypoints_retour)
            db.session.commit()

        # 3. en_retour → termine + disponible
        for i in Intervention.query.filter(
            Intervention.statut == InterventionStatutEnum.en_retour,
            Intervention.prevu_retour_at != None,
            Intervention.prevu_retour_at <= now
        ).all():
            v = Vehicule.query.get(i.vehicule_id) if i.vehicule_id else None
            if v:
                v.statut = VehiculeStatutEnum.disponible
            liens = InterventionPersonnel.query.filter_by(intervention_id=i.id).all()
            for lien in liens:
                p = Personnel.query.get(lien.personnel_id)
                if p and p.statut == PersonnelStatutEnum.en_intervention:
                    p.statut = PersonnelStatutEnum.disponible
            i.statut = InterventionStatutEnum.termine
            db.session.commit()

def boucle_progression(app):
    while True:
        try:
            progresser_interventions(app)
        except Exception as e:
            print(f"Erreur progression: {e}")
        time.sleep(10)

def creer_intervention_auto(app):
    with app.app_context():
        lat, lon = point_aleatoire_lyon()
        type_i = type_aleatoire()
        caserne = caserne_la_plus_proche(lat, lon)
        vehicule = vehicule_disponible(caserne.id) if caserne else None
        now = datetime.utcnow()

        depart_lat = to_shape_lat(caserne) if caserne else None
        depart_lon = to_shape_lon(caserne) if caserne else None

        duree_trajet, waypoints_aller = calculer_osrm_complet(
            depart_lon, depart_lat, lon, lat
        ) if caserne else (300, [[depart_lat, depart_lon], [lat, lon]])

        duree_sur_place = random.randint(300, 1800) # 5 à 30 minutes

        intervention = Intervention(
            type=type_i,
            statut=InterventionStatutEnum.en_attente,
            adresse=f"Lyon ({lat:.4f}, {lon:.4f})",
            geom=f"{lat},{lon}",
            caserne_id=caserne.id if caserne else None,
            vehicule_id=vehicule.id if vehicule else None,
            created_at=now,
            depart_lat=depart_lat,
            depart_lon=depart_lon,
        )
        db.session.add(intervention)

        if vehicule:
            vehicule.statut = VehiculeStatutEnum.en_route
            intervention.statut = InterventionStatutEnum.vehicule_envoye
            intervention.started_at = now
            intervention.prevu_sur_place_at = now + timedelta(seconds=duree_trajet)
            intervention.prevu_retour_at = now + timedelta(seconds=duree_trajet + duree_sur_place)
            intervention.waypoints_aller_json = json.dumps(waypoints_aller)

        db.session.commit()

def boucle_simulation(app):
    while True:
        try:
            time.sleep(random.randint(600, 1800))
            creer_intervention_auto(app)
        except Exception as e:
            print(f"Erreur simulateur: {e}")

def demarrer_simulateur(app):
    threading.Thread(target=boucle_progression, args=[app], daemon=True).start()
    threading.Thread(target=boucle_simulation, args=[app], daemon=True).start()
    print("✅ Simulateur démarré")