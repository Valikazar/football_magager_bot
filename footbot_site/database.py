import mysql.connector
import os
import json
from datetime import datetime, timedelta
import logging
import math
import re
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "footbot")
    )

def init_db():
    # Attempt to create database if it doesn't exist
    temp_conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root")
    )
    cursor = temp_conn.cursor(buffered=True)
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('DB_NAME', 'footbot')}")
    temp_conn.close()

    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    
    # Players table (basic info only)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT UNIQUE,
        name VARCHAR(255) NOT NULL
    )
    """)
    
    # Languages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS languages (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(10) UNIQUE NOT NULL,
        name VARCHAR(50) NOT NULL,
        emoji VARCHAR(10)
    )
    """)
    
    # Skill levels reference
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS skill_levels (
        id INT AUTO_INCREMENT PRIMARY KEY,
        language_id INT,
        label VARCHAR(100) NOT NULL,
        id_type INT DEFAULT 0,
        FOREIGN KEY (language_id) REFERENCES languages(id) ON DELETE CASCADE
    )
    """)
    
    # Age groups reference
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS age_groups (
        id INT AUTO_INCREMENT PRIMARY KEY,
        language_id INT,
        label VARCHAR(100) NOT NULL,
        id_type INT DEFAULT 0,
        FOREIGN KEY (language_id) REFERENCES languages(id) ON DELETE CASCADE
    )
    """)
    
    # Genders reference
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS genders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        language_id INT,
        label VARCHAR(100) NOT NULL,
        id_type INT DEFAULT 0,
        FOREIGN KEY (language_id) REFERENCES languages(id) ON DELETE CASCADE
    )
    """)
    
    # Venue types reference
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS venue_types (
        id INT AUTO_INCREMENT PRIMARY KEY,
        language_id INT,
        label VARCHAR(100) NOT NULL,
        id_type INT DEFAULT 0,
        FOREIGN KEY (language_id) REFERENCES languages(id) ON DELETE CASCADE
    )
    """)

    # Player stats per league/skill level
    # Player stats per chat/thread (skill_level removed - it's a match parameter, not player attribute)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_stats (
        player_id INT,
        chat_id BIGINT DEFAULT 0,
        thread_id BIGINT DEFAULT 0,
        display_name VARCHAR(255),
        attack INT DEFAULT 50,
        defense INT DEFAULT 50,
        speed INT DEFAULT 50,
        gk INT DEFAULT 50,
        is_core TINYINT DEFAULT 0,
        PRIMARY KEY (player_id, chat_id, thread_id),
        FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
    )
    """)

    # Schema migration for player_stats
    try:
        cursor.execute("SHOW COLUMNS FROM player_stats LIKE 'is_core'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE player_stats ADD COLUMN is_core TINYINT DEFAULT 0")
    except Exception as e:
        print(f"Warning checking schema: {e}")
    
    # Registrations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        player_id INT,
        chat_id BIGINT,
        thread_id BIGINT DEFAULT 0,
        position VARCHAR(20) NOT NULL,
        is_paid INT DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, chat_id, thread_id),
        FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
    )
    """)

    # Matches table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat_id BIGINT NOT NULL DEFAULT 0,
        thread_id BIGINT NOT NULL DEFAULT 0,
        match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        skill_level VARCHAR(100),
        score VARCHAR(20)
    )
    """)

    # Match history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS match_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        match_id INT,
        player_id INT,
        points INT DEFAULT 0,
        goals INT DEFAULT 0,
        autogoals INT DEFAULT 0,
        best_defender TINYINT DEFAULT 0,
        team VARCHAR(20),
        UNIQUE(match_id, player_id),
        FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
        FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
    )
    """)

    # Match events table (goals, autogoals, cards with optional time)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS match_events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        match_history_id INT,
        event_type ENUM('goal', 'autogoal', 'card_yellow', 'card_red'),
        event_time INT DEFAULT NULL,
        assist_player_id INT DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(match_history_id) REFERENCES match_history(id) ON DELETE CASCADE,
        FOREIGN KEY(assist_player_id) REFERENCES players(id) ON DELETE SET NULL
    )
    """)

    # Schema migration for match_events (add assist_player_id)
    try:
        cursor.execute("SHOW COLUMNS FROM match_events LIKE 'assist_player_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE match_events ADD COLUMN assist_player_id INT DEFAULT NULL")
            cursor.execute("ALTER TABLE match_events ADD CONSTRAINT fk_assist_player FOREIGN KEY (assist_player_id) REFERENCES players(id) ON DELETE SET NULL")
            print("Added assist_player_id to match_events")
            
        # Schema migration for match_events (add is_penalty)
        cursor.execute("SHOW COLUMNS FROM match_events LIKE 'is_penalty'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE match_events ADD COLUMN is_penalty TINYINT DEFAULT 0")
            print("Added is_penalty to match_events")

        # Ensure 'minute' column exists (rename event_time if present)
        cursor.execute("SHOW COLUMNS FROM match_events LIKE 'minute'")
        if not cursor.fetchone():
            cursor.execute("SHOW COLUMNS FROM match_events LIKE 'event_time'")
            if cursor.fetchone():
                cursor.execute("ALTER TABLE match_events CHANGE event_time minute INT DEFAULT NULL")
                print("Renamed event_time to minute in match_events")
            else:
                cursor.execute("ALTER TABLE match_events ADD COLUMN minute INT DEFAULT NULL")
                print("Added minute column to match_events")
                
    except Exception as e:
        print(f"Warning checking schema match_events: {e}")

    # Schema migration for match_history (add assists)
    try:
        cursor.execute("SHOW COLUMNS FROM match_history LIKE 'assists'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE match_history ADD COLUMN assists INT DEFAULT 0")
            print("Added assists to match_history")
    except Exception as e:
        print(f"Warning checking schema match_history: {e}")

    # Schema migration for match_history (add is_captain)
    try:
        cursor.execute("SHOW COLUMNS FROM match_history LIKE 'is_captain'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE match_history ADD COLUMN is_captain TINYINT DEFAULT 0")
            print("Added is_captain to match_history")
    except Exception as e:
        print(f"Warning checking schema match_history (is_captain): {e}")

    # Schema migration for match_history (add yellow_cards and red_cards)
    try:
        cursor.execute("SHOW COLUMNS FROM match_history LIKE 'yellow_cards'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE match_history ADD COLUMN yellow_cards INT DEFAULT 0")
            print("Added yellow_cards to match_history")
    except Exception as e:
        print(f"Warning checking schema match_history (yellow_cards): {e}")
    
    try:
        cursor.execute("SHOW COLUMNS FROM match_history LIKE 'red_cards'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE match_history ADD COLUMN red_cards INT DEFAULT 0")
            print("Added red_cards to match_history")
    except Exception as e:
        print(f"Warning checking schema match_history (red_cards): {e}")

    # Schema migration for settings (add championship_name)
    try:
        cursor.execute("SHOW COLUMNS FROM settings LIKE 'championship_name'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE settings ADD COLUMN championship_name VARCHAR(255) DEFAULT NULL")
            print("Added championship_name to settings")
    except Exception as e:
        print(f"Warning checking schema settings (championship_name): {e}")

    # Schema migration for match_events (add is_penalty)
    try:
        cursor.execute("SHOW COLUMNS FROM match_events LIKE 'is_penalty'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE match_events ADD COLUMN is_penalty TINYINT DEFAULT 0")
            print("Added is_penalty to match_events")
    except Exception as e:
        print(f"Warning checking schema match_events (is_penalty): {e}")



    # Draw voting
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS draw_votes (
        chat_id BIGINT NOT NULL DEFAULT 0,
        thread_id BIGINT NOT NULL DEFAULT 0,
        variant_id INT,
        voter_id BIGINT NOT NULL,
        vote_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, thread_id, voter_id)
    )
    """)

    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        chat_id BIGINT NOT NULL DEFAULT 0,
        thread_id BIGINT NOT NULL DEFAULT 0,
        language_id INT DEFAULT 1,
        player_count INT DEFAULT 12,
        skill_level_id INT,
        age_group_id INT,
        gender_id INT,
        venue_type_id INT,
        cost VARCHAR(100) DEFAULT '—',
        timezone VARCHAR(20) DEFAULT 'GMT+3',
        match_times TEXT,
        season_start DATE,
        season_end DATE,
        is_active TINYINT DEFAULT 0,
        location_lat DECIMAL(10, 8),
        location_lon DECIMAL(11, 8),
        remind_before_game TINYINT DEFAULT 0,
        remind_after_game TINYINT DEFAULT 1,
        core_team_mode TINYINT DEFAULT 0,
        track_assists TINYINT DEFAULT 0,
        PRIMARY KEY (chat_id, thread_id),
        FOREIGN KEY (language_id) REFERENCES languages(id),
        FOREIGN KEY (skill_level_id) REFERENCES skill_levels(id),
        FOREIGN KEY (age_group_id) REFERENCES age_groups(id),
        FOREIGN KEY (gender_id) REFERENCES genders(id),
        FOREIGN KEY (venue_type_id) REFERENCES venue_types(id)
    )
    """)

    # Draft state
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS draft_state (
        chat_id BIGINT NOT NULL DEFAULT 0,
        thread_id BIGINT NOT NULL DEFAULT 0,
        state_data LONGTEXT,
        PRIMARY KEY (chat_id, thread_id)
    )
    """)

    # Persistent FSM Storage table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fsm_data (
        chat_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        state VARCHAR(255) DEFAULT NULL,
        data LONGTEXT DEFAULT NULL,
        PRIMARY KEY (chat_id, user_id)
    )
    """)
    
    # Migration: add display_name to player_stats if missing
    cursor.execute("SHOW COLUMNS FROM player_stats LIKE 'display_name'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE player_stats ADD COLUMN display_name VARCHAR(255) AFTER skill_level")
        conn.commit()
    
    # Migration: add venue_type and location to settings if missing
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'venue_type'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN venue_type VARCHAR(50) DEFAULT '—' AFTER is_active")
        conn.commit()
    
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'location_lat'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN location_lat DECIMAL(10, 8) AFTER venue_type")
        cursor.execute("ALTER TABLE settings ADD COLUMN location_lon DECIMAL(11, 8) AFTER location_lat")
        conn.commit()
    
    
    # Migration: rename sort_order to id_type if needed
    for table_name in ["skill_levels", "age_groups", "genders", "venue_types"]:
        cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE 'id_type'")
        if not cursor.fetchone():
            # Check if sort_order or sort exists to rename
            cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE 'sort_order'")
            if cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table_name} CHANGE sort_order id_type INT DEFAULT 0")
            else:
                cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE 'sort'")
                if cursor.fetchone():
                    cursor.execute(f"ALTER TABLE {table_name} CHANGE sort id_type INT DEFAULT 0")
        conn.commit()

    # Migration: add multilingual support fields to settings
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'language_id'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN language_id INT DEFAULT 1 AFTER thread_id")
        cursor.execute("ALTER TABLE settings ADD COLUMN skill_level_id INT AFTER player_count")
        cursor.execute("ALTER TABLE settings ADD COLUMN age_group_id INT AFTER skill_level_id")
        cursor.execute("ALTER TABLE settings ADD COLUMN gender_id INT AFTER age_group_id")
        cursor.execute("ALTER TABLE settings ADD COLUMN venue_type_id INT AFTER gender_id")
        conn.commit()
    
    # Migration: update registrations and settings for payment
    cursor.execute("SHOW COLUMNS FROM registrations LIKE 'is_paid'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE registrations ADD COLUMN is_paid INT DEFAULT 0")
        conn.commit()

    cursor.execute("SHOW COLUMNS FROM settings LIKE 'remind_before_game'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN remind_before_game TINYINT DEFAULT 0")
        cursor.execute("ALTER TABLE settings ADD COLUMN remind_after_game TINYINT DEFAULT 1")
        conn.commit()
    
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'require_payment_confirmation'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN require_payment_confirmation TINYINT DEFAULT 0")
        conn.commit()

    # Migration: add poll_message_id
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'poll_message_id'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN poll_message_id BIGINT DEFAULT 0")
        conn.commit()
        
    cursor.execute("SHOW COLUMNS FROM registrations LIKE 'updated_at'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE registrations ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        conn.commit()

    # Migration: add status to registrations
    cursor.execute("SHOW COLUMNS FROM registrations LIKE 'status'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE registrations ADD COLUMN status VARCHAR(20) DEFAULT 'active'")
        conn.commit()

    # Migration: add match event tracking settings
    for col in ['track_goals', 'track_goal_times', 'track_cards', 'track_card_times']:
        cursor.execute(f"SHOW COLUMNS FROM settings LIKE '{col}'")
        if not cursor.fetchone():
            default = 1 if col == 'track_goals' else 0
            cursor.execute(f"ALTER TABLE settings ADD COLUMN {col} TINYINT DEFAULT {default}")
            conn.commit()

    # Migration: add rating system settings
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'rating_mode'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN rating_mode VARCHAR(20) DEFAULT 'ranked'")
        conn.commit()
    
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'track_best_defender'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN track_best_defender TINYINT DEFAULT 1")
        conn.commit()
    
    # Migration: add payment system settings
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'cost_mode'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN cost_mode VARCHAR(20) DEFAULT 'fixed_player'")
        conn.commit()
    
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'payment_details'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN payment_details TEXT NULL")
        conn.commit()
    
    # Migration: remove skill_level from player_stats (it's a match parameter, not player attribute)
    cursor.execute("SHOW COLUMNS FROM player_stats LIKE 'skill_level'")
    if cursor.fetchone():
        try:
            # Alternative approach: create new table, copy data, drop old, rename
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_stats_new (
                    player_id INT,
                    chat_id BIGINT DEFAULT 0,
                    thread_id BIGINT DEFAULT 0,
                    display_name VARCHAR(255),
                    attack INT DEFAULT 50,
                    defense INT DEFAULT 50,
                    speed INT DEFAULT 50,
                    gk INT DEFAULT 50,
                    PRIMARY KEY (player_id, chat_id, thread_id),
                    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                INSERT INTO player_stats_new (player_id, chat_id, thread_id, display_name, attack, defense, speed, gk)
                SELECT player_id, chat_id, thread_id, display_name, attack, defense, speed, gk
                FROM player_stats
                GROUP BY player_id, chat_id, thread_id
            """)
            
            cursor.execute("DROP TABLE player_stats")
            
            cursor.execute("RENAME TABLE player_stats_new TO player_stats")
            
            conn.commit()
        except Exception as e:
            # print(f"⚠️  Could not migrate player_stats: {e}")
            conn.rollback()
            # Try to clean up if new table was created
            try:
                cursor.execute("DROP TABLE IF EXISTS player_stats_new")
                conn.commit()
            except:
                pass
    
    # Migration: add core_team_mode to settings if missing
    cursor.execute("SHOW COLUMNS FROM settings LIKE 'core_team_mode'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE settings ADD COLUMN core_team_mode TINYINT DEFAULT 0")
        conn.commit()

    # Migration: add championship_name to matches
    cursor.execute("SHOW COLUMNS FROM matches LIKE 'championship_name'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE matches ADD COLUMN championship_name VARCHAR(255) DEFAULT NULL")
        conn.commit()
    
    # Initialize localization data (languages and reference tables)
    try:
        import localization
        localization.init_localization_data(conn)
    except Exception as e:
        import logging
        logging.warning(f"Could not initialize localization data: {e}")
    
    # Initialize translations table and data
    try:
        import translations
        translations.init_translations_table()
        translations.populate_initial_translations()
    except Exception as e:
        import logging
        logging.warning(f"Could not initialize translations: {e}")

    conn.commit()
    conn.close()

