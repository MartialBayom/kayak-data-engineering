# ============================================================
# PROJET KAYAK — Partie 3 : Data Lake S3 + ETL vers AWS RDS
# ============================================================
# PIPELINE ETL :
#   Extract  → Lecture des CSV locaux
#   Transform → Nettoyage et enrichissement des données
#   Load     → Envoi vers S3 (Data Lake) puis RDS (Data Warehouse)
# ============================================================

import boto3          # SDK AWS pour Python — interagit avec S3, RDS, etc.
import pandas as pd
import psycopg2       # Driver Python pour PostgreSQL (AWS RDS utilise PostgreSQL)
import sqlalchemy     # ORM Python pour les bases de données SQL
from sqlalchemy import create_engine, text
import io             # Pour écrire des fichiers en mémoire (sans passer par le disque)


# ╔══════════════════════════════════════════════════════════╗
# ║           CONFIGURATION AWS                             ║
# ╚══════════════════════════════════════════════════════════╝

# ⚠️ SÉCURITÉ : En production, ne JAMAIS mettre les credentials dans le code.
# Utiliser des variables d'environnement ou AWS IAM Roles.
# Pour ce projet de cours, on les met ici pour la lisibilité.

AWS_CONFIG = {
    "aws_access_key_id": "VOTRE_ACCESS_KEY",
    "aws_secret_access_key": "VOTRE_SECRET_KEY",
    "region_name": "eu-west-3"          # Paris
}

S3_BUCKET_NAME = "kayak-project-YOUR-NAME"  # Nom unique de votre bucket S3

# Configuration AWS RDS (base de données PostgreSQL)
RDS_CONFIG = {
    "host": "YOUR-RDS-ENDPOINT.rds.amazonaws.com",
    "port": 5432,
    "database": "kayak_db",
    "username": "kayak_admin",
    "password": "VOTRE_MOT_DE_PASSE"
}


# ╔══════════════════════════════════════════════════════════╗
# ║        PARTIE 1 : CHARGEMENT VERS S3 (DATA LAKE)       ║
# ╚══════════════════════════════════════════════════════════╝

# S3 = Simple Storage Service d'AWS.
# C'est un stockage objet (comme un Google Drive mais pour devs).
# On y stocke nos CSV bruts → c'est notre "Data Lake" (lac de données).
#
# Architecture Data Lake :
#   s3://kayak-project/raw/weather/        ← données brutes météo
#   s3://kayak-project/raw/hotels/         ← données brutes hôtels
#   s3://kayak-project/processed/          ← données nettoyées

def upload_to_s3(df, bucket_name, s3_key, aws_config):
    """
    Uploade un DataFrame pandas vers S3 en CSV.
    
    Args:
        df (pd.DataFrame): Le DataFrame à uploader
        bucket_name (str): Nom du bucket S3
        s3_key (str): Chemin du fichier dans S3 (ex: "raw/weather/cities.csv")
        aws_config (dict): Credentials AWS
    
    Explication jury :
    - boto3.client("s3") crée un client S3 (connexion à AWS)
    - io.StringIO() : on écrit le CSV en mémoire (pas sur disque)
    - put_object() : upload le fichier vers S3
    - Cette approche est plus efficace que d'écrire un fichier local puis l'uploader
    """
    
    # Création du client S3 avec les credentials AWS
    # boto3 est le SDK AWS officiel pour Python
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=aws_config["aws_access_key_id"],
        aws_secret_access_key=aws_config["aws_secret_access_key"],
        region_name=aws_config["region_name"]
    )
    
    # Conversion du DataFrame en CSV en mémoire (pas de fichier temporaire)
    # io.StringIO() = buffer mémoire qui se comporte comme un fichier texte
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding="utf-8")
    
    # Upload vers S3
    # put_object() = méthode boto3 pour uploader un objet dans S3
    s3_client.put_object(
        Bucket=bucket_name,           # Nom du bucket
        Key=s3_key,                   # Chemin dans le bucket
        Body=csv_buffer.getvalue(),   # Contenu du fichier (CSV en string)
        ContentType="text/csv"        # Type MIME du fichier
    )
    
    print(f"   ✅ Uploadé vers s3://{bucket_name}/{s3_key}")


