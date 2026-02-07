from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types
import translations as tr

def get_registration_kb(player_count=0, lang_id=1, lat=None, lon=None, chat_id=None, thread_id=None, bot_username=None):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("reg_att", lang_id), callback_data="reg_att")
    builder.button(text=tr.t("reg_def", lang_id), callback_data="reg_def")
    builder.button(text=tr.t("reg_gk", lang_id), callback_data="reg_gk")
    builder.button(text=tr.t("btn_im_not_coming", lang_id), callback_data="not_coming")
    
    # URL button for admin manage
    if bot_username and chat_id:
        tid_part = f"_{thread_id}" if thread_id else "_0"
        url = f"https://t.me/{bot_username}?start=admin_quick_{chat_id}{tid_part}"
        builder.button(text=tr.t("reg_add_legionnaire", lang_id), url=url)
    else:
        # Fallback if no username passed (should not happen if updated correctly)
        builder.button(text=tr.t("reg_add_legionnaire", lang_id), callback_data="admin_add_legionnaire")
    
    if player_count >= 2:
        builder.button(text=tr.t("reg_draw", lang_id), callback_data="admin_draw")
    builder.adjust(2)
    return builder.as_markup()
def get_admin_main_kb(chat_id=None, thread_id=None, lang_id=1):
    builder = InlineKeyboardBuilder()
    
    suffix = ""
    if chat_id:
        suffix = f"_{chat_id}_{thread_id}"

    builder.button(text=tr.t("btn_language", lang_id), callback_data=f"edit_bot_language")
    builder.button(text=tr.t("admin_player_mgmt", lang_id), callback_data=f"admin_player_mgmt{suffix}")
    builder.button(text=tr.t("admin_match_settings", lang_id), callback_data=f"admin_match_settings{suffix}")
    builder.button(text=tr.t("admin_payment", lang_id), callback_data=f"admin_payment{suffix}")
    builder.button(text=tr.t("admin_bot_settings", lang_id), callback_data=f"admin_bot_settings{suffix}")
    builder.button(text=tr.t("admin_cancel_game", lang_id), callback_data=f"admin_clear{suffix}")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_settings_kb(chat_id, thread_id, lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("setting_players", lang_id), callback_data="edit_count_start")
    builder.button(text=tr.t("setting_skill_level", lang_id), callback_data="edit_skill_start")
    builder.button(text=tr.t("setting_age", lang_id), callback_data="edit_age_start")
    builder.button(text=tr.t("setting_gender", lang_id), callback_data="edit_gender_start")
    builder.button(text=tr.t("setting_venue_type", lang_id), callback_data="edit_venue_start")
    builder.button(text=tr.t("setting_location", lang_id), callback_data="edit_location_start")
    builder.button(text=tr.t("setting_match_times", lang_id), callback_data="edit_time_group")
    builder.button(text=tr.t("setting_season", lang_id), callback_data="edit_season_group")
    builder.button(text=tr.t("setting_championship_name", lang_id), callback_data="edit_championship_start")
    builder.button(text=tr.t("btn_done", lang_id), callback_data="process_settings_done")
    builder.adjust(2)
    return builder.as_markup()

def get_admin_payment_kb(chat_id, thread_id, lang_id=1, settings=None):
    builder = InlineKeyboardBuilder()
    # Change direct edit to submenu
    builder.button(text=tr.t("btn_cost_settings", lang_id), callback_data="open_cost_settings")
    
    # Reminders toggle
    rem_before = "🔔" if settings.get('remind_before_game') else "🔕"
    rem_after = "🔔" if settings.get('remind_after_game') else "🔕"
    
    builder.button(text=f"{rem_before} {tr.t('remind_before_game', lang_id)}", callback_data="toggle_remind_before")
    builder.button(text=f"{rem_after} {tr.t('remind_after_game', lang_id)}", callback_data="toggle_remind_after")
    
    # Admin confirmation toggle
    req_confirm = "✅" if settings.get('require_payment_confirmation') else "❌"
    builder.button(text=f"{req_confirm} {tr.t('require_admin_confirmation', lang_id)}", callback_data="toggle_payment_confirmation")
    
    # Payment Details button
    builder.button(text=tr.t("setting_payment_details", lang_id), callback_data="admin_edit_pay_details")
    
    builder.button(text=tr.t("btn_back", lang_id), callback_data="admin_main_menu_back")
    builder.adjust(1)
    return builder.as_markup()

