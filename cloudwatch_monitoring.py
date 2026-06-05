import json
import uuid
import random
import boto3
import logging
from datetime import datetime

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
BUCKET_NAME    = "world-simulation-tonprenom"   # <-- change ici
NAMESPACE      = "WorldSimulation"              # namespace CloudWatch custom
JOB_NAME       = "world-evolution-job"          # nom de ton Glue Job

s3         = boto3.client("s3")
cloudwatch = boto3.client("cloudwatch", region_name="us-east-1")  # adapte ta région

# ─────────────────────────────────────────
# LOGGER structuré (visible dans CloudWatch Logs)
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# MÉTRIQUES CLOUDWATCH CUSTOM
# ═══════════════════════════════════════════════════════════

def send_metric(metric_name, value, unit="Count", step=0):
    """
    Envoie une métrique custom dans CloudWatch.
    Visible dans : CloudWatch → Metrics → Custom namespaces → WorldSimulation
    """
    try:
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": [
                        {"Name": "JobName", "Value": JOB_NAME},
                        {"Name": "Step",    "Value": str(step)}
                    ],
                    "Timestamp": datetime.utcnow()
                }
            ]
        )
        log.info(f"[METRIC] {metric_name} = {value} (step {step})")
    except Exception as e:
        log.warning(f"[METRIC ERROR] {metric_name} — {e}")


def send_all_metrics(step, alive, total, births, deaths, event_label):
    """Envoie toutes les métriques de l'étape courante en une fois."""
    send_metric("PopulationAlive",  alive,  step=step)
    send_metric("PopulationTotal",  total,  step=step)
    send_metric("Births",           births, step=step)
    send_metric("Deaths",           deaths, step=step)

    # Métrique binaire : catastrophe en cours (0 ou 1)
    is_catastrophe = 1 if event_label == "catastrophe" else 0
    send_metric("CatastropheTriggered", is_catastrophe, step=step)

    # Métrique binaire : fin du monde imminente
    end_of_world = 1 if alive <= 1 else 0
    send_metric("EndOfWorld", end_of_world, step=step)

    log.info(
        f"[STEP {step}] alive={alive} total={total} "
        f"births={births} deaths={deaths} event={event_label}"
    )


# ═══════════════════════════════════════════════════════════
# ALERTES CLOUDWATCH — À créer via la console AWS
# ═══════════════════════════════════════════════════════════
"""
Crée ces 3 alarmes dans CloudWatch → Alarms → Create alarm :

── ALARME 1 : Catastrophe imminente ──────────────────────────
  Metric    : WorldSimulation > PopulationAlive
  Condition : >= 900  (seuil d'alerte avant les 1000)
  Period    : 60 secondes
  Action    : (optionnel) SNS notification
  Name      : world-population-critical

── ALARME 2 : Catastrophe déclenchée ────────────────────────
  Metric    : WorldSimulation > CatastropheTriggered
  Condition : >= 1
  Period    : 60 secondes
  Name      : world-catastrophe-triggered

── ALARME 3 : Fin du monde ──────────────────────────────────
  Metric    : WorldSimulation > EndOfWorld
  Condition : >= 1
  Period    : 60 secondes
  Name      : world-end-of-world
  → Cette alarme passe en ALARM quand le job échoue volontairement
"""


def create_cloudwatch_alarms():
    """
    Crée les alarmes CloudWatch automatiquement via le SDK.
    Exécute cette fonction UNE SEULE FOIS dans un notebook Glue.
    """

    # Alarme 1 : Population critique (proche de 1000)
    cloudwatch.put_metric_alarm(
        AlarmName="world-population-critical",
        AlarmDescription="Population proche du seuil de catastrophe (900+)",
        Namespace=NAMESPACE,
        MetricName="PopulationAlive",
        Dimensions=[{"Name": "JobName", "Value": JOB_NAME}],
        Statistic="Maximum",
        Period=60,
        EvaluationPeriods=1,
        Threshold=900,
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        TreatMissingData="notBreaching"
    )
    log.info("[ALARM CREATED] world-population-critical")

    # Alarme 2 : Catastrophe déclenchée
    cloudwatch.put_metric_alarm(
        AlarmName="world-catastrophe-triggered",
        AlarmDescription="Une catastrophe majeure a frappé le monde",
        Namespace=NAMESPACE,
        MetricName="CatastropheTriggered",
        Dimensions=[{"Name": "JobName", "Value": JOB_NAME}],
        Statistic="Maximum",
        Period=60,
        EvaluationPeriods=1,
        Threshold=1,
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        TreatMissingData="notBreaching"
    )
    log.info("[ALARM CREATED] world-catastrophe-triggered")

    # Alarme 3 : Fin du monde
    cloudwatch.put_metric_alarm(
        AlarmName="world-end-of-world",
        AlarmDescription="Le monde s'est eteint — dernier survivant detecte",
        Namespace=NAMESPACE,
        MetricName="EndOfWorld",
        Dimensions=[{"Name": "JobName", "Value": JOB_NAME}],
        Statistic="Maximum",
        Period=60,
        EvaluationPeriods=1,
        Threshold=1,
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        TreatMissingData="notBreaching"
    )
    log.info("[ALARM CREATED] world-end-of-world")

    print("\n✅ 3 alarmes CloudWatch créées avec succès !")
    print("   Consulte-les dans : CloudWatch → Alarms")


