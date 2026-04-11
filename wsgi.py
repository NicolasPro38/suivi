import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from models.objet import Objet
from models.position import Position
from models.statut import Statut
from models.trajet import Trajet
from models.tache import Tache
from models.caserne import Caserne
from models.vehicule import Vehicule
from models.personnel import Personnel
from models.intervention import Intervention

app = create_app()

from app.services.simulateur import demarrer_simulateur
demarrer_simulateur(app)

if __name__ == "__main__":
    app.run()
