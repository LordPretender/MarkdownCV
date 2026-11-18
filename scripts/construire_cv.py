"""Génère le site (index.html + fichiers statiques) à partir d'un fichier markdown de données et du gabarit src/index.html."""

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

from lecture_cv import (
    BLOC_ENVIRONNEMENT,
    CHAMPS_FRONT,
    CLE_CV_PDF,
    CLE_DESCRIPTION,
    CLE_IMAGE,
    CLE_NOM,
    CLE_TITRE,
    CLE_URL,
    CONTEXTE,
    DOSSIER_GABARIT,
    ENTREPRISE,
    ETABLISSEMENT,
    FICHIER_GABARIT,
    ICONE,
    INTRO,
    LIEU,
    LOGO,
    MARQUEUR_PUCE,
    NIVEAU,
    PERIODE,
    PERIODE_DETAIL,
    PREFIXES_URL,
    RACINE,
    SECTION_ACCUEIL,
    SECTION_COMPETENCES,
    SECTION_DIPLOMES,
    SECTION_EXPERIENCE,
    SECTION_INTERETS,
    SECTION_LANGUES,
    SECTION_LIENS,
    SECTION_PROFIL,
    SECTION_PROJETS,
    SECTION_STAGES,
    SECTIONS,
    SOUS_TITRE,
    STATUT,
    TEXTE,
    TITRE,
    TITRE_DETAIL,
    URL,
    ErreurContenu,
    decouper,
    icones_du_gabarit,
    identifiant,
    retirer_puce,
    sans_accents,
    titre_de_page,
)
from valider_cv import DIMENSIONS_IMAGE, NIVEAU_ERREUR, compter, valider

FICHIER_FAVICON = "favicon.svg"
FICHIER_ROBOTS = "robots.txt"
FICHIER_SITEMAP = "sitemap.xml"
FRAGMENT_PARTAGE = "partage"
FRAGMENT_DONNEES_STRUCTUREES = "donnees_structurees"
FRAGMENT_ICONES = "icones"
FRAGMENT_TELECHARGEMENT = "telechargement"
FRAGMENT_IMPRESSION = "impression"
LIBELLE_TELECHARGEMENT = "Télécharger mon CV (PDF)"
TEXTE_BANDEAU_TELECHARGEMENT = "Une version PDF de ce CV est disponible."
TEXTE_IMPRESSION = "Ce CV est conçu pour être consulté en ligne."
TEXTE_IMPRESSION_PDF = "La version PDF à imprimer se trouve en bas de la page, après la section « {section} » (accessible depuis la navigation)."
TEXTE_IMPRESSION_SITE = "Retrouvez-le à l'adresse suivante :"
CLE_LIENS_TITRE = "liens_titre"
PREFIXE_NOM_PDF = "CV"
EXTENSION_PDF = ".pdf"
RE_CARACTERES_NOM_FICHIER = re.compile(r"[^A-Za-z0-9]+")
SEPARATEUR_NOM_FICHIER = "-"
SEPARATEUR_PARTIES_NOM_FICHIER = "_"
FICHIER_GABARIT_OG = "og.html"
FICHIER_GABARIT_ICONE = "icone.html"
FICHIER_OG = "og.png"
FICHIER_ICONE = "icone.png"
TAILLE_ICONE = (180, 180)
NAVIGATEURS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)
COMMANDES_NAVIGATEUR = ("msedge", "chrome", "google-chrome", "chromium")
OPTIONS_NAVIGATEUR = ("--headless", "--disable-gpu", "--hide-scrollbars")
ATTRIBUTS_ICONE_DECORATIVE = 'aria-hidden="true" focusable="false"'
OPTION_CAPTURE = "--screenshot="
OPTION_TAILLE_FENETRE = "--window-size="
DELAI_RENDU_SECONDES = 60
FICHIER_CSS = "style.css"
LONGUEUR_EMPREINTE = 8
CLE_VERSION_CSS = "version_css"
CLE_VERSION_FAVICON = "version_favicon"
FICHIERS_SANS_FRAGMENTS = (FICHIER_FAVICON, FICHIER_ROBOTS, FICHIER_SITEMAP)
FICHIERS_RENDUS = (FICHIER_GABARIT, FICHIER_GABARIT_OG, FICHIER_GABARIT_ICONE, *FICHIERS_SANS_FRAGMENTS)

