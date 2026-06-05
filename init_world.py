import json
import uuid
import boto3
from datetime import datetime

# ─────────────────────────────────────────
# CONFIGURATION — modifie cette ligne !
# ─────────────────────────────────────────
BUCKET_NAME = "world-simulation-rtes"   # <-- change ici
STEP = "000"   # étape initiale

s3 = boto3.client("s3")

# ─────────────────────────────────────────
# 1. Création de la planète
# ─────────────────────────────────────────
planet = {
    "planet_id": str(uuid.uuid4()),
    "name": "Terra Nova",
    "created_at": datetime.utcnow().isoformat(),
    "continents": ["Arkon", "Selvara"],
    "status": "alive"
}

s3.put_object(
    Bucket=BUCKET_NAME,
    Key="world/planet.json",
    Body=json.dumps(planet, indent=2),
    ContentType="application/json"
)
print(f"✅ Planète créée : {planet['name']}")

# ─────────────────────────────────────────
# 2. Création des continents
# ─────────────────────────────────────────
continents = [
    {
        "continent_id": str(uuid.uuid4()),
        "name": "Arkon",
        "climate": "temperate",
        "fertility_rate": 1.5    # taux de reproduction plus élevé
    },
    {
        "continent_id": str(uuid.uuid4()),
        "name": "Selvara",
        "climate": "tropical",
        "fertility_rate": 2.0    # continent très fertile
    }
]

s3.put_object(
    Bucket=BUCKET_NAME,
    Key="world/continents.json",
    Body=json.dumps(continents, indent=2),
    ContentType="application/json"
)
print(f"✅ {len(continents)} continents créés : {[c['name'] for c in continents]}")

# ─────────────────────────────────────────
# 3. Création des 2 premiers habitants
# ─────────────────────────────────────────
inhabitants = [
    {
        "inhabitant_id": str(uuid.uuid4()),
        "name": "Aelion",
        "gender": "M",
        "age": 25,
        "energy": 100,
        "health": 100,
        "continent": "Arkon",
        "status": "alive",
        "born_at_step": 0,
        "died_at_step": None
    },
    {
        "inhabitant_id": str(uuid.uuid4()),
        "name": "Lyara",
        "gender": "F",
        "age": 22,
        "energy": 100,
        "health": 100,
        "continent": "Arkon",
        "status": "alive",
        "born_at_step": 0,
        "died_at_step": None
    }
]

# Sauvegarde en JSON (le Glue Crawler pourra lire ce format)
inhabitants_json = "\n".join(json.dumps(h) for h in inhabitants)

s3.put_object(
    Bucket=BUCKET_NAME,
    Key=f"inhabitants/step={STEP}/data.json",
    Body=inhabitants_json,
    ContentType="application/json"
)
print(f"✅ {len(inhabitants)} habitants créés : {[h['name'] for h in inhabitants]}")

# ─────────────────────────────────────────
# 4. Premier snapshot de stats
# ─────────────────────────────────────────
snapshot = {
    "step": int(STEP),
    "timestamp": datetime.utcnow().isoformat(),
    "total_population": len(inhabitants),
    "alive": len([h for h in inhabitants if h["status"] == "alive"]),
    "event": "world_created"
}

s3.put_object(
    Bucket=BUCKET_NAME,
    Key=f"stats/step={STEP}/snapshot.json",
    Body=json.dumps(snapshot, indent=2),
    ContentType="application/json"
)
print(f"✅ Snapshot initial enregistré : {snapshot['total_population']} habitant(s)")

# ─────────────────────────────────────────
# RÉSUMÉ
# ─────────────────────────────────────────
print("\n🌍 Monde initialisé avec succès !")
print(f"   Planète   : {planet['name']}")
print(f"   Continents: {[c['name'] for c in continents]}")
print(f"   Population: {len(inhabitants)} habitants")
print(f"\n📁 Structure S3 créée dans : s3://{BUCKET_NAME}/")
print("   ├── world/planet.json")
print("   ├── world/continents.json")
print("   ├── inhabitants/step=000/data.json")
print("   └── stats/step=000/snapshot.json")