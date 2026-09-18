# État du projet — DataSonda

_Dernière mise à jour : 2026-09-18_

## Phase en cours

Phase 0 — Initialisation du dépôt (finalisation en cours)

## Ce qui est fait

- Dépôt GitHub créé (public) et cloné en local :
  https://github.com/leonardgst/DataSonda
- Squelette du package en place : `pyproject.toml` (uv + hatchling),
  licence MIT, structure `src/datasonde/`, `tests/`, CI GitHub Actions
- Bug résolu : fichiers créés via PowerShell `Set-Content -Encoding utf8`
  ajoutaient un BOM UTF-8, cassait le parsing TOML par hatchling → corrigé
  avec `[System.IO.File]::WriteAllText(..., UTF8Encoding($false))`
- Environnement de travail mis en place : Claude Code (VS Code) pour le
  développement direct sur le repo local, cette conversation pour les
  décisions d'architecture et l'apprentissage

## En cours / à vérifier

- CI : dernière exécution à reconfirmer après correction du bug BOM
  (`tests/test_import.py` renvoyait "collected 0 items" — cause probable :
  fichier vide ou mal poussé, diagnostic en cours à la reprise)

## Décisions actées

- Gestionnaire de projet : `uv`
- Licence : MIT
- Backend de build : `hatchling`
- Layout : `src/datasonde/`
- Lint/format : `ruff` ; typage : `mypy --strict`
- Python ≥ 3.11

## Prochaine étape

Une fois la CI confirmée verte : **Phase 1 — modèle de données et entrée
DataFrame** (accepter un `pandas.DataFrame`, le valider, calculer les
métadonnées générales : nombre de lignes, colonnes, types, mémoire)

## Pièges connus / notes pour reprise

- PowerShell 5.1 : toujours utiliser `[System.IO.File]::WriteAllText` avec
  `UTF8Encoding($false)` pour écrire des fichiers texte (jamais
  `Set-Content -Encoding utf8`, qui ajoute un BOM)
- Claude Code lit `CLAUDE.md` (racine) automatiquement à chaque session,
  qui référence ce fichier — donc mettre à jour ce fichier suffit à garder
  Claude Code à jour, pas besoin de réexpliquer l'historique
