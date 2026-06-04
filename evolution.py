"""
ÉTAPE 2 — Glue Job d'évolution du monde virtuel
=================================================
À coller dans un AWS Glue Job (type : Spark / Python Shell).
Exécute ce job plusieurs fois pour faire évoluer la population.

Remplace BUCKET_NAME par le nom de ton bucket S3.
"""

import json
import uuid
import random
import boto3
from datetime import datetime

# ─────────────────────────────────────────
# CONFIGURATION — modifie cette ligne !
# ─────────────────────────────────────────
BUCKET_NAME = "world-simulation-rtes"   # <-- change ici

s3 = boto3.client("s3")

# ─────────────────────────────────────────
# PARAMÈTRES D'ÉVOLUTION
# ─────────────────────────────────────────
AGE_MAX          = 80    # un habitant meurt à 80 ans
ENERGY_LOSS      = -10    # énergie perdue par étape
ENERGY_GAIN = 10    # énergie gagnée par étape (ex : nourriture)
REPRODUCTION_MIN_AGE  = 18
REPRODUCTION_MAX_AGE  = 45
REPRODUCTION_ENERGY   = 50   # énergie minimale pour se reproduire
CHILDREN_PER_COUPLE   = 2    # nombre d'enfants par couple
CATASTROPHE_THRESHOLD = 1000 # population déclenchant la catastrophe
CATASTROPHE_MORTALITY = 0.60 # 60% des habitants meurent pendant la catastrophe


# ═══════════════════════════════════════════════════════════
# UTILITAIRES S3
# ═══════════════════════════════════════════════════════════

def read_current_step():
    """Trouve le numéro de la dernière étape dans S3."""
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="stats/")
    if "Contents" not in response:
        return 0
    steps = []
    for obj in response["Contents"]:
        key = obj["Key"]
        # Extrait le numéro depuis "stats/step=003/snapshot.json"
        if "step=" in key:
            try:
                num = int(key.split("step=")[1].split("/")[0])
                steps.append(num)
            except Exception:
                pass
    return max(steps) if steps else 0


def read_inhabitants(step):
    """Lit tous les habitants de l'étape donnée depuis S3."""
    key = f"inhabitants/step={str(step).zfill(3)}/data.json"
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        lines = obj["Body"].read().decode("utf-8").strip().split("\n")
        return [json.loads(line) for line in lines if line.strip()]
    except s3.exceptions.NoSuchKey:
        print(f"⚠️  Aucun habitant trouvé à l'étape {step}")
        return []


def save_inhabitants(inhabitants, step):
    """Sauvegarde la population de la nouvelle étape dans S3."""
    key = f"inhabitants/step={str(step).zfill(3)}/data.json"
    body = "\n".join(json.dumps(h) for h in inhabitants)
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=body,
        ContentType="application/json"
    )


def save_events(events, step):
    """Sauvegarde les événements (naissances, morts) de l'étape."""
    if not events:
        return
    key = f"events/step={str(step).zfill(3)}/events.json"
    body = "\n".join(json.dumps(e) for e in events)
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=body, ContentType="application/json")


def save_snapshot(step, population, alive, event_label):
    """Sauvegarde les statistiques globales de l'étape."""
    snapshot = {
        "step": step,
        "timestamp": datetime.utcnow().isoformat(),
        "total_population": population,
        "alive": alive,
        "event": event_label
    }
    key = f"stats/step={str(step).zfill(3)}/snapshot.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(snapshot, indent=2),
        ContentType="application/json"
    )
    return snapshot


# ═══════════════════════════════════════════════════════════
# LOGIQUE D'ÉVOLUTION
# ═══════════════════════════════════════════════════════════

def age_inhabitants(inhabitants):
    """Fait vieillir tous les habitants d'un an et réduit leur énergie."""
    for h in inhabitants:
        if h["status"] == "alive":
            h["age"] += 1
            h["energy"] = max(0, h["energy"] + random.randint(ENERGY_LOSS, ENERGY_GAIN))
    return inhabitants