def get_cost_settings_kb(chat_id, thread_id, lang_id=1, settings=None):
    """Submenu for Price Settings (Amount + Calculation Mode)"""
    import database as db
    builder = InlineKeyboardBuilder()
    
    if settings is None:
        settings = db.get_match_settings(chat_id, thread_id)
        
    cost = settings.get('cost', 0)
    cost_mode = settings.get('cost_mode', 'fixed_player')
    
    # 1. Edit Amount Button
    builder.button(text=f"✏️ {tr.t('btn_edit_cost', lang_id)}: {cost}", callback_data="edit_cost_start_payment")
    
    # 2. Mode Radios
    for mode in ['fixed_player', 'fixed_game']:
        radio = "🔘" if cost_mode == mode else "⚪"
        mode_text = tr.t(f'cost_mode_{mode}', lang_id)
        builder.button(text=f"{radio} {mode_text}", callback_data=f"set_cost_mode_price_{mode}_{chat_id}_{thread_id}")

    builder.button(text=tr.t("btn_back", lang_id), callback_data="admin_payment_menu_back")
    builder.adjust(1)
    return builder.as_markup()

def get_payment_reminder_kb(players, require_confirmation=False, lang_id=1):
    """
    Keyboard for payment reminder message after match score.
    - Always includes "I Paid" button
    - If require_confirmation is True, adds admin confirmation buttons for each player
    """
    builder = InlineKeyboardBuilder()
    
    # Always add "I Paid" button for players
    builder.button(text=tr.t("btn_i_paid", lang_id), callback_data="pay_self_reminder")
    
    # Check if any unpaid remaining to show "Paid All" (Admin feature)
    any_unpaid = any(p[8] != 2 for p in players)
    if any_unpaid:
         builder.button(text=tr.t("btn_paid_all", lang_id), callback_data="confirm_payment_all")
    
    # If admin confirmation required, add buttons for each player
    if require_confirmation:
        for p in players:
            pid = p[0]
            name = p[2]
            is_paid = p[8]
            
            # Button text based on status:
            # 0 (Unpaid) -> ❌ Name
            # 1 (Claimed) -> 💰 Name
            # 2 (Confirmed) -> ✅ Name
            
            icon = "❌"
            if is_paid == 1:
                icon = "💰"
            elif is_paid == 2:
                icon = "✅"
                
            builder.button(text=f"{icon} {name}", callback_data=f"confirm_payment_{pid}")
    else:
        # If no confirmation required, add buttons for legionnaires (no user_id)
        # Regular players use the single "I Paid" button
        for p in players:
            pid = p[0]
            user_id = p[1]
            name = p[2]
            is_paid = p[8]
            
            if not user_id and is_paid == 0:
                 builder.button(text=f"🪙 {name}", callback_data=f"pay_legionnaire_{pid}")
    
    builder.adjust(1)
    return builder.as_markup()


def get_admin_bot_settings_kb(chat_id, thread_id, lang_id=1, settings=None):
    import database as db
    builder = InlineKeyboardBuilder()
    
    # Get current settings if not passed
    if settings is None:
        settings = db.get_match_settings(chat_id, thread_id)
    
    # Language setting
    builder.button(text=tr.t("choose_language", lang_id), callback_data="edit_bot_lang")
    
    # Match event tracking settings with checkmarks
    track_goals = settings.get('track_goals', 1)
    track_goal_times = settings.get('track_goal_times', 0)
    track_cards = settings.get('track_cards', 0)
    track_card_times = settings.get('track_card_times', 0)
    
    check = "✅" if track_goals else "❌"
    builder.button(text=f"{check} {tr.t('setting_track_goals', lang_id)}", callback_data=f"toggle_track_goals_{chat_id}_{thread_id}")
    
    check = "✅" if track_goal_times else "❌"
    builder.button(text=f"{check} {tr.t('setting_track_goal_times', lang_id)}", callback_data=f"toggle_track_goal_times_{chat_id}_{thread_id}")
    
    check = "✅" if track_cards else "❌"
    builder.button(text=f"{check} {tr.t('setting_track_cards', lang_id)}", callback_data=f"toggle_track_cards_{chat_id}_{thread_id}")
    
    check = "✅" if track_card_times else "❌"
    builder.button(text=f"{check} {tr.t('setting_track_card_times', lang_id)}", callback_data=f"toggle_track_card_times_{chat_id}_{thread_id}")

    check = "✅" if settings.get('track_assists', 0) else "❌"
    builder.button(text=f"{check} {tr.t('setting_track_assists', lang_id)}", callback_data=f"toggle_track_assists_{chat_id}_{thread_id}")
    
    # Rating system submenu button
    builder.button(text=f"⭐ {tr.t('setting_rating_mode', lang_id)}", callback_data=f"rating_settings_menu_{chat_id}_{thread_id}")
    
    # Payment system submenu button
    builder.button(text=f"💰 {tr.t('setting_payment_mode', lang_id)}", callback_data=f"payment_settings_menu_{chat_id}_{thread_id}")
    
    builder.button(text=tr.t("btn_back", lang_id), callback_data="admin_main_menu_back")
    builder.adjust(1)
    return builder.as_markup()

