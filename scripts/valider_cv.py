"""Valide le fichier markdown de données : liste toutes les anomalies (erreurs bloquantes et avertissements) avec leur numéro de ligne."""

import argparse
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from lecture_cv import (
    BLOC_COMPETENCES,
    BLOC_ENVIRONNEMENT,
    CATEGORIE_COMPETENCES_PERSONNELLES,
    CHAMPS_FRONT,
    CHAMPS_FRONT_OPTIONNELS,
    CLE_CV_PDF,
    CLE_DESCRIPTION,
    CLE_IMAGE,
    CLE_NOM,
    CLE_TITRE,
    CLE_URL,
    CONTEXTE,
    ENTREPRISE,
    ETABLISSEMENT,
    DOSSIER_GABARIT,
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
    cle_competence,
    decouper,
    icones_du_gabarit,
    indexer_competences,
    puces_du_bloc,
    titre_de_page,
)

GABARIT = RACINE / DOSSIER_GABARIT / FICHIER_GABARIT

NIVEAU_ERREUR = "ERREUR"
NIVEAU_AVERTISSEMENT = "AVERT."
CONTEXTE_FRONT = "front-matter"
LIGNE_FRONT = 1

CLE_EMAIL = "email"
CLE_INITIALES = "initiales"

PREFIXE_HTTPS = "https://"
CARACTERES_URL_INTERDITS = (" ", '"', "<", ">")
SEPARATEURS_CHEMIN = ("/", "\\")
EXTENSIONS_IMAGE = (".png", ".jpg", ".jpeg")
LIBELLE_EXTENSIONS_IMAGE = ".png, .jpg ou .jpeg"
EXTENSION_PNG = ".png"
EXTENSION_PDF = ".pdf"
FICHIERS_RESERVES = ("index.html", "style.css", "favicon.svg", "robots.txt", "sitemap.xml", "og.html", "icone.html", "icone.png")
SIGNATURE_PNG = b"\x89PNG\r\n\x1a\n"
TAILLE_ENTETE_PNG = 24
DECALAGE_DIMENSIONS_PNG = 16
FORMAT_DIMENSIONS_PNG = ">II"
MODE_LECTURE_BINAIRE = "rb"
DIMENSIONS_IMAGE = (1200, 630)

LONGUEUR_TITRE_MAX = 60
LONGUEUR_DESCRIPTION_MIN = 50
LONGUEUR_DESCRIPTION_MAX = 160
LONGUEUR_LOGO_MAX = 3

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MOIS_OU_ANNEE = r"(?:[^\W\d_]+\.?\s)?\d{4}"
RE_PERIODE = re.compile(rf"^{MOIS_OU_ANNEE}(?:\s–\s(?:auj\.|aujourd['’]hui|{MOIS_OU_ANNEE}))?$")

CHAMPS_SECTION = {
    SECTION_ACCUEIL: [ICONE, STATUT, SOUS_TITRE],
    SECTION_PROFIL: [ICONE, TITRE, TEXTE],
    SECTION_EXPERIENCE: [ICONE, TITRE, INTRO],
    SECTION_COMPETENCES: [ICONE, TITRE, INTRO],
    SECTION_PROJETS: [ICONE, TITRE, INTRO],
    SECTION_STAGES: [ICONE, TITRE, INTRO],
    SECTION_DIPLOMES: [ICONE, TITRE, INTRO],
    SECTION_LANGUES: [ICONE, TITRE, INTRO],
    SECTION_INTERETS: [ICONE, TITRE, INTRO],
    SECTION_LIENS: [ICONE, TITRE],
}
CHAMPS_ENTREE_REQUIS = {
    SECTION_EXPERIENCE: [ENTREPRISE, LIEU, PERIODE, LOGO],
    SECTION_COMPETENCES: [ICONE],
    SECTION_PROJETS: [CONTEXTE, PERIODE, LOGO],
    SECTION_STAGES: [ENTREPRISE, LIEU, PERIODE, LOGO],
    SECTION_DIPLOMES: [ETABLISSEMENT, PERIODE, LOGO],
    SECTION_LANGUES: [NIVEAU],
    SECTION_INTERETS: [ICONE],
    SECTION_LIENS: [URL, LOGO],
}
CHAMPS_ENTREE_OPTIONNELS = {SECTION_PROJETS: [TITRE_DETAIL, PERIODE_DETAIL]}
SECTIONS_AVEC_BLOCS = [SECTION_EXPERIENCE, SECTION_PROJETS, SECTION_STAGES]
SECTIONS_AVEC_PUCES = [SECTION_COMPETENCES, SECTION_INTERETS]
CHAMPS_PERIODE = [PERIODE, PERIODE_DETAIL]