# === LOCALIZATION FUNCTIONS ===

def get_languages():
    """Get all available languages"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, name, emoji FROM languages ORDER BY id")
    languages = cursor.fetchall()
    conn.close()
    return [{"id": l[0], "code": l[1], "name": l[2], "emoji": l[3]} for l in languages]

def get_skill_levels(language_id=1):
    """Get skill levels for a specific language"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_type, label FROM skill_levels 
        WHERE language_id = %s 
        ORDER BY id_type
    """, (language_id,))
    levels = cursor.fetchall()
    conn.close()
    return [{"id": l[0], "label": l[1]} for l in levels]

def get_age_groups(language_id=1):
    """Get age groups for a specific language"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_type, label FROM age_groups 
        WHERE language_id = %s 
        ORDER BY id_type
    """, (language_id,))
    groups = cursor.fetchall()
    conn.close()
    return [{"id": g[0], "label": g[1]} for g in groups]

def get_genders(language_id=1):
    """Get genders for a specific language"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_type, label FROM genders 
        WHERE language_id = %s 
        ORDER BY id_type
    """, (language_id,))
    genders = cursor.fetchall()
    conn.close()
    return [{"id": g[0], "label": g[1]} for g in genders]

def get_venue_types(language_id=1):
    """Get venue types for a specific language"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_type, label FROM venue_types 
        WHERE language_id = %s 
        ORDER BY id_type
    """, (language_id,))
    types = cursor.fetchall()
    conn.close()
    return [{"id": t[0], "label": t[1]} for t in types]

def get_label_by_id(table, id_value, language_id=1):
    """Get label for a specific ID from reference table"""
    if not id_value:
        return "—"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT label FROM {table} 
        WHERE id_type = %s AND language_id = %s
    """, (id_value, language_id))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "—"

