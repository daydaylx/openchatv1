from plugin_interface import ChatPlugin
from PySide6.QtWidgets import QAction, QMessageBox, QFileDialog
import os
import re

class ScaffoldAndWritePlugin(ChatPlugin):
    def get_name(self):
        return "Projektstruktur & Inhalte anlegen"
    def get_description(self):
        return "Legt KI-generierte Ordner, Dateien und deren Inhalte robust an – inklusive Fehlerübersicht."

    def __init__(self, main_window):
        super().__init__(main_window)
        # Menüeintrag einfügen
        action = QAction("Struktur & Inhalte anlegen", self.main_window)
        action.triggered.connect(self.run_scaffold_and_write)
        self.main_window.menuBar().addAction(action)

    def extract_structure(self, text):
        """Extrahiert die Struktur aus Markdown-Codeblöcken oder einfachen Listen."""
        # Falls Markdown-Codeblock, nur dessen Inhalt verwenden
        match = re.search(r"```(?:[a-zA-Z]*\\n)?([\\s\\S]*?)```", text)
        if match:
            text = match.group(1)
        # Filtert Kommentare/Leerzeilen, entfernt „├─│“ etc.
        return [l.strip(" │├─") for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]

    def find_files_and_content(self, messages):
        """Findet alle Datei/Codeblöcke im Chat – erkennt viele Marker-Stile."""
        files = {}
        # Marker wie: # Datei: pfad.py   (oder englisch)
        file_regex = re.compile(
            r"(?:(?:# ?(?:File|Datei):|// ?(?:File|Datei):)[ \\t]*|^)([\\w\\-/\\.]+\\.[\\w]+)\\s*\\n+"
            r"(?:```[a-zA-Z0-9]*\\n)?([\\s\\S]+?)(?:(?:```)|(?=\\n[#/ ]{0,10}(?:File|Datei):)|\\Z)",
            re.MULTILINE
        )
        # Auch: Dateiname als eigene Zeile über Codeblock (ohne Marker)
        alt_regex = re.compile(
            r"^([\\w\\-/\\.]+\\.[\\w]+)\\s*\\n+"
            r"(?:```[a-zA-Z0-9]*\\n)?([\\s\\S]+?)(?:(?:```)|\\Z)",
            re.MULTILINE
        )
        for m in messages:
            content = m.content
            # Marker-Variante
            for match in file_regex.finditer(content):
                fname, code = match.group(1), match.group(2).strip()
                if fname not in files or len(code) > len(files[fname]):
                    files[fname] = code
            # Alternativ-Variante
            for match in alt_regex.finditer(content):
                fname, code = match.group(1), match.group(2).strip()
                if fname not in files or len(code) > len(files[fname]):
                    files[fname] = code
        return files

    def run_scaffold_and_write(self):
        # 1. Zielordner wählen
        root_dir = QFileDialog.getExistingDirectory(self.main_window, "Projektziel wählen")
        if not root_dir:
            return

        messages = self.main_window.chat.messages
        errors, created, written = [], [], []

        # 2. Struktur finden und anlegen
        struct_text = None
        for m in reversed(messages):
            if m.role == "assistant" and "/" in m.content:
                struct_text = m.content
                break
        if struct_text:
            struct_lines = self.extract_structure(struct_text)
            for entry in struct_lines:
                name = entry.strip(" :")
                if not name or name.startswith("#"):
                    continue
                path = os.path.join(root_dir, name)
                try:
                    # Ordner, falls kein Punkt im Namen (außer .gitignore etc.)
                    if entry.endswith("/") or (not os.path.splitext(entry)[1] and not entry.startswith(".")):
                        os.makedirs(path, exist_ok=True)
                        created.append(path + "/")
                    else:
                        folder = os.path.dirname(path)
                        if folder and not os.path.exists(folder):
                            os.makedirs(folder, exist_ok=True)
                        if not os.path.exists(path):
                            with open(path, "w", encoding="utf-8") as f:
                                pass
                            created.append(path)
                except Exception as e:
                    errors.append(f"Ordner/Datei {name}: {e}")

        # 3. Dateien mit Inhalt suchen und schreiben
        files = self.find_files_and_content(messages)
        for fname, code in files.items():
            abspath = os.path.join(root_dir, fname)
            folder = os.path.dirname(abspath)
            try:
                os.makedirs(folder, exist_ok=True)
                overwrite = os.path.exists(abspath)
                with open(abspath, "w", encoding="utf-8") as f:
                    f.write(code)
                written.append(f"{fname}" + (" (überschrieben)" if overwrite else ""))
            except Exception as e:
                errors.append(f"Inhalt {fname}: {e}")

        # 4. Zusammenfassung
        summary = f"{len(created)} Ordner/Dateien angelegt.\\n{len(written)} Dateien mit Inhalt gefüllt.\\n"
        if errors:
            summary += f"\\nFehler:\\n" + \"\\n\".join(errors)
        else:
            summary += "\\nAlles erfolgreich!"
        QMessageBox.information(self.main_window, "Struktur & Inhalte", summary)

