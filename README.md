# OpenRouter Chat GUI - Das Komplette Handbuch

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg) ![UI Toolkit](https://img.shields.io/badge/UI-PySide6-blueviolet.svg) ![Lizenz](https://img.shields.io/badge/Lizenz-MIT-green.svg)

Willkommen beim OpenRouter Chat GUI! Dies ist eine erweiterbare, modulare Desktop-Anwendung für die Interaktion mit der OpenRouter.ai API, maßgeschneidert für Entwickler-Workflows auf Linux-Systemen wie Linux Mint. Das Projekt ist mehr als nur ein Chat-Client; es ist eine integrierte Entwicklungsumgebung (IDE), die den gesamten Zyklus von der Ideenfindung mit einer KI bis hin zur Erstellung, Bearbeitung, Prüfung und dem Debugging von Code unterstützt.

Das Herzstück ist ein robustes Plugin-System, das es Ihnen ermöglicht, die Anwendung tiefgreifend an Ihre Bedürfnisse anzupassen.

---

## 1. Philosophie & Architektur

* **Modularität & Erweiterbarkeit**: Die Kernanwendung bleibt schlank. Neue, komplexe Funktionen werden als eigenständige Plugins implementiert. Dies sorgt für hohe Wartbarkeit und Stabilität.
* **Robuste Fehlerbehandlung**: Die Anwendung ist so konzipiert, dass fehlerhafte Plugins den Start oder Betrieb der Hauptanwendung nicht beeinträchtigen. Fehler werden protokolliert, aber nicht zum Absturz führen.
* **Nahtloser Entwickler-Workflow**: Die mitgelieferten Plugins sind keine isolierten Werkzeuge, sondern so gestaltet, dass sie nahtlos ineinandergreifen. Sie unterstützen den folgenden Zyklus:
    1.  **Kontext beschaffen**: Mit dem `Datei Import`-Plugin bestehenden Code oder Dokumente in den Chat laden.
    2.  **Generieren & Entwerfen**: Die KI zur Erstellung von Code, Konzepten oder Projektstrukturen nutzen.
    3.  **Strukturieren**: Mit dem `Projektstruktur & Inhalte`-Plugin ein komplettes Projektverzeichnis aus der KI-Antwort auf der Festplatte anlegen.
    4.  **Bearbeiten & Prüfen**: Den generierten Code im `Code Editor` öffnen, mit `flake8` auf Fehler prüfen und anpassen.
    5.  **Testen & Debuggen**: Das Skript direkt aus dem Editor heraus ausführen oder eine interaktive Debugging-Sitzung mit `pdb` starten.
    6.  **Iterieren**: Code-Schnipsel direkt aus dem Chat heraus mit dem `Interaktions-Helfer` zur gezielten Verfeinerung an die KI zurücksenden oder zum Debuggen im Editor öffnen.

---

## 2. Installation & Einrichtung

### Schritt 2.1: Systemvoraussetzungen
Dieses Projekt wurde für Linux Mint entwickelt und nutzt Standard-Systemwerkzeuge.
* **Python 3.9+**
* **git** (empfohlen)
* Ein Standard-Terminal (z.B. `gnome-terminal`, `x-terminal-emulator` wird benötigt)

### Schritt 2.2: Projekt-Setup
Führen Sie diese Befehle in Ihrem Terminal aus.

```bash
# 1. Projekt klonen oder herunterladen und in den Ordner wechseln
# git clone https://ihr-repository/open-router-chat.git
# cd open-router-chat

# 2. Eine virtuelle Umgebung erstellen, um Abhängigkeiten zu isolieren
python3 -m venv .venv

# 3. Die virtuelle Umgebung aktivieren
source .venv/bin/activate

# 4. Erstellen Sie die Datei requirements.txt mit dem unten stehenden Inhalt
```

### Schritt 2.3: Abhängigkeiten installieren
Erstellen Sie eine Datei namens **`requirements.txt`** im Hauptverzeichnis mit folgendem Inhalt:

```
PySide6
requests
Pygments
flake8
PyPDF2
```

Installieren Sie nun alle Abhängigkeiten mit einem einzigen Befehl:

```bash
python3 -m pip install -r requirements.txt
```

### Schritt 2.4: API-Key konfigurieren
1.  Starten Sie die Anwendung: `python3 openchat_with_plugins.py`
2.  Folgen Sie dem Dialog, um Ihre Einstellungen zu öffnen.
3.  Im Tab "API" geben Sie Ihren OpenRouter-Key ein (beginnend mit `sk-or-v1-...`).
4.  Speichern Sie. Die Anwendung ist nun einsatzbereit.

---

## 3. Die Plugin-Werkzeugkiste

Dies ist eine detaillierte Übersicht über das empfohlene, optimierte Set von Plugins, das den Kern Ihrer Entwicklungs-Suite bildet.

### Plugin 1: Command Handler
* **Zweck**: Stellt grundlegende Slash-Befehle zur Steuerung des Chats bereit.
* **Abhängigkeiten**: Keine.
* **Verwendung**: Geben Sie `/help` oder `/clear` in das Chat-Feld ein.
* **Quellcode (`command_plugin.py`):**
    ```python
    import os
    from plugin_interface import ChatPlugin
    from PySide6.QtWidgets import QMessageBox

    class CommandPlugin(ChatPlugin):
        """Ein einfaches Plugin zur Implementierung von Slash-Befehlen."""
        def get_name(self) -> str:
            return "Command Handler"
        def get_description(self) -> str:
            return "Verarbeitet Befehle wie /clear und /help."
        def on_user_message(self, message: str) -> bool:
            if message.lower() == "/clear":
                self.main_window.chat.clear()
                return True
            if message.lower() == "/help":
                help_text = """<b>Verfügbare Befehle:</b><br>
                <ul>
                    <li><code>/clear</code> - Löscht den gesamten Chatverlauf.</li>
                    <li><code>/help</code> - Zeigt diese Hilfe an.</li>
                </ul>"""
                QMessageBox.information(self.main_window, "Hilfe", help_text)
                return True
            return False
    ```

### Plugin 2: Syntax Highlighter
* **Zweck**: Verbessert die Lesbarkeit von Code im Chatfenster durch farbliche Hervorhebung.
* **Abhängigkeiten**: `Pygments` (in `requirements.txt` enthalten).
* **Verwendung**: Automatisch. Das Plugin erkennt Codeblöcke in KI-Antworten und färbt sie ein.
* **Quellcode (`syntax_highlight_plugin.py`):**
    ```python
    import re
    from html import escape
    from plugin_interface import ChatPlugin, Message
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import HtmlFormatter

    class SyntaxHighlightPlugin(ChatPlugin):
        """Findet Codeblöcke in KI-Antworten und hebt sie mit Pygments hervor."""
        def get_name(self) -> str:
            return "Syntax Highlighter"
        def get_description(self) -> str:
            return "Färbt Codeblöcke in den Antworten der KI."
        def on_api_response(self, message_object: Message):
            content = message_object.content
            pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
            escaped_content = escape(content)
            def replacer(match):
                lang, code = match.group(1).strip(), match.group(2)
                try:
                    lexer = get_lexer_by_name(lang, stripall=True) if lang else guess_lexer(code, stripall=True)
                except Exception:
                    lexer = get_lexer_by_name("text", stripall=True)
                formatter = HtmlFormatter(style='dracula', nobackground=True)
                return highlight(code, lexer, formatter)
            new_content, count = pattern.subn(replacer, escaped_content)
            if count > 0:
                message_object.content = new_content.replace('\n', '<br>')
                message_object.display_format = 'html'
    ```

### Plugin 3: Datei Import
* **Zweck**: Ermöglicht das Laden von lokalen Dateien als Kontext in den Chat.
* **Abhängigkeiten**: `PyPDF2` (optional, nur für PDF-Dateien).
* **Verwendung**: Über den Menüeintrag "Datei einfügen".
* **Quellcode (`file_import_plugin.py`):**
    ```python
    from plugin_interface import ChatPlugin
    from PySide6.QtWidgets import QAction, QFileDialog, QMessageBox
    import os
    try:
        from PyPDF2 import PdfReader
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

    class FileImportPlugin(ChatPlugin):
        def get_name(self): return "Datei Import"
        def get_description(self): return "Importiert .md, .txt, .py und .pdf Dateien in den Chat."
        def __init__(self, main_window):
            super().__init__(main_window)
            action = QAction("Datei einfügen", self.main_window)
            action.triggered.connect(self.import_file)
            # Finde das Datei-Menü und füge die Aktion hinzu
            file_menu = next((m for m in self.main_window.menuBar().actions() if m.text() == "&Datei"), None)
            if file_menu:
                file_menu.menu().insertAction(self.main_window.menuBar().actions()[1], action)
        def import_file(self):
            path, _ = QFileDialog.getOpenFileName(self.main_window, "Datei auswählen", "", "Erlaubte Dateien (*.txt *.md *.py *.pdf)")
            if not path: return
            try:
                if path.endswith(".pdf"):
                    if not PDF_AVAILABLE:
                        QMessageBox.warning(self.main_window, "PDF-Abhängigkeit fehlt", "Für PDF-Import bitte `PyPDF2` installieren: pip install PyPDF2")
                        return
                    text = "".join(p.extract_text() or "" for p in PdfReader(path).pages)
                else:
                    with open(path, "r", encoding="utf-8") as f: text = f.read()
                maxlen = 8000
                if len(text) > maxlen: text = text[:maxlen] + "\n... (gekürzt)"
                self.main_window.chat.add_message("user", f"Inhalt von {os.path.basename(path)}:\n\n{text}")
            except Exception as e:
                QMessageBox.critical(self.main_window, "Fehler beim Laden", str(e))
    ```

### Plugin 4: Projektstruktur & Inhalte anlegen
* **Zweck**: Erstellt ein komplettes Projektverzeichnis inklusive aller Ordner und Dateien basierend auf einer KI-Antwort.
* **Abhängigkeiten**: Keine.
* **Verwendung**: Über den Menüeintrag "Struktur & Inhalte anlegen". Das Plugin durchsucht den Chatverlauf nach einer Verzeichnisstruktur und den dazugehörigen Codeblöcken.
* **Quellcode (`project_scaffold_plugin.py`):**
    ```python
    from plugin_interface import ChatPlugin
    from PySide6.QtWidgets import QAction, QMessageBox, QFileDialog
    import os
    import re

    class ScaffoldAndWritePlugin(ChatPlugin):
        def get_name(self): return "Projektstruktur & Inhalte anlegen"
        def get_description(self): return "Legt KI-generierte Ordner, Dateien und deren Inhalte robust an."
        def __init__(self, main_window):
            super().__init__(main_window)
            action = QAction("Struktur & Inhalte anlegen", self.main_window)
            action.triggered.connect(self.run_scaffold_and_write)
            self.main_window.menuBar().addAction(action)
        def extract_structure(self, text):
            match = re.search(r"```(?:[a-zA-Z]*\n)?([\s\S]*?)```", text)
            if match: text = match.group(1)
            return [l.strip(" │├─") for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        def find_files_and_content(self, messages):
            files = {}
            file_regex = re.compile(r"(?:(?:# ?(?:File|Datei):|// ?(?:File|Datei):)[ \t]*|^)([\w\-/]+\.[\w]+)\s*\n+(?:```[a-zA-Z0-9]*\n)?([\s\S]+?)(?:(?:```)|(?=\n[#/ ]{0,10}(?:File|Datei):)|\Z)", re.MULTILINE)
            for m in messages:
                for match in file_regex.finditer(m.content):
                    fname, code = match.group(1).strip(), match.group(2).strip()
                    if fname not in files or len(code) > len(files[fname]): files[fname] = code
            return files
        def run_scaffold_and_write(self):
            root_dir = QFileDialog.getExistingDirectory(self.main_window, "Projektziel wählen")
            if not root_dir: return
            messages, errors, created, written = self.main_window.chat.messages, [], [], []
            struct_text = next((m.content for m in reversed(messages) if m.role == "assistant" and "/" in m.content), None)
            if struct_text:
                for entry in self.extract_structure(struct_text):
                    name = entry.strip(" :"); path = os.path.join(root_dir, name)
                    try:
                        if entry.endswith("/") or (not os.path.splitext(name)[1] and not name.startswith(".")): os.makedirs(path, exist_ok=True); created.append(f"Ordner: {name}")
                        else:
                            if (folder := os.path.dirname(path)) and not os.path.exists(folder): os.makedirs(folder)
                            if not os.path.exists(path): open(path, "w").close(); created.append(f"Datei: {name}")
                    except Exception as e: errors.append(f"{name}: {e}")
            files = self.find_files_and_content(messages)
            for fname, code in files.items():
                abspath = os.path.join(root_dir, fname)
                try:
                    os.makedirs(os.path.dirname(abspath), exist_ok=True)
                    overwrite = os.path.exists(abspath)
                    with open(abspath, "w", encoding="utf-8") as f: f.write(code)
                    written.append(f"{fname}" + (" (überschrieben)" if overwrite else ""))
                except Exception as e: errors.append(f"{fname}: {e}")
            summary = f"Aktion abgeschlossen:\n\n- {len(created)} Ordner/Dateien angelegt\n- {len(written)} Dateien geschrieben\n"
            if errors: summary += f"\nFehler:\n" + "\n".join(f"- {e}" for e in errors)
            QMessageBox.information(self.main_window, "Ergebnis", summary)
    ```

### Plugin 5: Code Editor, Linter & Debugger
* **Zweck**: Das zentrale Werkzeug zur Code-Bearbeitung. Bietet einen Editor mit Tabs, die Möglichkeit, Code auszuführen, mit `flake8` zu prüfen und mit `pdb` zu debuggen.
* **Abhängigkeiten**: `flake8` (in `requirements.txt` enthalten).
* **Verwendung**: Über den Menüeintrag "Code-Editor öffnen".
* **Quellcode (`code_editor_plugin.py`):**
    ```python
    import os, sys, subprocess, logging
    from plugin_interface import ChatPlugin
    from PySide6.QtWidgets import QAction, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QTabWidget, QTextEdit
    from PySide6.QtGui import QFont

    class CodeEditorPlugin(ChatPlugin):
        def get_name(self): return "Code Editor, Linter & Debugger"
        def get_description(self): return "Editor mit Tabs, Ausführung, 'flake8'-Prüfung und 'pdb'-Debugging."
        def __init__(self, main_window):
            super().__init__(main_window)
            action = QAction("Code-Editor öffnen", self.main_window)
            action.triggered.connect(self.open_editor)
            edit_menu = next((m for m in self.main_window.menuBar().actions() if m.text() == "&Bearbeiten"), None)
            if edit_menu: edit_menu.menu().addAction(action)
            else: self.main_window.menuBar().addAction(action)
        def open_editor(self, initial_content: str = "", initial_title: str = "Neue Datei"):
            editor = QDialog(self.main_window); editor.setWindowTitle("Code Editor"); editor.resize(900, 700)
            layout = QVBoxLayout(editor); tabs = QTabWidget(); tabs.setTabsClosable(True); tabs.tabCloseRequested.connect(tabs.removeTab)
            layout.addWidget(tabs)
            def new_tab(content="", title="Neue Datei"):
                edit = QTextEdit(); font = QFont("Monospace"); font.setStyleHint(QFont.StyleHint.TypeWriter); edit.setFont(font)
                edit.setPlainText(content); idx = tabs.addTab(edit, title); tabs.setCurrentIndex(idx); edit.setProperty("file_path", None)
            
            # Button-Logik und -Layout
            btn_layout=QHBoxLayout(); btns = {n: QPushButton(n) for n in ["Neue Datei", "Öffnen...", "Speichern...", "Ausführen", "Code prüfen (Lint)", "Debuggen"]}
            btn_layout.addWidget(btns["Neue Datei"]); btn_layout.addWidget(btns["Öffnen..."]); btn_layout.addWidget(btns["Speichern..."]); btn_layout.addStretch()
            btn_layout.addWidget(btns["Ausführen"]); btn_layout.addWidget(btns["Code prüfen (Lint)"]); btn_layout.addWidget(btns["Debuggen"]); layout.addLayout(btn_layout)

            def save_logic(widget):
                path = widget.property("file_path") or QFileDialog.getSaveFileName(editor, "Speichern", "", "*.py;;*.*")[0]
                if path:
                    with open(path, "w", encoding="utf-8") as f: f.write(widget.toPlainText())
                    widget.setProperty("file_path", path); tabs.setTabText(tabs.currentIndex(), os.path.basename(path))
                return path

            def run_logic(cmd_func, title_prefix):
                widget = tabs.currentWidget()
                if not widget or not (path := save_logic(widget)): return
                try:
                    res = subprocess.run(cmd_func(path), capture_output=True, text=True, timeout=30)
                    output = res.stdout if res.stdout else ("Keine Probleme gefunden." if title_prefix=="Lint" else "Keine Ausgabe.")
                    if res.stderr: output += f"\n\n--- FEHLER ---\n{res.stderr}"
                    self.show_output(editor, f"{title_prefix}: {os.path.basename(path)}", output)
                except FileNotFoundError as e: QMessageBox.critical(editor, "Fehler", f"Befehl nicht gefunden: {e.filename}. Ist es installiert?")
                except Exception as e: QMessageBox.critical(editor, "Fehler", str(e))
            
            btns["Neue Datei"].clicked.connect(lambda: new_tab())
            btns["Öffnen..."].clicked.connect(lambda: (p:=(QFileDialog.getOpenFileName(editor, "Öffnen", "", "*.py;;*.*")[0])) and (new_tab(open(p).read(), os.path.basename(p)), tabs.currentWidget().setProperty("file_path", p)))
            btns["Speichern..."].clicked.connect(lambda: tabs.currentWidget() and save_logic(tabs.currentWidget()))
            btns["Ausführen"].clicked.connect(lambda: run_logic(lambda p: [sys.executable, p], "Ausgabe"))
            btns["Code prüfen (Lint)"].clicked.connect(lambda: run_logic(lambda p: [sys.executable, "-m", "flake8", p], "Lint"))
            btns["Debuggen"].clicked.connect(lambda: (w:=tabs.currentWidget()) and (p:=save_logic(w)) and subprocess.Popen(["x-terminal-emulator", "-e", f"python3 -m pdb {p}"]))
            
            new_tab(initial_content, initial_title); editor.exec()
        def show_output(self, parent, title, text):
            dialog = QDialog(parent); dialog.setWindowTitle(title); dialog.resize(800, 600)
            layout=QVBoxLayout(dialog); view=QTextEdit(readOnly=True); view.setFont(QFont("Monospace")); view.setPlainText(text)
            layout.addWidget(view); btn=QPushButton("Schließen"); btn.clicked.connect(dialog.accept); layout.addWidget(btn); dialog.exec()
    ```

### Plugin 6: Interaktions-Helfer (Verfeinern & Debuggen)
* **Zweck**: Das Bindeglied zwischen Chat und Editor. Ermöglicht es, Code-Schnipsel aus einer KI-Antwort direkt per Rechtsklick entweder zur gezielten Überarbeitung an die KI zurückzusenden oder zur Analyse im Code-Editor zu öffnen.
* **Abhängigkeiten**: Keine.
* **Verwendung**: Text in der rechten Chat-Spalte (KI-Antwort) markieren und mit der rechten Maustaste klicken.
* **Quellcode (`refinement_and_debug_plugin.py`):**
    ```python
    import sys
    from plugin_interface import ChatPlugin, Message
    from PySide6.QtWidgets import QMenu, QInputDialog, QTextBrowser, QLineEdit, QMessageBox
    from PySide6.QtGui import QAction, QContextMenuEvent
    from PySide6.QtCore import Qt

    class AdvancedTextBrowser(QTextBrowser):
        """Erweitertes QTextBrowser mit Rechtsklick-Menü für Code-Interaktionen."""
        def __init__(self, main_window, parent=None):
            super().__init__(parent)
            self.main_window = main_window
            self.setOpenExternalLinks(True)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self.show_context_menu)
        def show_context_menu(self, pos):
            menu = self.createStandardContextMenu()
            if selected_text := self.textCursor().selectedText():
                menu.addSeparator()
                refine_action = QAction("Markierung verfeinern...", self)
                refine_action.triggered.connect(lambda: self.refine_code(selected_text))
                debug_action = QAction("Markierung im Editor debuggen...", self)
                debug_action.triggered.connect(lambda: self.debug_in_editor(selected_text))
                menu.addAction(refine_action)
                menu.addAction(debug_action)
            menu.exec(self.mapToGlobal(pos))
        def refine_code(self, code_snippet: str):
            prompt, ok = QInputDialog.getText(self, "Code verfeinern", "Ihre Anweisung für den markierten Code:", QLineEdit.EchoMode.Normal)
            if ok and prompt:
                full_prompt = f"Bitte überarbeite den folgenden Code-Abschnitt:\n```\n{code_snippet.strip()}\n```\n\nAnweisung: {prompt}"
                self.main_window.chat.inp.setText(full_prompt)
                self.main_window._send()
        def debug_in_editor(self, code_snippet: str):
            editor_plugin = next((p for p in self.main_window.plugin_manager.plugins if "Code Editor" in p.get_name()), None)
            if editor_plugin:
                try:
                    editor_plugin.open_editor(initial_content=code_snippet, initial_title="Debug Snippet")
                except Exception as e:
                    QMessageBox.critical(self, "Fehler", f"Fehler beim Öffnen des Editors: {e}")
            else:
                QMessageBox.warning(self, "Plugin nicht gefunden", "Das 'Code Editor'-Plugin ist nicht geladen.")

    class RefinementAndDebugPlugin(ChatPlugin):
        """Ersetzt die Standard-Antwortansicht, um iterative Code-Verbesserung zu ermöglichen."""
        def get_name(self) -> str: return "Interaktions-Helfer (Verfeinern & Debuggen)"
        def get_description(self) -> str: return "Fügt ein Rechtsklick-Menü zur KI-Antwort hinzu."
        def __init__(self, main_window):
            super().__init__(main_window)
            try:
                assistant_pane = self.main_window.chat.layout().itemAt(0).itemAt(1)
                old_browser = self.main_window.chat.assistant_view
                new_browser = AdvancedTextBrowser(self.main_window)
                assistant_pane.replaceWidget(old_browser, new_browser)
                old_browser.deleteLater()
                self.main_window.chat.assistant_view = new_browser
                print("Interaktions-Helfer-Plugin: UI erfolgreich modifiziert.")
            except Exception as e:
                print(f"Fehler im Interaktions-Helfer-Plugin: {e}", file=sys.stderr)
    ```

---

## 4. Eigene Plugins erstellen

Um die Anwendung weiter anzupassen, können Sie eigene Plugins erstellen.

1.  Erstellen Sie eine neue `.py`-Datei im `plugins`-Ordner.
2.  Importieren Sie `ChatPlugin` aus `plugin_interface`.
3.  Erstellen Sie eine Klasse, die von `ChatPlugin` erbt, und implementieren Sie die Methoden `get_name`, `get_description` und die gewünschten Hooks (`on_user_message`, `on_api_response`).
4.  Starten Sie die Anwendung neu. Ihr Plugin wird automatisch geladen.