def get_player_by_id(player_id, chat_id=0, thread_id=0):
    """Get player info with stats for specific chat/thread"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.id, p.user_id, 
               COALESCE(s.display_name, p.name) as name,
               COALESCE(s.attack, 50), COALESCE(s.defense, 50), 
               COALESCE(s.speed, 50), COALESCE(s.gk, 50)
        FROM players p
        LEFT JOIN player_stats s ON p.id = s.player_id AND s.chat_id = %s AND s.thread_id = %s
        WHERE p.id = %s
    """, (chat_id, thread_id, player_id))
    player = cursor.fetchone()
    
    conn.close()
    return player

def get_player_by_user_id(user_id, chat_id=0, thread_id=0):
    """Get player info by Telegram user_id with stats for specific chat/thread"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.user_id, 
               COALESCE(s.display_name, p.name) as name,
               COALESCE(s.attack, 50), COALESCE(s.defense, 50), 
               COALESCE(s.speed, 50), COALESCE(s.gk, 50),
               COALESCE(s.is_core, 0)
        FROM players p
        LEFT JOIN player_stats s ON p.id = s.player_id AND s.chat_id = %s AND s.thread_id = %s
        WHERE p.id = %s
    """, (chat_id, thread_id, player_id))
    player = cursor.fetchone()
    conn.close()
    return player

