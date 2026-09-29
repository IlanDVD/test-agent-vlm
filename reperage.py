"""Localisation expérimentale des pictogrammes et création d'une copie annotée."""
import io
import json
import uuid
from pathlib import Path
from vision import lire_image, appeler_vision

BOITE = {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4}


def objet(proprietes):
    return {"type": "object", "properties": proprietes, "required": list(proprietes), "additionalProperties": False}


SCHEMA = objet({
    "legende": {"type": "array", "maxItems": 12, "items": objet({
        "label": {"type": "string"},
        "symbole_id": {"type": "integer"},
        "quantite_par_symbole": {"type": ["integer", "null"]}})},
    "incertitudes": {"type": "string"}})


def candidats_colores(image):
    """Composantes connexes colorées ; adapté aux icônes vives sur fond clair."""
    petite = image.copy()
    petite.thumbnail((768, 768))
    w, h = petite.size
    pixels = list(petite.getdata())
    masque = bytearray(int(max(p) > 140 and max(p)-min(p) > 70) for p in pixels)
    candidats = []
    sx, sy = image.width/w, image.height/h
    for debut in range(w*h):
        if not masque[debut]:
            continue
        masque[debut] = 0
        file = [debut]
        xs, ys, couleurs = [], [], []
        while file:
            n = file.pop()
            x, y = n % w, n // w
            xs.append(x); ys.append(y); couleurs.append(pixels[n])
            for voisin in (n-1 if x else -1, n+1 if x<w-1 else -1, n-w, n+w):
                if 0 <= voisin < len(masque) and masque[voisin]:
                    masque[voisin] = 0
                    file.append(voisin)
        if len(xs) < 100 or max(xs)-min(xs) > w/4 or max(ys)-min(ys) > h/3:
            continue
        bbox = [max(0, int(min(xs)*sx)-10), max(0, int(min(ys)*sy)-12),
                min(image.width, int((max(xs)+1)*sx)+10), min(image.height, int((max(ys)+1)*sy)+4)]
        candidats.append({"bbox": bbox, "couleur": [sum(c[k] for c in couleurs)/len(couleurs) for k in range(3)]})
    if not 2 <= len(candidats) <= 100:
        raise ValueError("Ce mode attend entre 2 et 100 pictogrammes colorés distincts sur fond clair.")
    for i, candidat in enumerate(candidats, 1):
        candidat["id"] = i
    return candidats


def associer(lecture, candidats):
    legende = lecture.get("legende", [])
    if not isinstance(legende, list) or not 1 <= len(legende) <= 12:
        raise ValueError("Aucune légende exploitable détectée.")
    par_id = {c["id"]: c for c in candidats}
    prototypes = []
    for entree in legende:
        identifiant = entree.get("symbole_id")
        if type(identifiant) is not int or identifiant not in par_id:
            raise ValueError("Le symbole de légende choisi par le VLM est invalide.")
        if any(p[0]["id"] == identifiant for p in prototypes):
            raise ValueError("Le VLM a associé deux labels au même symbole de légende.")
        prototypes.append((par_id[identifiant], entree))
    def distance(a, b):
        return sum((x-y)**2 for x, y in zip(a["couleur"], b["couleur"]))**.5
    if any(distance(a[0], b[0]) < 70 for i, a in enumerate(prototypes) for b in prototypes[i+1:]):
        raise ValueError("Les catégories ont des couleurs trop proches pour ce mode de repérage.")
    boites = [p[0]["bbox"] for p in prototypes]
    region = [min(b[0] for b in boites), min(b[1] for b in boites), max(b[2] for b in boites), max(b[3] for b in boites)]
    elements, ignores = [], 0
    for candidat in candidats:
        if intersection(candidat["bbox"], region):
            continue
        prototype, entree = min(prototypes, key=lambda p: distance(candidat, p[0]))
        if distance(candidat, prototype) > 65:
            ignores += 1
            continue
        elements.append({"label": entree["label"], "repere": "P"+str(candidat["id"]), "bbox": candidat["bbox"]})
    return {"legende_bbox": region, "legende": legende, "elements": elements,
            "incertitudes": str(lecture.get("incertitudes", "")), "candidats_non_classes": ignores}


def boite(valeur, largeur, hauteur):
    if (not isinstance(valeur, list) or len(valeur) != 4 or
            any(type(v) is not int for v in valeur)):
        raise ValueError("Coordonnées invalides : quatre entiers attendus.")
    x1, y1, x2, y2 = valeur
    if not (0 <= x1 < x2 <= largeur and 0 <= y1 < y2 <= hauteur):
        raise ValueError("Encadrement hors image ou inversé. Relancez le repérage.")
    return valeur


