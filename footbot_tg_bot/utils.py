import random
import logging
import asyncio
import math
import re
from datetime import datetime, timedelta, timezone
from aiogram import types
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from init_bot import bot
import database as db
import keyboards as kb
import translations as tr
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions, TelegramObject

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

def escape_md(text):
    """Escapes markdown special characters for legacy Markdown mode"""
    if not text: return ""
    import re
    return re.sub(r'([*_{}\[\]\(\)`])', r'\\\1', str(text))

def h(text):
    """Escapes text for HTML mode"""
    import html
    return html.escape(str(text))

def extract_amount(s):
    """Safely extracts a float amount from a string (e.g., '7000 р' -> 7000.0)"""
    if not s or s == "—": return 0.0
    if isinstance(s, (int, float)): return float(s)
    # Use global re if imported, else local
    import re
    match = re.search(r'(\d+(?:[.,]\d+)?)', str(s))
    if match:
        return float(match.group(1).replace(',', '.'))
    return 0.0

def calculate_ovr(p, chat_id, thread_id, mode='all', use_history=False):
    # p[3]=attack, p[4]=defense, p[5]=speed, p[6]=gk, p[7]=position
    attack, defense, speed, gk, position = p[3], p[4], p[5], p[6], p[7]
    
    # 1. Base score from stats
    if mode == 'none':
        base = (attack + defense + speed) / 3
    elif mode == 'gk':
        base = gk * 2 if position == 'gk' else (attack + defense + speed) / 3
    else:
        if position == 'gk':
            base = gk * 2
        elif position == 'att':
            base = attack * 0.6 + speed * 0.4
        else:
            base = defense * 0.7 + speed * 0.3

    # 2. History factor
    if use_history:
        avg_pts = db.get_player_avg_points(p[0], chat_id, thread_id)
        if avg_pts == 0:
            avg_pts = random.uniform(0.5, 2.5) 
        base = base * 0.7 + (float(avg_pts) * 20) * 0.3

    return base

def is_payment_complete(chat_id, thread_id):
    import database as db
    settings = db.get_match_settings(chat_id, thread_id)
    require_confirmation = settings.get('require_payment_confirmation', 0)
    regs = db.get_registrations(chat_id, thread_id)
    
    if not regs:
        return True # No players - nothing to pay
        
    for r in regs:
        # r[8] is is_paid
        status = r[8]
        if require_confirmation:
            if status != 2: return False
        else:
            if status == 0: return False
            
    return True