def get_player_by_user_id(user_id, chat_id, thread_id=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.user_id, 
               COALESCE(s.display_name, p.name) as name,
               COALESCE(s.attack, 50), COALESCE(s.defense, 50), 
               COALESCE(s.speed, 50), COALESCE(s.gk, 50),
               COALESCE(s.is_core, 0)
        FROM players p
        LEFT JOIN player_stats s ON p.id = s.player_id AND s.chat_id = %s AND s.thread_id = %s
        WHERE p.user_id = %s
    """, (chat_id, thread_id, user_id))
    player = cursor.fetchone()
    conn.close()
    return player

def player_has_stats(player_id, chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM player_stats WHERE player_id = %s AND chat_id = %s AND thread_id = %s", 
                   (player_id, chat_id, thread_id))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def upsert_player(user_id, name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO players (user_id, name) VALUES (%s, %s) 
    ON DUPLICATE KEY UPDATE name=VALUES(name)
    """, (user_id, name))
    conn.commit()
    conn.close()

def update_player_name_by_id(player_id, name):
    """Updates Telegram name in players table (not recommended - use update_player_display_name instead)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE players SET name = %s WHERE id = %s", (name, player_id))
    conn.commit()
    conn.close()

def update_player_display_name(player_id, chat_id, thread_id, display_name):
    """Updates context-specific display name in player_stats"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO player_stats (player_id, chat_id, thread_id, display_name)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE display_name = VALUES(display_name)
    """, (player_id, chat_id, thread_id, display_name))
    conn.commit()
    conn.close()

def create_legionnaire(name, chat_id, thread_id, attack, defense, speed, gk):
    """Create a legionnaire (player without Telegram account) with stats"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Create player record
    cursor.execute("INSERT INTO players (name) VALUES (%s)", (name,))
    player_id = cursor.lastrowid
    
    # 2. Add stats with display_name
    cursor.execute("""
        INSERT INTO player_stats (player_id, chat_id, thread_id, display_name, attack, defense, speed, gk)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (player_id, chat_id, thread_id, name, attack, defense, speed, gk))
    
    conn.commit()
    conn.close()
    return player_id

def update_player_stat(player_id, chat_id, thread_id, stat, value):
    conn = get_connection()
    cursor = conn.cursor()
    if stat in ['attack', 'defense', 'speed', 'gk']:
        query = f"""
            INSERT INTO player_stats (player_id, chat_id, thread_id, {stat}) 
            VALUES (%s, %s, %s, %s) 
            ON DUPLICATE KEY UPDATE {stat} = %s
        """
        cursor.execute(query, (player_id, chat_id, thread_id, value, value))
    conn.commit()
    conn.close()

def update_player_stats_full(player_id, chat_id, thread_id, attack, defense, speed, gk):
    """Update all stats for a player in specific chat/thread"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO player_stats (player_id, chat_id, thread_id, attack, defense, speed, gk)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE attack=%s, defense=%s, speed=%s, gk=%s
    """, (player_id, chat_id, thread_id, attack, defense, speed, gk, attack, defense, speed, gk))
    conn.commit()
    conn.close()

def register_player(player_id, chat_id, thread_id, position, status='active'):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO registrations (player_id, chat_id, thread_id, position, status) 
    VALUES (%s, %s, %s, %s, %s) 
    ON DUPLICATE KEY UPDATE position = VALUES(position), status = VALUES(status), updated_at = CURRENT_TIMESTAMP
    """, (player_id, chat_id, thread_id, position, status))
    conn.commit()
    conn.close()

