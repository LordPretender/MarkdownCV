# Scripts de MarkdownCV

- `construire_cv.py` : génère `build/` (index.html et fichiers statiques) à partir d'un fichier markdown de données et du gabarit `src/index.html` (`py -3 scripts/construire_cv.py --source <fichier.md> [--destination build]`, `--source` se passe toujours explicitement)
- `valider_cv.py` : liste toutes les anomalies (erreurs bloquantes, avertissements) d'un fichier markdown de données, avec numéros de ligne (`py -3 scripts/valider_cv.py --source <fichier.md>`, code de sortie 1 s'il y a au moins une erreur)
