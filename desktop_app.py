#!/usr/bin/env python3
"""
OpenRouter Chat GUI - Finale Refaktorierte Desktop-Version
-----------------------------------------------------------
Kombiniert die originale PySide6 UI und alle ihre Funktionen mit
der neuen, modularen Backend-Logik (Config, Logger, API-Client, Models).
"""

import sys
import json
import os
import toml
import logging
import traceback
import httpx
from datetime import datetime
from typing import List, Dict, Optional, Literal
from html import escape
from pathlib import Path

# --- Abhängigkeiten ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QLineEdit, QPushButton, QLabel, QTextEdit, QDialog, QComboBox,
    QMessageBox, QStatusBar, QFileDialog, QProgressBar, QCheckBox, QTabWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QMetaObject, Slot
from PySide6.QtGui import QAction, QCloseEvent

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

# --- 1. Logging-Modul ---
def setup_logger(log_level="INFO", log_file="app.log"):
    logger = logging.getLogger("OpenRouterDesktop")
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

# --- 2. Konfigurations-Modul ---
load_dotenv()

class Config:
    def __init__(self, config_path: str = 'config.toml'):
        self.api_key: str = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key or self.api_key == "dein_api_key_hier":
            raise ValueError("OPENROUTER_API_KEY nicht in .env oder nicht korrekt gesetzt.")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                toml_config: Dict[str, any] = toml.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")
        self.api: Dict[str, any] = toml_config.get('api', {})
        self.prompts: Dict[str, str] = toml_config.get('prompts', {})
        self.gui: Dict[str, any] = toml_config.get('gui', {})
        self.logging: Dict[str, str] = toml_config.get('logging', {})
        self.api_base_url: str = self.api.get('base_url')
        self.default_model: str = self.api.get('default_model')
        self.available_models: List[str] = self.api.get('available_models', [])
        self.system_prompt: str = self.prompts.get('system_prompt')

config = Config()
log = setup_logger(log_level=config.logging.get("level", "INFO"), log_file=config.logging.get("file_path", "app.log"))
log.info("Konfiguration und Logger erfolgreich geladen.")

# --- 3. Exception-Modul ---
class APIClientError(Exception):
    def __init__(self, status_code: int, error_message: str):
        self.message = f"API-Fehler (Code: {status_code}): {error_message}"
        super().__init__(self.message)

# --- 4. Datenmodelle ---
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    display_format: str = "text"
    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp.isoformat()}
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(role=data['role'], content=data['content'], timestamp=datetime.fromisoformat(data['timestamp']))

class ChatHistory:
    def __init__(self, max_length: int = 20):
        self.messages: List[Message] = []
        self.max_length = max_length
    def add_message(self, message: Message):
        self.messages.append(message)
        if len(self.messages) > self.max_length:
            system_message = self.messages[0] if self.messages and self.messages[0].role == "system" else None
            relevant_messages = self.messages[-self.max_length:]
            self.messages = ([system_message] + relevant_messages) if system_message and system_message not in relevant_messages else relevant_messages
    def get_history_for_api(self) -> List[dict]:
        return [msg.model_dump(include={'role', 'content'}) for msg in self.messages]
    def clear(self):
        self.messages.clear()
    def export_history(self) -> List[Dict]:
        return [m.to_dict() for m in self.messages]
    def import_history(self, data: List[Dict]):
        self.messages = [Message.from_dict(d) for d in data]

# --- 5. API-Client-Modul ---
class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        self.stop_requested = False
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def send_message_stream(self, messages: List[Dict], model: str, temperature: float, max_tokens: int):
        endpoint = f"{self.base_url}/chat/completions"
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        log.debug(f"Sende Streaming-Anfrage: {json.dumps(payload, indent=2)}")
        try:
            with httpx.stream("POST", endpoint, json=payload, headers=self.headers, timeout=60.0) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if self.stop_requested: break
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]": break
                        try:
                            chunk = json.loads(data_str)
                            if text := chunk.get("choices", [{}])[0].get("delta", {}).get("content"): yield text
                        except json.JSONDecodeError: continue
        except httpx.HTTPStatusError as e: raise APIClientError(e.response.status_code, e.response.text)
        except Exception as e: raise APIClientError(status_code=500, error_message=str(e))

api_client = OpenRouterClient(api_key=config.api_key, base_url=config.api_base_url)

