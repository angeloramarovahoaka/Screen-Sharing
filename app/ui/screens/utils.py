import os

def ui_debug(msg: str):
    """Fonction utilitaire pour le debug UI"""
    if os.getenv("SS_UI_DEBUG", "0") == "1":
        print(f"[UI_DEBUG] {msg}", flush=True)