# 🚒 Dispatch Pompiers Lyon

> Projet portfolio — Démonstration d'un outil métier de dispatch et suivi en temps réel des interventions des sapeurs-pompiers sur l'agglomération lyonnaise.

---

## 🎯 Contexte

Ce projet illustre ce qu'un outil de dispatch opérationnel pourrait être pour un SDIS (Service Départemental d'Incendie et de Secours). Il simule la gestion des interventions en temps réel : création, affectation des véhicules et du personnel, suivi cartographique, et retour à la disponibilité.

L'objectif est de démontrer la faisabilité technique d'un tel outil dans un contexte professionnel réel, en combinant des technologies open source éprouvées dans le domaine SIG et du développement web.

---

## ✨ Fonctionnalités clés

- 🗺️ **Carte interactive** — Suivi en temps réel des véhicules sur leurs trajets réels (routage OSRM)
- 🚨 **Création d'interventions** — Clic sur la carte, géocodage automatique, suggestion de la caserne la plus proche
- 🚒 **Dispatch intelligent** — Suggestion automatique des véhicules et personnel adaptés au type d'intervention
- 🔄 **Réaffectation en cours de route** — Un véhicule en retour peut être réaffecté depuis sa position exacte
- 👷 **Gestion du personnel** — Suivi de l'affectation par véhicule, lien persistant pendant le trajet de retour
- ⏱️ **Timers en temps réel** — Chronomètres côté client, indépendants des polls API
- 🏚️ **Données SIG éditables** — Casernes, véhicules et personnel gérables depuis QGIS via PostGIS

---

## 🛠️ Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | Python · Flask · SQLAlchemy |
| Base de données | PostgreSQL · PostGIS · GeoAlchemy2 |
| Cartographie | Leaflet.js · OpenStreetMap |
| Routage | OSRM (Open Source Routing Machine) |
| Migrations | Alembic |
| Données SIG | QGIS (édition directe en base) |
| Déploiement | OVH · Apache |

---

## 📸 Aperçu

*Captures d'écran à venir après déploiement.*

---

## 🔗 Autres projets portfolio

Ce projet fait partie d'une série d'applications de démonstration autour de la cartographie et des outils métier SIG.
