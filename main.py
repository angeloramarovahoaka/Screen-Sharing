"""
Screen Sharing Remote Desktop Application
Point d'entrée principal

Fonctionnalités:
- Login/Logout
- Liste des écrans partagés
- Zoom d'un écran spécifique
- Manipulation d'un écran (souris, clavier)
- Appel audio

Usage:
    python main.py
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.ui_login import LoginWindow
from app.ui_main import MainWindow
from app.config import app_state


class ScreenSharingApp:
    """
    Application principale de Screen Sharing
    Gère le flux entre Login et MainWindow
    """
    
    def __init__(self):
        # Créer l'application Qt
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Screen Sharing")
        self.app.setOrganizationName("ScreenShare")
        
        # Style global
        self.app.setStyle("Fusion")
        
        # Police par défaut
        font = QFont("Segoe UI", 10)
        self.app.setFont(font)
        
        # Style global de l'application
        self.app.setStyleSheet("""
            QMainWindow {
                background-color: #fafafa;
            }
            QToolTip {
                background-color: #333;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #f0f0f0;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                border: none;
                background-color: #f0f0f0;
                height: 10px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background-color: #c0c0c0;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)
        
        # Fenêtres
        self.login_window = None
        self.main_window = None
        
    def run(self):
        """Lance l'application"""
        self.show_login()
        return self.app.exec()
        
    def show_login(self):
        """Affiche la fenêtre de connexion"""
        # Fermer la fenêtre principale si elle existe
        if self.main_window:
            self.main_window.close()
            self.main_window = None
            
        # Créer et afficher la fenêtre de connexion
        self.login_window = LoginWindow()
        self.login_window.login_successful.connect(self.on_login_success)
        self.login_window.show()
        
    def on_login_success(self, username):
        """Callback après connexion réussie"""
        # Fermer la fenêtre de connexion
        if self.login_window:
            self.login_window.close()
            self.login_window = None
            
        # Créer et afficher la fenêtre principale
        self.main_window = MainWindow()
        self.main_window.set_user(username)
        self.main_window.show()
        
        # Connecter le signal de déconnexion pour revenir à l'écran de login
        try:
            self.main_window.logged_out.connect(self.show_login)
        except Exception:
            pass

        # Surveiller la fermeture au cas où la fenêtre serait fermée autrement
        self.main_window.destroyed.connect(self.on_main_window_closed)
        
    def on_main_window_closed(self):
        """Callback quand la fenêtre principale est fermée"""
        if not app_state.is_logged_in():
            # Revenir au login si déconnecté
            self.show_login()


def main():
    """Point d'entrée principal"""
    app = ScreenSharingApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
