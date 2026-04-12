from flask import Blueprint, jsonify, request
from models.caserne import Caserne
from models.vehicule import Vehicule, VehiculeStatutEnum
from models.personnel import Personnel
from models.intervention import Intervention, InterventionTypeEnum, InterventionStatutEnum
from geoalchemy2.shape import to_shape
from app import db
from datetime import datetime
from models.intervention_personnel import InterventionPersonnel
from app.services.simulateur import DUREE_TRAJET
import random

VEHICULES_RECOMMANDES = {
    'incendie_batiment':  ['fpt', 'epa', 'vsav'],
    'incendie_vehicule':  ['fpt', 'vsav'],
    'incendie_objet':     ['fpt', 'vtu'],
    'incendie_foret':     ['fpt', 'vlhr'],
    'secours_personne':   ['vsav'],
    'accident_route':     ['vsav', 'fpt'],
    'fuite_gaz':          ['fpt', 'vtu'],
    'inondation':         ['fpt', 'vtu'],
    'ouverture_porte':    ['vtu'],
    'sauvetage_animal':   ['vtu'],
    'risque_chimique':    ['ccu', 'fpt', 'vsav'],
    'constat_deces':      ['vsav', 'vtu'],
}

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/casernes', methods=['GET'])
def get_casernes():
    casernes = Caserne.query.filter_by(actif=True).all()
    result = []
    for c in casernes:
        point = to_shape(c.geom)
        result.append({
            'id': c.id,
            'nom': c.nom,
            'adresse': c.adresse,
            'lat': point.y,
            'lon': point.x,
            'nb_vehicules': Vehicule.query.filter_by(caserne_id=c.id).count(),
            'nb_personnel': Personnel.query.filter_by(caserne_id=c.id).count(),
            'nb_vehicules_dispo': Vehicule.query.filter(
                Vehicule.caserne_id == c.id,
                Vehicule.statut.in_([VehiculeStatutEnum.disponible, VehiculeStatutEnum.en_retour])
            ).count(),
            'nb_personnel_dispo': Personnel.query.filter_by(caserne_id=c.id, statut='disponible').count(),
        })
    return jsonify(result)

@api.route('/casernes/<int:caserne_id>/vehicules', methods=['GET'])
def get_vehicules(caserne_id):
    vehicules = Vehicule.query.filter_by(caserne_id=caserne_id).all()
    return jsonify([v.to_dict() for v in vehicules])

@api.route('/casernes/<int:caserne_id>/personnel', methods=['GET'])
def get_personnel(caserne_id):
    personnel = Personnel.query.filter_by(caserne_id=caserne_id).all()
    return jsonify([p.to_dict() for p in personnel])

@api.route('/interventions', methods=['GET'])
def get_interventions():
    statut = request.args.get('statut')
    query = Intervention.query
    if statut:
        query = query.filter_by(statut=statut)
    else:
        query = query.filter(
            Intervention.statut != InterventionStatutEnum.termine,
            Intervention.statut != InterventionStatutEnum.annule,
            Intervention.statut != InterventionStatutEnum.en_retour
        )
    interventions = query.order_by(Intervention.created_at.desc()).all()
    result = []
    now = datetime.utcnow()
    for i in interventions:
        d = i.to_dict()
        if i.vehicule_id:
            v = Vehicule.query.get(i.vehicule_id)
            d['vehicule'] = f"{v.type.value.upper()} - {v.nom}" if v else None
        else:
            d['vehicule'] = None
        if i.caserne_id:
            c = Caserne.query.get(i.caserne_id)
            d['caserne_nom'] = c.nom if c else None
        else:
            d['caserne_nom'] = None

        liens = InterventionPersonnel.query.filter_by(intervention_id=i.id).all()
        personnel_list = []
        for lien in liens:
            p = Personnel.query.get(lien.personnel_id)
            if p:
                personnel_list.append(p.grade.value + ' ' + p.prenom + ' ' + p.nom)
        d['personnel'] = personnel_list

        # Timestamps pour les timers côté client
        d['started_at_ts'] = i.started_at.isoformat() if i.started_at else None
        d['ended_at_ts'] = i.ended_at.isoformat() if i.ended_at else None
        d['created_at_ts'] = i.created_at.isoformat() if i.created_at else None
        d['server_now_ts'] = now.isoformat()

        result.append(d)
    return jsonify(result)

