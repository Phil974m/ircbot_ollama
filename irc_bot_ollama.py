import irc.bot
import irc.strings
from irc.client import ip_numstr_to_quad, ip_quad_to_numstr, Event, ServerConnection, NickMask
import json
import requests
import time
import logging
import ssl # Pour la connexion SSL
import random
from functools import partial

# --- Configuration et Logging ---
CONFIG_FILE = "config.json"
config = {}
conversation_history = {} # Pour stocker l'historique par canal { "canal": [{"role": "user/assistant", "name": "nick", "content": "message"}, ...]}

def load_config():
    global config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        logging.critical(f"Erreur: Le fichier de configuration '{CONFIG_FILE}' est introuvable.")
        exit(1)
    except json.JSONDecodeError as e:
        logging.critical(f"Erreur: Le fichier de configuration '{CONFIG_FILE}' n'est pas un JSON valide. Détails: {e}")
        exit(1)

def setup_logging():
    bot_settings = config.get("bot_settings", {})
    log_level_str = bot_settings.get("log_level", "INFO").upper()
    log_file = bot_settings.get("log_file", "ollama_irc_bot.log")
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_level = logging.DEBUG 
    logging.getLogger("irc.client").setLevel(logging.DEBUG)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    # Réduire la verbosité de la bibliothèque IRC si on est en INFO ou plus haut
    # if log_level <= logging.INFO: # Temporairement commenter ou ajuster pour voir les logs DEBUG d'IRC
    #     logging.getLogger("irc.client").setLevel(logging.WARNING)
    # else:
    #     logging.getLogger("irc.client").setLevel(log_level) # Ou fixez-le à DEBUG
    
    # Pour voir TOUS les messages de la bibliothèque IRC, y compris les données brutes :
    logging.getLogger("irc.client").setLevel(logging.DEBUG) # <<< MODIFICATION IMPORTANTE


class OllamaIRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channels, nickname, server, port, use_ssl=False, realname=None, server_password=None, nickserv_password=None):
        irc_config = config.get("irc", {})
        self.ollama_config = config.get("ollama", {})
        self.bot_settings = config.get("bot_settings", {})
        self.security_config = config.get("security", {})

        self.target_channels = channels
        self.nickserv_password = nickserv_password
        self.command_prefix = irc_config.get("command_prefix", "!")
        
        self.ollama_api_url = self.ollama_config.get("api_url")
        self.ollama_model = self.ollama_config.get("model")
        self.ollama_default_system_prompt = self.ollama_config.get("default_system_prompt")
        self.ollama_channel_tones = self.ollama_config.get("channel_tones", {})
        self.ollama_context_messages_count = self.ollama_config.get("context_messages_count", 5)
        self.ollama_request_timeout = self.ollama_config.get("request_timeout", 90)

        self.message_rate_limit_delay = self.bot_settings.get("message_rate_limit_delay", 1.5)
        self.last_message_time = 0

        connect_factory_args = {}
        if use_ssl:
            ssl_context = ssl.create_default_context()
            # Pour les serveurs avec certificats auto-signés (NON RECOMMANDÉ pour la production)
            # Vous pourriez avoir besoin de décommenter ces lignes si vous testez sur un serveur
            # avec un certificat non valide ou auto-signé.
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # === MODIFICATION IMPORTANTE ICI ===
            # Nous devons fournir server_hostname à wrap_socket.
            # functools.partial permet de créer une nouvelle fonction avec certains arguments pré-remplis.
            #wrapped_socket_factory = partial(ssl_context.wrap_socket, server_hostname=server)
            #connect_factory_args['connect_factory'] = irc.connection.Factory(wrapper=wrapped_socket_factory)
            # ===================================
            #connect_factory = irc.connection.Factory(wrapper=lambda sock: ssl_context.wrap_socket(sock, server_hostname=server))
            #connect_factory_args['connect_factory'] = connect_factory
            connect_factory_args['connect_factory'] = irc.connection.Factory(
            wrapper=lambda sock: ssl_context.wrap_socket(sock, server_hostname=server)
            )
        # Note: l'argument servername est utilisé par SingleServerIRCBot pour le SNI si connect_factory n'est pas utilisé
        # ou si la factory elle-même ne gère pas le SNI (ce que nous faisons maintenant avec partial).
        super().__init__([(server, port, server_password)], nickname, realname if realname else nickname, **connect_factory_args)
        logging.info(f"Bot initialisé pour {server}:{port} avec le pseudo {nickname}, SSL: {use_ssl}")
        
    def on_welcome(self, c: ServerConnection, e: Event):
        logging.info(f"Connecté au serveur: {e.source.host if isinstance(e.source, NickMask) else e.source}")
        if self.nickserv_password:
            logging.info(f"Identification auprès de NickServ pour {c.get_nickname()}...")
            c.privmsg("NickServ", f"IDENTIFY {self.nickserv_password}")
            # Il est préférable d'attendre une confirmation de NickServ ou un délai raisonnable
            # Pour ce code, on va supposer que ça marche et joindre les canaux après un court délai
            time.sleep(5) 

        for channel in self.target_channels:
            logging.info(f"Tentative de rejoindre le canal: {channel}")
            c.join(channel)
            if channel not in conversation_history:
                conversation_history[channel] = []

    def on_nicknameinuse(self, c: ServerConnection, e: Event):
        original_nick = c.get_nickname()
        new_nick = original_nick + "_"
        logging.warning(f"Pseudo '{original_nick}' déjà utilisé. Tentative avec '{new_nick}'")
        c.nick(new_nick)
        if self.nickserv_password and original_nick == config.get("irc", {}).get("nickname"): # Si c'est notre pseudo principal
            logging.info(f"Le pseudo principal {original_nick} était pris. Si vous utilisez NickServ, "
                         f"vous devrez peut-être récupérer votre pseudo manuellement ou configurer GHOST.")


    def on_kick(self, c: ServerConnection, e: Event):
        kicked_nick = e.arguments[0]
        channel = e.target
        kicker = e.source.nick
        reason = e.arguments[1] if len(e.arguments) > 1 else "aucune raison spécifiée"
        
        logging.warning(f"{kicked_nick} a été kické de {channel} par {kicker} pour : {reason}")
        
        if kicked_nick == c.get_nickname() and channel in self.target_channels:
            logging.info(f"J'ai été kické de {channel}. Je tenterai de rejoindre après un délai.")
            # Pour une gestion plus robuste, cela pourrait être un événement qui déclenche une tentative de rejoin dans la boucle principale
            # Ici, nous allons simplement attendre un peu et essayer de rejoindre si le bot est toujours connecté.
            # Attention: cela peut mener à des boucles de kick/rejoin si la raison du kick n'est pas résolue.
            # time.sleep(60) # Attendre 1 minute
            # c.join(channel) # Déplacé vers la logique de reconnexion pour plus de robustesse

    def on_disconnect(self, c: ServerConnection, e: Event):
        logging.error(f"Déconnecté du serveur: {e.source if e.source else 'Serveur inconnu'} - Raison: {e.arguments[0] if e.arguments else 'Inconnue'}")
        # Ceci va faire que la boucle `bot.start()` dans `main()` se termine, permettant à la logique de reconnexion de s'activer.
        # Pas besoin de `raise ConnectionAbortedError` explicitement, la fin de `start()` suffit.

    def _send_message_with_rate_limit(self, c: ServerConnection, target: str, message: str):
        current_time = time.time()
        if current_time - self.last_message_time < self.message_rate_limit_delay:
            sleep_duration = self.message_rate_limit_delay - (current_time - self.last_message_time)
            logging.debug(f"Rate limit: Attente de {sleep_duration:.2f}s avant d'envoyer le message.")
            time.sleep(sleep_duration)
        
        max_len_irc = 450 # Limite typique, un peu moins pour être sûr avec préfixes, etc.
        
        for line in message.splitlines():
            line = line.strip()
            if not line:
                continue
            
            remaining_line = line
            while len(remaining_line.encode('utf-8')) > max_len_irc: # Compter les octets pour UTF-8
                # Trouver la meilleure coupure (espace) en tenant compte de l'encodage
                part = ""
                temp_line = ""
                last_space_idx = -1
                for i, char_ in enumerate(remaining_line):
                    temp_line_bytes = (temp_line + char_).encode('utf-8')
                    if len(temp_line_bytes) > max_len_irc:
                        break
                    temp_line += char_
                    if char_ == ' ':
                        last_space_idx = i
                
                if last_space_idx != -1 and len(temp_line.encode('utf-8')) > max_len_irc * 0.75 : # Couper à l'espace si c'est raisonnable
                    part = remaining_line[:last_space_idx]
                    remaining_line = remaining_line[last_space_idx+1:].lstrip()
                else: # Coupure brutale si pas d'espace ou si la coupure est trop courte
                    # Trouver le point de coupure en octets
                    idx_byte_limit = 0
                    current_byte_len = 0
                    for i, char_ in enumerate(remaining_line):
                        char_byte_len = len(char_.encode('utf-8'))
                        if current_byte_len + char_byte_len > max_len_irc:
                            break
                        current_byte_len += char_byte_len
                        idx_byte_limit = i + 1
                    part = remaining_line[:idx_byte_limit]
                    remaining_line = remaining_line[idx_byte_limit:].lstrip()

                logging.debug(f"Envoi (partie): {target} <- {part}")
                c.privmsg(target, part)
                self.last_message_time = time.time()
                if remaining_line:
                    time.sleep(self.message_rate_limit_delay / 2) # Petite pause entre les parties
            
            if remaining_line:
                logging.debug(f"Envoi (fin): {target} <- {remaining_line}")
                c.privmsg(target, remaining_line)
                self.last_message_time = time.time()

    def get_ollama_response(self, user_nick: str, user_prompt: str, channel: str):
        logging.debug(f"Préparation de la requête Ollama pour [{channel}] <{user_nick}>: {user_prompt}")
        
        system_prompt_content = self.ollama_channel_tones.get(channel, self.ollama_default_system_prompt)
        
        #ollama_messages = [{"role": "system", "content": system_prompt_content}]
        prompt = f"{user_nick} dit dans {channel}: {user_prompt}"
        ollama_messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt}
        ]        
        channel_hist = conversation_history.get(channel, [])
        relevant_history = channel_hist[-(self.ollama_context_messages_count -1):] if self.ollama_context_messages_count > 1 else []

        for hist_entry in relevant_history:
            # hist_entry est déjà au format {"role": "user/assistant", "name": "nick", "content": "message"}
            # Pour Ollama, on simplifie le rôle à "user" ou "assistant"
            # Si "name" est le bot, c'est "assistant", sinon "user".
            role = "assistant" if hist_entry.get("name") == self.connection.get_nickname() else "user"
            
            # Pour les messages "user", Ollama peut bénéficier de savoir qui a parlé.
            # Cependant, la structure officielle `messages` n'a pas de champ "name" pour le rôle "user".
            # On préfixe donc le contenu pour les messages utilisateurs.
            content_with_name = f"{hist_entry.get('name', 'unknown_user')}: {hist_entry.get('content', '')}" if role == "user" else hist_entry.get('content', '')
            
            ollama_messages.append({"role": role, "content": content_with_name})
        
        # Ajouter le message actuel de l'utilisateur
        ollama_messages.append({"role": "user", "content": f"{user_nick}: {user_prompt}"})

        payload = {
            "model": self.ollama_model,
            "messages": ollama_messages,
            "stream": False,
            "options": { # Certaines options peuvent être utiles
            "temperature": 0.7,
                # "num_ctx": 4096 # Taille de la fenêtre de contexte du modèle si besoin d'ajuster
            }
        }
        
        logging.debug(f"Payload Ollama: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        try:
            response = requests.post(self.ollama_api_url, json=payload, timeout=self.ollama_request_timeout)
            response.raise_for_status()
            api_response = response.json()
            
            if "message" in api_response and "content" in api_response["message"]:
                bot_response = api_response["message"]["content"]
            elif "response" in api_response: # Compatibilité avec les modèles plus anciens/API generate simple
                bot_response = api_response["response"]
            else:
                logging.error(f"Réponse Ollama inattendue: {api_response}")
                return "Désolé, je n'ai pas pu traiter cette demande (format de réponse Ollama non reconnu)."

            logging.info(f"Réponse d'Ollama: {bot_response}")
            # On stocke la réponse du bot dans l'historique
            self._add_to_history(channel, self.connection.get_nickname(), bot_response, role="assistant")
            return bot_response.strip()
            
        except requests.exceptions.Timeout:
            logging.error(f"Timeout lors de la communication avec l'API Ollama ({self.ollama_api_url}).")
            return f"Désolé {user_nick}, mon cerveau (Ollama) met trop de temps à répondre. Réessayez plus tard."
        except requests.exceptions.RequestException as e:
            logging.error(f"Erreur de communication avec l'API Ollama ({self.ollama_api_url}): {e}")
            return f"Désolé {user_nick}, un souci technique m'empêche de contacter mon cerveau (Ollama) : {type(e).__name__}."
        except Exception as e:
            logging.error(f"Erreur inattendue lors de l'appel à Ollama: {e}", exc_info=True)
            return "Désolé, une erreur interne est survenue en essayant de générer une réponse."
        # ... (dans get_ollama_response, après response.raise_for_status())
        try:
            api_response = response.json()
            logging.debug(f"CONTENU BRUT DE LA RÉPONSE JSON D'OLLAMA: {api_response}") # <--- AJOUTER CE LOG

            #bot_response = api_response.get("message", {}).get("content") or api_response.get("response")
            bot_response = api_response.get("response", "")
            logging.debug(f"Réponse brute d'Ollama: {response.text}")
            if not bot_response: # Si bot_response est None ou une chaîne vide
                logging.error(f"Réponse Ollama valide (code 200) mais contenu attendu (message.content ou response) manquant ou vide. Réponse complète: {api_response}")
                # On peut même retourner l'erreur d'Ollama si elle existe
                ollama_error_message = api_response.get("error")
                if ollama_error_message:
                    return f"Ollama a retourné une erreur : {ollama_error_message}"
                return f"Désolé {user_nick}, je n'ai pas pu générer de réponse (contenu vide ou format non reconnu)."

            # Si on arrive ici, bot_response a quelque chose.
            logging.info(f"Réponse d'Ollama (contenu extrait): {bot_response[:200]}{'...' if len(bot_response) > 200 else ''}")
            self._add_to_history(channel, self.connection.get_nickname(), bot_response, role="assistant")
            return bot_response.strip()

        except json.JSONDecodeError: # Si la réponse n'est pas du JSON valide
            logging.error(f"Impossible de décoder la réponse JSON d'Ollama. Statut HTTP: {response.status_code}. Réponse texte: {response.text[:500]}")
            return f"Désolé {user_nick}, Ollama a renvoyé une réponse non-JSON."
        
    def _add_to_history(self, channel: str, nick: str, message: str, role: str = "user"):
        if channel not in conversation_history:
            conversation_history[channel] = []
        
        conversation_history[channel].append({
            "role": role, 
            "name": nick, 
            "content": message, 
            "timestamp": time.time()
        })
        
        # Limiter la taille de l'historique par canal (nombre total de messages)
        max_hist_size = self.ollama_context_messages_count * 2 # Un peu plus que le contexte envoyé
        if len(conversation_history[channel]) > max_hist_size:
            conversation_history[channel] = conversation_history[channel][-max_hist_size:]

    def on_pubmsg(self, c: ServerConnection, e: Event):
        user_nick = e.source.nick
        channel = e.target
        message_text = e.arguments[0]
        logging.debug(f"Message brut reçu: [{channel}] <{user_nick}> {message_text}")  # <-- Nouveau log
        logging.info(f"[{channel}] <{user_nick}> {message_text}")

        # Filtrage des nicks bloqués
        if user_nick in self.security_config.get("blocked_nicks", []):
            logging.warning(f"Message de {user_nick} (nick bloqué) ignoré dans {channel}.")
            return

        # Ignorer ses propres messages ou ceux d'autres bots (heuristique simple)
        if user_nick == c.get_nickname() or "bot" in user_nick.lower() and user_nick != c.get_nickname(): # Ne pas s'ignorer si on a "bot" dans le nom
            return

        # Ajouter le message de l'utilisateur à l'historique APRÈS les filtres
        self._add_to_history(channel, user_nick, message_text, role="user")

        # Filtrage de spam basique
        spam_keywords = self.security_config.get("spam_filter_keywords", [])
        for keyword in spam_keywords:
            if keyword.lower() in message_text.lower():
                logging.warning(f"Message de {user_nick} dans {channel} détecté comme spam potentiel (mot-clé: '{keyword}'): {message_text}")
                # Optionnel: c.kick(channel, user_nick, "Message contenant du spam.")
                return # Ne pas répondre au spam

        # Gestion des commandes
        if message_text.startswith(self.command_prefix):
            parts = message_text.split(" ", 1)
            command = parts[0][len(self.command_prefix):].lower()
            args = parts[1] if len(parts) > 1 else ""
            self.handle_command(c, channel, user_nick, command, args)
        # Interpellation directe (si le message commence par le pseudo du bot)
        #elif message_text.lower().startswith(c.get_nickname().lower()):
        elif message_text.lower().startswith(c.get_nickname().lower() + ":") or message_text.lower().startswith(c.get_nickname().lower() + ","):
            prompt = message_text[len(c.get_nickname()):].strip()
            if prompt and (prompt.startswith(":") or prompt.startswith(",")):
                prompt = prompt[1:].strip()
            
            if prompt: # S'il y a quelque chose après le nom du bot
                logging.info(f"Interpellation directe par {user_nick} dans {channel}: '{prompt}'")
                response = self.get_ollama_response(user_nick, prompt, channel)
                if response:
                    self._send_message_with_rate_limit(c, channel, f"{user_nick}: {response}")
            else: # Juste le nom du bot, sans rien d'autre
                 self._send_message_with_rate_limit(c, channel, f"{user_nick}: Oui ? Vous m'avez appelé ? Essayez '{self.command_prefix}aide' ou posez-moi une question.")


    def handle_command(self, c: ServerConnection, channel: str, nick: str, command: str, args: str):
        logging.info(f"Commande reçue de {nick} dans {channel}: !{command} {args}")
        if command == "aide" or command == "help":
            self._send_message_with_rate_limit(c, channel, 
                f"{nick}: Commandes disponibles: {self.command_prefix}ping, {self.command_prefix}aide, {self.command_prefix}info. "
                f"Pour discuter, mentionnez mon pseudo ({c.get_nickname()}) suivi de votre message."
            )
        elif command == "ping":
            self._send_message_with_rate_limit(c, channel, f"{nick}: Pong!")
        elif command == "info" or command == "source":
            self._send_message_with_rate_limit(c, channel, 
                f"{nick}: Je suis un chatbot Python utilisant Ollama (modèle: {self.ollama_model}). "
                f"Développé pour être intelligent et contextuel. Version 0.2-dev."
            )
        # --- Exemple d'extension pour futurs modules ---
        # elif command == "meteo" and hasattr(self, "weather_module"):
        #     if args:
        #         weather_info = self.weather_module.get_weather(args)
        #         self._send_message_with_rate_limit(c, channel, f"{nick}: {weather_info}")
        #     else:
        #         self._send_message_with_rate_limit(c, channel, f"{nick}: Veuillez spécifier une ville pour la météo. Ex: {self.command_prefix}meteo Paris")
        else:
            self._send_message_with_rate_limit(c, channel, f"{nick}: Commande '{command}' inconnue. Tapez {self.command_prefix}aide pour la liste des commandes.")
    
    def on_ctcp(self, c: ServerConnection, e: Event):
        """Répond aux requêtes CTCP courantes comme VERSION."""
        nick = e.source.nick
        ctcp_command = e.arguments[0].upper()
        if ctcp_command == "VERSION":
            logging.info(f"Réception d'une requête CTCP VERSION de {nick}")
            c.ctcp_reply(nick, f"VERSION OllamaIRCBotPy:0.2-dev - Python {irc.client.VERSION_STRING}")
        elif ctcp_command == "PING":
            if len(e.arguments) > 1:
                c.ctcp_reply(nick, f"PING {e.arguments[1]}")


def main():
    load_config()
    setup_logging()

    irc_cfg = config.get("irc", {})
    bot_cfg = config.get("bot_settings", {})

    server = irc_cfg.get("server")
    port = irc_cfg.get("port")
    use_ssl = irc_cfg.get("use_ssl", False)
    nickname = irc_cfg.get("nickname")
    realname = irc_cfg.get("realname", nickname)
    channels = irc_cfg.get("channels", [])
    server_password = irc_cfg.get("password") # Renommé pour clarté
    nickserv_password = irc_cfg.get("nickserv_password")

    if not all([server, port is not None, nickname, channels]): # port peut être 0, donc `is not None`
        logging.critical("Paramètres IRC essentiels manquants dans la configuration (server, port, nickname, channels). Arrêt.")
        return

    reconnect_min_delay = bot_cfg.get("reconnect_min_delay", 15)
    reconnect_max_delay = bot_cfg.get("reconnect_max_delay", 300)
    reconnect_attempts_config = bot_cfg.get("reconnect_attempts", 10) # 0 ou négatif pour infini
    
    current_reconnect_delay = reconnect_min_delay
    attempts = 0

    while True:
        if reconnect_attempts_config > 0 and attempts >= reconnect_attempts_config:
            logging.critical(f"Nombre maximum de tentatives de reconnexion ({reconnect_attempts_config}) atteint. Arrêt du bot.")
            break
        
        bot = None # S'assurer que bot est réinitialisé
        try:
            logging.info(f"Tentative de connexion à {server}:{port} (essai {attempts + 1})...")
            bot = OllamaIRCBot(
                channels, nickname, server, port, 
                use_ssl=use_ssl, 
                realname=realname, 
                server_password=server_password, 
                nickserv_password=nickserv_password
            )
            # bot.load_modules_if_any() # Si vous implémentez un système de modules
            bot.start() # Bloquant jusqu'à la déconnexion ou une erreur fatale interne à la lib
            
            # Si bot.start() se termine "normalement" (déconnexion propre ou kick non géré pour rejoin)
            logging.warning("Le bot s'est arrêté ou a été déconnecté. Tentative de reconnexion...")
            # Réinitialiser le délai après une déconnexion "normale"
            current_reconnect_delay = reconnect_min_delay
            # On ne compte pas cela comme une tentative de reconnexion "ratée"
            # attempts +=1 # Décommentez si vous voulez compter chaque déconnexion

        except (irc.client.ServerConnectionError, ConnectionRefusedError, ssl.SSLError, TimeoutError) as e:
            logging.error(f"Erreur de connexion au serveur IRC: {e}. Nouvelle tentative...")
            attempts += 1
        except Exception as e:
            logging.critical(f"Une erreur critique non gérée est survenue dans la boucle principale: {e}", exc_info=True)
            attempts += 1
            # Il pourrait être sage d'arrêter le bot ici si l'erreur est vraiment inconnue/grave.
            # break 
        
        if bot and bot.connection.connected: # Si une erreur s'est produite mais que la connexion est toujours active (peu probable ici)
            bot.disconnect("Arrêt suite à une erreur et tentative de redémarrage.")
        
        logging.info(f"Attente de {current_reconnect_delay} secondes avant la prochaine tentative.")
        time.sleep(current_reconnect_delay)
        # Augmenter le délai pour la prochaine fois (backoff exponentiel simple)
        current_reconnect_delay = min(current_reconnect_delay * 2, reconnect_max_delay)
        # Ajouter un peu de jitter pour éviter les "thundering herd" si plusieurs bots redémarrent
        current_reconnect_delay += random.randint(0, int(current_reconnect_delay * 0.1))
        current_reconnect_delay = min(current_reconnect_delay, reconnect_max_delay)


if __name__ == "__main__":
    main()