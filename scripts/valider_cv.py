"""Valide le fichier markdown de données : liste toutes les anomalies (erreurs bloquantes et avertissements) avec leur numéro de ligne."""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from lecture_cv import (
    BLOC_ENVIRONNEMENT,
    CHAMPS_FRONT,
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
    SECTION_LANGUES,
    SECTION_LIENS,
    SECTION_PROFIL,
    SECTION_PROJETS,
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
)

GABARIT = RACINE / DOSSIER_GABARIT / FICHIER_GABARIT

NIVEAU_ERREUR = "ERREUR"
NIVEAU_AVERTISSEMENT = "AVERT."
CONTEXTE_FRONT = "front-matter"
LIGNE_FRONT = 1

CLE_TELEPHONE = "telephone"
CLE_EMAIL = "email"
CLE_NOM = "nom"
CLE_INITIALES = "initiales"
CLE_DESCRIPTION = "description"
CHAMPS_FRONT_REQUIS = CHAMPS_FRONT + [CLE_TELEPHONE]
CHAMPS_FRONT_PDF = ["localisation", "permis", "mobilite", "linkedin"]
CHAMPS_FRONT_CONNUS = CHAMPS_FRONT_REQUIS + CHAMPS_FRONT_PDF

LONGUEUR_DESCRIPTION_MAX = 160
LONGUEUR_LOGO_MAX = 3
LONGUEUR_PROFIL_MIN = 200
LONGUEUR_PROFIL_MAX = 700

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RE_TELEPHONE = re.compile(r"^\+?[\d\s().-]+$")
MOIS_OU_ANNEE = r"(?:[^\W\d_]+\.?\s)?\d{4}"
RE_PERIODE = re.compile(rf"^{MOIS_OU_ANNEE}(?:\s–\s(?:auj\.|{MOIS_OU_ANNEE}))?$")
RE_CHIFFRE = re.compile(r"\d")

PARENTHESE_OUVRANTE = "("
BLOC_MISSIONS = "Missions"
ACRONYMES = ["N2/N3", "SaaS", "ERP", "SEPA", "PRA/PCA", "OWASP", "IA", "SGBD", "RCA"]

CHAMPS_SECTION = {
    SECTION_ACCUEIL: [ICONE, STATUT, SOUS_TITRE],
    SECTION_PROFIL: [ICONE, TITRE, TEXTE],
    SECTION_EXPERIENCE: [ICONE, TITRE, INTRO],
    SECTION_COMPETENCES: [ICONE, TITRE, INTRO],
    SECTION_PROJETS: [ICONE, TITRE, INTRO],
    SECTION_DIPLOMES: [ICONE, TITRE, INTRO],
    SECTION_LANGUES: [ICONE, TITRE, INTRO],
    SECTION_LIENS: [ICONE, TITRE],
}
CHAMPS_ENTREE_REQUIS = {
    SECTION_EXPERIENCE: [ENTREPRISE, LIEU, PERIODE, LOGO],
    SECTION_COMPETENCES: [ICONE],
    SECTION_PROJETS: [CONTEXTE, PERIODE, LOGO],
    SECTION_DIPLOMES: [ETABLISSEMENT, PERIODE, LOGO],
    SECTION_LANGUES: [NIVEAU],
    SECTION_LIENS: [URL, LOGO],
}
CHAMPS_ENTREE_OPTIONNELS = {SECTION_PROJETS: [TITRE_DETAIL, PERIODE_DETAIL]}
SECTIONS_AVEC_BLOCS = [SECTION_EXPERIENCE, SECTION_PROJETS]
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


def acronymes_non_developpes(texte):
    manquants = []
    for acronyme in ACRONYMES:
        motif = re.compile(rf"(?<![\w/]){re.escape(acronyme)}(?![\w/])")
        occurrences = list(motif.finditer(texte))
        developpe = any(
            texte[: m.start()].rstrip().endswith(PARENTHESE_OUVRANTE)
            or texte[m.end():].lstrip().startswith(PARENTHESE_OUVRANTE)
            for m in occurrences
        )
        if occurrences and not developpe:
            manquants.append(acronyme)
    return manquants


