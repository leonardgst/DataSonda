# État du projet — DataSonda

_Dernière mise à jour : 2026-09-21_

## Phase en cours

Phase 3 — Inférence de types : cadrée, implémentation en cours.

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
- Phase 2 : `profile.py` (`classify_dtype`, `profile_column`,
  `profile_dataframe`), `DtypeFamily`, `ColumnProfile` et `DatasetProfile`
  dans `models.py` ; correctif de validation des noms de colonnes qui
  entrent en collision après `str()` (détails dans le CHANGELOG)
- Correctif post-revue : `profile_column` distingue les valeurs non hachables
  (`"n_unique not computed: unhashable values"`) des types non supportés
  (`"n_unique not computed: unsupported dtype"`). Suite locale : 75 tests
  collectés, dont 3 ignorés sans `pyarrow` (72 exécutés) ; les 75 passent
  avec `pyarrow` installé temporairement, sous pandas 3 et pandas 2
- Phase 2 bis : `analyze(df, name=None)` → `Report` (`to_dict`, `to_json`,
  `to_html`, `export`), rendu HTML autonome dans `html_report.py`,
  `_version.py`, façade `__init__.py` (`analyze`, `Report`, `__version__`),
  `examples/demo.py` (dataset synthétique de 500 lignes), README réel
  (placeholder d'URL corrigé, nom « DataSonda »). `profile.py`, `metadata.py`
  et `models.py` inchangés, aucune dépendance ajoutée
- Vérifications locales de la Phase 2 bis : 142 tests réussis et 3 ignorés
  (145 collectés), sous pandas 3.0.6 et sous pandas 2.3.3 ; ruff et mypy verts.
  Le snippet du README et `uv run python examples/demo.py` ont été exécutés
  pour de vrai

## En cours / à vérifier

- Ouvrir `examples/output/customers_demo.html` dans un navigateur pour un
  contrôle visuel (non fait par Claude)

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
  (jamais NaN ni 0), avec un avertissement, sans jamais faire planter le profil
- Façade provisoire (tant que la version est `0.1.0.dev0`) : `analyze`,
  `Report` et `__version__` exportés par `__init__.py` ; `analyze` n'accepte
  qu'un DataFrame (`TypeError` sinon)
- `export(path)` : format déduit de l'extension (`.html`, `.json`,
  insensible à la casse), `ValueError` avant toute écriture sinon ; écrase un
  fichier existant, ne crée pas les dossiers ; UTF-8 sans BOM, fins de ligne
  `\n`
- Rendu HTML : bibliothèque standard uniquement (pas de Jinja2), tout texte
  dynamique échappé, aucun script ni ressource externe, aucune valeur de
  cellule, aucun horodatage (même entrée = mêmes octets)

## Prochaine étape

**Phase 3** (en cours) : inférence de types statistiques, distincte des faits
du profil : type inféré, indice de rôle, raisons chiffrées et avertissements,
sans jamais deviner en silence. Les constantes et colonnes presque vides
relèvent de la Phase 4 (qualité). Feuille de route (numérotation à confirmer
ensemble) : le chargement CSV, prévu à l'origine en Phase 2, est repoussé.

## Limites connues du rapport minimal

- Pas d'inférence de types ni de rôles (un booléen contenant des nuls apparaît
  en `text_or_object`)
- Pas d'alertes de qualité, pas de statistiques univariées, pas de graphiques
- API et format JSON provisoires (JSON non versionné)
- Pas de chargement de fichiers : `analyze` n'accepte qu'un DataFrame
- Valeur manquante = nul pandas uniquement (chaînes vides, `"N/A"` et
  sentinelles non comptées)

## Limites connues

- `dictionary[pyarrow]` (équivalent Arrow de `category`) est classé `other`
  par `classify_dtype`. À reprendre avec le chargement Parquet. Les autres
  dtypes Arrow courants (`int64`, `double`, `bool`, `timestamp`, `date32`,
  `decimal128`) sont classés correctement.
- Un label de colonne `None` est converti en `NaN` par pandas 3 (nom `"nan"`)
  mais conservé par pandas 2 (nom `"None"`). Cas exotique sans gravité ; la
  validation reste cohérente avec les labels réels.
- Les colonnes MultiIndex fonctionnent, mais leurs noms sont la
  représentation texte des tuples (ex. `"('a', 'x')"`). Support non garanti,
  hors périmètre.

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
- Fait : `.claude/settings.local.json` a été retiré du suivi Git et est
  ignoré par `.gitignore`
- Le test Arrow réel (`test_nested_arrow_dtype_gives_none_and_warning`) est
  ignoré partout où `pyarrow` est absent, CI comprise (`pyarrow` n'est pas une
  dépendance). Le test monkeypatch couvre la même branche. Pour le lancer :
  `uv pip install pyarrow`, `uv run --no-sync pytest tests/test_profile.py`,
  puis `uv sync`
- Démo : `uv run python examples/demo.py` (depuis la racine du dépôt) écrit
  le rapport dans `examples/output/`, dossier ignoré par Git
- PowerShell 5.1 : toujours utiliser `[System.IO.File]::WriteAllText` avec
  `UTF8Encoding($false)` pour écrire des fichiers texte (jamais
  `Set-Content -Encoding utf8`, qui ajoute un BOM)
- Claude Code lit `CLAUDE.md` (racine) automatiquement à chaque session,
  qui référence ce fichier — donc mettre à jour ce fichier suffit à garder
  Claude Code à jour, pas besoin de réexpliquer l'historique
