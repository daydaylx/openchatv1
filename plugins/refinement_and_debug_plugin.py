# plugins/refinement_and_debug_plugin.py

import sys
from plugin_interface import ChatPlugin, Message
from PySide6.QtWidgets import QMenu, QInputDialog, QTextBrowser, QLineEdit, QMessageBox
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtCore import Qt

class AdvancedTextBrowser(QTextBrowser):
    """
    Ein erweitertes TextBrowser-Widget, das ein Kontextmenü für die Code-Verfeinerung
    und das Debugging im Editor bereitstellt.
    """
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setOpenExternalLinks(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        """Erstellt und zeigt das benutzerdefinierte Kontextmenü an."""
        menu = self.createStandardContextMenu()
        
        selected_text = self.textCursor().selectedText()
        if selected_text:
            menu.addSeparator()
            
            # Aktion 1: Code verfeinern
            refine_action = QAction("Markierung verfeinern...", self)
            refine_action.triggered.connect(lambda: self.refine_code(selected_text))
            menu.addAction(refine_action)
            
            # Aktion 2: Code im Editor zum Debuggen öffnen
            debug_action = QAction("Markierung im Editor debuggen...", self)
            debug_action.triggered.connect(lambda: self.debug_in_editor(selected_text))
            menu.addAction(debug_action)
        
        menu.exec(self.mapToGlobal(pos))

    def refine_code(self, code_snippet: str):
        """Öffnet einen Dialog, um die Verfeinerungs-Anweisung zu erhalten."""
        prompt, ok = QInputDialog.getText(self, "Code verfeinern", "Ihre Anweisung für den markierten Code:", QLineEdit.EchoMode.Normal)
        if ok and prompt:
            full_prompt = f"Bitte überarbeite den folgenden Code-Abschnitt:\n```\n{code_snippet.strip()}\n```\n\nAnweisung: {prompt}"
            self.main_window.chat.inp.setText(full_prompt)
            self.main_window._send()

    def debug_in_editor(self, code_snippet: str):
        """Findet das Code-Editor-Plugin und übergibt den Code-Schnipsel."""
        editor_plugin = None
        # Suche nach dem Editor-Plugin im PluginManager
        for plugin in self.main_window.plugin_manager.plugins:
            # Wir suchen flexibel nach dem Namen, falls der Nutzer ihn ändert.
            if "Code Editor" in plugin.get_name():
                editor_plugin = plugin
                break
        
        if editor_plugin:
            try:
                # Rufe die (modifizierte) open_editor Methode auf und übergebe den Code
                editor_plugin.open_editor(initial_content=code_snippet, initial_title="Debug Snippet")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Öffnen des Editors: {e}")
        else:
            QMessageBox.warning(self, "Plugin nicht gefunden", "Das 'Code Editor'-Plugin wurde nicht gefunden oder ist nicht geladen.")


class RefinementAndDebugPlugin(ChatPlugin):
    """
    Dieses Plugin ersetzt die Standard-Antwortansicht, um iterative Code-Verbesserung
    und das Senden von Code an den Editor-Debugger zu ermöglichen.
    """
    def get_name(self) -> str:
        return "Interaktions-Helfer (Verfeinern & Debuggen)"

    def get_description(self) -> str:
        return "Fügt ein Rechtsklick-Menü zur KI-Antwort für Code-Interaktionen hinzu."

    def __init__(self, main_window):
        super().__init__(main_window)
        try:
            chat_panes_layout = self.main_window.chat.layout().itemAt(0)
            if not chat_panes_layout: return
            assistant_pane_layout = chat_panes_layout.itemAt(1)
            if not assistant_pane_layout: return
            
            old_browser = self.main_window.chat.assistant_view
            if not old_browser: return
            
            new_browser = AdvancedTextBrowser(self.main_window)
            assistant_pane_layout.replaceWidget(old_browser, new_browser)
            old_browser.deleteLater()
            
            self.main_window.chat.assistant_view = new_browser
            print("RefinementAndDebugPlugin: Assistant-Ansicht erfolgreich für Kontextmenü ersetzt.")
        except Exception as e:
            print(f"Fehler im RefinementAndDebugPlugin: {e}", file=sys.stderr)


