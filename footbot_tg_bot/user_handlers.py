import logging
import math
from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb
import utils
import translations as tr
from states import PlayerSelfRegister, MatchSettings, PairsBuilder
from init_bot import bot

logger = logging.getLogger(__name__)
router = Router()

def get_ids(event):
    return utils.get_ids(event)

@router.message(F.new_chat_members)
async def on_user_join(message: Message, state: FSMContext):
    from aiogram.exceptions import TelegramBadRequest
    cid, tid = get_ids(message)
    bot_obj = await bot.get_me()
    for member in message.new_chat_members:
        if member.id == bot_obj.id:
            # Bot was added
            lang_id = 1 # Default to English/International first
            try:
                await message.answer(
                     tr.t("welcome_select_lang", lang_id),
                     reply_markup=kb.get_language_kb()
                )
            except TelegramBadRequest as e:
                if "TOPIC_CLOSED" in str(e):
                    pass  # Silently skip if topic is closed
                else:
                    raise
            return

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Check for payload args
    try:
        await message.delete()
    except:
        pass
    logger.info(f"Start command received: {message.text}")
    args = message.text.split()
    if len(args) > 1:
        payload = args[1]
        
        # Admin Quick Manage Payload
        if payload.startswith("admin_quick_"):
            try:
                data = payload.replace("admin_quick_", "")
                parts = data.split("_")
                
                # Handling negative IDs logic:
                # If ID was negative like "-100123", it might be passed as "-100123_456"
                # split("_") gives ["-100123", "456"] -> Correct.
                
                target_cid = int(parts[0])
                target_tid = int(parts[1]) if len(parts) > 1 else 0
                target_lang = utils.get_chat_lang(target_cid, target_tid)
                
                try:
                    chat_member = await bot.get_chat_member(target_cid, message.from_user.id)
                    if chat_member.status not in ['administrator', 'creator']:
                        return await message.answer(tr.t("no_admin_rights", target_lang))
                except:
                    return await message.answer(tr.t("error_generic", target_lang))
                
                await state.update_data(chat_id=target_cid, thread_id=target_tid)
                
                await message.answer(
                     tr.t("admin_player_mgmt", target_lang), 
                     reply_markup=kb.get_quick_manage_kb(target_cid, target_tid, target_lang)
                )
                return
            except Exception as e:
                logger.error(f"Start payload error: {e}")
                await message.answer("Error processing request.")
                return

        # Pairs Building Payload
        if payload.startswith("pairs_"):
            parts = payload.split("_")
            if len(parts) < 3: 
                return await message.answer(tr.t("error_invalid_link", lang_id))
            
            target_cid = int(parts[1])
            target_tid = int(parts[2])
            target_lang = utils.get_chat_lang(target_cid, target_tid)
            
            players = db.get_registrations(target_cid, target_tid)
            avail_players = []
            for p in players:
                ovr = utils.calculate_ovr(p, target_cid, target_tid, mode='all')
                d = utils.player_to_dict(p)
                d['ovr'] = ovr
                avail_players.append(d)
                
            await state.clear()
            await state.set_state(PairsBuilder.selecting_left)
            await state.update_data(
                chat_id=target_cid, 
                thread_id=target_tid, 
                avail_players=avail_players,
                left_side=[],
                right_side=[],
                finished_pairs=[],
                selected_ids=[]
            )
            await message.answer(
                tr.t("pairs_builder_desc", target_lang),
                reply_markup=kb.get_pairs_builder_kb(avail_players, [], "left", False)
            )
            return

    # Regular /start logic
    if message.chat.type in ['group', 'supergroup']:
        from aiogram.exceptions import TelegramBadRequest
        try:
            if await utils.is_admin(message, state):
                 await message.answer(
                     tr.t("welcome_select_lang", lang_id),
                     reply_markup=kb.get_language_kb()
                 )
            else:
                 await message.answer(tr.t("welcome_msg_user", lang_id))
        except TelegramBadRequest as e:
            if "TOPIC_CLOSED" in str(e):
                pass  # Silently skip if topic is closed
            else:
                raise
        return
    await message.answer(tr.t("welcome_msg_admin", lang_id))



