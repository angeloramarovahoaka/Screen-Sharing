"""
Fenêtre principale de l'application

Ce module est un point d'entrée de rétrocompatibilité.
La logique est maintenant dans le sous-module `app.ui`.
"""
# Réexporter les classes depuis le module refactorisé
from .ui import MainWindow, AddScreenDialog, LogoutConfirmDialog, MonitorSelectDialog

__all__ = [
    'MainWindow',
    'AddScreenDialog',
    'LogoutConfirmDialog',
    'MonitorSelectDialog',
]
