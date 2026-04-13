# 📘 Documentation Technique — Dispatch Pompiers Lyon

---

## Table des matières

1. [Architecture générale](#architecture-générale)
2. [Modèle de données](#modèle-de-données)
3. [Installation locale](#installation-locale)
4. [Configuration](#configuration)
5. [Logique métier](#logique-métier)
6. [API REST](#api-rest)
7. [Gestion des données via QGIS](#gestion-des-données-via-qgis)
8. [Déploiement OVH](#déploiement-ovh)

---

## Architecture générale

```
suivi/
├── app/
│   ├── __init__.py           # Factory Flask + SQLAlchemy
│   ├── routes/
│   │   └── api.py            # Tous les endpoints REST
│   ├── services/
│   │   └── simulateur.py     # Boucles de progression + OSRM
│   └── templates/
│       └── index.html        # SPA Leaflet (HTML/CSS/JS vanilla)
├── models/
│   ├── caserne.py
│   ├── vehicule.py
│   ├── personnel.py
│   ├── intervention.py
│   └── intervention_personnel.py
├── migrations/               # Alembic
├── seed.py                   # Données initiales
├── wsgi.py                   # Point d'entrée
└── config.py
```

**Principe de fonctionnement :**

- Le frontend (Leaflet SPA) poll l'API toutes les 5–15 secondes selon le type de données
- Entre les polls, une animation locale à 100ms interpole les positions des véhicules sur les vrais waypoints OSRM
- Le simulateur tourne en daemon thread et fait progresser les interventions selon des timestamps stockés en base — résistant aux redémarrages Flask
- Les waypoints OSRM sont calculés une seule fois à la création de l'intervention et stockés en JSON dans la base

---

## Modèle de données

### `casernes`
| Colonne | Type | Description |
|---------|------|-------------|
| id | Integer PK | |
| nom | String | Nom de la caserne |
| adresse | String | |
| geom | Geometry(Point, 4326) | Position PostGIS |
| actif | Boolean | Filtre d'affichage |

### `vehicules`
| Colonne | Type | Description |
|---------|------|-------------|
| id | Integer PK | |
| caserne_id | FK → casernes | |
| nom | String | Ex: FPT-1 |
| type | Enum | fpt, vsav, epa, vtu, vlhr, ccu |
| immatriculation | String | |
| statut | Enum | disponible, en_route, sur_place, en_retour, en_maintenance, hors_service |

### `personnel`
| Colonne | Type | Description |
|---------|------|-------------|
| id | Integer PK | |
| caserne_id | FK → casernes | |
| nom, prenom | String | |
| grade | Enum | sapeur, caporal, sergent, adjudant, lieutenant, capitaine |
| statut | Enum | disponible, en_intervention, en_repos, absent |

### `interventions`
| Colonne | Type | Description |
|---------|------|-------------|
| id | Integer PK | |
| type | Enum | 12 types (incendie, secours, fuite gaz...) |
| statut | Enum | en_attente → vehicule_envoye → en_cours → en_retour → termine |
| geom | String (lat,lon) | Position de l'intervention |
| caserne_id | FK | Caserne affectée |
| vehicule_id | FK | Véhicule principal |
| depart_lat/lon | Float | Position réelle de départ du véhicule |
| retour_lat/lon | Float | Position réelle de départ du retour |
| started_at | DateTime | Départ du véhicule |
| ended_at | DateTime | Fin d'intervention |
| prevu_sur_place_at | DateTime | Timestamp d'arrivée calculé OSRM |
| prevu_retour_at | DateTime | Timestamp de fin de retour calculé OSRM |
| waypoints_aller_json | Text | Waypoints OSRM aller (JSON) |
| waypoints_retour_json | Text | Waypoints OSRM retour (JSON) |

### `intervention_personnel`
Table de liaison intervention ↔ personnel, avec `vehicule_id` pour lier le personnel au véhicule (indispensable pour la réaffectation en cours de route).

---

## Installation locale

### Prérequis

- Python 3.9+
- PostgreSQL 14+ avec extension PostGIS
- QGIS (optionnel, pour l'édition des données)

### Étapes

```bash
# 1. Cloner le dépôt
git clone https://github.com/NicolasPro38/suivi.git
cd suivi

# 2. Environnement virtuel
python -m venv venv
source venv/bin/activate

# 3. Dépendances
pip install -r requirements.txt

# 4. Créer la base de données
createdb -U postgres suivi_db
psql -U postgres -d suivi_db -c "CREATE EXTENSION postgis;"

# 5. Variables d'environnement
cp .env.example .env
# Éditer .env avec vos paramètres PostgreSQL

# 6. Migrations
FLASK_APP=wsgi.py flask db upgrade

# 7. Données initiales
python seed.py

# 8. Lancer le serveur
FLASK_APP=wsgi.py flask run --debug
```

L'application est accessible sur `http://127.0.0.1:5000`.

---

## Configuration

Variables d'environnement (fichier `.env`) :

```env
DATABASE_URL=postgresql://postgres:motdepasse@localhost/suivi_db
SECRET_KEY=votre_clé_secrète
```

---

## Logique métier

### Cycle de vie d'une intervention

```
Création (clic carte)
    ↓
OSRM calcule le trajet + durée
Waypoints stockés en base
prevu_sur_place_at = now + durée_trajet
prevu_retour_at = now + durée_trajet + durée_sur_place (300s–1800s)
    ↓
vehicule_envoye / en_route
    ↓ (boucle_progression vérifie prevu_sur_place_at)
en_cours / sur_place
    ↓ (boucle_progression vérifie prevu_retour_at)
OSRM calcule le trajet retour
en_retour
    ↓ (boucle_progression vérifie prevu_retour_at)
termine / disponible
```

### Résistance aux redémarrages

La boucle de progression (`boucle_progression`) tourne en daemon thread et vérifie toutes les 10 secondes les timestamps `prevu_sur_place_at` et `prevu_retour_at` stockés en base. Si Flask redémarre, la boucle reprend exactement là où elle en était — aucun timer en mémoire n'est perdu.

### Réaffectation en cours de route

Quand un véhicule `en_retour` ou `en_route` reçoit une nouvelle intervention :

1. Sa position exacte est calculée en interpolant sur les waypoints OSRM stockés en base
2. Cette position devient le point de départ de la nouvelle intervention
3. OSRM calcule un nouveau trajet depuis ce point exact
4. L'intervention précédente est terminée, le personnel est transféré automatiquement

### Calcul de position

```python
# Interpolation sur waypoints routiers (pas de ligne droite)
progress = elapsed / duree_totale
pos = waypoints[floor(progress * n)] + fraction
```

---

## API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/casernes` | Liste casernes avec stats temps réel |
| GET | `/api/interventions` | Interventions actives |
| POST | `/api/interventions` | Créer une intervention |
| POST | `/api/interventions/<id>/terminer` | Annuler/terminer |
| GET | `/api/vehicules/positions` | Positions + waypoints des véhicules actifs |
| GET | `/api/dispatch/suggestion` | Caserne + véhicules suggérés par position |
| GET | `/api/dispatch/caserne/<id>/disponibles` | Véhicules et personnel dispos |
| GET | `/api/trajet/osrm` | Calcul trajet routier |
| GET | `/api/geocode/reverse` | Géocodage inverse (Nominatim) |
| GET | `/api/geocode/search` | Recherche adresse (API Adresse gouv.fr) |

---

## Gestion des données via QGIS

Les données de référence (casernes, véhicules, personnel) sont stockées dans PostgreSQL/PostGIS et éditables directement depuis QGIS sans toucher au code.

### Connexion QGIS

- **Hôte** : `localhost` (local) ou IP OVH (production)
- **Port** : `5432`
- **Base** : `suivi_db`
- **Utilisateur** : `postgres`

### Ce que les utilisateurs SIG peuvent faire

- **Ajouter une caserne** : créer un point sur la carte dans la couche `casernes`, renseigner `nom`, `adresse`, `actif=true`
- **Déplacer une caserne** : déplacer le point, la carte Leaflet se met à jour immédiatement
- **Ajouter un véhicule** : ajouter une ligne dans la table attributaire `vehicules` avec le bon `caserne_id`
- **Gérer le personnel** : ajouter/modifier dans la table `personnel`

> ⚠️ Supprimer une caserne sans supprimer les véhicules et personnel associés laissera des enregistrements orphelins. Toujours supprimer dans l'ordre : personnel → véhicules → caserne.

---

## Déploiement OVH

*Documentation à compléter après déploiement.*

Le déploiement cible un serveur OVH avec Apache et mod_wsgi, dans la continuité des autres applications du portfolio hébergées sur `cartonicolasrey.duckdns.org`.
