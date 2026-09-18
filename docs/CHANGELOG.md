# Changelog — DataSonda

Historique des décisions et étapes franchies. Une entrée par avancée
significative, du plus récent au plus ancien. Ne pas détailler ici le
"comment" (c'est dans le code et les commits) — se concentrer sur le
"quoi" et le "pourquoi" des décisions.

## Phase 0 — Initialisation du dépôt (en cours)

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