URL_SCHEMA_ORG = "https://schema.org"
TYPE_PERSONNE = "Person"
JSON_LD_CONTEXTE = "@context"
JSON_LD_TYPE = "@type"
JSON_LD_NOM = "name"
JSON_LD_POSTE = "jobTitle"
JSON_LD_URL = "url"
JSON_LD_DESCRIPTION = "description"
JSON_LD_LIENS = "sameAs"
BALISE_SCRIPT_JSON_LD = '<script type="application/ld+json">'
FIN_BALISE_SCRIPT = "</"
FIN_BALISE_SCRIPT_ECHAPPEE = "<\\/"
ATTRIBUT_PROPERTY = "property"
ATTRIBUT_NAME = "name"
META_IMAGE = "og:image"
META_IMAGE_LARGEUR = "og:image:width"
META_IMAGE_HAUTEUR = "og:image:height"
META_IMAGE_ALT = "og:image:alt"
META_CARTE_TWITTER = "twitter:card"
META_IMAGE_TWITTER = "twitter:image"
CARTE_TWITTER_GRANDE_IMAGE = "summary_large_image"
DOSSIER_BUILD = "build"
PREFIXE_DETAIL_EXPERIENCE = "d-"
PREFIXE_DETAIL_PROJET = "p-"
PREFIXE_DETAIL_STAGE = "s-"
FRAGMENT_NAV = "nav"
FRAGMENT_DETAILS = "details"

CLE_ACCUEIL_STATUT = "accueil_statut"
CLE_ACCUEIL_SOUS_TITRE = "accueil_sous_titre"


def echapper(valeur):
    return html.escape(valeur, quote=True).replace("&#x27;", "'")


def champ(champs, cle, contexte):
    if not champs.get(cle):
        raise ErreurContenu(f"{contexte} : champ « {cle} » manquant")
    return champs[cle]


def attributs_lien_externe():
    """Point unique : tout lien externe du site s'ouvre dans un nouvel onglet (noopener contre l'accès à window.opener)."""
    return ' target="_blank" rel="noopener noreferrer"'


def liste_chips(items):
    return '<ul class="chips">' + "".join(f'<li class="chip">{echapper(i)}</li>' for i in items) + "</ul>"


def rendre_bloc(bloc, contexte):
    if not bloc.lignes:
        raise ErreurContenu(f"{contexte} : bloc « {bloc.nom} » vide")
    puces = all(ligne.startswith(MARQUEUR_PUCE) for ligne in bloc.lignes)
    if not puces and any(ligne.startswith(MARQUEUR_PUCE) for ligne in bloc.lignes):
        raise ErreurContenu(f"{contexte} : bloc « {bloc.nom} » mêle texte et puces")
    items = [retirer_puce(ligne) for ligne in bloc.lignes] if puces else []

    sortie = [f"<h3>{echapper(bloc.nom)}</h3>"]
    if bloc.nom == BLOC_ENVIRONNEMENT:
        if not puces:
            raise ErreurContenu(f"{contexte} : bloc « {BLOC_ENVIRONNEMENT} » doit être une liste à puces")
        sortie.append(liste_chips(items))
    elif puces:
        sortie.append('<ul class="bullets">')
        sortie.extend(f"  <li>{echapper(i)}</li>" for i in items)
        sortie.append("</ul>")
    else:
        sortie.append(f"<p>{echapper(' '.join(bloc.lignes))}</p>")
    return sortie


def rendre_detail(id_detail, titre, sous_titre, logo, entree, contexte):
    lignes = [
        f'<div id="{id_detail}" data-title="{echapper(titre)}" data-sub="{echapper(sous_titre)}" data-logo="{echapper(logo)}">'
    ]
    for bloc in entree.blocs:
        lignes.extend("  " + ligne for ligne in rendre_bloc(bloc, contexte))
    lignes.append("</div>")
    return lignes


