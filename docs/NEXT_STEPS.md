# État du projet — DataSonda

_Dernière mise à jour : 2026-09-18_

## Phase en cours

Phase 2 — Profil de base des colonnes (implémentée sur la branche
`feat/phase-2-column-profile`, pas encore poussée ni mergée)

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
  CHANGELOG). Mergé via la PR #1, CI verte
- Phase 2 : `profile.py` (`classify_dtype`, `profile_column`,
  `profile_dataframe`), `DtypeFamily`, `ColumnProfile` et `DatasetProfile`
  dans `models.py` ; correctif de validation des noms de colonnes qui
  entrent en collision après `str()`. 70 tests verts sous pandas 3 et pandas 2
  (détails dans le CHANGELOG)

## En cours / à vérifier

- Pousser la branche `feat/phase-2-column-profile`, ouvrir la PR et confirmer
  que la CI est verte (matrice Python 3.11/3.12/3.13 + étape pandas 2.x)

## Décisions actées

- Gestionnaire de projet : `uv` ; licence MIT ; build : `hatchling`
- Layout : `src/datasonde/` ; Python ≥ 3.11
- Lint/format : `ruff` ; typage : `mypy --strict` (+ `pandas-stubs`)
- Modèles de résultat : `dataclass(frozen=True)` de la stdlib (pas de
  pydantic à ce stade ; migration possible plus tard, limitée à `models.py`)
- Validation d'entrée : `TypeError` si non-DataFrame ; `ValueError` si aucune
  colonne, noms de colonnes dupliqués ou noms en collision après `str()` ;
  DataFrame sans lignes accepté
- Familles de dtype : `numeric`, `boolean`, `datetime`, `categorical`,
  `text_or_object`, `other` (complexes, timedelta, période, intervalle)
- Valeur manquante = `isna()` pandas uniquement ; « non calculable » = `None`
  (jamais NaN ni 0)
- Aucune façade publique dans `__init__.py` avant l'existence de `analyze`

## Prochaine étape

Feuille de route (numérotation à confirmer ensemble) : le chargement CSV,
prévu à l'origine en Phase 2, est repoussé.

**Phase 3** (à cadrer avec toi avant de coder) : inférence de types
statistiques à partir du profil de base (constantes, colonnes presque vides,
identifiants, booléens contenant `None`). Le chargement CSV, les statistiques
descriptives, la qualité et les exports sont à replacer dans les phases
suivantes lors de ce cadrage

## Pièges connus / notes pour reprise

- mypy : ne pas figer `python_version` dans `[tool.mypy]`. Sur Python ≥ 3.12,
  uv résout numpy 2.5 dont les stubs utilisent `type X = ...` (syntaxe
  3.12+) ; forcer 3.11 fait échouer mypy
- `uv.lock` verrouille pandas 3.x alors que `pyproject.toml` accepte
  `>=2.0` ; la CI réinstalle `pandas<3` sur 3.11 pour tester pandas 2
  (dernier 2.x, pas le plancher 2.0). Les dtypes texte diffèrent (`str` en
  3.x, `object` en 2.x) : `classify_dtype` les regroupe dans
  `text_or_object` ; ne jamais comparer des chaînes de dtype
- Vérifier sous pandas 2 en local : `uv pip install "pandas<3"`, puis
  `uv run --no-sync pytest`, puis `uv sync` pour rétablir l'environnement
- `.claude/settings.local.json` est suivi par Git alors que c'est un
  réglage local : à décider (le retirer de l'index et l'ignorer ?)
- PowerShell 5.1 : toujours utiliser `[System.IO.File]::WriteAllText` avec
  `UTF8Encoding($false)` pour écrire des fichiers texte (jamais
  `Set-Content -Encoding utf8`, qui ajoute un BOM)
- Claude Code lit `CLAUDE.md` (racine) automatiquement à chaque session,
  qui référence ce fichier — donc mettre à jour ce fichier suffit à garder
  Claude Code à jour, pas besoin de réexpliquer l'historique
