"""
Module UI - Interface utilisateur de l'application
"""
from .dialogs import AddScreenDialog, LogoutConfirmDialog, MonitorSelectDialog
from .main_window import MainWindow
from .ui_login import LoginWindow, UserInfoWidget
from .screens import ScreenListWidget, ScreenViewer, ScreenThumbnail
from .ui_style import THEME, ToastOverlay, button_solid, button_outline, status_badge

__all__ = [
    # Dialogs
    'AddScreenDialog',
    'LogoutConfirmDialog', 
    'MonitorSelectDialog',
    # Windows
    'MainWindow',
    'LoginWindow',
    # Widgets
    'UserInfoWidget',
    'ScreenListWidget',
    'ScreenViewer',
    'ScreenThumbnail',
    # Style
    'THEME',
    'ToastOverlay',
    'button_solid',
    'button_outline',
    'status_badge',
]
