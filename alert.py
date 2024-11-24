import sys
import time
import threading
import requests
import json
from pathlib import Path
from bs4 import BeautifulSoup
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QDialog
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QMutex, Signal
from PySide6.QtCore import Qt
from pygame import mixer


class VoltageCheckerApp(QWidget):
    alert_signal = Signal(float)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voltage Checker")

        # Layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Load default configuration
        self.config = self.load_config()

        self.url_label = QLabel("URL:")
        self.layout.addWidget(self.url_label)
        self.url_input = QLineEdit(self.config.get("url"))
        self.url_input.textChanged.connect(self.update_url)
        self.layout.addWidget(self.url_input)

        self.interval_label = QLabel("Check Interval (seconds):")
        self.layout.addWidget(self.interval_label)
        self.interval_input = QLineEdit(str(self.config.get("check_interval")))
        self.interval_input.textChanged.connect(self.update_interval)
        self.layout.addWidget(self.interval_input)

        self.threshold_label = QLabel("Voltage Threshold:")
        self.layout.addWidget(self.threshold_label)
        self.threshold_input = QLineEdit(str(self.config.get("threshold")))
        self.threshold_input.textChanged.connect(self.update_threshold)
        self.layout.addWidget(self.threshold_input)

        # Buttons
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        self.layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)  # Disabled initially
        self.layout.addWidget(self.stop_button)

        # Monitoring flags and variables
        self.monitoring = False
        self.alerted = False
        self.mutex = QMutex()
        self.url = self.config.get("url")
        self.interval = self.config.get("check_interval")
        self.threshold = self.config.get("threshold")

        # Media player for sound
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)

        # Connect the alert signal to the alert handler
        self.alert_signal.connect(self.alert_user)

    def update_url(self, new_url):
        try:
            self.mutex.lock()
            self.url = new_url
        finally:
            self.mutex.unlock()

    def update_interval(self, new_interval):
        try:
            self.mutex.lock()
            self.interval = int(new_interval)
        finally:
            self.mutex.unlock()

    def update_threshold(self, new_threshold):
        try:
            self.mutex.lock()
            self.threshold = float(new_threshold)
        finally:
            self.mutex.unlock()

    def load_config(self):
        if getattr(sys, 'frozen', False):
            # The application is frozen (running as an executable)
            base_path = Path(sys._MEIPASS)  # Temporary directory where PyInstaller bundles resources
        else:
            # The application is running in a normal Python environment
            base_path = Path(__file__).parent

        config_path = base_path / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as config_file:
                    return json.load(config_file)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to load config.json: {str(e)}"
                )
                return {}
        else:
            QMessageBox.critical(
                self, "Error", "Failed to find config.json"
            )
            return {}

    def start_monitoring(self):
        if self.monitoring:
            QMessageBox.information(self, "Info", "Monitoring is already running.")
            return

        self.monitoring = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        threading.Thread(target=self.monitor_voltage, daemon=True).start()

    def stop_monitoring(self):
        if not self.monitoring:
            QMessageBox.information(self, "Info", "Monitoring is stopped.")
            return

        self.monitoring = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def monitor_voltage(self):
        while self.monitoring:
            try:
                self.mutex.lock()
                url = self.url
                interval = self.interval
                threshold = self.threshold
                self.mutex.unlock()

                time.sleep(interval)

                try:
                    response = requests.get(url, timeout=5)
                    response.raise_for_status()
                except requests.exceptions.Timeout:
                    print("Request timed out")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")

                divs = soup.find_all("div", "text-md")
                if not divs:
                    continue

                voltage = next(div for div in divs if div.text.startswith("Напруга:"))
                if not voltage:
                    continue

                voltage = float(voltage.text[9:-1])

                if voltage >= threshold + 0.5:
                    self.alerted = False

                if voltage <= threshold and not self.alerted:
                    self.alerted = True
                    self.alert_signal.emit(voltage)

            except Exception as e:
                print(f"Error: {e}")

        self.start_button.setEnabled(True)

    def alert_user(self, voltage):
        mixer.init()
        mixer.music.load("alert.mp3")
        mixer.music.play()

        alert_dialog = QDialog(self)
        alert_dialog.setWindowTitle("Voltage Alert")
        alert_dialog.setWindowFlag(Qt.Window)
        alert_dialog.setFixedSize(1024, 768)

        # Layout for the dialog
        layout = QVBoxLayout()

        # Add alert message
        alert_message = QLabel(f"Voltage is: {voltage}")
        alert_message.setStyleSheet("font-size: 32px; color: red;")
        alert_message.setAlignment(Qt.AlignCenter)
        layout.addWidget(alert_message)

        # Add close button
        close_button = QPushButton("Close Alert")
        close_button.setStyleSheet("font-size: 24px;")
        close_button.clicked.connect(alert_dialog.accept)  # Close dialog on click
        layout.addWidget(close_button)

        # Set layout and show dialog
        alert_dialog.setLayout(layout)
        alert_dialog.exec()

        mixer.music.stop()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = VoltageCheckerApp()
    window.show()

    sys.exit(app.exec())

