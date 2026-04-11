from flask import Blueprint, jsonify, request
from models.caserne import Caserne
from models.vehicule import Vehicule, VehiculeStatutEnum
from models.personnel import Personnel
from models.intervention import Intervention, InterventionTypeEnum, InterventionStatutEnum
from geoalchemy2.shape import to_shape
from app import db
from datetime import datetime

# Véhicules recommandés par type d'intervention
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
            'nb_vehicules_dispo': Vehicule.query.filter_by(caserne_id=c.id, statut='disponible').count(),
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
    from models.caserne import Caserne
    statut = request.args.get('statut')
    query = Intervention.query
    if statut:
        query = query.filter_by(statut=statut)
    else:
        query = query.filter(
            Intervention.statut != InterventionStatutEnum.termine,
            Intervention.statut != InterventionStatutEnum.annule
        )
    interventions = query.order_by(Intervention.created_at.desc()).all()
    result = []
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

    # Premier véhicule = véhicule principal de l'intervention
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

    # Mettre TOUS les véhicules sélectionnés en route
    for vid in vehicules_ids:
        v = Vehicule.query.get(vid)
        if v:
            v.statut = VehiculeStatutEnum.en_route

    # Mettre TOUT le personnel sélectionné en intervention
    for pid in personnel_ids:
        p = Personnel.query.get(pid)
        if p:
            p.statut = PersonnelStatutEnum.en_intervention

    if vehicule_principal:
        intervention.statut = InterventionStatutEnum.vehicule_envoye
        intervention.started_at = datetime.utcnow()

    db.session.commit()
    return jsonify(intervention.to_dict()), 201

@api.route('/interventions/<int:intervention_id>/terminer', methods=['POST'])
def terminer_intervention(intervention_id):
    from models.personnel import Personnel, PersonnelStatutEnum
    intervention = Intervention.query.get_or_404(intervention_id)

    # Remettre le véhicule principal en retour
    if intervention.vehicule_id:
        vehicule = Vehicule.query.get(intervention.vehicule_id)
        if vehicule:
            vehicule.statut = VehiculeStatutEnum.en_retour

    # Remettre tout le personnel en disponible
    if intervention.caserne_id:
        personnels_en_intervention = Personnel.query.filter_by(
            caserne_id=intervention.caserne_id,
            statut=PersonnelStatutEnum.en_intervention
        ).all()
        for p in personnels_en_intervention:
            p.statut = PersonnelStatutEnum.disponible

    intervention.statut = InterventionStatutEnum.termine
    intervention.ended_at = datetime.utcnow()
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
        adresse = data.get('display_name', f"Lyon ({lat}, {lon})")
        # Simplifie l'adresse : numéro + rue + ville
        addr = data.get('address', {})
        courte = ', '.join(filter(None, [
            addr.get('house_number', ''),
            addr.get('road', ''),
            addr.get('city', addr.get('town', 'Lyon'))
        ]))
        return jsonify({'adresse': courte or adresse})
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

    from geoalchemy2.shape import to_shape
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

    # Types recommandés pour ce type d'intervention
    types_recommandes = VEHICULES_RECOMMANDES.get(type_intervention, [])

    # Véhicules disponibles
    vehicules_dispo = Vehicule.query.filter_by(
        caserne_id=caserne.id,
        statut=VehiculeStatutEnum.disponible
    ).all()

    # Véhicules en retour
    vehicules_retour = Vehicule.query.filter_by(
        caserne_id=caserne.id,
        statut=VehiculeStatutEnum.en_retour
    ).all()

    def vehicule_to_dict_enrichi(v, en_retour=False):
        d = v.to_dict()
        d['recommande'] = v.type.value in types_recommandes
        d['en_retour'] = en_retour
        d['priorite'] = 0
        if v.type.value in types_recommandes:
            d['priorite'] = 2 if not en_retour else 1
        return d

    vehicules = []
    # D'abord les disponibles recommandés
    for v in vehicules_dispo:
        vehicules.append(vehicule_to_dict_enrichi(v, False))
    # Ensuite les en_retour
    for v in vehicules_retour:
        vehicules.append(vehicule_to_dict_enrichi(v, True))

    # Trier par priorité décroissante
    vehicules.sort(key=lambda x: x['priorite'], reverse=True)

    personnel = Personnel.query.filter_by(
        caserne_id=caserne.id,
        statut=PersonnelStatutEnum.disponible
    ).all()

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

    vehicules_dispo = Vehicule.query.filter_by(
        caserne_id=caserne_id,
        statut=VehiculeStatutEnum.disponible
    ).all()
    vehicules_retour = Vehicule.query.filter_by(
        caserne_id=caserne_id,
        statut=VehiculeStatutEnum.en_retour
    ).all()

    def enrichir(v, en_retour=False):
        d = v.to_dict()
        d['recommande'] = v.type.value in types_recommandes
        d['en_retour'] = en_retour
        d['priorite'] = 0
        if v.type.value in types_recommandes:
            d['priorite'] = 2 if not en_retour else 1
        return d

    vehicules = [enrichir(v) for v in vehicules_dispo] + [enrichir(v, True) for v in vehicules_retour]
    vehicules.sort(key=lambda x: x['priorite'], reverse=True)

    personnel = Personnel.query.filter_by(
        caserne_id=caserne_id,
        statut=PersonnelStatutEnum.disponible
    ).all()

    return jsonify({
        'vehicules': vehicules,
        'personnel': [p.to_dict() for p in personnel]
    })
