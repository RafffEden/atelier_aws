# 🌍 World Simulation — Pipeline de données AWS

Simulation d'un monde virtuel évolutif sur AWS, avec pipeline de données (S3 + Glue + Athena) et monitoring (CloudWatch).

---

## 📐 Architecture

```
Script Python          AWS Glue Job           Amazon S3
(init_world.py)  ───►  (evolution_job.py) ───► world/
                              │                inhabitants/step=NNN/
                              │                events/step=NNN/
                              ▼                stats/step=NNN/
                       CloudWatch                    │
                       Logs + Métriques              ▼
                       Alarmes             AWS Glue Crawler
                                                     │
                                                     ▼
                                            Amazon Athena
                                            (requêtes SQL)
```

### Services utilisés

| Service | Rôle |
|---|---|
| **Amazon S3** | Stockage des données (habitants, événements, snapshots) |
| **AWS Glue** | Traitement et évolution de la population (PySpark / Python Shell) |
| **AWS Glue Crawler** | Détection automatique du schéma des fichiers S3 |
| **Amazon Athena** | Analyse SQL de la population à chaque étape |
| **Amazon CloudWatch** | Monitoring des métriques, logs et alarmes |

---

## 📁 Structure S3

```
world-simulation-<prénom>/
├── world/
│   ├── planet.json              # Données de la planète
│   └── continents.json          # Continents et leurs caractéristiques
├── inhabitants/
│   ├── step=000/data.json       # Population initiale (2 habitants)
│   ├── step=001/data.json       # Population après étape 1
│   └── step=NNN/data.json       # ...
├── events/
│   └── step=NNN/events.json     # Naissances, morts, catastrophes
├── stats/
│   └── step=NNN/snapshot.json   # Snapshot population totale
└── athena-results/              # Résultats des requêtes Athena
```

---

## 🚀 Déploiement — Étapes à suivre

### Prérequis

- Accès à un lab AWS avec S3, Glue, Athena et CloudWatch activés
- Région recommandée : `us-east-1`

---

### Étape 1 — Créer le bucket S3

1. Aller dans **S3 → Créer un bucket**
2. Nommer le bucket : `world-simulation-<tonprenom>` (doit être unique)
3. Laisser toutes les options par défaut → **Créer**
4. Dans le bucket, créer manuellement les dossiers : `world/`, `inhabitants/`, `events/`, `stats/`, `athena-results/`

---

### Étape 2 — Initialiser le monde (`init_world.py`)

1. Aller dans **AWS Glue → Notebooks ETL → Créer un notebook**
2. Choisir le kernel **Python Shell**
3. Coller le contenu de `init_world.py`
4. Remplacer `BUCKET_NAME` par le nom de ton bucket
5. Exécuter la cellule

**Résultat attendu :**
```
✅ Planète créée : Terra Nova
✅ 2 continents créés : ['Arkon', 'Selvara']
✅ 2 habitants créés : ['Aelion', 'Lyara']
✅ Snapshot initial enregistré : 2 habitant(s)
🌍 Monde initialisé avec succès !
```

Vérifier dans S3 que `world/planet.json`, `world/continents.json` et `inhabitants/step=000/data.json` sont bien créés.

---

### Étape 3 — Lancer les étapes d'évolution (`cloudwatch_monitoring.py`)

1. Dans le même notebook, créer une nouvelle cellule
2. Coller le contenu de `cloudwatch_monitoring.py`
3. Coller également les fonctions utilitaires de `evolution_job.py` (S3, vieillissement, reproduction, catastrophe)
4. Remplacer `BUCKET_NAME` et vérifier la `region_name` de CloudWatch
5. Exécuter `create_cloudwatch_alarms()` **une seule fois** pour créer les 3 alarmes
6. Exécuter `main()` à chaque fois pour avancer d'une étape

**Résultat attendu à chaque étape :**
```
[INFO] [START] Étape 3 → 4
[INFO] [POPULATION] 46 habitants vivants au départ
[INFO] ⏳ Vieillissement...
[INFO] 💀 Morts naturelles...
[INFO] 💞 Reproduction...
[INFO] 👶 Naissance de Kira (F)
[INFO] 📈 Population après évolution : 94 habitants vivants
[INFO] [END] Étape 4 terminée — 94 vivants, 48 naissances, 2 morts
```

**À l'étape de la catastrophe (≥ 1000 habitants) :**
```
[WARNING] [CATASTROPHE] Astéroïdes à l'étape 12 !
💥 CATASTROPHE : PLUIE D'ASTÉROÏDES !
☄️  600 habitants tués — 400 survivants
```