@dataclass
class Anomalie:
    niveau: str
    ligne: int
    contexte: str
    message: str

    def __str__(self):
        contexte = f"{self.contexte} : " if self.contexte else ""
        return f"ligne {self.ligne} : [{self.niveau}] {contexte}{self.message}"


def erreur(ligne, contexte, message):
    return Anomalie(NIVEAU_ERREUR, ligne, contexte, message)


def avertissement(ligne, contexte, message):
    return Anomalie(NIVEAU_AVERTISSEMENT, ligne, contexte, message)


def initiales_de(nom):
    return "".join(mot[0] for mot in nom.split()).upper()


def est_puce(ligne):
    return ligne.startswith(MARQUEUR_PUCE) or ligne == MARQUEUR_PUCE.strip()


def valider_url(front):
    url = front.get(CLE_URL)
    if not url:
        return []
    ligne = front.lignes_champs[CLE_URL]
    sortie = []
    if not url.startswith(PREFIXE_HTTPS):
        sortie.append(erreur(ligne, CONTEXTE_FRONT, f"« {CLE_URL} » doit commencer par {PREFIXE_HTTPS}"))
    if any(caractere in url for caractere in CARACTERES_URL_INTERDITS):
        sortie.append(erreur(ligne, CONTEXTE_FRONT, f"« {CLE_URL} » contient un espace, un guillemet, « < » ou « > »"))
    return sortie


def valider_fichier_voisin(front, cle, extensions, libelle_extensions, dossier_source, noms_reserves=()):
    """Contrôle commun aux champs désignant un fichier posé à côté du CV source ; retourne la première erreur trouvée."""
    nom_fichier = front[cle]
    ligne = front.lignes_champs[cle]
    if any(separateur in nom_fichier for separateur in SEPARATEURS_CHEMIN):
        return [erreur(ligne, CONTEXTE_FRONT, f"« {cle} » doit être un nom de fichier placé à côté du CV source, sans sous-dossier")]
    if not nom_fichier.lower().endswith(extensions):
        return [erreur(ligne, CONTEXTE_FRONT, f"« {cle} » doit être un fichier {libelle_extensions}")]
    if nom_fichier in noms_reserves:
        return [erreur(ligne, CONTEXTE_FRONT, f"« {cle} » porte le nom d'un fichier du gabarit ({nom_fichier}) que la copie écraserait")]
    return erreur_si_introuvable(front, cle, dossier_source / nom_fichier)


def erreur_si_introuvable(front, cle, chemin):
    if chemin.is_file():
        return []
    return [erreur(front.lignes_champs[cle], CONTEXTE_FRONT, f"« {cle} » : fichier introuvable ({chemin})")]


def valider_image(front, dossier_source):
    image = front.get(CLE_IMAGE)
    if not image:
        return []
    ligne = front.lignes_champs[CLE_IMAGE]
    anomalies = valider_fichier_voisin(front, CLE_IMAGE, EXTENSIONS_IMAGE, LIBELLE_EXTENSIONS_IMAGE, dossier_source, FICHIERS_RESERVES)
    if anomalies:
        return anomalies
    chemin = dossier_source / image
    if not image.lower().endswith(EXTENSION_PNG):
        return []
    with chemin.open(MODE_LECTURE_BINAIRE) as fichier:
        entete = fichier.read(TAILLE_ENTETE_PNG)
    if len(entete) < TAILLE_ENTETE_PNG or not entete.startswith(SIGNATURE_PNG):
        return [erreur(ligne, CONTEXTE_FRONT, f"« {CLE_IMAGE} » n'est pas un PNG valide")]
    dimensions = struct.unpack(FORMAT_DIMENSIONS_PNG, entete[DECALAGE_DIMENSIONS_PNG:TAILLE_ENTETE_PNG])
    if dimensions != DIMENSIONS_IMAGE:
        return [avertissement(ligne, CONTEXTE_FRONT, f"« {CLE_IMAGE} » de {dimensions[0]}x{dimensions[1]} px (attendu {DIMENSIONS_IMAGE[0]}x{DIMENSIONS_IMAGE[1]})")]
    return []


