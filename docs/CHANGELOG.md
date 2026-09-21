# Changelog — DataSonda

Historique des décisions et étapes franchies. Une entrée par avancée
significative, du plus récent au plus ancien. Ne pas détailler ici le
"comment" (c'est dans le code et les commits) — se concentrer sur le
"quoi" et le "pourquoi" des décisions.

## Phase 3 — Inférence de types

- **2026-09-21** — Chaque colonne reçoit une interprétation, distincte des
  faits du profil : type statistique inféré, indice de rôle éventuel, raisons
  (codes de règle + chiffres) et avertissements. Calculée par
  `infer_types(df, profile)` (`inference.py`), intégrée à `analyze`
  (`Report.inference`), au JSON (clé `type_inference`, avec les seuils
  utilisés) et au HTML (colonnes « (inferred) »). Elle servira de base aux
  phases suivantes : par exemple, ne jamais calculer la moyenne d'un
  identifiant.
  - **Changement de feuille de route :** les constantes, quasi-constantes et
    colonnes presque vides, que l'ancien NEXT_STEPS plaçait ici, passent en
    Phase 4 (qualité) : ce sont des observations de qualité, pas des types.
  - Décision : fait contre interprétation. Le profil reste la vérité mesurée ;
    l'inférence est une suggestion fondée sur des règles et des seuils
    documentés (`InferenceThresholds`, sept seuils validés à la construction).
    Jamais de devinette silencieuse : une ambiguïté produit un avertissement.
    `unknown` est une réponse légitime. Aucune donnée n'est convertie ni
    modifiée, et aucune valeur de cellule n'entre dans les résultats, le JSON
    ou le HTML (les preuves sont des nombres ou des identifiants de
    catalogues fermés).
  - Décision : un identifiant garde un type (`numeric_discrete` ou `text`)
    PLUS un indice de rôle (`identifier_candidate`, `code_candidate`) : les
    phases futures devront consulter le rôle. Un flottant non entier n'est
    jamais un identifiant.
  - Alternative écartée : un score de confiance chiffré (fausse précision ;
    des raisons chiffrées et des seuils documentés sont plus honnêtes).
  - Alternative écartée : le profil seul comme source. Contre-exemple constaté :
    deux faux positifs d'identifiant sur trois dans la démo ; il faut aussi
    regarder les valeurs (entier ou non, espaces, échantillon).
  - Décision : dates en texte, jamais devinées. Liste fermée de 11 formats
    stricts en 8 groupes, testés avec `pd.to_datetime(format=...)`. Pour une
    paire jour-d'abord / mois-d'abord, on compte les valeurs qui départagent ;
    aucune décision par seuil de ratio. Alternatives écartées : l'inférence de
    format de pandas (`dayfirst`, `format="mixed"`), et un seuil de ratio pour
    l'ambiguïté (contre-exemple : 96 % de dates ambiguës et 4 % de jours > 12
    font passer les deux formats au-dessus de 0,95). Ambigu = avertissement ;
    mélange des deux orientations = `unknown` ; plusieurs groupes retenus =
    `unknown`.
  - Décision : seules les dates de la plage `datetime64[ns]` (1677-09-21 à
    2262-04-11) sont reconnues. Fait constaté à la vérification : pandas 2 se
    limite à cette plage, pandas 3 accepte les années 1 à 9999, ce qui aurait
    donné des résultats différents (par exemple avec un sentinelle
    `31/12/9999`). Alternative écartée : `datetime.strptime` (accepte les
    chiffres Unicode, s'écarte de la décision initiale).
  - Décision : nombres en texte. Forme canonique stricte sur la chaîne brute
    (chiffres ASCII, sans strip). Un entier avec zéro initial est un CODE,
    jamais un nombre, car la conversion perdrait les zéros. Les nombres au
    format régional (virgule décimale, milliers avec espace ou virgule) donnent
    `unknown` avec un avertissement : jamais convertis ni devinés (`1,234` est
    ambigu). Alternative écartée : les convertir.
  - Décision : reproductibilité. Analyses de texte sur les valeurs non nulles
    ou sur un échantillon déterministe borné (`sample_size`, graine 0) ; avec
    au plus deux valeurs distinctes, effectifs exacts sur toute la colonne.
    L'échantillon et un `parse_ratio` sont épinglés par des tests, identiques
    sous pandas 2.3.3 et 3.0.6.
  - Décision : surcharge manuelle au niveau de la fonction (`overrides` de
    `infer_types`), validée avant tout calcul ; le type imposé remplace le
    résultat automatique (raison `USER_OVERRIDE`, avertissements conservés).
    `analyze` garde sa signature : la surcharge viendra avec l'objet de
    configuration. `__init__.py` n'exporte rien de plus.
  - Décision : dans le rapport HTML, les colonnes inférées sont marquées
    « (inferred) » et une phrase les distingue des faits mesurés ; les textes
    « Limits » sur l'inférence n'apparaissent que si le rapport contient une
    inférence.
  - Hors périmètre volontaire : constantes et colonnes presque vides (Phase 4),
    types sémantiques (e-mail, téléphone, code postal), catégories ordinales,
    distinction date/datetime, timedelta, formats régionaux configurables,
    conversion des données, détection de variable cible, statistiques, alertes,
    graphiques, chargement CSV.
  - Vérifié : 474 tests réussis et 3 ignorés (477 collectés) sous pandas 3.0.6
    et sous pandas 2.3.3, ruff et mypy verts. Des mutations ciblées des seuils
    et des règles ont été détectées par les tests (les mutants survivants
    étaient équivalents). Le snippet du README et la démo ont été exécutés pour
    de vrai. Mesure ponctuelle, sans promesse de performance : `infer_types`
    prend environ 0,25 s pour 1 million de lignes et 6 colonnes sous pandas
    3.0.6 (`profile_dataframe` : 1,27 s).

## Phase 2 bis — Rapport minimal (tranche verticale)

- **2026-09-21** — `analyze(df)` renvoie un `Report` ; `report.export("x.html")`
  et `report.export("x.json")` écrivent un rapport HTML autonome et un JSON
  strict. Démo de bout en bout : `examples/demo.py` (dataset synthétique de
  500 lignes). Quatre commits : rendu HTML, `analyze`/`Report` + README,
  démo, docs.
  - **Changement de feuille de route :** le rendu HTML (prévu en Phase 8) est
    avancé sous forme minimale, pour disposer d'une démo de bout en bout avant
    un entretien. Il ne consomme que `DatasetProfile.to_dict()`, déjà
    existant : le calcul ne change pas. Le rapport complet, les graphiques,
    Jinja2 et le schéma JSON versionné restent à leur place. La Phase 3
    (inférence de types) est décalée d'autant.
  - Décision : façade provisoire (tant que la version est `0.1.0.dev0`) :
    `analyze(data, *, name=None)`, `Report` (dataclass frozen), exports de
    `__init__.py` avec `__all__`. `_version.py` évite l'import circulaire ;
    alternative écartée : `importlib.metadata` (dépend de l'installation).
  - Décision : `export` déduit le format de l'extension (insensible à la
    casse) ; extension inconnue = `ValueError` avant toute écriture ;
    écrasement silencieux (comme pandas), dossiers non créés ; UTF-8 sans BOM
    et `\n`, pour des fichiers identiques octet pour octet sur toute
    plateforme.
  - Décision : rendu HTML par une fonction pure de la bibliothèque standard.
    Alternative écartée : Jinja2 (nouvelle dépendance, à réserver au rapport
    complet).
  - Décision : sécurité par construction. Tout texte dynamique est échappé ;
    ni script, ni ressource externe (CSP en défense en profondeur) ; aucune
    valeur de cellule dans le HTML ni dans le JSON ; pas d'horodatage.
  - Décision : le rapport présente des faits (aucun verdict, aucune colonne
    « problématique ») et affiche ses limites dans une section dédiée.
  - Correction du README : placeholder d'URL remplacé par le vrai dépôt ;
    nom « DataSonda » pour le projet (le package Python reste `datasonde`) ;
    « Planned usage » remplacé par un usage réel.
  - Hors périmètre volontaire : chargement CSV, nouvelles analyses,
    statistiques, inférence de types, alertes, graphiques, JavaScript, CLI,
    schéma JSON versionné, `pyproject.toml`/CI inchangés.
  - Vérifié : 142 tests réussis et 3 ignorés (145 collectés) sous pandas 3.0.6
    et sous pandas 2.3.3, ruff et mypy verts ; snippet du README et démo
    exécutés pour de vrai ; `profile.py`, `metadata.py`, `models.py` et
    `uv.lock` inchangés, aucune dépendance ajoutée.

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