def intersection(a, b):
    return max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))


def valider(resultat, largeur, hauteur):
    if not isinstance(resultat, dict):
        raise ValueError("Repérage invalide.")
    region = boite(resultat.get("legende_bbox"), largeur, hauteur)
    legende = resultat.get("legende")
    elements = resultat.get("elements")
    if not isinstance(legende, list) or not 1 <= len(legende) <= 12:
        raise ValueError("Aucune légende exploitable détectée.")
    labels = {}
    for entree in legende:
        if not isinstance(entree, dict):
            raise ValueError("Entrée de légende invalide.")
        label, quantite = entree.get("label"), entree.get("quantite_par_symbole")
        if not isinstance(label, str) or not label.strip() or len(label) > 80 or label in labels:
            raise ValueError("Label de légende vide, trop long ou dupliqué.")
        if quantite is not None and (type(quantite) is not int or not 1 <= quantite <= 1000000):
            raise ValueError("Quantité de légende invalide.")
        labels[label] = quantite
    if not isinstance(elements, list) or len(elements) > 100:
        raise ValueError("Liste de pictogrammes invalide (100 maximum).")
    propres, rejetes = [], 0
    for element in elements:
        if not isinstance(element, dict) or element.get("label") not in labels:
            raise ValueError("Pictogramme sans label correspondant dans la légende.")
        b = boite(element.get("bbox"), largeur, hauteur)
        repere = element.get("repere")
        if not isinstance(repere, str) or len(repere) > 40:
            raise ValueError("Repère invalide.")
        # Ne pas compter les exemplaires de la légende ni deux fois la même boîte.
        if intersection(b, region):
            rejetes += 1
            continue
        if any(intersection(b, e["bbox"]) / max(1, min(
                (b[2]-b[0])*(b[3]-b[1]),
                (e["bbox"][2]-e["bbox"][0])*(e["bbox"][3]-e["bbox"][1]))) > .8 for e in propres):
            rejetes += 1
            continue
        propres.append({"label": element["label"], "repere": repere, "bbox": b})
    if not propres:
        raise ValueError("Aucun pictogramme localisé hors légende ; aucune image annotée produite.")
    return region, legende, propres, rejetes


