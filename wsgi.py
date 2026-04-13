import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models.objet import Objet
from models.position import Position
from models.statut import Statut
from models.trajet import Trajet
from models.tache import Tache
from models.caserne import Caserne
from models.vehicule import Vehicule
from models.personnel import Personnel
from models.intervention import Intervention
from models.intervention_personnel import InterventionPersonnel

app = create_app()

from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

if __name__ == "__main__":
    app.run()