def unregister_player(player_id, chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM registrations WHERE player_id = %s AND chat_id = %s AND thread_id = %s", (player_id, chat_id, thread_id))
    conn.commit()
    conn.close()

def get_registrations(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.user_id, 
               COALESCE(s.display_name, p.name) as name,
               COALESCE(s.attack, 50), COALESCE(s.defense, 50), 
               COALESCE(s.speed, 50), COALESCE(s.gk, 50), 
               r.position, r.is_paid, r.status
        FROM registrations r
        JOIN players p ON r.player_id = p.id
        LEFT JOIN player_stats s ON p.id = s.player_id AND s.chat_id = %s AND s.thread_id = %s
        WHERE r.chat_id = %s AND r.thread_id = %s
        ORDER BY r.updated_at ASC
    """, (chat_id, thread_id, chat_id, thread_id))
    regs = cursor.fetchall()
    conn.close()
    return regs

def update_registration_status(player_id, chat_id, thread_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE registrations SET status = %s WHERE player_id = %s AND chat_id = %s AND thread_id = %s", 
                   (status, player_id, chat_id, thread_id))
    conn.commit()
    conn.close()

def get_queue(chat_id, thread_id):
    """Get players in queue ordered by join time"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.user_id, COALESCE(s.display_name, p.name) as name
        FROM registrations r
        JOIN players p ON r.player_id = p.id
        LEFT JOIN player_stats s ON p.id = s.player_id AND s.chat_id = %s AND s.thread_id = %s
        WHERE r.chat_id = %s AND r.thread_id = %s AND r.status = 'queue'
        ORDER BY r.updated_at ASC
    """, (chat_id, thread_id, chat_id, thread_id))
    queue = cursor.fetchall()
    conn.close()
    return queue

def clear_registrations(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM registrations WHERE chat_id = %s AND thread_id = %s", (chat_id, thread_id))
    conn.commit()
    conn.close()

def get_player_by_name(name_pattern, chat_id=0, thread_id=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.user_id, p.name, 
               COALESCE(s.attack, 50), COALESCE(s.defense, 50), 
               COALESCE(s.speed, 50), COALESCE(s.gk, 50)
        FROM players p
        LEFT JOIN player_stats s ON p.id = s.player_id AND s.chat_id = %s AND s.thread_id = %s
        WHERE p.name LIKE %s
    """, (chat_id, thread_id, name_pattern))
    player = cursor.fetchone()
    conn.close()
    return player

def get_legionnaires(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name 
        FROM players p
        JOIN player_stats s ON p.id = s.player_id
        WHERE p.user_id IS NULL AND s.chat_id = %s AND s.thread_id = %s
    """, (chat_id, thread_id))
    players = cursor.fetchall()
    conn.close()
    return players

def get_all_players_with_stats(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.user_id,
               COALESCE(s.display_name, p.name) as name,
               COALESCE(s.attack, 50), COALESCE(s.defense, 50), 
               COALESCE(s.speed, 50), COALESCE(s.gk, 50),
               COALESCE(s.is_core, 0)
        FROM players p
        JOIN player_stats s ON p.id = s.player_id AND s.chat_id = %s AND s.thread_id = %s
    """, (chat_id, thread_id))
    players = cursor.fetchall()
    conn.close()
    return players

def get_chat_players(chat_id, thread_id):
    """Get all players in a chat with both Telegram name and display name"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT p.id, p.name as telegram_name, s.display_name
        FROM players p
        JOIN player_stats s ON p.id = s.player_id
        WHERE s.chat_id = %s AND s.thread_id = %s AND p.user_id IS NOT NULL
    """, (chat_id, thread_id))
    players = cursor.fetchall()
    conn.close()
    return players

