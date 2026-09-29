import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import agent
import vision
from skills import executer_outil


class TestsVision(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = b'\x89PNG\r\n\x1a\n' + b'test'
        (self.root / 'test.png').write_bytes(self.data)

    def client(self, resultat):
        client = MagicMock()
        client.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(resultat).encode())
        return client

    def test_transport_et_boucle(self):
        client = self.client({'message': {'content': 'Total visible : 73,90 EUR.'}})
        decisions = iter([agent.appel('analyser_image', nom='test.png', question='Quel total ?'),
                          {'role': 'assistant', 'content': '73,90 EUR selon test.png.'}])
        with patch('vision.urllib.request.build_opener', return_value=client):
            trace = agent.lancer(lambda m: next(decisions), 'Total ?', self.root, bavard=False, modele_vision='vision-test')
        corps = json.loads(client.open.call_args.args[0].data)
        self.assertEqual(corps['model'], 'vision-test')
        self.assertEqual(base64.b64decode(corps['messages'][-1]['images'][0]), self.data)
        self.assertNotIn('tools', corps)
        self.assertEqual(trace[-1]['type'], 'reponse_finale')
        self.assertEqual(trace[0]['resultat']['source'], 'test.png')
        self.assertNotIn(base64.b64encode(self.data).decode(), json.dumps(trace))

    def test_controles_avant_appel(self):
        (self.root / 'faux.png').write_text('pas une image')
        with patch('vision.urllib.request.build_opener') as reseau:
            for nom, question in [('../test.png', 'Lire'), ('faux.png', 'Lire'), ('test.png', ''), ('test.pdf', 'Lire')]:
                self.assertIn('erreur', executer_outil('analyser_image', {'nom': nom, 'question': question}, self.root))
            reseau.assert_not_called()

    def test_reponses_inexploitables(self):
        for resultat in [{'done_reason': 'length', 'message': {'content': 'Partiel'}}, {'message': {'content': ''}}]:
            with patch('vision.urllib.request.build_opener', return_value=self.client(resultat)):
                with self.assertRaises(ValueError):
                    vision.analyser_image(self.root, 'test.png', 'Lire')

    def test_modele_absent(self):
        client = MagicMock()
        client.open.side_effect = vision.urllib.error.HTTPError('local', 404, 'absent', {}, None)
        with patch('vision.urllib.request.build_opener', return_value=client):
            resultat = executer_outil('analyser_image', {'nom': 'test.png', 'question': 'Lire'}, self.root)
        self.assertIn('ollama pull', resultat['erreur'])

    def test_liste_images(self):
        (self.root / 'autre.pdf').write_bytes(b'pdf')
        self.assertEqual(executer_outil('lister_documents', {}, self.root)['documents'], ['test.png'])


if __name__ == '__main__':
    unittest.main()