def create_s3_bucket(bucket_name, aws_config):
    """
    Crée un bucket S3 s'il n'existe pas déjà.
    
    Explication jury :
    - Un bucket S3 est un conteneur pour stocker des fichiers
    - Le nom doit être GLOBALEMENT unique sur tout AWS
    - CreateBucketConfiguration spécifie la région (Paris = eu-west-3)
    """
    
    s3_client = boto3.client("s3", **aws_config)
    
    try:
        # Tentative de création du bucket
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={
                "LocationConstraint": aws_config["region_name"]
            }
        )
        print(f"✅ Bucket créé : s3://{bucket_name}")
        
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        # Le bucket existe déjà et vous en êtes le propriétaire → pas de problème
        print(f"ℹ️ Bucket existe déjà : s3://{bucket_name}")
        
    except Exception as e:
        print(f"❌ Erreur création bucket : {e}")


# ----- EXÉCUTION : Upload des données vers S3 -----

print("☁️ Chargement des données vers S3...")

# Chargement des CSV créés dans les parties précédentes
df_weather = pd.read_csv("weather_france_cities.csv")
df_weather_daily = pd.read_csv("weather_daily_details.csv")
df_hotels = pd.read_csv("hotels_france.csv")

# Création du bucket
create_s3_bucket(S3_BUCKET_NAME, AWS_CONFIG)

# Upload des fichiers bruts dans la zone "raw" du Data Lake
upload_to_s3(df_weather, S3_BUCKET_NAME, "raw/weather/cities_weather.csv", AWS_CONFIG)
upload_to_s3(df_weather_daily, S3_BUCKET_NAME, "raw/weather/daily_details.csv", AWS_CONFIG)
upload_to_s3(df_hotels, S3_BUCKET_NAME, "raw/hotels/hotels.csv", AWS_CONFIG)


# ╔══════════════════════════════════════════════════════════╗
# ║      PARTIE 2 : ETL — TRANSFORM (Nettoyage)            ║
# ╚══════════════════════════════════════════════════════════╝

# Le ETL (Extract, Transform, Load) est un processus fondamental en Data Engineering :
# - Extract : lire les données brutes (depuis S3 dans notre cas)
# - Transform : nettoyer, enrichir, restructurer
# - Load : charger vers le Data Warehouse (AWS RDS)

print("\n🔄 Étape ETL — Transform...")

# ----- EXTRACT : Lecture depuis S3 -----

def read_csv_from_s3(bucket_name, s3_key, aws_config):
    """
    Lit un CSV depuis S3 et le retourne comme DataFrame pandas.
    
    Explication jury :
    - get_object() télécharge le fichier depuis S3
    - ["Body"].read() lit le contenu binaire
    - io.BytesIO() le convertit en buffer lisible par pandas
    - pd.read_csv() peut lire depuis un buffer mémoire
    """
    
    s3_client = boto3.client("s3", **aws_config)
    
    response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
    
    # response["Body"] = stream de données
    # .read() = lit tout le contenu en bytes
    # io.BytesIO() = buffer binaire en mémoire
    content = response["Body"].read()
    df = pd.read_csv(io.BytesIO(content))
    
    return df


# Lecture depuis S3 (simule un vrai workflow ETL)
df_weather_raw = read_csv_from_s3(S3_BUCKET_NAME, "raw/weather/cities_weather.csv", AWS_CONFIG)
df_hotels_raw = read_csv_from_s3(S3_BUCKET_NAME, "raw/hotels/hotels.csv", AWS_CONFIG)

print("   ✅ Données extraites depuis S3")


# ----- TRANSFORM : Nettoyage et enrichissement -----

# Table CITIES (dimension géographique)
df_cities_clean = df_weather_raw[[
    "city_id", "city_name", "latitude", "longitude"
]].copy()

# Table WEATHER (faits météo)
df_weather_clean = df_weather_raw[[
    "city_id", "city_name", "avg_weather_score", "avg_temperature",
    "total_rain", "avg_humidity", "avg_wind", "rank"
]].copy()

# Renommage pour clarté en base de données
df_weather_clean = df_weather_clean.rename(columns={
    "avg_weather_score": "weather_score",
    "avg_temperature": "avg_temp_celsius",
    "avg_humidity": "avg_humidity_pct",
    "avg_wind": "avg_wind_ms"
})

# Arrondi des valeurs numériques
for col in ["weather_score", "avg_temp_celsius", "total_rain"]:
    df_weather_clean[col] = df_weather_clean[col].round(2)