def a_detail(entree):
    """Une carte n'ouvre un volet de détail que si l'entrée porte au moins un bloc."""
    return bool(entree.blocs)


def rendre_carte(id_detail, logo, titre, sous_titre, chips, cliquable):
    pastilles = "".join(f'<span class="chip">{echapper(c)}</span>' for c in chips)
    corps = [
        f'  <span class="logo">{echapper(logo)}</span>',
        f'  <span class="card-body"><span class="card-title">{echapper(titre)}</span>'
        f'<span class="card-sub">{echapper(sous_titre)}</span></span>',
        f'  <span class="chips">{pastilles}</span>',
    ]
    if not cliquable:
        return ['<li class="card static">', *corps, "</li>"]
    return [f'<li><button class="card" type="button" data-detail="{id_detail}">', *corps, "</button></li>"]


def rendre_postes(section, nom_section, prefixe):
    cartes, details = [], []
    for rang, entree in enumerate(section.entrees, 1):
        contexte = f"{nom_section} / {entree.titre}"
        c = entree.champs
        entreprise, lieu = champ(c, ENTREPRISE, contexte), champ(c, LIEU, contexte)
        periode, logo = champ(c, PERIODE, contexte), champ(c, LOGO, contexte)
        id_detail = f"{prefixe}{rang}"
        cliquable = a_detail(entree)
        cartes += rendre_carte(id_detail, logo, entree.titre, entreprise, [periode, lieu], cliquable)
        if cliquable:
            details += rendre_detail(
                id_detail, entree.titre, f"{entreprise} · {lieu} · {periode}", logo, entree, contexte
            )
    return cartes, details


def rendre_projets(section):
    cartes, details = [], []
    for rang, entree in enumerate(section.entrees, 1):
        contexte = f"{SECTION_PROJETS} / {entree.titre}"
        c = entree.champs
        contexte_projet, periode = champ(c, CONTEXTE, contexte), champ(c, PERIODE, contexte)
        logo = champ(c, LOGO, contexte)
        id_detail = f"{PREFIXE_DETAIL_PROJET}{rang}"
        cliquable = a_detail(entree)
        cartes += rendre_carte(id_detail, logo, entree.titre, contexte_projet, [periode], cliquable)
        if cliquable:
            details += rendre_detail(
                id_detail,
                c.get(TITRE_DETAIL) or entree.titre,
                f"{contexte_projet} · {c.get(PERIODE_DETAIL) or periode}",
                logo,
                entree,
                contexte,
            )
    return cartes, details


def rendre_pastilles(section, icones):
    lignes = []
    for entree in section.entrees:
        contexte = f"{section.nom} / {entree.titre}"
        icone = verifier_icone(champ(entree.champs, ICONE, contexte), contexte, icones)
        if not entree.puces:
            raise ErreurContenu(f"{contexte} : aucune puce listée")
        lignes += [
            f'<li class="skill"><h3><svg class="ico" {ATTRIBUTS_ICONE_DECORATIVE}><use href="#i-{icone}"/></svg>{echapper(entree.titre)}</h3>',
            f"  {liste_chips(entree.puces)}</li>",
        ]
    return lignes


def rendre_diplomes(section):
    lignes = []
    for entree in section.entrees:
        contexte = f"{SECTION_DIPLOMES} / {entree.titre}"
        c = entree.champs
        etablissement, periode = champ(c, ETABLISSEMENT, contexte), champ(c, PERIODE, contexte)
        lignes.append(
            f'<li class="card static"><span class="logo">{echapper(champ(c, LOGO, contexte))}</span>'
            f'<span class="card-body"><span class="card-title">{echapper(entree.titre)}</span>'
            f'<span class="card-sub">{echapper(etablissement)}</span></span>'
            f'<span class="chips"><span class="chip">{echapper(periode)}</span></span></li>'
        )
    return lignes


def rendre_langues(section):
    lignes = []
    for entree in section.entrees:
        niveau = champ(entree.champs, NIVEAU, f"{SECTION_LANGUES} / {entree.titre}")
        lignes.append(
            f'<li class="card static"><span class="lang-name">{echapper(entree.titre)}</span>'
            f'<span class="lang-level">{echapper(niveau)}</span></li>'
        )
    return lignes


