import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import agent


class TestsObjectif(unittest.TestCase):
    def test_comprehension_structuree_sources_autorisees(self):
        decision = {'demande_image': True, 'plan': 'entrepot.png', 'stock': 'inventaire.csv', 'question_clarification': ''}
        with patch('agent.modele_ollama', return_value={'content': json.dumps(decision)}) as modele:
            resultat = agent.planifier_demande('Visualise le remplissage', [], ['entrepot.png', 'inventaire.csv'], 'test')
        self.assertEqual(resultat['objectif'], 'annotation')
        self.assertIn('schema', modele.call_args.kwargs)
        decision['plan'] = '../secret.png'
        with patch('agent.modele_ollama', return_value={'content': json.dumps(decision)}):
            with self.assertRaises(ValueError):
                agent.planifier_demande('Visualise', [], ['entrepot.png'], 'test')

    def test_annotation_ne_peut_devenir_resume_textuel(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            dossier = racine / 'documents'
            dossier.mkdir()
            (racine / 'annotations').mkdir()
            (racine / 'annotations' / 'test.png').write_bytes(b'test')
            resultat = {'annotation': 'test.png', 'source_stock': 'stock.csv', 'elements': [{'taux_remplissage': 70}]}
            with patch('agent.executer_outil', side_effect=[{'documents': ['plan.png', 'stock.csv']}, resultat]) as outil:
                trace = agent.lancer(lambda m: self.fail('Aucune synthèse libre ne doit remplacer le résultat'),
                    'Affiche le remplissage sur le plan', dossier, bavard=False,
                    planifier=lambda q,h,d: {'objectif':'annotation','plan':'plan.png','stock':'stock.csv'})
            self.assertEqual(trace[-1]['type'], 'reponse_finale')
            self.assertIn('1/1', trace[-1]['texte'])
            self.assertEqual(outil.call_args.args[1]['fichier_stock'], 'stock.csv')

    def test_image_absente_pas_de_fausse_reussite(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('agent.executer_outil', side_effect=[{'documents':['plan.png']}, {'annotation':'absente.png'}]):
                trace = agent.lancer(lambda m: {}, 'Dessine le plan', Path(tmp), bavard=False,
                    planifier=lambda q,h,d: {'objectif':'annotation','plan':'plan.png','stock':''})
            self.assertEqual(trace[-1]['type'], 'erreur')

    def test_discussion_conserve_boucle_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = agent.lancer(lambda m: {'role':'assistant','content':'Bonjour'}, 'Bonjour', Path(tmp), bavard=False,
                planifier=lambda q,h,d: {'objectif':'discussion','plan':'','stock':''})
            self.assertEqual(trace[-1]['texte'], 'Bonjour')

    def test_clarification_sans_annotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = agent.lancer(lambda m: self.fail(), 'Dessine', Path(tmp), bavard=False,
                planifier=lambda q,h,d: {'objectif':'clarification','plan':'','stock':'','question_clarification':'Quel plan ?'})
            self.assertEqual(trace[-1]['texte'], 'Quel plan ?')


if __name__ == '__main__':
    unittest.main()
