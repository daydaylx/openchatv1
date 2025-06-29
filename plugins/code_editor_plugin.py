# plugins/code_editor_plugin.py

import os
import sys
import subprocess
import logging
import difflib
import re
from plugin_interface import ChatPlugin
from openchat_with_plugins import ApiWorker
from PySide6.QtWidgets import (QAction, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QFileDialog, QMessageBox, QTabWidget, QTextEdit, QLabel, QMenu,
                               QTextBrowser)
from PySide6.QtGui import QFont, QTextCursor, QIcon
from PySide6.QtCore import Qt, QMetaObject

logger = logging.getLogger("CodeEditorPlugin")

class DiffDialog(QDialog):
    def __init__(self, diff_html, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Refactoring-Vorschlag"); self.setMinimumSize(800, 600); self.setModal(True)
        layout = QVBoxLayout(self); browser = QTextBrowser(); browser.setHtml(diff_html); layout.addWidget(browser)
        button_layout = QHBoxLayout(); btn_accept = QPushButton("Änderungen übernehmen"); btn_reject = QPushButton("Verwerfen")
        button_layout.addStretch(); button_layout.addWidget(btn_reject); button_layout.addWidget(btn_accept); layout.addLayout(button_layout)
        btn_accept.clicked.connect(self.accept); btn_reject.clicked.connect(self.reject)

REFACTOR_PROMPTS = {
    "Lesbarkeit verbessern": "Überarbeite den folgenden Python-Code, um die Lesbarkeit zu verbessern. Ändere nicht die Funktionalität. Gib nur den reinen, aktualisierten Code zurück.",
    "Docstrings generieren": "Generiere Python Docstrings (im Google-Stil) für den folgenden Code. Gib nur den Code inklusive der neuen Docstrings zurück.",
    "Fehlerbehandlung hinzufügen": "Füge dem folgenden Python-Code eine robuste Fehlerbehandlung mit try-except-Blöcken hinzu. Gib nur den aktualisierten Code zurück.",
    "Performance optimieren": "Analysiere den folgenden Python-Code und optimiere ihn für bessere Performance, falls möglich. Erkläre kurz als Kommentar am Anfang des Codes, was du geändert hast. Gib nur den optimierten Code zurück.",
    "In Funktion auslagern": "Wandle den folgenden Code-Block in eine wiederverwendbare Python-Funktion um. Wähle einen passenden Namen und Parameter. Gib nur die Funktion selbst zurück."
}

class RefactoringTextEdit(QTextEdit):
    def __init__(self, main_window, parent_dialog):
        super().__init__()
        self.main_window = main_window; self.parent_dialog = parent_dialog; self.active_cursor: QTextCursor = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.customContextMenuRequested.connect(self.show_context_menu)
    def show_context_menu(self, pos):
        menu = self.createStandardContextMenu(); cursor = self.textCursor()
        if not cursor.hasSelection(): menu.exec(self.mapToGlobal(pos)); return
        menu.addSeparator(); refactor_menu = menu.addMenu("KI-Refactoring")
        for action_text in REFACTOR_PROMPTS:
            action = refactor_menu.addAction(action_text); action.triggered.connect(self.handle_refactor_action)
        menu.exec(self.mapToGlobal(pos))
    def handle_refactor_action(self):
        action = self.sender()
        if not action: return
        self.active_cursor = self.textCursor(); selected_text = self.active_cursor.selectedText()
        base_prompt = REFACTOR_PROMPTS.get(action.text()); full_prompt = f"{base_prompt}\n\n```python\n{selected_text.strip()}\n```"
        self.setReadOnly(True); self.parent_dialog.statusBar().showMessage("Warte auf KI-Antwort für Refactoring...", 5000)
        worker = ApiWorker(); worker.moveToThread(self.main_window._api_thread)
        worker.response_ready.connect(self.on_refactor_response_ready); worker.error_occurred.connect(self.on_refactor_error)
        worker.finished.connect(worker.deleteLater)
        settings = self.main_window.settings; api_key = settings.value("api_key", ""); model_id = settings.value("model", "mistralai/mistral-7b-instruct")
        final_messages = [{"role": "user", "content": full_prompt}]; worker.set_request_data(api_key, model_id, final_messages, 2048, stream=False)
        QMetaObject.invokeMethod(worker, "make_request", Qt.QueuedConnection)
    def on_refactor_response_ready(self, response_text: str):
        self.setReadOnly(False); self.parent_dialog.statusBar().clearMessage()
        match = re.search(r"```(?:\w*\n)?(.*)```", response_text, re.DOTALL)
        new_code = match.group(1).strip() if match else response_text.strip()
        original_code = self.active_cursor.selectedText()
        diff = difflib.HtmlDiff(wrapcolumn=80); diff_html = diff.make_table(original_code.splitlines(), new_code.splitlines(), "Original", "Vorschlag")
        dialog = DiffDialog(diff_html, self.parent_dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.active_cursor.insertText(new_code)
        self.active_cursor = None
    def on_refactor_error(self, error_msg, code):
        self.setReadOnly(False); self.parent_dialog.statusBar().clearMessage()
        QMessageBox.critical(self.parent_dialog, "Refactoring-Fehler", f"Fehler bei der Anfrage (Code: {code}):\n{error_msg}")
        self.active_cursor = None

class CodeEditorPlugin(ChatPlugin):
    def get_name(self): return "Code Editor, Linter & Debugger"
    def get_description(self): return "Editor mit Tabs, Ausführung, 'flake8'-Prüfung, 'pdb'-Debugging und KI-Refactoring."
    def __init__(self, main_window):
        super().__init__(main_window)
        action = QAction(QIcon.fromTheme("accessories-text-editor"), "Code-Editor öffnen", self.main_window)
        action.triggered.connect(self.open_editor)
        
        # --- START: GEÄNDERTER CODE ---
        if hasattr(self.main_window, 'm_plugins'):
            self.main_window.m_plugins.addAction(action)
        else:
            self.main_window.menuBar().addMenu("Plugins").addAction(action)
        # --- ENDE: GEÄNDERTER CODE ---

    def open_editor(self, initial_content: str = "", initial_title: str = "Neue Datei"):
        editor = QDialog(self.main_window); editor.setWindowTitle("Code Editor"); editor.resize(900, 700)
        layout = QVBoxLayout(editor); status_bar = QLabel("Bereit"); editor.statusBar = status_bar
        tabs = QTabWidget(); tabs.setTabsClosable(True); tabs.tabCloseRequested.connect(tabs.removeTab); layout.addWidget(tabs)
        def new_tab(content="", title="Neue Datei"):
            edit = RefactoringTextEdit(self.main_window, editor); font = QFont("Monospace"); font.setStyleHint(QFont.StyleHint.TypeWriter)
            edit.setFont(font); edit.setPlainText(content); idx = tabs.addTab(edit, title); tabs.setCurrentIndex(idx); edit.setProperty("file_path", None)
        
        button_layout = QHBoxLayout()
        btn_new = QPushButton(" Neue Datei"); btn_new.setIcon(QIcon.fromTheme("document-new"))
        btn_open = QPushButton(" Öffnen..."); btn_open.setIcon(QIcon.fromTheme("document-open"))
        btn_save = QPushButton(" Speichern..."); btn_save.setIcon(QIcon.fromTheme("document-save"))
        btn_run = QPushButton(" Ausführen"); btn_run.setIcon(QIcon.fromTheme("media-playback-start"))
        btn_lint = QPushButton(" Prüfen"); btn_lint.setIcon(QIcon.fromTheme("dialog-warning"))
        btn_debug = QPushButton(" Debuggen"); btn_debug.setIcon(QIcon.fromTheme("debug-run"))
        
        button_layout.addWidget(btn_new); button_layout.addWidget(btn_open); button_layout.addWidget(btn_save)
        button_layout.addStretch()
        button_layout.addWidget(btn_run); button_layout.addWidget(btn_lint); button_layout.addWidget(btn_debug)
        layout.addLayout(button_layout); layout.addWidget(status_bar)
        
        def save_file_logic(current_widget):
            path = current_widget.property("file_path")
            if not path: path, _ = QFileDialog.getSaveFileName(editor, "Datei speichern", "", "Python Dateien (*.py);;Alle Dateien (*)")
            if path:
                with open(path, "w", encoding="utf-8") as f: f.write(current_widget.toPlainText())
                current_widget.setProperty("file_path", path); tabs.setTabText(tabs.currentIndex(), os.path.basename(path))
            return path
        btn_new.clicked.connect(lambda: new_tab())
        def open_file():
            path, _ = QFileDialog.getOpenFileName(editor, "Datei öffnen", "", "Python Dateien (*.py);;Alle Dateien (*)")
            if path:
                with open(path, "r", encoding="utf-8") as f: text = f.read()
                new_tab(text, os.path.basename(path)); tabs.currentWidget().setProperty("file_path", path)
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
            except subprocess.TimeoutExpired: QMessageBox.warning(editor, "Timeout", "Ausführung > 30s, abgebrochen.")
            except Exception as e: QMessageBox.critical(editor, "Fehler bei Ausführung", str(e))
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
            except FileNotFoundError: QMessageBox.critical(editor, "Fehler", "'flake8' wurde nicht gefunden.\nBitte installieren Sie es mit: pip install flake8")
            except Exception as e: QMessageBox.critical(editor, "Fehler beim Linten", str(e))
        btn_lint.clicked.connect(lint_code)
        def debug_code():
            current = tabs.currentWidget()
            if not current: return
            path = save_file_logic(current)
            if not path: return
            try:
                command = ["x-terminal-emulator", "-e", f"python3 -m pdb {path}"]
                subprocess.Popen(command)
            except FileNotFoundError: QMessageBox.critical(editor, "Fehler", "'x-terminal-emulator' nicht gefunden.\nBitte installieren Sie ein Standard-Terminal.")
            except Exception as e: QMessageBox.critical(editor, "Fehler beim Starten des Debuggers", str(e))
        btn_debug.clicked.connect(debug_code)
        new_tab(initial_content, initial_title)
        editor.exec()
    def show_output_dialog(self, parent, title, text):
        dialog = QDialog(parent); dialog.setWindowTitle(title); dialog.resize(800, 600)
        layout = QVBoxLayout(dialog); view = QTextEdit(readOnly=True); view.setFont(QFont("Monospace"))
        view.setPlainText(text); layout.addWidget(view); close_button = QPushButton("Schließen")
        close_button.clicked.connect(dialog.accept); layout.addWidget(close_button); dialog.exec()