def rendre_liens(section):
    lignes = []
    for entree in section.entrees:
        contexte = f"{SECTION_LIENS} / {entree.titre}"
        url = champ(entree.champs, URL, contexte)
        if not url.startswith(PREFIXES_URL):
            raise ErreurContenu(f"{contexte} : « {URL} » doit commencer par http:// ou https://")
        lignes.append(
            f'<li><a class="card" href="{echapper(url)}"{attributs_lien_externe()}>'
            f'<span class="logo dark">{echapper(champ(entree.champs, LOGO, contexte))}</span>'
            f'<span class="card-title">{echapper(entree.titre)}</span>'
            f'<svg class="arrow" {ATTRIBUTS_ICONE_DECORATIVE}><use href="#i-arrow"/></svg></a></li>'
        )
    return lignes


def normaliser_url(url):
    return url.strip().rstrip("/") + "/"


def rendre_partage(valeurs, image):
    if not image:
        return []
    url_image = valeurs[CLE_URL] + urllib.parse.quote(image)
    titre_page = titre_de_page(valeurs[CLE_NOM], valeurs[CLE_TITRE])
    largeur, hauteur = DIMENSIONS_IMAGE
    meta = [
        (ATTRIBUT_PROPERTY, META_IMAGE, url_image),
        (ATTRIBUT_PROPERTY, META_IMAGE_LARGEUR, str(largeur)),
        (ATTRIBUT_PROPERTY, META_IMAGE_HAUTEUR, str(hauteur)),
        (ATTRIBUT_PROPERTY, META_IMAGE_ALT, titre_page),
        (ATTRIBUT_NAME, META_CARTE_TWITTER, CARTE_TWITTER_GRANDE_IMAGE),
        (ATTRIBUT_NAME, META_IMAGE_TWITTER, url_image),
    ]
    return [f'<meta {attribut}="{cle}" content="{echapper(contenu)}">' for attribut, cle, contenu in meta]


def trouver_navigateur():
    candidats = [Path(chemin) for chemin in NAVIGATEURS]
    candidats += [Path(trouve) for trouve in map(shutil.which, COMMANDES_NAVIGATEUR) if trouve]
    return next((chemin for chemin in candidats if chemin.is_file()), None)


def rendre_png(navigateur, gabarit, valeurs, taille, destination_png):
    """Rend un gabarit HTML en PNG par un navigateur headless ; retourne False (avec avertissement) si le rendu échoue."""
    largeur, hauteur = taille
    with tempfile.TemporaryDirectory() as dossier_temporaire:
        page = Path(dossier_temporaire) / gabarit.name
        rendre_gabarit(gabarit, page, valeurs, {})
        commande = [
            str(navigateur),
            *OPTIONS_NAVIGATEUR,
            f"{OPTION_CAPTURE}{destination_png}",
            f"{OPTION_TAILLE_FENETRE}{largeur},{hauteur}",
            page.as_uri(),
        ]
        try:
            resultat = subprocess.run(commande, capture_output=True, timeout=DELAI_RENDU_SECONDES)
        except (OSError, subprocess.SubprocessError) as erreur:
            print(f"Avertissement : rendu de {destination_png.name} impossible ({erreur})", file=sys.stderr)
            return False
    if resultat.returncode != 0 or not destination_png.is_file():
        print(f"Avertissement : rendu de {destination_png.name} en échec (code {resultat.returncode})", file=sys.stderr)
        return False
    return True


def rendre_images(valeurs, dossier_gabarit, destination):
    """Génère icone.png et, sans image fournie, og.png ; retourne l'ensemble des PNG produits."""
    navigateur = trouver_navigateur()
    if navigateur is None:
        print("Avertissement : aucun navigateur Edge ou Chrome trouvé, image de partage et icône non générées", file=sys.stderr)
        return set()
    demandes = [(FICHIER_GABARIT_ICONE, TAILLE_ICONE, FICHIER_ICONE)]
    if not valeurs.get(CLE_IMAGE):
        demandes.append((FICHIER_GABARIT_OG, DIMENSIONS_IMAGE, FICHIER_OG))
    return {
        sortie
        for gabarit, taille, sortie in demandes
        if rendre_png(navigateur, dossier_gabarit / gabarit, valeurs, taille, destination / sortie)
    }


