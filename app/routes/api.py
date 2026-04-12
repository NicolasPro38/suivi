import json
import random
from flask import Blueprint, jsonify, request
from models.caserne import Caserne
from models.vehicule import Vehicule, VehiculeStatutEnum
from models.personnel import Personnel
from models.intervention import Intervention, InterventionTypeEnum, InterventionStatutEnum
from geoalchemy2.shape import to_shape
from app import db
from datetime import datetime, timedelta
from models.intervention_personnel import InterventionPersonnel

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
        d['started_at_ts'] = i.started_at.isoformat() if i.started_at else None
        d['ended_at_ts'] = i.ended_at.isoformat() if i.ended_at else None
        d['created_at_ts'] = i.created_at.isoformat() if i.created_at else None
        d['prevu_sur_place_at_ts'] = i.prevu_sur_place_at.isoformat() if i.prevu_sur_place_at else None
        d['server_now_ts'] = now.isoformat()
        result.append(d)
    return jsonify(result)

@api.route('/interventions', methods=['POST'])
def creer_intervention():
    data = request.get_json()
    from models.personnel import Personnel, PersonnelStatutEnum
    from app.services.simulateur import calculer_osrm_complet, get_position_sur_waypoints
    lat = float(data['lat'])
    lon = float(data['lon'])
    caserne_id = data.get('caserne_id')
    vehicules_ids = [int(v) for v in data.get('vehicules_ids', [])]
    personnel_ids = [int(p) for p in data.get('personnel_ids', [])]

    vehicule_principal = None
    if vehicules_ids:
        vehicule_principal = Vehicule.query.get(vehicules_ids[0])

    depart_lat = None
    depart_lon = None
    now_ts = datetime.utcnow()

    # Véhicule en retour ou en route → position exacte sur waypoints
    if vehicule_principal and vehicule_principal.statut in [
        VehiculeStatutEnum.en_retour, VehiculeStatutEnum.en_route
    ]:
        statut_recherche = (
            InterventionStatutEnum.en_retour
            if vehicule_principal.statut == VehiculeStatutEnum.en_retour
            else InterventionStatutEnum.vehicule_envoye
        )
        intervention_precedente = Intervention.query.filter_by(
            vehicule_id=vehicule_principal.id,
            statut=statut_recherche
        ).first()

        if intervention_precedente:
            pos = get_position_sur_waypoints(intervention_precedente, now_ts)
            if pos:
                depart_lat, depart_lon = pos[0], pos[1]
            else:
                # Fallback caserne
                if intervention_precedente.caserne_id:
                    c = Caserne.query.get(intervention_precedente.caserne_id)
                    if c:
                        pt = to_shape(c.geom)
                        depart_lat, depart_lon = pt.y, pt.x

            intervention_precedente.statut = InterventionStatutEnum.termine
            db.session.commit()

            liens_prec = InterventionPersonnel.query.filter_by(
                intervention_id=intervention_precedente.id
            ).all()
            for l in liens_prec:
                if l.personnel_id not in personnel_ids:
                    personnel_ids.append(l.personnel_id)

    # Fallback : caserne
    if depart_lat is None and caserne_id:
        caserne = Caserne.query.get(int(caserne_id))
        if caserne:
            pt = to_shape(caserne.geom)
            depart_lat, depart_lon = pt.y, pt.x

    # Calculer trajet OSRM complet et stocker les waypoints
    duree_trajet_sec, waypoints_aller = calculer_osrm_complet(
        depart_lon, depart_lat, lon, lat
    )
    duree_sur_place_sec = random.randint(30, 120)

    intervention = Intervention(
        type=InterventionTypeEnum[data['type']],
        statut=InterventionStatutEnum.en_attente,
        adresse=data.get('adresse', f"Lyon ({lat:.4f}, {lon:.4f})"),
        geom=f"{lat},{lon}",
        caserne_id=int(caserne_id) if caserne_id else None,
        vehicule_id=vehicule_principal.id if vehicule_principal else None,
        created_at=now_ts,
        depart_lat=depart_lat,
        depart_lon=depart_lon,
        waypoints_aller_json=json.dumps(waypoints_aller)
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
        intervention.started_at = now_ts
        intervention.prevu_sur_place_at = now_ts + timedelta(seconds=duree_trajet_sec)
        intervention.prevu_retour_at = now_ts + timedelta(seconds=duree_trajet_sec + duree_sur_place_sec)

    db.session.commit()
    return jsonify(intervention.to_dict()), 201

@api.route('/interventions/<int:intervention_id>/terminer', methods=['POST'])
def terminer_intervention(intervention_id):
    from app.services.simulateur import calculer_osrm_complet, get_position_sur_waypoints
    intervention = Intervention.query.get_or_404(intervention_id)
    now_ts = datetime.utcnow()

    # Position exacte sur waypoints au moment du clic
    pos = get_position_sur_waypoints(intervention, now_ts)
    if pos:
        retour_lat, retour_lon = pos[0], pos[1]
    else:
        parts = intervention.geom.split(',')
        retour_lat, retour_lon = float(parts[0]), float(parts[1])

    if intervention.vehicule_id:
        vehicule = Vehicule.query.get(intervention.vehicule_id)
        if vehicule:
            vehicule.statut = VehiculeStatutEnum.en_retour

    intervention.statut = InterventionStatutEnum.en_retour
    intervention.ended_at = now_ts
    intervention.retour_lat = retour_lat
    intervention.retour_lon = retour_lon

    # Calculer trajet retour OSRM complet depuis position actuelle
    if intervention.caserne_id:
        caserne = Caserne.query.get(intervention.caserne_id)
        if caserne:
            pt = to_shape(caserne.geom)
            duree_retour, waypoints_retour = calculer_osrm_complet(
                retour_lon, retour_lat, pt.x, pt.y
            )
            intervention.prevu_retour_at = now_ts + timedelta(seconds=duree_retour)
            intervention.waypoints_retour_json = json.dumps(waypoints_retour)

    db.session.commit()
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
        if en_retour:
            liens = InterventionPersonnel.query.filter_by(vehicule_id=v.id).join(
                Intervention, InterventionPersonnel.intervention_id == Intervention.id
            ).filter(Intervention.statut == InterventionStatutEnum.en_retour).all()
            d['personnel_lie'] = [lien.personnel_id for lien in liens]
        else:
            d['personnel_lie'] = []
        return d

    vehicules = [enrichir(v) for v in vehicules_dispo] + [enrichir(v, True) for v in vehicules_retour]
    vehicules.sort(key=lambda x: x['priorite'], reverse=True)

    personnel_dispo = Personnel.query.filter_by(caserne_id=caserne_id, statut=PersonnelStatutEnum.disponible).all()
    personnel_retour = []
    for v in vehicules_retour:
        liens = InterventionPersonnel.query.filter_by(vehicule_id=v.id).join(
            Intervention, InterventionPersonnel.intervention_id == Intervention.id
        ).filter(Intervention.statut == InterventionStatutEnum.en_retour).all()
        for lien in liens:
            p = Personnel.query.get(lien.personnel_id)
            if p:
                pd = p.to_dict()
                pd['en_retour'] = True
                pd['vehicule_id_lie'] = v.id
                personnel_retour.append(pd)

    return jsonify({'vehicules': vehicules, 'personnel': [p.to_dict() for p in personnel_dispo] + personnel_retour})

@api.route('/trajet/osrm', methods=['GET'])
def get_trajet_osrm():
    from app.services.simulateur import calculer_osrm_complet
    lat1 = request.args.get('lat1')
    lon1 = request.args.get('lon1')
    lat2 = request.args.get('lat2')
    lon2 = request.args.get('lon2')
    duree, waypoints = calculer_osrm_complet(float(lon1), float(lat1), float(lon2), float(lat2))
    return jsonify({'waypoints': waypoints, 'duree': duree})

@api.route('/vehicules/positions', methods=['GET'])
def get_vehicules_positions():
    from app.services.simulateur import get_position_sur_waypoints, interpoler_sur_waypoints

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
    now = datetime.utcnow()

    for i in interventions_actives:
        vehicule = Vehicule.query.get(i.vehicule_id)
        caserne = Caserne.query.get(i.caserne_id)
        if not vehicule or not caserne:
            continue

        pt_caserne = to_shape(caserne.geom)
        lat_caserne, lon_caserne = pt_caserne.y, pt_caserne.x
        parts = i.geom.split(',')
        lat_int, lon_int = float(parts[0]), float(parts[1])

        pos = get_position_sur_waypoints(i, now)
        if not pos:
            continue
        lat, lon = pos[0], pos[1]

        if vehicule.statut == VehiculeStatutEnum.en_route and i.started_at and i.prevu_sur_place_at:
            duree = (i.prevu_sur_place_at - i.started_at).total_seconds()
            elapsed = (now - i.started_at).total_seconds()
            etat = 'en_route'
            elapsed_sec = elapsed
            duree_trajet_sec = duree
            waypoints = json.loads(i.waypoints_aller_json) if i.waypoints_aller_json else []

        elif vehicule.statut == VehiculeStatutEnum.sur_place:
            etat = 'sur_place'
            elapsed_sec = 0
            duree_trajet_sec = 0
            waypoints = []

        elif vehicule.statut == VehiculeStatutEnum.en_retour and i.ended_at and i.prevu_retour_at:
            duree = (i.prevu_retour_at - i.ended_at).total_seconds()
            elapsed = (now - i.ended_at).total_seconds()
            etat = 'en_retour'
            elapsed_sec = elapsed
            duree_trajet_sec = duree
            waypoints = json.loads(i.waypoints_retour_json) if i.waypoints_retour_json else []
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
            'waypoints': waypoints,
            'lat_intervention': lat_int,
            'lon_intervention': lon_int,
            'lat_caserne': lat_caserne,
            'lon_caserne': lon_caserne,
            'caserne_nom': caserne.nom
        })

    return jsonify(result)