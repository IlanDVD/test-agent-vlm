"""Tests fonctionnels du chat, sans appels au modèle réel."""
import json
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from chat_local import Application, Serveur


class TestsChat(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.historiques = []
        def decider(messages):
            self.historiques.append(messages.copy())
            return {"role": "assistant", "content": "Réponse de test."}
        self.app = Application(Path(self.temp.name), decider=decider)

    def attendre(self, application=None):
        app = application or self.app
        for _ in range(100):
            if not app.calcul.locked():
                return
            time.sleep(.02)
        self.fail("Le traitement ne s'est pas terminé.")

    def test_contexte_et_persistance(self):
        session = self.app.nouvelle()
        self.app.envoyer(session["id"], "Le prix d'un carnet ?")
        self.attendre()
        self.app.envoyer(session["id"], "Et deux ?")
        self.attendre()
        self.assertEqual([m["role"] for m in self.historiques[-1]], ["system", "user", "assistant", "user"])
        self.assertEqual(self.historiques[-1][1]["content"], "Le prix d'un carnet ?")
        reprise = Application(Path(self.temp.name)).instantane(session["id"])
        self.assertEqual(len(reprise["tours"]), 2)
        self.assertEqual(reprise["tours"][-1]["statut"], "termine")

    def test_nouvelle_conversation_isolee(self):
        premiere = self.app.nouvelle()
        self.app.envoyer(premiere["id"], "Ancienne question")
        self.attendre()
        seconde = self.app.nouvelle()
        self.app.envoyer(seconde["id"], "Nouvelle question")
        self.attendre()
        self.assertEqual(len(self.historiques[-1]), 2)

    def test_echec_exclu_du_contexte(self):
        self.app.decider = lambda m: {"role": "assistant", "content": ""}
        session = self.app.nouvelle()
        self.app.envoyer(session["id"], "Question échouée")
        self.attendre()
        self.assertEqual(session["tours"][0]["statut"], "erreur")
        def decider(messages):
            self.assertEqual(len(messages), 2)
            return {"role": "assistant", "content": "OK"}
        self.app.decider = decider
        self.app.envoyer(session["id"], "Réessayer")
        self.attendre()
        self.assertEqual(session["tours"][-1]["statut"], "termine")

    def test_traitement_unique(self):
        porte = threading.Event()
        self.addCleanup(porte.set)
        self.app.decider = lambda m: (porte.wait(3) or True) and {"role": "assistant", "content": "OK"}
        session = self.app.nouvelle()
        self.app.envoyer(session["id"], "Première question")
        with self.assertRaises(BlockingIOError):
            self.app.envoyer(session["id"], "Deuxième question")
        porte.set()
        self.attendre()

    def test_session_interrompue_au_redemarrage(self):
        session = self.app.nouvelle()
        session["tours"] = [{"statut": "en_cours"}]
        self.app.sauver(session)
        reprise = Application(Path(self.temp.name)).instantane(session["id"])
        self.assertEqual(reprise["tours"][0]["statut"], "erreur")

    def test_http_et_acces_local(self):
        serveur = Serveur(("127.0.0.1", 0), self.app)
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        self.addCleanup(serveur.server_close)
        self.addCleanup(serveur.shutdown)
        base = "http://127.0.0.1:" + str(serveur.server_address[1])
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with client.open(base) as reponse:
            self.assertIn("Mon agent", reponse.read().decode())
            self.assertIn("frame-ancestors 'none'", reponse.headers["Content-Security-Policy"])
        for path, headers in [("/api/session", {}), ("/api/session", {"X-Chat-Token": self.app.token, "Origin": "https://exemple.invalid"})]:
            req = urllib.request.Request(base+path, data=b"{}", headers={"Content-Type": "application/json", **headers})
            with self.assertRaises(urllib.error.HTTPError) as erreur:
                client.open(req)
            self.assertEqual(erreur.exception.code, 403)
        req = urllib.request.Request(base+"/api/session", data=b"{}", headers={"Content-Type":"application/json", "X-Chat-Token": self.app.token})
        with client.open(req) as reponse:
            identifiant = json.load(reponse)["id"]
        req = urllib.request.Request(base+"/api/chat", data=json.dumps({"session":identifiant,"question":"Bonjour"}).encode(), headers={"Content-Type":"application/json", "X-Chat-Token": self.app.token})
        with client.open(req) as reponse:
            self.assertEqual(reponse.status, 202)
        self.attendre()
        with client.open(base+"/api/session/"+identifiant) as reponse:
            self.assertEqual(json.load(reponse)["tours"][0]["reponse"], "Réponse de test.")
        with self.assertRaises(urllib.error.HTTPError) as erreur:
            client.open(base+"/../agent.py")
        self.assertEqual(erreur.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