def get_payment_settings_kb(chat_id, thread_id, lang_id=1, settings=None):
    """Payment system submenu"""
    import database as db
    builder = InlineKeyboardBuilder()
    
    # Get current settings if not passed
    if settings is None:
        settings = db.get_match_settings(chat_id, thread_id)
    
    cost_mode = settings.get('cost_mode', 'fixed_player')
    
    # Cost mode selector (radio buttons)
    for mode in ['fixed_player', 'fixed_game']:
        radio = "🔘" if cost_mode == mode else "⚪"
        mode_text = tr.t(f'cost_mode_{mode}', lang_id)
        builder.button(text=f"{radio} {mode_text}", callback_data=f"set_cost_mode_{mode}_{chat_id}_{thread_id}")
    
    # Payment details edit button
    builder.button(text=f"💳 {tr.t('setting_payment_details', lang_id)}", callback_data=f"edit_payment_details_{chat_id}_{thread_id}")
    
    builder.button(text=tr.t("btn_back", lang_id), callback_data=f"payment_settings_back_{chat_id}_{thread_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_rating_settings_kb(chat_id, thread_id, lang_id=1, settings=None):
    """Rating system submenu"""
    import database as db
    builder = InlineKeyboardBuilder()
    
    # Get current settings if not passed
    if settings is None:
        settings = db.get_match_settings(chat_id, thread_id)
    
    rating_mode = settings.get('rating_mode', 'ranked')
    track_best_defender = settings.get('track_best_defender', 1)
    
    # Rating mode selector (radio buttons)
    for mode in ['ranked', 'top3', 'scale5', 'disabled']:
        radio = "🔘" if rating_mode == mode else "⚪"
        mode_text = tr.t(f'rating_mode_{mode}', lang_id)
        builder.button(text=f"{radio} {mode_text}", callback_data=f"set_rating_mode_{mode}_{chat_id}_{thread_id}")
    
    # Best defender toggle
    check = "✅" if track_best_defender else "❌"
    builder.button(text=f"{check} {tr.t('setting_track_best_defender', lang_id)}", callback_data=f"toggle_track_best_defender_{chat_id}_{thread_id}")
    
    builder.button(text=tr.t("btn_back", lang_id), callback_data=f"rating_settings_back_{chat_id}_{thread_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_language_selection_kb(chat_id, thread_id):
    import database as db
    builder = InlineKeyboardBuilder()
    languages = db.get_languages()
    for lang in languages:
        emoji = lang.get('emoji', '')
        text = f"{emoji} {lang['name']}" if emoji else lang['name']
        builder.button(text=text, callback_data=f"set_lang_{lang['id']}_{chat_id}_{thread_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_admin_time_settings_kb(chat_id, thread_id, lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("btn_timezone", lang_id), callback_data="edit_timezone_start")
    builder.button(text=tr.t("btn_match_time", lang_id), callback_data="edit_times_start")
    builder.button(text=tr.t("btn_back", lang_id), callback_data="admin_match_settings")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_season_settings_kb(chat_id, thread_id, lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("btn_season_start", lang_id), callback_data="edit_season_start_cb")
    builder.button(text=tr.t("btn_season_end", lang_id), callback_data="edit_season_end_cb")
    builder.button(text=tr.t("btn_back", lang_id), callback_data="admin_match_settings")
    builder.adjust(1)
    return builder.as_markup()

def get_day_selection_kb(lang_id=1):
    builder = InlineKeyboardBuilder()
    days = [("mon", "wd_mon"), ("tue", "wd_tue"), ("wed", "wd_wed"), ("thu", "wd_thu"), ("fri", "wd_fri"), ("sat", "wd_sat"), ("sun", "wd_sun")]
    for val, key in days:
        builder.button(text=tr.t(key, lang_id), callback_data=f"set_day_{val}")
    builder.adjust(4)
    return builder.as_markup()

def get_hour_selection_kb():
    builder = InlineKeyboardBuilder()
    for h in range(24):
        builder.button(text=f"{h:02d}:00", callback_data=f"set_hour_{h}")
    builder.adjust(6)
    return builder.as_markup()

def get_min_selection_kb():
    builder = InlineKeyboardBuilder()
    for m in ["00", "15", "30", "45"]:
        builder.button(text=f":{m}", callback_data=f"set_min_{m}")
    builder.adjust(2)
    return builder.as_markup()

def get_language_kb():
    """Dynamic language selection keyboard"""
    import database as db
    builder = InlineKeyboardBuilder()
    languages = db.get_languages()
    for lang in languages:
        emoji = lang.get('emoji', '')
        text = f"{emoji} {lang['name']}" if emoji else lang['name']
        builder.button(text=text, callback_data=f"lang_{lang['id']}")
    builder.adjust(2)
    return builder.as_markup()

def get_admin_player_mgmt_kb(chat_id, thread_id, lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("admin_mgmt_regular", lang_id), callback_data=f"admin_mgmt_regular_{chat_id}_{thread_id}")
    builder.button(text=tr.t("admin_mgmt_legionnaires", lang_id), callback_data=f"admin_list_legionnaires_{chat_id}_{thread_id}")
    builder.button(text=tr.t("admin_core_team", lang_id), callback_data=f"admin_core_team_{chat_id}_{thread_id}")
    builder.button(text=tr.t("btn_back", lang_id), callback_data=f"admin_main_menu_back_{chat_id}_{thread_id}") 
    builder.adjust(1)
    return builder.as_markup()

def get_core_team_menu_kb(chat_id, thread_id, lang_id=1, settings=None):
    """Core Team submenu with mode toggle and player selection"""
    import database as db
    if settings is None:
        settings = db.get_match_settings(chat_id, thread_id)
    
    builder = InlineKeyboardBuilder()
    
    # Mode toggle
    mode_active = settings.get('core_team_mode', 0)
    mode_icon = "✅" if mode_active else "❌"
    mode_text = tr.t("core_mode_active", lang_id) if mode_active else tr.t("core_mode_inactive", lang_id)
    builder.button(text=f"{mode_icon} {tr.t('btn_core_team_mode', lang_id)}: {mode_text}", callback_data=f"toggle_core_mode_{chat_id}_{thread_id}")
    
    # Player selection (only show if mode is active)
    if mode_active:
        builder.button(text=tr.t("btn_select_core_players", lang_id), callback_data=f"select_core_players_{chat_id}_{thread_id}")
    
    builder.button(text=tr.t("btn_back", lang_id), callback_data=f"admin_player_mgmt_{chat_id}_{thread_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_core_players_selection_kb(chat_id, thread_id, lang_id=1):
    """Keyboard for bulk Core Team player selection"""
    import database as db
    
    builder = InlineKeyboardBuilder()
    
    # Get all players (regular players + legionnaires with stats)
    all_players = db.get_all_players_with_stats(chat_id, thread_id)
    
    for p in all_players:
        pid = p[0]
        name = p[2]
        is_core = p[7] if len(p) > 7 else 0
        
        icon = "✅" if is_core else "⚪"
        builder.button(text=f"{icon} {name}", callback_data=f"toggle_player_core_{pid}_{chat_id}_{thread_id}")
    
    builder.button(text=tr.t("btn_back", lang_id), callback_data=f"admin_core_team_{chat_id}_{thread_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_stat_edit_kb(lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("stat_attack", lang_id), callback_data="stat_attack")
    builder.button(text=tr.t("stat_defense", lang_id), callback_data="stat_defense")
    builder.button(text=tr.t("stat_speed", lang_id), callback_data="stat_speed")
    builder.button(text=tr.t("stat_gk", lang_id), callback_data="stat_gk")
    builder.adjust(2)
    return builder.as_markup()

def get_players_list_kb(players):
    builder = InlineKeyboardBuilder()
    for p in players:
        # p[0] is player_id, p[2] is name
        builder.button(text=f"⚙️ {p[2]}", callback_data=f"edit_p_{p[0]}")
    builder.adjust(2)
    return builder.as_markup()

def get_legionnaire_list_kb(players, action_prefix="sel_myth_", create_callback="create_new_legionnaire", back_callback="admin_player_mgmt", lang_id=1):
    builder = InlineKeyboardBuilder()
    for p in players:
        # p[0] is id, p[1] is name
        builder.button(text=f"🎖 {p[1]}", callback_data=f"{action_prefix}{p[0]}")
    builder.button(text=tr.t("create_new", lang_id), callback_data=create_callback)
    builder.button(text=tr.t("btn_back", lang_id), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()

def get_quick_manage_kb(chat_id, thread_id, lang_id=1):
    builder = InlineKeyboardBuilder()
    # Add Legionnaire -> Reuse logic (calls admin_list_legionnaires but for specific Quick Action context)
    # We will use "admin_quick_add_leg_{cid}_{tid}" to distinguish back handling?
    # Or just reuse existing handlers if possible.
    # User asked for "Add Legionnaire" button functionality to remain same (list of legionnaires).
    # And "Remove Player" button to show list of players to remove.
    
    # We need explicit callbacks
    builder.button(text=tr.t("admin_legionnaires", lang_id), callback_data=f"admin_quick_add_leg_{chat_id}_{thread_id}")
    builder.button(text=tr.t("admin_add_real_player", lang_id), callback_data=f"admin_quick_add_real_{chat_id}_{thread_id}")
    builder.button(text=tr.t("reg_cancel", lang_id), callback_data=f"admin_quick_rem_list_{chat_id}_{thread_id}")
    
    builder.adjust(1)
    return builder.as_markup()

def get_remove_player_kb(players, chat_id, thread_id, lang_id=1):
    builder = InlineKeyboardBuilder()
    for p in players:
        # p[0]=id, p[2]=name, p[9]=status
        # Show status emoji?
        status_icon = ""
        if p[9] == 'queue': status_icon = "🕒 "
        elif p[9] == 'pending_confirm': status_icon = "⏳ "
        
        builder.button(text=f"❌ {status_icon}{p[2]}", callback_data=f"admin_force_rem_{p[0]}_{chat_id}_{thread_id}")
        
    builder.button(text=tr.t("btn_back", lang_id), callback_data=f"admin_quick_manage_{chat_id}_{thread_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_real_players_list_kb(players, chat_id, thread_id, lang_id=1, back_callback="admin_player_mgmt"):
    builder = InlineKeyboardBuilder()
    for p in players:
        # p[0] is id, p[1] is user_id, p[2] is name (from get_all_players_with_stats)
        # p[8] is telegram_name (added recently)
        name = p[2]
        if len(p) > 8 and p[8] and p[2] != p[8]:
             name = f"{p[2]} ({p[8]})"
        
        builder.button(text=f"👤 {name}", callback_data=f"admin_real_select_{p[0]}_{chat_id}_{thread_id}")
    builder.button(text=tr.t("btn_back", lang_id), callback_data=back_callback)
    builder.adjust(2)
    return builder.as_markup()


def get_chat_players_kb(players, lang_id=1):
    builder = InlineKeyboardBuilder()
    for p in players:
        # p[0]=id, p[1]=tg_name, p[2]=display_name
        # name = p[2] if p[2] else p[1]
        if p[2] and p[2] != p[1]:
            name = f"{p[2]} ({p[1]})"
        else:
            name = p[2] if p[2] else p[1]
            
        builder.button(text=f"⚙️ {name}", callback_data=f"sel_reg_{p[0]}")
        
    builder.button(text=tr.t("btn_back", lang_id), callback_data="admin_player_mgmt")
    builder.adjust(1)
    return builder.as_markup()

def get_draw_options_kb(lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("draw_opt_all", lang_id), callback_data="draw_mode_all")
    builder.button(text=tr.t("draw_opt_gk", lang_id), callback_data="draw_mode_gk")
    builder.button(text=tr.t("draw_opt_none", lang_id), callback_data="draw_mode_none")
    builder.adjust(1)
    return builder.as_markup()

def get_skill_level_kb(lang_id=1):
    import database as db
    builder = InlineKeyboardBuilder()
    items = db.get_skill_levels(lang_id)
    for i in items:
        # Callback format: skill_ID
        builder.button(text=i['label'], callback_data=f"skill_{i['id']}")
    builder.adjust(1)
    return builder.as_markup()

def get_age_group_kb(lang_id=1):
    import database as db
    builder = InlineKeyboardBuilder()
    items = db.get_age_groups(lang_id)
    for i in items:
        builder.button(text=i['label'], callback_data=f"age_{i['id']}")
    builder.adjust(2)
    return builder.as_markup()

def get_gender_kb(lang_id=1):
    import database as db
    builder = InlineKeyboardBuilder()
    items = db.get_genders(lang_id)
    for i in items:
        builder.button(text=i['label'], callback_data=f"gender_{i['id']}")
    builder.adjust(2)
    return builder.as_markup()

def get_venue_type_kb(lang_id=1):
    import database as db
    builder = InlineKeyboardBuilder()
    items = db.get_venue_types(lang_id)
    for i in items:
        builder.button(text=i['label'], callback_data=f"venue_{i['id']}")
    builder.adjust(1)
    return builder.as_markup()

# ... language_kb skipped (dynamic) ...

def get_draw_count_kb(lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("draw_1_auto", lang_id), callback_data="draw_count_1")
    builder.button(text=tr.t("draw_3_auto", lang_id), callback_data="draw_count_3")
    builder.button(text=tr.t("draw_manual", lang_id), callback_data="draw_count_manual")
    builder.button(text=tr.t("draw_contest", lang_id), callback_data="draw_count_contest")
    builder.adjust(2, 2)
    return builder.as_markup()

def get_pairs_start_kb(bot_username, chat_id, thread_id, lang_id=1):
    builder = InlineKeyboardBuilder()
    url = f"https://t.me/{bot_username}?start=pairs_{chat_id}_{thread_id}"
    builder.button(text=tr.t("pairs_propose", lang_id), url=url)
    builder.button(text=tr.t("pairs_best", lang_id), callback_data="contest_finish_best")
    builder.adjust(1)
    return builder.as_markup()

def get_vote_kb(variant_id, votes=0, lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{tr.t('vote_this', lang_id)} ({votes})", callback_data=f"vote_{variant_id}")
    return builder.as_markup()

def get_ask_captains_kb(lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("cap_yes", lang_id), callback_data="cap_ask_yes")
    builder.button(text=tr.t("cap_no", lang_id), callback_data="cap_ask_no")
    builder.adjust(2)
    return builder.as_markup()

def get_players_selection_kb(players, selected_ids=[], lang_id=1):
    builder = InlineKeyboardBuilder()
    for p in players:
        # p[0] is id, p[2] is name
        is_sel = p[0] in selected_ids
        prefix = "⭐️ " if is_sel else ""
        builder.button(text=f"{prefix}{p[2]}", callback_data=f"cap_sel_{p[0]}")
    
    if len(selected_ids) == 2:
        builder.button(text=tr.t("cap_done", lang_id), callback_data="cap_done")
    
    builder.adjust(2)
    return builder.as_markup()

def get_draft_kb(available_players):
    builder = InlineKeyboardBuilder()
    for p in available_players:
        # p is dict: {'id': ..., 'name': ...}
        builder.button(text=p['name'], callback_data=f"draft_pick_{p['id']}")
    builder.adjust(2)
    return builder.as_markup()

def get_start_rating_kb(team_id, lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("rate_start", lang_id), callback_data=f"rate_start_{team_id}")
    return builder.as_markup()

def get_rating_pick_kb(players):
    builder = InlineKeyboardBuilder()
    for p in players:
        builder.button(text=p['name'], callback_data=f"rate_pick_{p['id']}")
    builder.adjust(2)
    return builder.as_markup()

def get_defender_pick_kb(players):
    builder = InlineKeyboardBuilder()
    for p in players:
        builder.button(text=p['name'], callback_data=f"def_pick_{p['id']}")
    builder.adjust(2)
    return builder.as_markup()

def get_score_entry_kb(lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("enter_score", lang_id), callback_data="match_enter_score")
    return builder.as_markup()

def get_edit_stats_kb(players):
    builder = InlineKeyboardBuilder()
    for p in players:
        # p[0]=id, p[1]=name, p[2]=att, p[3]=def, p[4]=spd, p[5]=gk
        att = p[2] if p[2] is not None else 50
        df = p[3] if p[3] is not None else 50
        spd = p[4] if p[4] is not None else 50
        gk = p[5] if p[5] is not None else 50
        builder.button(text=f"{p[1]} ({att}/{df}/{spd}/{gk})", callback_data=f"edit_stats_{p[0]}")
    builder.adjust(1)
    return builder.as_markup()
def get_goal_scorer_kb(players, is_autogol_mode=False, lang_id=1):
    builder = InlineKeyboardBuilder()
    for p in players:
        builder.button(text=p['name'], callback_data=f"goal_pick_{p['id']}")
    
    ag_prefix = "✅ " if is_autogol_mode else ""
    builder.button(text=f"{ag_prefix}{tr.t('autogol', lang_id)}", callback_data="goal_autogol_toggle")
    
    builder.adjust(2)
    return builder.as_markup()

def get_weekday_kb(lang_id=1):
    builder = InlineKeyboardBuilder()
    days = [
        (tr.t("wd_mon", lang_id), "mon"), (tr.t("wd_tue", lang_id), "tue"), 
        (tr.t("wd_wed", lang_id), "wed"), (tr.t("wd_thu", lang_id), "thu"),
        (tr.t("wd_fri", lang_id), "fri"), (tr.t("wd_sat", lang_id), "sat"), 
        (tr.t("wd_sun", lang_id), "sun")
    ]
    for label, val in days:
        builder.button(text=label, callback_data=f"time_day_{val}")
    builder.adjust(4)
    return builder.as_markup()

def get_hours_kb():
    builder = InlineKeyboardBuilder()
    for h in range(24):
        builder.button(text=f"{h:02d}:00", callback_data=f"time_hour_{h}")
    builder.adjust(4)
    return builder.as_markup()

def get_minutes_kb():
    builder = InlineKeyboardBuilder()
    for m in [0, 15, 30, 45]:
        builder.button(text=f":{m:02d}", callback_data=f"time_min_{m}")
    builder.adjust(2)
    return builder.as_markup()

def get_timezone_kb():
    builder = InlineKeyboardBuilder()
    zones = ["GMT-1", "GMT+0", "GMT+1", "GMT+2", "GMT+3", "GMT+4", "GMT+5", "GMT+6", "GMT+7", "GMT+8", "GMT+9"]
    for z in zones:
        builder.button(text=z, callback_data=f"set_tz_{z}")
    builder.adjust(3)
    return builder.as_markup()

def get_months_kb(lang_id=1):
    builder = InlineKeyboardBuilder()
    months_keys = [
        ("mon_jan", 1), ("mon_feb", 2), ("mon_mar", 3), ("mon_apr", 4),
        ("mon_may", 5), ("mon_jun", 6), ("mon_jul", 7), ("mon_aug", 8),
        ("mon_sep", 9), ("mon_oct", 10), ("mon_nov", 11), ("mon_dec", 12)
    ]
    for key, val in months_keys:
        builder.button(text=tr.t(key, lang_id), callback_data=f"date_month_{val}")
    builder.adjust(3)
    return builder.as_markup()

def get_days_kb(month: int):
    builder = InlineKeyboardBuilder()
    # Simplified: 31 days for any month for UI ease, or calculate
    days_in_month = {1:31, 2:29, 3:31, 4:30, 5:31, 6:30, 7:31, 8:31, 9:30, 10:31, 11:30, 12:31}
    for d in range(1, days_in_month.get(month, 31) + 1):
        builder.button(text=str(d), callback_data=f"date_day_{d}")
    builder.adjust(7)
    return builder.as_markup()

def get_years_kb():
    builder = InlineKeyboardBuilder()
    import datetime
    curr_year = datetime.datetime.now().year
    builder.button(text=str(curr_year), callback_data=f"date_year_{curr_year}")
    builder.button(text=str(curr_year + 1), callback_data=f"date_year_{curr_year + 1}")
    builder.adjust(2)
    return builder.as_markup()

def get_pairs_builder_kb(players, selected_ids, selection_phase="left", can_proceed=False, lang_id=1):
    builder = InlineKeyboardBuilder()
    
    # List players
    for p in players:
        # p is dict: {'id': ..., 'name': ...}
        pid = p['id']
        name = p['name']
        
        is_sel = pid in selected_ids
        prefix = "✅ " if is_sel else "⬜ "
        role = f" ({p.get('position', '?')})"
        
        builder.button(text=f"{prefix}{name}{role}", callback_data=f"pairs_sel_{pid}")
        
    builder.adjust(1)
    
    # Control buttons
    if selection_phase == "left":
        label = tr.t("pairs_next", lang_id)
        cb = "pairs_next"
    else:
        label = tr.t("pairs_save", lang_id)
        cb = "pairs_save"

    if can_proceed:
        builder.button(text=label, callback_data=cb)
        
    return builder.as_markup()

# --- MATCH EVENTS KEYBOARDS ---

def get_goal_count_kb(player_id, match_id, event_type="goal", lang_id=1):
    """Keyboard for selecting goal count (0-5+)"""
    builder = InlineKeyboardBuilder()
    for i in range(6):
        builder.button(text=str(i), callback_data=f"event_count_{event_type}_{player_id}_{match_id}_{i}")
    builder.button(text=tr.t("btn_skip", lang_id), callback_data=f"event_count_{event_type}_{player_id}_{match_id}_0")
    builder.adjust(3)
    return builder.as_markup()

def get_minute_input_kb(player_id, match_id, event_type, event_num=1, lang_id=1, min_val=0):
    """Keyboard for entering minute (0-90)"""
    builder = InlineKeyboardBuilder()
    
    # Standard 5-min intervals, filtered
    minutes = range(5, 95, 5)
    
    for m in minutes:
        if m >= min_val:
            builder.button(text=str(m), callback_data=f"event_minute_{event_type}_{player_id}_{match_id}_{event_num}_{m}")
            
    # Add + / - buttons for adjusting? No, simpler to just have grid.
    # Maybe add "45+" and "90+"?
    
    builder.adjust(5)
    return builder.as_markup()

def get_card_type_kb(player_id, match_id, lang_id=1):
    """Keyboard for selecting card type"""
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("card_yellow", lang_id), callback_data=f"event_card_{player_id}_{match_id}_yellow_card")
    builder.button(text=tr.t("card_red", lang_id), callback_data=f"event_card_{player_id}_{match_id}_red_card")
    builder.adjust(2)
    return builder.as_markup()

def get_card_player_kb(players, match_id, lang_id=1):
    """Keyboard for selecting player to give card"""
    builder = InlineKeyboardBuilder()
    for p in players:
        # p[0] is player_id, p[2] is name
        builder.button(text=f"👤 {p[2]}", callback_data=f"event_card_player_{p[0]}_{match_id}")
    builder.button(text=tr.t("btn_done", lang_id), callback_data=f"event_cards_done_{match_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_player_goals_kb(players, match_id, event_type="goal", lang_id=1):
    """Keyboard for selecting player to enter goals"""
    builder = InlineKeyboardBuilder()
    for p in players:
        builder.button(text=f"⚽ {p[2]}", callback_data=f"event_player_{event_type}_{p[0]}_{match_id}")
    builder.button(text=tr.t("btn_done", lang_id), callback_data=f"event_goals_done_{match_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_assist_selection_kb(players, scorer_id, match_id, lang_id=1):
    """Keyboard for selecting player who assisted"""
    builder = InlineKeyboardBuilder()
    
    # List players excluding the scorer
    valid_assistants = [p for p in players if p['id'] != scorer_id]
    
    for p in valid_assistants:
        builder.button(text=f"👟 {p['name']}", callback_data=f"assist_pick_{p['id']}_{match_id}")
        
    builder.button(text=tr.t("btn_penalty", lang_id), callback_data=f"assist_penalty_{match_id}")
    builder.button(text=tr.t("no_assist", lang_id), callback_data=f"assist_none_{match_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_match_exists_kb(match_id, score, lang_id=1):
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("btn_overwrite", lang_id), callback_data=f"match_decision_overwrite_{match_id}_{score}")
    builder.button(text=tr.t("btn_create_new", lang_id), callback_data=f"match_decision_new_{match_id}_{score}")
    builder.button(text=tr.t("btn_cancel", lang_id), callback_data=f"match_decision_cancel")
    builder.adjust(1)
    return builder.as_markup()
