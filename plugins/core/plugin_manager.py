import importlib
import pkgutil
from typing import Dict, List

# Wir importieren wieder unsere eigenen Module
from src.logger import log
from .plugin_base import BasePlugin

class PluginManager:
    """
    Verwaltet die Entdeckung, das Laden und die Ausführung von Plugins.
    """
    def __init__(self, plugin_paths: List[str] = ['plugins']):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_paths = plugin_paths
        # Starte die Suche direkt beim Initialisieren
        self.discover_plugins()

    def discover_plugins(self):
        """
        Sucht und lädt alle gültigen Plugins aus den angegebenen Pfaden.
        Ein gültiges Plugin ist eine Klasse, die von BasePlugin erbt.
        """
        log.info("Suche nach Plugins...")
        for module_info in pkgutil.iter_modules(self.plugin_paths):
            # Wir durchsuchen nur den Haupt-Plugin-Ordner, nicht 'core'
            if module_info.name == 'core':
                continue
            try:
                # Dynamischer Import des gefundenen Plugin-Moduls
                module = importlib.import_module(f'plugins.{module_info.name}')
                for item_name in dir(module):
                    item = getattr(module, item_name)
                    if isinstance(item, type) and issubclass(item, BasePlugin) and item is not BasePlugin:
                        plugin_instance = item()
                        self.register_plugin(plugin_instance)
            except Exception as e:
                log.error(f"Fehler beim Laden des Plugins {module_info.name}: {e}")

    def register_plugin(self, plugin: BasePlugin):
        """Registriert eine einzelne Plugin-Instanz."""
        if plugin.name in self.plugins:
            log.warning(f"Plugin mit dem Namen '{plugin.name}' ist bereits registriert und wird überschrieben.")
        self.plugins[plugin.name] = plugin
        log.info(f"Plugin '{plugin.name}' erfolgreich registriert.")

    def apply_plugins(self, text: str) -> str:
        """Führt alle registrierten Plugins nacheinander auf einen Text aus."""
        processed_text = text
        for name, plugin in self.plugins.items():
            try:
                processed_text = plugin.execute(processed_text)
                log.debug(f"Plugin '{name}' erfolgreich auf Text angewendet.")
            except Exception as e:
                log.error(f"Fehler bei der Ausführung des Plugins '{name}': {e}")
        return processed_text

# Globale Instanz, die wir später in der Haupt-App verwenden
plugin_manager = PluginManager()
