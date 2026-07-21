# ============================================================
#   PARTIE 2 (BIS) : HÔTELS VIA GOOGLE PLACES API
# ============================================================
# Remplace le scraping Booking.com, bloqué par leur protection
# anti-bot AWS WAF (voir README pour l'explication du blocage).
#
# Google Places est une API OFFICIELLE (pas du scraping) :
# on interroge leurs serveurs avec une clé API, dans le respect
# de leurs conditions d'utilisation.
#
# Documentation : https://developers.google.com/maps/documentation/places/web-service/text-search
#
# Coût : gratuit jusqu'à 200$/mois de crédit offert par Google
# (largement suffisant pour 35 villes).
# ============================================================

import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ⚠️ Récupère ta clé sur https://console.cloud.google.com/
#    (active "Places API (New)" dans "APIs & Services")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "TA_CLE_ICI")

# Les 35 mêmes villes que la partie météo (garde la cohérence du pipeline)
CITIES = [
    "Mont Saint Michel", "St Malo", "Bayeux", "Le Havre", "Rouen",
    "Paris", "Amiens", "Lille", "Strasbourg", "Chateau du Haut Koenigsbourg",
    "Colmar", "Eguisheim", "Besancon", "Dijon", "Annecy",
    "Grenoble", "Lyon", "Gorges du Verdon", "Bormes les Mimosas", "Cassis",
    "Marseille", "Aix en Provence", "Avignon", "Uzes", "Nimes",
    "Aigues Mortes", "Saintes Maries de la mer", "Collioure", "Carcassonne", "Ariege",
    "Toulouse", "Montauban", "Biarritz", "Bayonne", "La Rochelle",
]

NB_HOTELS_PAR_VILLE = 20  # Pour pouvoir construire le Top 20 demandé


def search_hotels(city_name, max_results=20):
    """
    Recherche les hôtels d'une ville via l'API Google Places (Text Search).

    Returns:
        list: Liste de dicts avec les infos de chaque hôtel
    """
    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        # FieldMask : on ne demande que les champs utiles (réduit le coût de l'appel)
        "X-Goog-FieldMask": (
            "places.displayName,places.formattedAddress,"
            "places.location,places.rating,places.userRatingCount"
        ),
    }

    payload = {
        "textQuery": f"hotels in {city_name}, France",
        "languageCode": "fr",
        "maxResultCount": max_results,
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()

    hotels = []
    for place in data.get("places", []):
        hotels.append({
            "city_name": city_name,
            "hotel_name": place.get("displayName", {}).get("text", "N/A"),
            "address": place.get("formattedAddress", "N/A"),
            "rating": place.get("rating"),                    # note sur 5
            "rating_count": place.get("userRatingCount"),      # nombre d'avis
            "latitude": place.get("location", {}).get("latitude"),
            "longitude": place.get("location", {}).get("longitude"),
        })

    return hotels


# ── Collecte pour les 35 villes ──────────────────────────────
print("🏨 Récupération des hôtels via Google Places API...\n")
all_hotels = []

for city in CITIES:
    print(f"🔍 {city}...")
    try:
        hotels = search_hotels(city, max_results=NB_HOTELS_PAR_VILLE)
        all_hotels.extend(hotels)
        print(f"   ✅ {len(hotels)} hôtels récupérés")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erreur pour {city}: {e}")

    time.sleep(0.3)  # Petite pause pour rester raisonnable sur le rate limit

df_hotels = pd.DataFrame(all_hotels)
df_hotels = df_hotels.dropna(subset=["rating"])  # on garde seulement les hôtels notés

print(f"\n✅ {len(df_hotels)} hôtels au total sur {df_hotels['city_name'].nunique()} villes")
print(df_hotels.head())

# ── Sauvegarde ────────────────────────────────────────────────
df_hotels.to_csv("../data/hotels.csv", index=False)
print("\n✅ Fichier sauvegardé : data/hotels.csv")

# ── Top 20 hôtels (note × nombre d'avis, pour éviter qu'un hôtel
#    avec 1 seul avis à 5 étoiles écrase le classement) ────────
df_hotels["score"] = df_hotels["rating"] * (df_hotels["rating_count"].clip(upper=500) ** 0.3)
top20 = df_hotels.sort_values("score", ascending=False).head(20)
print("\n🏆 TOP 20 HÔTELS :")
print(top20[["city_name", "hotel_name", "rating", "rating_count"]].to_string(index=False))

top20.to_csv("../data/top20_hotels.csv", index=False)
print("\n✅ Fichier sauvegardé : data/top20_hotels.csv (pour la carte Plotly)")
