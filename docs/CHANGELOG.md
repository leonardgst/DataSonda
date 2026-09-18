# Changelog — DataSonda

Historique des décisions et étapes franchies. Une entrée par avancée
significative, du plus récent au plus ancien. Ne pas détailler ici le
"comment" (c'est dans le code et les commits) — se concentrer sur le
"quoi" et le "pourquoi" des décisions.

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
