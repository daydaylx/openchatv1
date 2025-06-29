# plugins/refinement_and_debug_plugin.py

import sys
import logging
from plugin_interface import ChatPlugin
from PySide6.QtWidgets import QMenu, QInputDialog, QTextBrowser, QLineEdit, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)

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
            
            refine_action = QAction("Markierung verfeinern...", self)
            refine_action.triggered.connect(lambda: self.refine_code(selected_text))
            menu.addAction(refine_action)
            
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
        editor_plugin = next((p for p in self.main_window.plugin_manager.plugins if "Code Editor" in p.get_name()), None)
        
        if editor_plugin:
            try:
                # Die open_editor Methode wird direkt auf der Plugin-Instanz aufgerufen
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
            # --- START: GEÄNDERTER CODE FÜR NEUES LAYOUT ---
            # Wir greifen auf das Hauptlayout des Chat-Widgets zu, das wir in V14 zugänglich gemacht haben
            chat_widget_layout = self.main_window.chat.layout()
            if not chat_widget_layout: return

            # Finde den alten Browser im Layout
            old_browser = self.main_window.chat.chat_view
            if not old_browser: return
            
            # Erstelle den neuen Browser
            new_browser = AdvancedTextBrowser(self.main_window)
            
            # Ersetze das Widget im Layout
            chat_widget_layout.replaceWidget(old_browser, new_browser)
            
            # Lösche das alte Widget sicher
            old_browser.deleteLater()
            
            # Aktualisiere die Referenzen im Chat-Widget und im Hauptfenster
            self.main_window.chat.chat_view = new_browser
            self.main_window.chat.assistant_view = new_browser # Für Kompatibilität
            logger.info("Interaktions-Helfer: Chat-Ansicht erfolgreich für Kontextmenü ersetzt.")
            # --- ENDE: GEÄNDERTER CODE ---
        except Exception as e:
            logger.error(f"Fehler bei der Initialisierung des Interaktions-Helfer-Plugins: {e}", exc_info=True)
