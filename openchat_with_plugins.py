#!/usr/bin/env python3
"""
OpenRouter Chat GUI - Finale, stabile und neustrukturierte Version
--------------------------------------------------------------------
Diese Version behebt alle bekannten Fehler, implementiert eine
automatische, token-basierte Kontextmaximierung und enthält ein
robustes Plugin-System. Die System-Prompts werden extern geladen.
Die Darstellung von HTML-formatierten Nachrichten durch Plugins wird unterstützt.

**Änderungsprotokoll (Benutzer-Anpassung V9 - Plugin HTML-Support):**
- Message-Klasse um 'display_format' erweitert.
- ChatWidget._refresh kann nun reines HTML von Plugins darstellen.
- Plugin-Hook 'on_api_response' übergibt das gesamte Message-Objekt.
- Notwendige CSS-Stile für Pygments-Syntax-Highlighting hinzugefügt.
"""

import sys
import os
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional, Type
from html import escape
import traceback
import logging
import importlib.util
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QLineEdit, QPushButton, QLabel, QTextEdit, QDialog, QComboBox, QSpinBox,
    QCheckBox, QMessageBox, QStatusBar, QFileDialog, QProgressBar, QTabWidget,
    QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QObject, QMetaObject, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIntValidator

# Importieren der Plugin-Schnittstelle
try:
    from plugin_interface import ChatPlugin, Message
except ImportError:
    # Fallback, falls die Datei nicht gefunden wird, um Abstürze zu vermeiden
    class Message:
        def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None):
            self.role, self.content = role, content
            self.timestamp = timestamp or datetime.now()
            self.display_format = "text"
        def to_dict(self) -> Dict:
            return {"role": self.role, "content": self.content, "timestamp": self.timestamp.isoformat()}

    class ChatPlugin:
        def __init__(self, main_window): pass
        def get_name(self) -> str: return "Interface Missing"
        def get_description(self) -> str: return "plugin_interface.py not found"
        def on_user_message(self, message) -> bool: return False
        def on_api_response(self, message_object: Message): pass


# --- Logging Konfiguration ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OpenRouterChat")


# --- Laden der System-Prompts ---
def load_system_prompts_from_json(file_path: Path) -> Dict[str, str]:
    """
    Lädt System-Prompts aus einer JSON-Datei.
    Fügt den 'Benutzerdefiniert'-Eintrag hinzu und bietet einen Fallback.
    """
    fallback_prompts = {
        "Kein Systemprompt": "",
        "Standard-Assistent": "Du bist ein hilfreicher Assistent."
    }
    if not file_path.exists():
        logger.warning(f"Prompt-Datei '{file_path}' nicht gefunden. Nutze Fallback-Prompts.")
        prompts = fallback_prompts
    else:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                prompts = json.load(f)
            logger.info(f"System-Prompts erfolgreich aus '{file_path}' geladen.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Fehler beim Laden von '{file_path}': {e}. Nutze Fallback-Prompts.")
            prompts = fallback_prompts
    
    prompts["Benutzerdefiniert"] = "custom"
    return prompts

# --- System-Prompts & Modell-Kategorien ---
PROMPT_FILE = Path(__file__).parent / "prompts.json"
SYSTEM_PROMPTS = load_system_prompts_from_json(PROMPT_FILE)

DEFINED_CATEGORIES = ["Coding", "Chat", "Großer Kontext", "Vision", "Kostenlos", "Open-Source"]


# ---------------------------------------------------------------------------
# Datenmodell (Message)
# ---------------------------------------------------------------------------
# Die Klasse 'Message' wird jetzt direkt aus 'plugin_interface' importiert,
# hier ist die Definition für den Fallback, falls der Import fehlschlägt.
# Die eigentliche, zu verwendende Definition liegt in 'plugin_interface.py'