def balance_teams(players, chat_id, thread_id, mode='all', use_history=False, shuffle_factor=0, captains=[]):
    processed_players = []
    # Identify captain IDs
    cap_ids = captains if captains else []
    
    for p in players:
        ovr = calculate_ovr(p, chat_id, thread_id, mode, use_history)
        final_ovr = ovr + random.uniform(-shuffle_factor, shuffle_factor)
        processed_players.append({
            "id": p[0],
            "user_id": p[1],
            "name": p[2],
            "ovr": final_ovr,
            "position": p[7]
        })
    
    team_1, team_2 = [], []
    score_1, score_2 = 0, 0
    total_count = len(processed_players)
    max_in_team = (total_count + 1) // 2

    # Fixed captains handling
    remaining_players = []
    for p in processed_players:
        if p['id'] in cap_ids:
            # First captain to T1, second to T2
            if len(team_1) == 0:
                team_1.append(p)
                score_1 += p['ovr']
            else:
                team_2.append(p)
                score_2 += p['ovr']
        else:
            remaining_players.append(p)

    # Logic to distribute by position groups
    if mode in ['all', 'gk']:
        # Group by position
        gks = [p for p in remaining_players if p['position'] == 'gk']
        if mode == 'all':
            defs = [p for p in remaining_players if p['position'] == 'def']
            atts = [p for p in remaining_players if p['position'] == 'att']
        else:
            fields = [p for p in remaining_players if p['position'] != 'gk']
            
        # Shuffle within groups first to vary equal ratings
        random.shuffle(gks)
        if mode == 'all':
            random.shuffle(defs)
            random.shuffle(atts)
            # Sort by OVR desc
            gks.sort(key=lambda x: x['ovr'], reverse=True)
            defs.sort(key=lambda x: x['ovr'], reverse=True)
            atts.sort(key=lambda x: x['ovr'], reverse=True)
            groups = [gks, defs, atts]
        else:
            random.shuffle(fields)
            gks.sort(key=lambda x: x['ovr'], reverse=True)
            fields.sort(key=lambda x: x['ovr'], reverse=True)
            groups = [gks, fields]
            
        # Distribute group by group
        for group in groups:
            for p in group:
                can_t1 = len(team_1) < max_in_team
                can_t2 = len(team_2) < max_in_team
                
                # Check position balance for this specific player's position
                pos = p['position']
                c1_pos = len([x for x in team_1 if x['position'] == pos])
                c2_pos = len([x for x in team_2 if x['position'] == pos])
                
                # Helper to add to T1
                def add_t1(pl): team_1.append(pl); nonlocal score_1; score_1 += pl['ovr']
                def add_t2(pl): team_2.append(pl); nonlocal score_2; score_2 += pl['ovr']

                # Prefer adding to the team with FEWER players of this position
                # But allow slight randomness if shuffle_factor > 0
                if c1_pos < c2_pos and can_t1:
                    add_t1(p)
                elif c2_pos < c1_pos and can_t2:
                    add_t2(p)
                else:
                    # If position count is equal, balance by total OVR
                    if can_t1 and not can_t2:
                        add_t1(p)
                    elif can_t2 and not can_t1:
                        add_t2(p)
                    else:
                        # Decide based on score with some randomness
                        diff = score_1 - score_2
                        # If shuffle factor is high, allow unbalanced pick occasionally
                        should_pick_t1 = diff <= 0
                        
                        if shuffle_factor > 0 and abs(diff) < 20: # If scores are close
                             if random.random() < 0.3: # 30% chance to flip logic
                                 should_pick_t1 = not should_pick_t1
                        
                        if should_pick_t1:
                            add_t1(p)
                        else:
                            add_t2(p)
    else:
        # Simple OVR balance for 'none' mode
        remaining_players.sort(key=lambda x: x['ovr'], reverse=True)
        for p in remaining_players:
            can_t1 = len(team_1) < max_in_team
            can_t2 = len(team_2) < max_in_team
            
            if can_t1 and not can_t2:
                team_1.append(p)
                score_1 += p['ovr']
            elif can_t2 and not can_t1:
                team_2.append(p)
                score_2 += p['ovr']
            else:
                if score_1 <= score_2:
                    team_1.append(p)
                    score_1 += p['ovr']
                else:
                    team_2.append(p)
                    score_2 += p['ovr']
            
    return team_1, team_2, score_1, score_2

def get_chat_lang(chat_id, thread_id):
    """Get language_id for a chat, defaulting to 1 (Russian)"""
    try:
        s = db.get_match_settings(chat_id, thread_id)
        return s.get('language_id', 1) if s else 1
    except:
        return 1

# --- MOVED HELPERS FROM main.py ---

def player_to_dict(p):
    return {
        "id": p[0],
        "user_id": p[1],
        "name": p[2],
        "position": p[7]
    }

async def track_msg(state: FSMContext, msg_id: int):
    data = await state.get_data()
    msgs = data.get("msgs_to_delete", [])
    msgs.append(msg_id)
    await state.update_data(msgs_to_delete=msgs)

async def cleanup_msgs(chat_id: int, state: FSMContext, exclude_ids: list = None):
    """Удаляет отслеживаемые сообщения, кроме тех, что в exclude_ids"""
    if exclude_ids is None:
        exclude_ids = []
    data = await state.get_data()
    msgs = data.get("msgs_to_delete", [])
    for m_id in msgs:
        if m_id not in exclude_ids:
            try:
                await bot.delete_message(chat_id, m_id)
            except:
                pass

async def auto_delete_message(chat_id: int, message_id: int, delay_seconds: int = 10):
    """Автоматически удаляет сообщение через указанное время"""
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

async def is_admin(event: types.Message | types.CallbackQuery, state: FSMContext = None):
    chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
    user_id = event.from_user.id
    
    # Если мы в личке с ботом, пытаемся взять chat_id из состояния (который установили в группе через /admin)
    if chat_id == user_id and state:
        data = await state.get_data()
        if data.get('chat_id'):
            chat_id = data['chat_id']
            
    try:
        # Для лички с самим собой get_chat_member может вести себя странно, 
        # но если мы подменили chat_id на ID группы, то всё сработает штатно.
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except Exception as e:
        logger.debug(f"is_admin check failed: {e}")
        # Если это личка и нет подмены chat_id — по умолчанию не админ
        if chat_id == user_id: return False
        return True # В группах при ошибке лучше разрешить (напр. если бот только зашел)