def nom_pdf_publie(valeurs):
    """Nom du PDF publié : CV_<nom>_<titre>.pdf, accents retirés, espaces et ponctuation remplacés par un tiret, casse conservée."""
    parties = [
        RE_CARACTERES_NOM_FICHIER.sub(SEPARATEUR_NOM_FICHIER, sans_accents(valeurs[cle])).strip(SEPARATEUR_NOM_FICHIER)
        for cle in (CLE_NOM, CLE_TITRE)
    ]
    return SEPARATEUR_PARTIES_NOM_FICHIER.join([PREFIXE_NOM_PDF, *parties]) + EXTENSION_PDF


def rendre_telechargement(nom_pdf):
    if not nom_pdf:
        return []
    return [
        '<aside class="download-banner">',
        '  <div class="container">',
        f"    <p>{TEXTE_BANDEAU_TELECHARGEMENT}</p>",
        f'    <a class="download" href="{echapper(urllib.parse.quote(nom_pdf))}" download{attributs_lien_externe()}>{LIBELLE_TELECHARGEMENT}</a>',
        "  </div>",
        "</aside>",
    ]


def rendre_impression(valeurs, nom_pdf):
    """Encart seul imprimé à la place du site : indique où trouver le PDF sur la page, ou l'adresse du site sans PDF."""
    adresse = valeurs[CLE_URL]
    if nom_pdf:
        consigne = TEXTE_IMPRESSION_PDF.format(section=valeurs[CLE_LIENS_TITRE])
    else:
        consigne = TEXTE_IMPRESSION_SITE
    return [
        '<div class="print-only">',
        f'  <p class="print-nom">{echapper(valeurs[CLE_NOM])}</p>',
        f"  <p>{echapper(valeurs[CLE_TITRE])}</p>",
        f"  <p>{TEXTE_IMPRESSION} {echapper(consigne)}</p>",
        f'  <p><a href="{echapper(adresse)}">{echapper(adresse)}</a></p>',
        "</div>",
    ]


def rendre_icones(produits):
    return [f'<link rel="apple-touch-icon" href="{FICHIER_ICONE}">'] if FICHIER_ICONE in produits else []


def rendre_donnees_structurees(valeurs, section_liens):
    personne = {
        JSON_LD_CONTEXTE: URL_SCHEMA_ORG,
        JSON_LD_TYPE: TYPE_PERSONNE,
        JSON_LD_NOM: valeurs[CLE_NOM],
        JSON_LD_POSTE: valeurs[CLE_TITRE],
        JSON_LD_URL: valeurs[CLE_URL],
        JSON_LD_DESCRIPTION: valeurs[CLE_DESCRIPTION],
    }
    liens = [entree.champs[URL] for entree in section_liens.entrees]
    if liens:
        personne[JSON_LD_LIENS] = liens
    # Une valeur contenant « </script> » refermerait la balise : on échappe la fin de balise.
    json_ld = json.dumps(personne, ensure_ascii=False, indent=2).replace(FIN_BALISE_SCRIPT, FIN_BALISE_SCRIPT_ECHAPPEE)
    return [BALISE_SCRIPT_JSON_LD, *json_ld.splitlines(), "</script>"]


def verifier_icone(icone, contexte, icones):
    if icone not in icones:
        raise ErreurContenu(f"{contexte} : icône « {icone} » absente du sprite du gabarit")
    return icone


def indexer_sections(sections):
    par_nom = {}
    for section in sections:
        if section.nom not in SECTIONS:
            raise ErreurContenu(f"section inconnue « {section.nom} »")
        if section.nom in par_nom:
            raise ErreurContenu(f"section « {section.nom} » présente plusieurs fois")
        par_nom[section.nom] = section
    for nom in SECTIONS:
        if nom not in par_nom:
            raise ErreurContenu(f"section « {nom} » absente")
    return par_nom