def apply_natural_deaths(inhabitants, step, events):
    """Tue les habitants trop vieux ou à énergie nulle."""
    for h in inhabitants:
        if h["status"] == "alive":
            if h["age"] >= AGE_MAX or h["energy"] <= 0:
                h["status"] = "dead"
                h["died_at_step"] = step
                events.append({
                    "type": "death",
                    "cause": "old_age" if h["age"] >= AGE_MAX else "energy_depleted",
                    "inhabitant_id": h["inhabitant_id"],
                    "name": h["name"],
                    "age": h["age"],
                    "step": step
                })
                print(f"  ☠️  {h['name']} est mort (âge {h['age']})")
    return inhabitants, events


def reproduce(inhabitants, step, events):
    """Crée de nouveaux habitants par reproduction entre couples fertiles."""
    males   = [h for h in inhabitants if h["status"] == "alive"
               and h["gender"] == "M"
               and REPRODUCTION_MIN_AGE <= h["age"] <= REPRODUCTION_MAX_AGE
               and h["energy"] >= REPRODUCTION_ENERGY]

    females = [h for h in inhabitants if h["status"] == "alive"
               and h["gender"] == "F"
               and REPRODUCTION_MIN_AGE <= h["age"] <= REPRODUCTION_MAX_AGE
               and h["energy"] >= REPRODUCTION_ENERGY]

    new_inhabitants = []
    used_females = set()

    for male in males:
        available = [f for f in females if f["inhabitant_id"] not in used_females]
        if not available:
            break

        female = random.choice(available)
        used_females.add(female["inhabitant_id"])

        # Coût énergétique de la reproduction
        male["energy"]   -= 20
        female["energy"] -= 20

        for _ in range(CHILDREN_PER_COUPLE):
            child_gender = random.choice(["M", "F"])
            child_name   = generate_name(child_gender)
            child = {
                "inhabitant_id": str(uuid.uuid4()),
                "name": child_name,
                "gender": child_gender,
                "age": 0,
                "energy": 100,
                "health": 100,
                "continent": random.choice([male["continent"], female["continent"]]),
                "status": "alive",
                "born_at_step": step,
                "died_at_step": None
            }
            new_inhabitants.append(child)
            events.append({
                "type": "birth",
                "inhabitant_id": child["inhabitant_id"],
                "name": child_name,
                "gender": child_gender,
                "parent_m": male["name"],
                "parent_f": female["name"],
                "continent": child["continent"],
                "step": step
            })
            print(f"  👶 Naissance de {child_name} ({child_gender})")

    return inhabitants + new_inhabitants, events


def generate_name(gender):
    """Génère un nom aléatoire pour un nouvel habitant."""
    male_names   = ["Aeron","Balar","Corin","Dravik","Eryn","Falon",
                    "Garan","Havel","Idris","Joryn","Kael","Loran",
                    "Maren","Norik","Ovin","Palar","Quell","Ravan",
                    "Soren","Tavik","Ulran","Varen","Wylen","Xoran",
                    "Yavel","Zaren"]
    female_names = ["Aelya","Brynn","Ceira","Davan","Elyn","Fara",
                    "Gwyn","Hira","Isla","Joran","Kira","Lyara",
                    "Mira","Nera","Oryn","Pira","Quen","Reva",
                    "Syla","Tara","Uren","Vera","Wyra","Xela",
                    "Yara","Zeva"]
    pool = male_names if gender == "M" else female_names
    return random.choice(pool)


# ═══════════════════════════════════════════════════════════
# ÉVÉNEMENT CRITIQUE : CATASTROPHE
# ═══════════════════════════════════════════════════════════

