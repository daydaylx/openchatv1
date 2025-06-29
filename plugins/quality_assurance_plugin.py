from plugin_interface import ChatPlugin
from PySide6.QtWidgets import QAction, QDialog, QVBoxLayout, QPushButton, QFileDialog, QMessageBox, QTabWidget, QTextEdit
from PySide6.QtGui import QFont
import subprocess
import logging
import os # Wichtig für os.path.basename

logger = logging.getLogger("CodeEditorPlugin")

class CodeEditorPlugin(ChatPlugin):
    def get_name(self):
        return "Code Editor"
    
    def get_description(self):
        return "Einfacher Editor mit Tabs und Ausführung (ohne externe Abhängigkeiten)."

    def __init__(self, main_window):
        super().__init__(main_window)
        action = QAction("Code-Editor öffnen", self.main_window)
        action.triggered.connect(self.open_editor)
        self.main_window.menuBar().addAction(action)

    def open_editor(self):
        editor = QDialog(self.main_window)
        editor.setWindowTitle("Code Editor")
        editor.resize(900, 700)
        layout = QVBoxLayout(editor)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Neuer Tab mit Standard-QTextEdit
        def new_tab(content="", title="Neue Datei"):
            # Verwende QTextEdit statt QsciScintilla
            edit = QTextEdit()
            # Setze eine Monospace-Schriftart für bessere Code-Lesbarkeit
            font = QFont("Monospace")
            font.setStyleHint(QFont.TypeWriter)
            edit.setFont(font)
            edit.setPlainText(content) # Verwende setPlainText für reinen Text
            
            idx = tabs.addTab(edit, title)
            tabs.setCurrentIndex(idx)

        # Buttons-Layout erstellen für eine saubere Anordnung
        button_layout = QVBoxLayout()
        btn_new = QPushButton("Neue Datei")
        btn_open = QPushButton("Datei öffnen")
        btn_save = QPushButton("Datei speichern")
        btn_run = QPushButton("Code ausführen")
        
        button_layout.addWidget(btn_new)
        button_layout.addWidget(btn_open)
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_run)
        
        # Füge das Button-Layout zum Hauptlayout hinzu
        layout.addLayout(button_layout)

        btn_new.clicked.connect(lambda: new_tab())

        # Datei öffnen
        def open_file():
            try:
                path, _ = QFileDialog.getOpenFileName(editor, "Datei öffnen", "", "Python Dateien (*.py);;Alle Dateien (*)")
                if path:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                    new_tab(text, os.path.basename(path))
            except Exception as e:
                logger.exception(e)
                QMessageBox.critical(editor, "Fehler beim Öffnen", str(e))
        btn_open.clicked.connect(open_file)

        # Speichern
        def save_file():
            current = tabs.currentWidget()
            if current:
                try:
                    # Verwende den aktuellen Tab-Titel als Vorschlag für den Dateinamen
                    suggested_filename = tabs.tabText(tabs.currentIndex())
                    if suggested_filename == "Neue Datei":
                        suggested_filename = ""

                    path, _ = QFileDialog.getSaveFileName(editor, "Datei speichern", suggested_filename, "Python Dateien (*.py);;Alle Dateien (*)")
                    if path:
                        # Verwende toPlainText() für QTextEdit
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(current.toPlainText())
                        tabs.setTabText(tabs.currentIndex(), os.path.basename(path))
                except Exception as e:
                    logger.exception(e)
                    QMessageBox.critical(editor, "Fehler beim Speichern", str(e))
        btn_save.clicked.connect(save_file)

        # Ausführen
        def run_code():
            current = tabs.currentWidget()
            if current:
                temp_filename = "_temp_run.py"
                try:
                    # Verwende toPlainText() für QTextEdit
                    code = current.toPlainText()
                    with open(temp_filename, "w", encoding="utf-8") as f:
                        f.write(code)
                    
                    # Führe das Skript aus und fange die Ausgabe ab
                    result = subprocess.run(["python3", temp_filename], capture_output=True, text=True, timeout=30)
                    
                    # Zeige die Ausgabe in einem neuen Dialog an
                    output_dialog = QDialog(editor)
                    output_dialog.setWindowTitle("Ausgabe")
                    output_dialog.resize(800, 600)
                    v_layout = QVBoxLayout(output_dialog)
                    output_view = QTextEdit(readOnly=True)
                    output_view.setFont(QFont("Monospace"))
                    
                    output_text = f"--- STDOUT ---\n{result.stdout}\n\n--- STDERR ---\n{result.stderr}"
                    output_view.setPlainText(output_text)
                    
                    v_layout.addWidget(output_view)
                    
                    close_button = QPushButton("Schließen")
                    close_button.clicked.connect(output_dialog.accept)
                    v_layout.addWidget(close_button)
                    
                    output_dialog.exec()
                except subprocess.TimeoutExpired:
                     QMessageBox.warning(editor, "Timeout", "Die Ausführung des Codes hat zu lange gedauert und wurde abgebrochen.")
                except Exception as e:
                    logger.exception(e)
                    QMessageBox.critical(editor, "Fehler bei der Ausführung", str(e))
                finally:
                    # Temporäre Datei aufräumen
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)

        btn_run.clicked.connect(run_code)

        new_tab() # Ersten leeren Tab beim Öffnen erstellen
        editor.exec()

```

### Zusammenfassung Ihrer Optionen:

1.  **Versuchen Sie Plan A:** Führen Sie `apt-cache search qscintilla | grep qt6` aus, um den korrekten Paketnamen für Ihr System zu finden und zu installieren. Dies ist die beste Lösung, wenn sie funktioniert.
2.  **Nutzen Sie Plan B:** Wenn Plan A fehlschlägt, ersetzen Sie den Code Ihres Editor-Plugins mit der von mir bereitgestellten Version. Damit funktioniert das Plugin sofort, aber ohne die farbliche Hervorhebung.

Ich bin zuversichtlich, dass einer dieser Wege zum Erfolg führen wi