def valider_cv_pdf(front, dossier_source):
    if not front.get(CLE_CV_PDF):
        return []
    chemin_pdf = front[CLE_CV_PDF]
    ligne = front.lignes_champs[CLE_CV_PDF]
    if not chemin_pdf.lower().endswith(EXTENSION_PDF):
        return [erreur(ligne, CONTEXTE_FRONT, f"« {CLE_CV_PDF} » doit être un fichier {EXTENSION_PDF}")]
    return erreur_si_introuvable(front, CLE_CV_PDF, dossier_source / chemin_pdf)


def valider_front(front, dossier_source):
    sortie = valider_url(front) + valider_image(front, dossier_source) + valider_cv_pdf(front, dossier_source)
    for cle in CHAMPS_FRONT:
        if not front.get(cle):
            sortie.append(erreur(front.lignes_champs.get(cle, LIGNE_FRONT), CONTEXTE_FRONT, f"champ « {cle} » manquant ou vide"))
    for cle, ligne in front.lignes_champs.items():
        if cle not in CHAMPS_FRONT + CHAMPS_FRONT_OPTIONNELS:
            sortie.append(avertissement(ligne, CONTEXTE_FRONT, f"champ « {cle} » inconnu, ignoré par le rendu"))
    courriel = front.get(CLE_EMAIL)
    if courriel and not RE_EMAIL.match(courriel):
        sortie.append(erreur(front.lignes_champs[CLE_EMAIL], CONTEXTE_FRONT, f"« {CLE_EMAIL} » n'a pas la forme x@y.z"))
    nom, initiales = front.get(CLE_NOM), front.get(CLE_INITIALES)
    if nom and initiales and initiales_de(nom) != initiales.upper():
        sortie.append(
            avertissement(front.lignes_champs[CLE_INITIALES], CONTEXTE_FRONT, f"« {CLE_INITIALES} » ({initiales}) différent des initiales de « {CLE_NOM} » ({initiales_de(nom)})")
        )
    if nom and front.get(CLE_TITRE):
        titre_page = titre_de_page(nom, front[CLE_TITRE])
        if len(titre_page) > LONGUEUR_TITRE_MAX:
            sortie.append(avertissement(LIGNE_FRONT, CONTEXTE_FRONT, f"titre de page de {len(titre_page)} caractères (au-delà de {LONGUEUR_TITRE_MAX})"))
    description = front.get(CLE_DESCRIPTION)
    if description and len(description) > LONGUEUR_DESCRIPTION_MAX:
        sortie.append(
            avertissement(front.lignes_champs[CLE_DESCRIPTION], CONTEXTE_FRONT, f"« {CLE_DESCRIPTION} » de {len(description)} caractères (au-delà de {LONGUEUR_DESCRIPTION_MAX})")
        )
    if description and len(description) < LONGUEUR_DESCRIPTION_MIN:
        sortie.append(
            avertissement(front.lignes_champs[CLE_DESCRIPTION], CONTEXTE_FRONT, f"« {CLE_DESCRIPTION} » de {len(description)} caractères (en dessous de {LONGUEUR_DESCRIPTION_MIN})")
        )
    return sortie


