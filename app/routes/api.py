from flask import Blueprint, jsonify
from models.caserne import Caserne
from models.vehicule import Vehicule
from models.personnel import Personnel
from geoalchemy2.shape import to_shape

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
