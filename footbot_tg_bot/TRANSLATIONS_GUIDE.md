# Translation System Usage Guide

## Overview

The bot uses an **in-memory translation system** for maximum performance. All translations are loaded once at bot startup and cached in RAM.

## Architecture

```
translations.py
├── TRANSLATIONS dict (in memory)
├── init_translations_table() - creates DB table
├── populate_initial_translations() - adds initial data
├── load_translations() - loads all into memory
└── t(key, language_id, **kwargs) - get translation
```

## Usage

### 1. Getting Translations

```python
import translations as tr

# Simple translation
text = tr.t("admin_player_mgmt", language_id=1)  # Returns: "👥 Управление игроками"
text = tr.t("admin_player_mgmt", language_id=2)  # Returns: "👥 Player Management"

# With formatting
text = tr.t("total_players", language_id=1, count=12)  # If translation has {count}
```

### 2. In Handlers

```python
@dp.callback_query(F.data == "some_action")
async def handler(callback: CallbackQuery, state: FSMContext):
    # Get language from settings
    settings = db.get_match_settings(chat_id, thread_id)
    language_id = settings.get('language_id', 1)
    
    # Use translations
    await callback.message.answer(tr.t("some_message", language_id))
    
    # Build keyboard with translations
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("btn_back", language_id), callback_data="back")
```

### 3. Adding New Translations

Edit `translations.py` and add to `translations_data` dict:

```python
"new_key": {
    "ru": "Русский текст",
    "en": "English text"
},
```

Then restart the bot - translations will be auto-populated and loaded.

## Adding New Language

1. Add language to `localization.py`:
```python
LANGUAGES.append({"code": "es", "name": "Español", "emoji": "🇪🇸"})
```

2. Add translations in `translations.py`:
```python
"admin_player_mgmt": {
    "ru": "👥 Управление игроками",
    "en": "👥 Player Management",
    "es": "👥 Gestión de Jugadores"  # NEW
},
```

3. Update `lang_code_map` in `translations.py`:
```python
lang_code_map = {1: "ru", 2: "en", 3: "es"}  # Add new mapping
```

4. Restart bot

## Performance

- ✅ **Zero DB queries** for translations during runtime
- ✅ **Instant access** - dictionary lookup in memory
- ✅ **Low memory footprint** - ~100KB for 1000 translations
- ✅ **Startup time** - <100ms to load all translations

## Current Translations

See `translations.py` for the complete list. Currently includes:
- Admin menu items
- Bot settings
- Match settings
- Registration interface
- Common buttons (Back, Done, Edit, etc.)
- Error messages

## Migration Strategy

The system supports gradual migration:
1. New features use `tr.t()` from the start
2. Old code can be updated incrementally
3. Hardcoded strings still work (backward compatible)
4. No breaking changes to existing functionality