def preparer_navigation(par_nom, icones, valeurs):
    """Renseigne `valeurs` (icône, titre, intro, texte de chaque section) et rend les liens de navigation."""
    nav = []
    for nom in SECTIONS:
        section = par_nom[nom]
        icone = verifier_icone(champ(section.champs, ICONE, nom), nom, icones)
        nav.append(
            f'<a href="#{identifiant(nom)}" data-label="{echapper(nom)}" aria-label="{echapper(nom)}">'
            f'<svg class="ico" {ATTRIBUTS_ICONE_DECORATIVE}><use href="#i-{icone}"/></svg></a>'
        )
        if nom == SECTION_ACCUEIL:
            continue
        valeurs[f"{identifiant(nom)}_icone"] = icone
        valeurs[f"{identifiant(nom)}_titre"] = champ(section.champs, TITRE, nom)
        if nom == SECTION_PROFIL:
            valeurs[f"{identifiant(nom)}_texte"] = champ(section.champs, TEXTE, nom)
            continue
        if not section.entrees:
            raise ErreurContenu(f"section « {nom} » sans aucune entrée (###)")
        if nom != SECTION_LIENS:
            valeurs[f"{identifiant(nom)}_intro"] = champ(section.champs, INTRO, nom)
    return nav


def preparer(front, sections, icones):
    for cle in CHAMPS_FRONT:
        champ(front, cle, "front-matter")
    par_nom = indexer_sections(sections)

    valeurs = dict(front)
    valeurs[CLE_URL] = normaliser_url(front[CLE_URL])
    accueil = par_nom[SECTION_ACCUEIL].champs
    valeurs[CLE_ACCUEIL_STATUT] = champ(accueil, STATUT, SECTION_ACCUEIL)
    valeurs[CLE_ACCUEIL_SOUS_TITRE] = champ(accueil, SOUS_TITRE, SECTION_ACCUEIL)
    nav = preparer_navigation(par_nom, icones, valeurs)

    cartes_experience, details_experience = rendre_postes(
        par_nom[SECTION_EXPERIENCE], SECTION_EXPERIENCE, PREFIXE_DETAIL_EXPERIENCE
    )
    cartes_projets, details_projets = rendre_projets(par_nom[SECTION_PROJETS])
    cartes_stages, details_stages = rendre_postes(par_nom[SECTION_STAGES], SECTION_STAGES, PREFIXE_DETAIL_STAGE)
    fragments = {
        FRAGMENT_NAV: nav,
        identifiant(SECTION_EXPERIENCE): cartes_experience,
        identifiant(SECTION_COMPETENCES): rendre_pastilles(par_nom[SECTION_COMPETENCES], icones),
        identifiant(SECTION_PROJETS): cartes_projets,
        identifiant(SECTION_STAGES): cartes_stages,
        identifiant(SECTION_DIPLOMES): rendre_diplomes(par_nom[SECTION_DIPLOMES]),
        identifiant(SECTION_LANGUES): rendre_langues(par_nom[SECTION_LANGUES]),
        identifiant(SECTION_INTERETS): rendre_pastilles(par_nom[SECTION_INTERETS], icones),
        identifiant(SECTION_LIENS): rendre_liens(par_nom[SECTION_LIENS]),
        FRAGMENT_DETAILS: details_experience + details_projets + details_stages,
        FRAGMENT_PARTAGE: [],
        FRAGMENT_ICONES: [],
        FRAGMENT_TELECHARGEMENT: [],
        FRAGMENT_IMPRESSION: [],
        FRAGMENT_DONNEES_STRUCTUREES: rendre_donnees_structurees(valeurs, par_nom[SECTION_LIENS]),
    }
    return valeurs, fragments


