# ============================================================
# PROJET KAYAK — Partie 2 : Scraping Booking.com
# ============================================================
# On scrape les hôtels de chaque ville via BeautifulSoup.
# IMPORTANT : Booking.com peut bloquer le scraping.
# On utilise des headers réalistes et des pauses aléatoires.
# ============================================================

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re

# NOTE JURY :
# Le scraping de Booking.com peut être bloqué par des mesures anti-bot.
# Pour un projet réel, on utiliserait Selenium (navigateur headless) ou
# une API officielle. Ici on présente l'approche BeautifulSoup.


# ----- Configuration -----
# Headers HTTP qui imitent un vrai navigateur.
# Sans ces headers, Booking.com identifie notre script comme un bot
# et retourne une page d'erreur ou un CAPTCHA.

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.booking.com/",
}


def build_booking_url(city_name, checkin="2024-08-01", checkout="2024-08-07"):
    """
    Construit l'URL de recherche Booking.com pour une ville.
    
    Explication jury :
    - On encode le nom de la ville pour l'URL (%20 à la place des espaces)
    - L'URL suit le format standard de Booking.com pour la recherche
    - On simule une recherche pour 2 adultes, 1 chambre
    """
    
    # Remplace les espaces par + pour l'URL
    city_encoded = city_name.replace(" ", "+")
    
    url = (
        f"https://www.booking.com/searchresults.fr.html"
        f"?ss={city_encoded}"
        f"&checkin={checkin}"
        f"&checkout={checkout}"
        f"&group_adults=2"
        f"&no_rooms=1"
        f"&order=review_score_and_price"  # Tri par score et prix
    )
    
    return url


def scrape_hotels_from_page(html_content, city_name):
    """
    Parse le HTML d'une page de résultats Booking.com
    et extrait les informations des hôtels.
    
    Args:
        html_content (str): Le HTML de la page
        city_name (str): Nom de la ville
        
    Returns:
        list: Liste de dicts avec les infos des hôtels
    
    Explication jury :
    - BeautifulSoup parse le HTML et permet de naviguer dans sa structure
    - On cherche des éléments HTML par leur attribut data-testid ou leur classe CSS
    - Ces sélecteurs peuvent changer si Booking.com met à jour son site
    """
    
    # BeautifulSoup(html, "html.parser") → crée un arbre navigable depuis le HTML
    # "html.parser" = parser HTML intégré à Python (pas besoin de librairie externe)
    soup = BeautifulSoup(html_content, "html.parser")
    
    hotels = []
    
    # Chaque hôtel est dans un div avec data-testid="property-card"
    # find_all() retourne une liste de tous les éléments correspondants
    hotel_cards = soup.find_all("div", {"data-testid": "property-card"})
    
    print(f"   → {len(hotel_cards)} hôtels trouvés sur cette page")
    
    for card in hotel_cards:
        try:
            hotel = {"city_name": city_name}
            
            # ----- Nom de l'hôtel -----
            # find() retourne le PREMIER élément correspondant (ou None si pas trouvé)
            name_elem = card.find("div", {"data-testid": "title"})
            hotel["hotel_name"] = name_elem.text.strip() if name_elem else "N/A"
            # .text → extrait le texte de l'élément HTML (sans les balises)
            # .strip() → supprime les espaces/sauts de ligne en début et fin
            
            # ----- URL de la page hôtel -----
            url_elem = card.find("a", {"data-testid": "title-link"})
            hotel["booking_url"] = url_elem.get("href") if url_elem else "N/A"
            # .get("href") → récupère l'attribut href d'une balise <a>
            
            # ----- Score / Note -----
            score_elem = card.find("div", {"data-testid": "review-score"})
            if score_elem:
                score_text = score_elem.find("div", class_=re.compile("ac4a7896c7"))
                hotel["score"] = float(score_text.text.replace(",", ".")) if score_text else None
            else:
                hotel["score"] = None
            
            # ----- Description -----
            desc_elem = card.find("div", {"data-testid": "property-card-meta-description"})
            hotel["description"] = desc_elem.text.strip() if desc_elem else "N/A"
            
            # ----- Prix -----
            price_elem = card.find("span", {"data-testid": "price-and-discounted-price"})
            hotel["price_per_night"] = price_elem.text.strip() if price_elem else "N/A"
            
            # ----- Localisation (coordonnées) -----
            # Certains éléments contiennent lat/lon en attributs data-*
            loc_elem = card.find("a", {"data-testid": "availability-cta-btn"})
            hotel["latitude"] = None
            hotel["longitude"] = None
            
            hotels.append(hotel)
            
        except Exception as e:
            # En scraping, les erreurs sont fréquentes car la structure HTML varie.
            # On les capture et on continue avec l'hôtel suivant.
            print(f"   ⚠️ Erreur parsing hôtel: {e}")
            continue
    
    return hotels


