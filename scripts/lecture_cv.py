"""Lecture du fichier markdown de données : découpe en front-matter, sections, entrées et blocs, avec numéros de ligne."""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_GABARIT = "src"
FICHIER_GABARIT = "index.html"
PREFIXES_URL = ("https://", "http://")

SECTION_ACCUEIL = "Accueil"
SECTION_PROFIL = "Profil"
SECTION_EXPERIENCE = "Expérience"
SECTION_COMPETENCES = "Compétences"
SECTION_PROJETS = "Projets"
SECTION_STAGES = "Stages"
SECTION_DIPLOMES = "Diplômes"
SECTION_LANGUES = "Langues"
SECTION_INTERETS = "Intérêts"
SECTION_LIENS = "Liens"
CATEGORIE_COMPETENCES_PERSONNELLES = "Personnelles"
SECTIONS = [
    SECTION_ACCUEIL,
    SECTION_PROFIL,
    SECTION_EXPERIENCE,
    SECTION_COMPETENCES,
    SECTION_PROJETS,
    SECTION_STAGES,
    SECTION_DIPLOMES,
    SECTION_LANGUES,
    SECTION_INTERETS,
    SECTION_LIENS,
]

CHAMPS_FRONT = ["nom", "titre", "description", "initiales", "email", "pied", "url"]
CHAMPS_FRONT_OPTIONNELS = ["image", "cv_pdf"]
CLE_NOM = "nom"
CLE_TITRE = "titre"
CLE_DESCRIPTION = "description"
CLE_URL = "url"
CLE_IMAGE = "image"
CLE_CV_PDF = "cv_pdf"
TITRE = "Titre"
ICONE = "Icône"
INTRO = "Intro"
STATUT = "Statut"
SOUS_TITRE = "Sous-titre"
TEXTE = "Texte"

ENTREPRISE = "Entreprise"
LIEU = "Lieu"
PERIODE = "Période"
LOGO = "Logo"
CONTEXTE = "Contexte"
TITRE_DETAIL = "Titre détail"
PERIODE_DETAIL = "Période détail"
ETABLISSEMENT = "Établissement"
NIVEAU = "Niveau"
URL = "Url"
BLOC_ENVIRONNEMENT = "Environnement"
BLOC_COMPETENCES = "Compétences"

RE_CHAMP = re.compile(r"^([^:#\-][^:]*?):\s*(.*)$")

MARQUEUR_FRONT = "---"
MARQUEUR_SECTION = "## "
MARQUEUR_ENTREE = "### "
MARQUEUR_BLOC = "#### "
MARQUEUR_PUCE = "- "


class ErreurContenu(Exception):
    pass


class FrontMatter(dict):
    def __init__(self):
        super().__init__()
        self.lignes_champs = {}


@dataclass
class Bloc:
    nom: str
    lignes: list = field(default_factory=list)
    ligne: int = 0


@dataclass
class Entree:
    titre: str
    champs: dict = field(default_factory=dict)
    puces: list = field(default_factory=list)
    blocs: list = field(default_factory=list)
    ligne: int = 0
    lignes_champs: dict = field(default_factory=dict)
    lignes_puces: list = field(default_factory=list)


@dataclass
class Section:
    nom: str
    champs: dict = field(default_factory=dict)
    entrees: list = field(default_factory=list)
    ligne: int = 0
    lignes_champs: dict = field(default_factory=dict)


def sans_accents(texte):
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def identifiant(nom):
    return sans_accents(nom).lower()


def titre_de_page(nom, titre):
    return f"{nom} — {titre}"


def cle_competence(libelle):
    return libelle.strip().casefold()


def indexer_competences(section):
    """Index des compétences de la section : clé normalisée → (libellé, entrée catégorie) ; la première occurrence l'emporte."""
    index = {}
    for entree in section.entrees:
        for libelle in entree.puces:
            index.setdefault(cle_competence(libelle), (libelle, entree))
    return index


def icones_du_gabarit(chemin):
    return set(re.findall(r'<symbol id="i-([\w-]+)"', chemin.read_text(encoding="utf-8")))


def retirer_puce(ligne):
    return ligne[len(MARQUEUR_PUCE):]


