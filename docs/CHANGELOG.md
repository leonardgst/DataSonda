# Changelog — DataSonda

Historique des décisions et étapes franchies. Une entrée par avancée
significative, du plus récent au plus ancien. Ne pas détailler ici le
"comment" (c'est dans le code et les commits) — se concentrer sur le
"quoi" et le "pourquoi" des décisions.

## Correctif post-revue de la Phase 2

- **2026-09-21** — Une colonne Arrow imbriquée (`list`, `struct`, `map`) faisait
  planter tout le profil : `nunique()` lève alors `ArrowNotImplementedError`,
  qui hérite de `NotImplementedError` et non de `TypeError`. Cela contredisait
  la règle « non calculable = `None`, jamais de plantage ».
  - Décision : deux clauses `except` et deux messages distincts,
    `"n_unique not computed: unhashable values"` (inchangé) et
    `"n_unique not computed: unsupported dtype"` ; les autres champs restent
    calculés. Alternatives écartées : `except Exception` (masquerait de vrais
    bugs) et un message unique générique (moins précis).
  - Vérifié sous pandas 3.0.6 et 2.3.3 avec un vrai `pyarrow`, installé
    temporairement. `pyarrow` n'est pas une dépendance : le test Arrow réel est
    ignoré en CI, le test monkeypatch couvre la branche.

## Phase 2 — Profil de base des colonnes

- **2026-09-18** — Pour chaque colonne : famille de dtype, nombre de lignes,
  valeurs manquantes (nombre, non-manquantes, taux), valeurs distinctes,
  avertissements. Résultat structuré, immuable et sérialisable en JSON
  (`DatasetProfile` → `ColumnProfile`), calculé par `profile_dataframe(df)`.
  Quatre commits : correctif de validation, classification des dtypes,
  profil de colonne, profil de dataset.
  - **Changement de feuille de route :** cette phase remplace le chargement
    CSV, qui était prévu ici. Raison : le profil des valeurs est la matière
    première des phases suivantes (types, qualité, statistiques) ; le CSV
    n'est qu'une porte d'entrée de plus. Le CSV est repoussé (phase à fixer
    lors du prochain cadrage).
  - Décision : famille de dtype = enum `DtypeFamily` (`numeric`, `boolean`,
    `datetime`, `categorical`, `text_or_object`, `other`), identique sous
    pandas 2 et 3. L'ordre des tests fait la classification : booléen avant
    numérique (`is_numeric_dtype` est vrai pour un booléen), catégoriel avant
    texte (`is_string_dtype` est vrai pour une Series `category`). On classe
    le dtype, pas la Series (aucun parcours de valeurs sous pandas 2).
    Alternative écartée : comparer des chaînes de dtype (`str` vs `object`,
    `datetime64[us]` vs `[ns]` selon la version de pandas).
  - Décision : les complexes vont dans `other`. Leurs prédicats pandas disent
    « numérique », mais ils n'ont pas d'ordre : min, max et médiane n'auraient
    pas de sens pour les statistiques à venir.
  - Décision : timedelta, période et intervalle vont aussi dans `other`.
    Limite connue : un booléen contenant `None` est de dtype `object`, donc
    `text_or_object`, jusqu'à l'inférence de types (Phase 3).
  - Décision : valeur manquante = nul au sens pandas (`isna()` : `None`,
    `NaN`, `pd.NA`, `NaT`). `inf`, `""`, `" "`, `"N/A"`, `"-999"` ne comptent
    pas ; les chaînes vides auront une métrique distincte plus tard.
  - Décision : « non calculable » = `None`, jamais NaN ni 0 (`missing_rate`
    sur 0 ligne ; `n_unique` sur valeurs non hachables, avec l'avertissement
    `"n_unique not computed: unhashable values"`). Alternative écartée : laisser
    le `TypeError` remonter, ce qui aurait fait échouer tout le profil pour
    une seule colonne de listes. `n_unique` exclut les manquants.
  - Décision : `profile_column(name, series)` ne valide rien et traite une
    colonne à la fois (frontière prévue pour un futur moteur Polars/DuckDB) ;
    `profile_dataframe` parcourt les colonnes par position, jamais par le nom
    converti en texte.
  - Correctif de la Phase 1 : `1` (entier) et `"1"` (texte) passaient la
    validation mais devenaient le même nom dans les résultats.
    `validate_dataframe` lève désormais `ValueError`. Alternative écartée :
    renommer automatiquement (masquerait le problème à l'utilisateur).
  - Hors périmètre volontaire : statistiques descriptives, inférence de types
    et de rôles, alertes/seuils, doublons de lignes, chaînes vides, export
    JSON/HTML, exports dans `__init__.py` (aucune façade avant `analyze`),
    colonnes MultiIndex.
  - Vérifié : 70 tests verts sous pandas 3.0.6 et sous pandas 2.3.3 ; aucune
    dépendance ajoutée.

## Hygiène du packaging (entre Phase 1 et Phase 2)

- **2026-09-18** — Audit du wheel et du sdist, puis six correctifs (un commit
  chacun, sauf la CI qui en compte deux).
  - sdist : liste `include` explicite. Il embarquait `CLAUDE.md`,
    `.claude/settings.local.json` et `uv.lock` (54 Ko → 3,6 Ko). Wheel inchangé.
  - Auteur : suppression du placeholder « Ton Nom » ; nom seul, sans e-mail
    (facultatif selon PEP 621, ajoutable plus tard).
  - Encodage : `LICENSE` et `README.md` contenaient du mojibake (double
    encodage UTF-8, cause probable : PowerShell). Corrigé ; le nom corrigé se
    propage dans le `METADATA` du wheel.
  - `py.typed` ajouté : sans lui, mypy chez l'utilisateur ignore les
    annotations du package (vérifié avant/après sur un script consommateur).
  - mypy : suppression de `python_version = "3.11"`. Décision : mypy suit
    l'interpréteur ; la cellule 3.11 de la CI garde la vérification de la
    version minimale. Réversible (une ligne). Alternative écartée : ne lancer
    mypy que sur 3.11 (condition `if:` en plus dans le workflow).
  - CI : matrice Python 3.11/3.12/3.13 (`fail-fast: false`) et étape pandas
    2.x sur 3.11 uniquement (`pandas<3` par-dessus l'environnement verrouillé).
  - Non traité volontairement : façade de `__init__.py` (décision d'API à
    prendre avec l'arrivée de `analyze`).

## Phase 1 — Modèle de données et entrée DataFrame

- **2026-09-18** — Entrée DataFrame et métadonnées générales : validation
  (`validate_dataframe`) et calcul (`describe_dataframe`) → `DatasetMetadata`.
  - Décision : résultats en `dataclass(frozen=True)` plutôt que pydantic —
    zéro dépendance, immuable, typage strict natif. Réversible : la
    migration ne toucherait que `models.py`.
  - Décision : rejeter les DataFrames sans colonnes et les noms de colonnes
    dupliqués (ils casseraient l'analyse par colonne) ; accepter 0 ligne.
  - Ajout de `pandas-stubs` en dépendance dev, nécessaire à `mypy --strict`.

## Phase 0 — Initialisation du dépôt (terminée)

- **2026-09-18** — Mise en place du workflow de continuité entre sessions :
  `CLAUDE.md` (racine, lu automatiquement par Claude Code) + `docs/NEXT_STEPS.md`
  (snapshot d'état, réécrit) + `docs/CHANGELOG.md` (historique, cumulatif).
  Raison : éviter de retransmettre tout l'historique à chaque nouvelle
  session, que ce soit ici ou dans Claude Code.
- **2026-09-18** — Dépôt GitHub créé (public) et cloné en local. Squelette
  du package généré : `pyproject.toml`, `LICENSE` (MIT), `.gitignore`,
  `README.md`, `src/datasonde/__init__.py`, `tests/test_import.py`,
  `.github/workflows/ci.yml`.
  - Décision : gestionnaire de projet `uv` — rapide, gère env/deps/build/
    publish en un seul outil, standard émergent de l'écosystème Python 2026.
  - Décision : licence MIT — permissive, standard pour un projet portfolio.
  - Décision : backend de build `hatchling` — simple, s'intègre nativement
    avec `uv`.
  - Décision : layout `src/datasonde/` plutôt qu'un package à plat — force
    l'installation avant import, évite les faux positifs de tests liés aux
    imports relatifs.
  - Décision : Python ≥ 3.11 — syntaxe `X | Y` pour les types sans imports.
  - Décision : `ruff` pour lint + format (remplace black/flake8/isort).
  - Bug rencontré et corrigé : `Set-Content -Encoding utf8` sous PowerShell
    ajoute un BOM UTF-8, incompatible avec le parsing TOML de hatchling.
