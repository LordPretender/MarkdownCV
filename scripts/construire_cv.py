"""Génère le site (index.html + fichiers statiques) à partir d'un fichier markdown de données et du gabarit src/index.html."""

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

from lecture_cv import (
    BLOC_ENVIRONNEMENT,
    CHAMPS_FRONT,
    CONTEXTE,
    ENTREPRISE,
    ETABLISSEMENT,
    ICONE,
    INTRO,
    LIEU,
    LOGO,
    MARQUEUR_PUCE,
    NIVEAU,
    PERIODE,
    PERIODE_DETAIL,
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
    identifiant,
)

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_GABARIT = "src"
FICHIER_GABARIT = "index.html"
FICHIER_FAVICON = "favicon.svg"
DOSSIER_BUILD = "build"
PREFIXE_DETAIL_EXPERIENCE = "d-"
PREFIXE_DETAIL_PROJET = "p-"
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


def liste_chips(items):
    return '<ul class="chips">' + "".join(f'<li class="chip">{echapper(i)}</li>' for i in items) + "</ul>"


def rendre_bloc(bloc, contexte):
    if not bloc.lignes:
        raise ErreurContenu(f"{contexte} : bloc « {bloc.nom} » vide")
    puces = all(ligne.startswith(MARQUEUR_PUCE) for ligne in bloc.lignes)
    if not puces and any(ligne.startswith(MARQUEUR_PUCE) for ligne in bloc.lignes):
        raise ErreurContenu(f"{contexte} : bloc « {bloc.nom} » mêle texte et puces")
    items = [ligne[len(MARQUEUR_PUCE):] for ligne in bloc.lignes] if puces else []

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


def rendre_carte_detail(id_detail, logo, titre, sous_titre, chips):
    pastilles = "".join(f'<span class="chip">{echapper(c)}</span>' for c in chips)
    return [
        f'<li><button class="card" type="button" data-detail="{id_detail}">',
        f'  <span class="logo">{echapper(logo)}</span>',
        f'  <span class="card-body"><span class="card-title">{echapper(titre)}</span>'
        f'<span class="card-sub">{echapper(sous_titre)}</span></span>',
        f'  <span class="chips">{pastilles}</span>',
        "</button></li>",
    ]


def rendre_experience(section):
    cartes, details = [], []
    for rang, entree in enumerate(section.entrees, 1):
        contexte = f"{SECTION_EXPERIENCE} / {entree.titre}"
        c = entree.champs
        entreprise, lieu = champ(c, ENTREPRISE, contexte), champ(c, LIEU, contexte)
        periode, logo = champ(c, PERIODE, contexte), champ(c, LOGO, contexte)
        id_detail = f"{PREFIXE_DETAIL_EXPERIENCE}{rang}"
        cartes += rendre_carte_detail(id_detail, logo, entree.titre, entreprise, [periode, lieu])
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
        cartes += rendre_carte_detail(id_detail, logo, entree.titre, contexte_projet, [periode])
        details += rendre_detail(
            id_detail,
            c.get(TITRE_DETAIL) or entree.titre,
            f"{contexte_projet} · {c.get(PERIODE_DETAIL) or periode}",
            logo,
            entree,
            contexte,
        )
    return cartes, details


def rendre_competences(section, icones):
    lignes = []
    for entree in section.entrees:
        contexte = f"{SECTION_COMPETENCES} / {entree.titre}"
        icone = verifier_icone(champ(entree.champs, ICONE, contexte), contexte, icones)
        if not entree.puces:
            raise ErreurContenu(f"{contexte} : aucune compétence listée")
        lignes += [
            f'<li class="skill"><h3><svg class="ico"><use href="#i-{icone}"/></svg>{echapper(entree.titre)}</h3>',
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
        if not url.startswith(("https://", "http://")):
            raise ErreurContenu(f"{contexte} : « {URL} » doit commencer par http:// ou https://")
        lignes.append(
            f'<li><a class="card" href="{echapper(url)}">'
            f'<span class="logo dark">{echapper(champ(entree.champs, LOGO, contexte))}</span>'
            f'<span class="card-title">{echapper(entree.titre)}</span>'
            f'<svg class="arrow"><use href="#i-arrow"/></svg></a></li>'
        )
    return lignes


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


def preparer(front, sections, icones):
    for cle in CHAMPS_FRONT:
        champ(front, cle, "front-matter")
    par_nom = indexer_sections(sections)

    valeurs = dict(front)
    accueil = par_nom[SECTION_ACCUEIL].champs
    valeurs[CLE_ACCUEIL_STATUT] = champ(accueil, STATUT, SECTION_ACCUEIL)
    valeurs[CLE_ACCUEIL_SOUS_TITRE] = champ(accueil, SOUS_TITRE, SECTION_ACCUEIL)

    nav = []
    for nom in SECTIONS:
        section = par_nom[nom]
        icone = verifier_icone(champ(section.champs, ICONE, nom), nom, icones)
        nav.append(
            f'<a href="#{identifiant(nom)}" data-label="{echapper(nom)}" aria-label="{echapper(nom)}">'
            f'<svg class="ico"><use href="#i-{icone}"/></svg></a>'
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

    cartes_experience, details_experience = rendre_experience(par_nom[SECTION_EXPERIENCE])
    cartes_projets, details_projets = rendre_projets(par_nom[SECTION_PROJETS])
    fragments = {
        FRAGMENT_NAV: nav,
        identifiant(SECTION_EXPERIENCE): cartes_experience,
        identifiant(SECTION_COMPETENCES): rendre_competences(par_nom[SECTION_COMPETENCES], icones),
        identifiant(SECTION_PROJETS): cartes_projets,
        identifiant(SECTION_DIPLOMES): rendre_diplomes(par_nom[SECTION_DIPLOMES]),
        identifiant(SECTION_LANGUES): rendre_langues(par_nom[SECTION_LANGUES]),
        identifiant(SECTION_LIENS): rendre_liens(par_nom[SECTION_LIENS]),
        FRAGMENT_DETAILS: details_experience + details_projets,
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


def rendre_gabarit(gabarit, destination, valeurs, fragments):
    texte = appliquer(gabarit.read_text(encoding="utf-8"), valeurs, fragments)
    destination.write_bytes(texte.encode("utf-8"))


def construire(source, destination):
    dossier_gabarit = RACINE / DOSSIER_GABARIT
    gabarit = (dossier_gabarit / FICHIER_GABARIT).read_text(encoding="utf-8")
    icones = set(re.findall(r'<symbol id="i-([\w-]+)"', gabarit))

    front, sections = decouper(source.read_text(encoding="utf-8"))
    valeurs, fragments = preparer(front, sections, icones)

    destination.mkdir(parents=True, exist_ok=True)
    rendre_gabarit(dossier_gabarit / FICHIER_GABARIT, destination / FICHIER_GABARIT, valeurs, fragments)
    rendre_gabarit(dossier_gabarit / FICHIER_FAVICON, destination / FICHIER_FAVICON, valeurs, {})
    for fichier in dossier_gabarit.iterdir():
        if fichier.is_file() and fichier.name not in (FICHIER_GABARIT, FICHIER_FAVICON):
            shutil.copy2(fichier, destination / fichier.name)


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--source", type=Path, required=True, help="fichier markdown des données")
    analyseur.add_argument("--destination", type=Path, default=RACINE / DOSSIER_BUILD, help="dossier de sortie")
    arguments = analyseur.parse_args()
    try:
        construire(arguments.source, arguments.destination)
    except (ErreurContenu, OSError) as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    print(f"Site généré dans {arguments.destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
