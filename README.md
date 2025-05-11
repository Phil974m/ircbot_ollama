# Chatbot IRC Intelligent avec Ollama en Python

Ce projet est un chatbot Python capable de se connecter à un serveur IRC, d'interagir avec les utilisateurs et de répondre intelligemment dans un canal en utilisant un modèle de langage local via Ollama.

## Fonctionnalités

*   Connexion configurable à un serveur IRC (hôte, port, SSL, nickname, canal, etc.).
*   Réception et analyse des messages des utilisateurs en temps réel.
*   Utilisation d'Ollama (via son API) pour générer des réponses intelligentes et contextuelles.
*   Gestion des commandes basiques (ex: `!aide`, `!ping`).
*   Respect des règles IRC de base (anti-flood).
*   Personnalisation du ton du bot par canal via des "system prompts" pour Ollama.
*   Reconnexion automatique en cas de déconnexion.
*   Filtrage basique des messages indésirables.
*   Journalisation des conversations et des erreurs pour le débogage.
*   Configuration via un fichier `config.json`.

## Prérequis

1.  **Ollama installé et fonctionnel** : Le bot nécessite qu'un service Ollama soit en cours d'exécution et accessible.
2.  **Python** : Version 3.8 ou ultérieure.
3.  **Un modèle LLM téléchargé via Ollama** : Par exemple, `llama3`, `mistral`, etc.

## 1. Installation d'Ollama

Ollama permet d'exécuter localement de grands modèles de langage.

### Sur Linux

1.  **Téléchargez et exécutez le script d'installation :**
    La méthode la plus simple est d'utiliser le script fourni par Ollama :
    ```bash
    curl -fsSL https://ollama.com/install.sh | sh
    ```
    Cela installera Ollama, configurera le service système et le démarrera.

2.  **Vérifiez l'installation :**
    ```bash
    ollama --version
    ```
    Si le service ne démarre pas automatiquement, vous pouvez le gérer avec `systemd` :
    ```bash
    sudo systemctl start ollama
    sudo systemctl enable ollama # Pour démarrer au boot
    sudo systemctl status ollama # Pour vérifier l'état
    ```

3.  **Téléchargez un modèle :**
    Par exemple, pour télécharger Llama 3 (le tag `:latest` prendra souvent la version 8B instruct) :
    ```bash
    ollama pull llama3
    ```
    Ou un modèle plus petit pour tester, comme `orca-mini`:
    ```bash
    ollama pull orca-mini
    ```
    Listez les modèles téléchargés avec :
    ```bash
    ollama list
    ```

### Sur Windows

