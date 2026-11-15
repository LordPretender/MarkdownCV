"""Génère le PDF du CV (texte sélectionnable, sans image, pensé pour les filtres ATS) à partir des données lues par lecture_cv."""

import re
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, NextPageTemplate, PageTemplate, Paragraph

from lecture_cv import (
    BLOC_ENVIRONNEMENT,
    CONTEXTE,
    ENTREPRISE,
    ETABLISSEMENT,
    LIEU,
    MARQUEUR_PUCE,
    NIVEAU,
    PERIODE,
    PERIODE_DETAIL,
    SECTION_ACCUEIL,
    SECTION_COMPETENCES,
    SECTION_DIPLOMES,
    SECTION_EXPERIENCE,
    SECTION_LANGUES,
    SECTION_PROFIL,
    SECTION_PROJETS,
    SOUS_TITRE,
    TEXTE,
    TITRE,
    TITRE_DETAIL,
    ErreurContenu,
    retirer_puce,
    sans_accents,
)

LARGEUR_PAGE, HAUTEUR_PAGE = A4
MARGE = 1.5 * cm
LARGEUR_LATERALE = 5.2 * cm
ECART_COLONNES = 0.6 * cm
HAUTEUR_ILLIMITEE = 10000
MARGE_SECURITE = 4

COULEUR_MARINE = HexColor("#1F3550")
COULEUR_TERRACOTTA = HexColor("#B5806A")
COULEUR_GRIS = HexColor("#555555")

POLICE = "Helvetica"
POLICE_GRAS = "Helvetica-Bold"
POLICE_ITALIQUE = "Helvetica-Oblique"

CLE_NOM = "nom"
CLE_TITRE = "titre"
CLE_DESCRIPTION = "description"
SEPARATEUR_INFOS = " | "
SEPARATEUR_LISTE = ", "
SEPARATEUR_LIBELLE = " : "
SAUT_LIGNE = "<br/>"
PUCE_PDF = "-"
PREFIXE_FICHIER = "CV_"
EXTENSION_PDF = ".pdf"
REMPLACEMENT_FICHIER = "_"
RE_CARACTERES_FICHIER = re.compile(r"[^\w-]+")
MODELE_PDF = "premiere"
MODELE_SUITE = "suite"
CADRE_ENTETE = "entete"
CADRE_COORDONNEES = "coordonnees"
CADRE_PRINCIPALE = "principale"
CADRE_LATERAL = "lateral"
CADRE_SUITE = "suite"

LIBELLE_COORDONNEES = "Coordonnées"
LIBELLE_COMPETENCES_CLES = "Compétences clés"
LIBELLE_ENVIRONNEMENT_IT = "Environnement IT"
LIBELLE_FORMATION = "Formation"
LIBELLE_LANGUES = "Langues"
ENTREE_COMPETENCES_CLES = "Personnelles"
COORDONNEES = [
    ("Téléphone", "telephone"),
    ("E-mail", "email"),
    ("Localisation", "localisation"),
    ("Permis", "permis"),
    ("Mobilité", "mobilite"),
    ("LinkedIn", "linkedin"),
]

STYLE_NOM = ParagraphStyle("nom", fontName=POLICE_GRAS, fontSize=24, leading=28, textColor=COULEUR_MARINE)
STYLE_TITRE_POSTE = ParagraphStyle("titre_poste", fontName=POLICE_GRAS, fontSize=13, leading=17, textColor=COULEUR_TERRACOTTA)
STYLE_SOUS_TITRE = ParagraphStyle("sous_titre", fontName=POLICE, fontSize=10.5, leading=14, textColor=COULEUR_GRIS)
STYLE_PROFIL = ParagraphStyle("profil", fontName=POLICE_ITALIQUE, fontSize=9.5, leading=13)
STYLE_BANDEAU = ParagraphStyle(
    "bandeau", fontName=POLICE_GRAS, fontSize=9.5, leading=12, textColor=white, backColor=COULEUR_MARINE,
    alignment=TA_CENTER, borderPadding=3, spaceBefore=10, spaceAfter=6, keepWithNext=1,
)
STYLE_POSTE = ParagraphStyle("poste", fontName=POLICE_GRAS, fontSize=9.5, leading=12, textColor=COULEUR_TERRACOTTA, spaceBefore=6)
STYLE_INFOS = ParagraphStyle("infos", fontName=POLICE, fontSize=8.5, leading=11, textColor=COULEUR_GRIS, spaceAfter=2)
STYLE_TEXTE = ParagraphStyle("texte", fontName=POLICE, fontSize=9, leading=12, spaceAfter=2)
STYLE_PUCE = ParagraphStyle("puce", parent=STYLE_TEXTE, leftIndent=10, bulletIndent=0, spaceAfter=1)
STYLE_LATERAL = ParagraphStyle("lateral", fontName=POLICE, fontSize=8.5, leading=11.5, spaceAfter=3)


