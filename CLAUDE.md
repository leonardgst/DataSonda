# DataSonda — instructions pour Claude Code

DataSonda est un toolkit Python modulaire pour le profiling automatique de
données, l'évaluation de qualité, l'analyse exploratoire et la génération de
rapports. Projet à but double : portfolio + apprentissage progressif
(Python, pandas, stats, architecture, packaging, CI/CD).

Voir @docs/NEXT_STEPS.md pour l'état d'avancement actuel et la prochaine étape.
Voir @docs/CHANGELOG.md pour l'historique des décisions et des versions.

## Commandes

- Installer l'environnement : `uv sync`
- Lancer les tests : `uv run pytest`
- Lint : `uv run ruff check .`
- Typage : `uv run mypy src`
- Tout vérifier avant un commit : `uv run pytest && uv run ruff check . && uv run mypy src`

## Conventions du projet

- Layout `src/datasonde/` (pas de package à plat à la racine)
- Gestionnaire de projet : `uv` ; backend de build : `hatchling`
- Python ≥ 3.11 ; typage strict (`mypy --strict`)
- Lint/format : `ruff` uniquement (pas de black/flake8/isort séparés)
- Licence MIT
- Un module = une responsabilité claire (voir le document de méthodologie
  du projet, section architecture)

## Méthode de travail attendue

- Avant toute étape de code, explique brièvement le plan (objectif,
  fichiers concernés, décisions techniques s'il y en a) avant d'écrire.
- Pour les décisions structurantes (choix de dépendance, changement
  d'architecture, format de sortie), présente problème / options /
  recommandation / réversibilité avant d'agir, plutôt que de trancher
  silencieusement.
- Écris des tests pour toute nouvelle logique métier (pas pour la config).
- À la fin d'une session de travail, mets à jour `docs/NEXT_STEPS.md` et
  `docs/CHANGELOG.md` pour refléter ce qui vient d'être fait.
- Docs : ne jamais consigner l'état Git ou CI dans `docs/` (branche poussée
  ou non, PR mergée ou non, CI verte ou non) ; GitHub fait foi. Décrire ce que
  le code fait et les décisions prises.

## Pièges connus

- Windows/PowerShell : ne jamais utiliser `Set-Content -Encoding utf8`
  pour écrire des fichiers texte (ajoute un BOM UTF-8 qui casse le
  parsing TOML par hatchling). Utiliser `-Encoding utf8NoBOM` (PS7+) ou
  `[System.IO.File]::WriteAllText(path, content, New-Object System.Text.UTF8Encoding($false))`
  (PS5.1).
