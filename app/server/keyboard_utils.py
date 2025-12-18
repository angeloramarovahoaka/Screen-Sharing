"""
app/server/keyboard_utils.py
Mapping des touches et gestion des touches spéciales
"""
import platform
from pynput.keyboard import Key

if platform.system() == 'Windows':
    import ctypes

# Mapping complet incluant les alias Windows
KEY_MAPPING = {
    'enter': Key.enter,
    'return': Key.enter,
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
    
    # --- LES ALIAS CRUCIAUX POUR WINDOWS ---
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
    'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
    'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
    'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
}

# Ajout de 'win'/'windows' dans les modificateurs
MODIFIER_KEYS = (
    'ctrl', 'ctrl_l', 'ctrl_r',
    'alt', 'alt_l', 'alt_r', 'alt_gr',
    'shift', 'shift_l', 'shift_r',
    'cmd', 'cmd_l', 'cmd_r', 
    'win', 'windows', 'super', 'meta'
)

ARROW_KEYS = ('arrow_left', 'arrow_up', 'arrow_right', 'arrow_down', 'left', 'right', 'up', 'down')

VK_ARROW_CODES = {
    'arrow_left': 0x25, 'arrow_up': 0x26, 'arrow_right': 0x27, 'arrow_down': 0x28,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28
}

def get_pynput_key(key_name: str):
    if not key_name: return None
    key_name = str(key_name).lower()
    return KEY_MAPPING.get(key_name, key_name)

def press_arrow_key_windows(direction: str) -> bool:
    if platform.system() != 'Windows': return False
    d = str(direction).lower()
    if d in VK_ARROW_CODES:
        ctypes.windll.user32.keybd_event(VK_ARROW_CODES[d], 0, 0, 0)
        return True
    return False

def release_arrow_key_windows(direction: str) -> bool:
    if platform.system() != 'Windows': return False
    d = str(direction).lower()
    if d in VK_ARROW_CODES:
        ctypes.windll.user32.keybd_event(VK_ARROW_CODES[d], 0, 0x0002, 0)
        return True
    return False

def is_modifier_key(key_name: str) -> bool:
    return str(key_name).lower() in MODIFIER_KEYS

def is_arrow_key(key_name: str) -> bool:
    return str(key_name).lower() in ARROW_KEYS