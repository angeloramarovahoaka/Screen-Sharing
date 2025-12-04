"""
Module d'appel audio - Communication vocale entre utilisateurs
"""
import socket
import threading
import time
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QLineEdit
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("⚠️ PyAudio non disponible - Fonctionnalité d'appel désactivée")

from .config import AUDIO_PORT, AUDIO_RATE, AUDIO_CHANNELS, AUDIO_CHUNK


class AudioCall(QObject):
    """
    Gestionnaire d'appel audio
    """
    call_started = Signal()
    call_ended = Signal()
    call_incoming = Signal(str)  # Émetteur
    status_changed = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.is_in_call = False
        self.is_muted = False
        self.peer_ip = None
        
        # PyAudio
        self.audio = None
        self.input_stream = None
        self.output_stream = None
        
        # Sockets
        self.audio_socket = None
        
        # Threads
        self.send_thread = None
        self.receive_thread = None
        
        if PYAUDIO_AVAILABLE:
            try:
                self.audio = pyaudio.PyAudio()
            except Exception as e:
                print(f"Erreur PyAudio: {e}")
                
    def start_call(self, peer_ip):
        """Démarre un appel avec un pair"""
        if not PYAUDIO_AVAILABLE or not self.audio:
            self.error_occurred.emit("PyAudio non disponible")
            return False
            
        if self.is_in_call:
            return False
            
        self.peer_ip = peer_ip
        
        try:
            # Créer le socket UDP
            self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_socket.bind(('0.0.0.0', AUDIO_PORT))
            self.audio_socket.settimeout(0.1)
            
            # Ouvrir les flux audio
            self.input_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_RATE,
                input=True,
                frames_per_buffer=AUDIO_CHUNK
            )
            
            self.output_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_RATE,
                output=True,
                frames_per_buffer=AUDIO_CHUNK
            )
            
            self.is_in_call = True
            
            # Démarrer les threads
            self.send_thread = threading.Thread(target=self._send_audio, daemon=True)
            self.send_thread.start()
            
            self.receive_thread = threading.Thread(target=self._receive_audio, daemon=True)
            self.receive_thread.start()
            
            self.call_started.emit()
            self.status_changed.emit(f"En appel avec {peer_ip}")
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Erreur démarrage appel: {e}")
            self.end_call()
            return False
            
    def end_call(self):
        """Termine l'appel en cours"""
        self.is_in_call = False
        
        # Fermer les flux
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except:
                pass
            self.input_stream = None
            
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
            self.output_stream = None
            
        # Fermer le socket
        if self.audio_socket:
            try:
                self.audio_socket.close()
            except:
                pass
            self.audio_socket = None
            
        self.peer_ip = None
        self.call_ended.emit()
        self.status_changed.emit("Appel terminé")
        
    def toggle_mute(self):
        """Active/désactive le micro"""
        self.is_muted = not self.is_muted
        status = "Micro coupé" if self.is_muted else "Micro activé"
        self.status_changed.emit(status)
        return self.is_muted
        
    def _send_audio(self):
        """Thread d'envoi audio"""
        while self.is_in_call:
            try:
                if not self.is_muted and self.input_stream:
                    data = self.input_stream.read(AUDIO_CHUNK, exception_on_overflow=False)
                    if self.audio_socket and self.peer_ip:
                        self.audio_socket.sendto(data, (self.peer_ip, AUDIO_PORT))
            except Exception:
                time.sleep(0.01)
                
    def _receive_audio(self):
        """Thread de réception audio"""
        while self.is_in_call:
            try:
                if self.audio_socket:
                    data, addr = self.audio_socket.recvfrom(AUDIO_CHUNK * 2)
                    if self.output_stream:
                        self.output_stream.write(data)
            except socket.timeout:
                continue
            except Exception:
                time.sleep(0.01)
                
    def cleanup(self):
        """Nettoyage des ressources"""
        self.end_call()
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass


class CallDialog(QDialog):
    """
    Dialog pour passer un appel
    """
    call_requested = Signal(str)  # IP à appeler
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📞 Passer un appel")
        self.setFixedSize(350, 180)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Titre
        title = QLabel("📞 Appeler un utilisateur")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Champ IP
        ip_layout = QHBoxLayout()
        ip_label = QLabel("Adresse IP:")
        ip_layout.addWidget(ip_label)
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.x.x")
        self.ip_input.setMinimumHeight(35)
        ip_layout.addWidget(self.ip_input)
        layout.addLayout(ip_layout)
        
        # Boutons
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        call_btn = QPushButton("📞 Appeler")
        call_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
        """)
        call_btn.clicked.connect(self._on_call)
        btn_layout.addWidget(call_btn)
        
        layout.addLayout(btn_layout)
        
    def _on_call(self):
        ip = self.ip_input.text().strip()
        if ip:
            self.call_requested.emit(ip)
            self.accept()


class CallWidget(QFrame):
    """
    Widget affichant l'état de l'appel en cours
    """
    end_call_requested = Signal()
    mute_toggled = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.call_duration = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_duration)
        self.setup_ui()
        self.hide()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #4CAF50;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Icône
        icon = QLabel("📞")
        icon.setFont(QFont("Segoe UI", 16))
        layout.addWidget(icon)
        
        # Info appel
        info_layout = QVBoxLayout()
        
        self.peer_label = QLabel("En appel avec...")
        self.peer_label.setStyleSheet("color: white; font-weight: bold;")
        info_layout.addWidget(self.peer_label)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("color: rgba(255,255,255,0.8);")
        info_layout.addWidget(self.duration_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Bouton mute
        self.mute_btn = QPushButton("🎤")
        self.mute_btn.setFixedSize(40, 40)
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                border: none;
                border-radius: 20px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
        """)
        self.mute_btn.clicked.connect(self.mute_toggled.emit)
        layout.addWidget(self.mute_btn)
        
        # Bouton raccrocher
        end_btn = QPushButton("📵")
        end_btn.setFixedSize(40, 40)
        end_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border: none;
                border-radius: 20px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        end_btn.clicked.connect(self.end_call_requested.emit)
        layout.addWidget(end_btn)
        
    def start_call(self, peer_ip):
        """Démarre l'affichage de l'appel"""
        self.peer_label.setText(f"En appel avec {peer_ip}")
        self.call_duration = 0
        self.duration_label.setText("00:00")
        self.timer.start(1000)
        self.show()
        
    def end_call(self):
        """Arrête l'affichage de l'appel"""
        self.timer.stop()
        self.hide()
        
    def set_muted(self, muted):
        """Met à jour l'état du bouton mute"""
        self.mute_btn.setText("🔇" if muted else "🎤")
        
    def _update_duration(self):
        """Met à jour le compteur de durée"""
        self.call_duration += 1
        minutes = self.call_duration // 60
        seconds = self.call_duration % 60
        self.duration_label.setText(f"{minutes:02d}:{seconds:02d}")
