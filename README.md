# MarkdownCV

Modèle de CV en une page, statique, sans framework ni dépendance. Les données vivent dans un fichier markdown, un script les injecte dans un gabarit HTML. Thème clair ou sombre selon les préférences du système.

## Utilisation

- Créer un fichier markdown de données sur le modèle d'`exemple.md` (fictif, il montre la structure attendue), où l'on veut
- La page s'ouvre sur un hero (nom et titre de poste du front-matter, puis le champ `Sous-titre` de `## Accueil`), suivi d'une section `Profil` (champ `Texte`) placée entre Accueil et Expérience ; le format exact est dans `exemple.md`
- Lancer `py -3 scripts/construire_cv.py --source <chemin du fichier>` pour générer `build/` (options `--source` et `--destination`, voir `scripts/README.md`)
- Le fichier est validé avant la génération : une erreur (section ou champ manquant, icône inconnue, URL invalide, `email` absent…) bloque le build avec son numéro de ligne, les avertissements s'affichent sans bloquer ; `py -3 scripts/valider_cv.py --source <chemin du fichier>` lance la validation seule
- Ouvrir `build/index.html` dans un navigateur
- Adapter les couleurs dans les variables `:root` de `src/style.css`

## Structure

- `exemple.md` : modèle fictif dont le fichier de données reprend le format
- `src/` : gabarit `index.html` (contenu de la page et script du tiroir de détail), `favicon.svg` (gabarit du favicon, rendu avec les initiales du CV) et `style.css` (mise en page, thèmes clair et sombre, responsive), sans aucune donnée
- `scripts/` : build, validation et lecture du fichier de données, voir `scripts/README.md`
- `build/` : site généré, à ne pas éditer à la main ; non versionné (ignoré par git), à régénérer après un clone

## Inspiration et licence

La structure générale (une page, sections empilées) s'inspire des CV en une page courants. Le code, les textes et l'identité graphique sont originaux : aucun fichier, texte ni image d'un modèle tiers n'est repris.

Police : Inter (Google Fonts, licence OFL). Code publié sous licence MIT, voir `LICENSE`.
