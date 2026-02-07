# Localization data for multilingual support

LANGUAGES = [
    {"code": "ru", "name": "Русский", "emoji": "🇷🇺"},
    {"code": "en", "name": "English", "emoji": "🇬🇧"},
]

# Skill levels: (language_code, label, id_type)
# Skill levels: (language_code, label, id_type)
SKILL_LEVELS = [
    ("ru", "⚽ Просто пинаем мяч", 1),
    ("ru", "🏆 Готовимся к турнирам", 2),
    ("ru", "🔥 Полупро/Про на отдыхе", 3),
    ("en", "⚽ Just for fun", 1),
    ("en", "🏆 Tournament prep", 2),
    ("en", "🔥 Semi-pro chill", 3),
]

# Age groups: (language_code, label, id_type)
# Age groups: (language_code, label, id_type)
AGE_GROUPS = [
    ("ru", "🧒 Школьники", 1),
    ("ru", "🎓 Студенты", 2),
    ("ru", "👨 До 40", 3),
    ("ru", "🎅 До 100", 4),
    ("en", "🧒 School", 1),
    ("en", "🎓 Students", 2),
    ("en", "👨 Under 40", 3),
    ("en", "🎅 Under 100", 4),
]

# Genders: (language_code, label, id_type)
# Genders: (language_code, label, id_type)
GENDERS = [
    ("ru", "👨 Мужчины", 1),
    ("ru", "👩 Женщины", 2),
    ("ru", "🚻 Смешанный", 3),
    ("en", "👨 Men", 1),
    ("en", "👩 Women", 2),
    ("en", "🚻 Mixed", 3),
]

# Venue types: (language_code, label, id_type)
# Venue types: (language_code, label, id_type)
VENUE_TYPES = [
    ("ru", "🏢 Закрытая", 1),
    ("ru", "🌳 Открытая", 2),
    ("ru", "🏛 Общественная", 3),
    ("en", "🏢 Indoor", 1),
    ("en", "🌳 Outdoor", 2),
    ("en", "🏛 Public", 3),
]

def _remove_duplicates(cursor, table_name):
    """Remove duplicate rows, keeping the one with the lowest ID"""
    try:
        cursor.execute(f"""
            DELETE t1 FROM {table_name} t1
            INNER JOIN {table_name} t2 
            WHERE 
                t1.id > t2.id AND 
                t1.language_id = t2.language_id AND 
                t1.label = t2.label
        """)
    except Exception as e:
        print(f"Error removing duplicates from {table_name}: {e}")

def _insert_if_not_exists(cursor, table_name, lang_id, label, id_type):
    cursor.execute(f"SELECT id FROM {table_name} WHERE language_id = %s AND label = %s", (lang_id, label))
    if not cursor.fetchone():
        cursor.execute(f"""
            INSERT INTO {table_name} (language_id, label, id_type)
            VALUES (%s, %s, %s)
        """, (lang_id, label, id_type))


def _get_table_fk_column(table_name):
    """Return the column name in settings table for the given reference table"""
    # map age_groups -> age_group_id
    if table_name.endswith('s'):
        return table_name[:-1] + "_id"
    return table_name + "_id"

def _cleanup_unknown(cursor, table_name, allowed_data, lang_map):
    """
    Remove rows that are not in the allowed list.
    If a row is removed, try to migrate any settings pointing to it 
    to a valid row with the same language and id_type.
    """
    # allowed_data is list of (lang_code, label, id_type)
    # Build map: (lang_id, id_type) -> { 'label': label, 'id': db_id }
    
    # 1. Get current valid IDs for the allowed data
    valid_map = {} # (lang_id, id_type) -> valid_db_id
    for lang_code, label, id_type in allowed_data:
        if lang_code not in lang_map: continue
        lid = lang_map[lang_code]
        
        cursor.execute(f"SELECT id FROM {table_name} WHERE language_id = %s AND label = %s", (lid, label))
        res = cursor.fetchone()
        if res:
            valid_map[(lid, id_type)] = res[0]
            
    # 2. Get all rows in DB
    cursor.execute(f"SELECT id, language_id, label, id_type FROM {table_name}")
    all_rows = cursor.fetchall()
    
    allowed_labels = set(item[1] for item in allowed_data)
    
    setting_col = _get_table_fk_column(table_name)
    
    for row_id, lid, label, id_type in all_rows:
        if label in allowed_labels:
            continue
            
        # This is an unknown/old label.
        # Try to find a replacement (same lang, same id_type)
        target_id = valid_map.get((lid, id_type))
        
        if target_id:
            # Migrate settings
            try:
                # print(f"Migrating {table_name} {row_id} ('{label}') -> {target_id}")
                cursor.execute(f"UPDATE settings SET {setting_col} = %s WHERE {setting_col} = %s", (target_id, row_id))
            except Exception as e:
                pass
                # print(f"Error migrating settings: {e}")
        
        # Delete the old row
        try:
            cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", (row_id,))
        except Exception as e:
            pass
            # print(f"Could not delete old row {row_id} from {table_name}: {e}")

def init_localization_data(conn):
    """Initialize languages and reference data"""
    cursor = conn.cursor()
    
    # Insert languages
    for lang in LANGUAGES:
        cursor.execute("""
            INSERT IGNORE INTO languages (code, name, emoji) 
            VALUES (%s, %s, %s)
        """, (lang["code"], lang["name"], lang["emoji"]))
    
    # Get language IDs
    cursor.execute("SELECT id, code FROM languages")
    lang_map = {code: id for id, code in cursor.fetchall()}
    
    # Tables to manage
    tables_data = [
        ("skill_levels", SKILL_LEVELS),
        ("age_groups", AGE_GROUPS),
        ("genders", GENDERS),
        ("venue_types", VENUE_TYPES),
    ]
    
    for table_name, data_list in tables_data:
        # 1. Insert missing (ensure new values exist)
        for lang_code, label, id_type in data_list:
            if lang_code in lang_map:
                _insert_if_not_exists(cursor, table_name, lang_map[lang_code], label, id_type)
        
        # 2. Cleanup old values (migrate references if possible)
        _cleanup_unknown(cursor, table_name, data_list, lang_map)
        
        # 3. Cleanup duplicates (just in case)
        _remove_duplicates(cursor, table_name)
    
    conn.commit()
