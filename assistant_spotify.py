#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assistant Vocal Local "Spotify-Link"
Script Python pour contrôler Spotify via commandes vocales en local.
"""

import json
import subprocess
import os
import sys
from typing import Optional

try:
    import vosk
    import pyaudio
    import pyttsx3
    import requests
except ImportError as e:
    print(f"❌ Module manquant : {e}")
    print("📦 Installez les dépendances avec : pip install -r requirements.txt")
    sys.exit(1)


# ==================== CONFIGURATION ====================

# Chemin vers l'exécutable Spotify (à adapter selon votre installation)
SPOTIFY_PATH = r"C:\Users\raphi\AppData\Roaming\Spotify\Spotify.exe"

# Chemin vers le modèle Vosk (sera téléchargé automatiquement si nécessaire)
VOSK_MODEL_PATH = r"vosk-model-small-fr-0.22"

# Configuration Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# Configuration audio
SAMPLE_RATE = 16000
CHUNK_SIZE = 4000

# Seuil de longueur minimale du texte pour l'analyse
MIN_TEXT_LENGTH = 3


# ==================== FONCTIONS ====================

def initialiser_voix() -> pyttsx3.Engine:
    """
    Configure et initialise le moteur de synthèse vocale pyttsx3.
    
    Returns:
        pyttsx3.Engine: Moteur TTS configuré
    """
    try:
        engine = pyttsx3.init()
        
        # Configuration de la voix française
        voices = engine.getProperty('voices')
        # Chercher une voix française si disponible
        for voice in voices:
            if 'french' in voice.name.lower() or 'fr' in voice.id.lower():
                engine.setProperty('voice', voice.id)
                break
        
        # Configuration de la vitesse (mots par minute)
        engine.setProperty('rate', 150)
        
        # Configuration du volume (0.0 à 1.0)
        engine.setProperty('volume', 0.9)
        
        print("✅ Voix initialisée")
        return engine
    
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la voix : {e}")
        sys.exit(1)


def parler(engine: pyttsx3.Engine, texte: str) -> None:
    """
    Fait parler l'assistant avec le texte fourni.
    
    Args:
        engine: Moteur TTS
        texte: Texte à prononcer
    """
    try:
        engine.say(texte)
        engine.runAndWait()
    except Exception as e:
        print(f"❌ Erreur lors de la synthèse vocale : {e}")


def verifier_ollama() -> bool:
    """
    Vérifie si Ollama est accessible et si le modèle est disponible.
    
    Returns:
        bool: True si Ollama est accessible, False sinon
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [model.get('name', '') for model in models]
            if OLLAMA_MODEL in model_names:
                print(f"✅ Ollama accessible avec le modèle '{OLLAMA_MODEL}'")
                return True
            else:
                print(f"⚠️  Modèle '{OLLAMA_MODEL}' non trouvé. Modèles disponibles : {model_names}")
                print(f"💡 Installez le modèle avec : ollama pull {OLLAMA_MODEL}")
                return False
        return False
    except requests.exceptions.RequestException:
        print("❌ Ollama n'est pas accessible. Assurez-vous qu'Ollama est démarré.")
        return False


