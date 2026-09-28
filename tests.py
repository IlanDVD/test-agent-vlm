"""Tests sans IA ni réseau : python -m unittest -v tests."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agent


class TestsAgent(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dossier = Path(self.temp.name) / "documents"
        self.dossier.mkdir()
        (self.dossier / "livraison.txt").write_text("Délai : 8 jours, exemple modifié.", encoding="utf-8")
        (Path(self.temp.name) / "secret.txt").write_text("NE PAS LIRE", encoding="utf-8")

    def lancer(self, decider, limite=10):
        with contextlib.redirect_stdout(io.StringIO()):
            return agent.lancer(decider, agent.QUESTION, self.dossier, limite)

    def test_demo_utilise_le_vrai_contenu(self):
        trace = self.lancer(agent.modele_simule)
        self.assertEqual([e["type"] for e in trace], ["outil", "outil", "reponse_finale"])
        self.assertIn("8 jours", trace[-1]["texte"])

    def test_recuperation_apres_erreur(self):
        trace = self.lancer(lambda m: agent.modele_simule(m, True))
        self.assertIn("erreur", trace[1]["resultat"])
        self.assertIn("8 jours", trace[-1]["texte"])

    def test_document_absent(self):
        (self.dossier / "livraison.txt").unlink()
        trace = self.lancer(agent.modele_simule)
        self.assertIn("manque", trace[-1]["texte"])

    def test_limite(self):
        trace = self.lancer(lambda m: agent.appel("lister_documents"), limite=2)
        self.assertEqual(trace[-1]["type"], "limite_atteinte")
        self.assertEqual(sum(e["type"] == "outil" for e in trace), 2)

    def test_controle_des_outils_et_parametres(self):
        for nom, args in [("terminal", {}), ("lister_documents", {"x": 1}),
                          ("lire_document", {"nom": "../secret.txt"}),
                          ("lire_document", {"nom": "..\\secret.txt"}),
                          ("lire_document", {"nom": "C:\\secret.txt"}),
                          ("lire_document", {"nom": "livraison.txt", "x": 1}),
                          ("lire_document", {"nom": 2}), ("lire_document", [])]:
            with self.subTest(nom=nom, args=args):
                resultat = agent.executer_outil(nom, args, self.dossier)
                self.assertIn("erreur", resultat)
                self.assertNotIn("NE PAS LIRE", json.dumps(resultat))

    def test_document_trop_long(self):
        (self.dossier / "grand.txt").write_text("x" * 12001, encoding="utf-8")
        self.assertIn("erreur", agent.executer_outil("lire_document", {"nom": "grand.txt"}, self.dossier))

    def test_observations_reviennent_au_decideur(self):
        def decider(messages):
            if messages[-1]["role"] == "user":
                return agent.appel("lister_documents")
            self.assertEqual(messages[-1]["role"], "tool")
            self.assertIn("livraison.txt", json.loads(messages[-1]["content"])["documents"])
            return {"role": "assistant", "content": "Reçu"}
        self.assertEqual(self.lancer(decider)[-1]["texte"], "Reçu")

    def test_reponse_vide_signalee(self):
        trace = self.lancer(lambda m: {"role": "assistant", "content": ""})
        self.assertEqual(trace[-1]["type"], "erreur")

    def test_adaptateur_ollama_avec_transport_simule(self):
        class ClientSimule:
            def open(interne, requete, timeout):
                charge = json.loads(requete.data)
                self.assertEqual(charge["model"], "modele-test")
                self.assertFalse(charge["stream"])
                self.assertNotIn("think", charge)
                self.assertEqual(charge["options"]["num_predict"], 8192)
                self.assertEqual(charge["tools"], agent.OUTILS)
                self.assertEqual(timeout, 300)
                return io.BytesIO(json.dumps({"message": {"role": "assistant", "content": "OK"}}).encode())
        with patch("agent.urllib.request.build_opener", return_value=ClientSimule()):
            self.assertEqual(agent.modele_ollama([], "modele-test")["content"], "OK")

    def test_deux_documents_successifs(self):
        (self.dossier / "produits.txt").write_text("Carnet : 12 EUR", encoding="utf-8")
        def decider(messages):
            observations = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
            if len(observations) == 0:
                return agent.appel("lire_document", nom="produits.txt")
            if len(observations) == 1:
                return agent.appel("lire_document", nom="livraison.txt")
            self.assertEqual([o["source"] for o in observations], ["produits.txt", "livraison.txt"])
            return {"role": "assistant", "content": "Deux sources reçues."}
        self.assertEqual(self.lancer(decider)[-1]["texte"], "Deux sources reçues.")

    def test_budget_personnalise_sans_modifier_historique(self):
        messages = [{"role": "user", "content": "Question"}]
        class ClientSimule:
            def open(interne, requete, timeout):
                charge = json.loads(requete.data)
                self.assertEqual(charge["options"]["num_predict"], 12000)
                self.assertEqual(charge["messages"][0]["content"], "Question")
                return io.BytesIO(json.dumps({"message": {"role": "assistant", "content": "OK"}}).encode())
        with patch("agent.urllib.request.build_opener", return_value=ClientSimule()):
            agent.modele_ollama(messages, "qwen3:4b", max_tokens=12000)
        self.assertEqual(messages[0]["content"], "Question")

    def test_deux_documents_dans_un_meme_tour(self):
        (self.dossier / "produits.txt").write_text("Carnet : 12 EUR", encoding="utf-8")
        def decider(messages):
            observations = [m for m in messages if m["role"] == "tool"]
            if not observations:
                reponse = agent.appel("lire_document", nom="produits.txt")
                reponse["tool_calls"] += agent.appel("lire_document", nom="livraison.txt")["tool_calls"]
                return reponse
            self.assertEqual(len(observations), 2)
            return {"role": "assistant", "content": "Deux observations reçues."}
        self.assertEqual(self.lancer(decider)[-1]["texte"], "Deux observations reçues.")

    def test_troncature_ne_declenche_pas_outil(self):
        reponse = agent.appel("lire_document", nom="livraison.txt")
        reponse["_diagnostic"] = {"done_reason": "length", "eval_count": 2048}
        trace = self.lancer(lambda m: reponse)
        self.assertEqual([e["type"] for e in trace], ["diagnostic_modele", "erreur"])
        self.assertIn("tokens", trace[-1]["message"])

    def test_reflexion_seule_n_est_pas_une_reponse(self):
        trace = self.lancer(lambda m: {"role": "assistant", "content": "", "thinking": "brouillon"})
        self.assertEqual(trace[-1]["type"], "erreur")
        self.assertIn("uniquement de la réflexion", trace[-1]["message"])
        self.assertNotIn("brouillon", json.dumps(trace))

    def test_diagnostic_non_renvoye_au_modele(self):
        def decider(messages):
            if len(messages) == 2:
                reponse = agent.appel("lister_documents")
                reponse["_diagnostic"] = {"done_reason": "stop"}
                return reponse
            self.assertNotIn("_diagnostic", messages[2])
            return {"role": "assistant", "content": "OK"}
        self.assertEqual(self.lancer(decider)[-1]["texte"], "OK")


if __name__ == "__main__":
    unittest.main()