# ---------------------------------------------------------------------------
# API-Worker
# ---------------------------------------------------------------------------
class ApiWorker(QObject):
    response_ready, chunk_ready = Signal(str), Signal(str)
    error_occurred, finished = Signal(str, int), Signal()

    def __init__(self):
        super().__init__()
        self.stop_requested = False

    def set_request_data(self, api_key: str, model: str, messages: List[Dict], max_tokens: int, stream: bool):
        self.api_key, self.model, self.messages = api_key, model, messages
        self.max_tokens, self.stream = max_tokens, stream
        self.stop_requested = False

    @Slot()
    def make_request(self):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            data = {"model": self.model, "messages": self.messages, "max_tokens": self.max_tokens, "temperature": 0.7, "stream": self.stream}
            
            logger.info(f"Sende an API mit Payload:\n{json.dumps(data, indent=2)}")
            
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=90, stream=self.stream)
            response.raise_for_status()

            if self.stream:
                for line in response.iter_lines():
                    if self.stop_requested: break
                    if line and (line_str := line.decode('utf-8')).startswith("data: "):
                        if (data_str := line_str[6:]) == "[DONE]": break
                        try:
                            chunk = json.loads(data_str)
                            if text := chunk.get("choices", [{}])[0].get("delta", {}).get("content"):
                                self.chunk_ready.emit(text)
                        except json.JSONDecodeError as e: self.error_occurred.emit(f"Stream-Parse-Fehler: {e}", -4); break
            else:
                if text := response.json().get("choices", [{}])[0].get("message", {}).get("content"):
                    self.response_ready.emit(text)
                else: self.error_occurred.emit("Leere Antwort vom Modell", 0)
        
        except requests.exceptions.HTTPError as e: self.error_occurred.emit(f"HTTP-Fehler: {e.response.text}", e.response.status_code)
        except requests.exceptions.RequestException as e: self.error_occurred.emit(f"Netzwerkfehler: {e}", -2)
        except Exception as e: logger.error(f"Worker-Fehler: {traceback.format_exc()}"); self.error_occurred.emit(f"Unerwarteter Fehler: {e}", -3)
        finally:
            if self.stop_requested: self.error_occurred.emit("Anfrage abgebrochen", -1)
            self.finished.emit()