def valider_front(front):
    sortie = []
    for cle in CHAMPS_FRONT_REQUIS:
        if not front.get(cle):
            sortie.append(erreur(front.lignes_champs.get(cle, LIGNE_FRONT), CONTEXTE_FRONT, f"champ « {cle} » manquant ou vide"))
    for cle, ligne in front.lignes_champs.items():
        if cle not in CHAMPS_FRONT_CONNUS:
            sortie.append(avertissement(ligne, CONTEXTE_FRONT, f"champ « {cle} » inconnu, ignoré par le rendu"))
    for cle in CHAMPS_FRONT_PDF:
        if cle not in front:
            sortie.append(avertissement(LIGNE_FRONT, CONTEXTE_FRONT, f"champ « {cle} » absent (coordonnée du PDF)"))
    courriel = front.get(CLE_EMAIL)
    if courriel and not RE_EMAIL.match(courriel):
        sortie.append(erreur(front.lignes_champs[CLE_EMAIL], CONTEXTE_FRONT, f"« {CLE_EMAIL} » n'a pas la forme x@y.z"))
    telephone = front.get(CLE_TELEPHONE)
    if telephone and not RE_TELEPHONE.match(telephone):
        sortie.append(
            avertissement(front.lignes_champs[CLE_TELEPHONE], CONTEXTE_FRONT, f"« {CLE_TELEPHONE} » contient autre chose que chiffres, espaces, +, parenthèses, points ou tirets")
        )
    nom, initiales = front.get(CLE_NOM), front.get(CLE_INITIALES)
    if nom and initiales and initiales_de(nom) != initiales.upper():
        sortie.append(
            avertissement(front.lignes_champs[CLE_INITIALES], CONTEXTE_FRONT, f"« {CLE_INITIALES} » ({initiales}) différent des initiales de « {CLE_NOM} » ({initiales_de(nom)})")
        )
    description = front.get(CLE_DESCRIPTION)
    if description and len(description) > LONGUEUR_DESCRIPTION_MAX:
        sortie.append(
            avertissement(front.lignes_champs[CLE_DESCRIPTION], CONTEXTE_FRONT, f"« {CLE_DESCRIPTION} » de {len(description)} caractères (au-delà de {LONGUEUR_DESCRIPTION_MAX})")
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


def valider_bloc(bloc, contexte):
    if not bloc.lignes:
        return [erreur(bloc.ligne, contexte, f"bloc « {bloc.nom} » vide")]
    sortie = []
    puces = [est_puce(ligne) for ligne in bloc.lignes]
    if any(puces) and not all(puces):
        sortie.append(erreur(bloc.ligne, contexte, f"bloc « {bloc.nom} » mêle texte et puces"))
    if bloc.nom == BLOC_ENVIRONNEMENT and not all(puces):
        sortie.append(erreur(bloc.ligne, contexte, f"bloc « {BLOC_ENVIRONNEMENT} » doit être une liste à puces"))
    if MARQUEUR_PUCE.strip() in bloc.lignes:
        sortie.append(erreur(bloc.ligne, contexte, f"bloc « {bloc.nom} » contient une puce vide"))
    return sortie


def valider_entree(section, entree, icones):
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
    if nom == SECTION_COMPETENCES and not entree.puces:
        sortie.append(erreur(entree.ligne, contexte, "aucune compétence listée"))
    if nom != SECTION_COMPETENCES and entree.puces:
        sortie.append(erreur(entree.lignes_puces[0], contexte, "puces ignorées par le rendu dans cette section"))
    if nom not in SECTIONS_AVEC_BLOCS and entree.blocs:
        sortie.append(erreur(entree.blocs[0].ligne, contexte, "blocs (####) ignorés par le rendu dans cette section"))
    for bloc in entree.blocs:
        sortie.extend(valider_bloc(bloc, contexte))
    if nom == SECTION_EXPERIENCE:
        sortie.extend(valider_ats_experience(entree, contexte))
    return sortie


def valider_ats_experience(entree, contexte):
    sortie = []
    if not any(bloc.nom == BLOC_MISSIONS for bloc in entree.blocs):
        sortie.append(avertissement(entree.ligne, contexte, f"aucun bloc « {BLOC_MISSIONS} »"))
    texte = "\n".join(ligne for bloc in entree.blocs for ligne in bloc.lignes)
    if not RE_CHIFFRE.search(texte):
        sortie.append(avertissement(entree.ligne, contexte, "aucun chiffre dans les blocs (réalisations chiffrées recommandées)"))
    for acronyme in acronymes_non_developpes(texte):
        sortie.append(avertissement(entree.ligne, contexte, f"acronyme « {acronyme} » sans forme développée"))
    return sortie


def valider_section(section, icones):
    nom = section.nom
    sortie = valider_champs(section.champs, section.lignes_champs, CHAMPS_SECTION[nom], CHAMPS_SECTION[nom], nom, section.ligne, icones)
    if nom not in CHAMPS_ENTREE_REQUIS:
        if section.entrees:
            sortie.append(erreur(section.entrees[0].ligne, nom, "entrées (###) ignorées par le rendu dans cette section"))
        if nom == SECTION_PROFIL:
            sortie.extend(valider_profil(section))
        return sortie
    if not section.entrees:
        sortie.append(erreur(section.ligne, nom, "aucune entrée (###)"))
    titres = {}
    for entree in section.entrees:
        if entree.titre in titres:
            sortie.append(erreur(entree.ligne, nom, f"entrée « {entree.titre} » en double (première ligne {titres[entree.titre]})"))
        titres.setdefault(entree.titre, entree.ligne)
        sortie.extend(valider_entree(section, entree, icones))
    return sortie


def valider_profil(section):
    texte = section.champs.get(TEXTE)
    if not texte:
        return []
    ligne = section.lignes_champs[TEXTE]
    sortie = []
    if not LONGUEUR_PROFIL_MIN <= len(texte) <= LONGUEUR_PROFIL_MAX:
        sortie.append(avertissement(ligne, SECTION_PROFIL, f"« {TEXTE} » de {len(texte)} caractères (attendu de {LONGUEUR_PROFIL_MIN} à {LONGUEUR_PROFIL_MAX})"))
    for acronyme in acronymes_non_developpes(texte):
        sortie.append(avertissement(ligne, SECTION_PROFIL, f"acronyme « {acronyme} » sans forme développée"))
    return sortie


def valider_espaces(texte):
    return [
        avertissement(numero, "", "espaces superflus en fin de ligne")
        for numero, ligne in enumerate(texte.splitlines(), 1)
        if ligne != ligne.rstrip()
    ]


def valider(texte, icones):
    consignees = []
    try:
        front, sections = decouper(texte, consignees)
    except ErreurContenu as fatale:
        return [erreur(LIGNE_FRONT, "", str(fatale))]
    anomalies = [erreur(ligne, contexte, message) for ligne, contexte, message in consignees]
    anomalies += valider_front(front)
    anomalies += valider_ordre(sections)
    for section in sections:
        if section.nom in SECTIONS:
            anomalies += valider_section(section, icones)
    anomalies += valider_espaces(texte)
    return sorted(anomalies, key=lambda a: a.ligne)


def compter(anomalies, niveau):
    return sum(1 for a in anomalies if a.niveau == niveau)


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--source", type=Path, required=True, help="fichier markdown des données")
    arguments = analyseur.parse_args()
    try:
        anomalies = valider(arguments.source.read_text(encoding="utf-8"), icones_du_gabarit(GABARIT))
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