@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if message.chat.type == 'private':
        return  # Ignore in private chat
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    await state.clear()
    await message.answer(tr.t("action_canceled", lang_id))
    try:
        await message.delete()
    except:
        pass

@router.message(Command("pay_info"))
async def cmd_pay_info(message: Message):
    """Show payment information with auto-delete after 2 minutes"""
    if message.chat.type == 'private':
        return  # Ignore in private chat
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    
    # Calculate per-player cost and detailed breakdown
    cost_val = settings.get('cost', '0')
    cost_mode = settings.get('cost_mode', 'fixed_player')
    player_cost = db.calculate_player_cost(cid, tid)
    
    import html
    def h(text): return html.escape(str(text))
    
    # Build message using HTML for more robust escaping
    text = f"<b>{h(tr.t('pay_info_title', lang_id))}</b>\n\n"
    
    if cost_mode == 'fixed_game':
        # Detailed breakdown for rental mode
        text += f"<b>{h(tr.t('pay_info_amount', lang_id).format(amount=h(cost_val)))}</b>\n"
        
        # Current vs Target
        max_p = int(settings.get('player_count', 0))
        cur_p = db.count_registered_players(cid, tid)
        
        # Rounding up to 0.1
        curr_c = player_cost # Already calculated by calculate_player_cost
        base = utils.extract_amount(cost_val)
        target_c = math.ceil((base / max_p if max_p > 0 else base) * 10) / 10
        
        per_person = "/чел" if lang_id == 1 else "/person"
        text += f" Сумма: <b>{curr_c:g}{per_person}</b>{h(tr.t('cost_desc_curr', lang_id))}, "
        text += f"<b>{target_c:g}{per_person}</b>{h(tr.t('cost_desc_full', lang_id))}\n\n"
    else:
        # Simple for fixed player
        text += f"<b>{h(tr.t('pay_info_amount', lang_id).format(amount=f'{player_cost:g}'))}</b>\n\n"
    
    payment_details = settings.get('payment_details')
    details = payment_details if payment_details else tr.t('payment_details_default', lang_id)
    text += f"📝 <b>{h(tr.t('btn_payment_details', lang_id))}:</b>\n{h(details)}\n\n"
    
    text += f"<i>{h(tr.t('pay_info_expires', lang_id))}</i>"
    
    sent_msg = await message.answer(text, parse_mode="HTML")
    
    # Check for cleanup
    try:
        await message.delete()
    except:
        pass
    
    # Auto-delete after 2 minutes
    import asyncio
    asyncio.create_task(delete_message_after_delay(sent_msg, 120))

@router.message(Command("table"))
async def cmd_table(message: Message):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    
    wait_msg = await message.answer(tr.t("processing_image", lang_id) if tr.t("processing_image", lang_id) != "processing_image" else "⏳ ...")
    
    try:
        photo = await utils.get_championship_image(cid, tid)
        if photo:
            await message.answer_photo(
                photo,
                reply_markup=kb.get_site_link_kb(cid, tid, lang_id)
            )
            await wait_msg.delete()
        else:
            await wait_msg.edit_text(tr.t("error_generic", lang_id))
    except Exception as e:
        logger.error(f"Table cmd error: {e}")
        await wait_msg.edit_text(tr.t("error_generic", lang_id))

@router.message(Command("site"))
async def cmd_site(message: Message):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    await message.answer(
        tr.t("btn_open_site", lang_id),
        reply_markup=kb.get_site_link_kb(cid, tid, lang_id)
    )

async def delete_message_after_delay(message, seconds):
    """Helper to delete message after delay"""
    import asyncio
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass  # Message might already be deleted