@api.route('/interventions', methods=['POST'])
def creer_intervention():
    data = request.get_json()
    from models.personnel import Personnel, PersonnelStatutEnum
    lat = float(data['lat'])
    lon = float(data['lon'])
    caserne_id = data.get('caserne_id')
    vehicules_ids = [int(v) for v in data.get('vehicules_ids', [])]
    personnel_ids = [int(p) for p in data.get('personnel_ids', [])]

    vehicule_principal = None
    if vehicules_ids:
        vehicule_principal = Vehicule.query.get(vehicules_ids[0])

    intervention = Intervention(
        type=InterventionTypeEnum[data['type']],
        statut=InterventionStatutEnum.en_attente,
        adresse=data.get('adresse', f"Lyon ({lat:.4f}, {lon:.4f})"),
        geom=f"{lat},{lon}",
        caserne_id=int(caserne_id) if caserne_id else None,
        vehicule_id=vehicule_principal.id if vehicule_principal else None,
        created_at=datetime.utcnow()
    )
    db.session.add(intervention)
    db.session.flush()

    for vid in vehicules_ids:
        v = Vehicule.query.get(vid)
        if v:
            v.statut = VehiculeStatutEnum.en_route

    for pid in personnel_ids:
        p = Personnel.query.get(pid)
        if p:
            p.statut = PersonnelStatutEnum.en_intervention
            lien = InterventionPersonnel(
                intervention_id=intervention.id,
                personnel_id=pid,
                vehicule_id=vehicule_principal.id if vehicule_principal else None
            )
            db.session.add(lien)

    if vehicule_principal:
        intervention.statut = InterventionStatutEnum.vehicule_envoye
        intervention.started_at = datetime.utcnow()

    db.session.commit()

    if vehicule_principal:
        from app.services.simulateur import passer_sur_place, passer_en_retour
        from flask import current_app
        import threading
        import requests as req
        app_obj = current_app._get_current_object()

        try:
            caserne = Caserne.query.get(int(caserne_id))
            pt = to_shape(caserne.geom)
            osrm_url = f"http://router.project-osrm.org/route/v1/driving/{pt.x},{pt.y};{lon},{lat}"
            r = req.get(osrm_url, params={'overview': 'false'}, timeout=5)
            duree_trajet_sec = r.json()['routes'][0]['duration']
        except:
            duree_trajet_sec = 5 * 60

        duree_sur_place_sec = random.randint(30, 120)

        threading.Timer(
            duree_trajet_sec,
            passer_sur_place,
            args=[intervention.id, vehicule_principal.id, app_obj]
        ).start()

        threading.Timer(
            duree_trajet_sec + duree_sur_place_sec,
            passer_en_retour,
            args=[intervention.id, app_obj]
        ).start()

    return jsonify(intervention.to_dict()), 201

@api.route('/interventions/<int:intervention_id>/terminer', methods=['POST'])
def terminer_intervention(intervention_id):
    from models.personnel import Personnel, PersonnelStatutEnum
    from app.services.simulateur import vehicule_disponible_apres_retour
    from flask import current_app
    import threading
    intervention = Intervention.query.get_or_404(intervention_id)

    if intervention.vehicule_id:
        vehicule = Vehicule.query.get(intervention.vehicule_id)
        if vehicule:
            vehicule.statut = VehiculeStatutEnum.en_retour

    intervention.statut = InterventionStatutEnum.en_retour
    intervention.ended_at = datetime.utcnow()
    db.session.commit()

    # Lancer le timer de retour
    if intervention.vehicule_id:
        app_obj = current_app._get_current_object()
        threading.Timer(
            DUREE_TRAJET * 60,
            vehicule_disponible_apres_retour,
            args=[intervention.vehicule_id, app_obj]
        ).start()

    return jsonify(intervention.to_dict())

@api.route('/geocode/reverse', methods=['GET'])
def geocode_reverse():
    import requests
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    try:
        r = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lon, 'format': 'json'},
            headers={'User-Agent': 'DispatchPompiers/1.0'}
        )
        data = r.json()
        addr = data.get('address', {})
        courte = ', '.join(filter(None, [
            addr.get('house_number', ''),
            addr.get('road', ''),
            addr.get('city', addr.get('town', 'Lyon'))
        ]))
        return jsonify({'adresse': courte or data.get('display_name', f"Lyon ({lat}, {lon})")})
    except:
        return jsonify({'adresse': f"Lyon ({float(lat):.4f}, {float(lon):.4f})"})