def gras(texte):
    return f"<b>{escape(texte)}</b>"


def libelle_valeur(libelle, valeur, separateur=SEPARATEUR_LIBELLE):
    return f"{gras(libelle)}{separateur}{escape(valeur)}"


def bandeau(titre):
    return Paragraph(escape(titre.upper()), STYLE_BANDEAU)


def hauteur(flowables, largeur):
    total = MARGE_SECURITE
    for flowable in flowables:
        total += flowable.wrap(largeur, HAUTEUR_ILLIMITEE)[1] + flowable.getSpaceBefore() + flowable.getSpaceAfter()
    return total


def nom_fichier(front):
    morceaux = [sans_accents(front[cle]) for cle in (CLE_NOM, CLE_TITRE)]
    corps = RE_CARACTERES_FICHIER.sub(REMPLACEMENT_FICHIER, REMPLACEMENT_FICHIER.join(morceaux)).strip(REMPLACEMENT_FICHIER)
    return PREFIXE_FICHIER + corps + EXTENSION_PDF


def rendre_entete(front, par_nom):
    profil = par_nom[SECTION_PROFIL].champs
    return [
        Paragraph(escape(front[CLE_NOM].upper()), STYLE_NOM),
        Paragraph(escape(front[CLE_TITRE].upper()), STYLE_TITRE_POSTE),
        Paragraph(escape(par_nom[SECTION_ACCUEIL].champs[SOUS_TITRE]), STYLE_SOUS_TITRE),
        bandeau(profil[TITRE]),
        Paragraph(escape(profil[TEXTE]), STYLE_PROFIL),
    ]


def rendre_coordonnees(front):
    sortie = [bandeau(LIBELLE_COORDONNEES)]
    for libelle, cle in COORDONNEES:
        if front.get(cle):
            sortie.append(Paragraph(libelle_valeur(libelle, front[cle], SAUT_LIGNE), STYLE_LATERAL))
    return sortie


def rendre_blocs(entree):
    sortie = []
    for bloc in entree.blocs:
        puces = [retirer_puce(ligne) for ligne in bloc.lignes if ligne.startswith(MARQUEUR_PUCE)]
        if bloc.nom == BLOC_ENVIRONNEMENT:
            sortie.append(Paragraph(libelle_valeur(bloc.nom, SEPARATEUR_LISTE.join(puces)), STYLE_TEXTE))
        elif puces:
            sortie += [Paragraph(escape(puce), STYLE_PUCE, bulletText=PUCE_PDF) for puce in puces]
        else:
            sortie.append(Paragraph(escape(" ".join(bloc.lignes)), STYLE_TEXTE))
    return sortie


def rendre_infos(*valeurs):
    return Paragraph(SEPARATEUR_INFOS.join(valeurs), STYLE_INFOS)


def rendre_experience(section):
    sortie = [bandeau(section.champs[TITRE])]
    for entree in section.entrees:
        c = entree.champs
        sortie.append(Paragraph(escape(entree.titre.upper()), STYLE_POSTE))
        sortie.append(rendre_infos(f"<b><i>{escape(c[ENTREPRISE])}</i></b>", escape(c[PERIODE]), escape(c[LIEU])))
        sortie += rendre_blocs(entree)
    return sortie


def rendre_projets(section):
    sortie = [bandeau(section.champs[TITRE])]
    for entree in section.entrees:
        c = entree.champs
        sortie.append(Paragraph(escape((c.get(TITRE_DETAIL) or entree.titre).upper()), STYLE_POSTE))
        sortie.append(rendre_infos(f"<b><i>{escape(c[CONTEXTE])}</i></b>", escape(c.get(PERIODE_DETAIL) or c[PERIODE])))
        sortie += rendre_blocs(entree)
    return sortie


