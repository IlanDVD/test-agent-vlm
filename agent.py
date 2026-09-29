"""Un agent pédagogique : simulation sans IA, ou vraie IA via Ollama local.

Python 3.10+ ; Pillow requis pour les annotations de plans. Voir GUIDE.md.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from skills import MISSION, OUTILS, executer_outil

BASE = Path(__file__).resolve().parent
QUESTION = "Quels sont le délai et les frais de livraison en France métropolitaine ?"
def appel(nom_outil, **arguments):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": nom_outil, "arguments": arguments}}
    ]}


def modele_simule(messages, erreur_volontaire=False):
    """Scénario déterministe : aucune IA, aucune compréhension du langage.

    Il utilise les vrais résultats d'outils, mais ses choix sont écrits à l'avance.
    """
    observations = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
    if not observations:
        return appel("lister_documents")
    if erreur_volontaire and len(observations) == 1:
        return appel("lire_document", nom="document-inexistant.txt")
    for observation in observations:
        if observation.get("source") == "livraison.txt":
            return {"role": "assistant", "content":
                    "Voici les informations du document fictif [livraison.txt] :\n\n"
                    + observation["contenu"]}
    if any("erreur" in o for o in observations[2 if erreur_volontaire else 1:]):
        return {"role": "assistant", "content": "Lecture impossible : je ne peux pas confirmer la réponse."}
    disponibles = observations[0].get("documents", [])
    if "livraison.txt" not in disponibles:
        return {"role": "assistant", "content": "Le document livraison.txt manque. Je ne peux pas confirmer la réponse."}
    return appel("lire_document", nom="livraison.txt")


def modele_ollama(messages, modele, max_tokens=8192):
    """Seule cette fonction dépend du fournisseur de modèle."""
    # La réflexion et la réponse partagent le budget de génération.
    # Conserver le mode natif du modèle et lui laisser un budget suffisant.
    corps = json.dumps({"model": modele, "messages": messages,
                        "tools": OUTILS, "stream": False,
                        "options": {"num_predict": max_tokens}}).encode("utf-8")
    requete = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=corps,
                                    headers={"Content-Type": "application/json"})
    # Le service local n'est pas envoyé à un proxy configuré sur le système.
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with client.open(requete, timeout=300) as reponse:
        donnees = reponse.read(2_000_001)
    if len(donnees) > 2_000_000:
        raise ValueError("Réponse du modèle trop volumineuse.")
    resultat = json.loads(donnees)
    message = resultat["message"]
    if not isinstance(message, dict):
        raise ValueError("Message Ollama invalide.")
    # Conserver les métadonnées utiles sans afficher ni journaliser la réflexion.
    # Le champ privé sera retiré avant de renvoyer l'historique à Ollama.
    message["_diagnostic"] = {
        "done_reason": resultat.get("done_reason"),
        "eval_count": resultat.get("eval_count"),
        "prompt_eval_count": resultat.get("prompt_eval_count"),
        "reflexion_presente": bool(message.get("thinking")),
        "caracteres_reponse": len(message.get("content") or ""),
        "max_tokens": max_tokens,
    }
    return message


def lancer(decider, question, dossier, limite=10, pause=False,
           historique=None, on_event=None, bavard=True, modele_vision="qwen2.5vl:3b"):
    """Boucle commune aux deux modes : modèle → outils → observations."""
    messages = [{"role": "system", "content": MISSION}]
    messages.extend(dict(m) for m in (historique or []))
    messages.append({"role": "user", "content": question})
    trace = []

    def afficher(*valeurs):
        if bavard:
            print(*valeurs)

    def signaler(evenement):
        if on_event:
            on_event(evenement)

    def noter(type_evenement, **champs):
        trace.append({"type": type_evenement, **champs})
        signaler(trace[-1])

    try:
        for etape in range(1, limite + 1):
            afficher(f"\n--- Tour {etape} : décision ---")
            signaler({"type": "etape", "tour": etape})
            reponse = decider(messages)
            if not isinstance(reponse, dict) or reponse.get("role") != "assistant":
                raise ValueError("Réponse du modèle invalide.")
            reponse = dict(reponse)
            diagnostic = reponse.pop("_diagnostic", None)
            if diagnostic is not None:
                noter("diagnostic_modele", tour=etape, **diagnostic)
                if diagnostic.get("done_reason") == "length":
                    raise ValueError("Génération interrompue : limite de tokens atteinte. "
                                     "Augmentez --max-tokens (maximum 16384). "
                                     "La réponse partielle et ses éventuels outils ne sont pas exécutés.")
            messages.append(reponse)
            appels = reponse.get("tool_calls") or []
            if not isinstance(appels, list) or len(appels) > 5:
                raise ValueError("Au maximum 5 appels d'outils sont autorisés par tour.")
            if not appels:
                texte = reponse.get("content", "")
                if not isinstance(texte, str) or not texte.strip():
                    if reponse.get("thinking"):
                        raise ValueError("Ollama a renvoyé uniquement de la réflexion, sans réponse "
                                         "ni outil. Consultez le diagnostic du journal.")
                    raise ValueError("Le modèle a terminé sans réponse exploitable.")
                afficher("Réponse finale :\n" + texte)
                noter("reponse_finale", tour=etape, texte=texte)
                return trace
            for action in appels:
                fonction = action["function"]
                nom, arguments = fonction["name"], fonction["arguments"]
                afficher("Demande d'outil :", nom, json.dumps(arguments, ensure_ascii=False))
                signaler({"type": "outil_demande", "tour": etape, "nom": nom, "arguments": arguments})
                if pause:
                    input("Entrée pour exécuter et voir le résultat… ")
                resultat = executer_outil(nom, arguments, dossier, modele_vision=modele_vision)
                afficher("Observation :", json.dumps(resultat, ensure_ascii=False, indent=2))
                noter("outil", tour=etape, nom=nom, arguments=arguments, resultat=resultat)
                messages.append({"role": "tool", "tool_name": nom,
                                 "content": json.dumps(resultat, ensure_ascii=False)})
        afficher("\nArrêt : limite de tours atteinte. La tâche n'est pas déclarée réussie.")
        noter("limite_atteinte", tours=limite)
    except (OSError, ValueError, KeyError, TypeError, EOFError) as erreur:
        afficher(f"\nArrêt sur erreur : {erreur}")
        noter("erreur", message=str(erreur))
    return trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["demo", "ollama"], default="demo")
    parser.add_argument("--model", help="Nom exact du modèle local installé dans Ollama")
    parser.add_argument("--question", default=QUESTION)
    parser.add_argument("--pas-a-pas", action="store_true")
    parser.add_argument("--demo-erreur", action="store_true")
    parser.add_argument("--max-tours", type=int, choices=range(1, 21), default=10, metavar="1..20")
    parser.add_argument("--max-tokens", type=int, choices=range(256, 16385), default=8192,
                        metavar="256..16384", help="Budget par génération, réflexion comprise (défaut : 8192)")
    parser.add_argument("--vision-model", default="qwen2.5vl:3b", help="Modèle Ollama pour les images")
    args = parser.parse_args()
    if args.mode == "demo" and args.question != QUESTION:
        parser.error("La simulation couvre uniquement la question prédéfinie. Utiliser --mode ollama pour une autre question.")
    if args.mode == "ollama" and not args.model:
        parser.error("Le mode ollama exige --model avec le nom d'un modèle local compatible outils.")
    if args.mode == "ollama" and args.demo_erreur:
        parser.error("--demo-erreur s'utilise uniquement avec --mode demo.")
    print("SIMULATION SANS IA — choix prédéfinis." if args.mode == "demo"
          else f"MODE IA — modèle demandé à Ollama : {args.model}")
    print("Objectif :", args.question)
    decider = (lambda m: modele_simule(m, args.demo_erreur)) if args.mode == "demo" else (
        lambda m: modele_ollama(m, args.model, args.max_tokens))
    trace = lancer(decider, args.question, BASE / "documents", args.max_tours, args.pas_a_pas, modele_vision=args.vision_model)
    journaux = BASE / "journaux"
    journaux.mkdir(exist_ok=True)
    chemin = journaux / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
    chemin.write_text(json.dumps({"mode": args.mode, "modele": args.model,
                                "question": args.question, "evenements": trace},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nJournal enregistré :", chemin)
    return 0 if trace and trace[-1]["type"] == "reponse_finale" else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.exit(main())
