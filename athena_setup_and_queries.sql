
-- ────────────────────────────────────────
-- 3A. Créer la base de données
-- ────────────────────────────────────────
CREATE DATABASE IF NOT EXISTS world_simulation;


-- ────────────────────────────────────────
-- 3B. Table des habitants (partitionnée par étape)
-- ────────────────────────────────────────
CREATE EXTERNAL TABLE IF NOT EXISTS world_simulation.inhabitants (
    inhabitant_id  STRING,
    name           STRING,
    gender         STRING,
    age            INT,
    energy         INT,
    health         INT,
    continent      STRING,
    status         STRING,
    born_at_step   INT,
    died_at_step   INT
)
PARTITIONED BY (step STRING)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://world-simulation-rtes/inhabitants/'
TBLPROPERTIES ('has_encrypted_data'='false');

-- Indispensable : charge les partitions existantes
MSCK REPAIR TABLE world_simulation.inhabitants;


-- ────────────────────────────────────────
-- 3C. Table des événements (naissances, morts, catastrophes)
-- ────────────────────────────────────────
CREATE EXTERNAL TABLE IF NOT EXISTS world_simulation.events (
    type           STRING,
    cause          STRING,
    label          STRING,
    inhabitant_id  STRING,
    name           STRING,
    age            INT,
    gender         STRING,
    parent_m       STRING,
    parent_f       STRING,
    continent      STRING,
    killed         INT,
    survivors      INT,
    step           INT
)
PARTITIONED BY (step_folder STRING)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://world-simulation-rtes/events/'
TBLPROPERTIES ('has_encrypted_data'='false');

MSCK REPAIR TABLE world_simulation.events;


-- ────────────────────────────────────────
-- 3D. Table des snapshots de population
-- ────────────────────────────────────────
CREATE EXTERNAL TABLE IF NOT EXISTS world_simulation.stats (
    step             INT,
    timestamp        STRING,
    total_population INT,
    alive            INT,
    event            STRING
)
PARTITIONED BY (step_folder STRING)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://world-simulation-rtes/stats/'
TBLPROPERTIES ('has_encrypted_data'='false');

MSCK REPAIR TABLE world_simulation.stats;


-- ════════════════════════════════════════════════════════
-- REQUÊTES D'ANALYSE — À exécuter après quelques étapes
-- ════════════════════════════════════════════════════════


-- ── Q1 : Population vivante à chaque étape ───────────────
SELECT
    step,
    alive                               AS population_vivante,
    total_population                    AS population_totale,
    event
FROM world_simulation.stats
ORDER BY step ASC;


-- ── Q2 : Évolution de la population (avec variation) ─────
SELECT
    step,
    alive,
    alive - LAG(alive) OVER (ORDER BY step)  AS variation,
    event
FROM world_simulation.stats
ORDER BY step ASC;


-- ── Q3 : Répartition par continent à la dernière étape ───
SELECT
    continent,
    COUNT(*) AS nb_habitants,
    AVG(age)    AS age_moyen,
    AVG(energy) AS energie_moyenne
FROM world_simulation.inhabitants
WHERE status = 'alive'
  AND step = (SELECT MAX(step) FROM world_simulation.inhabitants)
GROUP BY continent
ORDER BY nb_habitants DESC;


-- ── Q4 : Impact de la catastrophe ────────────────────────
SELECT
    step,
    killed     AS morts_catastrophe,
    survivors  AS survivants
FROM world_simulation.events
WHERE type = 'catastrophe';


-- ── Q5 : Taux de mortalité par étape ─────────────────────
SELECT
    step,
    COUNT(*)                                         AS total_morts,
    COUNT(*) FILTER (WHERE cause = 'old_age')        AS mort_vieillesse,
    COUNT(*) FILTER (WHERE cause = 'asteroid_rain')  AS mort_asteroide
FROM world_simulation.events
WHERE type = 'death'
GROUP BY step
ORDER BY step ASC;


-- ── Q6 : Naissances par étape ────────────────────────────
SELECT
    step,
    COUNT(*) AS naissances,
    COUNT(*) FILTER (WHERE gender = 'M') AS garcons,
    COUNT(*) FILTER (WHERE gender = 'F') AS filles
FROM world_simulation.events
WHERE type = 'birth'
GROUP BY step
ORDER BY step ASC;


-- ── Q7 : Habitants les plus vieux encore en vie ──────────
SELECT
    name,
    age,
    continent,
    energy,
    born_at_step
FROM world_simulation.inhabitants
WHERE status = 'alive'
  AND step = (SELECT MAX(step) FROM world_simulation.inhabitants)
ORDER BY age DESC
LIMIT 10;


-- ── Q8 : Dernier survivant (fin du monde) ────────────────
SELECT
    name,
    age,
    continent,
    energy,
    born_at_step
FROM world_simulation.inhabitants
WHERE status = 'alive'
  AND step = (SELECT MAX(step) FROM world_simulation.inhabitants);
