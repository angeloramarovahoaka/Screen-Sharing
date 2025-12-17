"""
Interface de connexion - Login/Logout
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QPixmap, QPalette, QColor

from .config import USERS, app_state
from .ui_style import THEME, button_solid


class LoginWindow(QWidget):
    """
    Fenêtre de connexion de l'application
    """
    login_successful = Signal(str)  # Émet le nom d'utilisateur
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screen Sharing - Connexion")
        # Allow window to expand so wrapped text isn't clipped; keep a reasonable minimum
        self.setMinimumSize(400, 480)
        self.setup_ui()
        self.apply_style()
        
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(12)
        
        # Logo / Titre
        title_label = QLabel("🖥️ Screen Sharing")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont("Segoe UI", 24, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {THEME.primary};")
        main_layout.addWidget(title_label)
        
        # Sous-titre
        subtitle_label = QLabel("Remote Desktop Application")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_font = QFont("Segoe UI", 10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #666;")
        main_layout.addWidget(subtitle_label)
        
        # Espace
        main_layout.addSpacing(12)
        
        # Frame de connexion
        login_frame = QFrame()
        login_frame.setFrameShape(QFrame.StyledPanel)
        # Remove padding from CSS (Qt doesn't handle it well for QFrame children)
        login_frame.setStyleSheet("""
            QFrame#loginFrame {
                background-color: #f5f5f5;
                border-radius: 10px;
            }
        """)
        login_frame.setObjectName("loginFrame")
        login_layout = QVBoxLayout(login_frame)
        login_layout.setSpacing(12)
        # Use layout margins instead of CSS padding
        login_layout.setContentsMargins(20, 20, 20, 20)
        
        # Champ utilisateur
        user_label = QLabel("👤 Nom d'utilisateur")
        user_label.setFont(QFont("Segoe UI", 10))
        user_label.setStyleSheet("color: #111; background: transparent;")
        login_layout.addWidget(user_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Entrez votre nom d'utilisateur")
        self.username_input.setStyleSheet("color: #111;")
        self.username_input.setMinimumHeight(40)
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())
        login_layout.addWidget(self.username_input)
        
        # Champ mot de passe
        pass_label = QLabel("🔒 Mot de passe")
        pass_label.setFont(QFont("Segoe UI", 10))
        pass_label.setStyleSheet("color: #111; background: transparent;")
        login_layout.addWidget(pass_label)

        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Entrez votre mot de passe")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(40)
        self.password_input.returnPressed.connect(self.handle_login)
        # Add a small row with the password input and a show/hide toggle button
        pw_row = QHBoxLayout()
        pw_row.setContentsMargins(0, 0, 0, 0)
        pw_row.setSpacing(8)
        pw_row.addWidget(self.password_input)

        self.pw_toggle = QPushButton("👁")
        self.pw_toggle.setCheckable(True)
        self.pw_toggle.setFixedSize(42, 42)
        # Use a visible styled button (not fully flat) so it contrasts on white
        self.pw_toggle.setFlat(False)
        self.pw_toggle.setCursor(Qt.PointingHandCursor)
        self.pw_toggle.setToolTip("Afficher / masquer le mot de passe")
        # Style: colored icon when unchecked, accent background when checked
        self.pw_toggle.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                color: {THEME.primary};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: #f6f9ff;
            }}
            QPushButton:checked {{
                background: {THEME.primary};
                color: white;
            }}
            """
        )
        self.pw_toggle.clicked.connect(self._toggle_password_visibility)
        pw_row.addWidget(self.pw_toggle)

        login_layout.addLayout(pw_row)

        # Erreur inline (évite les popups intrusives)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #f44336; font-size: 12px; background: transparent;")
        self.error_label.hide()
        login_layout.addWidget(self.error_label)
        
        # Bouton de connexion
        self.login_button = QPushButton("Se connecter")
        self.login_button.setMinimumHeight(42)
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setStyleSheet(button_solid(THEME.primary, THEME.primary_hover, padding="10px 14px"))
        self.login_button.clicked.connect(self.handle_login)
        login_layout.addWidget(self.login_button)
        
        main_layout.addWidget(login_frame)
        
        # Espace extensible
        main_layout.addStretch()
        
        # Test accounts info removed per UX decision

        # Focus direct
        self.username_input.setFocus()
        
    def apply_style(self):
        """Applique le style à la fenêtre"""
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                background-color: white;
                color: #333;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
            /* Le style du bouton principal est appliqué sur login_button */
        """)

    def _toggle_password_visibility(self):
        """Toggle the password field echo between hidden and visible."""
        try:
            if self.pw_toggle.isChecked():
                self.password_input.setEchoMode(QLineEdit.Normal)
                self.pw_toggle.setText("🙈")
            else:
                self.password_input.setEchoMode(QLineEdit.Password)
                self.pw_toggle.setText("👁")
        except Exception:
            # Safe guard: if anything goes wrong, ensure password remains hidden
            self.password_input.setEchoMode(QLineEdit.Password)
            self.pw_toggle.setChecked(False)
            self.pw_toggle.setText("👁")
        
    def handle_login(self):
        """Gère la tentative de connexion"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        # Reset error state and ensure inputs use a safe explicit style
        self.error_label.hide()
        safe_input_style = (
            "border: 2px solid #ddd; border-radius: 8px; padding: 8px 12px; "
            "font-size: 14px; background-color: white; color: #333;"
        )
        self.username_input.setStyleSheet(safe_input_style)
        self.password_input.setStyleSheet(safe_input_style)
        
        if not username or not password:
            self.error_label.setText("Veuillez remplir tous les champs.")
            self.error_label.show()
            # Highlight missing fields
            if not username:
                self.username_input.setStyleSheet(safe_input_style + " border-color: #f44336;")
            if not password:
                self.password_input.setStyleSheet(safe_input_style + " border-color: #f44336;")
            return
            
        # Vérification des identifiants
        if username in USERS and USERS[username] == password:
            app_state.login(username)
            self.login_successful.emit(username)
        else:
            self.error_label.setText("Nom d'utilisateur ou mot de passe incorrect.")
            self.error_label.show()
            self.password_input.clear()
            self.password_input.setFocus()
            # mark inputs as error visually
            self.username_input.setStyleSheet(safe_input_style + " border-color: #f44336;")
            self.password_input.setStyleSheet(safe_input_style + " border-color: #f44336;")
    def clear_fields(self):
        """Efface les champs de saisie"""
        self.username_input.clear()
        self.password_input.clear()


class UserInfoWidget(QWidget):
    """
    Widget affichant les informations de l'utilisateur connecté
    avec bouton de déconnexion
    """
    logout_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Configure l'interface"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Avatar/Icône utilisateur
        self.user_icon = QLabel("👤")
        self.user_icon.setFont(QFont("Segoe UI", 16))
        layout.addWidget(self.user_icon)
        
        # Nom d'utilisateur
        self.username_label = QLabel("Non connecté")
        self.username_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        # Texte foncé pour contraste sur fond clair
        self.username_label.setStyleSheet("color: #111111;")
        layout.addWidget(self.username_label)
        
        layout.addStretch()
        
        # Bouton déconnexion
        self.logout_button = QPushButton("Déconnexion")
        self.logout_button.setCursor(Qt.PointingHandCursor)
        self.logout_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.logout_button.clicked.connect(self.logout_requested.emit)
        layout.addWidget(self.logout_button)
        
    def set_username(self, username):
        """Définit le nom d'utilisateur affiché"""
        self.username_label.setText(username)
