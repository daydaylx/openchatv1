import gradio as gr

# Importiere alle unsere modularen Komponenten
from src.config_loader import config
from src.logger import log, setup_logger
from src.models import Message, ChatHistory
from src.api_client import api_client
from src.exceptions import APIClientError
from plugins.core.plugin_manager import plugin_manager

# Konfiguriere den Logger mit den Werten aus unserer config.toml
setup_logger(
    log_level=config.logging.get("level", "INFO"), 
    log_file=config.logging.get("file_path", "app.log")
)

# Initialisiere die zentrale Chathistorie
chat_history = ChatHistory()

def handle_chat_interaction(user_input: str, temperature: float, selected_model: str, history: list) -> tuple:
    """
    Die Kernfunktion, die die Benutzeranfrage verarbeitet und eine Antwort generiert.
    """
    try:
        # 1. Benutzernachricht zur Historie hinzufügen
        chat_history.add_message(Message(role="user", content=user_input))

        # 2. API-Client aufrufen, um eine Antwort zu erhalten
        assistant_response = api_client.send_message(
            messages=chat_history.get_history_for_api(),
            model=selected_model,
            temperature=temperature,
            max_tokens=config.gui.get("max_output_tokens", 1024)
        )

        if not assistant_response:
            assistant_response = "Entschuldigung, ich konnte keine Antwort generieren."

        # 3. Antwort des Assistenten zur Historie hinzufügen
        chat_history.add_message(Message(role="assistant", content=assistant_response))

        # 4. Gradio-Chat-Darstellung aktualisieren
        # Gradio erwartet eine Liste von Tupeln: [(user_msg, assistant_msg), ...]
        updated_history = []
        # Wir durchlaufen die Nachrichten paarweise
        user_msgs = [msg for msg in chat_history.messages if msg.role == 'user']
        assistant_msgs = [msg for msg in chat_history.messages if msg.role == 'assistant']
        for u_msg, a_msg in zip(user_msgs, assistant_msgs):
            updated_history.append((u_msg.content, a_msg.content))
        
        return updated_history, "" # Leerer String für die Textbox

    except APIClientError as e:
        log.error(f"Ein API-Fehler ist aufgetreten: {e.message}")
        error_message = f"**Fehler bei der API-Anfrage:**\n{e.message}"
        history.append((user_input, error_message))
        return history, ""
    except Exception as e:
        log.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}", exc_info=True)
        error_message = f"**Ein unerwarteter Fehler ist aufgetreten:**\n{str(e)}"
        history.append((user_input, error_message))
        return history, ""

def clear_chat() -> tuple:
    """Löscht die Chathistorie."""
    chat_history.clear()
    # Füge den System-Prompt wieder hinzu, falls vorhanden
    if config.system_prompt:
        chat_history.add_message(Message(role="system", content=config.system_prompt))
    log.info("Chat wurde zurückgesetzt.")
    return [], ""

# Initialisiere die Historie mit dem System-Prompt aus der Konfiguration
if config.system_prompt:
    chat_history.add_message(Message(role="system", content=config.system_prompt))

# === Aufbau der Gradio-Benutzeroberfläche ===
with gr.Blocks(theme=config.gui.get("theme", "default"), title=config.gui.get("title", "OpenChat")) as app:
    gr.Markdown(f"# {config.gui.get('title', 'OpenChat v2')}")

    chatbot = gr.Chatbot(label="Chat", height=500, elem_id="chatbot")
    msg_textbox = gr.Textbox(label="Deine Nachricht", placeholder="Stelle eine Frage...", scale=7)

    with gr.Row():
        model_dropdown = gr.Dropdown(
            label="Modell",
            choices=config.available_models,
            value=config.default_model
        )
        temperature_slider = gr.Slider(
            minimum=0.0,
            maximum=2.0,
            step=0.1,
            value=config.gui.get("default_temperature", 0.7),
            label="Temperatur"
        )
    
    with gr.Row():
        send_button = gr.Button("Senden", variant="primary")
        clear_button = gr.Button("Chat löschen")

    # Event-Handler, die UI-Elemente mit Funktionen verbinden
    send_button.click(
        fn=handle_chat_interaction,
        inputs=[msg_textbox, temperature_slider, model_dropdown, chatbot],
        outputs=[chatbot, msg_textbox]
    )
    msg_textbox.submit(
        fn=handle_chat_interaction,
        inputs=[msg_textbox, temperature_slider, model_dropdown, chatbot],
        outputs=[chatbot, msg_textbox]
    )
    clear_button.click(fn=clear_chat, outputs=[chatbot, msg_textbox])


if __name__ == "__main__":
    log.info("Starte die Gradio-Anwendung...")
    # `share=True` erzeugt einen öffentlichen Link, nützlich für Demos. Kann weggelassen werden.
    app.launch()
