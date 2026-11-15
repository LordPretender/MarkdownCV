"""Lecture du fichier markdown de données : découpe en front-matter, sections, entrées et blocs, avec numéros de ligne."""

import re
import unicodedata
from dataclasses import dataclass, field

SECTION_ACCUEIL = "Accueil"
SECTION_PROFIL = "Profil"
SECTION_EXPERIENCE = "Expérience"
SECTION_COMPETENCES = "Compétences"
SECTION_PROJETS = "Projets"
SECTION_DIPLOMES = "Diplômes"
SECTION_LANGUES = "Langues"
SECTION_LIENS = "Liens"
SECTIONS = [
    SECTION_ACCUEIL,
    SECTION_PROFIL,
    SECTION_EXPERIENCE,
    SECTION_COMPETENCES,
    SECTION_PROJETS,
    SECTION_DIPLOMES,
    SECTION_LANGUES,
    SECTION_LIENS,
]

CHAMPS_FRONT = ["nom", "titre", "description", "initiales", "email", "pied"]
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


def identifiant(nom):
    decompose = unicodedata.normalize("NFD", nom)
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


def lire_champ(ligne, contexte):
    correspondance = RE_CHAMP.match(ligne)
    if not correspondance:
        raise ErreurContenu(f"{contexte} : ligne non reconnue « {ligne} »")
    return correspondance.group(1), correspondance.group(2)


def lire_front_matter(lignes):
    if not lignes or lignes[0].strip() != MARQUEUR_FRONT:
        raise ErreurContenu("front-matter absent (la première ligne doit être « --- »)")
    try:
        fin = lignes.index(MARQUEUR_FRONT, 1)
    except ValueError:
        raise ErreurContenu("front-matter non refermé (ligne « --- » manquante)") from None
    front = FrontMatter()
    for numero, ligne in enumerate(lignes[1:fin], 2):
        if ligne.strip():
            cle, valeur = lire_champ(ligne.strip(), "front-matter")
            front[cle] = valeur
            front.lignes_champs[cle] = numero
    return front, fin


def ajouter_ligne(sections, brut, numero):
    if not sections:
        raise ErreurContenu(f"contenu avant la première section : « {brut} »")
    section = sections[-1]
    entree = section.entrees[-1] if section.entrees else None
    if entree and entree.blocs:
        entree.blocs[-1].lignes.append(brut)
    elif entree and brut.startswith(MARQUEUR_PUCE):
        entree.puces.append(brut[len(MARQUEUR_PUCE):])
        entree.lignes_puces.append(numero)
    elif entree:
        cle, valeur = lire_champ(brut, f"{section.nom} / {entree.titre}")
        entree.champs[cle] = valeur
        entree.lignes_champs[cle] = numero
    else:
        cle, valeur = lire_champ(brut, section.nom)
        section.champs[cle] = valeur
        section.lignes_champs[cle] = numero


def decouper(texte):
    lignes = texte.splitlines()
    front, fin = lire_front_matter(lignes)

    sections = []
    for numero, ligne in enumerate(lignes[fin + 1:], fin + 2):
        brut = ligne.strip()
        if not brut:
            continue
        if brut.startswith(MARQUEUR_BLOC):
            nom = brut[len(MARQUEUR_BLOC):]
            if not sections or not sections[-1].entrees:
                raise ErreurContenu(f"bloc « {nom} » placé hors d'une entrée (###)")
            sections[-1].entrees[-1].blocs.append(Bloc(nom, ligne=numero))
        elif brut.startswith(MARQUEUR_ENTREE):
            titre = brut[len(MARQUEUR_ENTREE):]
            if not sections:
                raise ErreurContenu(f"entrée « {titre} » placée avant toute section (##)")
            sections[-1].entrees.append(Entree(titre, ligne=numero))
        elif brut.startswith(MARQUEUR_SECTION):
            sections.append(Section(brut[len(MARQUEUR_SECTION):], ligne=numero))
        else:
            ajouter_ligne(sections, brut, numero)
    return front, sections
