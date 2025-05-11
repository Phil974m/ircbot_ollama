import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os

CONFIG_FILE = "config.json"

class ConfigEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Éditeur de Configuration Ollama IRC Bot")
        # Augmenter légèrement la taille de la fenêtre initiale
        self.root.geometry("650x750")


        self.config_data = {}
        self.vars = {} # Pour stocker les StringVar, IntVar, etc.

        # --- Menu ---
        menubar = tk.Menu(root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Charger", command=self.load_config_from_file)
        filemenu.add_command(label="Sauvegarder", command=self.save_config_to_file)
        filemenu.add_separator()
        filemenu.add_command(label="Quitter", command=root.quit)
        menubar.add_cascade(label="Fichier", menu=filemenu)
        root.config(menu=menubar)

        # --- Panneau principal avec scrollbar ---
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.create_widgets()
        self.load_config() # Charger la configuration au démarrage

    def create_entry(self, parent, label_text, section, key, default_value="", var_type=tk.StringVar, row=None, col_offset=0, width=40):
        """Crée une étiquette et un champ d'entrée."""
        if row is None:
            row = parent.grid_size()[1] # Prochaine ligne disponible

        label = ttk.Label(parent, text=label_text)
        label.grid(row=row, column=0 + col_offset, sticky="w", padx=5, pady=2)
        
        var = var_type()
        self.vars[f"{section}_{key}"] = var
        
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=1 + col_offset, sticky="ew", padx=5, pady=2)
        parent.grid_columnconfigure(1 + col_offset, weight=1) # Permet à l'entrée de s'étendre

        # Initialiser avec la valeur par défaut si la clé n'est pas dans config_data
        # Ceci sera écrasé par load_config si la clé existe
        if section not in self.config_data:
            self.config_data[section] = {}
        if key not in self.config_data[section]:
             self.config_data[section][key] = default_value
        var.set(self.config_data[section].get(key, default_value))


    def create_checkbutton(self, parent, label_text, section, key, default_value=False, row=None, col_offset=0):
        """Crée une étiquette et une case à cocher."""
        if row is None:
            row = parent.grid_size()[1]

        var = tk.BooleanVar()
        self.vars[f"{section}_{key}"] = var
        
        check = ttk.Checkbutton(parent, text=label_text, variable=var)
        check.grid(row=row, column=0 + col_offset, columnspan=2, sticky="w", padx=5, pady=2)

        if section not in self.config_data:
            self.config_data[section] = {}
        if key not in self.config_data[section]:
            self.config_data[section][key] = default_value
        var.set(self.config_data[section].get(key, default_value))


    def create_widgets(self):
        # --- Section IRC ---
        irc_frame = ttk.LabelFrame(self.scrollable_frame, text="Configuration IRC", padding=10)
        irc_frame.pack(fill="x", expand=True, padx=10, pady=5)

        self.create_entry(irc_frame, "Serveur:", "irc", "server", "irc.libera.chat")
        self.create_entry(irc_frame, "Port:", "irc", "port", 6697, var_type=tk.IntVar)
        self.create_checkbutton(irc_frame, "Utiliser SSL", "irc", "use_ssl", True)
        self.create_entry(irc_frame, "Pseudo (Nickname):", "irc", "nickname", "OllamaBotTk")
        self.create_entry(irc_frame, "Nom réel:", "irc", "realname", "Ollama Python Bot")
        self.create_entry(irc_frame, "Canaux (séparés par virgule):", "irc", "channels_str", "#canal1,#canal2")
        self.create_entry(irc_frame, "Mot de passe serveur (si requis):", "irc", "password", "")
        self.create_entry(irc_frame, "Mot de passe NickServ:", "irc", "nickserv_password", "")
        self.create_entry(irc_frame, "Préfixe Commande:", "irc", "command_prefix", "!")

        # --- Section Ollama ---
        ollama_frame = ttk.LabelFrame(self.scrollable_frame, text="Configuration Ollama", padding=10)
        ollama_frame.pack(fill="x", expand=True, padx=10, pady=5)

        self.create_entry(ollama_frame, "URL API Ollama:", "ollama", "api_url", "http://localhost:11434/api/chat")
        self.create_entry(ollama_frame, "Modèle Ollama:", "ollama", "model", "llama3:latest")
        self.create_entry(ollama_frame, "Prompt Système par Défaut:", "ollama", "default_system_prompt", "Tu es un assistant IA utile.")
        # Pour channel_tones, une gestion plus complexe serait nécessaire. Ici, on simplifie.
        self.create_entry(ollama_frame, "Tons Spécifiques (JSON simple; ex: {\"#canal\":\"ton\"}):", "ollama", "channel_tones_str", "{}")
        self.create_entry(ollama_frame, "Nb Messages Contexte:", "ollama", "context_messages_count", 7, var_type=tk.IntVar)
        self.create_entry(ollama_frame, "Timeout Requête (sec):", "ollama", "request_timeout", 90, var_type=tk.IntVar)


        # --- Section Paramètres Bot ---
        bot_settings_frame = ttk.LabelFrame(self.scrollable_frame, text="Paramètres du Bot", padding=10)
        bot_settings_frame.pack(fill="x", expand=True, padx=10, pady=5)

        self.create_entry(bot_settings_frame, "Niveau de Log (DEBUG, INFO, etc.):", "bot_settings", "log_level", "INFO")
        self.create_entry(bot_settings_frame, "Fichier de Log:", "bot_settings", "log_file", "ollama_irc_bot.log")
        self.create_entry(bot_settings_frame, "Délai Reconnexion Min (sec):", "bot_settings", "reconnect_min_delay", 15, var_type=tk.IntVar)
        self.create_entry(bot_settings_frame, "Délai Reconnexion Max (sec):", "bot_settings", "reconnect_max_delay", 300, var_type=tk.IntVar)
        self.create_entry(bot_settings_frame, "Tentatives Reconnexion (0=infini):", "bot_settings", "reconnect_attempts", 0, var_type=tk.IntVar)
        self.create_entry(bot_settings_frame, "Délai Anti-Flood (sec):", "bot_settings", "message_rate_limit_delay", 1.2, var_type=tk.DoubleVar)

        # --- Section Sécurité ---
        security_frame = ttk.LabelFrame(self.scrollable_frame, text="Sécurité", padding=10)
        security_frame.pack(fill="x", expand=True, padx=10, pady=5)
        self.create_entry(security_frame, "Mots-clés Spam (séparés par virgule):", "security", "spam_filter_keywords_str", "spam1,spam2")
        self.create_entry(security_frame, "Nicks Bloqués (séparés par virgule):", "security", "blocked_nicks_str", "Troll1,BotSpammer")

        # --- Boutons ---
        button_frame = ttk.Frame(self.scrollable_frame, padding=10)
        button_frame.pack(fill="x")

        save_button = ttk.Button(button_frame, text="Sauvegarder Configuration", command=self.save_config)
        save_button.pack(side="left", padx=5)

        load_button = ttk.Button(button_frame, text="Recharger depuis Fichier", command=self.load_config_from_ui) # Recharge depuis le fichier
        load_button.pack(side="left", padx=5)

        default_button = ttk.Button(button_frame, text="Restaurer Défauts", command=self.load_default_config_into_ui)
        default_button.pack(side="left", padx=5)


    def get_default_config(self):
        """Retourne une structure de configuration par défaut."""
        return {
            "irc": {
                "server": "irc.libera.chat", "port": 6697, "use_ssl": True,
                "nickname": "OllamaBotDefault", "realname": "Ollama Python Bot",
                "channels": ["#ollama-testing"], # Sera géré via channels_str
                "password": None, "nickserv_password": "", "command_prefix": "!"
            },
            "ollama": {
                "api_url": "http://localhost:11434/api/chat", "model": "llama3:latest",
                "default_system_prompt": "Tu es un assistant IA utile.",
                "channel_tones": {}, # Sera géré via channel_tones_str
                "context_messages_count": 7, "request_timeout": 90
            },
            "bot_settings": {
                "log_level": "INFO", "log_file": "ollama_irc_bot.log",
                "reconnect_min_delay": 15, "reconnect_max_delay": 300,
                "reconnect_attempts": 0, "message_rate_limit_delay": 1.2
            },
            "security": {
                "spam_filter_keywords": [], # Sera géré via spam_filter_keywords_str
                "blocked_nicks": [] # Sera géré via blocked_nicks_str
            }
        }

    def load_default_config_into_ui(self):
        if messagebox.askyesno("Restaurer Défauts", "Voulez-vous vraiment charger les valeurs par défaut dans l'interface ? Les modifications non sauvegardées seront perdues."):
            self.config_data = self.get_default_config()
            self.populate_ui_from_config()
            messagebox.showinfo("Information", "Valeurs par défaut chargées dans l'interface. N'oubliez pas de sauvegarder si vous souhaitez les appliquer au fichier.")


    def load_config(self, filepath=CONFIG_FILE):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
            else:
                messagebox.showinfo("Information", f"Fichier '{filepath}' non trouvé. Utilisation d'une configuration par défaut.")
                self.config_data = self.get_default_config()
                # Optionnel: sauvegarder immédiatement le fichier par défaut
                # self.save_config_to_file(filepath, self.config_data) 
            self.populate_ui_from_config()
        except json.JSONDecodeError:
            messagebox.showerror("Erreur", f"Impossible de lire '{filepath}'. Le fichier n'est pas un JSON valide.")
            self.config_data = self.get_default_config()
            self.populate_ui_from_config()
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du chargement de la configuration: {e}")
            self.config_data = self.get_default_config()
            self.populate_ui_from_config()

    def load_config_from_file(self):
        filepath = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")],
            initialfile=CONFIG_FILE,
            title="Charger un fichier de configuration"
        )
        if filepath:
            self.load_config(filepath)

    def load_config_from_ui(self):
        """Recharge la configuration depuis le fichier CONFIG_FILE actuel dans l'UI"""
        if messagebox.askyesno("Recharger", f"Recharger la configuration depuis '{CONFIG_FILE}' ? Les modifications non sauvegardées dans l'interface seront perdues."):
            self.load_config(CONFIG_FILE)


    def populate_ui_from_config(self):
        """Met à jour les widgets de l'interface avec les données de self.config_data."""
        for section, keys in self.config_data.items():
            if not isinstance(keys, dict): continue # S'assurer que c'est bien un dictionnaire de section
            for key, value in keys.items():
                var_name = f"{section}_{key}"
                if var_name in self.vars:
                    self.vars[var_name].set(value)
                # Gestion spéciale pour les listes transformées en chaînes
                elif key == "channels" and "irc_channels_str" in self.vars:
                    self.vars["irc_channels_str"].set(",".join(value) if isinstance(value, list) else "")
                elif key == "spam_filter_keywords" and "security_spam_filter_keywords_str" in self.vars:
                    self.vars["security_spam_filter_keywords_str"].set(",".join(value) if isinstance(value, list) else "")
                elif key == "blocked_nicks" and "security_blocked_nicks_str" in self.vars:
                    self.vars["security_blocked_nicks_str"].set(",".join(value) if isinstance(value, list) else "")
                elif key == "channel_tones" and "ollama_channel_tones_str" in self.vars:
                     try:
                        self.vars["ollama_channel_tones_str"].set(json.dumps(value) if isinstance(value, dict) else "{}")
                     except TypeError:
                        self.vars["ollama_channel_tones_str"].set("{}")


    def collect_data_from_ui(self):
        """Récupère les données depuis les widgets de l'interface et les met à jour dans self.config_data."""
        temp_config_data = self.get_default_config() # Commencer avec une structure valide

        for var_key, tk_var in self.vars.items():
            section, key = var_key.split("_", 1)
            if section not in temp_config_data: temp_config_data[section] = {}
            
            value = tk_var.get()

            # Cas spéciaux pour les conversions
            if key == "channels_str":
                temp_config_data[section]["channels"] = [c.strip() for c in value.split(',') if c.strip()]
            elif key == "spam_filter_keywords_str":
                 temp_config_data[section]["spam_filter_keywords"] = [c.strip() for c in value.split(',') if c.strip()]
            elif key == "blocked_nicks_str":
                 temp_config_data[section]["blocked_nicks"] = [c.strip() for c in value.split(',') if c.strip()]
            elif key == "channel_tones_str":
                try:
                    temp_config_data[section]["channel_tones"] = json.loads(value) if value.strip() else {}
                except json.JSONDecodeError:
                    messagebox.showwarning("Avertissement Format", f"Le format JSON pour 'Tons Spécifiques' est invalide. La valeur '{value}' sera ignorée.")
                    temp_config_data[section]["channel_tones"] = self.config_data.get(section, {}).get("channel_tones", {}) # Conserver l'ancienne valeur valide
            elif isinstance(tk_var, tk.IntVar):
                try:
                    temp_config_data[section][key] = int(value)
                except ValueError:
                    messagebox.showwarning("Avertissement Format", f"La valeur pour '{section}.{key}' doit être un entier. La valeur '{value}' est ignorée.")
                    temp_config_data[section][key] = self.config_data.get(section, {}).get(key, 0) # Conserver l'ancienne ou 0
            elif isinstance(tk_var, tk.DoubleVar):
                try:
                    temp_config_data[section][key] = float(value)
                except ValueError:
                     messagebox.showwarning("Avertissement Format", f"La valeur pour '{section}.{key}' doit être un nombre flottant. La valeur '{value}' est ignorée.")
                     temp_config_data[section][key] = self.config_data.get(section, {}).get(key, 0.0) # Conserver l'ancienne ou 0.0
            elif isinstance(tk_var, tk.BooleanVar):
                 temp_config_data[section][key] = bool(value)
            else: # tk.StringVar
                 # Gérer le cas où "null" est entré pour un mot de passe ou une valeur optionnelle
                 if (section == "irc" and key == "password") and (value.strip().lower() == "null" or not value.strip()):
                     temp_config_data[section][key] = None
                 else:
                    temp_config_data[section][key] = str(value)

        return temp_config_data

    def save_config(self):
        """Sauvegarde la configuration actuelle de l'interface dans le fichier."""
        updated_config_data = self.collect_data_from_ui()
        self.save_config_to_file(CONFIG_FILE, updated_config_data)


    def save_config_to_file(self, filepath=CONFIG_FILE, data_to_save=None):
        if data_to_save is None:
            data_to_save = self.collect_data_from_ui()
        
        # Demander où sauvegarder si le fichier est celui par défaut pour la première fois
        # ou si l'utilisateur a choisi "Sauvegarder" depuis le menu.
        # Si filepath est déjà spécifié (ex: après un "Charger"), on l'utilise.
        
        # Pour une première sauvegarde ou via menu "Sauvegarder"
        if filepath == CONFIG_FILE and (not os.path.exists(CONFIG_FILE) or data_to_save is None): # data_to_save is None est un peu une heuristique pour le menu
             _filepath = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")],
                initialfile=CONFIG_FILE,
                title="Sauvegarder la configuration sous..."
            )
             if not _filepath: # L'utilisateur a annulé
                 return
             filepath = _filepath


        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Succès", f"Configuration sauvegardée dans '{filepath}'")
            self.config_data = data_to_save # Mettre à jour la config interne
        except Exception as e:
            messagebox.showerror("Erreur de Sauvegarde", f"Impossible de sauvegarder la configuration : {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigEditorApp(root)
    root.mainloop()