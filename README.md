# 🛶 Kayak — Data Engineering : Météo, Hôtels & Pipeline AWS

> *Construire un pipeline de données complet pour recommander les meilleures destinations de vacances en France*

[![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python)](https://www.python.org/)
[![AWS S3](https://img.shields.io/badge/AWS-S3-FF9900?logo=amazonaws)](https://aws.amazon.com/s3/)
[![AWS RDS](https://img.shields.io/badge/AWS-RDS-FF9900?logo=amazonaws)](https://aws.amazon.com/rds/)
[![Plotly](https://img.shields.io/badge/Plotly-Maps-3F4F75?logo=plotly)](https://plotly.com/)

---

## 🎯 Objectif

Construire un pipeline de données end-to-end pour recommander aux utilisateurs Kayak les meilleures destinations françaises selon la météo et la qualité des hôtels disponibles.

---

## 🏗️ Architecture

```
Nominatim API          → Coordonnées GPS (35 villes)
        ↓
OpenWeatherMap API     → Prévisions météo 7 jours
        ↓
Score météo composite  → Classement des destinations
        ↓
Booking.com scraping   → Hôtels (Top 5 destinations)
        ↓
AWS S3 (Data Lake)     → Stockage raw + processed
        ↓
AWS RDS (PostgreSQL)   → Data Warehouse requêtable
        ↓
Plotly Maps            → 2 cartes interactives
```

---

## 📊 Résultats

- **35 villes** françaises géocodées et analysées
- **7 jours** de prévisions météo par ville
- **Top 5 destinations** selon score météo composite
- **Top 20 hôtels** scrapés sur Booking.com
- Data Lake S3 + Data Warehouse RDS alimentés

---

## 🗂️ Structure du projet

```
kayak/
├── data/                             # Données générées (non versionnées)
│   ├── weather_data.csv
│   ├── hotels_data.csv
│   └── city_scores.csv
├── notebooks/
│   └── kayak_project.ipynb           # Pipeline complet
├── .env.example                      # Template variables d'environnement
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 🧠 Score Météo

| Critère | Poids | Logique |
|---|---|---|
| Température | 40% | Gaussienne centrée sur 22°C |
| Probabilité de pluie | 35% | 1 − pop (OpenWeatherMap) |
| Humidité | 15% | Idéale entre 40 et 60% |
| Vent | 10% | Décroissant exponentiellement |

---

## ⚙️ Installation

```bash
git clone https://github.com/MartialBayom/kayak-data-engineering.git
cd kayak-data-engineering

pip install -r requirements.txt

cp .env.example .env
# Remplir .env avec vos clés API et credentials AWS

jupyter notebook notebooks/kayak_project.ipynb
```

---

## 🔑 APIs utilisées

| Service | Usage | Docs |
|---|---|---|
| Nominatim | Géocodage GPS | [nominatim.org](https://nominatim.org/) |
| OpenWeatherMap | Prévisions 7 jours | [openweathermap.org](https://openweathermap.org/) |
| Booking.com | Scraping hôtels | Web scraping (BeautifulSoup) |
| AWS S3 | Data Lake | [aws.amazon.com/s3](https://aws.amazon.com/s3/) |
| AWS RDS | Data Warehouse | [aws.amazon.com/rds](https://aws.amazon.com/rds/) |

---

## 👤 Auteur

| | Nom | Rôle |
|---|---|---|
| 🧑‍💻 | **Martial BAYOM** | Data Engineering |

Projet réalisé dans le cadre de la **certification Jedha AI School** (RNCP Niveau 6)