def get_match_settings(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT player_count, cost, is_active, 
               timezone, match_times, season_start, season_end,
               location_lat, location_lon, language_id,
               skill_level_id, age_group_id, gender_id, venue_type_id,
               remind_before_game, remind_after_game, require_payment_confirmation,
               poll_message_id, track_goals, track_goal_times, track_cards, track_card_times,
               rating_mode, track_best_defender, cost_mode, payment_details, core_team_mode, track_assists,
               championship_name
        FROM settings 
        WHERE chat_id = %s AND thread_id = %s
    """, (chat_id, thread_id))
    settings = cursor.fetchone()
    conn.close()
    if settings:
        return {
            "player_count": settings[0],
            "cost": settings[1],
            "is_active": settings[2],
            "timezone": settings[3] or "GMT+3",
            "match_times": settings[4] or "—",
            "season_start": str(settings[5]) if settings[5] else "—",
            "season_end": str(settings[6]) if settings[6] else "—",
            "location_lat": float(settings[7]) if settings[7] else None,
            "location_lon": float(settings[8]) if settings[8] else None,
            "language_id": settings[9] if settings[9] else 1,
            "skill_level_id": settings[10],
            "age_group_id": settings[11],
            "gender_id": settings[12],
            "venue_type_id": settings[13],
            "remind_before_game": settings[14],
            "remind_after_game": settings[15],
            "require_payment_confirmation": settings[16] if len(settings) > 16 else 0,
            "poll_message_id": settings[17] if len(settings) > 17 else 0,
            "track_goals": settings[18] if len(settings) > 18 else 1,
            "track_goal_times": settings[19] if len(settings) > 19 else 0,
            "track_cards": settings[20] if len(settings) > 20 else 0,
            "track_card_times": settings[21] if len(settings) > 21 else 0,
            "rating_mode": settings[22] if len(settings) > 22 else "ranked",
            "track_best_defender": settings[23] if len(settings) > 23 else 1,
            "cost_mode": settings[24] if len(settings) > 24 else "fixed_player",
            "payment_details": settings[25] if len(settings) > 25 else None,
            "core_team_mode": settings[26] if len(settings) > 26 else 0,
            "track_assists": settings[27] if len(settings) > 27 else 0,
            "championship_name": settings[28] if len(settings) > 28 else None
        }
    return {
        "player_count": 12,
        "cost": "—",
        "is_active": 0,
        "timezone": "GMT+3",
        "match_times": "—",
        "season_start": "—",
        "season_end": "—",
        "location_lat": None,
        "location_lon": None,
        "language_id": 1,
        "skill_level_id": None,
        "age_group_id": None,
        "gender_id": None,
        "venue_type_id": None,
        "remind_before_game": 0,
        "remind_after_game": 1,
        "core_team_mode": 0
    }

def update_match_settings(chat_id, thread_id, key, value):
    conn = get_connection()
    cursor = conn.cursor()
    allowed_keys = ['player_count', 'cost', 'is_active', 
                    'timezone', 'match_times', 'season_start', 'season_end', 
                    'location_lat', 'location_lon', 'language_id',
                    'skill_level_id', 'age_group_id', 'gender_id', 'venue_type_id',
                    'remind_before_game', 'remind_after_game', 'require_payment_confirmation',
                    'poll_message_id', 'track_goals', 'track_goal_times', 'track_cards', 'track_card_times',
                    'rating_mode', 'track_best_defender', 'cost_mode', 'payment_details', 'core_team_mode',
                    'track_assists']
    if key in allowed_keys:
        # Handle empty values as None for dates
        if key in ['season_start', 'season_end'] and (not value or value == "—"):
            value = None
        
        # Log poll_message_id updates for debugging
        if key == 'poll_message_id':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Saving poll_message_id={value} for chat_id={chat_id}, thread_id={thread_id}")
            
        query = f"""
            INSERT INTO settings (chat_id, thread_id, {key}) VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE {key} = VALUES({key})
        """
        cursor.execute(query, (chat_id, thread_id, value))
    conn.commit()
    conn.close()

def calculate_player_cost(chat_id, thread_id):
    """Calculate cost per player based on cost mode setting"""
    settings = get_match_settings(chat_id, thread_id)
    cost_val = settings.get('cost', '0')
    cost_mode = settings.get('cost_mode', 'fixed_player')
    
    def extract_amount(s):
        if not s or s == "—": return 0.0
        if isinstance(s, (int, float)): return float(s)
        import re
        match = re.search(r'(\d+(?:[.,]\d+)?)', str(s))
        if match:
            return float(match.group(1).replace(',', '.'))
        return 0.0

    base_cost = extract_amount(cost_val)
    
    if cost_mode == 'fixed_game':
        # Divide total cost by number of registered players
        player_count = count_registered_players(chat_id, thread_id)
        if player_count > 0:
            # Round up to 0.1
            return math.ceil((base_cost / player_count) * 10) / 10
        return base_cost
    else:
        # Fixed cost per player
        return base_cost

def count_registered_players(chat_id, thread_id):
    """Count total number of registered players"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM registrations 
        WHERE chat_id = %s AND thread_id = %s AND status = 'active'
    """, (chat_id, thread_id))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def create_player_full(user_id, name, chat_id, thread_id, attack, defense, speed, gk):
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Ensure basic player info exists
    cursor.execute("""
    INSERT INTO players (user_id, name) VALUES (%s, %s) 
    ON DUPLICATE KEY UPDATE name=VALUES(name)
    """, (user_id, name))
    
    cursor.execute("SELECT id FROM players WHERE user_id = %s", (user_id,))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return
    player_id = res[0]
    
    # 2. Insert/Update stats for this specific chat and thread
    cursor.execute("""
    INSERT INTO player_stats (player_id, chat_id, thread_id, attack, defense, speed, gk) 
    VALUES (%s, %s, %s, %s, %s, %s, %s) 
    ON DUPLICATE KEY UPDATE 
        attack=VALUES(attack), 
        defense=VALUES(defense), 
        speed=VALUES(speed), 
        gk=VALUES(gk)
    """, (player_id, chat_id, thread_id, attack, defense, speed, gk))
    
    conn.commit()
    conn.close()

def upsert_player_stats(player_id, chat_id, thread_id, attack, defense, speed, gk, display_name=None):
    """Insert or update player stats for specific chat/thread"""
    conn = get_connection()
    cursor = conn.cursor()
    if display_name:
        cursor.execute("""
        INSERT INTO player_stats (player_id, chat_id, thread_id, display_name, attack, defense, speed, gk) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
        ON DUPLICATE KEY UPDATE 
            display_name=VALUES(display_name),
            attack=VALUES(attack), 
            defense=VALUES(defense), 
            speed=VALUES(speed), 
            gk=VALUES(gk)
        """, (player_id, chat_id, thread_id, display_name, attack, defense, speed, gk))
    else:
        cursor.execute("""
        INSERT INTO player_stats (player_id, chat_id, thread_id, attack, defense, speed, gk) 
        VALUES (%s, %s, %s, %s, %s, %s, %s) 
        ON DUPLICATE KEY UPDATE 
            attack=VALUES(attack), 
            defense=VALUES(defense), 
            speed=VALUES(speed), 
            gk=VALUES(gk)
        """, (player_id, chat_id, thread_id, attack, defense, speed, gk))
    conn.commit()
    conn.close()

def set_player_core(player_id, chat_id, thread_id, is_core):
    """Set core status for a player in a chat"""
    conn = get_connection()
    cursor = conn.cursor()
    # Ensure stats record exists first (it should if player is being managed)
    # We use INSERT ON DUPLICATE in case stats don't exist yet but usually they do
    # We maintain default 50 for stats if creating new
    cursor.execute("""
    INSERT INTO player_stats (player_id, chat_id, thread_id, is_core) 
    VALUES (%s, %s, %s, %s) 
    ON DUPLICATE KEY UPDATE is_core = VALUES(is_core)
    """, (player_id, chat_id, thread_id, int(is_core)))
    conn.commit()
    conn.close()

def get_core_players(chat_id, thread_id):
    """Get list of core players for chat"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.user_id, p.name 
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.id
        WHERE ps.chat_id = %s AND ps.thread_id = %s AND ps.is_core = 1
    """, (chat_id, thread_id))
    res = cursor.fetchall()
    conn.close()
    return res

def get_player_avg_points(player_id, chat_id, thread_id=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT AVG(h.points) 
        FROM match_history h
        JOIN matches m ON h.match_id = m.id
        WHERE h.player_id = %s AND m.chat_id = %s AND m.thread_id = %s
    """, (player_id, chat_id, thread_id))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res and res[0] is not None else 0