# ═══════════════════════════════════════════════════════════
# VERSION COMPLÈTE DU MAIN — remplace celui d'evolution_job.py
# ═══════════════════════════════════════════════════════════
# (copie les fonctions utilitaires S3 et d'évolution
#  depuis evolution_job.py, puis utilise ce main à la place)

def main():
    events       = []
    births_count = 0
    deaths_count = 0

    # 1. Trouver l'étape courante
    current_step = read_current_step()
    next_step    = current_step + 1
    log.info(f"[START] Étape {current_step} → {next_step}")

    # 2. Lire la population
    inhabitants  = read_inhabitants(current_step)
    alive_before = [h for h in inhabitants if h["status"] == "alive"]
    log.info(f"[POPULATION] {len(alive_before)} habitants vivants au départ")

    # 3. Vieillissement
    inhabitants = age_inhabitants(inhabitants)

    # 4. Morts naturelles
    inhabitants, events = apply_natural_deaths(inhabitants, next_step, events)
    deaths_count = len([e for e in events if e["type"] == "death"])

    # 5. Catastrophe si seuil atteint
    alive_now = [h for h in inhabitants if h["status"] == "alive"]
    catastrophe_triggered = False
    if len(alive_now) >= CATASTROPHE_THRESHOLD:
        inhabitants, events   = apply_catastrophe(inhabitants, next_step, events)
        catastrophe_triggered = True
        deaths_count += len([
            e for e in events
            if e["type"] == "death" and e.get("cause") == "asteroid_rain"
        ])
        log.warning(f"[CATASTROPHE] Astéroïdes à l'étape {next_step} !")

    # 6. Reproduction
    before_repro = len(inhabitants)
    inhabitants, events = reproduce(inhabitants, next_step, events)
    births_count = len(inhabitants) - before_repro

    # 7. Compter les vivants
    alive_after = [h for h in inhabitants if h["status"] == "alive"]
    event_label = "catastrophe" if catastrophe_triggered else "normal_evolution"

    # 8. Envoyer les métriques CloudWatch
    send_all_metrics(
        step        = next_step,
        alive       = len(alive_after),
        total       = len(inhabitants),
        births      = births_count,
        deaths      = deaths_count,
        event_label = event_label
    )

    # 9. ☠️ FIN DU MONDE
    if len(alive_after) == 1:
        last = alive_after[0]
        log.error(
            f"[END_OF_WORLD] Dernier survivant : {last['name']}, "
            f"âge {last['age']}, continent {last['continent']}"
        )
        send_metric("EndOfWorld", 1, step=next_step)

        save_inhabitants(inhabitants, next_step)
        save_events(events, next_step)
        save_snapshot(next_step, len(inhabitants), 1, "end_of_world")

        # Échec volontaire — observable dans CloudWatch
        raise RuntimeError(
            f"[END_OF_WORLD] Le monde s'est éteint à l'étape {next_step}. "
            f"Dernier survivant : {last['name']}, âge {last['age']}."
        )

    if len(alive_after) == 0:
        log.error(f"[EXTINCTION] Toute vie a disparu à l'étape {next_step}.")
        save_inhabitants(inhabitants, next_step)
        save_events(events, next_step)
        save_snapshot(next_step, len(inhabitants), 0, "extinction")
        raise RuntimeError(f"[EXTINCTION] Toute vie disparue à l'étape {next_step}.")

    # 10. Sauvegarde S3
    save_inhabitants(inhabitants, next_step)
    save_events(events, next_step)
    save_snapshot(next_step, len(inhabitants), len(alive_after), event_label)

    log.info(
        f"[END] Étape {next_step} terminée — "
        f"{len(alive_after)} vivants, {births_count} naissances, "
        f"{deaths_count} morts"
    )


# ─────────────────────────────────────────
# Pour créer les alarmes (une seule fois) :
#   create_cloudwatch_alarms()
#
# Pour lancer une étape d'évolution :
#   main()
# ─────────────────────────────────────────