def puces_du_bloc(bloc):
    return [retirer_puce(ligne) for ligne in bloc.lignes if ligne.startswith(MARQUEUR_PUCE)]


def signaler(anomalies, numero, contexte, message):
    """Lève ErreurContenu si `anomalies` est None, sinon consigne (numéro, contexte, message) et laisse la lecture continuer."""
    if anomalies is None:
        raise ErreurContenu(f"{contexte} : {message}" if contexte else message)
    anomalies.append((numero, contexte, message))


def lire_champ(ligne, contexte, numero=0, anomalies=None):
    correspondance = RE_CHAMP.match(ligne)
    if not correspondance:
        signaler(anomalies, numero, contexte, f"ligne non reconnue « {ligne} »")
        return None
    return correspondance.group(1), correspondance.group(2)


def lire_front_matter(lignes, anomalies=None):
    if not lignes or lignes[0].strip() != MARQUEUR_FRONT:
        raise ErreurContenu("front-matter absent (la première ligne doit être « --- »)")
    fin = next((i for i, ligne in enumerate(lignes[1:], 1) if ligne.strip() == MARQUEUR_FRONT), None)
    if fin is None:
        raise ErreurContenu("front-matter non refermé (ligne « --- » manquante)")
    front = FrontMatter()
    for numero, ligne in enumerate(lignes[1:fin], 2):
        if ligne.strip():
            lu = lire_champ(ligne.strip(), "front-matter", numero, anomalies)
            if lu:
                front[lu[0]] = lu[1]
                front.lignes_champs[lu[0]] = numero
    return front, fin


def ajouter_ligne(sections, brut, numero, anomalies=None):
    if not sections:
        raise ErreurContenu(f"contenu avant la première section : « {brut} »")
    section = sections[-1]
    entree = section.entrees[-1] if section.entrees else None
    if entree and entree.blocs:
        entree.blocs[-1].lignes.append(brut)
    elif entree and brut.startswith(MARQUEUR_PUCE):
        entree.puces.append(retirer_puce(brut))
        entree.lignes_puces.append(numero)
    elif entree:
        lu = lire_champ(brut, f"{section.nom} / {entree.titre}", numero, anomalies)
        if lu:
            entree.champs[lu[0]] = lu[1]
            entree.lignes_champs[lu[0]] = numero
    else:
        lu = lire_champ(brut, section.nom, numero, anomalies)
        if lu:
            section.champs[lu[0]] = lu[1]
            section.lignes_champs[lu[0]] = numero


def decouper(texte, anomalies=None):
    """Sans `anomalies`, la première ligne non reconnue ou le premier bloc mal placé lève ErreurContenu.
    Avec une liste, ils y sont consignés sous forme (numéro de ligne, contexte, message) et la lecture continue."""
    lignes = texte.splitlines()
    front, fin = lire_front_matter(lignes, anomalies)

    sections = []
    bloc_orphelin = False
    for numero, ligne in enumerate(lignes[fin + 1:], fin + 2):
        brut = ligne.strip()
        if not brut:
            continue
        if brut.startswith(MARQUEUR_BLOC):
            nom = brut[len(MARQUEUR_BLOC):]
            bloc_orphelin = not sections or not sections[-1].entrees
            if bloc_orphelin:
                signaler(anomalies, numero, sections[-1].nom if sections else "", f"bloc « {nom} » placé hors d'une entrée (###)")
            else:
                sections[-1].entrees[-1].blocs.append(Bloc(nom, ligne=numero))
        elif brut.startswith(MARQUEUR_ENTREE):
            bloc_orphelin = False
            titre = brut[len(MARQUEUR_ENTREE):]
            if not sections:
                raise ErreurContenu(f"entrée « {titre} » placée avant toute section (##)")
            sections[-1].entrees.append(Entree(titre, ligne=numero))
        elif brut.startswith(MARQUEUR_SECTION):
            bloc_orphelin = False
            sections.append(Section(brut[len(MARQUEUR_SECTION):], ligne=numero))
        elif not bloc_orphelin:
            ajouter_ligne(sections, brut, numero, anomalies)
    return front, sections
