"""
Utilitaires clavier - Mapping des touches et gestion des touches spéciales
"""
import platform
from pynput.keyboard import Key

# Import pour la gestion des touches spéciales sur Windows
if platform.system() == 'Windows':
    import ctypes


# Mapping des touches spéciales vers pynput
KEY_MAPPING = {
    'enter': Key.enter,
    'return': Key.enter, # Alias souvent utilisé
    'backspace': Key.backspace,
    'tab': Key.tab,
    'esc': Key.esc,
    'escape': Key.esc,
    'space': Key.space,
    'delete': Key.delete,
    'del': Key.delete,
    'home': Key.home,
    'end': Key.end,
    'left': Key.left,
    'right': Key.right,
    'up': Key.up,
    'down': Key.down,
    'arrow_left': Key.left,
    'arrow_right': Key.right,
    'arrow_up': Key.up,
    'arrow_down': Key.down,
    'page_up': Key.page_up,
    'page_down': Key.page_down,
    'shift': Key.shift_l,
    'shift_l': Key.shift_l,
    'shift_r': Key.shift_r,
    'ctrl': Key.ctrl_l,
    'ctrl_l': Key.ctrl_l,
    'ctrl_r': Key.ctrl_r,
    'alt': Key.alt_l,
    'alt_l': Key.alt_l,
    'alt_r': Key.alt_r,
    'alt_gr': Key.alt_gr,
    
    # --- CORRECTION ICI : Alias complets pour la touche Windows ---
    'cmd': Key.cmd,
    'cmd_l': Key.cmd,
    'cmd_r': Key.cmd_r,
    'win': Key.cmd,       # Indispensable
    'windows': Key.cmd,   # Indispensable
    'super': Key.cmd,     # Linux
    'meta': Key.cmd,
    'menu': Key.menu,
    
    'caps_lock': Key.caps_lock,
    'num_lock': Key.num_lock,
    'insert': Key.insert,
    'pause': Key.pause,
    'print_screen': Key.print_screen,
    'f1': Key.f1,
    'f2': Key.f2,
    'f3': Key.f3,
    'f4': Key.f4,
    'f5': Key.f5,
    'f6': Key.f6,
    'f7': Key.f7,
    'f8': Key.f8,
    'f9': Key.f9,
    'f10': Key.f10,
    'f11': Key.f11,
    'f12': Key.f12,
}

# Liste des modificateurs
# --- CORRECTION ICI : Ajout de win/windows/super ---
MODIFIER_KEYS = (
    'ctrl', 'ctrl_l', 'ctrl_r',
    'alt', 'alt_l', 'alt_r', 'alt_gr',
    'shift', 'shift_l', 'shift_r',
    'cmd', 'cmd_l', 'cmd_r', 
    'win', 'windows', 'super', 'meta'
)

# Touches directionnelles
ARROW_KEYS = ('arrow_left', 'arrow_up', 'arrow_right', 'arrow_down', 'left', 'right', 'up', 'down')

# Codes virtuels Windows pour les touches directionnelles
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
KEYEVENTF_KEYUP = 0x0002

VK_ARROW_CODES = {
    'arrow_left': VK_LEFT,
    'arrow_up': VK_UP,
    'arrow_right': VK_RIGHT,
    'arrow_down': VK_DOWN,
    'left': VK_LEFT,
    'up': VK_UP,
    'right': VK_RIGHT,
    'down': VK_DOWN
}


def get_pynput_key(key_name: str):
    """Convertit une chaîne en objet pynput Key ou caractère."""
    if not key_name:
        return None
    # Normaliser en minuscules pour éviter les erreurs "Win" vs "win"
    key_name = str(key_name).lower()
    
    if key_name in KEY_MAPPING:
        return KEY_MAPPING[key_name]
    return key_name


def press_arrow_key_windows(direction: str) -> bool:
    if platform.system() != 'Windows':
        return False
    direction = str(direction).lower()
    if direction in VK_ARROW_CODES:
        ctypes.windll.user32.keybd_event(VK_ARROW_CODES[direction], 0, 0, 0)
        return True
    return False


def release_arrow_key_windows(direction: str) -> bool:
    if platform.system() != 'Windows':
        return False
    direction = str(direction).lower()
    if direction in VK_ARROW_CODES:
        ctypes.windll.user32.keybd_event(VK_ARROW_CODES[direction], 0, KEYEVENTF_KEYUP, 0)
        return True
    return False


def is_modifier_key(key_name: str) -> bool:
    if not key_name: return False
    return str(key_name).lower() in MODIFIER_KEYS


def is_arrow_key(key_name: str) -> bool:
    if not key_name: return False
    return str(key_name).lower() in ARROW_KEYS