# --- UI-spezifischer Worker-Thread ---
class ApiWorker(QObject):
    chunk_ready = Signal(str)
    error_occurred = Signal(str)
    finished = Signal()
    def __init__(self, messages: List[Dict], model: str, temperature: float, max_tokens: int):
        super().__init__()
        self.messages, self.model, self.temperature, self.max_tokens = messages, model, temperature, max_tokens
    @Slot()
    def make_request(self):
        try:
            api_client.stop_requested = False
            for chunk in api_client.send_message_stream(self.messages, self.model, self.temperature, self.max_tokens):
                self.chunk_ready.emit(chunk)
        except APIClientError as e: self.error_occurred.emit(e.message)
        except Exception as e: self.error_occurred.emit(f"Unerwarteter Fehler: {e}")
        finally: self.finished.emit()

# --- Hauptanwendung ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.gui.get("title", "OpenChat Desktop v2"))
        self.setGeometry(100, 100, 1000, 800)
        self.chat_history = ChatHistory()
        self._current_worker: Optional[ApiWorker] = None
        self._api_thread = QThread(); self._api_thread.start()
        self._init_ui()
        self._connect_signals()
        log.info("Hauptfenster initialisiert.")

    def _init_ui(self):
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        self.chat_view = QTextBrowser(openExternalLinks=True); self.chat_view.setStyleSheet("font-size: 11pt;")
        self.input_field = QTextEdit(); self.input_field.setPlaceholderText("Nachricht eingeben (Shift+Enter für neue Zeile)..."); self.input_field.setFixedHeight(100)
        send_button = QPushButton("Senden"); send_button.setStyleSheet("font-weight: bold; padding: 8px;")
        input_layout = QHBoxLayout(); input_layout.addWidget(self.input_field, 4); input_layout.addWidget(send_button, 1)
        main_layout.addWidget(self.chat_view); main_layout.addLayout(input_layout)
        self.send_button = send_button # Referenz speichern
        self._build_menus(); self._build_statusbar()

    def _build_menus(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("&Datei")
        file_menu.addAction(QAction("Neuer Chat", self, shortcut="Ctrl+N", triggered=self.clear_chat))
        file_menu.addAction(QAction("Speichern…", self, shortcut="Ctrl+S", triggered=self._save_chat))
        file_menu.addAction(QAction("Laden…", self, shortcut="Ctrl+O", triggered=self._load_chat))
        file_menu.addSeparator()
        file_menu.addAction(QAction("Beenden", self, shortcut="Ctrl+Q", triggered=self.close))
        edit_menu = mb.addMenu("&Bearbeiten")
        edit_menu.addAction(QAction("Einstellungen…", self, shortcut="Ctrl+,", triggered=self._open_settings))

    def _build_statusbar(self):
        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Bereit"); self.status_bar.addWidget(self.status_label, 1)
        self.stop_button = QPushButton("Stop", visible=False); self.stop_button.clicked.connect(self._stop_request)
        self.status_bar.addPermanentWidget(self.stop_button)

    def _connect_signals(self):
        self.send_button.clicked.connect(self._send)
        # Ermöglicht Senden mit Enter, aber nicht mit Shift+Enter
        self.input_field.keyPressEvent = self._input_key_press_event

    def _input_key_press_event(self, event: QCloseEvent):
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._send()
        else:
            QTextEdit.keyPressEvent(self.input_field, event)

    def _open_settings(self):
        # Dialog wird bei Bedarf erstellt
        dialog = SettingsDialog(self)
        dialog.exec()
        log.info("Einstellungen gespeichert.")

    def clear_chat(self):
        self.chat_history.clear()
        self.chat_view.clear()
        log.info("Chat zurückgesetzt.")

    def _save_chat(self):
        path, _ = QFileDialog.getSaveFileName(self, "Chat speichern", "", "JSON (*.json)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.chat_history.export_history(), f, indent=2, ensure_ascii=False)
                log.info(f"Chat erfolgreich in {path} gespeichert.")
            except Exception as e:
                log.error(f"Fehler beim Speichern des Chats: {e}")
                QMessageBox.critical(self, "Fehler", f"Speichern fehlgeschlagen: {e}")
    
    def _load_chat(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chat laden", "", "JSON (*.json)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.chat_history.import_history(data)
                self.render_chat_history()
                log.info(f"Chat erfolgreich aus {path} geladen.")
            except Exception as e:
                log.error(f"Fehler beim Laden des Chats: {e}")
                QMessageBox.critical(self, "Fehler", f"Laden fehlgeschlagen: {e}")

    def _send(self):
        user_text = self.input_field.toPlainText().strip()
        if not user_text: return
        self.set_ui_for_request(True)
        self.chat_history.add_message(Message(role="user", content=user_text))
        self.render_chat_history()
        self.input_field.clear()

        messages = self.chat_history.get_history_for_api()
        worker = ApiWorker(
            messages=messages,
            model=config.default_model, # Vereinfacht, aus config
            temperature=float(config.gui.get("default_temperature", 0.7)),
            max_tokens=int(config.gui.get("max_output_tokens", 1024))
        )
        worker.moveToThread(self._api_thread)
        worker.chunk_ready.connect(self._handle_chunk)
        worker.error_occurred.connect(self._handle_error)
        worker.finished.connect(self._on_worker_finish)
        worker.finished.connect(worker.deleteLater)
        self._current_worker = worker
        self.current_assistant_message = ""
        QMetaObject.invokeMethod(worker, "make_request", Qt.QueuedConnection)

    def _handle_chunk(self, chunk: str):
        self.current_assistant_message += chunk
        self.render_chat_history(streaming_content=self.current_assistant_message)

    def _on_worker_finish(self):
        self.chat_history.add_message(Message(role="assistant", content=self.current_assistant_message.strip()))
        self.render_chat_history()
        self.set_ui_for_request(False)
        self._current_worker = None

    def _handle_error(self, error_msg: str):
        log.error(f"API Fehler: {error_msg}")
        QMessageBox.critical(self, "API Fehler", error_msg)
        self.set_ui_for_request(False)
        # Fehlerhafte "leere" Nachricht entfernen
        if self.chat_history.messages and self.chat_history.messages[-1].role == 'assistant' and not self.chat_history.messages[-1].content:
            self.chat_history.messages.pop()
        self.render_chat_history()

    def _stop_request(self):
        if self._current_worker:
            api_client.stop_requested = True
            self.status_label.setText("Wird abgebrochen...")

    def set_ui_for_request(self, is_requesting: bool):
        self.input_field.setEnabled(not is_requesting)
        self.send_button.setEnabled(not is_requesting)
        self.menuBar().setEnabled(not is_requesting)
        self.stop_button.setVisible(is_requesting)
        self.status_label.setText("Warte auf Antwort..." if is_requesting else "Bereit")
        if not is_requesting: self.input_field.setFocus()

    def render_chat_history(self, streaming_content: Optional[str] = None):
        stylesheet = """
        <style>
            body { font-family: Segoe UI, sans-serif; line-height: 1.5; }
            .message { margin-bottom: 15px; }
            .user { color: #3498db; font-weight: bold; }
            .assistant { color: #e67e22; font-weight: bold; }
            .content { padding-left: 10px; }
        </style>
        """
        html = stylesheet
        for msg in self.chat_history.messages:
            html += f"<div class='message'><span class='{msg.role}'>{msg.role.capitalize()}:</span><div class='content'>{escape(msg.content).replace(chr(10), '<br>')}</div></div>"
        
        if streaming_content is not None:
             html += f"<div class='message'><span class='assistant'>Assistant:</span><div class='content'>{escape(streaming_content).replace(chr(10), '<br>')}...</div></div>"
        
        self.chat_view.setHtml(html)
        self.chat_view.verticalScrollBar().setValue(self.chat_view.verticalScrollBar().maximum())
    
    def closeEvent(self, event: QCloseEvent):
        self._api_thread.quit()
        self._api_thread.wait(500)
        event.accept()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(500)
        
        # Einstellungen werden hier direkt aus `config` und `.env` gelesen
        self.api_key = config.api_key
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._create_general_tab(), "Allgemein")
        layout.addWidget(tabs)
        
        save_button = QPushButton("Schließen") # Speichern passiert jetzt direkt in config.toml
        save_button.clicked.connect(self.accept)
        layout.addWidget(save_button)

    def _create_general_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel(f"<b>API Key:</b><br>...{self.api_key[-4:]} (aus .env geladen)"))
        layout.addWidget(QLabel(f"<b>Default Model:</b><br>{config.default_model}"))
        layout.addWidget(QLabel("Verfügbare Modelle:"))
        
        models_text = QTextEdit(readOnly=True)
        models_text.setText("\n".join(config.available_models))
        layout.addWidget(models_text)
        
        return widget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except (ValueError, FileNotFoundError) as e:
        QMessageBox.critical(None, "Startfehler", f"Ein kritischer Fehler ist beim Start aufgetreten:\n\n{e}\n\nBitte prüfen Sie Ihre .env und config.toml Dateien.")
        sys.exit(1)
