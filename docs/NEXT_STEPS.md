# État du projet — DataSonda

_Dernière mise à jour : 2026-09-21_

## Phase en cours

Phase 3 — Inférence de types : implémentée. Aucune phase en développement :
la Phase 4 (qualité) est à cadrer avec toi avant de coder.

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
- Phase 3 : `inference.py` (`infer_types`, `infer_column_type`) ; modèles
  `InferredType`, `RoleHint`, `ReasonCode`, `Reason`, `InferenceThresholds`,
  `ColumnTypeInference`, `DatasetTypeInference` dans `models.py`. Types
  inférés, indice de rôle, raisons chiffrées et avertissements ; reconnaît les
  booléens en texte, les nombres en texte, les codes à zéros initiaux et les
  dates en texte sans jamais deviner un format. Intégrée à `analyze`
  (`Report.inference`), au JSON (`type_inference`) et au HTML (colonnes
  « (inferred) ») ; la démo compte 13 colonnes. `profile.py`, `metadata.py`,
  `ColumnProfile` et `DatasetProfile` inchangés, aucune dépendance ajoutée
- Vérifications locales de la Phase 3 : 474 tests réussis et 3 ignorés
  (477 collectés), sous pandas 3.0.6 et sous pandas 2.3.3 ; ruff et mypy
  verts. Le snippet du README et la démo ont été exécutés pour de vrai.
  Mesure ponctuelle : `infer_types` ≈ 0,25 s pour 1 million de lignes et
  6 colonnes (pandas 3.0.6)

## En cours / à vérifier

- Ouvrir `examples/output/customers_demo.html` dans un navigateur pour un
  contrôle visuel, colonnes « (inferred) » comprises (non fait par Claude)
- Valider les seuils par défaut de l'inférence sur de vrais datasets

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
- Inférence de types : fait contre interprétation (le profil est la vérité
  mesurée) ; pas de score de confiance ; `unknown` est légitime ; jamais de
  devinette silencieuse (ambiguïté = avertissement) ; aucune conversion ni
  modification des données ; aucune valeur de cellule dans les résultats
- Types inférés : `numeric_continuous`, `numeric_discrete`, `categorical`,
  `boolean`, `datetime`, `text`, `unknown`. Rôles : `identifier_candidate`,
  `code_candidate` (un identifiant garde un type PLUS un rôle). Un flottant
  non entier n'est jamais un identifiant
- Seuils par défaut (`InferenceThresholds`, configurables et validés) :
  identifiant = ratio d'unicité ≥ 0,99 et ≥ 20 valeurs non manquantes ;
  entier discret ≤ 20 valeurs distinctes ; catégoriel ≤ 50 valeurs et ratio ≤
  0,5 ; reconnaissance de nombres et dates en texte ≥ 0,95 de l'échantillon ;
  échantillon de 1000 valeurs (graine 0). Les seuils utilisés figurent dans le
  JSON
- Dates en texte : liste fermée de 11 formats stricts en 8 groupes ; jour/mois
  jamais tranchés par un ratio (compte des valeurs qui départagent) ; seules
  les dates de 1677-09-21 à 2262-04-11 sont reconnues, pour un résultat
  identique sous pandas 2 et 3
- Nombres en texte : forme canonique stricte ; un entier à zéro initial est un
  code, jamais un nombre ; format régional = `unknown` avec avertissement,
  jamais converti
- Surcharge manuelle au niveau de la fonction (`overrides` de `infer_types`) ;
  `analyze` garde sa signature (la surcharge viendra avec l'objet de
  configuration)

## Prochaine étape

Cadrer la **Phase 4 (qualité)** avec toi avant de coder. Elle reprend les
constantes, quasi-constantes et colonnes presque vides (sorties de la Phase 3),
et devra consulter l'indice de rôle (par exemple ne jamais calculer la moyenne
d'un identifiant). Feuille de route (numérotation à confirmer ensemble) : le
chargement CSV, prévu à l'origine en Phase 2, reste repoussé ; les statistiques
descriptives, les alertes et les graphiques sont à replacer lors du cadrage.

## Limites connues du rapport

- Pas d'alertes de qualité, pas de statistiques univariées, pas de graphiques
- API et format JSON provisoires (JSON non versionné)
- Pas de chargement de fichiers : `analyze` n'accepte qu'un DataFrame
- Valeur manquante = nul pandas uniquement (chaînes vides, `"N/A"` et
  sentinelles non comptées)

## Limites connues de l'inférence de types

- Formats de date non supportés (laissés au texte) : années à 2 chiffres, noms
  de mois, formes compactes (`20240105`), fuseaux horaires, fractions de
  seconde, heures sans secondes
- Seules les dates de 1677 à 2262 sont reconnues : un sentinelle comme
  `9999-12-31` compte comme non reconnu (il pèse dans la tolérance de 5 %)
- Des codes numériques stockés en entiers ne se distinguent pas de vraies
  mesures (une colonne d'entiers presque tous uniques est proposée comme
  identifiant) : utiliser une surcharge
- Une colonne de `"0"` et `"1"` en texte est typée `boolean`, et des
  identifiants numériques en texte deviennent `numeric_discrete` avec le rôle
  `identifier_candidate` (aucune conversion)
- Les valeurs `Decimal` (ou tout objet non texte) donnent `unknown`
  (`NON_TEXT_OBJECTS`)
- Pas de catégories ordinales, pas de types sémantiques (e-mail, téléphone,
  code postal), pas de distinction date/datetime
- Les analyses de texte portent sur un échantillon de 1000 valeurs : une
  minorité de valeurs à espaces peut échapper au test « identifiant »
- Les seuils par défaut sont des heuristiques à valider sur de vrais datasets

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
  `uv run --no-sync pytest`, puis `uv sync` pour rétablir l'environnement.
  Des tests épinglent l'échantillon déterministe et des `parse_ratio` exacts :
  s'ils diffèrent entre pandas 2 et 3, s'arrêter et comprendre pourquoi
- `Series.sample(random_state=0)` donne les mêmes valeurs sous pandas 2.3.3 et
  3.0.6 ; mais `pd.to_datetime` n'accepte pas les mêmes années (ns sous
  pandas 2, 1 à 9999 sous pandas 3) : d'où la garde de plage dans
  `inference.py`
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
