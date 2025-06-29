import re
from html import escape

from plugin_interface import ChatPlugin, Message
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter

class SyntaxHighlightPlugin(ChatPlugin):
    """
    Findet Codeblöcke in KI-Antworten und hebt sie mit Pygments hervor.
    """

    def get_name(self) -> str:
        return "Syntax Highlighter"

    def get_description(self) -> str:
        return "Färbt Codeblöcke in den Antworten der KI."

    def on_api_response(self, message_object: Message):
        """
        Verarbeitet die Antwort, sucht nach Codeblöcken und wandelt sie in HTML um.
        """
        content = message_object.content
        
        # Pattern, um Codeblöcke wie ```python ... ``` zu finden.
        # Es erfasst die Sprache (optional) und den Code.
        pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

        # Wir müssen den Text manuell escapen, bevor wir HTML einfügen,
        # da der Standard-Escaping-Pfad nicht mehr für diese Nachricht gilt.
        escaped_content = escape(content)

        # Eine Funktion, die jeden gefundenen Codeblock durch seine HTML-Version ersetzt.
        def replacer(match):
            lang = match.group(1).strip()
            code = match.group(2)
            
            try:
                # Versuche, den Lexer anhand des Sprachnamens zu finden (z.B. "python")
                if lang:
                    lexer = get_lexer_by_name(lang, stripall=True)
                else:
                    # Wenn keine Sprache angegeben ist, versuche sie zu erraten
                    lexer = guess_lexer(code, stripall=True)
            except Exception:
                # Wenn alles fehlschlägt, nimm einen einfachen Text-Lexer
                lexer = get_lexer_by_name("text", stripall=True)
            
            # Formatter für HTML, passend zu unserem dunklen Thema.
            # nobackground=True ist wichtig, damit die Blase ihre Farbe behält.
            formatter = HtmlFormatter(style='dracula', nobackground=True)
            
            # Generiere das HTML für den Codeblock
            highlighted_code = highlight(code, lexer, formatter)
            
            # Da der umgebende Text bereits escaped ist, ist dies sicher.
            return highlighted_code

        # Führe die Ersetzung für alle gefundenen Blöcke durch
        new_content, num_replacements = pattern.subn(replacer, escaped_content)

        # Wenn mindestens ein Codeblock gefunden wurde, aktualisiere das Message-Objekt
        if num_replacements > 0:
            # Ersetze die escaped newlines wieder durch <br> für die HTML-Anzeige
            message_object.content = new_content.replace('\n', '<br>')
            message_object.display_format = 'html'
