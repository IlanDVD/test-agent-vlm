"""Chat local, bibliothèque standard uniquement. Lancer avec LANCER-CHAT.cmd."""
import argparse
import json
import secrets
import threading
import urllib.request
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import agent

BASE = Path(__file__).resolve().parent
IDENTITE = "mon-premier-agent-chat-v1"


def maintenant():
    return datetime.now(timezone.utc).isoformat()


class Application:
    def __init__(self, dossier=BASE / "conversations", modele="qwen3:4b", decider=None):
        self.dossier = Path(dossier)
        self.dossier.mkdir(exist_ok=True, parents=True)
        self.modele = modele
        self.decider = decider or (lambda messages: agent.modele_ollama(messages, modele))
        self.token = secrets.token_urlsafe(32)
        self.sessions = {}
        self.lock = threading.RLock()
        self.calcul = threading.Lock()

    def sauver(self, session):
        cible = self.dossier / (session["id"] + ".json")
        temporaire = cible.with_suffix(".tmp")
        temporaire.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
        temporaire.replace(cible)

    def obtenir(self, identifiant):
        if not isinstance(identifiant, str) or str(uuid.UUID(identifiant)) != identifiant:
            raise ValueError("Conversation invalide.")
        with self.lock:
            if identifiant not in self.sessions:
                cible = self.dossier / (identifiant + ".json")
                if not cible.is_file():
                    raise FileNotFoundError("Conversation introuvable.")
                session = json.loads(cible.read_text(encoding="utf-8"))
                for tour in session["tours"]:
                    if tour["statut"] == "en_cours":
                        tour.update(statut="erreur", erreur="Le serveur a été arrêté pendant la réponse. Vous pouvez renvoyer votre question.")
                self.sessions[identifiant] = session
                self.sauver(session)
            return self.sessions[identifiant]

    def nouvelle(self):
        with self.lock:
            session = {"id": str(uuid.uuid4()), "creation": maintenant(), "tours": []}
            self.sauver(session)
            self.sessions[session["id"]] = session
            return session

    def instantane(self, identifiant):
        with self.lock:
            return json.loads(json.dumps(self.obtenir(identifiant)))

    def envoyer(self, identifiant, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("Écrivez une question de 1 à 4 000 caractères.")
        if not self.calcul.acquire(blocking=False):
            raise BlockingIOError("L'agent prépare déjà une réponse. Attendez sa fin avant d'envoyer un autre message.")
        try:
            with self.lock:
                session = self.obtenir(identifiant)
                if len(session["tours"]) >= 60:
                    raise ValueError("Cette conversation contient 60 messages. Commencez une nouvelle conversation.")
                historique = []
                for precedent in [t for t in session["tours"] if t["statut"] == "termine"][-8:]:
                    historique.extend([{"role": "user", "content": precedent["question"]},
                                       {"role": "assistant", "content": precedent["reponse"]}])
                tour = {"id": str(uuid.uuid4()), "question": question.strip(), "reponse": "",
                        "statut": "en_cours", "debut": maintenant(), "evenements": [], "erreur": ""}
                session["tours"].append(tour)
                self.sauver(session)
            threading.Thread(target=self.travailler, args=(session, tour, historique), daemon=True).start()
        except Exception:
            self.calcul.release()
            raise

    def travailler(self, session, tour, historique):
        def evenement(e):
            with self.lock:
                tour["evenements"].append(e)
                self.sauver(session)
        try:
            trace = agent.lancer(self.decider, tour["question"], BASE / "documents",
                                 historique=historique, on_event=evenement, bavard=False)
            with self.lock:
                if trace and trace[-1]["type"] == "reponse_finale":
                    tour.update(statut="termine", reponse=trace[-1]["texte"])
                else:
                    erreur = trace[-1].get("message", "Limite d'étapes atteinte. Reformulez la demande.") if trace else "Aucune réponse reçue."
                    tour.update(statut="erreur", erreur=erreur)
        except Exception as erreur:
            with self.lock:
                tour.update(statut="erreur", erreur="Impossible de terminer la réponse : " + str(erreur))
        finally:
            try:
                with self.lock:
                    tour["fin"] = maintenant()
                    self.sauver(session)
            finally:
                self.calcul.release()

    def etat_ollama(self):
        try:
            client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with client.open("http://127.0.0.1:11434/api/tags", timeout=3) as reponse:
                modeles = [m["name"] for m in json.load(reponse).get("models", [])]
            disponible = self.modele in modeles
            return {"ok": disponible, "message": "Prêt à discuter" if disponible else
                    f"Modèle absent. Dans PowerShell : ollama pull {self.modele}"}
        except Exception:
            return {"ok": False, "message": "Ollama est indisponible. Ouvrez Ollama, puis actualisez cette page."}


class Serveur(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, adresse, application):
        self.application = application
        super().__init__(adresse, Requetes)


class Requetes(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def repondre(self, status, contenu, mime="application/json; charset=utf-8"):
        donnees = contenu if isinstance(contenu, bytes) else json.dumps(contenu, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(donnees)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(donnees)

    def origine_valide(self):
        port = self.server.server_address[1]
        autorises = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origine = self.headers.get("Origin")
        return (self.headers.get("Host") in autorises and
                (origine is None or origine in {"http://" + h for h in autorises}))

    def do_GET(self):
        if not self.origine_valide():
            return self.repondre(403, {"erreur": "Accès local uniquement."})
        app = self.server.application
        if self.path == "/api/health":
            return self.repondre(200, {"application": IDENTITE})
        if self.path == "/api/bootstrap":
            return self.repondre(200, {"token": app.token, "modele": app.modele,
                                      "etat": app.etat_ollama(),
                                      "documents": agent.executer_outil("lister_documents", {}, BASE / "documents").get("documents", [])})
        if self.path.startswith("/api/session/"):
            try:
                return self.repondre(200, app.instantane(self.path.removeprefix("/api/session/")))
            except (ValueError, FileNotFoundError):
                return self.repondre(404, {"erreur": "Conversation introuvable."})
        fichiers = {"/": ("index.html", "text/html; charset=utf-8"),
                    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                    "/style.css": ("style.css", "text/css; charset=utf-8"),
                    "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        if self.path in fichiers:
            fichier, mime = fichiers[self.path]
            return self.repondre(200, (BASE / "web" / fichier).read_bytes(), mime)
        self.repondre(404, {"erreur": "Page introuvable."})

    def do_POST(self):
        app = self.server.application
        if not self.origine_valide() or not secrets.compare_digest(self.headers.get("X-Chat-Token", ""), app.token):
            return self.repondre(403, {"erreur": "Actualisez la page pour reconnecter le chat."})
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Format JSON attendu.")
            taille = int(self.headers.get("Content-Length", "0"))
            if not 0 < taille <= 20000:
                raise ValueError("Message trop volumineux ou vide.")
            donnees = json.loads(self.rfile.read(taille))
            if not isinstance(donnees, dict):
                raise ValueError("Objet JSON attendu.")
            if self.path == "/api/session":
                return self.repondre(201, app.nouvelle())
            if self.path == "/api/chat":
                app.envoyer(donnees.get("session"), donnees.get("question"))
                return self.repondre(202, {"ok": True})
            return self.repondre(404, {"erreur": "Action introuvable."})
        except BlockingIOError as erreur:
            self.repondre(409, {"erreur": str(erreur)})
        except (ValueError, TypeError, AttributeError, FileNotFoundError) as erreur:
            self.repondre(400, {"erreur": str(erreur)})
        except OSError:
            self.repondre(500, {"erreur": "Impossible de sauvegarder la conversation sur le disque."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--ouvrir", action="store_true")
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    try:
        serveur = Serveur(("127.0.0.1", args.port), Application(modele=args.model))
    except OSError:
        try:
            client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with client.open(url + "/api/health", timeout=2) as reponse:
                deja_present = json.load(reponse).get("application") == IDENTITE
        except Exception:
            deja_present = False
        if deja_present:
            print("Le chat est déjà ouvert :", url)
            if args.ouvrir:
                webbrowser.open(url)
            return
        raise SystemExit("Port indisponible. Essayez : chat_local.py --port 8766 --ouvrir")
    print("Votre chat local :", url, flush=True)
    print("Gardez cette fenêtre ouverte. Ctrl+C arrête le serveur.", flush=True)
    if args.ouvrir:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nChat arrêté.")
    finally:
        serveur.server_close()


if __name__ == "__main__":
    main()
