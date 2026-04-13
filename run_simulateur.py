import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
app = create_app()

from app.services.simulateur import demarrer_simulateur
demarrer_simulateur(app)

# Garder le processus vivant
import time
while True:
    time.sleep(60)