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
- Hygiène du packaging (7 commits, entre Phase 1 et Phase 2) : sdist
  restreint, auteur, encodage UTF-8, `py.typed`, mypy sans `python_version`,
  CI en matrice Python 3.11/3.12/3.13 + étape pandas 2.x (détails dans le
  CHANGELOG)

## En cours / à vérifier

- Pousser les correctifs de packaging et confirmer dans l'onglet Actions
  GitHub que la CI est verte sur 3.11, 3.12 et 3.13, ainsi que l'étape
  « Test against pandas 2.x » (validée localement, jamais exécutée sur
  GitHub)

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

- mypy : ne pas figer `python_version` dans `[tool.mypy]`. Sur Python ≥ 3.12,
  uv résout numpy 2.5 dont les stubs utilisent `type X = ...` (syntaxe
  3.12+) ; forcer 3.11 fait échouer mypy
- `uv.lock` verrouille pandas 3.x alors que `pyproject.toml` accepte
  `>=2.0` ; la CI réinstalle `pandas<3` sur 3.11 pour tester pandas 2
  (dernier 2.x, pas le plancher 2.0). Les dtypes texte diffèrent (`str` en
  3.x, `object` en 2.x) : à garder en tête pour l'inférence de types
- `.claude/settings.local.json` est suivi par Git alors que c'est un
  réglage local : à décider (le retirer de l'index et l'ignorer ?)
- PowerShell 5.1 : toujours utiliser `[System.IO.File]::WriteAllText` avec
  `UTF8Encoding($false)` pour écrire des fichiers texte (jamais
  `Set-Content -Encoding utf8`, qui ajoute un BOM)
- Claude Code lit `CLAUDE.md` (racine) automatiquement à chaque session,
  qui référence ce fichier — donc mettre à jour ce fichier suffit à garder
  Claude Code à jour, pas besoin de réexpliquer l'historique