1.  **Téléchargez l'installateur :**
    Rendez-vous sur [ollama.com](https://ollama.com/) et téléchargez l'installateur pour Windows.

2.  **Exécutez l'installateur :**
    Suivez les instructions à l'écran. Ollama sera généralement installé et une icône apparaîtra dans la zone de notification, indiquant que le service est en cours d'exécution.

3.  **Téléchargez un modèle (via l'invite de commandes ou PowerShell) :**
    Ouvrez une invite de commandes (cmd) ou PowerShell et utilisez les mêmes commandes Ollama que pour Linux :
    ```bash
    ollama pull llama3
    ollama list
    ```

## 2. Configuration de l'Environnement Python

Il est fortement recommandé d'utiliser un environnement virtuel pour isoler les dépendances de votre projet.

### Option A : Utilisation de `venv` (intégré à Python)

1.  **Créez un environnement virtuel :**
    Dans le répertoire de votre projet, ouvrez un terminal et exécutez :
    ```bash
    python -m venv .venv 
    # ou python3 -m venv .venv sur certains systèmes Linux
    ```
    Cela créera un répertoire `.venv` contenant l'environnement.

2.  **Activez l'environnement virtuel :**
    *   **Linux/macOS :**
        ```bash
        source .venv/bin/activate
        ```
    *   **Windows (cmd) :**
        ```bash
        .venv\Scripts\activate.bat
        ```
    *   **Windows (PowerShell) :**
        ```bash
        .venv\Scripts\Activate.ps1
        ```
        (Si l'exécution de scripts PowerShell est désactivée, vous devrez peut-être exécuter `Set-ExecutionPolicy Unrestricted -Scope Process` d'abord dans cette session PowerShell.)

    Votre invite de commande devrait maintenant être préfixée par `(.venv)`.

### Option B : Utilisation de `conda` (Anaconda3 ou Miniconda3)

Si vous avez Anaconda ou Miniconda installé :

1.  **Créez un nouvel environnement conda :**
    ```bash
    conda create --name ollama_irc_bot python=3.9 # ou la version de Python souhaitée >= 3.8
    ```
    Remplacez `ollama_irc_bot` par le nom d'environnement de votre choix.

2.  **Activez l'environnement conda :**
    ```bash
    conda activate ollama_irc_bot
    ```
    Votre invite de commande devrait maintenant être préfixée par `(ollama_irc_bot)`.

## 3. Installation des Dépendances Python

1.  **Assurez-vous que votre environnement virtuel (venv ou conda) est activé.**

2.  **Créez un fichier `requirements.txt`** dans le répertoire de votre projet avec le contenu suivant :
    ```text
    irc>=20.0.0,<21.0.0
    requests>=2.25.0,<3.0.0
    ```

3.  **Installez les dépendances en utilisant pip :**
    ```bash
    pip install -r requirements.txt
    ```

## 4. Configuration du Chatbot

1.  **Copiez ou renommez `config.example.json` en `config.json`** (si un exemple est fourni, sinon créez `config.json`).

2.  **Modifiez `config.json`** avec vos propres paramètres :
    ```json
    {
      "irc": {
        "server": "irc.libera.chat", // Adresse du serveur IRC
        "port": 6697,                 // Port (6697 pour SSL, 6667 pour non-SSL)
        "use_ssl": true,              // true pour SSL, false sinon
        "nickname": "MonOllamaBot",   // Pseudo du bot sur IRC
        "realname": "Mon Bot Ollama Python", // Nom réel du bot
        "channels": ["#moncanal-test"], // Liste des canaux à rejoindre
        "password": null,             // Mot de passe du serveur IRC (si requis, sinon null)
        "nickserv_password": "VOTRE_MOT_DE_PASSE_NICKSREV", // Mot de passe pour NickServ (si pseudo enregistré, sinon null)
        "command_prefix": "!"         // Préfixe pour les commandes (ex: !ping)
      },
      "ollama": {
        "api_url": "http://localhost:11434/api/chat", // URL de l'API Ollama (important: utiliser /api/chat)
        "model": "llama3:latest",       // Nom du modèle Ollama à utiliser (doit être téléchargé)
        "default_system_prompt": "Tu es un assistant IA utile et concis sur IRC.",
        "channel_tones": {
          "#moncanal-test": "Tu es un chatbot plein d'humour sur #moncanal-test."
        },
        "context_messages_count": 7,    // Nombre de messages d'historique à envoyer à Ollama (prompt système + N-1 messages)
        "request_timeout": 90           // Timeout en secondes pour les requêtes à Ollama
      },
      "bot_settings": {
        "log_level": "INFO",          // Niveau de log: DEBUG, INFO, WARNING, ERROR, CRITICAL
        "log_file": "ollama_irc_bot.log", // Nom du fichier de log
        "reconnect_min_delay": 15,    // Délai minimum avant reconnexion (secondes)
        "reconnect_max_delay": 300,   // Délai maximum avant reconnexion (secondes)
        "reconnect_attempts": 0,      // Nombre max de tentatives (0 pour infini)
        "message_rate_limit_delay": 1.2 // Délai minimum entre les messages envoyés (secondes)
      },
      "security": {
        "spam_filter_keywords": ["motcléspam1", "http://liensuspect.com"],
        "blocked_nicks": ["UtilisateurBloqué1"]
      }
    }
    ```
    *   **Important :** Assurez-vous que `ollama.api_url` pointe vers `http://localhost:11434/api/chat` (ou l'URL correcte si Ollama tourne ailleurs) et que `ollama.model` correspond à un modèle que vous avez téléchargé avec `ollama pull`.
    *   Si vous n'utilisez pas NickServ, mettez `nickserv_password` à `null`.

## 5. Lancement du Bot

1.  **Assurez-vous que votre service Ollama est en cours d'exécution.**
    Vous pouvez vérifier avec `ollama ps` (il peut être vide si aucun modèle n'est activement chargé, c'est normal avant la première requête du bot).

2.  **Assurez-vous que votre environnement virtuel Python est activé.**

3.  **Exécutez le script principal du bot** (par exemple, `ollama_irc_bot.py`) :
    ```bash
    python ollama_irc_bot.py 
    # ou python3 ollama_irc_bot.py
    ```

4.  Le bot devrait se connecter au serveur IRC, rejoindre les canaux spécifiés, et commencer à écouter les messages. Vous verrez des logs dans la console et/ou dans le fichier `ollama_irc_bot.log`.

## Interaction avec le Bot sur IRC

*   **Commandes :** Tapez `!aide` (ou le préfixe que vous avez configuré) pour voir les commandes disponibles.
*   **Discussion :** Pour parler au bot, mentionnez son pseudo suivi de votre message. La manière exacte de déclencher une réponse d'Ollama peut dépendre de la logique dans `on_pubmsg` (par exemple, `MonOllamaBot: Salut, comment vas-tu ?`).

## Débogage

*   Vérifiez les logs produits par le script (console et fichier de log). Réglez `log_level` sur `DEBUG` dans `config.json` pour des informations plus détaillées.
*   Vérifiez les logs du service Ollama lui-même s'il semble y avoir un problème avec la génération des réponses.
*   Testez l'API Ollama manuellement avec `curl` si vous suspectez un problème avec le service Ollama ou le modèle :
    ```bash
    curl http://localhost:11434/api/chat -d '{
      "model": "VOTRE_MODELE",
      "messages": [
        {"role": "system", "content": "Sois bref."},
        {"role": "user", "content": "Dis bonjour."}
      ]
    }'
    ```
    Remplacez `VOTRE_MODELE` par le nom du modèle utilisé par le bot.

## Pour arrêter le Bot

Appuyez sur `Ctrl+C` dans le terminal où le script est en cours d'exécution.

* Script python tkComment utiliser ce script :

    Enregistrez le code ci-dessus dans un fichier, par exemple config_editor_tk.py, dans le même répertoire que votre config.json (ou là où vous voulez qu'il soit créé).

    Exécutez le script :

    ```bash  
    python config_editor_tk.py
    ``` 

    (Assurez-vous que votre environnement Python avec tkinter est actif. tkinter est généralement inclus avec les installations standard de Python).

    Interface :

        Une fenêtre apparaîtra. Si config.json existe, ses valeurs seront chargées. Sinon, des valeurs par défaut seront utilisées.

        Modifiez les champs.

        Utilisez le menu "Fichier > Sauvegarder" (ou le bouton "Sauvegarder Configuration") pour enregistrer vos modifications. Si config.json n'existe pas, il vous demandera où le sauvegarder.

        Le bouton "Recharger depuis Fichier" recharge les valeurs du config.json actuel dans l'interface (utile si vous avez modifié le fichier manuellement).

        Le bouton "Restaurer Défauts" charge des valeurs par défaut dans l'interface (ne sauvegarde pas automatiquement).

Améliorations possibles (pour aller plus loin) :

    Validation plus stricte des entrées (par exemple, s'assurer que le port est un nombre valide, que l'URL a le bon format, etc.).

    Gestion dynamique des listes et dictionnaires (par exemple, pour channels et channel_tones, avoir des boutons pour ajouter/supprimer des entrées au lieu de chaînes séparées par des virgules ou du JSON brut). Cela complexifierait significativement l'interface.

    Utilisation de ttk.Combobox pour des choix prédéfinis (comme log_level).

    Meilleure gestion des erreurs et feedback à l'utilisateur.

    Thèmes et style pour rendre l'interface plus agréable.

    Intégration d'un éditeur de texte simple pour les champs plus longs comme default_system_prompt.

Ce script fournit une base solide pour une configuration plus conviviale de votre bot. qui permet de paramétrer avec une interface:

## Contributions

Les contributions sont les bienvenues ! Veuillez ouvrir une issue ou une pull request.