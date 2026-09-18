# État du projet — DataSonda

_Dernière mise à jour : 2026-09-18_

## Phase en cours

Phase 1 — Modèle de données et entrée DataFrame (implémentée, à valider en CI)

## Ce qui est fait

- Phase 0 terminée : dépôt GitHub public, squelette uv + hatchling, licence
  MIT, `src/datasonde/`, `tests/`, CI GitHub Actions, `CLAUDE.md` + `docs/`
- Phase 1 : `models.py` (`ColumnInfo`, `DatasetMetadata`, dataclasses frozen
  avec `to_dict()`), `metadata.py` (`validate_dataframe`, `describe_dataframe`),
  `tests/test_metadata.py` (9 tests). `pandas-stubs` ajouté en dépendance dev
  (requis par `mypy --strict`)
- Vérifications locales vertes : pytest (10 tests), ruff, mypy

## En cours / à vérifier

- Confirmer dans l'onglet Actions GitHub que la CI est verte (commit de
  la Phase 1 pas encore poussé)

## Décisions actées

- Gestionnaire de projet : `uv` ; licence MIT ; build : `hatchling`
- Layout : `src/datasonde/` ; Python ≥ 3.11
- Lint/format : `ruff` ; typage : `mypy --strict` (+ `pandas-stubs`)
- Modèles de résultat : `dataclass(frozen=True)` de la stdlib (pas de
  pydantic à ce stade ; migration possible plus tard, limitée à `models.py`)
- Validation d'entrée : `TypeError` si non-DataFrame ; `ValueError` si aucune
  colonne ou noms de colonnes dupliqués ; DataFrame sans lignes accepté

## Prochaine étape

**Phase 2** (à cadrer avec toi avant de coder) : profiling par colonne —
valeurs manquantes, cardinalité, statistiques descriptives selon le type

## Pièges connus / notes pour reprise

- PowerShell 5.1 : toujours utiliser `[System.IO.File]::WriteAllText` avec
  `UTF8Encoding($false)` pour écrire des fichiers texte (jamais
  `Set-Content -Encoding utf8`, qui ajoute un BOM)
- Claude Code lit `CLAUDE.md` (racine) automatiquement à chaque session,
  qui référence ce fichier — donc mettre à jour ce fichier suffit à garder
  Claude Code à jour, pas besoin de réexpliquer l'historique
