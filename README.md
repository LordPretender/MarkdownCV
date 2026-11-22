# MarkdownCV

Modèle de CV en une page, statique, sans framework ni dépendance. Les données vivent dans un fichier markdown, un script les injecte dans un gabarit HTML. Thème clair ou sombre selon les préférences du système.

## Utilisation

- Créer un fichier markdown de données sur le modèle d'`exemple.md` (fictif, il montre la structure attendue), où l'on veut
- La page s'ouvre sur un hero (nom et titre de poste du front-matter, puis le champ `Sous-titre` de `## Accueil`), suivi d'une section `Profil` (champ `Texte`) placée entre Accueil et Expérience ; le format exact est dans `exemple.md`
- Les stages ont leur propre section `Stages` (cartes cliquables quand elles ont du détail), placée entre Projets et Diplômes ; le format est dans `exemple.md`
- Un bloc optionnel `#### Compétences` (liste à puces) dans une entrée d'Expérience, de Projets ou de Stages affiche dans son volet les compétences concernées, regroupées par catégorie de la section `Compétences` ; chaque puce doit reprendre le libellé d'une compétence de cette section (casse indifférente), sinon la validation échoue ; le bloc `Environnement` reste libre. Une fois le bloc utilisé, la validation signale en avertissement les compétences rattachées à aucune entrée ; le format est dans `exemple.md`
- Les entrées de la section `Diplômes` ont aussi un volet : tout bloc `####` (par exemple `Enseignements et technologies étudiés`, liste à puces) y est affiché tel quel ; le bloc `Compétences` y est interdit, un diplôme ne rattache pas de compétences à la section `Compétences` ; le format est dans `exemple.md`
- Les centres d'intérêt ont leur propre section `Intérêts` (pastilles groupées comme les compétences), placée entre Langues et Liens ; le format est dans `exemple.md`
- Le front-matter porte `url` (adresse publique du site, obligatoire : canonical, Open Graph, JSON-LD, `robots.txt` et `sitemap.xml` en dépendent) et `image` (optionnel) ; le format est dans `exemple.md`
- L'image de partage (`og.png`, 1200x630 px) est générée par le build à partir du gabarit `src/og.html`, rendu par Edge ou Chrome en mode headless, sans photo ; `image` (optionnel) sert seulement à la remplacer par un PNG de 1200x630 px rangé à côté du fichier de données (pas dans le dépôt, c'est une donnée personnelle), que le build copie à la racine du site
- L'icône d'écran d'accueil `icone.png` (180x180 px, gabarit `src/icone.html`) est générée de la même façon ; si aucun navigateur n'est trouvé, le build avertit sans échouer et n'émet alors ni balise d'image de partage ni `apple-touch-icon`
- `cv_pdf` (optionnel) désigne un PDF à l'emplacement libre (chemin absolu, ou relatif au fichier de données ; pas dans le dépôt, il contient des coordonnées personnelles) : le build le copie dans `build/`, à la racine du site, sous le nom `CV_<nom>_<titre>.pdf` et ajoute un bandeau « Télécharger mon CV (PDF) » en fin de page, avant le pied de page (le lien s'ouvre dans un nouvel onglet) ; sans ce champ, aucun lien
- À l'impression, seul un encart s'imprime : il indique que le CV est conçu pour être consulté en ligne et, avec `cv_pdf`, que le PDF à imprimer se trouve en bas de la page après la section Liens (sans `cv_pdf`, il donne l'adresse du site)
- Redirection vers `www`, compression et cache se règlent côté serveur (Apache : un `.htaccess` placé dans `build/`, non versionné, que le build n'écrase pas)
- Lancer `py -3 scripts/construire_cv.py --source <chemin du fichier>` pour générer `build/` (options `--source` et `--destination`, voir `scripts/README.md`)
- Le fichier est validé avant la génération : une erreur (section ou champ manquant, icône inconnue, URL invalide, `email` absent…) bloque le build avec son numéro de ligne, les avertissements s'affichent sans bloquer ; `py -3 scripts/valider_cv.py --source <chemin du fichier>` lance la validation seule
- Ouvrir `build/index.html` dans un navigateur
- Un lien d'évitement et un focus visible permettent la navigation au clavier ; les icônes décoratives sont masquées aux lecteurs d'écran
- Adapter les couleurs dans les variables `:root` de `src/style.css`

## Structure

- `exemple.md` : modèle fictif dont le fichier de données reprend le format
- `src/` : gabarit `index.html` (contenu de la page et script du tiroir de détail), `favicon.svg` (gabarit du favicon, rendu avec les initiales du CV) et `style.css` (mise en page, thèmes clair et sombre, responsive), les gabarits `robots.txt` et `sitemap.xml`, et les gabarits `og.html` et `icone.html` (rendus en PNG par le build), sans aucune donnée
- `scripts/` : build, validation et lecture du fichier de données, voir `scripts/README.md`
- `build/` : site généré, à ne pas éditer à la main ; non versionné (ignoré par git), à régénérer après un clone

## Inspiration et licence

La structure générale (une page, sections empilées) s'inspire des CV en une page courants. Le code, les textes et l'identité graphique sont originaux : aucun fichier, texte ni image d'un modèle tiers n'est repris.

Polices : le site utilise la pile de polices du système, aucune police n'est téléchargée et aucun service tiers n'est appelé. Code publié sous licence MIT, voir `LICENSE`.
