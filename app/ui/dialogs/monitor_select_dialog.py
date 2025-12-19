from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QPushButton, QHBoxLayout, QCheckBox
from PySide6.QtCore import Qt


class MonitorSelectDialog(QDialog):
    """Dialog pour sélectionner le moniteur à partager"""

    def __init__(self, monitors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélection du moniteur")
        self.setFixedSize(420, 350)
        self.setModal(True)
        self.monitors = monitors
        self.selected_monitor_id = 1  # Par défaut, premier moniteur
        self._apply_style()
        self.setup_ui()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 12px;
            }
            QLabel {
                color: #333333;
                background: transparent;
            }
            QLabel#titleLabel {
                color: #1976D2;
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#subtitleLabel {
                color: #666666;
                font-size: 12px;
            }
            QListWidget {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #ffffff;
                color: #333333;
                padding: 12px;
                border-bottom: 1px solid #eee;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # Titre
        title_label = QLabel("🖥️ Quel écran voulez-vous partager ?")
        title_label.setObjectName("titleLabel")
        layout.addWidget(title_label)

        # Sous-titre
        subtitle_label = QLabel("Sélectionnez le moniteur à diffuser aux autres participants")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)

        # Option: partager tout le bureau
        self.share_all_checkbox = QCheckBox("Partager tout le bureau (tous les écrans)")
        self.share_all_checkbox.setCursor(Qt.PointingHandCursor)
        self.share_all_checkbox.setChecked(False)
        self.share_all_checkbox.toggled.connect(self._on_share_all_toggled)
        layout.addWidget(self.share_all_checkbox)

        # Liste des moniteurs
        self.monitor_list = QListWidget()
        self.monitor_list.setMinimumHeight(150)

        for mon in self.monitors:
            # Icône selon le type
            if mon['id'] == 0:
                icon = "🖼️"  # Tous les écrans
            elif mon.get('is_primary'):
                icon = "🖥️"  # Principal
            else:
                icon = "🖵"  # Secondaire

            item = QListWidgetItem(f"{icon}  {mon['name']}\n      {mon['width']}×{mon['height']}")
            item.setData(Qt.UserRole, mon['id'])
            self.monitor_list.addItem(item)

            # Sélectionner le moniteur principal par défaut (ou le premier si un seul)
            if mon.get('is_primary') or (len(self.monitors) == 1):
                self.monitor_list.setCurrentItem(item)
                self.selected_monitor_id = mon['id']

        self.monitor_list.itemClicked.connect(self._on_monitor_selected)
        self.monitor_list.itemDoubleClicked.connect(self._on_monitor_double_clicked)
        layout.addWidget(self.monitor_list)

        # Initialiser la checkbox si la liste contient explicitement l'entrée "Tous les écrans" (id == 0)
        has_all = any(mon.get('id') == 0 for mon in self.monitors)
        if has_all:
            # This will trigger the toggled handler which will disable the list
            self.share_all_checkbox.setChecked(True)

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()

        share_btn = QPushButton("Partager cet écran")
        share_btn.setCursor(Qt.PointingHandCursor)
        share_btn.setMinimumHeight(40)
        share_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
        """)
        share_btn.clicked.connect(self.accept)
        btn_layout.addWidget(share_btn)

        layout.addLayout(btn_layout)

    def _on_monitor_selected(self, item):
        self.selected_monitor_id = item.data(Qt.UserRole)

    def _on_monitor_double_clicked(self, item):
        self.selected_monitor_id = item.data(Qt.UserRole)
        self.accept()

    def _on_share_all_toggled(self, checked: bool):
        """Handler when the "share all" checkbox is toggled.

        When checked we disable the list and set the selected monitor to 0
        (meaning: share the whole desktop). When unchecked we re-enable
        the list and keep/restore selection.
        """
        if checked:
            # Prefer id 0 (all screens) when available; otherwise 0 still
            # signals the server to attempt capturing the whole desktop.
            self.selected_monitor_id = 0
            self.monitor_list.setDisabled(True)
            # If the list contains an item with data==0, select it for clarity
            for i in range(self.monitor_list.count()):
                itm = self.monitor_list.item(i)
                if itm.data(Qt.UserRole) == 0:
                    self.monitor_list.setCurrentItem(itm)
                    break
        else:
            # Re-enable list and pick selected item (or first) as default
            self.monitor_list.setDisabled(False)
            cur = self.monitor_list.currentItem()
            if cur:
                self.selected_monitor_id = cur.data(Qt.UserRole)
            elif self.monitor_list.count() > 0:
                itm = self.monitor_list.item(0)
                self.monitor_list.setCurrentItem(itm)
                self.selected_monitor_id = itm.data(Qt.UserRole)

    def get_selected_monitor(self):
        return self.selected_monitor_id