def get_ids(event: types.Message | types.CallbackQuery):
    if isinstance(event, Message):
        return event.chat.id, event.message_thread_id or 0
    elif isinstance(event, CallbackQuery):
        # Callback query message can be absent if it was too old, but usually it is there
        return event.message.chat.id, (event.message.message_thread_id or 0) if event.message else 0
    return 0, 0

def get_match_date(match_times_str, timezone_str, find_past=False):
    """
    Calculates the match date based on specific weekday/time string (e.g., 'mon 21:00').
    find_past: If True, finds the most recent past (or current) occurrence.
    Returns: datetime object (naive, representing Local Match Time) or None
    """
    if not match_times_str or match_times_str == "—": return None
    import re
    match_time = re.match(r"^([a-z]{3})\s+(\d{1,2}):(\d{2})$", str(match_times_str))
    if not match_time: return None

    day_code = match_time.group(1)
    hh = int(match_time.group(2))
    mm = int(match_time.group(3))

    offset = 3
    if timezone_str:
        tm_match = re.search(r"GMT([+-]?\d+)", str(timezone_str))
        if tm_match: offset = int(tm_match.group(1))

    utc_now = datetime.now(timezone.utc)
    client_now = utc_now + timedelta(hours=offset)
    client_now = client_now.replace(tzinfo=None)

    days_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
    target_wd = days_map.get(day_code, 0)
    current_wd = client_now.weekday()

    delta = target_wd - current_wd

    if find_past:
        if delta > 0: delta -= 7
        elif delta == 0:
             if client_now.hour < hh or (client_now.hour == hh and client_now.minute < mm):
                 delta -= 7
    else:
        if delta < 0: delta += 7
        elif delta == 0:
            if client_now.hour > hh or (client_now.hour == hh and client_now.minute >= mm):
                delta = 7

    target_date = client_now + timedelta(days=delta)
    target_date = target_date.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return target_date

