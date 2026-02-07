# Translation system for the bot
# All UI strings are loaded from JSON files in locales/ directory

import json
import os
from dotenv import load_dotenv

load_dotenv()

# Global translations dictionary
# Structure: {language_code: {key: value}}
TRANSLATIONS = {}

def init_translations_table():
    """Deprecated: Translations now loaded from files."""
    pass

def populate_initial_translations():
    """Deprecated: Translations now loaded from files."""
    pass

def load_translations():
    """Load all translations from locales/ directory into memory"""
    global TRANSLATIONS
    TRANSLATIONS = {}
    
    # Path is relative to this file
    base_dir = os.path.dirname(__file__)
    locales_dir = os.path.join(base_dir, "locales")
    
    if not os.path.exists(locales_dir):
        print(f"⚠️ Locales directory not found: {locales_dir}")
        return

    # Load known languages
    for lang_code in ["ru", "en"]:
        file_path = os.path.join(locales_dir, f"{lang_code}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    TRANSLATIONS[lang_code] = data
                print(f"✅ Loaded {lang_code} from {file_path} ({len(data)} keys)")
            except Exception as e:
                print(f"❌ Error loading {lang_code}.json: {e}")
        else:
            print(f"⚠️ File not found: {file_path}")
            
    # Verify loaded
    if not TRANSLATIONS:
         print("⚠️ No translations loaded!")

def t(key, language_id=1, **kwargs):
    """
    Get translation for a key
    
    Args:
        key: Translation key
        language_id: Language ID (1=Russian, 2=English, etc.)
        **kwargs: Format parameters for string formatting
    
    Returns:
        Translated string
    """
    # Map language_id to language_code
    lang_code_map = {1: "ru", 2: "en"}
    lang_code = lang_code_map.get(language_id, "ru")
    
    # Get translation
    # Fallback to key if not found
    translation = TRANSLATIONS.get(lang_code, {}).get(key, key)
    
    # Apply formatting if kwargs provided
    if kwargs:
        try:
            translation = translation.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            # If format fails (e.g. missing arg), return unformatted or formatted partially
            pass
    
    return translation

def get_lang_code(language_id):
    """Convert language_id to language code"""
    lang_code_map = {1: "ru", 2: "en"}
    return lang_code_map.get(language_id, "ru")
