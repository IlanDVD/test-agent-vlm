"""Lecture de l'inventaire et calculs déterministes, indépendants du modèle."""
import csv
import io
import re
import unicodedata
from collections import Counter


def lire_stock(dossier, nom):
    if not isinstance(nom, str) or not nom or any(c in nom for c in '/\\:'):
        raise ValueError("Nom de CSV invalide.")
    racine = dossier.resolve()
    chemin = (racine / nom).resolve()
    if chemin.parent != racine or chemin.suffix.lower() != '.csv':
        raise ValueError("Le stock doit être un CSV du dossier documents.")
    with chemin.open('rb') as fichier:
        contenu = fichier.read(12001)
    if len(contenu) > 12000:
        raise ValueError("CSV de stock trop volumineux.")
    lecteur = csv.DictReader(io.StringIO(contenu.decode('utf-8-sig')))
    if lecteur.fieldnames != ['numero', 'quantite', 'type_objet']:
        raise ValueError("Colonnes attendues : numero,quantite,type_objet.")
    lignes = {}
    for ligne in lecteur:
        if None in ligne or any(v is None for v in ligne.values()):
            raise ValueError("Ligne CSV incomplète ou mal formée.")
        numero = ligne['numero'].strip().upper()
        quantite = ligne['quantite'].strip()
        if not re.fullmatch(r'[A-Z]+[0-9]+', numero) or numero in lignes:
            raise ValueError("Identifiant de stock invalide ou dupliqué.")
        if not re.fullmatch(r'[0-9]+', quantite) or not ligne['type_objet'].strip():
            raise ValueError("Quantité ou type d'objet invalide dans le CSV.")
        lignes[numero] = {'quantite': int(quantite), 'type_objet': ligne['type_objet'].strip()}
    if not lignes:
        raise ValueError("CSV de stock vide.")
    return lignes


def appliquer_stock(elements, legende, lectures, stock):
    capacites = {e['label']: e['quantite_par_symbole'] for e in legende}
    correspondances = {}
    for lecture in lectures:
        candidat = lecture.get('candidat')
        repere = lecture.get('repere')
        if candidat in correspondances or not isinstance(repere, str):
            raise ValueError("Lecture des identifiants incohérente.")
        correspondances[candidat] = repere.strip().upper()
    comptes = Counter(correspondances.values())
    for element in elements:
        candidat = element['repere']
        repere = correspondances.get(candidat, '')
        element.update(candidat=candidat, repere=repere, quantite_reelle=None,
                       capacite=capacites[element['label']], taux_remplissage=None)
        if not repere or comptes[repere] != 1:
            element['statut_stock'] = 'identifiant illisible ou dupliqué'
        elif repere not in stock:
            element['statut_stock'] = 'absent du CSV'
        elif not element['capacite']:
            element['statut_stock'] = 'capacité illisible'
        elif normaliser_type(element['label']) != normaliser_type(stock[repere]['type_objet']):
            element['statut_stock'] = "type du CSV différent du pictogramme"
        else:
            element['quantite_reelle'] = stock[repere]['quantite']
            element['type_objet_csv'] = stock[repere]['type_objet']
            element['taux_remplissage'] = round(100 * element['quantite_reelle'] / element['capacite'], 1)
            element['statut_stock'] = 'dépassement de capacité' if element['taux_remplissage'] > 100 else 'calculé'
    return elements


def normaliser_type(texte):
    texte = ''.join(c for c in unicodedata.normalize('NFD', texte.lower()) if not unicodedata.combining(c))
    return ' '.join(mot.rstrip('s') for mot in re.findall(r'[a-z]+', texte))
