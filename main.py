import os
import sys
import shutil
import subprocess

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QHBoxLayout,
    QMessageBox,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import QIcon


SERVICE_NAME = "autodarts"


def resource_path(relative_path):
    """
    Sorgt dafür, dass Dateien sowohl im normalen Python-Modus
    als auch im PyInstaller-Build gefunden werden.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class AutodartsManager(QWidget):
    def __init__(self):
        super().__init__()

        self.is_root = os.geteuid() == 0
        self.current_process = None
        self.log_process = None

        self.setWindowTitle("Autodarts Manager")
        self.setMinimumSize(980, 700)

        icon_path = resource_path("assets/autodarts-manager.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet("""
            QWidget {
                background-color: #1c1d20;
                color: #e6e6e6;
                font-family: Arial, Helvetica, sans-serif;
                font-size: 14px;
            }

            QLabel {
                color: #e6e6e6;
                background: transparent;
            }

            QFrame#MainCard {
                background-color: #232428;
                border: 1px solid #2f3136;
                border-radius: 16px;
            }

            QFrame#InfoBar {
                background-color: #232428;
                border: 1px solid #2c2f34;
                border-radius: 10px;
            }

            QLabel#Title {
                font-size: 30px;
                font-weight: bold;
                color: #ffffff;
            }

            QLabel#SubTitle {
                font-size: 14px;
                color: #bfc3c9;
            }

            QLabel#InfoTitle {
                font-size: 15px;
                font-weight: bold;
                color: #ffffff;
            }

            QLabel#InfoText {
                font-size: 14px;
                color: #d9d9d9;
            }

            QLabel#SectionTitle {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                padding-top: 2px;
                padding-bottom: 4px;
            }

            QLabel#StatusBox {
                background-color: #232428;
                border: 1px solid #30333a;
                border-radius: 12px;
                padding: 18px;
                font-size: 18px;
                font-weight: bold;
            }

            QPushButton {
                background-color: #2c2f35;
                color: #f2f2f2;
                border: 1px solid #3a3d44;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: normal;
                min-height: 18px;
            }

            QPushButton:hover {
                border: 1px solid #67c8ff;
                background-color: #30333a;
            }

            QPushButton:pressed {
                background-color: #26282d;
            }

            QPushButton:disabled {
                background-color: #25272b;
                color: #777777;
                border: 1px solid #31343a;
            }

            QPushButton#PrimaryButton {
                background-color: #67c8ff;
                color: #101214;
                border: none;
                font-weight: bold;
            }

            QPushButton#PrimaryButton:hover {
                background-color: #7fd2ff;
            }

            QPushButton#PrimaryButton:pressed {
                background-color: #51b6ef;
            }

            QPushButton#DarkButton {
                background-color: #30333a;
                color: #f0f0f0;
                border: 1px solid #434750;
            }

            QPushButton#DarkButton:hover {
                border: 1px solid #67c8ff;
            }

            QTextEdit {
                background-color: #1f2024;
                color: #e8e8e8;
                border: 1px solid #31343a;
                border-radius: 10px;
                padding: 10px;
                font-family: Consolas, Menlo, monospace;
                font-size: 13px;
            }
        """)

        self.build_ui()
        self.connect_buttons()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)

        if self.is_root:
            self.log("Root-Modus aktiv. Alle Befehle laufen direkt ohne Passwortabfrage.\n")
        else:
            self.log(
                "Benutzer-Modus aktiv. Root-Befehle laufen über pkexec.\n"
                "Für direkten Root-Modus bitte so starten:\n"
                "sudo ./AutodartsManager\n"
                "oder während der Entwicklung:\n"
                "sudo venv/bin/python main.py\n"
            )

        self.update_status()

    def build_ui(self):
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(28, 28, 28, 28)
        outer_layout.setSpacing(16)

        info_bar_layout = QHBoxLayout()
        info_bar_layout.setContentsMargins(14, 10, 14, 10)
        info_bar_layout.setSpacing(12)

        info_bar_layout.addStretch()

        header_card = QFrame()
        header_card.setObjectName("MainCard")

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(6)

        self.status_label = QLabel("Status wird geladen ...")
        self.status_label.setObjectName("StatusBox")
        self.status_label.setAlignment(Qt.AlignCenter)

        controls_card = QFrame()
        controls_card.setObjectName("MainCard")

        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(18, 18, 18, 18)
        controls_layout.setSpacing(12)

        self.btn_install_update = QPushButton("Installieren / Updaten")
        self.btn_install_update.setObjectName("PrimaryButton")
        self.btn_install_update.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        controls_layout.addWidget(self.btn_install_update)

        service_title = QLabel("Dienststeuerung")
        service_title.setObjectName("SectionTitle")
        controls_layout.addWidget(service_title)

        row_service = QHBoxLayout()
        row_service.setSpacing(10)

        self.btn_start = QPushButton("Starten")
        self.btn_stop = QPushButton("Stoppen")
        self.btn_restart = QPushButton("Neustarten")
        self.btn_status = QPushButton("Status aktualisieren")

        row_service.addWidget(self.btn_start)
        row_service.addWidget(self.btn_stop)
        row_service.addWidget(self.btn_restart)
        row_service.addWidget(self.btn_status)

        controls_layout.addLayout(row_service)

        autostart_title = QLabel("Autostart")
        autostart_title.setObjectName("SectionTitle")
        controls_layout.addWidget(autostart_title)

        row_autostart = QHBoxLayout()
        row_autostart.setSpacing(10)

        self.btn_enable = QPushButton("Dienst aktivieren")
        self.btn_disable = QPushButton("Dienst deaktivieren")
        self.btn_disable.setObjectName("DarkButton")

        row_autostart.addWidget(self.btn_enable)
        row_autostart.addWidget(self.btn_disable)

        controls_layout.addLayout(row_autostart)

        logs_title = QLabel("Logs")
        logs_title.setObjectName("SectionTitle")
        controls_layout.addWidget(logs_title)

        row_logs = QHBoxLayout()
        row_logs.setSpacing(10)

        self.btn_logs_start = QPushButton("Live-Logs starten")
        self.btn_logs_stop = QPushButton("Live-Logs stoppen")
        self.btn_logs_stop.setObjectName("DarkButton")
        self.btn_logs_stop.setEnabled(False)

        row_logs.addWidget(self.btn_logs_start)
        row_logs.addWidget(self.btn_logs_stop)

        controls_layout.addLayout(row_logs)

        controls_card.setLayout(controls_layout)

        output_card = QFrame()
        output_card.setObjectName("MainCard")

        output_layout = QVBoxLayout()
        output_layout.setContentsMargins(18, 18, 18, 18)
        output_layout.setSpacing(10)

        output_title = QLabel("Ausgabe")
        output_title.setObjectName("SectionTitle")

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        output_layout.addWidget(output_title)
        output_layout.addWidget(self.log_output)
        output_card.setLayout(output_layout)

        outer_layout.addWidget(header_card)
        outer_layout.addWidget(self.status_label)
        outer_layout.addWidget(controls_card)
        outer_layout.addWidget(output_card)

        self.setLayout(outer_layout)

    def connect_buttons(self):
        self.btn_install_update.clicked.connect(self.install_or_update_autodarts)

        self.btn_start.clicked.connect(
            lambda: self.run_admin_command(["systemctl", "start", SERVICE_NAME])
        )

        self.btn_stop.clicked.connect(
            lambda: self.run_admin_command(["systemctl", "stop", SERVICE_NAME])
        )

        self.btn_restart.clicked.connect(
            lambda: self.run_admin_command(["systemctl", "restart", SERVICE_NAME])
        )

        self.btn_status.clicked.connect(self.update_status)

        self.btn_enable.clicked.connect(
            lambda: self.run_admin_command(["systemctl", "enable", SERVICE_NAME])
        )

        self.btn_disable.clicked.connect(
            lambda: self.run_admin_command(["systemctl", "disable", SERVICE_NAME])
        )

        self.btn_logs_start.clicked.connect(self.start_live_logs)
        self.btn_logs_stop.clicked.connect(self.stop_live_logs)

    def log(self, text):
        self.log_output.append(text.rstrip())

    def set_busy(self, busy):
        buttons = [
            self.btn_install_update,
            self.btn_start,
            self.btn_stop,
            self.btn_restart,
            self.btn_enable,
            self.btn_disable,
        ]

        for button in buttons:
            button.setEnabled(not busy)

        self.btn_status.setEnabled(True)

    def command_exists(self, command_name):
        return shutil.which(command_name) is not None

    def detect_package_manager(self):
        if self.command_exists("pacman"):
            return "pacman"

        if self.command_exists("apt"):
            return "apt"

        if self.command_exists("dnf"):
            return "dnf"

        if self.command_exists("zypper"):
            return "zypper"

        return None

    def prepare_admin_command(self, command):
        if self.is_root:
            return command

        return ["pkexec"] + command

    def run_admin_command(self, command, on_success=None, on_failure=None):
        if self.current_process is not None:
            QMessageBox.warning(
                self,
                "Aktion läuft bereits",
                "Es läuft bereits ein anderer Befehl.\n\n"
                "Bitte warte, bis dieser fertig ist.",
            )
            return

        full_command = self.prepare_admin_command(command)
        self.start_process(full_command, on_success, on_failure)

    def start_process(self, command, on_success=None, on_failure=None):
        self.set_busy(True)
        self.log(f"\n$ {' '.join(command)}")

        self.current_process = QProcess(self)
        self.current_process.setProcessChannelMode(QProcess.MergedChannels)
        self.current_process.readyReadStandardOutput.connect(self.read_process_output)

        def finished(exit_code, exit_status):
            self.process_finished(exit_code, exit_status, on_success, on_failure)

        self.current_process.finished.connect(finished)

        program = command[0]
        args = command[1:]

        self.current_process.start(program, args)

        if not self.current_process.waitForStarted(3000):
            self.log("Fehler: Prozess konnte nicht gestartet werden.\n")
            self.current_process = None
            self.set_busy(False)

            if on_failure:
                on_failure()

    def read_process_output(self):
        if self.current_process:
            data = self.current_process.readAllStandardOutput().data().decode(errors="replace")

            if data.strip():
                self.log(data)

    def process_finished(self, exit_code, exit_status, on_success=None, on_failure=None):
        success = exit_code == 0

        if success:
            self.log(f"Befehl erfolgreich beendet. Rückgabecode: {exit_code}\n")
        else:
            self.log(f"Befehl fehlgeschlagen. Rückgabecode: {exit_code}\n")

        self.current_process = None
        self.set_busy(False)
        self.update_status()

        if success and on_success:
            on_success()

        if not success and on_failure:
            on_failure()

    def install_or_update_autodarts(self):
        self.log("\nInstallieren / Updaten wurde gestartet ...")

        if self.command_exists("curl"):
            self.log("curl ist bereits installiert.")
            self.run_autodarts_installer()
            return

        self.log("curl wurde nicht gefunden. Installation wird gestartet ...")

        package_manager = self.detect_package_manager()

        if package_manager == "pacman":
            command = ["pacman", "-S", "curl", "--needed", "--noconfirm"]
        elif package_manager == "apt":
            command = ["apt", "install", "curl", "-y"]
        elif package_manager == "dnf":
            command = ["dnf", "install", "curl", "-y"]
        elif package_manager == "zypper":
            command = ["zypper", "install", "-y", "curl"]
        else:
            self.log("Kein unterstützter Paketmanager gefunden.")

            QMessageBox.critical(
                self,
                "Fehler",
                "Kein unterstützter Paketmanager gefunden.\n\n"
                "Unterstützt werden aktuell: pacman, apt, dnf und zypper.",
            )
            return

        self.run_admin_command(
            command,
            on_success=self.run_autodarts_installer,
            on_failure=lambda: QMessageBox.critical(
                self,
                "Fehler",
                "curl konnte nicht installiert werden.",
            ),
        )

    def run_autodarts_installer(self):
        self.log("\nStarte Autodarts Installer ...")

        command = [
            "bash",
            "-c",
            "bash <(curl -sL get.autodarts.io)",
        ]

        self.run_admin_command(
            command,
            on_success=self.autodarts_install_success,
            on_failure=self.autodarts_install_failure,
        )

    def autodarts_install_success(self):
        self.log("Autodarts Installation / Update abgeschlossen.\n")

        QMessageBox.information(
            self,
            "Fertig",
            "Autodarts wurde installiert oder aktualisiert.",
        )

        self.update_status()

    def autodarts_install_failure(self):
        self.log("Autodarts Installation / Update fehlgeschlagen.\n")

        QMessageBox.critical(
            self,
            "Fehler",
            "Autodarts konnte nicht installiert oder aktualisiert werden.\n\n"
            "Bitte prüfe die Ausgabe im Fenster.",
        )

        self.update_status()

    def start_live_logs(self):
        if self.log_process is not None:
            self.log("Live-Logs laufen bereits.")
            return

        self.log(f"\n$ journalctl -u {SERVICE_NAME} -f -n 100")
        self.log("Live-Logs werden gestartet ...")

        self.log_process = QProcess(self)
        self.log_process.setProcessChannelMode(QProcess.MergedChannels)
        self.log_process.readyReadStandardOutput.connect(self.read_log_output)
        self.log_process.finished.connect(self.live_logs_finished)

        self.log_process.start("journalctl", ["-u", SERVICE_NAME, "-f", "-n", "100"])

        if not self.log_process.waitForStarted(3000):
            self.log("Live-Logs konnten nicht gestartet werden.")
            self.log_process = None
            return

        self.btn_logs_start.setEnabled(False)
        self.btn_logs_stop.setEnabled(True)

    def read_log_output(self):
        if self.log_process:
            data = self.log_process.readAllStandardOutput().data().decode(errors="replace")

            if data.strip():
                self.log(data)

    def stop_live_logs(self):
        if self.log_process is None:
            return

        self.log("\nLive-Logs werden gestoppt ...")
        self.log_process.terminate()

        if not self.log_process.waitForFinished(3000):
            self.log_process.kill()

        self.log_process = None
        self.btn_logs_start.setEnabled(True)
        self.btn_logs_stop.setEnabled(False)

    def live_logs_finished(self):
        self.log_process = None
        self.btn_logs_start.setEnabled(True)
        self.btn_logs_stop.setEnabled(False)
        self.log("Live-Logs wurden beendet.")

    def run_status_command(self, command):
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3,
            )

            return result.returncode, result.stdout.strip(), result.stderr.strip()

        except Exception:
            return 1, "", ""

    def update_status(self):
        active_code, active, _ = self.run_status_command(
            ["systemctl", "is-active", SERVICE_NAME]
        )

        enabled_code, enabled, _ = self.run_status_command(
            ["systemctl", "is-enabled", SERVICE_NAME]
        )

        if active == "active":
            status_text = "● Autodarts läuft"
            status_color = "#67c8ff"
        elif active == "inactive":
            status_text = "● Autodarts ist gestoppt"
            status_color = "#d5d5d5"
        elif active == "failed":
            status_text = "● Autodarts hat einen Fehler"
            status_color = "#ff7b7b"
        else:
            status_text = "● Autodarts nicht installiert oder Status unbekannt"
            status_color = "#9a9a9a"

        if enabled == "enabled":
            autostart_text = "Autostart: aktiviert"
        elif enabled == "disabled":
            autostart_text = "Autostart: deaktiviert"
        else:
            autostart_text = "Autostart: unbekannt"

        root_text = "Rootrechte: aktiv" if self.is_root else "Rootrechte: nicht aktiv"

        self.status_label.setText(
            f"{status_text}\n{autostart_text}\n{root_text}"
        )

        self.status_label.setStyleSheet(
            f"""
            QLabel#StatusBox {{
                background-color: #232428;
                border: 1px solid #30333a;
                border-radius: 12px;
                padding: 18px;
                font-size: 18px;
                font-weight: bold;
                color: {status_color};
            }}
            """
        )

    def closeEvent(self, event):
        if self.current_process is not None:
            reply = QMessageBox.question(
                self,
                "Aktion läuft",
                "Es läuft noch ein Befehl.\n\n"
                "Soll das Programm wirklich beendet werden?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.No:
                event.ignore()
                return

            self.current_process.kill()
            self.current_process = None

        if self.log_process is not None:
            self.log_process.kill()
            self.log_process = None

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    icon_path = resource_path("assets/autodarts-manager.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = AutodartsManager()
    window.show()

    sys.exit(app.exec())