async def update_poll_message(message: Message = None, chat_id: int = None, thread_id: int = None, message_id: int = None):
    cid = chat_id or (message.chat.id if message else None)
    tid = thread_id if thread_id is not None else (message.message_thread_id or 0 if message else 0)
    if not cid: return
    
    settings = db.get_match_settings(cid, tid) or {}
    regs = db.get_registrations(cid, tid)
    lang_id = settings.get('language_id', 1)

    def t_val(v):
        if not v or v == "—": return "—" # Keep dash for unset in poll
        return tr.t(str(v), lang_id)
    
    # Header
    text = tr.t("poll_header", lang_id) + "\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    # Settings Rows
    skill_l = db.get_label_by_id("skill_levels", settings.get('skill_level_id'), lang_id)
    age_l = db.get_label_by_id("age_groups", settings.get('age_group_id'), lang_id)
    gender_l = db.get_label_by_id("genders", settings.get('gender_id'), lang_id)
    venue_l = db.get_label_by_id("venue_types", settings.get('venue_type_id'), lang_id)
    
    text += f"{tr.t('setting_players', lang_id)}: {h(settings.get('player_count', '—'))}\n"
    text += f"{tr.t('setting_skill_level', lang_id)}: {h(skill_l)}\n"
    text += f"{tr.t('setting_age', lang_id)}: {h(age_l)}\n"
    text += f"{tr.t('setting_gender', lang_id)}: {h(gender_l)}\n"
    
    # Cost display logic
    cost_mode = settings.get('cost_mode', 'fixed_player')
    cost_val = settings.get('cost', '0')
    base_cost = extract_amount(cost_val)
    
    if cost_mode == 'fixed_game':
        max_players = int(settings.get('player_count', 0))
        current_players = len([r for r in regs if r[9] == 'active'])
        
        # Calculate costs
        t_cost = base_cost / max_players if max_players > 0 else base_cost
        c_cost = base_cost / current_players if current_players > 0 else base_cost
        
        # Round up to 1/10 (tenth)
        target_cost = math.ceil(t_cost * 10) / 10
        current_cost = math.ceil(c_cost * 10) / 10
        
        per_person = "/чел" if lang_id == 1 else "/person"
        cost_str = f"{cost_val} ({current_cost:g}{per_person}{tr.t('cost_desc_curr', lang_id)}, {target_cost:g}{per_person}{tr.t('cost_desc_full', lang_id)})"
        text += f"{tr.t('setting_cost', lang_id)}: {h(cost_str)}{h(tr.t('pay_info_hint', lang_id))}\n"
    else:
        text += f"{tr.t('setting_cost', lang_id)}: {h(cost_val)}{h(tr.t('pay_info_hint', lang_id))}\n"
    
    text += f"{tr.t('setting_venue_type', lang_id)}: {h(venue_l)}\n"
    
    lat = settings.get('location_lat')
    lon = settings.get('location_lon')
    if lat and lon:
        text += f"{tr.t('setting_location', lang_id)}: <a href=\"https://www.google.com/maps?q={lat},{lon}\">{lat:.6f}, {lon:.6f}</a>\n"
    
    time_val = settings.get('match_times', '—')
    tz_val = settings.get('timezone', 'GMT+3')

    next_dt = get_match_date(time_val, tz_val, find_past=False)

    if next_dt:
        match_time = re.match(r"^([a-z]{3})\s+(\d{1,2}):(\d{2})$", str(time_val))
        day_code = match_time.group(1)
        hh = int(match_time.group(2))
        mm = int(match_time.group(3))

        date_str = next_dt.strftime("%d.%m.%y")
        day_short = tr.t("wd_short_" + day_code, lang_id)
        display_str = f"{day_short} {hh:02d}:{mm:02d} ({h(tz_val)}), {date_str}г."
        text += f"{tr.t('setting_match_times', lang_id)}: {display_str}\n"
    else:
        text += f"{tr.t('setting_match_times', lang_id)}: {h(time_val)} ({h(tz_val)})\n"
    
    if settings.get('season_start') != "—":
        text += f"{tr.t('setting_season', lang_id)}: {h(settings.get('season_start'))} — {h(settings.get('season_end', '—'))}\n"
    
    text += h(tr.t("poll_separator", lang_id)) + "\n\n"
    
    # Player Lists
    roles = [('att', 'role_att_list'), ('def', 'role_def_list'), ('gk', 'role_gk_list')]
    
    # Filter active players
    active_regs = [r for r in regs if r[9] == 'active']
    
    # Debug logging
    logger.info(f"UpdatePoll: Total regs={len(regs)}, Active={len(active_regs)}")
    for r in regs:
        logger.info(f"  - Player {r[2]} (id={r[0]}), status='{r[9]}', position={r[7]}")
    
    for pos, key in roles:
        # Debug position matching
        for r in active_regs:
             if r[7] != pos:
                  logger.debug(f"Mismatch: Player {r[2]} pos='{r[7]}' != '{pos}'")
             else:
                  logger.debug(f"MATCH: Player {r[2]} pos='{r[7]}' == '{pos}'")
                  
        list_p = [r for r in active_regs if r[7] == pos]
        label = tr.t(key, lang_id)
        text += f"<b>{h(label)} ({len(list_p)}):</b>\n"
        
        lines = []
        for r in list_p:
            # r[0] = player_id, r[2] = name, r[8] = is_paid
            name = h(r[2])
            is_paid = r[8]
            
            # Add coin emoji for paid players (status >= 1)
            if is_paid >= 1:
                lines.append(f"- {name} 💰")
            else:
                lines.append(f"- {name}")
            
        text += "\n".join(lines) or h(tr.t("list_empty", lang_id))
        text += "\n\n"
    
    # Add Queue Section if exists
    queue_regs = [r for r in regs if r[9] == 'queue']
    if queue_regs:
        text += f"<b>{h(tr.t('status_queue', lang_id))} ({len(queue_regs)}):</b>\n"
        q_lines = []
        for i, r in enumerate(queue_regs):
            q_lines.append(f"{i+1}. {h(r[2])}")
        text += "\n".join(q_lines) + "\n\n"

    pending_regs = [r for r in regs if r[9] == 'pending_confirm']
    if pending_regs:
         text += f"<b>Pending ({len(pending_regs)}):</b>\n"
         p_lines = [f"- {h(r[2])}" for r in pending_regs]
         text += "\n".join(p_lines) + "\n\n"

    # Not Coming Section
    not_coming_regs = [r for r in regs if r[9] == 'not_coming']
    if not_coming_regs:
        text += f"<b>{h(tr.t('status_not_coming', lang_id))} ({len(not_coming_regs)}):</b>\n"
        nc_lines = [f"- {h(r[2])}" for r in not_coming_regs]
        text += "\n".join(nc_lines) + "\n\n"

    # Calculate Total including Reserved Core
    core_team_mode = settings.get('core_team_mode', 0)
    all_core = db.get_core_players(cid, tid)
    core_ids = [c[0] for c in all_core]
    regs_map = {r[0]: r[9] for r in regs}
    
    logger.info(f"UpdatePoll: Core team players: {len(all_core)}")
    for c in all_core:
        logger.info(f"  - Core player: {c[2]} (id={c[0]})")
    
    # Reserved = Core players who are NOT Active and NOT "Not Coming"
    # ONLY IF core_team_mode is enabled (1)
    reserved_core = 0
    if core_team_mode:
        for c_id in core_ids:
            status = regs_map.get(c_id)
            if status != 'active' and status != 'not_coming':
                reserved_core += 1
                logger.info(f"  - Core player id={c_id} is RESERVED (status={status})")
            
    total_occupied = len(active_regs) + reserved_core
    
    logger.info(f"UpdatePoll: Final count - Active={len(active_regs)}, Reserved={reserved_core}, Total={total_occupied}")

    text += f"{h(tr.t('poll_total', lang_id))}: {total_occupied} / {h(settings.get('player_count', 0))}"

    # Core Team Summary Footer
    if core_team_mode and all_core:
        core_confirmed = 0
        core_refused = 0
        for c_id in core_ids:
            status = regs_map.get(c_id)
            if status == 'active':
                core_confirmed += 1
            elif status == 'not_coming':
                core_refused += 1
        
        summary_text = tr.t("core_team_summary", lang_id).format(
            confirmed=core_confirmed,
            total=len(all_core),
            refused=core_refused
        )
        text += f"\n\nℹ️ {h(summary_text)}"
    
    # Build keyboard with registration buttons and single payment button
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    combined = InlineKeyboardBuilder()
    
    # Add registration buttons
    bot_user = await bot.get_me()
    reg_markup = kb.get_registration_kb(len(regs), lang_id, lat=lat, lon=lon, chat_id=cid, thread_id=tid, bot_username=bot_user.username)
    combined.attach(InlineKeyboardBuilder.from_markup(reg_markup))
    
    # Add single "I Paid" button
    combined.button(text=tr.t("btn_i_paid", lang_id), callback_data="pay_self")
    
    markup = combined.as_markup()

    if not message and not message_id and chat_id:
        # Try to find stored poll_message_id
        poll_id = settings.get('poll_message_id')
        if poll_id:
            message_id = poll_id
        else:
            logger.warning(f"UpdatePoll: No poll_message_id found for cid={chat_id} tid={thread_id}")

    try:
        if message:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True))
        elif chat_id and message_id:
            logger.info(f"UpdatePoll: Updating msg {message_id} in {chat_id}")
            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True))
        else:
            logger.warning("UpdatePoll: Skipped (no message or ID)")
    except Exception as e:
        if "message is not modified" in str(e):
             logger.info("UpdatePoll: Message content unchanged")
        else:
             logger.error(f"Update poll failed: {e}")