def valider_ordre(sections):
    sortie, vues = [], {}
    for section in sections:
        if section.nom not in SECTIONS:
            sortie.append(erreur(section.ligne, section.nom, "section inconnue"))
        elif section.nom in vues:
            sortie.append(erreur(section.ligne, section.nom, "section présente plusieurs fois"))
        else:
            vues[section.nom] = section
    for nom in SECTIONS:
        if nom not in vues:
            sortie.append(erreur(LIGNE_FRONT, nom, "section absente"))
    presentes = list(vues)
    attendues = [nom for nom in SECTIONS if nom in vues]
    if presentes != attendues:
        rang = next(i for i, nom in enumerate(presentes) if nom != attendues[i])
        sortie.append(erreur(vues[presentes[rang]].ligne, presentes[rang], f"ordre des sections non conforme (attendu : {', '.join(attendues)})"))
    return sortie


def valider_champs(champs, lignes, requis, autorises, contexte, ligne_defaut, icones):
    sortie = []
    for cle in requis:
        if not champs.get(cle):
            sortie.append(erreur(lignes.get(cle, ligne_defaut), contexte, f"champ « {cle} » manquant ou vide"))
    for cle in champs:
        if cle not in autorises:
            sortie.append(erreur(lignes[cle], contexte, f"champ « {cle} » inconnu, il serait ignoré par le rendu"))
    if champs.get(ICONE) and champs[ICONE] not in icones:
        sortie.append(erreur(lignes[ICONE], contexte, f"icône « {champs[ICONE]} » absente du sprite du gabarit"))
    return sortie


def valider_bloc(bloc, contexte, competences):
    if not bloc.lignes:
        return [erreur(bloc.ligne, contexte, f"bloc « {bloc.nom} » vide")]
    sortie = []
    puces = [est_puce(ligne) for ligne in bloc.lignes]
    if any(puces) and not all(puces):
        sortie.append(erreur(bloc.ligne, contexte, f"bloc « {bloc.nom} » mêle texte et puces"))
    for nom_liste in (BLOC_ENVIRONNEMENT, BLOC_COMPETENCES):
        if bloc.nom == nom_liste and not all(puces):
            sortie.append(erreur(bloc.ligne, contexte, f"bloc « {nom_liste} » doit être une liste à puces"))
    if bloc.nom == BLOC_COMPETENCES:
        for libelle in puces_du_bloc(bloc):
            if cle_competence(libelle) not in competences:
                sortie.append(erreur(bloc.ligne, contexte, f"compétence « {libelle} » absente de la section « {SECTION_COMPETENCES} »"))
    if MARQUEUR_PUCE.strip() in bloc.lignes:
        sortie.append(erreur(bloc.ligne, contexte, f"bloc « {bloc.nom} » contient une puce vide"))
    return sortie


def valider_entree(section, entree, icones, competences):
    nom = section.nom
    contexte = f"{nom} / {entree.titre}"
    requis = CHAMPS_ENTREE_REQUIS[nom]
    sortie = valider_champs(entree.champs, entree.lignes_champs, requis, requis + CHAMPS_ENTREE_OPTIONNELS.get(nom, []), contexte, entree.ligne, icones)
    if len(entree.champs.get(LOGO, "")) > LONGUEUR_LOGO_MAX:
        sortie.append(avertissement(entree.lignes_champs[LOGO], contexte, f"« {LOGO} » de plus de {LONGUEUR_LOGO_MAX} caractères"))
    for cle in CHAMPS_PERIODE:
        valeur = entree.champs.get(cle)
        if valeur and not RE_PERIODE.match(valeur):
            sortie.append(avertissement(entree.lignes_champs[cle], contexte, f"« {cle} » de forme inhabituelle : « {valeur} »"))
    url = entree.champs.get(URL)
    if url and not url.startswith(PREFIXES_URL):
        sortie.append(erreur(entree.lignes_champs[URL], contexte, f"« {URL} » doit commencer par https:// ou http://"))
    if nom in SECTIONS_AVEC_PUCES and not entree.puces:
        sortie.append(erreur(entree.ligne, contexte, "aucune puce listée"))
    if nom not in SECTIONS_AVEC_PUCES and entree.puces:
        sortie.append(erreur(entree.lignes_puces[0], contexte, "puces ignorées par le rendu dans cette section"))
    if nom not in SECTIONS_AVEC_BLOCS and entree.blocs:
        sortie.append(erreur(entree.blocs[0].ligne, contexte, "blocs (####) ignorés par le rendu dans cette section"))
    for bloc in entree.blocs:
        sortie.extend(valider_bloc(bloc, contexte, competences))
    return sortie


