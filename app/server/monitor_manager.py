"""
Gestionnaire de moniteurs - Détection et sélection des écrans
"""
import logging

# Import mss pour le support multi-moniteur
try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

logger = logging.getLogger("screenshare.server.monitor")


class MonitorManager:
    """Gère la détection et la sélection des moniteurs."""
    
    def __init__(self, default_width: int = 1920, default_height: int = 1080):
        """Initialise le gestionnaire de moniteurs.
        
        Args:
            default_width: Largeur par défaut si aucun moniteur détecté
            default_height: Hauteur par défaut si aucun moniteur détecté
        """
        self.default_width = default_width
        self.default_height = default_height
        self.selected_monitor = 1  # 0 = tous les écrans, 1+ = moniteur spécifique
        self.monitor_info = None   # Info du moniteur sélectionné
        self.screen_width = default_width
        self.screen_height = default_height
    
    def get_monitors(self) -> list:
        """Retourne la liste des moniteurs disponibles.
        
        Returns:
            Liste de dictionnaires avec les infos de chaque moniteur:
            {id, name, left, top, width, height, is_primary}
        """
        monitors = []
        
        if HAS_MSS:
            try:
                with mss.mss() as sct:
                    # sct.monitors[0] = tous les écrans combinés
                    # sct.monitors[1+] = moniteurs individuels
                    for i, mon in enumerate(sct.monitors):
                        if i == 0:
                            # Écran virtuel (tous combinés) - seulement si plusieurs moniteurs
                            if len(sct.monitors) > 2:
                                monitors.append({
                                    'id': 0,
                                    'name': 'Tous les écrans',
                                    'left': mon['left'],
                                    'top': mon['top'],
                                    'width': mon['width'],
                                    'height': mon['height'],
                                    'is_primary': False
                                })
                        else:
                            monitors.append({
                                'id': i,
                                'name': f'Écran {i}' + (' (Principal)' if i == 1 else ''),
                                'left': mon['left'],
                                'top': mon['top'],
                                'width': mon['width'],
                                'height': mon['height'],
                                'is_primary': (i == 1)
                            })
                        logger.info(f"Detected {len(monitors)} monitors via mss")
                        return monitors
            except Exception as e:
                logger.warning(f"Error getting monitors with mss: {e}")
        
        # Fallback: un seul écran par défaut
            logger.info("No multi-monitor detection available, using default 1 monitor fallback")
            return [{
            'id': 1,
            'name': 'Écran principal',
            'left': 0,
            'top': 0,
            'width': self.default_width,
            'height': self.default_height,
            'is_primary': True
        }]
    
    def set_monitor(self, monitor_id: int) -> bool:
        """Définit le moniteur à capturer.
        
        Args:
            monitor_id: 0 = tous les écrans, 1+ = moniteur spécifique
            
        Returns:
            True si le moniteur a été trouvé et sélectionné
        """
        self.selected_monitor = monitor_id
        monitors = self.get_monitors()
        
        # Trouver le moniteur sélectionné
        for mon in monitors:
            if mon['id'] == monitor_id:
                self.monitor_info = mon
                self.screen_width = mon['width']
                self.screen_height = mon['height']
                logger.info(
                    f"Selected monitor {monitor_id}: {mon['name']} "
                    f"({mon['width']}x{mon['height']} at {mon['left']},{mon['top']})"
                )
                return True
        
        # Si non trouvé, utiliser le premier
        if monitors:
            self.monitor_info = monitors[0]
            self.screen_width = monitors[0]['width']
            self.screen_height = monitors[0]['height']
            logger.warning(f"Monitor {monitor_id} not found, using {monitors[0]['name']}")
        
        return False
    
    def get_capture_bbox(self) -> tuple:
        """Retourne la zone de capture (bounding box) pour le moniteur sélectionné.
        
        Returns:
            Tuple (left, top, right, bottom) ou None si tous les écrans
        """
        if self.monitor_info and self.selected_monitor > 0:
            return (
                self.monitor_info['left'],
                self.monitor_info['top'],
                self.monitor_info['left'] + self.monitor_info['width'],
                self.monitor_info['top'] + self.monitor_info['height']
            )
        return None
    
    @property
    def has_mss(self) -> bool:
        """Vérifie si mss est disponible."""
        return HAS_MSS