def scrape_city_hotels(city_name, max_pages=3):
    """
    Scrape les hôtels d'une ville sur plusieurs pages Booking.com.
    
    Args:
        city_name (str): Nom de la ville
        max_pages (int): Nombre de pages à scraper (25 hôtels/page)
        
    Returns:
        list: Liste de tous les hôtels trouvés
    
    Explication jury :
    - Booking.com pagine ses résultats (25 hôtels par page)
    - Le paramètre 'offset' dans l'URL permet d'accéder aux pages suivantes
    - offset=0 → page 1, offset=25 → page 2, offset=50 → page 3
    """
    
    all_hotels = []
    base_url = build_booking_url(city_name)
    
    for page in range(max_pages):
        # Calcul de l'offset pour la pagination
        offset = page * 25
        url = f"{base_url}&offset={offset}"
        
        try:
            print(f"\n    Scraping page {page + 1} pour {city_name}...")
            
            # Requête HTTP avec les headers réalistes
            response = requests.get(url, headers=HEADERS, timeout=15)
            
            # timeout=15 → abandon de la requête après 15 secondes
            # Évite que le script reste bloqué si le serveur ne répond pas
            
            response.raise_for_status()
            open("debug_page.html", "w").write(response.text)
            
            hotels = scrape_hotels_from_page(response.text, city_name)
            all_hotels.extend(hotels)
            
            # Si pas d'hôtels trouvés, c'est qu'on a atteint la dernière page
            if not hotels:
                print(f"   → Pas d'hôtels sur cette page, arrêt.")
                break
            
            # Pause aléatoire entre 2 et 5 secondes entre chaque page
            # Aléatoire pour imiter un comportement humain et éviter les blocages
            sleep_time = random.uniform(2, 5)
            print(f"    Pause de {sleep_time:.1f}s avant la prochaine page...")
            time.sleep(sleep_time)
            
        except requests.exceptions.RequestException as e:
            print(f"    Erreur lors du scraping de {city_name} (page {page+1}): {e}")
            break
    
    return all_hotels


# ============================================================
# SCRAPING DE TOUTES LES VILLES
# ============================================================

# On charge le CSV des villes créé dans la Partie 1
# pour avoir la liste des villes avec leurs coordonnées
try:
    df_cities = pd.read_csv("weather_france_cities.csv")
    cities_to_scrape = df_cities["city_name"].tolist()
except FileNotFoundError:
    # Si le CSV n'existe pas encore, on utilise la liste complète
    cities_to_scrape = [
        "Mont Saint Michel", "St Malo", "Bayeux", "Le Havre", "Rouen",
        "Paris", "Amiens", "Lille", "Strasbourg", "Colmar",
        "Dijon", "Annecy", "Grenoble", "Lyon", "Marseille",
        "Aix en Provence", "Avignon", "Nimes", "Toulouse",
        "Biarritz", "Bayonne", "La Rochelle", "Carcassonne",
        "Montauban", "Collioure", "Cassis", "Besancon",
        "Strasbourg", "Lille", "Bordeaux"
    ]

print(f"🏨 Début du scraping pour {len(cities_to_scrape)} villes...")

all_hotels_data = []

for city in cities_to_scrape[:5]:  #  Limité à 5 villes pour la démo
    print(f"\n🔍 Scraping de {city}...")
    hotels = scrape_city_hotels(city, max_pages=2)
    all_hotels_data.extend(hotels)
    
    print(f"    {len(hotels)} hôtels récupérés pour {city}")
    
    # Pause plus longue entre les villes pour éviter les blocages
    sleep_time = random.uniform(5, 10)
    print(f"   ⏳ Pause de {sleep_time:.1f}s avant la prochaine ville...")
    time.sleep(sleep_time)


# Création du DataFrame hôtels
df_hotels = pd.DataFrame(all_hotels_data)

# Nettoyage : suppression des doublons
df_hotels = df_hotels.drop_duplicates(subset=["hotel_name", "city_name"])

# Suppression des lignes sans nom d'hôtel
df_hotels = df_hotels[df_hotels["hotel_name"] != "N/A"]

# Ajout d'un ID unique pour chaque hôtel
df_hotels["hotel_id"] = range(1, len(df_hotels) + 1)

print(f"\n {len(df_hotels)} hôtels uniques récupérés au total")
print(df_hotels.head(10))

# Sauvegarde
df_hotels.to_csv("hotels_france.csv", index=False, encoding="utf-8")
print("\n hotels_france.csv sauvegardé")


# ============================================================
# VISUALISATION : TOP 20 HÔTELS SUR UNE CARTE
# ============================================================

# Pour avoir les coordonnées des hôtels, on les joint avec df_cities
# (les coordonnées des hôtels seront approximativement celles de la ville)

import plotly.express as px

# On charge les données météo pour avoir les coords des villes
df_weather_cities = pd.read_csv("weather_france_cities.csv")

# Jointure hôtels + coordonnées des villes
df_hotels_map = pd.merge(
    df_hotels[df_hotels["score"].notna()],   # Garde seulement les hôtels avec une note
    df_weather_cities[["city_name", "latitude", "longitude", "rank"]],
    on="city_name",
    how="inner"
)

# Top 20 hôtels par score
top20_hotels = df_hotels_map.nlargest(20, "score")

print(f"\n TOP 20 HÔTELS :")
print(top20_hotels[["hotel_name", "city_name", "score"]].to_string(index=False))

# Carte Top 20 Hôtels
fig_hotels = px.scatter_mapbox(
    top20_hotels,
    lat="latitude",
    lon="longitude",
    size="score",
    color="score",
    hover_name="hotel_name",
    hover_data={
        "city_name": True,
        "score": ":.1f",
        "price_per_night": True
    },
    color_continuous_scale="Viridis",
    size_max=30,
    zoom=4.5,
    center={"lat": 46.5, "lon": 2.5},
    mapbox_style="carto-positron",
    title=" Top 20 Meilleurs Hôtels en France"
)

fig_hotels.update_layout(height=600)
fig_hotels.show()