@api.route('/geocode/search', methods=['GET'])
def geocode_search():
    import requests
    q = request.args.get('q')
    try:
        r = requests.get(
            'https://api-adresse.data.gouv.fr/search/',
            params={'q': q, 'citycode': '69123', 'limit': 6}
        )
        data = r.json()
        results = [{
            'adresse': f.get('properties', {}).get('label', ''),
            'lat': f['geometry']['coordinates'][1],
            'lon': f['geometry']['coordinates'][0]
        } for f in data.get('features', [])]
        return jsonify(results)
    except:
        return jsonify([])

@api.route('/dispatch/suggestion', methods=['GET'])
def dispatch_suggestion():
    from app.services.simulateur import caserne_la_plus_proche
    from models.personnel import Personnel, PersonnelStatutEnum
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    type_intervention = request.args.get('type', '')

    caserne = caserne_la_plus_proche(lat, lon)
    if not caserne:
        return jsonify({'error': 'Aucune caserne disponible'}), 404

    toutes = Caserne.query.filter_by(actif=True).all()
    casernes_list = []
    for c in toutes:
        pt = to_shape(c.geom)
        casernes_list.append({
            'id': c.id,
            'nom': c.nom,
            'distance_km': round(((pt.y - lat)**2 + (pt.x - lon)**2)**0.5 * 111, 2),
            'suggested': c.id == caserne.id
        })
    casernes_list.sort(key=lambda x: x['distance_km'])

    types_recommandes = VEHICULES_RECOMMANDES.get(type_intervention, [])
    vehicules_dispo = Vehicule.query.filter_by(caserne_id=caserne.id, statut=VehiculeStatutEnum.disponible).all()
    vehicules_retour = Vehicule.query.filter_by(caserne_id=caserne.id, statut=VehiculeStatutEnum.en_retour).all()

    def vehicule_to_dict_enrichi(v, en_retour=False):
        d = v.to_dict()
        d['recommande'] = v.type.value in types_recommandes
        d['en_retour'] = en_retour
        d['priorite'] = 2 if v.type.value in types_recommandes and not en_retour else (1 if v.type.value in types_recommandes else 0)
        return d

    vehicules = [vehicule_to_dict_enrichi(v) for v in vehicules_dispo] + [vehicule_to_dict_enrichi(v, True) for v in vehicules_retour]
    vehicules.sort(key=lambda x: x['priorite'], reverse=True)
    personnel = Personnel.query.filter_by(caserne_id=caserne.id, statut=PersonnelStatutEnum.disponible).all()

    return jsonify({
        'caserne_suggeree': caserne.id,
        'casernes': casernes_list,
        'vehicules': vehicules,
        'personnel': [p.to_dict() for p in personnel]
    })

@api.route('/dispatch/caserne/<int:caserne_id>/disponibles', methods=['GET'])
def disponibles_caserne(caserne_id):
    from models.personnel import Personnel, PersonnelStatutEnum
    type_intervention = request.args.get('type', '')
    types_recommandes = VEHICULES_RECOMMANDES.get(type_intervention, [])

    vehicules_dispo = Vehicule.query.filter_by(caserne_id=caserne_id, statut=VehiculeStatutEnum.disponible).all()
    vehicules_retour = Vehicule.query.filter_by(caserne_id=caserne_id, statut=VehiculeStatutEnum.en_retour).all()

    def enrichir(v, en_retour=False):
        d = v.to_dict()
        d['recommande'] = v.type.value in types_recommandes
        d['en_retour'] = en_retour
        d['priorite'] = 2 if v.type.value in types_recommandes and not en_retour else (1 if v.type.value in types_recommandes else 0)
        # Personnel lié à ce véhicule si en retour
        if en_retour:
            liens = InterventionPersonnel.query.filter_by(vehicule_id=v.id).join(
                Intervention, InterventionPersonnel.intervention_id == Intervention.id
            ).filter(
                Intervention.statut == InterventionStatutEnum.en_retour
            ).all()
            d['personnel_lie'] = [lien.personnel_id for lien in liens]
        else:
            d['personnel_lie'] = []
        return d

    vehicules = [enrichir(v) for v in vehicules_dispo] + [enrichir(v, True) for v in vehicules_retour]
    vehicules.sort(key=lambda x: x['priorite'], reverse=True)

    personnel_dispo = Personnel.query.filter_by(caserne_id=caserne_id, statut=PersonnelStatutEnum.disponible).all()

    # Personnel en retour lié à un véhicule de cette caserne
    personnel_retour = []
    for v in vehicules_retour:
        liens = InterventionPersonnel.query.filter_by(vehicule_id=v.id).join(
            Intervention, InterventionPersonnel.intervention_id == Intervention.id
        ).filter(
            Intervention.statut == InterventionStatutEnum.en_retour
        ).all()
        for lien in liens:
            p = Personnel.query.get(lien.personnel_id)
            if p:
                pd = p.to_dict()
                pd['en_retour'] = True
                pd['vehicule_id_lie'] = v.id
                personnel_retour.append(pd)

    personnel_final = [p.to_dict() for p in personnel_dispo] + personnel_retour

    return jsonify({'vehicules': vehicules, 'personnel': personnel_final})