@router.callback_query(F.data.startswith("reg_"))
async def process_registration(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    # Save poll message ID
    if callback.message:
        db.update_match_settings(cid, tid, "poll_message_id", callback.message.message_id)
        
    pos = callback.data.split("_")[1]
    user_id = callback.from_user.id
    name = callback.from_user.full_name
    lang_id = utils.get_chat_lang(cid, tid)
    p = db.get_player_by_user_id(user_id, cid, tid)
    # New player logic: Ask for name
    if not p or not db.player_has_stats(p[0], cid, tid):
        await state.update_data(
            poll_chat_id=cid, 
            poll_thread_id=tid, 
            poll_msg_id=callback.message.message_id if callback.message else 0,
            reg_pos=pos,
            user_name=name
        )
        sent = await callback.message.answer(tr.t("ask_your_name", lang_id))
        await state.update_data(ask_name_msg_id=sent.message_id)
        await state.set_state(PlayerSelfRegister.waiting_for_name)
        await callback.answer()
        return
    
    is_new = False
    
    # Check max players
    settings = db.get_match_settings(cid, tid)
    max_p = settings.get('player_count', 12)
    regs = db.get_registrations(cid, tid)
    
    # Calculate Occupied (Active + Reserved Core)
    active_regs = [r for r in regs if r[9] == 'active']
    regs_map = {r[0]: r[9] for r in regs}
    all_core = db.get_core_players(cid, tid)
    
    core_team_mode = settings.get('core_team_mode', 0)
    reserved_core = 0
    if core_team_mode:
        for c in all_core:
            st = regs_map.get(c[0])
            if st != 'active' and st != 'not_coming':
                reserved_core += 1
                
    total_occupied = len(active_regs) + reserved_core
    logger.info(f"RegCheck: active={len(active_regs)}, reserved={reserved_core}, total={total_occupied}, max={max_p}")
    
    # Determine status
    status = 'active'
    msg_key = "reg_success_role"
    
    is_core = p[7] if len(p) > 7 else 0
    
    # Check if already registered
    my_reg = next((r for r in regs if r[0] == p[0]), None)
    
    if my_reg and my_reg[9] not in ['not_coming']:
        # Existing registration (keep status unless specific change needed)
        if my_reg[9] == 'active': 
             status = 'active'
        elif my_reg[9] == 'queue':
             status = 'queue'
             msg_key = "queue_joined"
        else: # pending
             status = my_reg[9]
    else:
        # New or Re-joining from Not Coming
        if is_core:
            status = 'active'
        elif total_occupied >= max_p:
            status = 'queue'
            msg_key = "queue_joined"

    db.register_player(p[0], cid, tid, pos, status=status)
    
    role_label = tr.t("reg_" + pos, lang_id)
    if status == 'queue':
        # recalc queue pos
        q = db.get_queue(cid, tid)
        try:
             my_pos = next(i for i, v in enumerate(q) if v[0] == p[0]) + 1
        except: my_pos = "?"
        msg = tr.t("queue_joined", lang_id).format(pos=my_pos)
    else: 
        msg = tr.t("reg_success_role", lang_id).format(role=role_label)
        if is_new:
            msg += tr.t("reg_success_default", lang_id)

    await callback.answer(msg)
    await callback.answer(msg)
    await utils.update_poll_message(callback.message)

@router.callback_query(F.data == "not_coming")
async def process_not_coming(callback: CallbackQuery):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    
    if callback.message:
        db.update_match_settings(cid, tid, "poll_message_id", callback.message.message_id)
        
    user_id = callback.from_user.id
    name = callback.from_user.full_name
    p = db.get_player_by_user_id(user_id, cid, tid)
    
    if not p or not db.player_has_stats(p[0], cid, tid):
         db.create_player_full(user_id, name, cid, tid, 50, 50, 50, 50)
         p = db.get_player_by_user_id(user_id, cid, tid)
    
    # Check if was active
    regs = db.get_registrations(cid, tid)
    my_reg = next((r for r in regs if r[0] == p[0]), None)
    was_active = (my_reg and my_reg[9] == 'active')
    
    # Update status to not_coming
    # We keep position if known, else 'unknown' (or use last position)
    pos = my_reg[3] if my_reg else 'att' # Default to att if unknown, doesn't matter much for not_coming
    
    db.register_player(p[0], cid, tid, pos, status='not_coming')
    
    await callback.answer(tr.t("reg_canceled_not_coming", lang_id))
    if was_active:
         # Free spot opened
         await utils.check_queue_promotion(cid, tid)
         
    await utils.update_poll_message(callback.message)

@router.callback_query(F.data == "unreg")
async def process_unregistration(callback: CallbackQuery):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Save poll message ID
    if callback.message:
        db.update_match_settings(cid, tid, "poll_message_id", callback.message.message_id)
    
    p = db.get_player_by_user_id(callback.from_user.id, cid, tid)
    if p:
        # Check if was active
        regs = db.get_registrations(cid, tid)
        my_reg = next((r for r in regs if r[0] == p[0]), None)
        was_active = (my_reg and my_reg[9] == 'active')
        
        db.unregister_player(p[0], cid, tid)
        await callback.answer(tr.t("reg_canceled", lang_id))
        if was_active:
             await utils.check_queue_promotion(cid, tid)
             
        await utils.update_poll_message(callback.message)

@router.callback_query(F.data.startswith("queue_confirm_"))
async def process_queue_confirm(callback: CallbackQuery):
    cid, tid = get_ids(callback)
    pid = int(callback.data.split("_")[2])
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Verify user
    p = db.get_player_by_id(pid, cid, tid)
    if not p: return await callback.answer("Error")
    
    # Check if user matches or admin
    is_adm = await utils.is_admin(callback)
    if not is_adm and (not p[1] or p[1] != callback.from_user.id):
        return await callback.answer(tr.t("error_not_your_button", lang_id), show_alert=True)
        
    db.update_registration_status(pid, cid, tid, 'active')
    await callback.message.edit_text(tr.t("queue_confirmed", lang_id), reply_markup=None)
    await callback.answer()
    await utils.update_poll_message(chat_id=cid, thread_id=tid)

@router.callback_query(F.data.startswith("queue_cancel_"))
async def process_queue_cancel(callback: CallbackQuery):
    cid, tid = get_ids(callback)
    pid = int(callback.data.split("_")[2])
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Verify user
    p = db.get_player_by_id(pid, cid, tid)
    if not p: return await callback.answer("Error")
    
    is_adm = await utils.is_admin(callback)
    if not is_adm and (not p[1] or p[1] != callback.from_user.id):
        return await callback.answer(tr.t("error_not_your_button", lang_id), show_alert=True)

    db.unregister_player(pid, cid, tid)
    await callback.message.edit_text(tr.t("queue_left", lang_id), reply_markup=None)
    await callback.answer()
    
    # Trigger promotion check again in case there are others in queue
    await utils.check_queue_promotion(cid, tid)
    
    await utils.update_poll_message(chat_id=cid, thread_id=tid)

# --- PLAYER SELF-REGISTER FSM ---

@router.message(PlayerSelfRegister.waiting_for_name)
async def player_self_name(message: Message, state: FSMContext):
    data = await state.get_data()
    target_cid = data.get('poll_chat_id')
    target_tid = data.get('poll_thread_id', 0)
    
    # Use target chat language
    lang_id = utils.get_chat_lang(target_cid, target_tid) if target_cid else 1
    
    val = message.text.strip()
    if not val:
        await message.answer(tr.t("error_empty_name", lang_id))
        return

    user_id = message.from_user.id
    user_fullname = data.get('user_name', message.from_user.full_name)
    
    # Create player with default stats (50)
    db.create_player_full(user_id, user_fullname, target_cid, target_tid, 50, 50, 50, 50)
    
    # Update display name and get PID
    p_row = db.get_player_by_user_id(user_id, target_cid, target_tid)
    if p_row:
        pid = p_row[0]
        db.update_player_display_name(pid, target_cid, target_tid, val)
        
        # Calculate status (queue vs active)
        settings = db.get_match_settings(target_cid, target_tid)
        max_p = settings.get('player_count', 12)
        regs = db.get_registrations(target_cid, target_tid)
        
        active_regs = [r for r in regs if r[9] == 'active']
        regs_map = {r[0]: r[9] for r in regs}
        all_core = db.get_core_players(target_cid, target_tid)
        
        core_team_mode = settings.get('core_team_mode', 0)
        reserved_core = 0
        if core_team_mode:
            for c in all_core:
                st = regs_map.get(c[0])
                if st != 'active' and st != 'not_coming':
                    reserved_core += 1
                    
        total_occupied = len(active_regs) + reserved_core
        
        status = 'active'
        is_core = p_row[7] if len(p_row) > 7 else 0
        
        if is_core:
            status = 'active'
        elif total_occupied >= max_p:
            status = 'queue'
            
        pos = data.get('reg_pos', 'att')
        db.register_player(pid, target_cid, target_tid, pos, status=status)
        
        sent_success = await message.answer(tr.t("reg_success_named", lang_id).format(name=val), parse_mode="Markdown")
        
        # Cleanup messages
        ask_msg_id = data.get('ask_name_msg_id')
        if ask_msg_id and target_cid:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=ask_msg_id)
            except: pass
        try:
             await message.delete()
        except: pass
        
        # Auto-delete success message after 10s
        import asyncio
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent_success.message_id, delay_seconds=10))
        
        if data.get('poll_msg_id'):
             await utils.update_poll_message(chat_id=target_cid, thread_id=target_tid, message_id=data['poll_msg_id'])
             
    await state.clear()

