# Kayak - Recommandation de Destinations Françaises

> *Pipeline Data Engineering complet : API Météo → Scraping Booking.com → AWS S3 → AWS RDS*

[![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python)](https://www.python.org/)
[![AWS S3](https://img.shields.io/badge/AWS-S3-FF9900?logo=amazonaws)](https://aws.amazon.com/s3/)
[![AWS RDS](https://img.shields.io/badge/AWS-RDS-FF9900?logo=amazonaws)](https://aws.amazon.com/rds/)
[![Plotly](https://img.shields.io/badge/Plotly-Maps-3F4F75?logo=plotly)](https://plotly.com/)

---

## Objectif

Construire un pipeline de données end-to-end pour recommander aux utilisateurs Kayak les meilleures destinations françaises selon la météo et la qualité des hôtels.

---

## Architecture

```
Nominatim API          → Coordonnées GPS (35 villes)
        ↓
OpenWeatherMap API     → Prévisions météo 7 jours
        ↓
Score météo composite  → Classement des destinations
        ↓
Google Places API      → Hôtels (699, notes réelles)
        ↓
AWS S3 (Data Lake)     → Stockage raw + processed
        ↓
AWS RDS (PostgreSQL)   → Data Warehouse requêtable
        ↓
Plotly Maps            → 2 cartes interactives
```

---

## Résultats

### Top 5 Destinations (Score Météo)

| Rang | Ville | Score | Temp. moy | Pluie |
|---|---|---|---|---|
| 1 | **Collioure** | 85.9 | 17.6°C | 0% |
| 2 | **Nîmes** | 84.4 | 16.6°C | 0% |
| 3 | **Bayonne** | 83.0 | 16.5°C | 0% |
| 4 | **Avignon** | 82.2 | 15.8°C | 0% |
| 5 | **Uzès** | 81.6 | 15.8°C | 0% |

---

## Structure du projet

```
kayak/
├── data/
│   ├── weather_france_cities.csv     # Scores météo des 35 villes
│   ├── weather_daily_details.csv     # Météo journalière (35 × 7 jours)
│   ├── hotels.csv                    # Hôtels scrapés Booking.com
│   ├── final_kayak_data.csv          # Dataset consolidé final
│   └── kayak_destinations.csv        # Top destinations avec coordonnées
├── notebooks/
│   └── kayak_final.ipynb             # Notebook consolidé : météo, hôtels, géocodage, ETL, cartes
├── src/
│   ├── kayak_part1_weather.py        # Collecte météo (Nominatim + OpenWeatherMap)
│   ├── kayak_part2_scraping.py       # Scraping hôtels (BeautifulSoup)
│   └── kayak_part3_etl.py            # ETL S3 → RDS PostgreSQL
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Score Météo Composite

| Critère | Poids | Logique |
|---|---|---|
| Température | 40% | Gaussienne centrée sur 22°C |
| Probabilité de pluie | 35% | 1 − pop (OpenWeatherMap) |
| Humidité | 15% | Idéale entre 40 et 60% |
| Vent | 10% | Décroissant exponentiellement |

---

## Installation

```bash
git clone https://github.com/MartialBayom/kayak-data-engineering.git
cd kayak-data-engineering
pip install -r requirements.txt
cp .env.example .env
# Remplir .env avec vos clés API et credentials AWS
jupyter notebook notebooks/kayak_final.ipynb
```

---

## APIs & Services utilisés

| Service | Usage |
|---|---|
| Nominatim | Géocodage GPS des 35 villes |
| OpenWeatherMap | Prévisions météo 7 jours |
| Booking.com | Scraping hôtels (BeautifulSoup) |
| AWS S3 | Data Lake (CSV raw + processed) |
| AWS RDS | Data Warehouse PostgreSQL |

---

##  Auteur

| | Nom | Rôle |
|---|---|---|
| | **Martial BAYOM** | Data Engineering |

Projet réalisé dans le cadre de la **certification Jedha AI School** (RNCP Niveau 6)
