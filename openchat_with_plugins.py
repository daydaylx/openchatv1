#!/usr/bin/env python3
"""
OpenRouter Chat GUI - Finale, stabile und neustrukturierte Version
--------------------------------------------------------------------
**Änderungsprotokoll (Benutzer-Anpassung V17 - Plugin-Menü):**
- Ein dediziertes "Plugins"-Menü wurde zur Menüleiste hinzugefügt.
- Das Menü-Objekt wird in der MainWindow-Instanz gespeichert, damit Plugins darauf zugreifen können.
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
from PySide6.QtGui import QAction, QCloseEvent, QIntValidator, QKeyEvent

try:
    from plugin_interface import ChatPlugin, Message
except ImportError:
    class Message:
        def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None):
            self.role, self.content, self.timestamp, self.display_format = role, content, timestamp or datetime.now(), "text"
        def to_dict(self) -> Dict: return {"role": self.role, "content": self.content, "timestamp": self.timestamp.isoformat()}
    class ChatPlugin:
        def __init__(self, main_window): pass
        def get_name(self) -> str: return "Interface Missing";
        def get_description(self) -> str: return "plugin_interface.py not found"
        def on_user_message(self, message) -> bool: return False
        def on_api_response(self, message_object: Message): pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OpenRouterChat")

def load_system_prompts_from_json(file_path: Path) -> Dict[str, str]:
    fallback_prompts = {"Kein Systemprompt": "","Standard-Assistent": "Du bist ein hilfreicher Assistent."}
    if not file_path.exists():
        logger.warning(f"Prompt-Datei '{file_path}' nicht gefunden."); prompts = fallback_prompts
    else:
        try:
            with open(file_path, "r", encoding="utf-8") as f: prompts = json.load(f)
            logger.info(f"System-Prompts erfolgreich geladen.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Fehler beim Laden von '{file_path}': {e}."); prompts = fallback_prompts
    prompts["Benutzerdefiniert"] = "custom"
    return prompts

PROMPT_FILE = Path(__file__).parent / "prompts.json"
SYSTEM_PROMPTS = load_system_prompts_from_json(PROMPT_FILE)
DEFINED_CATEGORIES = ["Coding", "Chat", "Großer Kontext", "Vision", "Kostenlos", "Open-Source"]

class ApiWorker(QObject):
    response_ready, chunk_ready, error_occurred, finished = Signal(str), Signal(str), Signal(str, int), Signal()
    def __init__(self): super().__init__(); self.stop_requested = False
    def set_request_data(self, api_key: str, model: str, messages: List[Dict], max_tokens: int, stream: bool):
        self.api_key, self.model, self.messages, self.max_tokens, self.stream, self.stop_requested = api_key, model, messages, max_tokens, stream, False
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
                            if text := chunk.get("choices", [{}])[0].get("delta", {}).get("content"): self.chunk_ready.emit(text)
                        except json.JSONDecodeError as e: self.error_occurred.emit(f"Stream-Parse-Fehler: {e}", -4); break
            else:
                if text := response.json().get("choices", [{}])[0].get("message", {}).get("content"): self.response_ready.emit(text)
                else: self.error_occurred.emit("Leere Antwort vom Modell", 0)
        except requests.exceptions.HTTPError as e: self.error_occurred.emit(f"HTTP-Fehler: {e.response.text}", e.response.status_code)
        except requests.exceptions.RequestException as e: self.error_occurred.emit(f"Netzwerkfehler: {e}", -2)
        except Exception as e: logger.error(f"Worker-Fehler: {traceback.format_exc()}"); self.error_occurred.emit(f"Unerwarteter Fehler: {e}", -3)
        finally:
            if self.stop_requested: self.error_occurred.emit("Anfrage abgebrochen", -1)
            self.finished.emit()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Einstellungen"); self.setModal(True); self.setMinimumWidth(600); self.settings = QSettings("OpenRouterGUI", "Settings"); self._models: List[Dict] = self._fetch_models(); self._build_ui(); self._connect_signals(); self._load_settings()
    def _fetch_models(self) -> List[Dict]:
        try:
            response = requests.get("https://openrouter.ai/api/v1/models", timeout=10); response.raise_for_status()
            return sorted(response.json().get("data", []), key=lambda x: x.get('popularity', 0), reverse=True)
        except Exception as e:
            QMessageBox.warning(self, "Modell-Liste", f"Modelle konnten nicht geladen werden.\nFehler: {e}"); return [{"id": "mistralai/mistral-7b-instruct", "name": "Mistral 7B (Fallback)", "context_length": 32768, "top_provider": {"max_completion_tokens": 4096}}]
    def _build_ui(self):
        tabs = QTabWidget(self); tabs.addTab(self._create_model_tab(), "Modell & Kontext"); tabs.addTab(self._create_api_tab(), "API"); tabs.addTab(self._create_system_prompt_tab(), "System-Prompt")
        layout = QVBoxLayout(self); layout.addWidget(tabs); btn_bar = QHBoxLayout(); self.save_btn = QPushButton("Speichern"); self.cancel_btn = QPushButton("Abbrechen")
        btn_bar.addStretch(); btn_bar.addWidget(self.save_btn); btn_bar.addWidget(self.cancel_btn); layout.addLayout(btn_bar)
    def _create_api_tab(self) -> QWidget:
        api_tab = QWidget(); layout = QVBoxLayout(api_tab); layout.addWidget(QLabel("OpenRouter API-Key:")); key_layout = QHBoxLayout()
        self.key_input = QLineEdit(echoMode=QLineEdit.Password, placeholderText="sk-or-v1-..."); self.valid_icon = QLabel(alignment=Qt.AlignCenter, fixedWidth=24)
        key_layout.addWidget(self.key_input); key_layout.addWidget(self.valid_icon); layout.addLayout(key_layout)
        layout.addWidget(QLabel("Tipp: Key kann als Umgebungsvariable (OPENROUTER_API_KEY) gesetzt werden.")); layout.addStretch(); return api_tab
    def _create_model_tab(self) -> QWidget:
        model_tab = QWidget(); layout = QVBoxLayout(model_tab); layout.addWidget(QLabel("Kategorie:")); self.category_combo = QComboBox(); self.category_combo.addItems(["Alle"] + DEFINED_CATEGORIES); layout.addWidget(self.category_combo)
        layout.addWidget(QLabel("Modell:")); self.model_combo = QComboBox(); layout.addWidget(self.model_combo); self.model_info_label = QLabel("Bitte ein Modell auswählen"); layout.addWidget(self.model_info_label)
        layout.addSpacing(10); layout.addWidget(QLabel("Maximale Antwort-Token:")); self.token_box = QLineEdit(); self.token_box.setValidator(QIntValidator(256, 2147483647, self)); layout.addWidget(self.token_box)
        layout.addSpacing(10); self.context_chk = QCheckBox("Chat-Verlauf als Kontext senden"); layout.addWidget(self.context_chk); self.stream_chk = QCheckBox("Streaming-Antworten aktivieren"); layout.addWidget(self.stream_chk); layout.addStretch(); return model_tab
    def _create_system_prompt_tab(self) -> QWidget:
        prompt_tab = QWidget(); layout = QVBoxLayout(prompt_tab); style_layout = QHBoxLayout(); style_layout.addWidget(QLabel("Antwort-Stil:")); self.style_combo = QComboBox()
        self.style_combo.addItems(["Standard", "Kurz & Prägnant", "Ausführlich & Erklärend"]); style_layout.addWidget(self.style_combo); layout.addLayout(style_layout)
        layout.addWidget(QLabel("Vordefinierter Systemprompt:")); self.prompt_combo = QComboBox(); self.prompt_combo.addItems(SYSTEM_PROMPTS.keys()); layout.addWidget(self.prompt_combo)
        layout.addWidget(QLabel("Prompt-Text:")); self.prompt_text_edit = QTextEdit(acceptRichText=False); layout.addWidget(self.prompt_text_edit); return prompt_tab
    def _connect_signals(self):
        self.save_btn.clicked.connect(self.accept); self.cancel_btn.clicked.connect(self.reject); self.key_input.textChanged.connect(self._validate_key)
        self.model_combo.currentIndexChanged.connect(self._on_model_selection_changed); self.category_combo.currentTextChanged.connect(self._filter_models_by_category)
        self.prompt_combo.currentTextChanged.connect(self._on_prompt_selection_changed)
    def _get_categories_for_model(self, model_data: Dict) -> List[str]:
        categories, model_id_lower = [], model_data.get('id', '').lower()
        if any(kw in model_id_lower for kw in ["code", "coder"]): categories.append("Coding");
        if any(kw in model_id_lower for kw in ["chat", "instruct"]): categories.append("Chat")
        if "vision" in model_id_lower: categories.append("Vision")
        if any(p in model_id_lower for p in ["huggingface", "meta-llama", "mistralai"]): categories.append("Open-Source")
        if model_data.get('context_length', 0) >= 65536: categories.append("Großer Kontext")
        pricing = model_data.get('pricing', {});
        if float(pricing.get('prompt', 1)) == 0.0 and float(pricing.get('completion', 1)) == 0.0: categories.append("Kostenlos")
        return list(set(categories))
    def _filter_models_by_category(self, category: str):
        current_model_data, current_model_id = self.model_combo.currentData(), self.model_combo.currentData()['id'] if self.model_combo.currentData() else None
        self.model_combo.blockSignals(True); self.model_combo.clear()
        for model_data in self._models:
            if category == "Alle" or category in self._get_categories_for_model(model_data): self.model_combo.addItem(model_data.get('name', model_data['id']), model_data)
        self.model_combo.blockSignals(False)
        if current_model_id and (idx := self.model_combo.findData(next((m for m in self._models if m['id'] == current_model_id), None))) != -1: self.model_combo.setCurrentIndex(idx); return
        if self.model_combo.count() > 0: self.model_combo.setCurrentIndex(0)
        else: self._on_model_selection_changed(-1)
    def _on_model_selection_changed(self, index: int):
        if index < 0 or not (model_data := self.model_combo.itemData(index)):
            self.model_info_label.setText("Kein Modell verfügbar"); self.token_box.clear(); return
        context_len, top_provider = model_data.get('context_length', 8192), model_data.get('top_provider', {})
        max_completion = top_provider.get('max_completion_tokens') or (context_len // 2)
        try: max_completion = int(max_completion)
        except (ValueError, TypeError): max_completion = context_len // 2
        self.model_info_label.setText(f"Max. Kontext: {context_len} / Empf. max. Antwort: {max_completion}"); self.token_box.setText(str(max_completion))
    def _on_prompt_selection_changed(self, prompt_name: str):
        prompt_text = SYSTEM_PROMPTS.get(prompt_name)
        self.prompt_text_edit.setReadOnly(prompt_text != "custom")
        if prompt_text != "custom": self.prompt_text_edit.setText(prompt_text)
    def _validate_key(self, text: str):
        is_valid = (text and text.startswith("sk-or-")) or os.getenv("OPENROUTER_API_KEY")
        self.valid_icon.setText("✓" if is_valid else "✗"); self.valid_icon.setStyleSheet(f"color: {'#2ecc71' if is_valid else '#e74c3c'}; font-size: 14pt; font-weight: bold;")
    def _load_settings(self):
        self.key_input.setText(self.settings.value("api_key", os.getenv("OPENROUTER_API_KEY", ""))); self.stream_chk.setChecked(self.settings.value("streaming", True, type=bool)); self.context_chk.setChecked(self.settings.value("send_context", True, type=bool))
        self.category_combo.setCurrentText(self.settings.value("model_category", "Alle", type=str))
        if (saved_model_id := self.settings.value("model", "", type=str)):
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i)['id'] == saved_model_id: self.model_combo.setCurrentIndex(i); break
        elif self.model_combo.count() > 0: self.model_combo.setCurrentIndex(0)
        default_tokens = int(self.token_box.text()) if self.token_box.text() else 4096; self.token_box.setText(str(self.settings.value("max_tokens", default_tokens, type=int)))
        saved_prompt = self.settings.value("system_prompt", "", type=str); found_name = next((name for name, text in SYSTEM_PROMPTS.items() if text == saved_prompt), "Benutzerdefiniert")
        self.prompt_combo.setCurrentText(found_name)
        if found_name == "Benutzerdefiniert": self.prompt_text_edit.setText(saved_prompt)
        else: self.prompt_text_edit.setText(SYSTEM_PROMPTS.get(found_name, ""))
        self.style_combo.setCurrentText(self.settings.value("response_style", "Standard", type=str))
    def save_settings(self) -> bool:
        if not ((self.key_input.text() and self.key_input.text().startswith("sk-or-")) or os.getenv("OPENROUTER_API_KEY")):
            QMessageBox.warning(self, "Ungültiger API-Key", "Der API-Key muss mit 'sk-or-' beginnen."); return False
        self.settings.setValue("api_key", self.key_input.text())
        if self.model_combo.currentData(): self.settings.setValue("model", self.model_combo.currentData()['id'])
        self.settings.setValue("model_category", self.category_combo.currentText())
        try: max_tokens_val = int(self.token_box.text())
        except ValueError: max_tokens_val = 4096
        self.settings.setValue("max_tokens", max_tokens_val); self.settings.setValue("streaming", self.stream_chk.isChecked()); self.settings.setValue("send_context", self.context_chk.isChecked())
        self.settings.setValue("system_prompt", self.prompt_text_edit.toPlainText()); self.settings.setValue("response_style", self.style_combo.currentText()); return True
    def accept(self):
        if self.save_settings(): super().accept()
    def get_api_key(self) -> str: return os.getenv("OPENROUTER_API_KEY") or self.settings.value("api_key", "", type=str)

class ChatInputWidget(QWidget):
    send_triggered = Signal()
    def __init__(self, parent=None):
        super().__init__(parent); layout = QHBoxLayout(self); layout.setContentsMargins(0,0,0,0); self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Nachricht eingeben (Shift+Enter für neue Zeile)..."); self.text_input.setFixedHeight(80); self.text_input.keyPressEvent = self.input_key_press_event
        self.btn_send = QPushButton("Senden"); layout.addWidget(self.text_input); layout.addWidget(self.btn_send); self.btn_send.clicked.connect(self.send_triggered.emit)
    def input_key_press_event(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier): self.send_triggered.emit()
        else: QTextEdit.keyPressEvent(self.text_input, event)
    def getText(self) -> str: return self.text_input.toPlainText()
    def clear(self): self.text_input.clear()
    def setEnabled(self, enabled: bool): self.text_input.setEnabled(enabled); self.btn_send.setEnabled(enabled)
    def setFocus(self): self.text_input.setFocus()

class ChatWidget(QWidget):
    def __init__(self, settings: QSettings, parent: Optional[QWidget] = None):
        super().__init__(parent); self.settings = settings; self.messages: List[Message] = []; self._streaming_msg: Optional[Message] = None; self._build_ui()
    def _build_ui(self):
        self.main_layout = QVBoxLayout(self); self.main_layout.setContentsMargins(5, 5, 5, 5); self.chat_view = QTextBrowser(openExternalLinks=True, readOnly=True); self.assistant_view = self.chat_view; self.main_layout.addWidget(self.chat_view, 1)
        self.input_widget = ChatInputWidget(); token_layout = QHBoxLayout(); token_layout.addStretch(); self.token_label = QLabel("Tokens: 0"); token_layout.addWidget(self.token_label)
        self.main_layout.addWidget(self.input_widget); self.main_layout.addLayout(token_layout)
    def _refresh(self):
        pygments_css = """.codehilite .hll { background-color: #49483e } .codehilite .c { color: #908090 } .codehilite .err { color: #960050; background-color: #1e0010 } .codehilite .k { color: #ff6188 } .codehilite .l { color: #ae81ff } .codehilite .n { color: #f8f8f2 } .codehilite .o { color: #ff6188 } .codehilite .p { color: #f8f8f2 } .codehilite .ch { color: #908090 } .codehilite .cm { color: #908090 } .codehilite .cp { color: #908090 } .codehilite .cpf { color: #908090 } .codehilite .c1 { color: #908090 } .codehilite .cs { color: #908090 } .codehilite .gd { color: #f92672 } .codehilite .ge { font-style: italic } .codehilite .gi { color: #a6e22e } .codehilite .gs { font-weight: bold } .codehilite .gu { color: #75715e } .codehilite .kc { color: #ff6188 } .codehilite .kd { color: #ff6188 } .codehilite .kn { color: #ff6188 } .codehilite .kp { color: #ff6188 } .codehilite .kr { color: #ff6188 } .codehilite .kt { color: #66d9ef } .codehilite .ld { color: #e6db74 } .codehilite .m { color: #ae81ff } .codehilite .s { color: #a6e22e } .codehilite .na { color: #a6e22e } .codehilite .nb { color: #f8f8f2 } .codehilite .nc { color: #a6e22e; font-weight: bold } .codehilite .no { color: #66d9ef } .codehilite .nd { color: #a6e22e; font-weight: bold } .codehilite .ni { color: #f8f8f2 } .codehilite .ne { color: #a6e22e; font-weight: bold } .codehilite .nf { color: #a6e22e; font-weight: bold } .codehilite .nl { color: #f8f8f2 } .codehilite .nn { color: #f8f8f2 } .codehilite .nx { color: #f8f8f2 } .codehilite .py { color: #f8f8f2 } .codehilite .nt { color: #ff6188 } .codehilite .nv { color: #f8f8f2 } .codehilite .ow { color: #ff6188 } .codehilite .w { color: #f8f8f2 } .codehilite .mb { color: #ae81ff } .codehilite .mf { color: #ae81ff } .codehilite .mh { color: #ae81ff } .codehilite .mi { color: #ae81ff } .codehilite .mo { color: #ae81ff } .codehilite .sa { color: #a6e22e } .codehilite .sb { color: #a6e22e } .codehilite .sc { color: #a6e22e } .codehilite .dl { color: #a6e22e } .codehilite .sd { color: #e6db74 } .codehilite .s2 { color: #a6e22e } .codehilite .se { color: #ae81ff } .codehilite .sh { color: #a6e22e } .codehilite .si { color: #a6e22e } .codehilite .sx { color: #a6e22e } .codehilite .sr { color: #a6e22e } .codehilite .s1 { color: #a6e22e } .codehilite .ss { color: #a6e22e } .codehilite .vc { color: #f8f8f2 } .codehilite .vg { color: #f8f8f2 } .codehilite .vi { color: #f8f8f2 } .codehilite .il { color: #ae81ff }"""
        stylesheet = f"""<style>body {{ font-family: Segoe UI, sans-serif; line-height: 1.5; }} .message-wrapper {{ margin-bottom: 15px; clear: both; }} .message {{ display: inline-block; max-width: 85%; padding: 8px 12px; border-radius: 12px; }} .message.user {{ float: right; background-color: #3498db; color: white; }} .message.assistant {{ float: left; background-color: #3e536b; }} .message.system {{ clear: both; float: none; display: block; width: 95%; margin: 10px auto; background-color: #2c50; border: 1px dashed #7f8c8d; text-align: center; font-style: italic; }} .header {{ font-size: 8pt; color: #bdc3c7; padding-bottom: 4px; }} .message.user .header {{ text-align: right; }} .content {{ white-space: pre-wrap; word-wrap: break-word; }} .codehilite {{ background: #2c3e50; border-radius: 4px; padding: 8px; margin: 4px 0; display: block; }} {pygments_css}</style>"""
        full_html = "".join([f"""<div class="message-wrapper {m.role}"><div class="message {m.role}"><div class="header">{m.timestamp.strftime('%H:%M:%S')}</div><div class="content">{m.content if getattr(m, 'display_format', 'text') == 'html' else escape(m.content).replace('\n', '<br>')}</div></div></div>""" for m in self.messages])
        self.chat_view.setHtml(stylesheet + full_html); self.chat_view.verticalScrollBar().setValue(self.chat_view.verticalScrollBar().maximum())
    def add_message(self, role: str, content: str, streaming: bool = False):
        msg = Message(role, content); self.messages.append(msg)
        if streaming and role == "assistant": self._streaming_msg = msg
        self._refresh()
    def add_stream_chunk(self, chunk: str):
        if self._streaming_msg: self._streaming_msg.content += chunk; self._refresh()
    def end_stream(self): self._streaming_msg = None
    def export_history(self) -> List[Dict]: return [m.to_dict() for m in self.messages]
    def import_history(self, data: List[Dict]):
        self.clear();
        try: self.messages = [Message(d["role"], d["content"], datetime.fromisoformat(d.get("timestamp"))) for d in data]; self._refresh()
        except (KeyError, TypeError, ValueError) as e: self.clear(); raise ValueError(f"Ungültiges Chat-Format: {e}")
    def clear(self): self.messages.clear(); self.end_stream(); self._refresh()

class PluginManager:
    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window; self.plugins: List[ChatPlugin] = []; self.plugin_dir = Path(__file__).parent / "plugins"
    def load_plugins(self):
        logger.info("Lade Plugins..."); self.plugin_dir.mkdir(exist_ok=True)
        for file_path in self.plugin_dir.glob("*.py"):
            if file_path.name.startswith("_"): continue
            module_name = file_path.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None: raise ImportError(f"Konnte kein Spec für {module_name} erstellen")
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if isinstance(attribute, type) and issubclass(attribute, ChatPlugin) and attribute is not ChatPlugin:
                        plugin_instance = attribute(self.main_window); self.plugins.append(plugin_instance); logger.info(f"Plugin '{plugin_instance.get_name()}' geladen.")
            except Exception as e: logger.error(f"Fehler beim Laden von '{file_path.name}': {e}"); traceback.print_exc()
    def dispatch_user_message(self, message: str) -> bool:
        for plugin in self.plugins:
            try:
                if plugin.on_user_message(message): logger.info(f"Nachricht verarbeitet von '{plugin.get_name()}'."); return True
            except Exception as e: logger.error(f"Fehler in '{plugin.get_name()}': {e}")
        return False
    def dispatch_api_response(self, message_object: Message):
        for plugin in self.plugins:
            try: plugin.on_api_response(message_object)
            except Exception as e: logger.error(f"Fehler in '{plugin.get_name()}': {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("OpenRouter Chat GUI"); self.setGeometry(100, 100, 900, 750)
        self.settings = QSettings("OpenRouterGUI", "Settings"); self._settings_dialog = None; self._current_worker: Optional[ApiWorker] = None
        self._api_thread = QThread(); self._api_thread.start()
        self.plugin_manager = PluginManager(self)
        self._init_ui() # UI vor den Plugins initialisieren
        self.plugin_manager.load_plugins()
        self.check_api_key_on_startup()
    def _init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QVBoxLayout(central); self.chat = ChatWidget(self.settings)
        self.chat.main_layout = main_layout
        main_layout.addWidget(self.chat)
        self.chat.input_widget.send_triggered.connect(self._send)
        self.chat.input_widget.text_input.textChanged.connect(self._update_token_count)
        self._build_menus(); self._build_statusbar()
        
    def _build_menus(self):
        mb = self.menuBar()
        m_file = mb.addMenu("&Datei")
        m_edit = mb.addMenu("&Bearbeiten")
        # --- START: NEUER CODE ---
        self.m_plugins = mb.addMenu("&Plugins")
        # --- ENDE: NEUER CODE ---
        
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
        if not self._get_settings_dialog().get_api_key(): QMessageBox.information(self, "Willkommen!", "Bitte hinterlege zuerst deinen OpenRouter API-Key."); self._open_settings()
    def _estimate_tokens(self, text: str) -> int: return len(text) // 3
    def _update_token_count(self):
        text = self.chat.input_widget.getText(); token_count = self._estimate_tokens(text); self.chat.token_label.setText(f"Tokens: {token_count}")
    def _prepare_api_context(self) -> List[Dict]:
        system_prompt_base = self.settings.value("system_prompt", "", type=str); response_style = self.settings.value("response_style", "Standard", type=str)
        style_instructions = {"Kurz & Prägnant": "Antworte immer so kurz und prägnant wie möglich.", "Ausführlich & Erklärend": "Gib immer ausführliche Antworten und erkläre deine Gedankengänge Schritt für Schritt."}
        style_instruction = style_instructions.get(response_style, ""); system_prompt = f"{system_prompt_base}\n{style_instruction}".strip()
        send_context = self.settings.value("send_context", True, type=bool); final_messages = []
        if send_context:
            logger.info("Chat-Verlauf wird als Kontext gesendet..."); model_id = self.settings.value("model", "", type=str)
            dialog = self._get_settings_dialog(); model_data = next((m for m in dialog._models if m['id'] == model_id), None)
            context_limit = model_data.get('context_length', 8192) if model_data else 8192
            try: max_tokens_val = int(self.settings.value("max_tokens", "4096"))
            except ValueError: max_tokens_val = 4096
            safety_margin = max_tokens_val + self._estimate_tokens(system_prompt) + 500; available_tokens = context_limit - safety_margin; current_tokens = 0
            for msg in reversed(self.chat.messages):
                msg_tokens = self._estimate_tokens(msg.content)
                if current_tokens + msg_tokens <= available_tokens: final_messages.insert(0, msg.to_dict()); current_tokens += msg_tokens
                else: logger.info(f"Kontext gekürzt."); break
        else:
            if self.chat.messages: final_messages.append(self.chat.messages[-1].to_dict())
        if system_prompt: final_messages.insert(0, {"role": "system", "content": system_prompt})
        return final_messages
    def _send(self):
        text = self.chat.input_widget.getText().strip()
        if not text: return
        if self.plugin_manager.dispatch_user_message(text): self.chat.input_widget.clear(); return
        api_key = self._get_settings_dialog().get_api_key()
        if not api_key: QMessageBox.warning(self, "API-Key fehlt", "Bitte API-Key festlegen."); self._open_settings(); return
        self.chat.add_message("user", text); self.chat.input_widget.clear()
        final_messages = self._prepare_api_context()
        if not final_messages:
            if self.chat.messages and not self.chat.messages[-1].content: self.chat.messages.pop()
            return
        self.chat.add_message("assistant", "", streaming=True); worker = ApiWorker(); worker.moveToThread(self._api_thread)
        worker.response_ready.connect(self._handle_response); worker.chunk_ready.connect(self.chat.add_stream_chunk)
        worker.error_occurred.connect(self._handle_error); worker.finished.connect(self._on_worker_finish); worker.finished.connect(worker.deleteLater)
        self._current_worker = worker; model_id = self.settings.value("model", "mistralai/mistral-7b-instruct", type=str)
        try: max_tokens = int(self.settings.value("max_tokens", "4096"))
        except ValueError: max_tokens = 4096
        streaming = self.settings.value("streaming", True, type=bool)
        worker.set_request_data(api_key, model_id, final_messages, max_tokens, streaming)
        QMetaObject.invokeMethod(worker, "make_request", Qt.QueuedConnection); self._set_ui_for_request(True)
    def _stop_request(self):
        if self._current_worker: self.lbl_status.setText("Wird abgebrochen…"); self._current_worker.stop_requested = True
    def _handle_response(self, response: str):
        if self.chat._streaming_msg: self.chat._streaming_msg.content = response; self.chat._refresh()
    def _on_worker_finish(self):
        if self.chat._streaming_msg and "[Abgebrochen]" not in self.chat._streaming_msg.content and "Fehler (Code:" not in self.chat._streaming_msg.content:
            self.plugin_manager.dispatch_api_response(self.chat._streaming_msg)
        self.chat._refresh(); self.chat.end_stream(); self._set_ui_for_request(False); self._current_worker = None
    def _handle_error(self, error_msg: str, code: int):
        logger.error(f"Worker-Fehler (Code: {code}): {error_msg}")
        if code == -1:
            if self.chat._streaming_msg: self.chat._streaming_msg.content += "\n\n[Abgebrochen]"; self.chat._refresh()
            return
        error_display = f"Fehler (Code: {code})"
        if self.chat._streaming_msg: self.chat._streaming_msg.content = error_display
        else: self.chat.add_message("assistant", error_display)
        self.chat._refresh(); advice = {401: "\n\nAPI-Key prüfen.", 429: "\n\nRate Limit erreicht.", -2: "\n\nNetzwerkverbindung prüfen."}.get(code, "")
        QMessageBox.critical(self, f"API Fehler (Code: {code})", f"Fehler aufgetreten:\n\n{error_msg}{advice}")
    def _set_ui_for_request(self, is_requesting: bool):
        self.chat.input_widget.setEnabled(not is_requesting); self.menuBar().setEnabled(not is_requesting)
        self.lbl_status.setVisible(not is_requesting); self.bar_progress.setVisible(is_requesting); self.btn_stop.setVisible(is_requesting)
        self.lbl_status.setText("Warte auf Antwort…" if is_requesting else "Bereit")
        if not is_requesting: self.chat.input_widget.setFocus()
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
                self.lbl_status.setText(f"Chat aus '{os.path.basename(path)}' geladen."); self._request_summary()
            except Exception as e: QMessageBox.critical(self, "Fehler", f"Laden fehlgeschlagen: {e}")
    def _request_summary(self):
        if len(self.chat.messages) < 4: return
        self.lbl_status.setText("Erstelle Zusammenfassung...")
        sample_messages = self.chat.messages[:3] + self.chat.messages[-3:]
        history_text = "\n".join([f"{m.role}: {m.content}" for m in sample_messages])
        summary_prompt = f"Fasse die folgende Konversation in 3-4 prägnanten Stichpunkten zusammen. Antworte nur mit den Stichpunkten.\n\n---\n\n{history_text}"
        worker = ApiWorker(); worker.moveToThread(self._api_thread); worker.response_ready.connect(self._handle_summary_response)
        worker.error_occurred.connect(lambda err, code: logger.error(f"Fehler bei Zusammenfassung: {err}"))
        worker.finished.connect(worker.deleteLater); worker.finished.connect(lambda: self.lbl_status.setText("Bereit"))
        api_key = self.get_api_key(); model_id = "openai/gpt-3.5-turbo"
        worker.set_request_data(api_key, model_id, [{"role": "user", "content": summary_prompt}], 512, stream=False)
        QMetaObject.invokeMethod(worker, "make_request", Qt.QueuedConnection)
    def _handle_summary_response(self, summary: str): QMessageBox.information(self, "Zusammenfassung der Konversation", summary)
    def closeEvent(self, event: QCloseEvent):
        if self._api_thread.isRunning(): self._api_thread.quit(); self._api_thread.wait(1000)
        event.accept()

def set_global_style(app: QApplication):
    app.setStyle("Fusion")
    app.setStyleSheet("""QWidget{background-color:#2c3e50;color:#ecf0f1;font-family:'Segoe UI',sans-serif;font-size:10pt;} QMainWindow,QDialog{background-color:#2c3e50;} QTextBrowser,QTextEdit{background-color:#34495e;border:1px solid #4a627a;border-radius:4px;padding:8px;} QLineEdit,QComboBox,QSpinBox{padding:8px;border:1px solid #4a627a;border-radius:4px;background-color:#34495e;} QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QTextEdit:focus{border:1px solid #3498db;} QPushButton{padding:8px 16px;background-color:#3498db;color:white;border:none;border-radius:4px;font-weight:bold;} QPushButton:hover{background-color:#5dade2;} QPushButton:disabled{background-color:#566573;color:#95a5a6;} QStatusBar{font-size:9pt;border-top:1px solid #4a627a;} QMenuBar{background-color:#34495e;border-bottom:1px solid #4a627a;} QMenuBar::item:selected{background-color:#3498db;} QMenu{background-color:#34495e;border:1px solid #4a627a;}QMenu::item:selected{background-color:#3498db;} QComboBox QAbstractItemView{background-color:#34495e;border:1px solid #4a627a;selection-background-color:#3498db;} QTabWidget::pane{border:1px solid #4a627a;border-top:none;} QTabBar::tab{padding:10px;background-color:#2c3e50;border:1px solid #4a627a;border-bottom:none;border-top-left-radius:4px;border-top-right-radius:4px;} QTabBar::tab:selected{background-color:#34495e;border-bottom:1px solid #34495e;} QLabel{padding-top:4px;} QProgressBar{text-align:center;border-radius:4px;border:1px solid #4a627a;} QProgressBar::chunk{background-color:#3498db;border-radius:4px;}""")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_global_style(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