def apply_catastrophe(inhabitants, step, events):
    """
    Déclenche une catastrophe (pluie d'astéroïdes) qui tue 60% de la population.
    S'active quand la population dépasse CATASTROPHE_THRESHOLD.
    """
    print("\n" + "═"*50)
    print("💥  CATASTROPHE : PLUIE D'ASTÉROÏDES !")
    print("═"*50)

    alive = [h for h in inhabitants if h["status"] == "alive"]
    nb_to_kill = int(len(alive) * CATASTROPHE_MORTALITY)
    victims = random.sample(alive, nb_to_kill)

    for h in victims:
        h["status"] = "dead"
        h["died_at_step"] = step
        h["health"] = 0
        events.append({
            "type": "death",
            "cause": "asteroid_rain",
            "inhabitant_id": h["inhabitant_id"],
            "name": h["name"],
            "age": h["age"],
            "step": step
        })

    survivors = len([h for h in inhabitants if h["status"] == "alive"])
    print(f"  ☄️  {nb_to_kill} habitants tués — {survivors} survivants")
    print("═"*50 + "\n")

    events.append({
        "type": "catastrophe",
        "label": "asteroid_rain",
        "killed": nb_to_kill,
        "survivors": survivors,
        "step": step
    })

    return inhabitants, events


# ═══════════════════════════════════════════════════════════
# PROGRAMME PRINCIPAL
# ═══════════════════════════════════════════════════════════

def main():
    events = []

    # 1. Trouver l'étape courante
    current_step = read_current_step()
    next_step    = current_step + 1
    print(f"\n🌍 Étape {current_step} → {next_step}")
    print("─"*40)

    # 2. Lire la population existante
    inhabitants = read_inhabitants(current_step)
    alive_before = [h for h in inhabitants if h["status"] == "alive"]
    print(f"📊 Population actuelle : {len(alive_before)} habitants vivants")

    # 3. Vieillissement
    print("\n⏳ Vieillissement...")
    inhabitants = age_inhabitants(inhabitants)

    # 4. Morts naturelles
    print("\n💀 Morts naturelles...")
    inhabitants, events = apply_natural_deaths(inhabitants, next_step, events)

    # 5. Vérifier la catastrophe AVANT la reproduction
    alive_now = [h for h in inhabitants if h["status"] == "alive"]
    catastrophe_triggered = False
    if len(alive_now) >= CATASTROPHE_THRESHOLD:
        inhabitants, events = apply_catastrophe(inhabitants, next_step, events)
        catastrophe_triggered = True

    # 6. Reproduction
    print("\n💞 Reproduction...")
    inhabitants, events = reproduce(inhabitants, next_step, events)

    # 7. Compter les vivants après reproduction
    alive_after = [h for h in inhabitants if h["status"] == "alive"]
    print(f"\n📈 Population après évolution : {len(alive_after)} habitants vivants")

    # 8. ☠️ FIN DU MONDE — dernier survivant
    if len(alive_after) == 1:
        last = alive_after[0]
        print("\n" + "═"*50)
        print(f"☠️  FIN DU MONDE — dernier survivant : {last['name']}")
        print("═"*50)

        # Sauvegarde avant l'échec
        save_inhabitants(inhabitants, next_step)
        save_events(events, next_step)
        save_snapshot(next_step, len(inhabitants), 1, "end_of_world")

        # Échec volontaire — visible dans CloudWatch
        raise RuntimeError(
            f"[END_OF_WORLD] Le monde s'est éteint à l'étape {next_step}. "
            f"Dernier survivant : {last['name']}, âge {last['age']}."
        )

    if len(alive_after) == 0:
        save_inhabitants(inhabitants, next_step)
        save_events(events, next_step)
        save_snapshot(next_step, len(inhabitants), 0, "extinction")
        raise RuntimeError(f"[EXTINCTION] Toute vie a disparu à l'étape {next_step}.")

    # 9. Sauvegarde dans S3
    event_label = "catastrophe" if catastrophe_triggered else "normal_evolution"
    save_inhabitants(inhabitants, next_step)
    save_events(events, next_step)
    snap = save_snapshot(next_step, len(inhabitants), len(alive_after), event_label)

    print(f"\n✅ Étape {next_step} sauvegardée dans S3")
    print(f"   Vivants  : {snap['alive']}")
    print(f"   Événement: {snap['event']}")
    print(f"   Timestamp: {snap['timestamp']}")


# ─────────────────────────────────────────
main()