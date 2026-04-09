import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from models.objet import Objet
from models.position import Position
from models.statut import Statut

app = create_app()

if __name__ == "__main__":
    app.run()