def perform_full_clear(chat_id, thread_id):
    db.clear_registrations(chat_id, thread_id)
    db.clear_draft_state(chat_id, thread_id)

def get_unpaid_players_mention(chat_id, thread_id, lang_id=1):
    """Returns a string with mentions for unpaid players and a status keyboard"""
    regs = db.get_registrations(chat_id, thread_id)
    # Filter active and unpaid
    unpaid = [r for r in regs if r[8] < 2 and r[9] == 'active']
    if not unpaid:
        return tr.t("all_paid", lang_id), None
    
    mentions = []
    for r in unpaid:
        # r[1] is user_id, r[2] is name
        if r[1]:
            mentions.append(f"<a href=\"tg://user?id={r[1]}\">{h(r[2])}</a>")
        else:
            mentions.append(h(r[2]))
    
    text = tr.t("unpaid_reminder_text", lang_id).format(tags=", ".join(mentions))
    
    # Calculate player cost
    cost = db.calculate_player_cost(chat_id, thread_id)
    text += f"\n💰 <b>{cost:g}</b>₽ {h(tr.t('pay_info_hint', lang_id))}"
    
    return text, None

async def check_queue_promotion(chat_id, thread_id):
    """
    Checks if there is a free slot for a player from the queue.
    If yes, sends a confirmation message to the first player in the queue.
    """
    settings = db.get_match_settings(chat_id, thread_id)
    req_count = settings.get('player_count', 12)
    regs = db.get_registrations(chat_id, thread_id)
    
    # Active players are those with status='active'
    for r in regs:
        logger.info(f"Reg: id={r[0]}, name={r[2]}, status='{r[9]}'")
    active_players = [r for r in regs if r[9] == 'active']
    
    # Calculate occupied spots including reserved core
    all_core = db.get_core_players(chat_id, thread_id)
    core_ids = [c[0] for c in all_core]
    regs_map = {r[0]: r[9] for r in regs}
    
    core_team_mode = settings.get('core_team_mode', 0)
    reserved_core = 0
    if core_team_mode:
        for c_id in core_ids:
            status = regs_map.get(c_id)
            if status != 'active' and status != 'not_coming':
                reserved_core += 1
            
    total_occupied = len(active_players) + reserved_core
    
    logger.info(f"QueueCheck: req={req_count}, occupied={total_occupied} (active={len(active_players)}, reserved={reserved_core})")
    
    # Only promote if we have space
    if total_occupied < req_count:
        # First check if anyone is ALREADY pending confirm (stuck?)
        pending_players = [r for r in regs if r[9] == 'pending_confirm']
        
        target_candidate = None
        
        if pending_players:
            # We have someone pending. Let's assume we need to re-send message or just wait.
            # Ideally we pick the first one to re-notify if needed.
            # But simpler logic: if pending exists, treat as candidate.
            c = pending_players[0]
            target_candidate = (c[0], c[1], c[2]) # id, user_id, name
            logger.info(f"QueueCheck: Found pending candidate {target_candidate[2]}")
        else:
            # No pending, check queue
            queue = db.get_queue(chat_id, thread_id)
            logger.info(f"QueueCheck: queue_size={len(queue)}")
            if queue:
                target_candidate = queue[0]
                # Update status immediately
                db.update_registration_status(target_candidate[0], chat_id, thread_id, 'pending_confirm')

        if target_candidate:
            pid = target_candidate[0]
            user_id = target_candidate[1]
            name = target_candidate[2]
            
            lang_id = settings.get('language_id', 1)
            tag = f"[{name}](tg://user?id={user_id})" if user_id else name
            msg_text = tr.t("queue_promotion_msg", lang_id).format(tag=tag)
            
            builder = InlineKeyboardBuilder()
            builder.button(text=tr.t("btn_confirm_queue", lang_id), callback_data=f"queue_confirm_{pid}")
            builder.button(text=tr.t("btn_leave_queue", lang_id), callback_data=f"queue_cancel_{pid}")
            builder.adjust(2)
            
            await bot.send_message(chat_id, msg_text, message_thread_id=thread_id if thread_id else None, reply_markup=builder.as_markup(), parse_mode="Markdown")

class PMContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message) and event.chat.type == 'private':
            # It's a private message. Check for command.
            if event.text and event.text.startswith('/'):
                # It's a command. Check if it's /start with payload.
                if event.text.startswith('/start ') and len(event.text.split()) > 1:
                    # Deep link - allow through.
                    return await handler(event, data)
                
                # Not a deep link. Check state for chat_id.
                state: FSMContext = data.get('state')
                if state:
                    state_data = await state.get_data()
                    if not state_data.get('chat_id'):
                        # No context. Block and warn.
                        # Try to guess language from user's telegram language code
                        user_lang = event.from_user.language_code
                        lang_id = 2 if user_lang and 'en' in user_lang.lower() else 1
                        
                        await event.answer(tr.t("use_admin_in_group_topic", lang_id))
                        return
                else:
                    # No state at all? Usually FSMContext is always present if using Dispatcher
                    pass
        
        return await handler(event, data)

async def get_championship_image(chat_id: int, thread_id: int = 0):
    """
    Fetches championship image from local API
    """
    try:
        import aiohttp
        import base64
        from aiogram.types import BufferedInputFile
        
        url = "http://localhost:3000/api/championship/image"
        payload = {
            "chat_id": chat_id,
            "thread_id": thread_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    logger.error(f"API Error status: {response.status}")
                    return None
                    
                data = await response.json()
                
                if "image" in data:
                    image_data = base64.b64decode(data["image"])
                    return BufferedInputFile(image_data, filename="championship.jpg")
                else:
                    logger.error("No image data in response")
                    return None
                    
    except Exception as e:
        logger.error(f"API Error: {e}")
        return None