# Table HOTELS : nettoyage
df_hotels_clean = df_hotels_raw.copy()

# Nettoyage du prix : "€ 89" → 89.0
def clean_price(price_str):
    """
    Extrait le nombre d'une chaîne comme "€ 89" ou "89 €".
    
    Explication jury :
    - re.findall() → trouve tous les nombres dans la chaîne (regex)
    - \d+ → motif regex qui matche un ou plusieurs chiffres
    """
    if pd.isna(price_str) or price_str == "N/A":
        return None
    import re
    numbers = re.findall(r'\d+', str(price_str))
    return float(numbers[0]) if numbers else None

df_hotels_clean["price_eur"] = df_hotels_clean["price_per_night"].apply(clean_price)

# Suppression des hôtels sans score
df_hotels_clean = df_hotels_clean.dropna(subset=["score"])
df_hotels_clean["score"] = pd.to_numeric(df_hotels_clean["score"], errors="coerce")

# Ajout de la clé étrangère city_id
df_hotels_clean = pd.merge(
    df_hotels_clean,
    df_cities_clean[["city_id", "city_name"]],
    on="city_name",
    how="left"
)

# Sélection des colonnes finales pour la BDD
df_hotels_final = df_hotels_clean[[
    "hotel_id", "city_id", "city_name", "hotel_name",
    "booking_url", "score", "price_eur", "description"
]].copy()

print(f"   ✅ {len(df_cities_clean)} villes nettoyées")
print(f"   ✅ {len(df_weather_clean)} entrées météo nettoyées")
print(f"   ✅ {len(df_hotels_final)} hôtels nettoyés")

# Upload des données transformées dans la zone "processed"
upload_to_s3(df_cities_clean, S3_BUCKET_NAME, "processed/cities.csv", AWS_CONFIG)
upload_to_s3(df_weather_clean, S3_BUCKET_NAME, "processed/weather.csv", AWS_CONFIG)
upload_to_s3(df_hotels_final, S3_BUCKET_NAME, "processed/hotels.csv", AWS_CONFIG)


# ╔══════════════════════════════════════════════════════════╗
# ║    PARTIE 3 : ETL — LOAD (vers AWS RDS PostgreSQL)     ║
# ╚══════════════════════════════════════════════════════════╝

# AWS RDS = Relational Database Service
# C'est une base de données PostgreSQL managée dans le cloud.
# On s'y connecte exactement comme à une BDD PostgreSQL locale.
#
# SQLAlchemy est un ORM (Object Relational Mapper) Python.
# Il permet d'interagir avec des BDD SQL en Python.
# create_engine() crée une connexion réutilisable.

print("\n🗄️ Connexion à AWS RDS (PostgreSQL)...")

# Construction de l'URL de connexion PostgreSQL
# Format : postgresql://user:password@host:port/database
DB_URL = (
    f"postgresql://{RDS_CONFIG['username']}:{RDS_CONFIG['password']}"
    f"@{RDS_CONFIG['host']}:{RDS_CONFIG['port']}"
    f"/{RDS_CONFIG['database']}"
)

# create_engine() établit la connexion à la base de données
# pool_pre_ping=True → vérifie la connexion avant chaque requête
engine = create_engine(DB_URL, pool_pre_ping=True)