def appliquer(gabarit, valeurs, fragments):
    def remplacer_valeur(correspondance):
        cle = correspondance.group(1)
        if cle not in valeurs:
            raise ErreurContenu(f"marqueur de gabarit sans valeur « {{{{{cle}}}}} »")
        return echapper(valeurs[cle])

    def remplacer_fragment(correspondance):
        cle = correspondance.group("nom")
        if cle not in fragments:
            raise ErreurContenu(f"marqueur de gabarit inconnu « <!-- @{cle} --> »")
        indentation = correspondance.group("indentation")
        return "\n".join(indentation + ligne for ligne in fragments[cle])

    texte = re.sub(r"\{\{(\w+)\}\}", remplacer_valeur, gabarit)
    texte = re.sub(
        r"^(?P<indentation>[ \t]*)<!-- @(?P<nom>\w+) -->[ \t]*$", remplacer_fragment, texte, flags=re.M
    )
    restant = re.search(r"<!-- @\w+ -->", texte)
    if restant:
        raise ErreurContenu(f"marqueur non remplacé dans le gabarit : « {restant.group(0)} » (doit être seul sur sa ligne)")
    return texte


def empreinte(fichier):
    """Empreinte courte du contenu d'un fichier, utilisée pour versionner son URL et contourner les caches."""
    return hashlib.sha256(fichier.read_bytes()).hexdigest()[:LONGUEUR_EMPREINTE]


def rendre_gabarit(gabarit, destination, valeurs, fragments):
    texte = appliquer(gabarit.read_text(encoding="utf-8"), valeurs, fragments)
    destination.write_bytes(texte.encode("utf-8"))


def construire(source, destination):
    dossier_gabarit = RACINE / DOSSIER_GABARIT
    icones = icones_du_gabarit(dossier_gabarit / FICHIER_GABARIT)

    texte = source.read_text(encoding="utf-8")
    anomalies = valider(texte, icones, source.parent)
    for anomalie in anomalies:
        print(anomalie, file=sys.stderr)
    erreurs = compter(anomalies, NIVEAU_ERREUR)
    if erreurs:
        raise ErreurContenu(f"{erreurs} erreur(s) dans {source}, build annulé")

    front, sections = decouper(texte)
    valeurs, fragments = preparer(front, sections, icones)

    destination.mkdir(parents=True, exist_ok=True)
    for fichier in dossier_gabarit.iterdir():
        if fichier.is_file() and fichier.name not in FICHIERS_RENDUS:
            shutil.copy2(fichier, destination / fichier.name)
    valeurs[CLE_VERSION_CSS] = empreinte(dossier_gabarit / FICHIER_CSS)
    valeurs[CLE_VERSION_FAVICON] = empreinte(dossier_gabarit / FICHIER_FAVICON)
    image_fournie = valeurs.get(CLE_IMAGE)
    if image_fournie:
        shutil.copy2(source.parent / image_fournie, destination / image_fournie)
    cv_pdf = valeurs.get(CLE_CV_PDF)
    nom_pdf = nom_pdf_publie(valeurs) if cv_pdf else None
    if cv_pdf:
        shutil.copy2(source.parent / cv_pdf, destination / nom_pdf)
    fragments[FRAGMENT_TELECHARGEMENT] = rendre_telechargement(nom_pdf)
    fragments[FRAGMENT_IMPRESSION] = rendre_impression(valeurs, nom_pdf)
    produits = rendre_images(valeurs, dossier_gabarit, destination)
    fragments[FRAGMENT_PARTAGE] = rendre_partage(valeurs, image_fournie or (FICHIER_OG if FICHIER_OG in produits else None))
    fragments[FRAGMENT_ICONES] = rendre_icones(produits)
    rendre_gabarit(dossier_gabarit / FICHIER_GABARIT, destination / FICHIER_GABARIT, valeurs, fragments)
    for nom_fichier in FICHIERS_SANS_FRAGMENTS:
        rendre_gabarit(dossier_gabarit / nom_fichier, destination / nom_fichier, valeurs, {})


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--source", type=Path, required=True, help="fichier markdown des données")
    analyseur.add_argument("--destination", type=Path, default=RACINE / DOSSIER_BUILD, help="dossier de sortie")
    arguments = analyseur.parse_args()
    try:
        construire(arguments.source, arguments.destination)
    except (ErreurContenu, OSError, ValueError) as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    print(f"Site généré dans {arguments.destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