# ---------------------------------------------------------------------------
# SettingsDialog
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.settings = QSettings("OpenRouterGUI", "Settings")
        self._models: List[Dict] = self._fetch_models()
        self._build_ui()
        self._connect_signals()
        self._load_settings()

    def _fetch_models(self) -> List[Dict]:
        try:
            response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
            response.raise_for_status()
            return sorted(response.json().get("data", []), key=lambda x: x.get('popularity', 0), reverse=True)
        except Exception as e:
            QMessageBox.warning(self, "Modell-Liste", f"Modelle konnten nicht geladen werden.\nFehler: {e}")
            return [{"id": "mistralai/mistral-7b-instruct", "name": "Mistral 7B (Fallback)", "context_length": 32768, "top_provider": {"max_completion_tokens": 4096}}]

    def _build_ui(self):
        tabs = QTabWidget(self)
        tabs.addTab(self._create_model_tab(), "Modell & Kontext")
        tabs.addTab(self._create_api_tab(), "API")
        tabs.addTab(self._create_system_prompt_tab(), "System-Prompt")
        
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        
        btn_bar = QHBoxLayout()
        self.save_btn = QPushButton("Speichern")
        self.cancel_btn = QPushButton("Abbrechen")
        btn_bar.addStretch(); btn_bar.addWidget(self.save_btn); btn_bar.addWidget(self.cancel_btn)
        layout.addLayout(btn_bar)

    def _create_api_tab(self) -> QWidget:
        api_tab = QWidget(); layout = QVBoxLayout(api_tab); layout.addWidget(QLabel("OpenRouter API-Key:"))
        key_layout = QHBoxLayout()
        self.key_input = QLineEdit(echoMode=QLineEdit.Password, placeholderText="sk-or-v1-...")
        self.valid_icon = QLabel(alignment=Qt.AlignCenter, fixedWidth=24)
        key_layout.addWidget(self.key_input); key_layout.addWidget(self.valid_icon)
        layout.addLayout(key_layout)
        layout.addWidget(QLabel("Tipp: Key kann als Umgebungsvariable (OPENROUTER_API_KEY) gesetzt werden.")); layout.addStretch()
        return api_tab

    def _create_model_tab(self) -> QWidget:
        model_tab = QWidget(); layout = QVBoxLayout(model_tab)
        layout.addWidget(QLabel("Kategorie:"))
        self.category_combo = QComboBox(); self.category_combo.addItems(["Alle"] + DEFINED_CATEGORIES); layout.addWidget(self.category_combo)
        
        layout.addWidget(QLabel("Modell:"))
        self.model_combo = QComboBox()
        layout.addWidget(self.model_combo)
        
        self.model_info_label = QLabel("Bitte ein Modell auswählen"); layout.addWidget(self.model_info_label)
        layout.addSpacing(10)
        
        layout.addWidget(QLabel("Maximale Antwort-Token:"))
        self.token_box = QLineEdit()
        self.token_box.setValidator(QIntValidator(256, 2147483647, self))
        self.token_box.setEnabled(True)
        layout.addWidget(self.token_box)
        layout.addSpacing(10)
        
        self.context_chk = QCheckBox("Chat-Verlauf als Kontext senden")
        layout.addWidget(self.context_chk)
        
        self.stream_chk = QCheckBox("Streaming-Antworten aktivieren"); layout.addWidget(self.stream_chk); layout.addStretch()
        return model_tab
        
    def _create_system_prompt_tab(self) -> QWidget:
        prompt_tab = QWidget(); layout = QVBoxLayout(prompt_tab)
        layout.addWidget(QLabel("Vordefinierter Systemprompt:"))
        self.prompt_combo = QComboBox()
        self.prompt_combo.addItems(SYSTEM_PROMPTS.keys())
        layout.addWidget(self.prompt_combo)
        layout.addWidget(QLabel("Prompt-Text:")); self.prompt_text_edit = QTextEdit(acceptRichText=False); layout.addWidget(self.prompt_text_edit)
        return prompt_tab

    def _connect_signals(self):
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.key_input.textChanged.connect(self._validate_key)
        self.model_combo.currentIndexChanged.connect(self._on_model_selection_changed)
        self.category_combo.currentTextChanged.connect(self._filter_models_by_category)
        self.prompt_combo.currentTextChanged.connect(self._on_prompt_selection_changed)

    def _get_categories_for_model(self, model_data: Dict) -> List[str]:
        categories = []
        model_id_lower = model_data.get('id', '').lower()
        
        if any(kw in model_id_lower for kw in ["code", "coder"]): categories.append("Coding")
        if any(kw in model_id_lower for kw in ["chat", "instruct"]): categories.append("Chat")
        if "vision" in model_id_lower: categories.append("Vision")
        if any(p in model_id_lower for p in ["huggingface", "meta-llama", "mistralai"]): categories.append("Open-Source")
            
        if model_data.get('context_length', 0) >= 65536: categories.append("Großer Kontext")
        pricing = model_data.get('pricing', {})
        if float(pricing.get('prompt', 1)) == 0.0 and float(pricing.get('completion', 1)) == 0.0: categories.append("Kostenlos")
            
        return list(set(categories))

    def _filter_models_by_category(self, category: str):
        current_model_data = self.model_combo.currentData()
        current_model_id = current_model_data['id'] if current_model_data else None

        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        for model_data in self._models:
            if category == "Alle" or category in self._get_categories_for_model(model_data):
                self.model_combo.addItem(model_data.get('name', model_data['id']), model_data)
        
        self.model_combo.blockSignals(False)

        if current_model_id:
            idx = self.model_combo.findData(next((m for m in self._models if m['id'] == current_model_id), None))
            if idx != -1:
                self.model_combo.setCurrentIndex(idx)
                return
        
        if self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)
        else:
            self._on_model_selection_changed(-1)


    def _on_model_selection_changed(self, index: int):
        if index < 0 or not (model_data := self.model_combo.itemData(index)):
            self.model_info_label.setText("Kein Modell in dieser Kategorie verfügbar")
            self.token_box.clear()
            return
        
        context_len = model_data.get('context_length', 8192)
        top_provider = model_data.get('top_provider', {})
        max_completion = top_provider.get('max_completion_tokens') or (context_len // 2)
        try: max_completion = int(max_completion)
        except (ValueError, TypeError): max_completion = context_len // 2
        
        self.model_info_label.setText(f"Max. Kontext: {context_len} / Empf. max. Antwort: {max_completion}")
        self.token_box.setText(str(max_completion))

    def _on_prompt_selection_changed(self, prompt_name: str):
        prompt_text = SYSTEM_PROMPTS.get(prompt_name)
        self.prompt_text_edit.setReadOnly(prompt_text != "custom")
        if prompt_text != "custom": self.prompt_text_edit.setText(prompt_text)

    def _validate_key(self, text: str):
        is_valid = (text and text.startswith("sk-or-")) or os.getenv("OPENROUTER_API_KEY")
        self.valid_icon.setText("✓" if is_valid else "✗")
        self.valid_icon.setStyleSheet(f"color: {'#2ecc71' if is_valid else '#e74c3c'}; font-size: 14pt; font-weight: bold;")

    def _load_settings(self):
        self.key_input.setText(self.settings.value("api_key", os.getenv("OPENROUTER_API_KEY", "")))
        self.stream_chk.setChecked(self.settings.value("streaming", True, type=bool))
        self.context_chk.setChecked(self.settings.value("send_context", True, type=bool))
        
        saved_category = self.settings.value("model_category", "Alle", type=str)
        self.category_combo.setCurrentText(saved_category)
        
        saved_model_id = self.settings.value("model", "", type=str)
        if saved_model_id:
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i)['id'] == saved_model_id:
                    self.model_combo.setCurrentIndex(i)
                    break
        else:
            if self.model_combo.count() > 0:
                self.model_combo.setCurrentIndex(0)

        default_tokens = int(self.token_box.text()) if self.token_box.text() else 4096
        self.token_box.setText(str(self.settings.value("max_tokens", default_tokens, type=int)))

        saved_prompt = self.settings.value("system_prompt", "", type=str)
        found_name = next((name for name, text in SYSTEM_PROMPTS.items() if text == saved_prompt), "Benutzerdefiniert")
        self.prompt_combo.setCurrentText(found_name)
        if found_name == "Benutzerdefiniert":
            self.prompt_text_edit.setText(saved_prompt)
        else:
            self.prompt_text_edit.setText(SYSTEM_PROMPTS.get(found_name, ""))


    def save_settings(self) -> bool:
        if not ((self.key_input.text() and self.key_input.text().startswith("sk-or-")) or os.getenv("OPENROUTER_API_KEY")):
            QMessageBox.warning(self, "Ungültiger API-Key", "Der API-Key muss mit 'sk-or-' beginnen."); return False
        
        self.settings.setValue("api_key", self.key_input.text())
        if self.model_combo.currentData(): self.settings.setValue("model", self.model_combo.currentData()['id'])
        self.settings.setValue("model_category", self.category_combo.currentText())
        
        try: max_tokens_val = int(self.token_box.text())
        except ValueError: max_tokens_val = 4096
        self.settings.setValue("max_tokens", max_tokens_val)
        
        self.settings.setValue("streaming", self.stream_chk.isChecked())
        self.settings.setValue("send_context", self.context_chk.isChecked())
        self.settings.setValue("system_prompt", self.prompt_text_edit.toPlainText())
        return True

    def accept(self):
        if self.save_settings(): super().accept()
            
    def get_api_key(self) -> str:
        return os.getenv("OPENROUTER_API_KEY") or self.settings.value("api_key", "", type=str)

