"""Package `app.ui.dialogs` re-exporting dialog classes.
This package replaces the old `app/ui/dialogs.py` with the same public API.
"""
from .add_screen_dialog import AddScreenDialog
from .logout_confirm_dialog import LogoutConfirmDialog
from .monitor_select_dialog import MonitorSelectDialog

__all__ = [
    'AddScreenDialog',
    'LogoutConfirmDialog',
    'MonitorSelectDialog',
]