**À la fin du monde (1 seul habitant) :**
```
[ERROR] [END_OF_WORLD] Dernier survivant : Lyara, âge 43
RuntimeError: [END_OF_WORLD] Le monde s'est éteint à l'étape 24.
```
Le job **échoue volontairement** — cet échec est visible dans CloudWatch.

---

### Étape 4 — Configurer Athena (`athena_setup_and_queries.sql`)

1. Aller dans **Athena → Settings** → définir le dossier de résultats :
   `s3://world-simulation-<tonprenom>/athena-results/`
2. Ouvrir l'éditeur de requêtes
3. Exécuter les blocs SQL **dans l'ordre**, un par un :
   - `CREATE DATABASE`
   - `CREATE TABLE inhabitants` + `MSCK REPAIR TABLE`
   - `CREATE TABLE events` + `MSCK REPAIR TABLE`
   - `CREATE TABLE stats` + `MSCK REPAIR TABLE`

> ⚠️ Relancer `MSCK REPAIR TABLE` après chaque nouvelle étape d'évolution pour charger les nouvelles partitions.

---

### Étape 5 — Vérifier le monitoring CloudWatch

- **Logs** : `CloudWatch → Logs → Log groups → /aws-glue/jobs/output`
- **Métriques** : `CloudWatch → Metrics → Custom namespaces → WorldSimulation`
- **Alarmes** : `CloudWatch → Alarms` → vérifier les 3 alarmes créées

| Alarme | Condition | Signification |
|---|---|---|
| `world-population-critical` | Population ≥ 900 | Catastrophe imminente |
| `world-catastrophe-triggered` | CatastropheTriggered ≥ 1 | Catastrophe en cours |
| `world-end-of-world` | EndOfWorld ≥ 1 | Fin du monde atteinte |

---

## 📊 Requêtes Athena — Résultats attendus

### Population à chaque étape (Q1)

| step | population_vivante | variation | event |
|---|---|---|---|
| 0 | 2 | — | world_created |
| 1 | 6 | +4 | normal_evolution |
| 2 | 18 | +12 | normal_evolution |
| 3 | 46 | +28 | normal_evolution |
| 12 | 412 | -612 | catastrophe |
| 24 | 1 | -N | end_of_world |

### Impact de la catastrophe (Q4)

| step | morts_catastrophe | survivants |
|---|---|---|
| 12 | 612 | 412 |

### Dernier survivant (Q8)

| name | age | continent | energy | born_at_step |
|---|---|---|---|---|
| Lyara | 43 | Arkon | 30 | 0 |

---

## 🧩 Modélisation des habitants

```json
{
  "inhabitant_id": "uuid",
  "name": "Aelion",
  "gender": "M",
  "age": 25,
  "energy": 100,
  "health": 100,
  "continent": "Arkon",
  "status": "alive",
  "born_at_step": 0,
  "died_at_step": null
}
```

### Logique d'évolution

| Règle | Valeur |
|---|---|
| Âge maximum | 80 ans |
| Perte d'énergie par étape | 10 points |
| Âge de reproduction | 18 – 45 ans |
| Énergie minimale pour reproduire | 50 points |
| Enfants par couple | 2 |
| Seuil de catastrophe | 1 000 habitants |
| Mortalité catastrophe | 60% |

---

## 💡 Pour aller plus loin

- Ajouter plusieurs continents avec des taux de fertilité différents
- Implémenter plusieurs types d'habitants (guerriers, sages, explorateurs)
- Simuler plusieurs types de catastrophes (épidémie, famine, guerre)
- Ajouter des indicateurs avancés dans Athena (taux de reproduction, espérance de vie)
- Automatiser l'exécution du Glue Job avec **AWS EventBridge** (toutes les X minutes)

---

## ⚠️ Points d'attention

- **Sauvegarder les scripts en local** après chaque session : le lab AWS s'éteint et efface tout.
- Bien relancer `MSCK REPAIR TABLE` dans Athena après chaque étape d'évolution.
- Le `RuntimeError` final du job est **volontaire** — c'est le comportement attendu pour signaler la fin du monde dans CloudWatch.

---

## 📋 Fichiers du projet

| Fichier | Description |
|---|---|
| `init_world.py` | Initialisation de la planète et des 2 premiers habitants |
| `evolution_job.py` | Logique d'évolution : vieillissement, reproduction, catastrophe |
| `cloudwatch_monitoring.py` | Métriques custom et alarmes CloudWatch |
| `athena_setup_and_queries.sql` | Création des tables et requêtes d'analyse |
| `README.md` | Ce fichier |