def valider_section(section, icones, competences):
    nom = section.nom
    sortie = valider_champs(section.champs, section.lignes_champs, CHAMPS_SECTION[nom], CHAMPS_SECTION[nom], nom, section.ligne, icones)
    if nom not in CHAMPS_ENTREE_REQUIS:
        if section.entrees:
            sortie.append(erreur(section.entrees[0].ligne, nom, "entrées (###) ignorées par le rendu dans cette section"))
        return sortie
    if not section.entrees:
        sortie.append(erreur(section.ligne, nom, "aucune entrée (###)"))
    cles = {}
    for entree in section.entrees:
        cle = (entree.titre, entree.champs.get(ENTREPRISE))
        if cle in cles:
            sortie.append(erreur(entree.ligne, nom, f"entrée « {entree.titre} » en double (première ligne {cles[cle]})"))
        cles.setdefault(cle, entree.ligne)
        sortie.extend(valider_entree(section, entree, icones, competences))
    return sortie


def blocs_competences(sections):
    return [
        bloc
        for section in sections
        if section.nom in SECTIONS_AVEC_BLOCS
        for entree in section.entrees
        for bloc in entree.blocs
        if bloc.nom == BLOC_COMPETENCES
    ]


def valider_competences_inutilisees(sections, competences):
    """Avertit des compétences jamais citées dans un bloc « Compétences » ; muet tant qu'aucun bloc n'est utilisé, et pour la catégorie des savoir-être."""
    blocs = blocs_competences(sections)
    if not blocs:
        return []
    citees = {cle_competence(libelle) for bloc in blocs for libelle in puces_du_bloc(bloc)}
    sortie = []
    for cle, (libelle, entree) in competences.items():
        if cle not in citees and entree.titre != CATEGORIE_COMPETENCES_PERSONNELLES:
            ligne = entree.lignes_puces[entree.puces.index(libelle)]
            sortie.append(avertissement(ligne, f"{SECTION_COMPETENCES} / {entree.titre}", f"compétence « {libelle} » rattachée à aucune expérience, projet ou stage"))
    return sortie


def valider_espaces(texte):
    return [
        avertissement(numero, "", "espaces superflus en fin de ligne")
        for numero, ligne in enumerate(texte.splitlines(), 1)
        if ligne != ligne.rstrip()
    ]


def valider(texte, icones, dossier_source):
    consignees = []
    try:
        front, sections = decouper(texte, consignees)
    except ErreurContenu as fatale:
        return [erreur(LIGNE_FRONT, "", str(fatale))]
    anomalies = [erreur(ligne, contexte, message) for ligne, contexte, message in consignees]
    anomalies += valider_front(front, dossier_source)
    anomalies += valider_ordre(sections)
    section_competences = next((s for s in sections if s.nom == SECTION_COMPETENCES), None)
    competences = indexer_competences(section_competences) if section_competences else {}
    for section in sections:
        if section.nom in SECTIONS:
            anomalies += valider_section(section, icones, competences)
    anomalies += valider_competences_inutilisees(sections, competences)
    anomalies += valider_espaces(texte)
    return sorted(anomalies, key=lambda a: a.ligne)


def compter(anomalies, niveau):
    return sum(1 for a in anomalies if a.niveau == niveau)


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--source", type=Path, required=True, help="fichier markdown des données")
    arguments = analyseur.parse_args()
    try:
        anomalies = valider(arguments.source.read_text(encoding="utf-8"), icones_du_gabarit(GABARIT), arguments.source.parent)
    except (OSError, ValueError) as erreur_lecture:
        print(f"Erreur : {erreur_lecture}", file=sys.stderr)
        return 1
    for anomalie in anomalies:
        print(anomalie)
    erreurs = compter(anomalies, NIVEAU_ERREUR)
    print(f"{erreurs} erreur(s), {compter(anomalies, NIVEAU_AVERTISSEMENT)} avertissement(s)")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