# ---------------------------------------------------------------------------
# Chat-Widget
# ---------------------------------------------------------------------------
class ChatWidget(QWidget):
    def __init__(self, settings: QSettings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self.messages: List[Message] = []
        self._streaming_msg: Optional[Message] = None
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        chat_panes_layout = QHBoxLayout()
        user_pane_layout = QVBoxLayout()
        user_label = QLabel("<b>Ihre Fragen</b>")
        user_label.setAlignment(Qt.AlignCenter)
        self.user_view = QTextBrowser(openExternalLinks=True, readOnly=True)
        user_pane_layout.addWidget(user_label)
        user_pane_layout.addWidget(self.user_view)
        chat_panes_layout.addLayout(user_pane_layout)
        assistant_pane_layout = QVBoxLayout()
        assistant_label = QLabel("<b>KI-Antworten</b>")
        assistant_label.setAlignment(Qt.AlignCenter)
        self.assistant_view = QTextBrowser(openExternalLinks=True, readOnly=True)
        assistant_pane_layout.addWidget(assistant_label)
        assistant_pane_layout.addWidget(self.assistant_view)
        chat_panes_layout.addLayout(assistant_pane_layout)
        main_layout.addLayout(chat_panes_layout, 1)
        entry_bar = QHBoxLayout()
        self.inp = QLineEdit(placeholderText="Nachricht eingeben …")
        self.btn_send = QPushButton("Senden")
        entry_bar.addWidget(self.inp, 1)
        entry_bar.addWidget(self.btn_send)
        main_layout.addLayout(entry_bar)

    def _refresh(self):
        user_html = ""
        assistant_html = ""

        # CSS-Definitionen von Pygments für ein dunkles Thema (hier 'dracula')
        pygments_css = """
        .codehilite .hll { background-color: #49483e }
        .codehilite .c { color: #908090 } /* Comment */
        .codehilite .err { color: #960050; background-color: #1e0010 } /* Error */
        .codehilite .k { color: #ff6188 } /* Keyword */
        .codehilite .l { color: #ae81ff } /* Literal */
        .codehilite .n { color: #f8f8f2 } /* Name */
        .codehilite .o { color: #ff6188 } /* Operator */
        .codehilite .p { color: #f8f8f2 } /* Punctuation */
        .codehilite .ch { color: #908090 } /* Comment.Hashbang */
        .codehilite .cm { color: #908090 } /* Comment.Multiline */
        .codehilite .cp { color: #908090 } /* Comment.Preproc */
        .codehilite .cpf { color: #908090 } /* Comment.PreprocFile */
        .codehilite .c1 { color: #908090 } /* Comment.Single */
        .codehilite .cs { color: #908090 } /* Comment.Special */
        .codehilite .gd { color: #f92672 } /* Generic.Deleted */
        .codehilite .ge { font-style: italic } /* Generic.Emph */
        .codehilite .gi { color: #a6e22e } /* Generic.Inserted */
        .codehilite .gs { font-weight: bold } /* Generic.Strong */
        .codehilite .gu { color: #75715e } /* Generic.Subheading */
        .codehilite .kc { color: #ff6188 } /* Keyword.Constant */
        .codehilite .kd { color: #ff6188 } /* Keyword.Declaration */
        .codehilite .kn { color: #ff6188 } /* Keyword.Namespace */
        .codehilite .kp { color: #ff6188 } /* Keyword.Pseudo */
        .codehilite .kr { color: #ff6188 } /* Keyword.Reserved */
        .codehilite .kt { color: #66d9ef } /* Keyword.Type */
        .codehilite .ld { color: #e6db74 } /* Literal.Date */
        .codehilite .m { color: #ae81ff } /* Literal.Number */
        .codehilite .s { color: #a6e22e } /* Literal.String */
        .codehilite .na { color: #a6e22e } /* Name.Attribute */
        .codehilite .nb { color: #f8f8f2 } /* Name.Builtin */
        .codehilite .nc { color: #a6e22e; font-weight: bold } /* Name.Class */
        .codehilite .no { color: #66d9ef } /* Name.Constant */
        .codehilite .nd { color: #a6e22e; font-weight: bold } /* Name.Decorator */
        .codehilite .ni { color: #f8f8f2 } /* Name.Entity */
        .codehilite .ne { color: #a6e22e; font-weight: bold } /* Name.Exception */
        .codehilite .nf { color: #a6e22e; font-weight: bold } /* Name.Function */
        .codehilite .nl { color: #f8f8f2 } /* Name.Label */
        .codehilite .nn { color: #f8f8f2 } /* Name.Namespace */
        .codehilite .nx { color: #f8f8f2 } /* Name.Other */
        .codehilite .py { color: #f8f8f2 } /* Name.Property */
        .codehilite .nt { color: #ff6188 } /* Name.Tag */
        .codehilite .nv { color: #f8f8f2 } /* Name.Variable */
        .codehilite .ow { color: #ff6188 } /* Operator.Word */
        .codehilite .w { color: #f8f8f2 } /* Text.Whitespace */
        .codehilite .mb { color: #ae81ff } /* Literal.Number.Bin */
        .codehilite .mf { color: #ae81ff } /* Literal.Number.Float */
        .codehilite .mh { color: #ae81ff } /* Literal.Number.Hex */
        .codehilite .mi { color: #ae81ff } /* Literal.Number.Integer */
        .codehilite .mo { color: #ae81ff } /* Literal.Number.Oct */
        .codehilite .sa { color: #a6e22e } /* Literal.String.Affix */
        .codehilite .sb { color: #a6e22e } /* Literal.String.Backtick */
        .codehilite .sc { color: #a6e22e } /* Literal.String.Char */
        .codehilite .dl { color: #a6e22e } /* Literal.String.Delimiter */
        .codehilite .sd { color: #e6db74 } /* Literal.String.Doc */
        .codehilite .s2 { color: #a6e22e } /* Literal.String.Double */
        .codehilite .se { color: #ae81ff } /* Literal.String.Escape */
        .codehilite .sh { color: #a6e22e } /* Literal.String.Heredoc */
        .codehilite .si { color: #a6e22e } /* Literal.String.Interpol */
        .codehilite .sx { color: #a6e22e } /* Literal.String.Other */
        .codehilite .sr { color: #a6e22e } /* Literal.String.Regex */
        .codehilite .s1 { color: #a6e22e } /* Literal.String.Single */
        .codehilite .ss { color: #a6e22e } /* Literal.String.Symbol */
        .codehilite .vc { color: #f8f8f2 } /* Name.Variable.Class */
        .codehilite .vg { color: #f8f8f2 } /* Name.Variable.Global */
        .codehilite .vi { color: #f8f8f2 } /* Name.Variable.Instance */
        .codehilite .il { color: #ae81ff } /* Literal.Number.Integer.Long */
        """
        
        stylesheet = f"""
        <style>
            body {{ font-family: Segoe UI, sans-serif; line-height: 1.5; }}
            .message {{ margin-bottom: 12px; padding: 5px; border-radius: 4px; background-color: #3e536b; }}
            .header {{ font-size: 8pt; color: #aab; padding-bottom: 4px; }}
            .content {{ white-space: pre-wrap; word-wrap: break-word; }}
            .codehilite {{ background: #2c3e50; border-radius: 4px; padding: 8px; margin: 4px 0; display: block; }}
            {pygments_css}
        </style>
        """

        for m in self.messages:
            content_html = ""
            if getattr(m, 'display_format', 'text') == 'html':
                content_html = m.content
            else:
                content_html = escape(m.content).replace('\n', '<br>')

            message_html = f"""
            <div class="message">
                <div class="header">{m.timestamp.strftime('%H:%M:%S')}</div>
                <div class="content">{content_html}</div>
            </div>"""
            
            if m.role == 'user':
                user_html += message_html
            else:
                assistant_html += message_html
        
        self.user_view.setHtml(stylesheet + user_html)
        self.assistant_view.setHtml(stylesheet + assistant_html)
        self.user_view.verticalScrollBar().setValue(self.user_view.verticalScrollBar().maximum())
        self.assistant_view.verticalScrollBar().setValue(self.assistant_view.verticalScrollBar().maximum())


    def add_message(self, role: str, content: str, streaming: bool = False):
        msg = Message(role, content)
        self.messages.append(msg)
        if streaming and role == "assistant":
            self._streaming_msg = msg
        self._refresh()

    def add_stream_chunk(self, chunk: str):
        if self._streaming_msg:
            self._streaming_msg.content += chunk
            self._refresh()

    def end_stream(self):
        self._streaming_msg = None

    def export_history(self) -> List[Dict]:
        return [m.to_dict() for m in self.messages]

    def import_history(self, data: List[Dict]):
        self.clear()
        try:
            self.messages = [Message(d["role"], d["content"], datetime.fromisoformat(d.get("timestamp"))) for d in data]
            self._refresh()
        except (KeyError, TypeError, ValueError) as e:
            self.clear()
            raise ValueError(f"Ungültiges Chat-Format: {e}")

    def clear(self):
        self.messages.clear()
        self.end_stream()
        self._refresh()


# ---------------------------------------------------------------------------
# Plugin Manager
# ---------------------------------------------------------------------------
class PluginManager:
    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self.plugins: List[ChatPlugin] = []
        self.plugin_dir = Path(__file__).parent / "plugins"

    def load_plugins(self):
        logger.info("Lade Plugins...")
        self.plugin_dir.mkdir(exist_ok=True) 
        
        for file_path in self.plugin_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            module_name = file_path.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Konnte kein Spec für {module_name} erstellen")
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if isinstance(attribute, type) and issubclass(attribute, ChatPlugin) and attribute is not ChatPlugin:
                        plugin_instance = attribute(self.main_window)
                        self.plugins.append(plugin_instance)
                        logger.info(f"Plugin '{plugin_instance.get_name()}' erfolgreich geladen.")

            except Exception as e:
                logger.error(f"Fehler beim Laden des Plugins aus '{file_path.name}': {e}")
                traceback.print_exc()

    def dispatch_user_message(self, message: str) -> bool:
        for plugin in self.plugins:
            try:
                if plugin.on_user_message(message):
                    logger.info(f"Nachricht wurde vom Plugin '{plugin.get_name()}' verarbeitet.")
                    return True 
            except Exception as e:
                logger.error(f"Fehler im Plugin '{plugin.get_name()}' bei on_user_message: {e}")
        return False

    def dispatch_api_response(self, message_object: Message):
        """Leitet das KI-Antwort-Objekt an alle Plugins weiter."""
        for plugin in self.plugins:
            try:
                plugin.on_api_response(message_object)
            except Exception as e:
                logger.error(f"Fehler im Plugin '{plugin.get_name()}' bei on_api_response: {e}")

# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenRouter Chat GUI")
        self.setGeometry(100, 100, 1100, 750)
        self.settings = QSettings("OpenRouterGUI", "Settings")
        self._settings_dialog = None
        self._current_worker: Optional[ApiWorker] = None
        self._api_thread = QThread()
        self._api_thread.start()

        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_plugins()

        self._init_ui()
        self.check_api_key_on_startup()

    def _init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QVBoxLayout(central); self.chat = ChatWidget(self.settings); main_layout.addWidget(self.chat)
        self.chat.btn_send.clicked.connect(self._send); self.chat.inp.returnPressed.connect(self._send)
        self._build_menus(); self._build_statusbar()

    def _build_menus(self):
        mb = self.menuBar(); m_file = mb.addMenu("&Datei"); m_edit = mb.addMenu("&Bearbeiten")
        m_file.addAction(QAction("Neuer Chat", self, shortcut="Ctrl+N", triggered=self.chat.clear))
        m_file.addAction(QAction("Speichern…", self, shortcut="Ctrl+S", triggered=self._save_chat))
        m_file.addAction(QAction("Laden…", self, shortcut="Ctrl+O", triggered=self._load_chat))
        m_file.addSeparator(); m_file.addAction(QAction("Beenden", self, shortcut="Ctrl+Q", triggered=self.close))
        m_edit.addAction(QAction("Einstellungen…", self, shortcut="Ctrl+,", triggered=self._open_settings))
        m_edit.addAction(QAction("Chat löschen", self, triggered=self.chat.clear))
        
    def _build_statusbar(self):
        sb = QStatusBar(); self.setStatusBar(sb); self.lbl_status = QLabel("Bereit"); sb.addWidget(self.lbl_status, 1)
        self.bar_progress = QProgressBar(visible=False, minimum=0, maximum=0); sb.addWidget(self.bar_progress)
        self.btn_stop = QPushButton("Stop", visible=False); self.btn_stop.clicked.connect(self._stop_request); sb.addWidget(self.btn_stop)

    def check_api_key_on_startup(self):
        if not self._get_settings_dialog().get_api_key():
            QMessageBox.information(self, "Willkommen!", "Bitte hinterlege zuerst deinen OpenRouter API-Key.")
            self._open_settings()
            
    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 3

    def _prepare_api_context(self) -> List[Dict]:
        system_prompt = self.settings.value("system_prompt", "", type=str)
        send_context = self.settings.value("send_context", True, type=bool)
        
        final_messages = []

        if send_context:
            logger.info("Chat-Verlauf wird als Kontext gesendet. Kürze bei Bedarf...")
            model_id = self.settings.value("model", "", type=str)
            
            dialog = self._get_settings_dialog()
            model_data = next((m for m in dialog._models if m['id'] == model_id), None)
            context_limit = model_data.get('context_length', 8192) if model_data else 8192
            
            try: max_tokens_val = int(self.settings.value("max_tokens", "4096"))
            except ValueError: max_tokens_val = 4096

            safety_margin = max_tokens_val + self._estimate_tokens(system_prompt) + 500
            available_tokens = context_limit - safety_margin

            current_tokens = 0
            for msg in reversed(self.chat.messages):
                msg_tokens = self._estimate_tokens(msg.content)
                if current_tokens + msg_tokens <= available_tokens:
                    final_messages.insert(0, msg.to_dict())
                    current_tokens += msg_tokens
                else:
                    logger.info(f"Kontext gekürzt. Nachricht '{msg.content[:30]}...' wurde entfernt.")
                    break
            logger.info(f"Verfügbare Tokens für Kontext: {available_tokens}. Genutzte Tokens: {current_tokens}.")
        else:
            logger.info("Chat-Verlauf wird nicht als Kontext gesendet.")
            if self.chat.messages:
                final_messages.append(self.chat.messages[-1].to_dict())

        if system_prompt:
            final_messages.insert(0, {"role": "system", "content": system_prompt})
            
        return final_messages


    def _send(self):
        text = self.chat.inp.text().strip()
        if not text: return

        if self.plugin_manager.dispatch_user_message(text):
            self.chat.inp.clear() 
            return

        api_key = self._get_settings_dialog().get_api_key()
        if not api_key: QMessageBox.warning(self, "API-Key fehlt", "Bitte API-Key festlegen."); self._open_settings(); return
        
        self.chat.add_message("user", text); self.chat.inp.clear()
        
        final_messages = self._prepare_api_context()

        if not final_messages:
            logger.warning("Keine Nachrichten zum Senden vorhanden.")
            if self.chat.messages and not self.chat.messages[-1].content:
                self.chat.messages.pop()
            return

        self.chat.add_message("assistant", "", streaming=True)
        
        worker = ApiWorker()
        worker.moveToThread(self._api_thread)
        worker.response_ready.connect(self._handle_response); worker.chunk_ready.connect(self.chat.add_stream_chunk)
        worker.error_occurred.connect(self._handle_error); worker.finished.connect(self._on_worker_finish); worker.finished.connect(worker.deleteLater)
        self._current_worker = worker
        
        model_id = self.settings.value("model", "mistralai/mistral-7b-instruct", type=str)
        
        try: max_tokens = int(self.settings.value("max_tokens", "4096"))
        except ValueError: max_tokens = 4096
        
        streaming = self.settings.value("streaming", True, type=bool)
        
        worker.set_request_data(api_key, model_id, final_messages, max_tokens, streaming)
        QMetaObject.invokeMethod(worker, "make_request", Qt.QueuedConnection)
        self._set_ui_for_request(True)

    def _stop_request(self):
        if self._current_worker: self.lbl_status.setText("Wird abgebrochen…"); self._current_worker.stop_requested = True
    def _handle_response(self, response: str):
        if self.chat._streaming_msg: self.chat._streaming_msg.content = response; self.chat._refresh()
    
    def _on_worker_finish(self):
        if self.chat._streaming_msg:
            message_obj = self.chat._streaming_msg
            if "[Abgebrochen]" not in message_obj.content and "Fehler (Code:" not in message_obj.content:
                self.plugin_manager.dispatch_api_response(message_obj)
        
        self.chat._refresh() 

        self.chat.end_stream()
        self._set_ui_for_request(False)
        self._current_worker = None
    
    def _handle_error(self, error_msg: str, code: int):
        logger.error(f"Fehler vom Worker (Code: {code}): {error_msg}")
        if code == -1:
            if self.chat._streaming_msg: self.chat._streaming_msg.content += "\n\n[Abgebrochen]"; self.chat._refresh()
            return
        error_display = f"Fehler (Code: {code})";
        if self.chat._streaming_msg:
            self.chat._streaming_msg.content = error_display
        else:
            self.chat.add_message("assistant", error_display)
        self.chat._refresh()
        advice = {401: "\n\nAPI-Key prüfen.", 429: "\n\nRate Limit erreicht.", -2: "\n\nNetzwerkverbindung prüfen."}.get(code, "")
        QMessageBox.critical(self, f"API Fehler (Code: {code})", f"Fehler aufgetreten:\n\n{error_msg}{advice}")

    def _set_ui_for_request(self, is_requesting: bool):
        self.chat.btn_send.setEnabled(not is_requesting); self.chat.inp.setEnabled(not is_requesting); self.menuBar().setEnabled(not is_requesting)
        self.lbl_status.setVisible(not is_requesting); self.bar_progress.setVisible(is_requesting); self.btn_stop.setVisible(is_requesting)
        self.lbl_status.setText("Warte auf Antwort…" if is_requesting else "Bereit")
        if not is_requesting: self.chat.inp.setFocus()

    def _get_settings_dialog(self) -> SettingsDialog:
        if not self._settings_dialog: self._settings_dialog = SettingsDialog(self)
        return self._settings_dialog
    def _open_settings(self): self._get_settings_dialog()._load_settings(); self._get_settings_dialog().exec()
    def _save_chat(self):
        path, _ = QFileDialog.getSaveFileName(self, "Chat speichern", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f: json.dump(self.chat.export_history(), f, indent=2, ensure_ascii=False)
                self.lbl_status.setText(f"Chat in '{os.path.basename(path)}' gespeichert.")
            except Exception as e: QMessageBox.critical(self, "Fehler", f"Speichern fehlgeschlagen: {e}")
    def _load_chat(self):
        if self.chat.messages and QMessageBox.question(self, "Chat laden", "Aktueller Chat wird gelöscht. Fortfahren?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No: return
        path, _ = QFileDialog.getOpenFileName(self, "Chat laden", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f: self.chat.import_history(json.load(f))
                self.lbl_status.setText(f"Chat aus '{os.path.basename(path)}' geladen.")
            except Exception as e: QMessageBox.critical(self, "Fehler", f"Laden fehlgeschlagen: {e}")
    def closeEvent(self, event: QCloseEvent):
        if self._api_thread.isRunning(): self._api_thread.quit(); self._api_thread.wait(1000)
        event.accept()

# ---------------------------------------------------------------------------
# Globales Styling & App-Start
# ---------------------------------------------------------------------------
def set_global_style(app: QApplication):
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QWidget{background-color:#2c3e50;color:#ecf0f1;font-family:'Segoe UI',sans-serif;font-size:10pt;}
        QMainWindow,QDialog{background-color:#2c3e50;}
        QTextBrowser,QTextEdit{background-color:#34495e;border:1px solid #4a627a;border-radius:4px;padding:8px;}
        QLineEdit,QComboBox,QSpinBox{padding:8px;border:1px solid #4a627a;border-radius:4px;background-color:#34495e;}
        QLineEdit:focus,QComboBox:focus,QSpinBox:focus{border:1px solid #3498db;}
        QPushButton{padding:8px 16px;background-color:#3498db;color:white;border:none;border-radius:4px;font-weight:bold;}
        QPushButton:hover{background-color:#2980b9;}QPushButton:disabled{background-color:#566573;color:#95a5a6;}
        QStatusBar{font-size:9pt;border-top:1px solid #4a627a;}
        QMenuBar{background-color:#34495e;border-bottom:1px solid #4a627a;}
        QMenuBar::item:selected{background-color:#3498db;}
        QMenu{background-color:#34495e;border:1px solid #4a627a;}QMenu::item:selected{background-color:#3498db;}
        QComboBox QAbstractItemView{background-color:#34495e;border:1px solid #4a627a;selection-background-color:#3498db;}
        QTabWidget::pane{border:1px solid #4a627a;border-top:none;}
        QTabBar::tab{padding:10px;background-color:#2c3e50;border:1px solid #4a627a;border-bottom:none;border-top-left-radius:4px;border-top-right-radius:4px;}
        QTabBar::tab:selected{background-color:#34495e;border-bottom:1px solid #34495e;}
        QLabel{padding-top:4px;}
        QProgressBar{text-align:center;border-radius:4px;border:1px solid #4a627a;}
        QProgressBar::chunk{background-color:#3498db;border-radius:4px;}
    """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_global_style(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
