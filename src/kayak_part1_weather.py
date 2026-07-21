# ============================================================
# PROJET KAYAK — RECOMMANDATION DE DESTINATIONS EN FRANCE
# Partie 1 : Récupération des données météo via API
# ============================================================
# PIPELINE COMPLET :
#   1. Coordonnées GPS via Nominatim API
#   2. Données météo via OpenWeatherMap API
#   3. Score météo et classement des villes
#   4. Visualisation carte interactive Plotly
# ============================================================


# ╔══════════════════════════════════════════════════════════╗
# ║           PARTIE 1 : IMPORTS & CONFIGURATION            ║
# ╚══════════════════════════════════════════════════════════╝

# requests : librairie Python pour faire des requêtes HTTP (appels API)
# pandas : manipulation de données sous forme de tableaux (DataFrame)
# time : pour ajouter des pauses entre les requêtes API (éviter le rate limiting)
# plotly.express : visualisation de données interactive

import requests
import pandas as pd
import time
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Inscription gratuite sur : https://openweathermap.org/appid
import os
from dotenv import load_dotenv
load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Liste des 35 villes françaises à analyser (fournie par le projet)
CITIES = [
    "Mont Saint Michel", "St Malo", "Bayeux", "Le Havre", "Rouen",
    "Paris", "Amiens", "Lille", "Strasbourg", "Chateau du Haut Koenigsbourg",
    "Colmar", "Eguisheim", "Besancon", "Dijon", "Annecy",
    "Grenoble", "Lyon", "Gorges du Verdon", "Bormes les Mimosas", "Cassis",
    "Marseille", "Aix en Provence", "Avignon", "Uzes", "Nimes",
    "Aigues Mortes", "Saintes Maries de la mer", "Collioure", "Carcassonne", "Ariege",
    "Toulouse", "Montauban", "Biarritz", "Bayonne", "La Rochelle"
]

print(f" Configuration prête — {len(CITIES)} villes à analyser")


# ╔══════════════════════════════════════════════════════════╗
# ║      PARTIE 2 : COORDONNÉES GPS VIA NOMINATIM           ║
# ╚══════════════════════════════════════════════════════════╝

# Nominatim est l'API de géocodage d'OpenStreetMap.
# Elle convertit un nom de ville en coordonnées GPS (latitude, longitude).
# C'est GRATUIT et ne nécessite pas de clé API.
#
# Documentation : https://nominatim.org/release-docs/develop/api/Search/
# Format de la requête : GET https://nominatim.openstreetmap.org/search
# Paramètres :
#   - q : nom de la ville à chercher
#   - format : "json" pour obtenir du JSON
#   - limit : nombre de résultats maximum (on prend 1 = le meilleur match)
#   - countrycodes : "fr" pour limiter à la France