def clear_draw_votes(chat_id, thread_id=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM draw_votes WHERE chat_id = %s AND thread_id = %s", (chat_id, thread_id))
    conn.commit()
    conn.close()

def add_draw_vote(chat_id, thread_id, variant_id, voter_id):
    conn = get_connection()
    cursor = conn.cursor()
    # One vote per user regardless of variant
    cursor.execute("DELETE FROM draw_votes WHERE chat_id = %s AND thread_id = %s AND voter_id = %s", (chat_id, thread_id, voter_id))
    cursor.execute("INSERT INTO draw_votes (chat_id, thread_id, variant_id, voter_id) VALUES (%s, %s, %s, %s)", (chat_id, thread_id, variant_id, voter_id))
    conn.commit()
    conn.close()

def get_draw_votes_count(chat_id, thread_id, variant_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM draw_votes WHERE chat_id = %s AND thread_id = %s AND variant_id = %s", (chat_id, thread_id, variant_id))
    res = cursor.fetchone()
    conn.close()
    return res[0]

def get_all_variant_votes(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT variant_id, COUNT(*) as vote_count, MIN(vote_time) as first_vote
        FROM draw_votes
        WHERE chat_id = %s AND thread_id = %s
        GROUP BY variant_id
        ORDER BY vote_count DESC
    """, (chat_id, thread_id))
    res = cursor.fetchall() # list of (variant_id, count, first_vote_time)
    conn.close()
    return res

def get_draw_winner(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT variant_id, COUNT(*) as vote_count, MAX(vote_time) as last_vote
        FROM draw_votes
        WHERE chat_id = %s AND thread_id = %s
        GROUP BY variant_id
        ORDER BY vote_count DESC, last_vote ASC
        LIMIT 1
    """, (chat_id, thread_id))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def set_draft_state(chat_id, thread_id, data):
    conn = get_connection()
    cursor = conn.cursor()
    json_data = json.dumps(data)
    cursor.execute("""
        INSERT INTO draft_state (chat_id, thread_id, state_data) 
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE state_data = %s
    """, (chat_id, thread_id, json_data, json_data))
    conn.commit()
    conn.close()

def get_draft_state(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT state_data FROM draft_state WHERE chat_id = %s AND thread_id = %s", (chat_id, thread_id))
    res = cursor.fetchone()
    conn.close()
    if res:
        return json.loads(res[0])
    return None

def clear_draft_state(chat_id, thread_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM draft_state WHERE chat_id = %s AND thread_id = %s", (chat_id, thread_id))
    conn.commit()
    conn.close()

def create_match(chat_id, thread_id, skill_level, score, match_date=None, championship_name=None):
    conn = get_connection()
    cursor = conn.cursor()
    if match_date:
        cursor.execute("INSERT INTO matches (chat_id, thread_id, skill_level, score, match_date, championship_name) VALUES (%s, %s, %s, %s, %s, %s)", (chat_id, thread_id, skill_level, score, match_date, championship_name))
    else:
        cursor.execute("INSERT INTO matches (chat_id, thread_id, skill_level, score, championship_name) VALUES (%s, %s, %s, %s, %s)", (chat_id, thread_id, skill_level, score, championship_name))
    match_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return match_id

def get_season_match_number(chat_id, thread_id, match_id=None):
    """Get the match number within the current season for this chat/thread.
    
    If match_id is provided, returns the number for that specific match.
    Otherwise, returns the count of all matches in the current season.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get season dates from settings
    settings = get_match_settings(chat_id, thread_id)
    season_start = settings.get('season_start')
    season_end = settings.get('season_end')
    
    # Build date filter
    date_filter = ""
    params = [chat_id, thread_id]
    
    if season_start and season_start != "—":
        date_filter += " AND DATE(match_date) >= %s"
        params.append(season_start)
    
    if season_end and season_end != "—":
        date_filter += " AND DATE(match_date) <= %s"
        params.append(season_end)
    
    if match_id:
        # Count matches before this one (including it)
        cursor.execute(f"""
            SELECT COUNT(*) FROM matches 
            WHERE chat_id = %s AND thread_id = %s AND id <= %s {date_filter}
        """, params[:2] + [match_id] + params[2:])
    else:
        # Count all matches in season
        cursor.execute(f"""
            SELECT COUNT(*) FROM matches 
            WHERE chat_id = %s AND thread_id = %s {date_filter}
        """, params)
    
    count = cursor.fetchone()[0]
    conn.close()
    return count

def save_player_rating(match_id, player_id, points, team, is_best_defender=0, goals=0, autogoals=0, is_captain=0, yellow_cards=0, red_cards=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO match_history (match_id, player_id, points, team, best_defender, goals, autogoals, is_captain, yellow_cards, red_cards)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            points = GREATEST(points, VALUES(points)),
            best_defender = GREATEST(best_defender, VALUES(best_defender)),
            goals = goals + VALUES(goals),
            autogoals = autogoals + VALUES(autogoals),
            is_captain = GREATEST(is_captain, VALUES(is_captain)),
            yellow_cards = yellow_cards + VALUES(yellow_cards),
            red_cards = red_cards + VALUES(red_cards)
    """, (match_id, player_id, points, team, is_best_defender, goals, autogoals, is_captain, yellow_cards, red_cards))
    conn.commit()
    conn.close()

def get_match_player_count(match_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT player_id) FROM match_history WHERE match_id = %s", (match_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def update_payment_status(player_id, chat_id, thread_id, status):
    """Update payment status for a player in a specific registration"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE registrations 
        SET is_paid = %s, updated_at = CURRENT_TIMESTAMP 
        WHERE player_id = %s AND chat_id = %s AND thread_id = %s
    """, (status, player_id, chat_id, thread_id))
    conn.commit()
    conn.close()

# --- MATCH EVENTS ---

def add_match_event(match_history_id, event_type, minute=None, assist_player_id=None):
    """Add a match event (goal, autogoal, yellow_card, red_card)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO match_events (match_history_id, event_type, minute, assist_player_id)
        VALUES (%s, %s, %s, %s)
    """, (match_history_id, event_type, minute, assist_player_id))
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return event_id

def update_match_event_assist(event_id, assist_player_id):
    """Update assist_player_id for a match event"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE match_events SET assist_player_id = %s WHERE id = %s
    """, (assist_player_id, event_id))
    conn.commit()
    conn.close()

