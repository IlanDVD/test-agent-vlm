import io
import json
import tempfile
import unittest
import threading
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from reperage import valider, reperer_pictogrammes, candidats_colores, associer
from chat_local import Application, Serveur


class TestsReperage(unittest.TestCase):
    def resultat(self):
        return {"legende_bbox": [150, 100, 200, 200],
            "legende": [{"label": "Carnets", "symbole_id": 2, "quantite_par_symbole": 10}],
            "elements": [{"label": "Carnets", "categorie": 0, "repere": "N1", "bbox": [10, 20, 40, 50]}],
            "incertitudes": ""}

    def test_exclusion_legende_et_doublon(self):
        r = self.resultat()
        r['elements'] += [dict(r['elements'][0]), {"label": "Carnets", "repere": "", "bbox": [160, 120, 180, 140]}]
        _, _, elements, rejetes = valider(r, 200, 200)
        self.assertEqual(len(elements), 1)
        self.assertEqual(rejetes, 2)

    def test_rejet_coordonnees_et_labels(self):
        for boite in [[-1, 0, 5, 8], [20, 20, 10, 30], [0, 0, 201, 5], [True, 2, 4, 6]]:
            r = self.resultat()
            r['elements'][0]['bbox'] = boite
            with self.assertRaises(ValueError):
                valider(r, 200, 200)
        r = self.resultat()
        r['elements'][0]['label'] = 'Inconnu'
        with self.assertRaises(ValueError):
            valider(r, 200, 200)

    def test_source_preservee_et_rapport(self):
        with tempfile.TemporaryDirectory() as tmp:
            documents = Path(tmp) / 'documents'
            documents.mkdir()
            chemin = documents / 'plan.png'
            Image.new('RGB', (200, 200), 'white').save(chemin)
            original = chemin.read_bytes()
            with patch('reperage.appeler_vision', return_value=json.dumps(self.resultat())), patch('reperage.candidats_colores', return_value=[{'id':1, 'bbox':[10,20,40,50], 'couleur':[10,150,230]}, {'id':2, 'bbox':[150,100,200,200], 'couleur':[10,150,230]}]):
                resultat = reperer_pictogrammes(documents, 'plan.png')
            self.assertEqual(chemin.read_bytes(), original)
            self.assertEqual(resultat['legende'][0]['quantite_estimee'], 10)
            fichier = Path(tmp) / 'annotations' / resultat['annotation']
            self.assertTrue(fichier.is_file())
            self.assertTrue(fichier.with_suffix('.json').is_file())
            with Image.open(fichier) as image:
                self.assertNotEqual(image.getpixel((10, 30)), (255, 255, 255))

    def test_aucune_legende_pas_de_sortie(self):
        r = self.resultat()
        r['legende'] = []
        with self.assertRaises(ValueError):
            valider(r, 200, 200)

    def test_detection_coloree_sans_coordonnees_codees(self):
        from PIL import ImageDraw
        image = Image.new('RGB', (500, 300), 'white')
        dessin = ImageDraw.Draw(image)
        for b in [(20, 30, 55, 70), (200, 130, 235, 170), (400, 220, 435, 260)]:
            dessin.rectangle(b, fill=(20, 150, 230))
        candidats = candidats_colores(image)
        self.assertEqual(len(candidats), 3)
        resultat = associer({'legende': [{'label': 'Produit test', 'symbole_id': 3, 'quantite_par_symbole': 7}]}, candidats)
        self.assertEqual(len(resultat['elements']), 2)
        self.assertTrue(all(e['label'] == 'Produit test' for e in resultat['elements']))

    def test_couleurs_ambigues_refusees(self):
        candidats = [{'id': 1, 'bbox': [0, 0, 20, 20], 'couleur': [20, 150, 230]},
                     {'id': 2, 'bbox': [30, 30, 50, 50], 'couleur': [21, 151, 231]}]
        with self.assertRaises(ValueError):
            associer({'legende': [{'label': 'A', 'symbole_id': 1}, {'label': 'B', 'symbole_id': 2}]}, candidats)

    def test_http_annotations_et_chemins(self):
        with tempfile.TemporaryDirectory() as tmp, patch('chat_local.BASE', Path(tmp)):
            root = Path(tmp)
            (root / 'annotations').mkdir()
            nom = 'a' * 32 + '.png'
            Image.new('RGB', (20, 20)).save(root / 'annotations' / nom)
            serveur = Serveur(('127.0.0.1', 0), Application(root / 'conversations'))
            threading.Thread(target=serveur.serve_forever, daemon=True).start()
            client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            base = 'http://127.0.0.1:' + str(serveur.server_address[1])
            try:
                with client.open(base + '/annotations/' + nom) as reponse:
                    self.assertEqual(reponse.headers['Content-Type'], 'image/png')
                    self.assertTrue(reponse.read().startswith(b'\x89PNG'))
                for chemin in ['../vision.py', '%2e%2e/vision.py', 'autre.png']:
                    with self.assertRaises(urllib.error.HTTPError) as erreur:
                        client.open(base + '/annotations/' + chemin)
                    self.assertEqual(erreur.exception.code, 404)
            finally:
                serveur.shutdown()
                serveur.server_close()


if __name__ == '__main__':
    unittest.main()
