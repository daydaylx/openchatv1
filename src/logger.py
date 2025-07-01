import logging
import sys

def setup_logger(log_level="INFO", log_file="app.log"):
    """
    Konfiguriert und initialisiert einen globalen Logger.

    Der Logger gibt Nachrichten sowohl in die Konsole als auch in eine Log-Datei aus.
    Das Format enthält Zeitstempel, Loglevel und die Nachricht.
    """
    # Verhindert das Hinzufügen mehrerer Handler, wenn die Funktion erneut aufgerufen wird
    logger = logging.getLogger()
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(log_level)

    # Format für die Log-Nachrichten definieren
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Konsolen-Handler erstellen (gibt Logs im Terminal aus)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # Datei-Handler erstellen (schreibt Logs in eine Datei)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Einmalige Initialisierung beim Import, damit der Logger sofort verfügbar ist
log = setup_logger()

log.info("Logger wurde erfolgreich initialisiert.")
