# plugins/code_editor_plugin_with_debugger.py

import os
import sys
import subprocess
import logging
from plugin_interface import ChatPlugin
from PySide6.QtWidgets import (QAction, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QFileDialog, QMessageBox, QTabWidget, QTextEdit, QLabel)
from PySide6.QtGui import QFont

logger = logging.getLogger("CodeEditorPlugin")

class CodeEditorPlugin(ChatPlugin):
    """
    Ein erweiterter Code-Editor, der Öffnen, Speichern, Ausführen, 
    Linting mit 'flake8' und interaktives Debugging mit 'pdb' unterstützt.
    Kann mit initialem Inhalt geöffnet werden.
    """
    def get_name(self):
        return "Code Editor, Linter & Debugger"
    
    def get_description(self):
        return "Editor mit Tabs, Ausführung, 'flake8'-Prüfung und 'pdb'-Debugging."

    def __init__(self, main_window):
        super().__init__(main_window)
        action = QAction("Code-Editor öffnen", self.main_window)
        # Wir machen die open_editor Methode direkt zugänglich
        action.triggered.connect(self.open_editor)
        
        edit_menu = next((m for m in self.main_window.menuBar().actions() if m.text() == "&Bearbeiten"), None)
        if edit_menu:
            edit_menu.menu().addAction(action)
        else:
            self.main_window.menuBar().addAction(action)

    def open_editor(self, initial_content: str = "", initial_title: str = "Neue Datei"):
        """
        Öffnet den Editor. Kann optional mit Inhalt und Titel aufgerufen werden.
        """
        editor = QDialog(self.main_window)
        editor.setWindowTitle("Code Editor")
        editor.resize(900, 700)
        layout = QVBoxLayout(editor)

        tabs = QTabWidget()
        tabs.setTabsClosable(True)
        tabs.tabCloseRequested.connect(tabs.removeTab)
        layout.addWidget(tabs)

        def new_tab(content="", title="Neue Datei"):
            edit = QTextEdit()
            font = QFont("Monospace")
            font.setStyleHint(QFont.StyleHint.TypeWriter)
            edit.setFont(font)
            edit.setPlainText(content)
            idx = tabs.addTab(edit, title)
            tabs.setCurrentIndex(idx)
            edit.setProperty("file_path", None)

        button_layout = QHBoxLayout()
        btn_new = QPushButton("Neue Datei")
        btn_open = QPushButton("Öffnen...")
        btn_save = QPushButton("Speichern...")
        btn_run = QPushButton("Ausführen")
        btn_lint = QPushButton("Code prüfen (Lint)")
        btn_debug = QPushButton("Debuggen")

        button_layout.addWidget(btn_new)
        button_layout.addWidget(btn_open)
        button_layout.addWidget(btn_save)
        button_layout.addStretch()
        button_layout.addWidget(btn_run)
        button_layout.addWidget(btn_lint)
        button_layout.addWidget(btn_debug)
        layout.addLayout(button_layout)

        def save_file_logic(current_widget):
            path = current_widget.property("file_path")
            if not path:
                path, _ = QFileDialog.getSaveFileName(editor, "Datei speichern", "", "Python Dateien (*.py);;Alle Dateien (*)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(current_widget.toPlainText())
                current_widget.setProperty("file_path", path)
                tabs.setTabText(tabs.currentIndex(), os.path.basename(path))
            return path

        btn_new.clicked.connect(lambda: new_tab())
        # ... (der Rest der Button-Logik bleibt identisch) ...
        # --- START: Kopierter Code aus der vorherigen Version ---
        def open_file():
            path, _ = QFileDialog.getOpenFileName(editor, "Datei öffnen", "", "Python Dateien (*.py);;Alle Dateien (*)")
            if path:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                new_tab(text, os.path.basename(path))
                tabs.currentWidget().setProperty("file_path", path)
        btn_open.clicked.connect(open_file)

        def save_file():
            current = tabs.currentWidget()
            if current: save_file_logic(current)
        btn_save.clicked.connect(save_file)
        
        def run_code():
            current = tabs.currentWidget()
            if not current: return
            path = save_file_logic(current)
            if not path: return

            try:
                result = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=30)
                self.show_output_dialog(editor, "Ausgabe", f"--- STDOUT ---\n{result.stdout}\n\n--- STDERR ---\n{result.stderr}")
            except subprocess.TimeoutExpired:
                QMessageBox.warning(editor, "Timeout", "Ausführung > 30s, abgebrochen.")
            except Exception as e:
                QMessageBox.critical(editor, "Fehler bei Ausführung", str(e))
        btn_run.clicked.connect(run_code)

        def lint_code():
            current = tabs.currentWidget()
            if not current: return
            path = save_file_logic(current)
            if not path: return

            try:
                result = subprocess.run([sys.executable, "-m", "flake8", path], capture_output=True, text=True)
                output = result.stdout if result.stdout else "Keine Probleme gefunden. Sehr gut!"
                self.show_output_dialog(editor, "Flake8 Linter-Ergebnis", output)
            except FileNotFoundError:
                 QMessageBox.critical(editor, "Fehler", "'flake8' wurde nicht gefunden.\nBitte installieren Sie es mit: pip install flake8")
            except Exception as e:
                QMessageBox.critical(editor, "Fehler beim Linten", str(e))
        btn_lint.clicked.connect(lint_code)

        def debug_code():
            current = tabs.currentWidget()
            if not current: return
            path = save_file_logic(current)
            if not path: return

            try:
                command = ["x-terminal-emulator", "-e", f"python3 -m pdb {path}"]
                subprocess.Popen(command)
            except FileNotFoundError:
                QMessageBox.critical(editor, "Fehler", 
                                     "'x-terminal-emulator' nicht gefunden.\n"
                                     "Bitte installieren Sie ein Standard-Terminal (z.B. gnome-terminal) "
                                     "oder passen Sie den Befehl im Plugin-Code an.")
            except Exception as e:
                QMessageBox.critical(editor, "Fehler beim Starten des Debuggers", str(e))
        btn_debug.clicked.connect(debug_code)
        # --- ENDE: Kopierter Code ---

        # Erstelle den ersten Tab mit dem übergebenen Inhalt
        new_tab(initial_content, initial_title)
        
        editor.exec()

    def show_output_dialog(self, parent, title, text):
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)
        view = QTextEdit(readOnly=True)
        view.setFont(QFont("Monospace"))
        view.setPlainText(text)
        layout.addWidget(view)
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

