"""
Gestionnaire de commandes - Exécution des commandes souris et clavier
"""
import platform
import time
import logging
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController
import os

from .keyboard_utils import (
    get_pynput_key,
    press_arrow_key_windows,
    release_arrow_key_windows,
    press_win_windows,
    release_win_windows,
    is_modifier_key,
    is_arrow_key,
    MODIFIER_KEYS
)

logger = logging.getLogger("screenshare.server.command")


def _ui_input_debug(msg: str):
    """Log de debug pour les inputs."""
    if os.getenv("SS_INPUT_DEBUG", "0") == "1":
        logger.info(f"[INPUT-SERVER] {msg}")


class CommandHandler:
    """Gère l'exécution des commandes de contrôle distant."""
    
    # Mapping des boutons souris
    BUTTON_MAP = {
        "left": Button.left,
        "right": Button.right,
        "middle": Button.middle
    }
    
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        """Initialise le gestionnaire de commandes.
        
        Args:
            screen_width: Largeur de l'écran pour le calcul des coordonnées
            screen_height: Hauteur de l'écran pour le calcul des coordonnées
        """
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._pressed_modifiers = set()
    
    def update_screen_size(self, width: int, height: int):
        """Met à jour les dimensions de l'écran.
        
        Args:
            width: Nouvelle largeur
            height: Nouvelle hauteur
        """
        self.screen_width = width
        self.screen_height = height
    
    def execute(self, command: dict):
        """Exécute une commande reçue.
        
        Args:
            command: Dictionnaire contenant le type et les paramètres de la commande
        """
        cmd_type = command.get('type')
        
        if cmd_type == 'mouse':
            self._handle_mouse(command)
        elif cmd_type == 'key':
            self._handle_keyboard(command)
    
    def _handle_mouse(self, command: dict):
        """Gère les commandes souris.
        
        Args:
            command: Commande souris avec action, x, y, button
        """
        action = command['action']
        
        if action != 'scroll':
            x = int(command['x'] * self.screen_width)
            y = int(command['y'] * self.screen_height)
            self.mouse.position = (x, y)
        
        if action == 'move':
            pass
        elif action == 'scroll':
            self.mouse.scroll(command.get('dx', 0), command.get('dy', 0))
        else:
            button_str = command.get('button')
            pynput_button = self.BUTTON_MAP.get(button_str)
            
            if pynput_button:
                if action == 'press':
                    self.mouse.press(pynput_button)
                elif action == 'release':
                    self.mouse.release(pynput_button)
    
    def _handle_keyboard(self, command: dict):
        """Gère les commandes clavier.
        
        Args:
            command: Commande clavier avec action, key/keys
        """
        action = command['action']
        _ui_input_debug(f"recv key action={action} payload={command}")
        
        # Support combo atomique: modifiers + main keys en une commande
        if action == 'combo' and isinstance(command.get('keys'), (list, tuple)):
            self._handle_combo(command['keys'])
            return
        
        # Fallback: gestion touche par touche
        if 'keys' in command:
            key_names = command['keys']
        else:
            key_names = [command.get('key')]
        
        for key_name in key_names:
            if not key_name:
                _ui_input_debug("Skipping None key_name")
                continue
            
            # Mise à jour de l'état des modificateurs
            if is_modifier_key(key_name):
                if action == 'press':
                    self._pressed_modifiers.add(key_name)
                elif action == 'release':
                    self._pressed_modifiers.discard(key_name)
            
            _ui_input_debug(f"per-key {action} {key_name}")
            self._execute_key_action(key_name, action)
    
    def _handle_combo(self, key_names: list):
        """Gère une combinaison de touches atomique.
        
        Args:
            key_names: Liste des noms de touches (modificateurs + touches principales)
        """
        # Séparer modificateurs et touches principales
        mods = [k for k in key_names if is_modifier_key(k)]
        mains = [k for k in key_names if not is_modifier_key(k)]
        
        pressed_now = []
        
        # Appuyer sur les modificateurs d'abord
        for m in mods:
            if m not in self._pressed_modifiers:
                mapped = get_pynput_key(m)
                if mapped:
                    try:
                        self.keyboard.press(mapped)
                        self._pressed_modifiers.add(m)
                        pressed_now.append(m)
                    except Exception:
                        logger.exception(f"Failed to press modifier {m}")
                        _ui_input_debug(f"press modifier failed {m}")
        
        # Appuyer et relâcher les touches principales
        for k in mains:
            _ui_input_debug(f"combo main key: {k}")
            self._press_and_release_key(k)
        
        # Relâcher les modificateurs pressés par ce combo
        for m in reversed(pressed_now):
            mapped = get_pynput_key(m)
            if mapped:
                try:
                    self.keyboard.release(mapped)
                except Exception:
                    logger.exception(f"Failed to release modifier {m} after combo")
                    _ui_input_debug(f"release modifier combo failed {m}")
            self._pressed_modifiers.discard(m)
    
    def _press_and_release_key(self, key_name: str):
        """Appuie et relâche une touche.
        
        Args:
            key_name: Nom de la touche
        """
        # Special-case: use native Windows API for arrow keys and Win key
        if is_arrow_key(key_name):
            if platform.system() == 'Windows':
                pressed = press_arrow_key_windows(key_name)
                if pressed:
                    time.sleep(0.005)
                    release_arrow_key_windows(key_name)
                    _ui_input_debug(f"Arrow {key_name} sent via ctypes")
                else:
                    self._pynput_press_release(key_name)
            else:
                self._pynput_press_release(key_name)
        elif key_name in ('win', 'win_l', 'win_r'):
            # Try native Windows Win key synth if available
            if platform.system() == 'Windows':
                pressed = press_win_windows(key_name)
                if pressed:
                    time.sleep(0.005)
                    release_win_windows(key_name)
                    _ui_input_debug(f"Win {key_name} sent via ctypes")
                else:
                    self._pynput_press_release(key_name)
            else:
                self._pynput_press_release(key_name)
        else:
            self._pynput_press_release(key_name)
    
    def _pynput_press_release(self, key_name: str):
        """Appuie et relâche une touche via pynput.
        
        Args:
            key_name: Nom de la touche
        """
        mapped = get_pynput_key(key_name)
        _ui_input_debug(f"Key '{key_name}' mapped to: {mapped}")
        if mapped:
            try:
                self.keyboard.press(mapped)
                time.sleep(0.005)
                self.keyboard.release(mapped)
                _ui_input_debug(f"Key {key_name} sent via pynput")
            except Exception as e:
                logger.exception(f"Failed key {key_name}: {e}")
                _ui_input_debug(f"Key {key_name} FAILED: {e}")
        else:
            _ui_input_debug(f"No mapping for key '{key_name}'")
    
    def _execute_key_action(self, key_name: str, action: str):
        """Exécute une action sur une touche (press ou release).
        
        Args:
            key_name: Nom de la touche
            action: 'press' ou 'release'
        """
        if is_arrow_key(key_name):
            self._execute_arrow_key_action(key_name, action)
        else:
            self._execute_normal_key_action(key_name, action)
    
    def _execute_arrow_key_action(self, key_name: str, action: str):
        """Exécute une action sur une touche directionnelle.
        
        Args:
            key_name: Nom de la touche directionnelle
            action: 'press' ou 'release'
        """
        if platform.system() == 'Windows':
            if action == 'press':
                if not press_arrow_key_windows(key_name):
                    self._pynput_key_action(key_name, action)
            elif action == 'release':
                if not release_arrow_key_windows(key_name):
                    self._pynput_key_action(key_name, action)
        else:
            self._pynput_key_action(key_name, action)
    
    def _execute_normal_key_action(self, key_name: str, action: str):
        """Exécute une action sur une touche normale.
        
        Args:
            key_name: Nom de la touche
            action: 'press' ou 'release'
        """
        self._pynput_key_action(key_name, action)
    
    def _pynput_key_action(self, key_name: str, action: str):
        """Exécute une action sur une touche via pynput.
        
        Args:
            key_name: Nom de la touche
            action: 'press' ou 'release'
        """
        pynput_key = get_pynput_key(key_name)
        _ui_input_debug(f"pynput_key for '{key_name}': {pynput_key}")
        
        # Special-case Win key on Windows: prefer native API
        if key_name in ('win', 'win_l', 'win_r') and platform.system() == 'Windows':
            try:
                if action == 'press':
                    press_win_windows(key_name)
                    _ui_input_debug(f"Pressed native Win {key_name}")
                elif action == 'release':
                    release_win_windows(key_name)
                    _ui_input_debug(f"Released native Win {key_name}")
                return
            except Exception as e:
                logger.exception(f"Native Win key action failed: {e}")

        if pynput_key:
            try:
                if action == 'press':
                    self.keyboard.press(pynput_key)
                    _ui_input_debug(f"Pressed {key_name} -> {pynput_key}")
                elif action == 'release':
                    self.keyboard.release(pynput_key)
                    _ui_input_debug(f"Released {key_name} -> {pynput_key}")
            except Exception as e:
                logger.error(f"Failed to execute key action {action} for {key_name}: {e}")
                _ui_input_debug(f"FAILED {action} {key_name}: {e}")
        else:
            logger.warning(f"Could not map key_name '{key_name}' to pynput key")
            _ui_input_debug(f"No mapping for '{key_name}'")