def create_tables(engine):
    """
    Crée les tables SQL dans la base de données AWS RDS.
    
    Explication jury :
    - On utilise des requêtes SQL brutes avec SQLAlchemy
    - text() encapsule une chaîne SQL pour SQLAlchemy
    - SERIAL = auto-incrément en PostgreSQL
    - REFERENCES = clé étrangère (lien entre tables)
    - ON DELETE CASCADE = si une ville est supprimée, ses hôtels le sont aussi
    """
    
    with engine.connect() as conn:
        
        # Table CITIES
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cities (
                city_id     SERIAL PRIMARY KEY,
                city_name   VARCHAR(100) NOT NULL UNIQUE,
                latitude    DECIMAL(10, 6),
                longitude   DECIMAL(10, 6)
            );
        """))
        
        # Table WEATHER (liée à cities par city_id)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weather (
                id              SERIAL PRIMARY KEY,
                city_id         INTEGER REFERENCES cities(city_id) ON DELETE CASCADE,
                city_name       VARCHAR(100),
                weather_score   DECIMAL(5, 2),
                avg_temp_celsius    DECIMAL(5, 2),
                total_rain      DECIMAL(8, 2),
                avg_humidity_pct    DECIMAL(5, 2),
                avg_wind_ms     DECIMAL(5, 2),
                rank            INTEGER
            );
        """))
        
        # Table HOTELS (liée à cities par city_id)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS hotels (
                hotel_id        SERIAL PRIMARY KEY,
                city_id         INTEGER REFERENCES cities(city_id) ON DELETE CASCADE,
                city_name       VARCHAR(100),
                hotel_name      VARCHAR(255),
                booking_url     TEXT,
                score           DECIMAL(3, 1),
                price_eur       DECIMAL(8, 2),
                description     TEXT
            );
        """))
        
        # Commit : valide les transactions en attente
        conn.commit()
    
    print("   ✅ Tables créées dans AWS RDS")


def load_dataframe_to_rds(df, table_name, engine):
    """
    Charge un DataFrame pandas dans une table SQL.
    
    Explication jury :
    - df.to_sql() est la méthode pandas pour écrire dans une BDD SQL
    - if_exists="append" → ajoute les données (ne recrée pas la table)
    - if_exists="replace" → recrée la table (⚠️ supprime les données existantes)
    - index=False → ne pas écrire l'index pandas comme colonne
    - chunksize=1000 → insère par lots de 1000 lignes (plus performant)
    """
    
    df.to_sql(
        name=table_name,
        con=engine,
        if_exists="append",
        index=False,
        chunksize=1000
    )
    
    print(f"   ✅ {len(df)} lignes chargées dans la table '{table_name}'")


# ----- EXÉCUTION : Création des tables et chargement -----

create_tables(engine)

print("\n📤 Chargement des données dans AWS RDS...")
load_dataframe_to_rds(df_cities_clean, "cities", engine)
load_dataframe_to_rds(df_weather_clean, "weather", engine)
load_dataframe_to_rds(df_hotels_final, "hotels", engine)


# ╔══════════════════════════════════════════════════════════╗
# ║    PARTIE 4 : VÉRIFICATION — REQUÊTES SQL               ║
# ╚══════════════════════════════════════════════════════════╝

# On vérifie que les données sont bien dans la BDD
# en exécutant des requêtes SQL de vérification

print("\n🔍 Vérification des données dans AWS RDS...")

with engine.connect() as conn:
    
    # Requête 1 : Top 5 destinations
    top5_query = text("""
        SELECT c.city_name, w.weather_score, w.avg_temp_celsius, 
               w.total_rain, w.rank
        FROM weather w
        JOIN cities c ON w.city_id = c.city_id
        ORDER BY w.weather_score DESC
        LIMIT 5;
    """)
    
    # pd.read_sql() exécute une requête SQL et retourne un DataFrame pandas
    df_top5_check = pd.read_sql(top5_query, conn)
    print("\n🏆 TOP 5 DESTINATIONS (depuis RDS) :")
    print(df_top5_check.to_string(index=False))
    
    # Requête 2 : Top 20 hôtels
    top20_query = text("""
        SELECT h.hotel_name, h.city_name, h.score, h.price_eur
        FROM hotels h
        WHERE h.score IS NOT NULL
        ORDER BY h.score DESC
        LIMIT 20;
    """)
    
    df_top20_check = pd.read_sql(top20_query, conn)
    print("\n🏨 TOP 20 HÔTELS (depuis RDS) :")
    print(df_top20_check.to_string(index=False))
    
    # Requête 3 : Stats globales
    stats_query = text("""
        SELECT 
            (SELECT COUNT(*) FROM cities) as nb_cities,
            (SELECT COUNT(*) FROM hotels) as nb_hotels,
            (SELECT ROUND(AVG(weather_score)::numeric, 2) FROM weather) as avg_score
    """)
    
    df_stats = pd.read_sql(stats_query, conn)
    print(f"\n📊 STATS BDD : {df_stats.to_dict('records')[0]}")


print("\n✅ ETL complet ! Data Lake S3 + Data Warehouse RDS opérationnels.")
print(f"   → S3 : s3://{S3_BUCKET_NAME}/")
print(f"   → RDS : {RDS_CONFIG['host']}/{RDS_CONFIG['database']}")