def reperer_pictogrammes(dossier, nom, modele="qwen2.5vl:3b", fichier_stock=None):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as erreur:
        raise ValueError("Installez Pillow avec : python -m pip install -r requirements.txt") from erreur
    from stocks import lire_stock, appliquer_stock
    if fichier_stock is None and (Path(dossier) / "stock-reel.csv").is_file():
        fichier_stock = "stock-reel.csv"
    stock = lire_stock(dossier, fichier_stock) if fichier_stock else None
    contenu = lire_image(dossier, nom)
    with Image.open(io.BytesIO(contenu)) as source:
        if source.width * source.height > 20_000_000:
            raise ValueError("Image trop grande pour le repérage (20 millions de pixels maximum).")
        image = source.convert("RGB")
    # Coordonnées définies sur une image de travail de taille connue du modèle.
    image.thumbnail((1536, 1536))
    largeur, hauteur = image.size
    candidats = candidats_colores(image)
    guide = image.copy()
    dessin_guide = ImageDraw.Draw(guide)
    police_guide = ImageFont.load_default(size=18)
    for candidat in candidats:
        x, y, _, _ = candidat["bbox"]
        etiquette = "P" + str(candidat["id"])
        dessin_guide.rectangle((x, max(0, y-22), x+48, y), fill="white", outline="#B00080")
        dessin_guide.text((x+2, max(0, y-22)), etiquette, fill="#B00080", font=police_guide)
    flux = io.BytesIO()
    guide.save(flux, format="PNG")
    schema = json.loads(json.dumps(SCHEMA))
    schema["properties"]["legende"]["items"]["properties"]["symbole_id"]["enum"] = [c["id"] for c in candidats]
    question = ("Lis uniquement la LÉGENDE de ce plan. Des étiquettes magenta P1, P2, etc. ont été ajoutées "
        "près des pictogrammes pour les identifier. Pour CHAQUE catégorie de la légende, donne un label court "
        "du produit en français, sa quantité par pictogramme, et symbole_id = le numéro P du pictogramme EXEMPLE "
        "situé DANS LA LÉGENDE (pas un objet du plan). Par exemple P12 donne symbole_id 12. "
        "Ne liste pas les objets du plan. Quantité null si illisible. Si aucune légende, renvoie une liste vide. "
        "Les repères N/S imprimés dans le plan ne sont pas les identifiants P ajoutés. "
        "Réponds au schéma JSON : " + json.dumps(schema, ensure_ascii=False))
    brut = appeler_vision(flux.getvalue(), question, modele, schema=schema, max_tokens=1024)
    resultat = associer(json.loads(brut), candidats)
    region, legende, elements, rejetes = valider(resultat, largeur, hauteur)
    if stock is not None:
        # Agrandir les zones de texte adjacentes sans modifier les boîtes des pictogrammes.
        tuiles = Image.new("RGB", (960, ((len(elements)+3)//4)*170), "white")
        dessin_tuiles = ImageDraw.Draw(tuiles)
        for i, element in enumerate(elements):
            x1, y1, x2, y2 = element["bbox"]
            extrait = image.crop((max(0,x1-2), max(0,y1-2), min(largeur,x2+100), min(hauteur,y2+3)))
            extrait.thumbnail((230, 135))
            tx, ty = (i%4)*240, (i//4)*170
            tuiles.paste(extrait, (tx, ty+28))
            dessin_tuiles.text((tx+5, ty+3), element["repere"], fill="black", font=ImageFont.load_default(size=20))
        flux_tuiles = io.BytesIO()
        tuiles.save(flux_tuiles, format="PNG")
        schema_reperes = objet({"reperes": {"type": "array", "items": objet({
            "candidat": {"type": "string", "enum": [e["repere"] for e in elements]},
            "repere": {"type": "string"}})}})
        lecture_reperes = json.loads(appeler_vision(flux_tuiles.getvalue(),
            "Chaque tuile montre un pictogramme et son identifiant imprimé à droite. "
            "Le titre P est l'identifiant temporaire du candidat. Pour chaque candidat, transcris "
            "EXACTEMENT l'identifiant noir visible à droite (exemple N7 ou S3). "
            "Ne déduis aucun numéro depuis l'ordre des tuiles. Si illisible, repere doit être vide. "
            "Renvoie tous les candidats une seule fois. Schéma : " + json.dumps(schema_reperes),
            modele, schema=schema_reperes, max_tokens=2048))
        appliquer_stock(elements, legende, lecture_reperes.get("reperes", []), stock)
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#6A3D9A", "#7A5900"]
    couleurs = {e["label"]: palette[i % len(palette)] for i, e in enumerate(legende)}
    dessin = ImageDraw.Draw(image)
    police = ImageFont.load_default(size=16)
    for e in elements:
        x1, y1, x2, y2 = e["bbox"]
        couleur = couleurs[e["label"]]
        dessin.rectangle(e["bbox"], outline=couleur, width=4)
        if stock is not None:
            taux = e["taux_remplissage"]
            pourcentage = "indisponible" if taux is None else f"{taux:g} %"
            texte = (e["repere"] or e["candidat"]) + " : " + pourcentage
        else:
            texte = (e["repere"] + " · " if e["repere"] else "") + e["label"]
        limites = dessin.textbbox((0, 0), texte, font=police)
        w, h = limites[2]+8, limites[3]+6
        x, y = min(x1, max(0, largeur-w)), max(0, y1-h)
        dessin.rectangle((x, y, x+w, y+h), fill="white", outline=couleur)
        dessin.text((x+4, y+1), texte, fill=couleur, font=police)
    bilan = [{**e, "pictogrammes": sum(x["label"] == e["label"] for x in elements)} for e in legende]
    for e in bilan:
        e["quantite_theorique"] = None if e["quantite_par_symbole"] is None else e["pictogrammes"] * e["quantite_par_symbole"]
    racine = Path(dossier).resolve().parent
    sortie = racine / "annotations"
    sortie.mkdir(exist_ok=True)
    if sortie.resolve().parent != racine:
        raise ValueError("Dossier de sortie non autorisé.")
    identifiant = uuid.uuid4().hex
    fichier = identifiant + ".png"
    image.save(sortie / fichier)
    rapport = {"source": nom, "modele": modele, "dimensions": [largeur, hauteur],
        "legende_bbox": region, "legende": bilan, "elements": elements,
        "source_stock": fichier_stock,
        "methode": "VLM pour la légende et les identifiants ; couleurs pour les positions ; calcul des taux en Python à partir du CSV",
        "candidats_non_classes": resultat.get("candidats_non_classes", 0),
        "elements_exclus": rejetes, "incertitudes": str(resultat.get("incertitudes", ""))[:2000],
        "annotation": fichier, "avertissement": ("Taux calculés depuis le CSV et les capacités lues sur le plan. Vérifier les identifiants et la légende ; aucun stock en temps réel." if stock is not None else "Repérage automatique expérimental : vérifier les cadres et les oublis. Les quantités sont théoriques, pas un stock en temps réel.")}
    (sortie / (identifiant + ".json")).write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    return rapport