def analyser_intention(texte: str) -> Optional[str]:
    """
    Analyse l'intention de l'utilisateur via Ollama (Mistral).
    
    Args:
        texte: Texte transcrit à analyser
        
    Returns:
        str: 'ACTION_SPOTIFY' si l'utilisateur veut lancer Spotify, 'IGNORE' sinon, None en cas d'erreur
    """
    if not texte or len(texte.strip()) < MIN_TEXT_LENGTH:
        return None
    
    prompt_system = (
        "Tu es un assistant vocal. Analyse la demande de l'utilisateur. "
        "Si l'utilisateur veut lancer Spotify, réponds uniquement 'ACTION_SPOTIFY'. "
        "Sinon, réponds 'IGNORE'. "
        "Réponds UNIQUEMENT avec 'ACTION_SPOTIFY' ou 'IGNORE', sans autre texte."
    )
    
    prompt_complet = f"{prompt_system}\n\nUtilisateur : {texte}\n\nAssistant :"
    
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt_complet,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Faible température pour des réponses déterministes
                "num_predict": 10   # Limite la réponse à quelques tokens
            }
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        reponse_llm = result.get('response', '').strip().upper()
        
        # Nettoyer la réponse pour extraire ACTION_SPOTIFY ou IGNORE
        if 'ACTION_SPOTIFY' in reponse_llm:
            return 'ACTION_SPOTIFY'
        elif 'IGNORE' in reponse_llm:
            return 'IGNORE'
        else:
            # Si la réponse n'est pas claire, on ignore par défaut
            return 'IGNORE'
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la requête à Ollama : {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse de l'intention : {e}")
        return None


def executer_action(code_intention: str, engine: pyttsx3.Engine) -> None:
    """
    Exécute l'action correspondant au code d'intention.
    
    Args:
        code_intention: Code d'intention ('ACTION_SPOTIFY' ou 'IGNORE')
        engine: Moteur TTS pour les réponses vocales
    """
    if code_intention == 'ACTION_SPOTIFY':
        lancer_spotify(engine)
    elif code_intention == 'IGNORE':
        # Ne rien faire, juste continuer à écouter
        pass


def lancer_spotify(engine: pyttsx3.Engine) -> None:
    """
    Lance l'application Spotify.
    
    Args:
        engine: Moteur TTS pour les réponses vocales
    """
    if not os.path.exists(SPOTIFY_PATH):
        message = f"Erreur : le chemin vers Spotify est introuvable. Vérifiez le chemin dans le script."
        print(f"❌ {message}")
        parler(engine, "Je n'ai pas trouvé Spotify sur votre système. Vérifiez le chemin dans le script.")
        return
    
    try:
        # Vérifier si Spotify est déjà en cours d'exécution
        # Sur Windows, on peut vérifier avec tasklist
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq Spotify.exe'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if 'Spotify.exe' in result.stdout:
            print("ℹ️  Spotify est déjà en cours d'exécution")
            parler(engine, "Spotify est déjà lancé")
            return
        
        # Lancer Spotify
        subprocess.Popen([SPOTIFY_PATH], shell=False)
        print("✅ Spotify lancé")
        parler(engine, "Spotify lancé")
    
    except subprocess.TimeoutExpired:
        print("⚠️  Timeout lors de la vérification de Spotify")
        parler(engine, "Erreur lors du lancement de Spotify")
    except Exception as e:
        print(f"❌ Erreur lors du lancement de Spotify : {e}")
        parler(engine, "Erreur lors du lancement de Spotify")


def telecharger_modele_vosk() -> Optional[str]:
    """
    Télécharge le modèle Vosk si nécessaire.
    
    Returns:
        str: Chemin vers le modèle, None si erreur
    """
    if os.path.exists(VOSK_MODEL_PATH) and os.path.isdir(VOSK_MODEL_PATH):
        print(f"✅ Modèle Vosk trouvé : {VOSK_MODEL_PATH}")
        return VOSK_MODEL_PATH
    
    print(f"📥 Téléchargement du modèle Vosk...")
    print(f"💡 Téléchargez manuellement depuis : https://alphacephei.com/vosk/models")
    print(f"💡 Ou utilisez : python -m vosk --model vosk-model-small-fr-0.22")
    return None


def ecouter_micro(engine: pyttsx3.Engine) -> None:
    """
    Écoute le microphone en continu et traite les commandes vocales.
    
    Args:
        engine: Moteur TTS
    """
    # Vérifier et télécharger le modèle Vosk
    model_path = telecharger_modele_vosk()
    if not model_path:
        print("❌ Modèle Vosk introuvable. Veuillez le télécharger.")
        parler(engine, "Modèle de reconnaissance vocale introuvable")
        return
    
    try:
        # Charger le modèle Vosk
        model = vosk.Model(model_path)
        recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(True)
        
        # Initialiser PyAudio
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        print("🎤 Microphone activé. Dites 'lance Spotify' pour démarrer l'application.")
        print("💬 Appuyez sur Ctrl+C pour arrêter.\n")
        
        buffer_texte = ""
        dernier_texte = ""
        
        while True:
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    texte = result.get('text', '').strip()
                    
                    if texte and texte != dernier_texte:
                        print(f"🎤 Vous avez dit : {texte}")
                        buffer_texte = texte
                        dernier_texte = texte
                        
                        # Analyser l'intention
                        intention = analyser_intention(buffer_texte)
                        
                        if intention:
                            print(f"🧠 Intention détectée : {intention}")
                            executer_action(intention, engine)
                            buffer_texte = ""  # Réinitialiser le buffer
                
                else:
                    # Résultat partiel (en cours de reconnaissance)
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = partial.get('partial', '').strip()
                    if partial_text:
                        # Afficher le texte partiel (optionnel, peut être commenté)
                        pass
            
            except KeyboardInterrupt:
                print("\n\n🛑 Arrêt demandé par l'utilisateur")
                break
            except Exception as e:
                print(f"❌ Erreur lors de l'écoute : {e}")
                continue
        
        # Nettoyage
        stream.stop_stream()
        stream.close()
        audio.terminate()
        print("✅ Microphone fermé")
    
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation du microphone : {e}")
        parler(engine, "Erreur lors de l'initialisation du microphone")


def main_loop() -> None:
    """
    Boucle principale qui orchestre toutes les fonctionnalités.
    """
    print("=" * 60)
    print("🎵 Assistant Vocal Local 'Spotify-Link'")
    print("=" * 60)
    print()
    
    # Initialiser la voix
    engine = initialiser_voix()
    
    # Vérifier Ollama
    if not verifier_ollama():
        print("\n⚠️  Ollama n'est pas accessible. Le script continuera mais l'analyse d'intention ne fonctionnera pas.")
        reponse = input("Voulez-vous continuer quand même ? (o/n) : ")
        if reponse.lower() != 'o':
            sys.exit(1)
    
    # Message de bienvenue vocal
    parler(engine, "Assistant vocal initialisé. Dites 'lance Spotify' pour démarrer l'application.")
    
    # Démarrer l'écoute
    ecouter_micro(engine)
    
    # Message de fin
    parler(engine, "Au revoir")
    print("\n👋 Au revoir !")


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n\n🛑 Arrêt du programme")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur fatale : {e}")
        sys.exit(1)