def mark_event_as_penalty(event_id):
    """Mark a match event as a penalty goal"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE match_events SET is_penalty = 1, assist_player_id = NULL WHERE id = %s", (event_id,))
    conn.commit()
    conn.close()

def save_assist(match_id, player_id, team='Unknown'):
    """Increment assist count for player in match_history"""
    conn = get_connection()
    cursor = conn.cursor()
    # Ensure match_history record exists (it should, but safety first)
    # We assume player is already in match_history (from registration/team setup), 
    # but if not, we need to insert. 
    # Ideally assists come from players who played.
    
    cursor.execute("""
        INSERT INTO match_history (match_id, player_id, points, team, assists)
        VALUES (%s, %s, 0, %s, 1)
        ON DUPLICATE KEY UPDATE 
            assists = assists + 1
    """, (match_id, player_id, team))
    conn.commit()
    conn.close()

def get_match_events(match_history_id):
    """Get all events for a match history record"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, event_type, minute FROM match_events
        WHERE match_history_id = %s ORDER BY minute, id
    """, (match_history_id,))
    events = cursor.fetchall()
    conn.close()
    return events

def delete_match_event(event_id):
    """Delete a match event"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM match_events WHERE id = %s", (event_id,))
    conn.commit()
    conn.close()

def get_match_history_id(match_id, player_id):
    """Get match_history record ID for a player in a match"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM match_history WHERE match_id = %s AND player_id = %s
    """, (match_id, player_id))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_match_by_criteria(chat_id, thread_id, match_date, championship_name):
    """Find existing match by date/time and championship"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    # Match date in DB is TIMESTAMP. We check if there's a match within 5 minutes of target time to avoid exact second mismatch issues?
    # Or strict equality? User said "on this date and time".
    # Let's try flexible matching +/- 15 mins for safety, since we rely on settings time which might align with match_date logic in code
    
    # Actually, process_match_score calculates match_date strictly based on settings. 
    # If settings haven't changed, the calculated time will be identical.
    
    query = """
    SELECT * FROM matches 
    WHERE chat_id = %s AND thread_id = %s 
    AND (
        (championship_name IS NULL AND %s IS NULL) OR championship_name = %s
    )
    AND ABS(TIMESTAMPDIFF(MINUTE, match_date, %s)) < 5
    LIMIT 1
    """
    cursor.execute(query, (chat_id, thread_id, championship_name, championship_name, match_date))
    match = cursor.fetchone()
    conn.close()
    return match

def clear_match_stats(match_id):
    """Clear all stats (history, events) for a match but keep the match record"""
    conn = get_connection()
    cursor = conn.cursor()
    # match_events linked to match_history, match_history linked to matches.
    # ON DELETE CASCADE is set for history->matches. 
    # But we want to keep match record.
    # So we delete from match_history and cascading will delete events.
    cursor.execute("DELETE FROM match_history WHERE match_id = %s", (match_id,))
    conn.commit()
    conn.close()

def update_match_score(match_id, score, skill_level, championship_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE matches 
        SET score = %s, skill_level = %s, championship_name = %s 
        WHERE id = %s
    """, (score, skill_level, championship_name, match_id))
    conn.commit()
    conn.close()

def update_match_event_assist(event_id, assist_player_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE match_events SET assist_player_id = %s WHERE id = %s", (assist_player_id, event_id))
    conn.commit()
    conn.close()