@api.route('/trajet/osrm', methods=['GET'])
def get_trajet_osrm():
    import requests
    lat1 = request.args.get('lat1')
    lon1 = request.args.get('lon1')
    lat2 = request.args.get('lat2')
    lon2 = request.args.get('lon2')
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        r = requests.get(url, params={'overview': 'full', 'geometries': 'geojson'})
        data = r.json()
        coords = data['routes'][0]['geometry']['coordinates']
        waypoints = [[c[1], c[0]] for c in coords]
        duree = data['routes'][0]['duration']
        return jsonify({'waypoints': waypoints, 'duree': duree})
    except:
        return jsonify({'waypoints': [[float(lat1), float(lon1)], [float(lat2), float(lon2)]], 'duree': 300})

@api.route('/vehicules/positions', methods=['GET'])
def get_vehicules_positions():
    import requests as req
    interventions_actives = Intervention.query.filter(
        Intervention.statut.in_([
            InterventionStatutEnum.vehicule_envoye,
            InterventionStatutEnum.en_cours,
            InterventionStatutEnum.en_retour
        ]),
        Intervention.vehicule_id != None,
        Intervention.caserne_id != None
    ).all()

    result = []
    for i in interventions_actives:
        vehicule = Vehicule.query.get(i.vehicule_id)
        caserne = Caserne.query.get(i.caserne_id)
        if not vehicule or not caserne:
            continue

        pt_caserne = to_shape(caserne.geom)
        lat_caserne = pt_caserne.y
        lon_caserne = pt_caserne.x

        parts = i.geom.split(',')
        lat_int = float(parts[0])
        lon_int = float(parts[1])

        now = datetime.utcnow()

        if vehicule.statut == VehiculeStatutEnum.en_route and i.started_at:
            elapsed = (now - i.started_at).total_seconds()
            try:
                osrm_url = f"http://router.project-osrm.org/route/v1/driving/{lon_caserne},{lat_caserne};{lon_int},{lat_int}"
                r = req.get(osrm_url, params={'overview': 'false'}, timeout=3)
                duree_trajet = r.json()['routes'][0]['duration']
            except:
                duree_trajet = 300
            progress = min(elapsed / duree_trajet, 1.0)
            lat = lat_caserne + (lat_int - lat_caserne) * progress
            lon = lon_caserne + (lon_int - lon_caserne) * progress
            etat = 'en_route'
            elapsed_sec = elapsed
            duree_trajet_sec = duree_trajet

        elif vehicule.statut == VehiculeStatutEnum.sur_place:
            lat = lat_int
            lon = lon_int
            etat = 'sur_place'
            elapsed_sec = 0
            duree_trajet_sec = 300

        elif vehicule.statut == VehiculeStatutEnum.en_retour and i.ended_at:
            elapsed = (now - i.ended_at).total_seconds()
            try:
                osrm_url = f"http://router.project-osrm.org/route/v1/driving/{lon_int},{lat_int};{lon_caserne},{lat_caserne}"
                r = req.get(osrm_url, params={'overview': 'false'}, timeout=3)
                duree_trajet = r.json()['routes'][0]['duration']
            except:
                duree_trajet = 300
            progress = min(elapsed / duree_trajet, 1.0)
            lat = lat_int + (lat_caserne - lat_int) * progress
            lon = lon_int + (lon_caserne - lon_int) * progress
            etat = 'en_retour'
            elapsed_sec = elapsed
            duree_trajet_sec = duree_trajet
        else:
            continue

        result.append({
            'vehicule_id': vehicule.id,
            'vehicule_nom': vehicule.nom,
            'vehicule_type': vehicule.type.value,
            'intervention_id': i.id,
            'intervention_type': i.type.value,
            'etat': etat,
            'lat': lat,
            'lon': lon,
            'elapsed_sec': elapsed_sec,
            'duree_trajet_sec': duree_trajet_sec,
            'started_at_ts': i.started_at.isoformat() if i.started_at else None,
            'lat_intervention': lat_int,
            'lon_intervention': lon_int,
            'lat_caserne': lat_caserne,
            'lon_caserne': lon_caserne,
            'caserne_nom': caserne.nom
        })

    return jsonify(result)