def get_coordinates(city_name):
    """
    Récupère les coordonnées GPS d'une ville via l'API Nominatim.
    
    Args:
        city_name (str): Nom de la ville
        
    Returns:
        dict: {"lat": float, "lon": float} ou None si pas trouvé
    
    Explication jury :
    - On envoie une requête GET à l'API Nominatim
    - L'API retourne une liste de résultats en JSON
    - On prend le premier résultat (le plus pertinent)
    - On extrait lat et lon
    """
    
    # URL de base de l'API Nominatim
    url = "https://nominatim.openstreetmap.org/search"
    
    # Paramètres de la requête (seront ajoutés à l'URL automatiquement)
    params = {
        "q": f"{city_name}, France",  # Nom de la ville + pays pour plus de précision
        "format": "json",              # Format de réponse
        "limit": 1,                    # On veut seulement le meilleur résultat
        "countrycodes": "fr"           # Limite à la France
    }
    
    # Headers HTTP : Nominatim exige un User-Agent identifiable
    # Sans ça, les requêtes peuvent être bloquées
    headers = {
        "User-Agent": "KayakProject/1.0 (martialbayom@gmail.com)"
    }
    
    try:
        # requests.get() envoie une requête HTTP GET
        # response contient le statut HTTP et les données retournées
        response = requests.get(url, params=params, headers=headers)
        
        # raise_for_status() lève une exception si le statut HTTP est une erreur (4xx, 5xx)
        response.raise_for_status()
        
        # response.json() parse la réponse JSON en dictionnaire/liste Python
        data = response.json()
        
        # Si la liste n'est pas vide, on extrait lat/lon du premier résultat
        if data:
            return {
                "lat": float(data[0]["lat"]),
                "lon": float(data[0]["lon"])
            }
        else:
            print(f"    Aucun résultat pour : {city_name}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"    Erreur pour {city_name}: {e}")
        return None


# Récupération des coordonnées pour toutes les villes
print("\n Récupération des coordonnées GPS...")
cities_data = []

for i, city in enumerate(CITIES):
    coords = get_coordinates(city)
    
    if coords:
        cities_data.append({
            "city_id": i + 1,           # Identifiant unique de la ville
            "city_name": city,
            "latitude": coords["lat"],
            "longitude": coords["lon"]
        })
        print(f"   {city}: lat={coords['lat']:.4f}, lon={coords['lon']:.4f}")
    
    # IMPORTANT : Pause de 1 seconde entre chaque requête !
    # Nominatim impose une limite d'1 requête/seconde (rate limit).
    # Sans cette pause, nos requêtes seront bloquées.
    time.sleep(1)

# Création du DataFrame avec les coordonnées
df_cities = pd.DataFrame(cities_data)
print(f"\n {len(df_cities)} villes géocodées sur {len(CITIES)}")
print(df_cities.head())


# ╔══════════════════════════════════════════════════════════╗
# ║       PARTIE 3 : DONNÉES MÉTÉO VIA OPENWEATHERMAP       ║
# ╚══════════════════════════════════════════════════════════╝

# OpenWeatherMap One Call API retourne les prévisions sur 7 jours.
# Pour chaque jour on obtient : température, précipitations, humidité,
# vitesse du vent, probabilité de pluie (pop), etc.
#
# URL : https://api.openweathermap.org/data/2.5/onecall
# Paramètres :
#   - lat, lon : coordonnées GPS
#   - exclude : données à exclure (on exclut "current,minutely,hourly,alerts")
#   - units : "metric" pour Celsius
#   - appid : clé API

def get_weather(lat, lon, city_name):
    """
    Récupère les prévisions météo sur 5 jours pour une ville,
    via l'endpoint gratuit /forecast (par tranches de 3h),
    regroupées par jour.

    Returns:
        list: Liste de dicts avec les données météo par jour
    """

    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "lat": lat,
        "lon": lon,
        "units": "metric",
        "appid": OPENWEATHER_API_KEY
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # On regroupe les entrées 3h par jour calendaire
        from collections import defaultdict
        by_day = defaultdict(list)
        for entry in data.get("list", []):
            day = entry["dt_txt"].split(" ")[0]  # "2026-07-21"
            by_day[day].append(entry)

        daily_data = []
        for day_idx, (day, entries) in enumerate(sorted(by_day.items())[:5]):
            temps = [e["main"]["temp"] for e in entries]
            humidities = [e["main"]["humidity"] for e in entries]
            pops = [e.get("pop", 0) for e in entries]
            rain_vols = [e.get("rain", {}).get("3h", 0) for e in entries]

            daily_data.append({
                "city_name": city_name,
                "date": day,
                "day_index": day_idx,
                "day_temperature": sum(temps) / len(temps),
                "humidity": sum(humidities) / len(humidities),
                "precipitation_prob": sum(pops) / len(pops),
                "rain_volume": sum(rain_vols),
                "wind_speed": sum(e["wind"]["speed"] for e in entries) / len(entries),
            })

        return daily_data

    except requests.exceptions.RequestException as e:
        print(f"    Erreur météo pour {city_name}: {e}")
        return []


# Récupération de la météo pour toutes les villes
print("\n Récupération des données météo (7 jours)...")
all_weather_data = []

for _, row in df_cities.iterrows():
    weather = get_weather(row["latitude"], row["longitude"], row["city_name"])
    all_weather_data.extend(weather)
    if weather:
        print(f"    Météo récupérée pour {row['city_name']}")

# Création du DataFrame météo
df_weather = pd.DataFrame(all_weather_data)
print(f"\n {len(df_weather)} entrées météo créées ({len(CITIES)} villes × 7 jours)")
print(df_weather.head(10))


# ╔══════════════════════════════════════════════════════════╗
# ║         PARTIE 4 : CALCUL DU SCORE MÉTÉO               ║
# ╚══════════════════════════════════════════════════════════╝

# On calcule un score météo sur 100 pour chaque ville.
# Le score prend en compte :
#   - Température moyenne sur 7 jours (on veut chaud mais pas trop)
#   - Volume de pluie (moins = mieux)
#   - Probabilité de pluie (moins = mieux)
#   - Humidité (moins = mieux)
#
# Explication jury :
# "Beau temps" est subjectif, mais on définit des règles simples :
# temp idéale entre 20°C et 28°C, pas de pluie, faible humidité

def compute_weather_score(temp, rain_vol, precip_prob, humidity):
    """
    Calcule un score météo de 0 à 100.
    Plus le score est élevé, meilleur est le temps.
    """
    # Score température : idéal entre 22 et 26°C
    # On utilise une parabole inversée centrée sur 24°C
    temp_score = max(0, 100 - abs(temp - 24) * 5)
    
    # Score pluie : 0mm de pluie = 100 pts, 10mm+ = 0 pts
    rain_score = max(0, 100 - rain_vol * 10)
    
    # Score probabilité de pluie : 0% = 100 pts, 100% = 0 pts
    precip_score = (1 - precip_prob) * 100
    
    # Score humidité : 40% = idéal, 80%+ = mauvais
    humidity_score = max(0, 100 - abs(humidity - 40) * 1.5)
    
    # Score final = moyenne pondérée
    # On accorde plus d'importance à la température et à la pluie
    final_score = (
        temp_score * 0.35 +        # 35% pour la température
        rain_score * 0.25 +        # 25% pour le volume de pluie
        precip_score * 0.25 +      # 25% pour la probabilité de pluie
        humidity_score * 0.15      # 15% pour l'humidité
    )
    
    return round(final_score, 2)


# Application du score météo à chaque ligne du DataFrame
# apply() applique une fonction sur chaque ligne (axis=1) ou colonne (axis=0)
df_weather["weather_score"] = df_weather.apply(
    lambda row: compute_weather_score(
        row["day_temperature"],
        row["rain_volume"],
        row["precipitation_prob"],
        row["humidity"]
    ),
    axis=1   # axis=1 = appliquer sur chaque LIGNE
)

# Explication jury :
# lambda row: ... → fonction anonyme qui prend une ligne du DataFrame
# row["day_temperature"] → accès à une valeur dans la ligne
# axis=1 → on parcourt les lignes (axis=0 parcourrait les colonnes)

print("\n Scores météo calculés :")
print(df_weather[["city_name", "date", "day_temperature", "rain_volume", 
                   "precipitation_prob", "weather_score"]].head(14))


# Agrégation par ville : moyenne du score météo sur 7 jours
df_city_score = df_weather.groupby("city_name").agg(
    avg_weather_score=("weather_score", "mean"),
    avg_temperature=("day_temperature", "mean"),
    total_rain=("rain_volume", "sum"),
    avg_humidity=("humidity", "mean"),
    avg_wind=("wind_speed", "mean")
).reset_index()

# Explication jury :
# .groupby("city_name") → regroupe par ville
# .agg() → applique des fonctions d'agrégation à plusieurs colonnes
# ("weather_score", "mean") → nom de la nouvelle colonne = avg_weather_score
# .reset_index() → remet city_name comme colonne (enlève l'index multi-niveaux)

# Arrondi des valeurs
df_city_score["avg_weather_score"] = df_city_score["avg_weather_score"].round(2)
df_city_score["avg_temperature"] = df_city_score["avg_temperature"].round(1)
df_city_score["total_rain"] = df_city_score["total_rain"].round(1)

# Tri par score décroissant + ajout du rang
df_city_score = df_city_score.sort_values("avg_weather_score", ascending=False)
df_city_score["rank"] = range(1, len(df_city_score) + 1)

print("\n CLASSEMENT DES VILLES PAR SCORE MÉTÉO :")
print(df_city_score.to_string(index=False))

# Top 5 destinations
top5_cities = df_city_score.head(5)
print("\n TOP 5 MEILLEURES DESTINATIONS :")
print(top5_cities[["rank", "city_name", "avg_weather_score", "avg_temperature", "total_rain"]].to_string(index=False))


# ╔══════════════════════════════════════════════════════════╗
# ║      PARTIE 5 : FUSION ET SAUVEGARDE EN CSV             ║
# ╚══════════════════════════════════════════════════════════╝

# On joint df_cities (coordonnées) avec df_city_score (scores météo)
# pd.merge() = équivalent SQL JOIN
# on="city_name" = colonne commune pour la jointure
# how="inner" = garde seulement les villes présentes dans les deux DataFrames

df_final_weather = pd.merge(df_cities, df_city_score, on="city_name", how="inner")

print("\n DataFrame final (météo + coordonnées) :")
print(df_final_weather.head())

# Sauvegarde en CSV
# index=False → ne pas sauvegarder l'index pandas (colonne 0,1,2,3...)
df_final_weather.to_csv("weather_france_cities.csv", index=False, encoding="utf-8")
df_weather.to_csv("weather_daily_details.csv", index=False, encoding="utf-8")

print("\n Fichiers CSV sauvegardés :")
print("   - weather_france_cities.csv (scores par ville)")
print("   - weather_daily_details.csv (détails 7 jours)")


# ╔══════════════════════════════════════════════════════════╗
# ║         PARTIE 6 : VISUALISATION CARTE PLOTLY          ║
# ╚══════════════════════════════════════════════════════════╝

# Plotly Express permet de créer des cartes interactives facilement.
# px.scatter_mapbox() crée une carte avec des points (scatter = nuage de points).
# La taille des bulles représente le score météo.
# La couleur représente la température.

# Map 1 : Toutes les villes avec leur score météo
fig_weather = px.scatter_mapbox(
    df_final_weather,
    lat="latitude",                          # Colonne latitude
    lon="longitude",                         # Colonne longitude
    size="avg_weather_score",               # Taille des bulles = score météo
    color="avg_temperature",                # Couleur = température
    hover_name="city_name",                 # Texte au survol = nom de la ville
    hover_data={                            # Infos supplémentaires au survol
        "avg_weather_score": ":.1f",
        "avg_temperature": ":.1f",
        "total_rain": ":.1f",
        "rank": True
    },
    color_continuous_scale="RdYlBu_r",     # Rouge=chaud, Bleu=froid (inversé)
    size_max=40,                            # Taille maximale des bulles
    zoom=4.5,                               # Niveau de zoom sur la carte
    center={"lat": 46.5, "lon": 2.5},      # Centre de la carte (France)
    mapbox_style="carto-positron",          # Style de fond de carte
    title=" Score Météo des 35 Villes Françaises (7 prochains jours)",
    labels={
        "avg_weather_score": "Score Météo",
        "avg_temperature": "Température moy. (°C)",
        "total_rain": "Pluie totale (mm)"
    }
)

# Mise en forme de la carte
fig_weather.update_layout(
    height=600,
    coloraxis_colorbar=dict(title="Température (°C)")
)

fig_weather.show()

# Explication jury :
# px.scatter_mapbox() → carte interactive avec bulles
# color_continuous_scale="RdYlBu_r" → dégradé rouge→jaune→bleu inversé
# hover_name → affiché en titre au survol de la souris
# mapbox_style="carto-positron" → fond de carte gris clair, lisible


# Map 2 : Top 5 destinations mis en évidence
df_top5_map = df_final_weather.copy()
df_top5_map["is_top5"] = df_top5_map["rank"].apply(
    lambda x: " Top 5" if x <= 5 else "Autres villes"
)

fig_top5 = px.scatter_mapbox(
    df_top5_map,
    lat="latitude",
    lon="longitude",
    size="avg_weather_score",
    color="is_top5",
    hover_name="city_name",
    hover_data={"avg_weather_score": ":.1f", "rank": True, "avg_temperature": ":.1f"},
    color_discrete_map={" Top 5": "#FF6B35", "Autres villes": "#A0A0A0"},
    size_max=50,
    zoom=4.5,
    center={"lat": 46.5, "lon": 2.5},
    mapbox_style="carto-positron",
    title=" Top 5 Meilleures Destinations Météo en France"
)

fig_top5.update_layout(height=600)
fig_top5.show()

print("\n Cartes générées avec succès !")
print(f"\n TOP 5 FINAL :")
for _, row in top5_cities.iterrows():
    print(f"   #{int(row['rank'])} {row['city_name']} — Score: {row['avg_weather_score']:.1f}/100 | {row['avg_temperature']:.1f}°C | {row['total_rain']:.1f}mm de pluie")