def rendre_competences(section):
    cles = [entree for entree in section.entrees if entree.titre == ENTREE_COMPETENCES_CLES]
    autres = [entree for entree in section.entrees if entree.titre != ENTREE_COMPETENCES_CLES]
    principale, lateral = [], []
    if cles:
        principale.append(bandeau(LIBELLE_COMPETENCES_CLES))
        principale += [
            Paragraph(libelle_valeur(entree.titre, SEPARATEUR_LISTE.join(entree.puces)), STYLE_TEXTE) for entree in cles
        ]
    if autres:
        lateral.append(bandeau(LIBELLE_ENVIRONNEMENT_IT))
        for entree in autres:
            lateral.append(Paragraph(libelle_valeur(entree.titre, SEPARATEUR_LISTE.join(entree.puces), SAUT_LIGNE), STYLE_LATERAL))
    return principale, lateral


def rendre_formation(section):
    sortie = [bandeau(LIBELLE_FORMATION)]
    for entree in section.entrees:
        sortie.append(Paragraph(gras(entree.titre), STYLE_TEXTE))
        sortie.append(rendre_infos(escape(entree.champs[ETABLISSEMENT]), escape(entree.champs[PERIODE])))
    return sortie


def rendre_langues(section):
    sortie = [bandeau(LIBELLE_LANGUES)]
    sortie += [Paragraph(libelle_valeur(entree.titre, entree.champs[NIVEAU]), STYLE_LATERAL) for entree in section.entrees]
    return sortie


def cadre(identifiant, x, y, largeur, hauteur_cadre):
    return Frame(x, y, largeur, hauteur_cadre, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id=identifiant)


def construire_modeles(entete, coordonnees, lateral):
    largeur_utile = LARGEUR_PAGE - 2 * MARGE
    largeur_principale = largeur_utile - LARGEUR_LATERALE - ECART_COLONNES
    x_principale = MARGE + LARGEUR_LATERALE + ECART_COLONNES
    hauteur_entete = hauteur(entete, largeur_utile)
    hauteur_coordonnees = hauteur(coordonnees, LARGEUR_LATERALE)
    hauteur_corps = HAUTEUR_PAGE - 2 * MARGE - hauteur_entete
    cadre_lateral = cadre(CADRE_LATERAL, MARGE, MARGE, LARGEUR_LATERALE, hauteur_corps - hauteur_coordonnees)

    # écrite en fin de page, la colonne latérale vient après la colonne principale dans le texte extrait par un ATS
    def ecrire_lateral(canvas, document):
        cadre_lateral.addFromList(lateral, canvas)
        if lateral:
            raise ErreurContenu("PDF : colonne latérale trop longue pour la première page")

    modele_premiere = PageTemplate(
        id=MODELE_PDF,
        frames=[
            cadre(CADRE_ENTETE, MARGE, HAUTEUR_PAGE - MARGE - hauteur_entete, largeur_utile, hauteur_entete),
            cadre(CADRE_COORDONNEES, MARGE, MARGE + hauteur_corps - hauteur_coordonnees, LARGEUR_LATERALE, hauteur_coordonnees),
            cadre(CADRE_PRINCIPALE, x_principale, MARGE, largeur_principale, hauteur_corps),
        ],
        onPageEnd=ecrire_lateral,
    )
    modele_suite = PageTemplate(
        id=MODELE_SUITE, frames=[cadre(CADRE_SUITE, MARGE, MARGE, largeur_utile, HAUTEUR_PAGE - 2 * MARGE)]
    )
    return [modele_premiere, modele_suite]


def construire_pdf(front, par_nom, destination):
    """Écrit le PDF dans `destination` et renvoie son chemin."""
    chemin = destination / nom_fichier(front)
    entete = rendre_entete(front, par_nom)
    coordonnees = rendre_coordonnees(front)
    competences_cles, environnement_it = rendre_competences(par_nom[SECTION_COMPETENCES])
    principale = (
        competences_cles
        + rendre_experience(par_nom[SECTION_EXPERIENCE])
        + rendre_projets(par_nom[SECTION_PROJETS])
        + rendre_formation(par_nom[SECTION_DIPLOMES])
    )
    lateral = environnement_it + rendre_langues(par_nom[SECTION_LANGUES])

    document = BaseDocTemplate(
        str(chemin),
        pagesize=A4,
        pageTemplates=construire_modeles(entete, coordonnees, lateral),
        title=f"CV {front[CLE_NOM]} — {front[CLE_TITRE]}",
        author=front[CLE_NOM],
        subject=front[CLE_DESCRIPTION],
    )
    document.build(
        [NextPageTemplate(MODELE_SUITE)] + entete + [FrameBreak()] + coordonnees + [FrameBreak()] + principale
    )
    return chemin