@router.message(PlayerSelfRegister.waiting_for_attack)
async def player_self_attack(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        data = await state.get_data()
        skill = data.get('skill_level', '—')
        await state.update_data(attack=val)
        await message.answer(tr.t("ask_self_defense", lang_id).format(skill=skill))
        await state.set_state(PlayerSelfRegister.waiting_for_defense)
    except:
        await message.answer(tr.t("error_0_100", lang_id))

@router.message(PlayerSelfRegister.waiting_for_defense)
async def player_self_defense(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(defense=val)
        await message.answer(tr.t("ask_self_speed", lang_id))
        await state.set_state(PlayerSelfRegister.waiting_for_speed)
    except:
        await message.answer(tr.t("error_0_100", lang_id))

@router.message(PlayerSelfRegister.waiting_for_speed)
async def player_self_speed(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(speed=val)
        await message.answer(tr.t("ask_self_gk", lang_id))
        await state.set_state(PlayerSelfRegister.waiting_for_gk)
    except:
        await message.answer(tr.t("error_0_100", lang_id))

@router.message(PlayerSelfRegister.waiting_for_gk)
async def player_self_gk(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        data = await state.get_data()
        db.create_player_full(message.from_user.id, data['user_name'], cid, tid, data['attack'], data['defense'], data['speed'], val)
        p = db.get_player_by_user_id(message.from_user.id, cid, tid)
        reg_cid = data.get('poll_chat_id', cid)
        reg_tid = data.get('poll_thread_id', tid)
        db.register_player(p[0], reg_cid, reg_tid, data['reg_pos'])
        await message.answer(tr.t("self_reg_success", lang_id))
        if data.get('poll_chat_id') and data.get('poll_msg_id'):
            await utils.update_poll_message(chat_id=data['poll_chat_id'], thread_id=data.get('poll_thread_id', 0), message_id=data['poll_msg_id'])
        await state.clear()
    except Exception as e:
        logger.error(f"Error in player self-reg: {e}")
        await message.answer(tr.t("error_save_profile", lang_id))
