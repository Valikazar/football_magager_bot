import random
import logging
import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.base import StorageKey

import database as db
import keyboards as kb
from states import LegionnaireCreate, PlayerStatEdit, MatchSettings, CaptainSelection, MatchResult, PlayerRating, MatchScoring, PairsBuilder, MatchEvents, InitialSetup
import utils
import translations as tr
from init_bot import bot

logger = logging.getLogger(__name__)
router = Router()

# Helper for handlers
def get_ids(event):
    return utils.get_ids(event)

# --- FSM HANDLERS (Legionnaires) ---

@router.message(LegionnaireCreate.waiting_for_name)
async def legionnaire_name(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    logger.info(f"FSM: Received name '{message.text}' from user {message.from_user.id}")
    data = await state.get_data()
    cid = data.get('chat_id') or message.chat.id
    tid = data.get('thread_id', 0)
    await state.update_data(name=message.text, chat_id=cid, thread_id=tid)
    lang_id = utils.get_chat_lang(cid, tid)
    sent = await message.answer(tr.t("enter_att_for", lang_id).format(name=message.text))
    await utils.track_msg(state, sent.message_id)
    await state.set_state(LegionnaireCreate.waiting_for_attack)

@router.message(LegionnaireCreate.waiting_for_attack)
async def legionnaire_attack(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    cid = data.get('chat_id') or message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(attack=val)
        sent = await message.answer(tr.t("enter_def", lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(LegionnaireCreate.waiting_for_defense)
    except ValueError:
        sent = await message.answer(tr.t("error_0_100", lang_id))
        await utils.track_msg(state, sent.message_id)

@router.message(LegionnaireCreate.waiting_for_defense)
async def legionnaire_defense(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    cid = data.get('chat_id') or message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(defense=val)
        sent = await message.answer(tr.t("enter_spd", lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(LegionnaireCreate.waiting_for_speed)
    except ValueError:
        sent = await message.answer(tr.t("error_0_100", lang_id))
        await utils.track_msg(state, sent.message_id)

@router.message(LegionnaireCreate.waiting_for_speed)
async def legionnaire_speed(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    cid = data.get('chat_id') or message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(speed=val)
        sent = await message.answer(tr.t("enter_gk", lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(LegionnaireCreate.waiting_for_gk)
    except ValueError:
        sent = await message.answer(tr.t("error_0_100", lang_id))
        await utils.track_msg(state, sent.message_id)

@router.message(LegionnaireCreate.waiting_for_gk)
async def legionnaire_gk(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    if data.get('processing'): return

    # Use state data for correct language (original group/topic, not private chat)
    cid = data.get('chat_id') or message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)

    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(processing=True)
        pid = db.create_legionnaire(data['name'], cid, tid, data['attack'], data['defense'], data['speed'], val)
        await state.update_data(player_id=pid, chat_id=cid, thread_id=tid)

        
        if data.get('is_admin_mode'):
            updated_players = db.get_legionnaires(cid, tid)
            await state.set_state(None)
            back_cb = f"admin_player_mgmt_{cid}_{tid}"
            await message.answer(
                tr.t("legionnaire_created_list", lang_id).format(name=data['name']),
                reply_markup=kb.get_legionnaire_list_kb(updated_players, action_prefix="adm_myth_edit_", create_callback="create_new_legionnaire_admin", back_callback=back_cb, lang_id=lang_id), 
                parse_mode="Markdown"
            )
            await utils.cleanup_msgs(message.chat.id, state)
        else:
            builder = InlineKeyboardBuilder()
            builder.button(text=tr.t("reg_att", lang_id), callback_data=f"myth_reg_att_{pid}")
            builder.button(text=tr.t("reg_def", lang_id), callback_data=f"myth_reg_def_{pid}")
            builder.button(text=tr.t("reg_gk", lang_id), callback_data=f"myth_reg_gk_{pid}")
            builder.adjust(3)
            sent = await message.answer(tr.t("adding_legionnaire", lang_id).format(name=data['name']), reply_markup=builder.as_markup())
            await utils.track_msg(state, sent.message_id)
            await state.set_state(None)
    except ValueError:
        sent = await message.answer(tr.t("error_0_100", lang_id))
        await utils.track_msg(state, sent.message_id)
    except Exception as e:
        await state.update_data(processing=False)
        logger.error(f"Error saving legionnaire: {e}")
        cid, tid = get_ids(message)
        lang_id = utils.get_chat_lang(cid, tid)
        await message.answer(tr.t("error_save", lang_id))

# --- PLAYER EDIT HANDLERS ---

@router.callback_query(F.data.startswith("edit_player_stats_"))
async def start_player_edit(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[3])
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    skill_id = settings.get('skill_level_id')
    skill = db.get_label_by_id("skill_levels", skill_id, lang_id) if skill_id else "—"
    p = db.get_player_by_id(pid, cid, tid)
    # p[2] is display_name or name
    await state.update_data(edit_pid=pid, edit_skill=skill, info_msg_id=callback.message.message_id, original_name=p[2])
    msg_text = f"{tr.t('editing_player', lang_id).format(name=p[2])}\n\n{tr.t('enter_new_name', lang_id).format(name=p[2])}"
    sent = await callback.message.answer(msg_text, parse_mode="Markdown")
    await utils.track_msg(state, sent.message_id)
    await state.set_state(PlayerStatEdit.waiting_for_name)
    await callback.answer()

@router.message(PlayerStatEdit.waiting_for_name)
async def edit_player_name_msg(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    new_name = message.text.strip() if message.text else ""
    
    if not new_name:
         data = await state.get_data()
         new_name = data.get('original_name')
         
    await state.update_data(name=new_name)
    data = await state.get_data()
    cid = data.get('chat_id') or message.chat.id
    tid = data.get('thread_id') or 0
    lang_id = utils.get_chat_lang(cid, tid)
    sent = await message.answer(tr.t('enter_att', lang_id))
    await utils.track_msg(state, sent.message_id)
    await state.set_state(PlayerStatEdit.waiting_for_attack)

@router.message(PlayerStatEdit.waiting_for_attack)
async def edit_player_attack_msg(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id', message.chat.id), data.get('thread_id', 0))
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(attack=val)
        sent = await message.answer(tr.t('enter_def', lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(PlayerStatEdit.waiting_for_defense)
    except ValueError:
        await message.answer(tr.t('error_0_100', lang_id))

@router.message(PlayerStatEdit.waiting_for_defense)
async def edit_player_defense_msg(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id', message.chat.id), data.get('thread_id', 0))
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(defense=val)
        sent = await message.answer(tr.t('enter_spd', lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(PlayerStatEdit.waiting_for_speed)
    except ValueError:
        await message.answer(tr.t('error_0_100', lang_id))

@router.message(PlayerStatEdit.waiting_for_speed)
async def edit_player_speed_msg(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id', message.chat.id), data.get('thread_id', 0))
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        await state.update_data(speed=val)
        sent = await message.answer(tr.t('enter_gk', lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(PlayerStatEdit.waiting_for_gk)
    except ValueError:
        await message.answer(tr.t('error_0_100', lang_id))

@router.message(PlayerStatEdit.waiting_for_gk)
async def edit_player_gk_msg(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    try:
        val = int(message.text)
        if not (0 <= val <= 100): raise ValueError
        data = await state.get_data()
        pid = data['edit_pid']
        cid, tid = get_ids(message)
        target_cid = data.get('chat_id', cid)
        target_tid = data.get('thread_id', tid)
        db.update_player_display_name(pid, target_cid, target_tid, data['name'])
        db.update_player_stats_full(pid, target_cid, target_tid, data['attack'], data['defense'], data['speed'], val)
        
        if data.get('is_legionnaire_view') and data.get('info_msg_id'):
            try:
                target_lang_id = utils.get_chat_lang(target_cid, target_tid)
                text = f"{tr.t('legionnaire_single', target_lang_id)}: **{data['name']}**\n"
                text += f"{tr.t('stat_att_short', target_lang_id)}: {data['attack']} | {tr.t('stat_def_short', target_lang_id)}: {data['defense']}\n"
                text += f"{tr.t('stat_spd_short', target_lang_id)}: {data['speed']} | {tr.t('stat_gk_short', target_lang_id)}: {val}\n\n"
                text += tr.t('choose_action', target_lang_id)
                builder = InlineKeyboardBuilder()
                builder.button(text=tr.t('btn_edit', target_lang_id), callback_data=f"edit_player_stats_{pid}")
                builder.button(text=tr.t('btn_back', target_lang_id), callback_data="admin_list_legionnaires")
                builder.adjust(1)
                await bot.edit_message_text(text, chat_id=message.chat.id, message_id=data['info_msg_id'], reply_markup=builder.as_markup(), parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to update info message: {e}")

        target_lang_id = utils.get_chat_lang(target_cid, target_tid)
        await message.answer(tr.t('player_updated', target_lang_id).format(name=data['name']), parse_mode="Markdown")
        poll_id = data.get('poll_msg_id')
        exclude = [poll_id] if poll_id else []
        await utils.cleanup_msgs(message.chat.id, state, exclude_ids=exclude)
        await state.clear()
        await state.update_data(chat_id=target_cid, thread_id=target_tid)
    except ValueError:
        data = await state.get_data()
        lang_id = utils.get_chat_lang(data.get('chat_id', message.chat.id), data.get('thread_id', 0))
        await message.answer(tr.t('error_0_100', lang_id))

# --- COMMANDS ---

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):

    if message.chat.type == 'private':
        data = await state.get_data()
        lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id', 0))
        if data.get('chat_id'):
            try:
                await message.delete()
            except:
                pass
            return await show_admin_settings_menu(message, state)
        # Should delete even if error? Yes.
        try:
            await message.delete()
        except:
            pass
        return await message.answer(tr.t("use_admin_in_group_topic", lang_id))

    if not await utils.is_admin(message):
        try:
            await message.delete()
        except:
            pass
        cid, tid = get_ids(message)
        lang_id = utils.get_chat_lang(cid, tid)
        sent = await message.answer(tr.t("no_admin_rights", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    
    cid, tid = get_ids(message)
    user_id = message.from_user.id
    lang_id = utils.get_chat_lang(cid, tid)
    pm_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    from init_bot import dp
    pm_state = FSMContext(storage=dp.storage, key=pm_key)
    await pm_state.update_data(chat_id=cid, thread_id=tid)
    
    try:
        title = tr.t("admin_panel_title", lang_id)
        desc = tr.t("admin_panel_desc", lang_id)
        group_name = message.chat.title if message.chat.type != 'private' else (data.get('chat_title') or "Unknown Group")
        group_info = f"{tr.t('group_label', lang_id)}: {group_name}\nID: {tid}" 
        text = f"{title}\n{group_info}\n\n{desc}"
        bot_user = await bot.get_me()
        await bot.send_message(user_id, text, reply_markup=kb.get_admin_main_kb(cid, tid, lang_id), parse_mode="Markdown")
        url = f"https://t.me/{bot_user.username}"
        builder = InlineKeyboardBuilder()
        builder.button(text=tr.t("go_to_settings", lang_id), url=url)
        sent = await message.reply(tr.t("admin_panel_sent", lang_id), reply_markup=builder.as_markup())
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
    except Exception as e:
        logger.error(f"Failed to send admin panels to {user_id}: {e}")
        bot_user = await bot.get_me()
        url = f"https://t.me/{bot_user.username}?start=admin_{cid}_{tid}"
        builder = InlineKeyboardBuilder()
        builder.button(text=tr.t("open_settings", lang_id), url=url)
        sent = await message.reply(tr.t("go_to_settings", lang_id), reply_markup=builder.as_markup())
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=60))
    
    try:
        await message.delete()
    except:
        pass

@router.message(Command("clear"))
async def cmd_clear(message: Message, state: FSMContext):
    if message.chat.type == 'private':
        return  # Ignore in private chat
    if not await utils.is_admin(message, state):
        cid, tid = get_ids(message)
        lang_id = utils.get_chat_lang(cid, tid)
        sent = await message.answer(tr.t("no_admin_rights", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    
    # Same as process_clear but for command
    cid, tid = get_ids(message)
    utils.perform_full_clear(cid, tid)
    
    lang_id = utils.get_chat_lang(cid, tid)
    await message.answer(tr.t("match_cleared", lang_id))
    try:
        await message.delete()
    except:
        pass

# --- PLAYER MANAGEMENT ---

@router.callback_query(F.data.startswith("admin_player_mgmt"))
async def admin_player_mgmt(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Player Mgmt: Received callback {callback.data} from user {callback.from_user.id}")
    
    # First, try to get cid/tid from state (for private chat admin panel)
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    # If not in state, get from callback (for group chat)
    if not cid:
        cid, tid = get_ids(callback)
    
    logger.info(f"Player Mgmt: Initial cid={cid}, tid={tid}")
    
    if not await utils.is_admin(callback, state): 
        lang_id = utils.get_chat_lang(cid, tid)
        logger.warning(f"Player Mgmt: User {callback.from_user.id} is not admin for chat {cid}/{tid}")
        return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
    
    # Parse callback data for potential cid/tid override
    parts = callback.data.split("_")
    if len(parts) >= 5:
        try:
            cid = int(parts[3])
            tid = int(parts[4])
            logger.info(f"Player Mgmt: Updated cid={cid}, tid={tid} from callback data")
            await state.update_data(chat_id=cid, thread_id=tid)
        except: pass
    lang_id = utils.get_chat_lang(cid, tid)
    
    logger.info(f"Player Mgmt: Showing menu with cid={cid}, tid={tid}")
    
    await callback.message.edit_text(
        f"**{tr.t('admin_player_mgmt_title', lang_id)}**", 
        reply_markup=kb.get_admin_player_mgmt_kb(cid, tid, lang_id), 
        parse_mode="Markdown"
    )
    logger.info(f"Player Mgmt: Menu displayed successfully")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_main_menu_back"))
async def admin_main_menu_back(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) >= 6:
        try:
             cid = int(parts[4])
             tid = int(parts[5])
             await state.update_data(chat_id=cid, thread_id=tid)
        except: pass
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    if not cid:
        cid, tid = get_ids(callback)
        
    lang_id = utils.get_chat_lang(cid, tid)
    title = tr.t("admin_panel_title", lang_id)
    desc = tr.t("admin_panel_desc", lang_id)
    await callback.message.edit_text(
        f"{title}\n\n{desc}",
        reply_markup=kb.get_admin_main_kb(cid, tid, lang_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_mgmt_regular"))
async def admin_mgmt_regular(callback: CallbackQuery, state: FSMContext):
    # First, try to get cid/tid from state (for private chat admin panel)
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    # If not in state, get from callback (for group chat)
    if not cid:
        cid, tid = get_ids(callback)
    
    if not await utils.is_admin(callback, state): 
        lang_id = utils.get_chat_lang(cid, tid)
        return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
    
    # Parse callback data for potential cid/tid override
    parts = callback.data.split("_")
    if len(parts) >= 5:
        try:
             cid = int(parts[3])
             tid = int(parts[4])
             await state.update_data(chat_id=cid, thread_id=tid)
        except: pass
    lang_id = utils.get_chat_lang(cid, tid)
    players = db.get_chat_players(cid, tid)
    header = tr.t("admin_regular_players", lang_id)
    if not players:
        try:
            return await callback.message.edit_text(
                f"**{header}**\n\n{tr.t('list_empty', lang_id)}", 
                reply_markup=kb.get_admin_player_mgmt_kb(cid, tid, lang_id), 
                parse_mode="Markdown"
            )
        except Exception:
            return await callback.answer()
    try:
        await callback.message.edit_text(
            f"**{header}**\n\n{tr.t('chat_players_list', lang_id)}", 
            reply_markup=kb.get_chat_players_kb(players, lang_id), 
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin_add_legionnaire")
async def process_quick_manage_entry(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    if not cid:
        cid, tid = get_ids(callback)
    
    lang_id = utils.get_chat_lang(cid, tid)
    
    if not await utils.is_admin(callback, state): 
        return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
    
    # Store context
    await state.update_data(chat_id=cid, thread_id=tid)
    
    # If in group, send to PM
    if callback.message.chat.type != 'private':
        try:
             # Send "Manage" menu to PM
             await bot.send_message(
                 callback.from_user.id, 
                 tr.t("admin_player_mgmt", lang_id), # "Player Management"
                 reply_markup=kb.get_quick_manage_kb(cid, tid, lang_id)
             )
             await callback.answer(tr.t("admin_panel_sent", lang_id), show_alert=True)
        except Exception as e:
             await callback.answer(tr.t("no_pm_error", lang_id), show_alert=True)
    else:
        # Already in private
        await callback.message.edit_text(
            tr.t("admin_player_mgmt", lang_id),
            reply_markup=kb.get_quick_manage_kb(cid, tid, lang_id)
        )
        await callback.answer()

@router.callback_query(F.data.startswith("admin_quick_manage_"))
async def process_quick_manage_menu(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    cid = int(parts[3])
    tid = int(parts[4])
    lang_id = utils.get_chat_lang(cid, tid)
    
    await callback.message.edit_text(
         tr.t("admin_player_mgmt", lang_id),
         reply_markup=kb.get_quick_manage_kb(cid, tid, lang_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_quick_add_leg_"))
async def process_quick_add_leg(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    cid = int(parts[4])
    tid = int(parts[5])
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Store context for finish_legionnaire
    await state.update_data(chat_id=cid, thread_id=tid)
    
    # Use existing legionnaire list KB but point back to simple management
    # Note: existing get_legionnaire_list_kb uses 'admin_player_mgmt' as back callback.
    # We might want to customize back callback.
    # We'll use a custom back_callback arg in get_legionnaire_list_kb if we update it, or just handle 'admin_player_mgmt' to check context?
    # Simpler: Modify get_legionnaire_list_kb in keyboards.py to accept back_callback (DONE in step 225? No, I reused it).
    # Ah, get_legionnaire_list_kb HAS back_callback param!
    
    back_cb = f"admin_quick_manage_{cid}_{tid}"
    players = db.get_legionnaires(cid, tid)
    
    # Re-use standard "myth_reg_" prefix? Yes, reusing finish_legionnaire
    # Reuse "admin_add_legionnaire" logic basically
    await callback.message.edit_text(
        tr.t("select_legionnaire_for_match", lang_id), 
        reply_markup=kb.get_legionnaire_list_kb(players, lang_id=lang_id, back_callback=back_cb), 
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_quick_add_real_"))
async def process_quick_add_real(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    cid = int(parts[4])
    tid = int(parts[5])
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Store context for finish_real_player_registration
    await state.update_data(chat_id=cid, thread_id=tid)
    
    # Get all players from player_stats
    all_players = db.get_all_players_with_stats(cid, tid)
    
    # Filter for only players with real Telegram accounts (user_id not NULL)
    real_players = [p for p in all_players if p[1] is not None]  # p[1] is user_id
    
    # Get currently registered players
    regs = db.get_registrations(cid, tid)
    registered_ids = {r[0] for r in regs}
    
    # Filter out registered players
    unregistered = [p for p in real_players if p[0] not in registered_ids]
    
    if not unregistered:
        await callback.answer("Все игроки уже записаны!", show_alert=True)
        return
    
    back_cb = f"admin_quick_manage_{cid}_{tid}"
    await callback.message.edit_text(
        tr.t("select_real_player", lang_id), 
        reply_markup=kb.get_real_players_list_kb(unregistered, cid, tid, lang_id=lang_id, back_callback=back_cb)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_real_select_"))
async def process_real_player_select(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    pid = int(parts[3])
    cid = int(parts[4])
    tid = int(parts[5])
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Store player ID for registration
    await state.update_data(selected_real_player_id=pid, chat_id=cid, thread_id=tid)
    
    # Get player info
    p = db.get_player_by_id(pid, cid, tid)
    
    # Show position selection
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("reg_att", lang_id), callback_data=f"real_reg_att_{pid}_{cid}_{tid}")
    builder.button(text=tr.t("reg_def", lang_id), callback_data=f"real_reg_def_{pid}_{cid}_{tid}")
    builder.button(text=tr.t("reg_gk", lang_id), callback_data=f"real_reg_gk_{pid}_{cid}_{tid}")
    builder.button(text=tr.t("btn_back", lang_id), callback_data=f"admin_quick_add_real_{cid}_{tid}")
    builder.adjust(1)
    
    text = f"**{p[2]}**\n\n{tr.t('choose_position', lang_id)}"
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("real_reg_"))
async def finish_real_player_registration(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    pos = parts[2]  # att, def, or gk
    pid = int(parts[3])
    cid = int(parts[4])
    tid = int(parts[5])
    
    # Check max players to decide status
    settings = db.get_match_settings(cid, tid)
    req_count = settings.get('player_count', 12)
    regs = db.get_registrations(cid, tid)
    # Calculate Occupied (Active + Reserved Core)
    active_regs = [r for r in regs if r[9] == 'active' and r[0] != pid]
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
    
    status = 'active'
    if total_occupied >= req_count:
        status = 'queue'
        
    db.register_player(pid, cid, tid, pos, status=status)
    lang_id = utils.get_chat_lang(cid, tid)
    
    text = tr.t("legionnaire_added_success", lang_id)  # Reuse translation
    if status == 'queue':
        text += f" ({tr.t('status_queue', lang_id)})"
        
    await callback.answer(text, show_alert=True)

    # Update poll
    await utils.update_poll_message(chat_id=cid, thread_id=tid)
    
    # Return to main management menu
    # Modify callback data to trick process_quick_manage into thinking it was called directly
    # format: admin_quick_manage_{cid}_{tid}
    new_data = f"admin_quick_manage_{cid}_{tid}"
    # Create a new callback object or just call the function if logic permits, 
    # but since it uses callback.data, we better just edit the message directly here 
    # OR call the handler. Calling handler is cleaner but we need to patch callback.data.

    # Easier way: just render the menu here.
    await callback.message.edit_text(
        tr.t("admin_player_mgmt", lang_id), 
        reply_markup=kb.get_quick_manage_kb(cid, tid, lang_id)
    )


@router.callback_query(F.data.startswith("admin_quick_rem_list_"))
async def process_quick_rem_list(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    cid = int(parts[4])
    tid = int(parts[5])
    lang_id = utils.get_chat_lang(cid, tid)
    
    regs = db.get_registrations(cid, tid)
    # regs: [id, user_id, name, ..., status(9)]
    
    await callback.message.edit_text(
        tr.t("reg_cancel", lang_id), # "Cancel" label or "Select to remove"
        reply_markup=kb.get_remove_player_kb(regs, cid, tid, lang_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_force_rem_"))
async def process_force_remove(callback: CallbackQuery, state: FSMContext):
    logger.info(f"ForceRemove: {callback.data}")
    parts = callback.data.split("_")
    pid = int(parts[3])
    cid = int(parts[4])
    tid = int(parts[5])
    
    db.unregister_player(pid, cid, tid)
    
    logger.info("ForceRemove: Unregistered. Calling QueueCheck...")
    # Check queue first (so status updates to pending if promoted)
    await utils.check_queue_promotion(cid, tid)
    logger.info("ForceRemove: QueueCheck done. Calling UpdatePoll...")
    
    # Update poll after queue check
    await utils.update_poll_message(chat_id=cid, thread_id=tid)
    
    # Refresh list
    await process_quick_rem_list(callback, state) # Go back to list
    
@router.callback_query(F.data.startswith("admin_list_legionnaires"))
async def start_legionnaire_mgmt(callback: CallbackQuery, state: FSMContext):
    # First, try to get cid/tid from state (for private chat admin panel)
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    # If not in state, get from callback (for group chat)
    if not cid:
        cid, tid = get_ids(callback)
    
    if not await utils.is_admin(callback, state): 
        lang_id = utils.get_chat_lang(cid, tid)
        return await callback.answer(tr.t("no_admin_rights", lang_id))
    
    # Parse callback data for potential cid/tid override
    parts = callback.data.split("_")
    if len(parts) >= 5:
        try:
             cid = int(parts[3])
             tid = int(parts[4])
             await state.update_data(chat_id=cid, thread_id=tid)
        except: pass
    lang_id = utils.get_chat_lang(cid, tid)
    players = db.get_legionnaires(cid, tid)
    back_cb = f"admin_player_mgmt_{cid}_{tid}"
    header = tr.t("admin_legionnaires", lang_id)
    sub = tr.t("select_legionnaire", lang_id)
    await callback.message.edit_text(
        f"**{header}**\n\n{sub}", 
        reply_markup=kb.get_legionnaire_list_kb(players, action_prefix="adm_myth_edit_", create_callback="create_new_legionnaire_admin", back_callback=back_cb, lang_id=lang_id), 
        parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("sel_reg_"))
async def sel_reg_player(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    if not cid:
        cid, tid = get_ids(callback)
        
    settings = db.get_match_settings(cid, tid)
    skill_level_id = settings.get('skill_level_id')
    lang_id = utils.get_chat_lang(cid, tid)
    
    if skill_level_id:
        skill = db.get_label_by_id('skill_levels', skill_level_id, lang_id)
    else:
        skill = settings.get('skill_level', '—')
        
    p = db.get_player_by_id(pid, cid, tid)
    text = f"{tr.t('player_label', lang_id)}: **{p[2]}**\n"
    text += f"{tr.t('stat_att_short', lang_id)}: {p[3]} | {tr.t('stat_def_short', lang_id)}: {p[4]}\n"
    text += f"{tr.t('stat_spd_short', lang_id)}: {p[5]} | {tr.t('stat_gk_short', lang_id)}: {p[6]}\n\n"
    text += tr.t('choose_action', lang_id)
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t('btn_edit', lang_id), callback_data=f"edit_player_stats_{pid}")
    builder.button(text=tr.t("reg_cancel", lang_id), callback_data=f"admin_force_rem_{pid}_{cid}_{tid}")
    builder.button(text=tr.t('btn_back', lang_id), callback_data="admin_mgmt_regular")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.in_({"create_new_legionnaire", "create_new_legionnaire_admin"}))
async def create_new_legionnaire_cb(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    if not cid:
        cid, tid = get_ids(callback)
        
    lang_id = utils.get_chat_lang(cid, tid)
    is_admin_mode = (callback.data == "create_new_legionnaire_admin")
    await state.update_data(is_admin_mode=is_admin_mode, processing=False, chat_id=cid, thread_id=tid)
    sent = await callback.message.answer(tr.t("enter_legionnaire_name", lang_id))
    await utils.track_msg(state, sent.message_id)
    await state.set_state(LegionnaireCreate.waiting_for_name)
    await callback.answer()

@router.callback_query(F.data.startswith("sel_myth_"))
async def sel_myth_cb(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    if not cid:
        cid, tid = get_ids(callback)
        
    lang_id = utils.get_chat_lang(cid, tid)
    pid = int(callback.data.split("_")[2])
    p = db.get_player_by_id(pid, cid, tid)
    await state.update_data(player_id=pid, chat_id=cid, thread_id=tid)
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t("reg_att", lang_id), callback_data=f"myth_reg_att_{pid}")
    builder.button(text=tr.t("reg_def", lang_id), callback_data=f"myth_reg_def_{pid}")
    builder.button(text=tr.t("reg_gk", lang_id), callback_data=f"myth_reg_gk_{pid}")
    builder.adjust(3)
    await utils.track_msg(state, callback.message.message_id)
    await callback.message.edit_text(tr.t("adding_legionnaire", lang_id).format(name=p[2]), reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("adm_myth_edit_"))
async def adm_myth_edit_cb(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[3])
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    if not cid:
        cid, tid = get_ids(callback)
        
    settings = db.get_match_settings(cid, tid)
    skill_level_id = settings.get('skill_level_id')
    lang_id = utils.get_chat_lang(cid, tid)
    
    if skill_level_id:
        skill = db.get_label_by_id('skill_levels', skill_level_id, lang_id)
    else:
        skill = settings.get('skill_level', '—')
        
    p = db.get_player_by_id(pid, cid, tid)
    text = f"{tr.t('legionnaire_single', lang_id)}: **{p[2]}**\n"
    text += f"{tr.t('stat_att_short', lang_id)}: {p[3]} | {tr.t('stat_def_short', lang_id)}: {p[4]}\n"
    text += f"{tr.t('stat_spd_short', lang_id)}: {p[5]} | {tr.t('stat_gk_short', lang_id)}: {p[6]}\n\n"
    text += tr.t('choose_action', lang_id)
    builder = InlineKeyboardBuilder()
    builder.button(text=tr.t('btn_edit', lang_id), callback_data=f"edit_player_stats_{pid}")
    builder.button(text=tr.t('btn_back', lang_id), callback_data="admin_list_legionnaires")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()



@router.callback_query(F.data.startswith("admin_core_team_"))
async def show_core_team_menu(callback: CallbackQuery, state: FSMContext):
    """Show Core Team submenu"""
    logger.info(f"Core Team Menu: Received callback {callback.data} from user {callback.from_user.id}")
    
    parts = callback.data.split("_")
    cid = int(parts[3])
    tid = int(parts[4])
    
    logger.info(f"Core Team Menu: Parsed cid={cid}, tid={tid}")
    
    if not await utils.is_admin(callback, state):
        lang_id = utils.get_chat_lang(cid, tid)
        logger.warning(f"Core Team Menu: User {callback.from_user.id} is not admin for chat {cid}/{tid}")
        return await callback.answer(tr.t("no_admin_rights", lang_id))
    
    await state.update_data(chat_id=cid, thread_id=tid)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    
    logger.info(f"Core Team Menu: Settings loaded, core_team_mode={settings.get('core_team_mode', 0)}")
    
    await callback.message.edit_text(
        tr.t("admin_core_team_menu", lang_id),
        reply_markup=kb.get_core_team_menu_kb(cid, tid, lang_id, settings),
        parse_mode="Markdown"
    )
    logger.info(f"Core Team Menu: Menu displayed successfully")
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_core_mode_"))
async def toggle_core_team_mode(callback: CallbackQuery, state: FSMContext):
    """Toggle Core Team mode on/off"""
    logger.info(f"Toggle Core Mode: Received callback {callback.data} from user {callback.from_user.id}")
    
    parts = callback.data.split("_")
    cid = int(parts[3])
    tid = int(parts[4])
    
    logger.info(f"Toggle Core Mode: Parsed cid={cid}, tid={tid}")
    
    if not await utils.is_admin(callback, state):
        lang_id = utils.get_chat_lang(cid, tid)
        logger.warning(f"Toggle Core Mode: User {callback.from_user.id} is not admin for chat {cid}/{tid}")
        return await callback.answer(tr.t("no_admin_rights", lang_id))
    
    settings = db.get_match_settings(cid, tid)
    current_mode = settings.get('core_team_mode', 0)
    new_mode = 0 if current_mode else 1
    
    logger.info(f"Toggle Core Mode: Changing from {current_mode} to {new_mode}")
    
    db.update_match_settings(cid, tid, 'core_team_mode', new_mode)
    
    # Refresh menu
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    
    logger.info(f"Toggle Core Mode: Updated settings, new mode={settings.get('core_team_mode', 0)}")
    
    try:
        await callback.message.edit_text(
            tr.t("admin_core_team_menu", lang_id),
            reply_markup=kb.get_core_team_menu_kb(cid, tid, lang_id, settings),
            parse_mode="Markdown"
        )
        logger.info(f"Toggle Core Mode: Menu refreshed successfully")
    except TelegramBadRequest:
        logger.warning(f"Toggle Core Mode: Message content didn't change")
        pass  # Message content didn't change
    await callback.answer()

@router.callback_query(F.data.startswith("select_core_players_"))
async def show_core_players_selection(callback: CallbackQuery, state: FSMContext):
    """Show bulk player selection interface"""
    logger.info(f"Core Players Selection: Received callback {callback.data} from user {callback.from_user.id}")
    
    parts = callback.data.split("_")
    cid = int(parts[3])
    tid = int(parts[4])
    
    logger.info(f"Core Players Selection: Parsed cid={cid}, tid={tid}")
    
    if not await utils.is_admin(callback, state):
        lang_id = utils.get_chat_lang(cid, tid)
        logger.warning(f"Core Players Selection: User {callback.from_user.id} is not admin for chat {cid}/{tid}")
        return await callback.answer(tr.t("no_admin_rights", lang_id))
    
    lang_id = utils.get_chat_lang(cid, tid)
    
    logger.info(f"Core Players Selection: Displaying player selection menu")
    
    await callback.message.edit_text(
        tr.t("select_core_players_prompt", lang_id),
        reply_markup=kb.get_core_players_selection_kb(cid, tid, lang_id),
        parse_mode="Markdown"
    )
    logger.info(f"Core Players Selection: Menu displayed successfully")
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_player_core_"))
async def toggle_player_core_bulk(callback: CallbackQuery, state: FSMContext):
    """Toggle player Core status from bulk selection interface"""
    logger.info(f"Toggle Player Core: Received callback {callback.data} from user {callback.from_user.id}")
    
    parts = callback.data.split("_")
    pid = int(parts[3])
    cid = int(parts[4])
    tid = int(parts[5])
    
    logger.info(f"Toggle Player Core: Parsed pid={pid}, cid={cid}, tid={tid}")
    
    if not await utils.is_admin(callback, state):
        lang_id = utils.get_chat_lang(cid, tid)
        logger.warning(f"Toggle Player Core: User {callback.from_user.id} is not admin for chat {cid}/{tid}")
        return await callback.answer(tr.t("no_admin_rights", lang_id))
    
    # Get current status
    p = db.get_player_by_id(pid, cid, tid)
    current_core = p[7] if len(p) > 7 else 0
    new_core = 0 if current_core else 1
    
    logger.info(f"Toggle Player Core: Player {p[2]} (id={pid}) changing from core={current_core} to core={new_core}")
    
    db.set_player_core(pid, cid, tid, new_core)
    
    # Refresh selection interface
    lang_id = utils.get_chat_lang(cid, tid)
    
    try:
        await callback.message.edit_text(
            tr.t("select_core_players_prompt", lang_id),
            reply_markup=kb.get_core_players_selection_kb(cid, tid, lang_id),
            parse_mode="Markdown"
        )
        logger.info(f"Toggle Player Core: Selection interface refreshed successfully")
    except TelegramBadRequest:
        logger.warning(f"Toggle Player Core: Message content didn't change")
        pass  # Message content didn't change
    await callback.answer()

@router.callback_query(F.data.startswith("myth_reg_"))
async def finish_legionnaire(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id', 0)
    pos = callback.data.split("_")[2]
    pid = int(callback.data.split("_")[3])
    if not db.player_has_stats(pid, cid, tid):
        db.upsert_player_stats(pid, cid, tid, 50, 50, 50, 50)
    
    # Check max players to decide status
    settings = db.get_match_settings(cid, tid)
    req_count = settings.get('player_count', 12)
    regs = db.get_registrations(cid, tid)
    # Calculate Occupied (Active + Reserved Core)
    active_regs = [r for r in regs if r[9] == 'active' and r[0] != pid]
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
    
    status = 'active'
    if total_occupied >= req_count:
        status = 'queue'
        
    db.register_player(pid, cid, tid, pos, status=status)
    lang_id = utils.get_chat_lang(cid, tid)
    
    msg_key = "legionnaire_added_success"
    if status == 'queue':
        msg_key = "queue_joined" # Using generic queue message or we can add specific one
        
    # Ideally should differentiate message
    text = tr.t("legionnaire_added_success", lang_id)
    if status == 'queue':
        text += f" ({tr.t('status_queue', lang_id)})"
        
    # Send success notification (temporary or just alert?)
    # User wants menu to stay.
    # We can answer with alert=True for success?
    await callback.answer(text, show_alert=True)

    poll_id = data.get("poll_msg_id")
    if poll_id:
        await utils.update_poll_message(chat_id=cid, thread_id=tid, message_id=poll_id)
    else:
        await utils.update_poll_message(chat_id=cid, thread_id=tid)

    # Return to Legionnaire List
    # We need to decide which list? 
    # If we came from Quick Manage, back_cb should be quick manage.
    # If from main admin, back_cb should be admin_player_mgmt.
    # We can infer or just check state?
    # Quick Manage sets 'chat_id' in state usually.
    # Let's default to "admin_list_legionnaires" style but checking if we need special back button?
    # Actually, reusing `process_quick_add_leg` logic is good.
    
    # Check if we are in Quick Manage mode (deep link)
    # Start payload sets poll_msg_id... 
    # Let's just use a generic "Back" that goes to the main player management?
    # Or better, show the list again with valid back button.
    
    back_cb = "admin_player_mgmt"
    # If we detected quick manage (e.g. if we are in PM but chat_id is diff)
    if callback.message.chat.type == 'private' and cid != callback.message.chat.id:
        back_cb = f"admin_quick_manage_{cid}_{tid}"
        
    players = db.get_legionnaires(cid, tid)
    await callback.message.edit_text(
        tr.t("select_legionnaire_for_match", lang_id), 
        reply_markup=kb.get_legionnaire_list_kb(players, lang_id=lang_id, back_callback=back_cb), 
        parse_mode="Markdown"
    )
    # We do NOT clear state because we might need cid/tid for next actions
    # But we should clear 'LegionnaireCreate' specific states if any were set?
    # Currently we are not in a specific state for selecting (we are in default state).
    # ensure no garbage in state?
    # await state.set_state(None)? 
    # Safe to keep data.

# --- SETTINGS MENU ---

async def show_admin_settings_menu(message: Message, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id') or message.chat.id
    tid = data.get('thread_id') or 0
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid) or {}
    
    skill_l = db.get_label_by_id("skill_levels", settings.get('skill_level_id'), lang_id)
    age_l = db.get_label_by_id("age_groups", settings.get('age_group_id'), lang_id)
    gender_l = db.get_label_by_id("genders", settings.get('gender_id'), lang_id)
    venue_l = db.get_label_by_id("venue_types", settings.get('venue_type_id'), lang_id)

    text = f"{tr.t('match_settings_title', lang_id)}\n\n"
    text += f"{tr.t('setting_players', lang_id)}: {settings.get('player_count', '—')}\n"
    text += f"{tr.t('setting_skill_level', lang_id)}: {skill_l}\n"
    text += f"{tr.t('setting_age', lang_id)}: {age_l}\n"
    text += f"{tr.t('setting_gender', lang_id)}: {gender_l}\n"
    text += f"{tr.t('setting_venue_type', lang_id)}: {venue_l}\n"
    text += f"{tr.t('setting_location', lang_id)}: {'✅' if settings.get('location_lat') else '—'}\n"
    text += f"{tr.t('setting_match_times', lang_id)}: {settings.get('match_times', '—')}\n"
    text += f"{tr.t('setting_season', lang_id)}: {settings.get('season_start', '—')} - {settings.get('season_end', '—')}\n"
    
    await message.answer(text, reply_markup=kb.get_admin_settings_kb(cid, tid, lang_id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_match_settings"))
async def process_admin_settings(callback: CallbackQuery, state: FSMContext):
    # First, try to get cid/tid from state (for private chat admin panel)
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    # If not in state, get from callback (for group chat)
    if not cid:
        cid, tid = get_ids(callback)
    
    if not await utils.is_admin(callback, state): 
        lang_id = utils.get_chat_lang(cid, tid)
        return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
    
    # Parse callback data for potential cid/tid override
    parts = callback.data.split("_")
    if len(parts) >= 5:
        try:
             cid = int(parts[3])
             tid = int(parts[4])
             await state.update_data(chat_id=cid, thread_id=tid)
        except: pass
    await show_admin_settings_menu(callback.message, state)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_bot_settings"))
async def process_admin_bot_settings(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    if not await utils.is_admin(callback, state): 
        lang_id = utils.get_chat_lang(cid, tid)
        return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
    parts = callback.data.split("_")
    if len(parts) >= 5:
        try:
             cid = int(parts[3])
             tid = int(parts[4])
             await state.update_data(chat_id=cid, thread_id=tid)
        except: pass
    # Re-fetch from state after potential update
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    lang_id = utils.get_chat_lang(cid, tid)
    text = f"{tr.t('bot_settings_title', lang_id)}\n\n"
    await callback.message.edit_text(text, reply_markup=kb.get_admin_bot_settings_kb(cid, tid, lang_id), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_payment"))
async def process_admin_payment(callback: CallbackQuery, state: FSMContext):
    # First, try to get cid/tid from state (for private chat admin panel)
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    
    # If not in state, get from callback (for group chat)
    if not cid:
        cid, tid = get_ids(callback)
    
    if not await utils.is_admin(callback, state): 
        lang_id = utils.get_chat_lang(cid, tid)
        return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
    
    # Parse callback data for potential cid/tid override
    parts = callback.data.split("_")
    if len(parts) >= 5:
        try:
             cid = int(parts[3])
             tid = int(parts[4])
             await state.update_data(chat_id=cid, thread_id=tid)
        except: pass
    
    # Get lang_id AFTER cid/tid are finalized
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    text = f"**{tr.t('admin_payment', lang_id)}**\n\n"
    text += f"{tr.t('setting_cost', lang_id)}: {settings.get('cost', '—')}\n"
    text += f"{tr.t('admin_reminders_settings', lang_id)}:\n"
    text += f"  - {tr.t('remind_before_game', lang_id)}: {'✅' if settings.get('remind_before_game') else '❌'}\n"
    text += f"  - {tr.t('remind_after_game', lang_id)}: {'✅' if settings.get('remind_after_game') else '❌'}\n"
    text += f"{tr.t('require_admin_confirmation', lang_id)}: {'✅' if settings.get('require_payment_confirmation') else '❌'}\n"
    
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_admin_payment_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    except Exception:
        pass  # Message content didn't change
    await callback.answer()

@router.callback_query(F.data.startswith("edit_cost_start_payment"))
async def edit_cost_payment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(cost_from="payment")
    await edit_cost_start(callback, state)

@router.callback_query(F.data.startswith("admin_edit_pay_details"))
async def edit_payment_details_start(callback: CallbackQuery, state: FSMContext):
    """Start FSM for entering payment details"""
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    lang_id = utils.get_chat_lang(cid, tid)
    
    await state.set_state(MatchSettings.waiting_for_payment_details)
    
    # Prompt the admin, showing the current details if any, or a default placeholder
    settings = db.get_match_settings(cid, tid)
    current = settings.get('payment_details') or tr.t("payment_details_default", lang_id)
    
    text = f"{tr.t('payment_details_prompt', lang_id)}\n\n`{current}`"
    sent = await callback.message.answer(text, parse_mode="Markdown")
    await utils.track_msg(state, sent.message_id)
    await callback.answer()

@router.message(MatchSettings.waiting_for_payment_details)
async def process_payment_details(message: Message, state: FSMContext):
    """Save payment details and return to payment menu"""
    await utils.track_msg(state, message.message_id)
    cid, tid = get_ids(message)
    db.update_match_settings(cid, tid, "payment_details", message.text)
    
    lang_id = utils.get_chat_lang(cid, tid)
    await message.answer(tr.t("settings_saved", lang_id))
    
    # Clear state but keep chat_id/thread_id for correctly refreshing the menu
    data = await state.get_data()
    new_data = {k: v for k, v in data.items() if k in ['chat_id', 'thread_id']}
    await state.set_data(new_data)
    await state.set_state(None)
    
    # Cleanup and show payment menu again
    await utils.cleanup_msgs(cid, state)
    
    # Show payment menu (effectively re-running process_admin_payment logic)
    settings = db.get_match_settings(cid, tid)
    text = f"**{tr.t('admin_payment', lang_id)}**\n\n"
    text += f"{tr.t('setting_cost', lang_id)}: {settings.get('cost', '—')}\n"
    text += f"{tr.t('admin_reminders_settings', lang_id)}:\n"
    text += f"  - {tr.t('remind_before_game', lang_id)}: {'✅' if settings.get('remind_before_game') else '❌'}\n"
    text += f"  - {tr.t('remind_after_game', lang_id)}: {'✅' if settings.get('remind_after_game') else '❌'}\n"
    text += f"{tr.t('require_admin_confirmation', lang_id)}: {'✅' if settings.get('require_payment_confirmation') else '❌'}\n"
    
    await message.answer(text, reply_markup=kb.get_admin_payment_kb(cid, tid, lang_id, settings), parse_mode="Markdown")

@router.callback_query(F.data.startswith("toggle_remind_"))
async def toggle_reminder(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    key = "remind_before_game" if "before" in callback.data else "remind_after_game"
    settings = db.get_match_settings(cid, tid)
    new_val = 0 if settings.get(key) else 1
    db.update_match_settings(cid, tid, key, new_val)
    await process_admin_payment(callback, state)

@router.callback_query(F.data.startswith("toggle_track_"))
async def toggle_tracking_setting(callback: CallbackQuery, state: FSMContext):
    """Toggle match event tracking settings (goals, goal_times, cards, card_times, best_defender)"""
    parts = callback.data.split("_")
    # toggle_track_{setting}_{cid}_{tid}
    setting_name = "_".join(parts[2:-2])  # e.g. "goals", "goal_times", "cards", "card_times", "best_defender"
    cid = int(parts[-2])
    tid = int(parts[-1])
    
    key = f"track_{setting_name}"
    settings = db.get_match_settings(cid, tid)
    new_val = 0 if settings.get(key, 0) else 1
    db.update_match_settings(cid, tid, key, new_val)
    
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)  # Re-fetch after update
    
    # Determine which menu to refresh
    if setting_name == "best_defender":
        # Refresh rating settings submenu
        text = f"**{tr.t('setting_rating_mode', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
        try:
            await callback.message.edit_text(text, reply_markup=kb.get_rating_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
        except TelegramBadRequest:
            pass
        except TelegramBadRequest:
            pass
    elif setting_name in ["goals", "goal_times", "cards", "card_times", "assists"]:
        # Refresh match event settings submenu
        text = f"**{tr.t('setting_match_events', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
        try:
            await callback.message.edit_text(text, reply_markup=kb.get_admin_bot_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
        except TelegramBadRequest:
            pass
    else:
        # Fallback to main bot settings
        text = f"🤖 **{tr.t('bot_settings_title', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
        try:
            await callback.message.edit_text(text, reply_markup=kb.get_admin_bot_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
        except TelegramBadRequest:
            pass
    
    await callback.answer(tr.t("settings_applied", lang_id))



@router.callback_query(F.data.startswith("rating_settings_menu_"))
async def open_rating_settings_menu(callback: CallbackQuery, state: FSMContext):
    """Open rating system settings submenu"""
    parts = callback.data.split("_")
    cid = int(parts[3])
    tid = int(parts[4])
    
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    text = f"**{tr.t('setting_rating_mode', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_rating_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("rating_settings_back_"))
async def rating_settings_back(callback: CallbackQuery, state: FSMContext):
    """Return from rating settings submenu to main bot settings"""
    parts = callback.data.split("_")
    cid = int(parts[3])
    tid = int(parts[4])
    
    # Return to bot settings menu
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    text = f"🤖 **{tr.t('bot_settings_title', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_admin_bot_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("set_rating_mode_"))
async def set_rating_mode(callback: CallbackQuery, state: FSMContext):
    """Set rating mode (ranked/top3/scale5/disabled)"""
    parts = callback.data.split("_")
    # set_rating_mode_{mode}_{cid}_{tid}
    mode = parts[3]  # ranked, top3, scale5, or disabled
    cid = int(parts[4])
    tid = int(parts[5])
    
    db.update_match_settings(cid, tid, 'rating_mode', mode)
    
    # Refresh rating settings submenu
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    text = f"**{tr.t('setting_rating_mode', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_rating_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    except TelegramBadRequest:
        pass
    await callback.answer(tr.t("settings_applied", lang_id))

@router.callback_query(F.data.startswith("payment_settings_menu_"))
async def open_payment_settings_menu(callback: CallbackQuery, state: FSMContext):
    """Open payment system settings submenu"""
    parts = callback.data.split("_")
    cid = int(parts[3])
    tid = int(parts[4])
    
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    text = f"**{tr.t('setting_payment_mode', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_payment_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("open_cost_settings"))
async def open_cost_settings(callback: CallbackQuery, state: FSMContext):
    """Open cost settings submenu"""
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    
    text = f"💰 **{tr.t('btn_cost_settings', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_cost_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("set_cost_mode_price_"))
async def set_cost_mode_price(callback: CallbackQuery, state: FSMContext):
    """Set cost mode from Price Settings submenu"""
    parts = callback.data.split("_")
    # set_cost_mode_price_{mode}_{cid}_{tid}
    # Index 0:set, 1:cost, 2:mode, 3:price, 4:mode_part1, 5:mode_part2 (if fixed_player), etc.
    # The mode is between index 4 and the last two parts (cid, tid)
    mode = "_".join(parts[4:-2]) 
    cid = int(parts[-2])
    tid = int(parts[-1])
    
    db.update_match_settings(cid, tid, 'cost_mode', mode)
    
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    text = f"💰 **{tr.t('btn_cost_settings', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_cost_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    except TelegramBadRequest:
        pass
    await callback.answer(tr.t("settings_applied", lang_id))

@router.callback_query(F.data.startswith("admin_payment_menu_back"))
async def admin_payment_menu_back(callback: CallbackQuery, state: FSMContext):
    """Return from cost settings to payment settings"""
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    
    await process_admin_payment(callback, state)  # Reuse existing handler to show payment menu

@router.callback_query(F.data.startswith("payment_settings_back_"))
async def payment_settings_back(callback: CallbackQuery, state: FSMContext):
    """Return from payment settings submenu to main bot settings"""
    parts = callback.data.split("_")
    cid = int(parts[3])
    tid = int(parts[4])

    
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    text = f"🤖 **{tr.t('bot_settings_title', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
    await callback.message.edit_text(text, reply_markup=kb.get_admin_bot_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("set_cost_mode_"))
async def set_cost_mode(callback: CallbackQuery, state: FSMContext):
    """Set cost mode (fixed_player/fixed_game)"""
    parts = callback.data.split("_")
    mode = "_".join(parts[3:-2])  # fixed_player or fixed_game
    cid = int(parts[-2])
    tid = int(parts[-1])
    
    db.update_match_settings(cid, tid, 'cost_mode', mode)
    
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    text =f"💰 **{tr.t('setting_payment_mode', lang_id)}**\n\n{tr.t('bot_settings_desc', lang_id)}"
    await callback.message.edit_text(text, reply_markup=kb.get_payment_settings_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    await callback.answer(tr.t("settings_applied", lang_id))



@router.callback_query(F.data.startswith("toggle_payment_confirmation"))
async def toggle_payment_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    settings = db.get_match_settings(cid, tid)
    new_val = 0 if settings.get('require_payment_confirmation') else 1
    db.update_match_settings(cid, tid, 'require_payment_confirmation', new_val)
    # Reload settings to ensure correct display
    await state.update_data(settings_updated=True)
    await process_admin_payment(callback, state)

@router.callback_query(F.data == "pay_self")
async def process_pay_self(callback: CallbackQuery, state: FSMContext):
    """Handler for single 'I Paid' button - player marks themselves as paid"""
    cid, tid = get_ids(callback.message)
    lang_id = utils.get_chat_lang(cid, tid)
    user_id = callback.from_user.id
    
    # Find player's registration by user_id
    regs = db.get_registrations(cid, tid)
    player_reg = None
    for r in regs:
        if r[1] == user_id:  # r[1] is user_id
            player_reg = r
            break
    
    if not player_reg:
        return await callback.answer(tr.t("error_not_registered", lang_id), show_alert=True)
    
    pid = player_reg[0]  # player_id
    name = player_reg[2]  # name
    
    # Update payment status to 1 (claimed)
    db.update_payment_status(pid, cid, tid, 1)
    await callback.answer(tr.t("payment_claimed", lang_id).format(name=name))
    
    # Refresh poll - use the message_id from the callback (the poll message itself)
    await utils.update_poll_message(chat_id=cid, thread_id=tid, message_id=callback.message.message_id)

@router.callback_query(F.data == "pay_self_reminder")
async def process_pay_self_reminder(callback: CallbackQuery, state: FSMContext):
    """Handler for 'I Paid' button in payment reminder message"""
    cid, tid = get_ids(callback.message)
    lang_id = utils.get_chat_lang(cid, tid)
    user_id = callback.from_user.id
    
    # Find player's registration by user_id
    regs = db.get_registrations(cid, tid)
    player_reg = None
    for r in regs:
        if r[1] == user_id:  # r[1] is user_id
            player_reg = r
            break
    
    if not player_reg:
        return await callback.answer(tr.t("error_not_registered", lang_id), show_alert=True)
    
    pid = player_reg[0]  # player_id
    name = player_reg[2]  # name
    
    # Update payment status to 1 (claimed)
    db.update_payment_status(pid, cid, tid, 1)
    await callback.answer(tr.t("payment_claimed", lang_id).format(name=name))
    
    # Refresh payment reminder message
    await refresh_payment_reminder(callback.message, cid, tid, lang_id)

@router.callback_query(F.data.regexp(r"^confirm_payment_\d+$"))
async def process_confirm_payment(callback: CallbackQuery, state: FSMContext):
    """Handler for admin confirmation buttons in payment reminder"""
    cid, tid = get_ids(callback.message)
    lang_id = utils.get_chat_lang(cid, tid)
    
    if not await utils.is_admin(callback, state):
        return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
    
    pid = int(callback.data.split("_")[2])
    
    # Find player's current status
    regs = db.get_registrations(cid, tid)
    current_status = 0
    name = "Player"
    for r in regs:
        if r[0] == pid:
            current_status = r[8]
            name = r[2]
            break
            
    # Toggle logic: if confirmed (2) -> set to unpaid (0), otherwise -> confirmed (2)
    new_status = 2 if current_status != 2 else 0
    
    # Update payment status
    db.update_payment_status(pid, cid, tid, new_status)
    
    # Text for answer
    if new_status == 2:
        ans_text = tr.t("payment_confirmed", lang_id).format(name=name)
    else:
        ans_text = f"❌ {name}" # Simple text for unconfirm
        
    await callback.answer(ans_text)
    
    # Refresh payment reminder message
    await refresh_payment_reminder(callback.message, cid, tid, lang_id)

@router.callback_query(F.data.startswith("pay_legionnaire_"))
async def process_pay_legionnaire(callback: CallbackQuery, state: FSMContext):
    """Handler for legionnaire payment buttons (when no admin confirmation required)"""
    cid, tid = get_ids(callback.message)
    lang_id = utils.get_chat_lang(cid, tid)
    
    if not await utils.is_admin(callback, state):
        return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
        
    pid = int(callback.data.split("_")[2])
    p_info = db.get_player_by_id(pid, cid, tid)
    
    # Update payment status to 1 (claimed/paid)
    db.update_payment_status(pid, cid, tid, 1)
    await callback.answer(tr.t("payment_claimed", lang_id).format(name=p_info[2]))
    
    # Refresh payment reminder message
    await refresh_payment_reminder(callback.message, cid, tid, lang_id)

async def refresh_payment_reminder(message, cid, tid, lang_id):
    """Helper function to refresh payment reminder message"""
    settings = db.get_match_settings(cid, tid)
    regs = db.get_registrations(cid, tid)
    
    # Filter only active players
    active_regs = [r for r in regs if r[9] == 'active']
    
    if not active_regs:
        return
    
    # Group players by payment status
    unpaid = []  # is_paid = 0
    pending = []  # is_paid = 1
    paid = []  # is_paid = 2
    
    for r in active_regs:
        if r[8] == 0:
            unpaid.append(r)
        elif r[8] == 1:
            pending.append(r)
        else:
            paid.append(r)
            
    # Check for completion and auto-delete
    require_confirmation = settings.get('require_payment_confirmation', 0)
    all_done = False
    
    if require_confirmation:
        # All must be confirmed (status 2), so unpaid and pending must be empty
        if not unpaid and not pending:
            all_done = True
    else:
        # Just need everyone to have paid (status 1 or 2), so unpaid must be empty
        if not unpaid:
            all_done = True
            
    if all_done:
        try:
            await message.delete()
            await message.answer(tr.t("all_paid", lang_id))
            
            # Check if ratings are done
            draft_data = db.get_draft_state(cid, tid)
            if draft_data and draft_data.get('ratings_done'):
                 db.update_match_settings(cid, tid, "is_active", 0)
                 db.clear_draft_state(cid, tid)
                 db.clear_registrations(cid, tid)
                 await message.answer(tr.t("match_finished_full", lang_id))
        except:
            pass
        return
    
    # Build payment reminder message
    text = f"**{tr.t('payment_reminder_title', lang_id)}**\n\n"
    
    # Unpaid players - with tags
    if unpaid:
        text += f"**{tr.t('payment_reminder_unpaid', lang_id)}:**\n"
        mentions = []
        for r in unpaid:
            if r[1]:  # has user_id
                mentions.append(f"[{r[2]}](tg://user?id={r[1]})")
            else:
                mentions.append(r[2])
        text += ", ".join(mentions) + "\n\n"
    
    # Pending confirmation - with 💰
    if pending:
        text += f"**{tr.t('payment_reminder_pending', lang_id)}:**\n"
        names = [f"{r[2]} 💰" for r in pending]
        text += ", ".join(names) + "\n\n"
    
    # Paid - with ✅
    if paid:
        text += f"**{tr.t('payment_reminder_paid', lang_id)}:**\n"
        names = [f"{r[2]} ✅" for r in paid]
        text += ", ".join(names) + "\n\n"
    
    # Get keyboard
    require_confirmation = settings.get('require_payment_confirmation', 0)
    reminder_kb = kb.get_payment_reminder_kb(active_regs, require_confirmation=require_confirmation, lang_id=lang_id)
    
    try:
        await message.edit_text(text, reply_markup=reminder_kb, parse_mode="Markdown")
    except:
        pass

@router.callback_query(F.data.startswith("pay_claim_"))
async def process_pay_claim(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    cid, tid = get_ids(callback.message)
    lang_id = utils.get_chat_lang(cid, tid)
    # Check if user is the player
    # Since we don't have user_id in callback here easily, we rely on name or just let anyone click it for simplicity for now
    # but ideally we check if callback.from_user.id match player (we would need to fetch player info)
    p_info = db.get_player_by_id(pid, cid, tid)
    # p_info[1] is user_id
    if p_info[1] and p_info[1] != callback.from_user.id:
        if not await utils.is_admin(callback, state):
             return await callback.answer(tr.t("error_not_your_button", lang_id), show_alert=True)
    
    db.update_payment_status(pid, cid, tid, 1) # Claimed
    await callback.answer(tr.t("payment_claimed", lang_id).format(name=p_info[2]))
    # Refresh poll or wherever it was
    await utils.update_poll_message(chat_id=cid, thread_id=tid)

@router.callback_query(F.data.startswith("pay_confirm_"))
async def process_pay_confirm(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback.message)
    lang_id = utils.get_chat_lang(cid, tid)
    if not await utils.is_admin(callback, state): return await callback.answer(tr.t("no_admin_rights", lang_id), show_alert=True)
    
    pid = int(callback.data.split("_")[2])
    p_info = db.get_player_by_id(pid, cid, tid)
    db.update_payment_status(pid, cid, tid, 2) # Confirmed
    await callback.answer(tr.t("payment_confirmed", lang_id).format(name=p_info[2]))
    await utils.update_poll_message(chat_id=cid, thread_id=tid)

@router.callback_query(F.data == "edit_championship_start")
async def edit_championship_start(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    current_name = settings.get('championship_name') or tr.t("championship_name_default", lang_id)
    
    await state.update_data(chat_id=cid, thread_id=tid)
    await state.set_state(MatchSettings.waiting_for_championship)
    await callback.message.answer(
        f"{tr.t('ask_championship_name', lang_id)}\n\n**Текущее:** {current_name}"
    )
    await callback.answer()

@router.message(MatchSettings.waiting_for_championship)
async def process_championship_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    
    championship_name = message.text.strip()
    if not championship_name:
        championship_name = tr.t("championship_name_default", lang_id)
    
    db.update_match_settings(cid, tid, 'championship_name', championship_name)
    await message.answer(tr.t("settings_saved", lang_id))
    await state.clear()

@router.callback_query(F.data == "admin_mgmt_regular")
async def admin_mgmt_regular(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    lang_id = utils.get_chat_lang(cid, tid)
    players = db.get_all_player_stats(cid, tid)
    try:
        return await callback.message.edit_text(
            tr.t("title_regular_players", lang_id),
            reply_markup=kb.get_real_players_list_kb(players, cid, tid, lang_id)
        )
    except Exception:
        await callback.answer()

@router.callback_query(F.data.startswith("edit_bot_lang"))
async def edit_bot_language(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id') or 0
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        await callback.message.edit_text(tr.t("choose_language", lang_id), reply_markup=kb.get_language_selection_kb(cid, tid), parse_mode="Markdown")
    except TelegramBadRequest:
        pass # Message is not modified, no need to update
    await callback.answer()

@router.callback_query(F.data.startswith("set_lang_"))
async def process_language_selection(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    lang_id = int(parts[2])
    cid = int(parts[3])
    tid = int(parts[4])
    
    # Check if this is initial setup (no existing settings record)
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT language_id FROM settings WHERE chat_id = %s AND thread_id = %s", (cid, tid))
    existing_settings = cursor.fetchone()
    conn.close()
    
    db.update_match_settings(cid, tid, 'language_id', lang_id)
    await callback.answer(tr.t("language_updated", lang_id))
    
    if not existing_settings or not existing_settings[0]:
        # Initial setup: continue with setup flow
        msg = await callback.message.edit_text(tr.t("initial_setup_count", lang_id))
        await state.update_data(last_bot_msg_id=msg.message_id)
        await state.set_state(InitialSetup.waiting_for_player_count)
    else:
        # Existing settings: show admin menu
        await state.update_data(chat_id=cid, thread_id=tid)
        await process_admin_bot_settings(callback, state)

@router.callback_query(F.data.startswith("lang_"))
async def process_lang_select_group(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = int(callback.data.split("_")[1])
    db.update_match_settings(cid, tid, 'language_id', lang_id)
    await callback.answer(tr.t("language_changed", lang_id))
    
    # Start Initial Setup Flow
    await callback.message.edit_text(tr.t("initial_setup_count", lang_id))
    await state.set_state(InitialSetup.waiting_for_player_count)
    # We need to save lang_id to state or re-fetch it later if needed, but db is updated so utils.get_chat_lang will work

@router.message(InitialSetup.waiting_for_player_count)
async def process_initial_player_count(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    try:
        count = int(message.text)
        if count < 2: raise ValueError
        db.update_match_settings(cid, tid, 'player_count', count)
        
        # Delete previous bot message and user's input
        if data.get('last_bot_msg_id'):
            asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
        asyncio.create_task(utils.auto_delete_message(cid, message.message_id, delay_seconds=2))
        
        msg = await message.answer(tr.t("initial_setup_timezone", lang_id), reply_markup=kb.get_timezone_kb())
        await state.update_data(last_bot_msg_id=msg.message_id)
        await state.set_state(InitialSetup.waiting_for_timezone)
    except:
        await message.answer(tr.t("initial_setup_count_error", lang_id))

@router.callback_query(InitialSetup.waiting_for_timezone)
async def process_initial_timezone(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    if callback.data.startswith("set_tz_"):
        tz = callback.data.replace("set_tz_", "")
        db.update_match_settings(cid, tid, 'timezone', tz)
        
        # Delete previous bot message
        if data.get('last_bot_msg_id'):
            asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
        
        # Ask for Match DAY
        msg = await callback.message.answer(tr.t("initial_setup_day", lang_id), reply_markup=kb.get_day_selection_kb(lang_id))
        await state.update_data(last_bot_msg_id=msg.message_id)
        await state.set_state(InitialSetup.waiting_for_match_day) 
        await callback.answer()
    else:
        await callback.answer("Error")

@router.callback_query(InitialSetup.waiting_for_match_day)
async def process_initial_match_day(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    
    if callback.data.startswith("set_day_"):
        day = callback.data.split("_")[2]
        await state.update_data(temp_setup_day=day)
        
        # Delete previous bot message
        if data.get('last_bot_msg_id'):
            asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
        
        # Next: Hour
        msg = await callback.message.answer(tr.t("initial_setup_hour", lang_id), reply_markup=kb.get_hour_selection_kb())
        await state.update_data(last_bot_msg_id=msg.message_id)
        await state.set_state(InitialSetup.waiting_for_match_times)
        await callback.answer()

@router.callback_query(InitialSetup.waiting_for_match_times)
async def process_initial_match_time(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    
    if callback.data.startswith("set_hour_"):
        hour = callback.data.split("_")[2]
        await state.update_data(temp_setup_hour=hour)
        await callback.message.edit_text(tr.t("initial_setup_min", lang_id), reply_markup=kb.get_min_selection_kb())
        return await callback.answer()

    if callback.data.startswith("set_min_"):
        minute = callback.data.split("_")[2]
        data_new = await state.get_data()
        day = data_new.get('temp_setup_day', 'sat')
        hour = data_new.get('temp_setup_hour', '20')
        
        # Save as match_times (string format: "day hour:minute", e.g. "sat 20:00")
        time_str = f"{day} {hour}:{minute}"
        db.update_match_settings(cid, tid, 'match_times', time_str)
        
        # Delete previous bot message
        if data.get('last_bot_msg_id'):
            asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
        
        # Next: Skill Level
        msg = await callback.message.answer(tr.t("initial_setup_skill", lang_id), reply_markup=kb.get_skill_level_kb(lang_id))
        await state.update_data(last_bot_msg_id=msg.message_id)
        await state.set_state(InitialSetup.waiting_for_skill_level)
        await callback.answer()

@router.callback_query(InitialSetup.waiting_for_skill_level)
async def process_initial_skill(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    
    if callback.data.startswith("skill_"):
        sid = int(callback.data.split("_")[1])
        db.update_match_settings(cid, tid, 'skill_level_id', sid)
        
        # Delete previous bot message
        if data.get('last_bot_msg_id'):
            asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
        
        # Next: Age Group
        msg = await callback.message.answer(tr.t("initial_setup_age", lang_id), reply_markup=kb.get_age_group_kb(lang_id))
        await state.update_data(last_bot_msg_id=msg.message_id)
        await state.set_state(InitialSetup.waiting_for_age_group)
        await callback.answer()

@router.callback_query(InitialSetup.waiting_for_age_group)
async def process_initial_age(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()

    if callback.data.startswith("age_"):
        aid = int(callback.data.split("_")[1])
        db.update_match_settings(cid, tid, 'age_group_id', aid)
        
        # Delete previous bot message
        if data.get('last_bot_msg_id'):
            asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
        
        # Next: Gender
        msg = await callback.message.answer(tr.t("initial_setup_gender", lang_id), reply_markup=kb.get_gender_kb(lang_id))
        await state.update_data(last_bot_msg_id=msg.message_id)
        await state.set_state(InitialSetup.waiting_for_gender)
        await callback.answer()

@router.callback_query(InitialSetup.waiting_for_gender)
async def process_initial_gender(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()

    if callback.data.startswith("gender_"):
        gid = int(callback.data.split("_")[1])
        db.update_match_settings(cid, tid, 'gender_id', gid)
        
        # Delete previous bot message
        if data.get('last_bot_msg_id'):
            asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
        
        # Next: Venue Type
        msg = await callback.message.answer(tr.t("initial_setup_venue", lang_id), reply_markup=kb.get_venue_type_kb(lang_id))
        await state.update_data(last_bot_msg_id=msg.message_id)
        await state.set_state(InitialSetup.waiting_for_venue)
        await callback.answer()

@router.callback_query(InitialSetup.waiting_for_venue)
async def process_initial_venue(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)

    if callback.data.startswith("venue_"):
        vid = int(callback.data.split("_")[1])
        db.update_match_settings(cid, tid, 'venue_type_id', vid)
        
        # Delete previous bot message with buttons
        data = await state.get_data()
        if data.get('last_bot_msg_id'):
            asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
        
        # Next: Cost (Message)
        sent = await callback.message.answer(tr.t("initial_setup_cost", lang_id))
        await state.update_data(last_bot_msg_id=sent.message_id)
        await state.set_state(InitialSetup.waiting_for_cost)
        await callback.answer()

@router.message(InitialSetup.waiting_for_cost)
async def process_initial_cost(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    
    cost_text = message.text
    db.update_match_settings(cid, tid, 'cost', cost_text)
    
    # Delete previous bot message and user's input
    if data.get('last_bot_msg_id'):
        asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
    asyncio.create_task(utils.auto_delete_message(cid, message.message_id, delay_seconds=2))
    
    # Next: Championship Name
    msg = await message.answer(tr.t("initial_setup_championship", lang_id))
    await state.update_data(last_bot_msg_id=msg.message_id)
    await state.set_state(InitialSetup.waiting_for_championship)

@router.message(InitialSetup.waiting_for_championship)
async def process_initial_championship(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    
    championship_name = message.text.strip()
    # Use default if empty or use provided text
    if not championship_name:
        championship_name = tr.t("championship_name_default", lang_id)
    
    db.update_match_settings(cid, tid, 'championship_name', championship_name)
    
    # Delete previous bot message and user's input
    if data.get('last_bot_msg_id'):
        asyncio.create_task(utils.auto_delete_message(cid, data['last_bot_msg_id'], delay_seconds=2))
    asyncio.create_task(utils.auto_delete_message(cid, message.message_id, delay_seconds=2))
    
    # FINISH
    complete_msg = await message.answer(tr.t("initial_setup_complete", lang_id))
    await state.clear()
    
    # Auto-delete completion message after 2 minutes
    asyncio.create_task(utils.auto_delete_message(cid, complete_msg.message_id, delay_seconds=120))
    
    # Show main menu or welcome
    await asyncio.sleep(2)
    welcome_msg = await message.answer(tr.t("welcome_msg_admin", lang_id))
    # Auto-delete welcome message after 2 minutes
    asyncio.create_task(utils.auto_delete_message(cid, welcome_msg.message_id, delay_seconds=120))


@router.callback_query(F.data.startswith("process_settings_done"))
async def process_settings_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid) if cid else 1
    if cid:
        await utils.update_poll_message(chat_id=cid, thread_id=tid)
    await callback.message.edit_text(tr.t("settings_applied", lang_id))
    await asyncio.sleep(2)
    # Return to admin main menu
    await admin_main_menu_back(callback, state)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_count_start"))
async def edit_count_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    sent = await callback.message.answer(tr.t("enter_player_count", lang_id))
    await utils.track_msg(state, sent.message_id)
    await state.set_state(MatchSettings.waiting_for_player_count)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_skill_start"))
async def edit_skill_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    await callback.message.edit_text(tr.t("choose_skill_level", lang_id), reply_markup=kb.get_skill_level_kb(lang_id))
    await state.set_state(MatchSettings.waiting_for_skill_level)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_age_start"))
async def edit_age_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    await callback.message.edit_text(tr.t("choose_age_group", lang_id), reply_markup=kb.get_age_group_kb(lang_id))
    await state.set_state(MatchSettings.waiting_for_age_group)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_gender_start"))
async def edit_gender_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    await callback.message.edit_text(tr.t("choose_gender", lang_id), reply_markup=kb.get_gender_kb(lang_id))
    await state.set_state(MatchSettings.waiting_for_gender)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_cost_start"))
async def edit_cost_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    sent = await callback.message.answer(tr.t("enter_match_cost", lang_id))
    await utils.track_msg(state, sent.message_id)
    await state.set_state(MatchSettings.waiting_for_cost)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_venue_start"))
async def edit_venue_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    await callback.message.edit_text(tr.t("choose_venue_type", lang_id), reply_markup=kb.get_venue_type_kb(lang_id))
    await state.set_state(MatchSettings.waiting_for_venue)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_location_start"))
async def edit_location_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    markup = InlineKeyboardBuilder()
    markup.button(text=tr.t("btn_back", lang_id), callback_data="process_admin_settings")
    sent = await callback.message.answer(tr.t("ask_location", lang_id), reply_markup=markup.as_markup())
    await utils.track_msg(state, sent.message_id)
    await state.set_state(MatchSettings.waiting_for_location)
    await callback.answer()

@router.message(MatchSettings.waiting_for_location)
async def process_location(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id')
    lang_id = utils.get_chat_lang(cid, tid)
    if message.location:
        db.update_match_settings(cid, tid, "location_lat", message.location.latitude)
        db.update_match_settings(cid, tid, "location_lon", message.location.longitude)
        await message.answer(tr.t("location_saved", lang_id, lat=message.location.latitude, lon=message.location.longitude))
        await utils.cleanup_msgs(message.chat.id, state)
        await state.set_state(None)
        await show_admin_settings_menu(message, state)
    else:
        await message.answer(tr.t("error_send_location", lang_id))

@router.callback_query(F.data.startswith("edit_time_group"))
async def edit_time_group(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id')
    lang_id = utils.get_chat_lang(cid, tid)
    await callback.message.edit_text(tr.t("timesettingstitle", lang_id), reply_markup=kb.get_admin_time_settings_kb(cid, tid, lang_id), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("edit_timezone_start"))
async def edit_timezone_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    await callback.message.edit_text(tr.t("choose_timezone", lang_id), reply_markup=kb.get_timezone_kb())
    await callback.answer()

@router.callback_query(F.data.startswith("set_tz_"))
async def process_timezone_cb(callback: CallbackQuery, state: FSMContext):
    tz = callback.data.replace("set_tz_", "")
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id')
    db.update_match_settings(cid, tid, "timezone", tz)
    await callback.answer(f"Timezone: {tz}")
    await edit_time_group(callback, state)

@router.callback_query(F.data.startswith("edit_times_start"))
async def edit_times_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    await callback.message.edit_text(tr.t("choose_day", lang_id), reply_markup=kb.get_day_selection_kb(lang_id))
    await callback.answer()

@router.callback_query(F.data.startswith("set_day_"))
async def process_times_day(callback: CallbackQuery, state: FSMContext):
    day = callback.data.split("_")[2]
    await state.update_data(temp_day=day)
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    await callback.message.edit_text(tr.t("choose_hour", lang_id), reply_markup=kb.get_hour_selection_kb())
    await callback.answer()

@router.callback_query(F.data.startswith("set_hour_"))
async def process_times_hour(callback: CallbackQuery, state: FSMContext):
    hour = callback.data.split("_")[2]
    await state.update_data(temp_hour=hour)
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    await callback.message.edit_text(tr.t("choose_min", lang_id), reply_markup=kb.get_min_selection_kb())
    await callback.answer()

@router.callback_query(F.data.startswith("set_min_"))
async def process_times_min(callback: CallbackQuery, state: FSMContext):
    minute = callback.data.split("_")[2]
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id')
    day = data['temp_day']
    hour = data['temp_hour']
    lang_id = utils.get_chat_lang(cid, tid)
    time_str = f"{day} {hour}:{minute}"
    db.update_match_settings(cid, tid, "match_times", time_str)
    # For user feedback, we can still show translated
    user_time_str = f"{tr.t('wd_'+day, lang_id)}, {hour}:{minute}"
    await callback.answer(f"Time: {user_time_str}")
    await edit_time_group(callback, state)

@router.callback_query(F.data.startswith("edit_season_group"))
async def edit_season_group(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id')
    lang_id = utils.get_chat_lang(cid, tid)
    await callback.message.edit_text(tr.t("title_season_settings", lang_id), reply_markup=kb.get_admin_season_settings_kb(cid, tid, lang_id), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("edit_season_start_cb"))
async def edit_season_start_cb(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    sent = await callback.message.answer(tr.t("enter_season_start", lang_id))
    await utils.track_msg(state, sent.message_id)
    await state.set_state(MatchSettings.waiting_for_season_start)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_season_end_cb"))
async def edit_season_end_cb(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id'), data.get('thread_id'))
    sent = await callback.message.answer(tr.t("enter_season_end", lang_id))
    await utils.track_msg(state, sent.message_id)
    await state.set_state(MatchSettings.waiting_for_season_end)
    await callback.answer()

async def validate_and_save_date(message: Message, state: FSMContext, target_key: str):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id')
    lang_id = utils.get_chat_lang(cid, tid)
    import re
    if re.match(r"^\d{2}\.\d{2}\.\d{4}$", message.text):
        db.update_match_settings(cid, tid, target_key, message.text)
        await message.answer(tr.t("date_saved", lang_id).format(date=message.text))
        await utils.cleanup_msgs(message.chat.id, state)
        await state.set_state(None)
        await edit_season_group(None if not message else types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data=""), state)
    else:
        await message.answer(tr.t("invalid_date", lang_id))

@router.message(MatchSettings.waiting_for_season_start)
async def process_manual_season_start(message: Message, state: FSMContext):
    await validate_and_save_date(message, state, "season_start")

@router.message(MatchSettings.waiting_for_season_end)
async def process_manual_season_end(message: Message, state: FSMContext):
    await validate_and_save_date(message, state, "season_end")

# --- DRAW FLOW ---

@router.callback_query(F.data.startswith("admin_draw"))
async def process_draw_start(callback: CallbackQuery, state: FSMContext):
    if not await utils.is_admin(callback, state):
        return await callback.answer("⛔ Нет прав", show_alert=True)
    
    parts = callback.data.split("_")
    cid, tid = 0, 0
    if len(parts) >= 4:
         try:
             cid = int(parts[2])
             tid = int(parts[3])
         except: pass
    if not cid:
        cid, tid = get_ids(callback)
    
    await state.update_data(chat_id=cid, thread_id=tid)
    lang_id = utils.get_chat_lang(cid, tid)
    msg = await callback.message.answer(tr.t("ask_manual_captains", lang_id), reply_markup=kb.get_ask_captains_kb(lang_id))
    await utils.track_msg(state, msg.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("cap_ask_"))
async def process_cap_ask(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split("_")[2]
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    
    if choice == "no":
        await state.update_data(captains=[])
        msg = await callback.message.answer(tr.t("ask_draw_count", lang_id), reply_markup=kb.get_draw_count_kb(lang_id))
        await utils.track_msg(state, msg.message_id)
    else:
        # Filter only active players
        all_regs = db.get_registrations(cid, tid)
        players = [r for r in all_regs if r[9] == 'active']
        
        if len(players) < 2:
            return await callback.answer(tr.t("not_enough_captains", lang_id), show_alert=True)
        await state.update_data(captains=[])
        msg = await callback.message.edit_text(tr.t("select_two_captains", lang_id), reply_markup=kb.get_players_selection_kb(players, lang_id=lang_id))
        await utils.track_msg(state, msg.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("cap_sel_"))
async def process_cap_sel(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected = data.get("captains", [])
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)

    if pid in selected:
        selected.remove(pid)
    else:
        if len(selected) >= 2:
            return await callback.answer(tr.t("already_selected_two", lang_id), show_alert=True)
        selected.append(pid)
    await state.update_data(captains=selected)
    
    all_regs = db.get_registrations(cid, tid)
    players = [r for r in all_regs if r[9] == 'active']
    
    await callback.message.edit_reply_markup(reply_markup=kb.get_players_selection_kb(players, selected, lang_id=lang_id))
    await callback.answer()

@router.callback_query(F.data == "cap_done")
async def process_cap_done(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    msg = await callback.message.answer(tr.t("ask_draw_count", lang_id), reply_markup=kb.get_draw_count_kb(lang_id))
    await utils.track_msg(state, msg.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("draw_count_"))
async def process_draw_count_choice(callback: CallbackQuery, state: FSMContext):
    count_data = callback.data.split("_")[2]
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)

    if count_data == "manual":
        caps = data.get("captains", [])
        if len(caps) < 2:
            return await callback.answer(tr.t("manual_needs_two_captains", lang_id), show_alert=True)
            
        all_regs = db.get_registrations(cid, tid)
        players = [r for r in all_regs if r[9] == 'active']
        
        p1_list = [p for p in players if p[0] == caps[0]]
        p2_list = [p for p in players if p[0] == caps[1]]
        if not p1_list or not p2_list:
             return await callback.answer(tr.t("error_captains_not_found", lang_id), show_alert=True)
        p1 = utils.player_to_dict(p1_list[0])
        p2 = utils.player_to_dict(p2_list[0])
        available = [utils.player_to_dict(p) for p in players if p[0] not in caps]
        turn_idx = random.randint(0, 1)
        first_cap_id = caps[turn_idx]
        first_cap_name = p1['name'] if turn_idx == 0 else p2['name']
        draft_data = {
            "draft_teams": {str(caps[0]): [p1], str(caps[1]): [p2]},
            "draft_available": available,
            "draft_turn": first_cap_id,
            "draft_caps": caps,
            "admin_id": callback.from_user.id
        }
        db.set_draft_state(cid, tid, draft_data)
        poll_id = data.get('poll_msg_id')
        exclude = [poll_id] if poll_id else []
        await utils.cleanup_msgs(callback.message.chat.id, state, exclude_ids=exclude)
        await callback.message.answer(tr.t("coin_toss_result", lang_id).format(name=first_cap_name), parse_mode="Markdown")
        msg = await send_draft_status(callback.message, draft_data)
        await utils.track_msg(state, msg.message_id) 
        return
    elif count_data == "contest":
        all_regs = db.get_registrations(cid, tid)
        players = [r for r in all_regs if r[9] == 'active']
        
        if len(players) % 2 != 0:
             return await callback.answer(tr.t("error_odd_player_count_pairs", lang_id).format(count=len(players)), show_alert=True)
        bot_user = await bot.get_me()
        poll_id = data.get('poll_msg_id')
        exclude = [poll_id] if poll_id else []
        await utils.cleanup_msgs(callback.message.chat.id, state, exclude_ids=exclude)
        await callback.message.answer(
            tr.t("pairs_contest_launched", lang_id),
            reply_markup=kb.get_pairs_start_kb(bot_user.username, cid, tid),
            parse_mode="Markdown"
        )
        return

    count = int(count_data)
    settings = db.get_match_settings(cid, tid)
    
    all_regs = db.get_registrations(cid, tid)
    players = [r for r in all_regs if r[9] == 'active']
    
    req_count = settings['player_count'] if settings else 12
    warning = ""
    if len(players) < req_count:
        warning = tr.t("poll_warning_less_players", lang_id).format(count=len(players), req=req_count)
    msg = await callback.message.answer(
        f"{warning}{tr.t('ask_accounting_roles', lang_id)}", 
        reply_markup=kb.get_draw_options_kb(lang_id=lang_id),
        parse_mode="Markdown"
    )
    await state.update_data(draw_variant_count=count)
    await utils.track_msg(state, msg.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("draw_mode_"))
async def process_draw_mode(callback: CallbackQuery, state: FSMContext):
    if not await utils.is_admin(callback, state): return
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    v_count = data.get("draw_variant_count", 1)
    mode = callback.data.split("_")[2]
    
    all_regs = db.get_registrations(cid, tid)
    players = [r for r in all_regs if r[9] == 'active']
    
    if len(players) < 2:
        return await callback.answer(tr.t("error_min_players", lang_id), show_alert=True)
    if mode == 'gk':
        gks = [p for p in players if p[7] == 'gk']
        if len(gks) < 2:
            return await callback.answer(tr.t("error_min_gks", lang_id), show_alert=True)
    db.clear_draw_votes(cid, tid)
    captains = data.get("captains", [])
    poll_id = data.get('poll_msg_id')
    exclude = [poll_id] if poll_id else []
    await utils.cleanup_msgs(callback.message.chat.id, state, exclude_ids=exclude)
    variants = {}
    if v_count == 1:
        t1, t2, s1, s2 = utils.balance_teams(players, cid, tid, mode, captains=captains)
        caps = captains if (captains and len(captains) == 2) else [t1[0]['id'], t2[0]['id']]
        final_data = {
            "draft_teams": {str(caps[0]): t1, str(caps[1]): t2},
            "draft_caps": caps,
            "admin_id": callback.from_user.id
        }
        db.set_draft_state(cid, tid, final_data)
        await send_draw_variant(callback.message, t1, t2, s1, s2, mode, 0, captains=captains, kb_markup=kb.get_score_entry_kb(lang_id))
    else:
        t1, t2, s1, s2 = utils.balance_teams(players, cid, tid, mode=mode, use_history=False, captains=captains)
        m1 = await send_draw_variant(callback.message, t1, t2, s1, s2, mode, 1, is_vote=True, captains=captains)
        variants[1] = {"t1": t1, "t2": t2, "s1": s1, "s2": s2}
        t1, t2, s1, s2 = utils.balance_teams(players, cid, tid, mode=mode, use_history=True, shuffle_factor=5, captains=captains)
        m2 = await send_draw_variant(callback.message, t1, t2, s1, s2, mode, 2, is_vote=True, type_label=tr.t("mode_by_stats", lang_id), captains=captains)
        variants[2] = {"t1": t1, "t2": t2, "s1": s1, "s2": s2}
        t1, t2, s1, s2 = utils.balance_teams(players, cid, tid, mode=mode, use_history=True, shuffle_factor=15, captains=captains)
        m3 = await send_draw_variant(callback.message, t1, t2, s1, s2, mode, 3, is_vote=True, type_label=tr.t("mode_random_stats", lang_id), captains=captains)
        variants[3] = {"t1": t1, "t2": t2, "s1": s1, "s2": s2}
        await state.update_data(variant_msg_ids={1: m1.message_id, 2: m2.message_id, 3: m3.message_id}, draw_variants=variants)
    await callback.answer()

async def send_draft_status(message, data, edit_id=None):
    if isinstance(message, Message):
        cid, tid = get_ids(message)
    else:
        cid, tid = get_ids(message.message)
    lang_id = utils.get_chat_lang(cid, tid)
    
    teams = data['draft_teams']
    available = data['draft_available']
    turn = data['draft_turn']
    caps = data['draft_caps']
    cap1_id, cap2_id = str(caps[0]), str(caps[1])
    text = f"{tr.t('manual_draft_title', lang_id)}\n\n"
    p1_list = teams[cap1_id]
    text += f"{tr.t('manual_draft_team', lang_id, emoji='🔴', name=p1_list[0]['name'])}\n"
    text += "\n".join([f"- {p['name']} ({p.get('position') or '?'})" for p in p1_list])
    text += "\n\n"
    p2_list = teams[cap2_id]
    text += f"{tr.t('manual_draft_team', lang_id, emoji='⚪', name=p2_list[0]['name'])}\n"
    text += "\n".join([f"- {p['name']} ({p.get('position') or '?'})" for p in p2_list])
    text += "\n\n"
    if not available:
        text += tr.t("manual_draft_finished", lang_id)
        db.set_draft_state(cid, tid, data)
        kb_score = kb.get_score_entry_kb(lang_id)
        if edit_id:
            try: return await bot.edit_message_text(text, chat_id=message.chat.id if isinstance(message, Message) else message.message.chat.id, message_id=edit_id, reply_markup=kb_score, parse_mode="Markdown")
            except: pass
        return await (message.answer(text, reply_markup=kb_score, parse_mode="Markdown") if isinstance(message, Message) else message.message.answer(text, reply_markup=kb_score, parse_mode="Markdown"))

    turn_name = [p['name'] for p in (p1_list + p2_list) if p['id'] == turn][0]
    text += tr.t("manual_draft_turn", lang_id).format(name=turn_name)
    kb_markup = kb.get_draft_kb(available)
    if edit_id:
        try: return await bot.edit_message_text(text, chat_id=message.chat.id if isinstance(message, Message) else message.message.chat.id, message_id=edit_id, reply_markup=kb_markup, parse_mode="Markdown")
        except: pass
    return await (message.answer(text, reply_markup=kb_markup, parse_mode="Markdown") if isinstance(message, Message) else message.message.answer(text, reply_markup=kb_markup, parse_mode="Markdown"))

@router.callback_query(F.data.startswith("draft_pick_"))
async def process_draft_pick(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = db.get_draft_state(cid, tid)
    if not data or 'draft_teams' not in data:
        await callback.answer(tr.t("error_draft_not_found", lang_id), show_alert=True)
        return
    turn_id = data['draft_turn']
    caps = data['draft_caps']
    teams = data['draft_teams']
    current_cap_obj = teams[str(turn_id)][0]
    initiator_admin_id = data.get("admin_id")
    is_initiator = (callback.from_user.id == initiator_admin_id)
    if current_cap_obj.get('user_id'):
        if callback.from_user.id != current_cap_obj['user_id'] and not is_initiator:
            return await callback.answer(tr.t("error_not_your_turn", lang_id).format(name=current_cap_obj['name']), show_alert=True)
    else:
        if not is_initiator:
            return await callback.answer(tr.t("error_wait_admin_turn", lang_id).format(name=current_cap_obj['name']), show_alert=True)
    pid = int(callback.data.split("_")[2])
    available = data['draft_available']
    picked = [p for p in available if p['id'] == pid]
    if not picked: return await callback.answer(tr.t("error_player_already_picked", lang_id))
    p = picked[0]
    available = [p_ for p_ in available if p_['id'] != pid]
    teams[str(turn_id)].append(p)
    next_turn_id = caps[1] if turn_id == caps[0] else caps[0]
    if len(available) == 1:
        last_p = available[0]
        teams[str(next_turn_id)].append(last_p)
        available = []
    new_data = {
        "draft_teams": teams,
        "draft_available": available,
        "draft_turn": next_turn_id,
        "draft_caps": caps,
        "admin_id": initiator_admin_id
    }
    db.set_draft_state(cid, tid, new_data)
    await send_draft_status(callback, new_data, edit_id=callback.message.message_id)
    await callback.answer()

async def send_draw_variant(message, t1, t2, s1, s2, mode, v_id, is_vote=False, type_label=None, captains=[], kb_markup=None):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    mode_text = type_label or {
        "all": tr.t("mode_all_pos", lang_id),
        "gk": tr.t("mode_gk_only", lang_id),
        "none": tr.t("mode_no_pos", lang_id)
    }.get(mode, "")
    def get_p_line(p):
        role = f"({p['position'] or '?'})"
        cap = " ⭐️**(К)**" if p['id'] in captains else ""
        return f"- {p['name']} {role}{cap}"
    text = tr.t("draw_variant_header", lang_id).format(v_id=v_id if v_id else '', mode=mode_text) + "\n\n"
    text += tr.t("team_red", lang_id) + f" (Сила: {int(s1)})\n"
    text += "\n".join([get_p_line(p) for p in t1])
    text += "\n\n"
    text += tr.t("team_white", lang_id) + f" (Сила: {int(s2)})\n"
    text += "\n".join([get_p_line(p) for p in t2])
    
    reply_markup = kb_markup or (kb.get_vote_kb(v_id, lang_id=lang_id) if is_vote else None)
    
    cost = settings.get('cost', '0')
    is_cost_set = cost and str(cost) != "0" and str(cost) != "—"
    
    if settings.get('remind_before_game') and not is_vote and is_cost_set:
        rem_text, rem_kb = utils.get_unpaid_players_mention(cid, tid, lang_id)
        if rem_kb: # There are unpaid players
            text += "\n\n" + rem_text
            # If we already have a markup (like "Enter Score"), we should combine them or send rem_kb separately
            # We'll send it as a separate message for better UI if we have score entry button
            if reply_markup:
                 await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")
                 return await message.answer(tr.t("admin_reminders_settings", lang_id), reply_markup=rem_kb)
            else:
                 reply_markup = rem_kb

    return await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")

@router.callback_query(F.data.startswith("vote_"))
async def process_vote(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    v_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    regs = db.get_registrations(cid, tid)
    if not any(r[1] == user_id for r in regs):
        return await callback.answer(tr.t("error_only_players_vote", lang_id), show_alert=True)
    db.add_draw_vote(cid, tid, v_id, user_id)
    await callback.answer(tr.t("vote_success", lang_id))
    total_players = len(regs)
    needed = (total_players // 2) + 1
    votes = db.get_draw_votes_count(cid, tid, v_id)
    try: await callback.message.edit_reply_markup(reply_markup=kb.get_vote_kb(v_id, votes))
    except: pass
    if votes >= needed:
        data = await state.get_data()
        msg_ids = data.get("variant_msg_ids", {})
        for vid, mid in msg_ids.items():
            if vid != v_id:
                try: await bot.delete_message(cid, mid)
                except: pass
        await callback.message.answer(tr.t("draw_approved", lang_id).format(v_id=v_id), parse_mode="Markdown")
        await callback.message.edit_reply_markup(reply_markup=None)
        variants = data.get("draw_variants", {})
        win = variants.get(v_id)
        if win:
            t1, t2 = win['t1'], win['t2']
            pre_caps = data.get("captains", [])
            caps = pre_caps if (pre_caps and len(pre_caps) == 2) else [t1[0]['id'], t2[0]['id']]
            final_data = {
                "draft_teams": {str(caps[0]): t1, str(caps[1]): t2},
                "draft_caps": caps,
                "admin_id": callback.from_user.id
            }
            db.set_draft_state(cid, tid, final_data)
        try: await callback.message.edit_reply_markup(reply_markup=kb.get_score_entry_kb(lang_id=lang_id))
        except: pass
        await state.update_data(variant_msg_ids={})

@router.message(Command("finish_draw"))
async def cmd_finish_draw(message: Message, state: FSMContext):
    if message.chat.type == 'private':
        return  # Ignore in private chat
    if not await utils.is_admin(message, state):
        cid, tid = get_ids(message)
        lang_id = utils.get_chat_lang(cid, tid)
        sent = await message.answer(tr.t("no_admin_rights", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    winner_id = db.get_draw_winner(cid, tid)
    if winner_id is None:
        sent = await message.answer(tr.t("draw_no_votes", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    data = await state.get_data()
    msg_ids = data.get("variant_msg_ids", {})
    if not msg_ids:
        sent = await message.answer(tr.t("draw_not_found", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    await message.answer(tr.t("draw_finished_admin", lang_id).format(v_id=winner_id), parse_mode="Markdown")
    for vid, mid in msg_ids.items():
        if vid != winner_id:
            try: await bot.delete_message(cid, mid)
            except: pass
        else:
            try: await bot.edit_message_reply_markup(chat_id=cid, message_id=mid, reply_markup=None)
            except: pass
    variants = data.get("draw_variants", {})
    win = variants.get(winner_id)
    if win:
        t1, t2 = win['t1'], win['t2']
        pre_caps = data.get("captains", [])
        caps = pre_caps if (pre_caps and len(pre_caps) == 2) else [t1[0]['id'], t2[0]['id']]
        final_data = {
            "draft_teams": {str(caps[0]): t1, str(caps[1]): t2},
            "draft_caps": caps,
            "admin_id": message.from_user.id
        }
        db.set_draft_state(cid, tid, final_data)
    mid = msg_ids.get(winner_id)
    if mid:
        try: await bot.edit_message_reply_markup(chat_id=cid, message_id=mid, reply_markup=kb.get_score_entry_kb(lang_id))
        except: pass
    await state.update_data(variant_msg_ids={})

@router.callback_query(F.data.regexp(r"^match_decision_(overwrite|new|cancel)(?:_(\d+)_([\d:]+))?$"))
async def process_match_decision(callback: CallbackQuery, state: FSMContext):
    """Handle decision for duplicate match (Overwrite / New / Cancel)"""
    import re
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    
    match = re.search(r"^match_decision_(overwrite|new|cancel)(?:_(\d+)_([\d:]+))?$", callback.data)
    action = match.group(1)
    
    if action == "cancel":
        await callback.message.delete()
        await callback.answer(tr.t("match_creation_cancelled", lang_id))
        return

    # Extract score and match_id (passed for context)
    ref_match_id = int(match.group(2))
    score = match.group(3)

    # Recalculate match params
    skill_id = settings.get('skill_level_id')
    skill = db.get_label_by_id("skill_levels", skill_id, lang_id) if skill_id else "—"
    championship = settings.get('championship_name')
    
    # Calculate match date (UTC)
    match_date_local = utils.get_match_date(settings.get('match_times'), settings.get('timezone'), find_past=True)
    match_date = None
    if match_date_local:
        from datetime import timedelta
        tz_val = settings.get('timezone', 'GMT+3')
        offset = 3
        tm_match = re.search(r"GMT([+-]?\d+)", str(tz_val))
        if tm_match: offset = int(tm_match.group(1))
        match_date = match_date_local - timedelta(hours=offset)

    if action == "overwrite":
        # Clear old stats
        db.clear_match_stats(ref_match_id)
        # Update match details
        db.update_match_score(ref_match_id, score, skill, championship)
        match_id = ref_match_id
        await callback.answer(tr.t("match_overwritten", lang_id))
        
    elif action == "new":
        # Create NEW match (duplicate allowed explicitly)
        match_id = db.create_match(cid, tid, skill, score, match_date=match_date, championship_name=championship)
        await callback.answer(tr.t("match_saved", lang_id).format(score=score, id="..."))

    # Proceed to final setup
    await callback.message.delete()
    # We pass 'message' as callback.message (so it can answer). 
    # But usually finalize_match_setup sends new messages logic.
    await finalize_match_setup(callback.message, state, match_id, score, settings, lang_id, cid, tid)

# --- SCORING & RATING ---

@router.callback_query(F.data == "match_enter_score")
async def process_match_score_start(callback: CallbackQuery, state: FSMContext):
    if not await utils.is_admin(callback): return
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    await state.update_data(chat_id=cid, thread_id=tid)
    await state.set_state(MatchResult.waiting_for_score)
    await callback.message.answer(tr.t("enter_score_prompt", lang_id), parse_mode="Markdown")
    await callback.answer()

@router.message(MatchResult.waiting_for_score)
async def process_match_score(message: Message, state: FSMContext):
    if not await utils.is_admin(message, state):
        data = await state.get_data()
        cid = data.get('chat_id') or message.chat.id
        tid = data.get('thread_id') or 0
        lang_id = utils.get_chat_lang(cid, tid)
        sent = await message.answer(tr.t("no_admin_rights", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    import re
    if not re.match(r'^\d+[:\- ]\d+$', message.text):
        sent = await message.answer(tr.t("error_score_format", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    score = message.text.replace("-", ":").replace(" ", ":")
    await state.update_data(chat_id=cid, thread_id=tid)
    settings = db.get_match_settings(cid, tid)
    
    # Calculate match date (UTC)
    match_date_local = utils.get_match_date(settings.get('match_times'), settings.get('timezone'), find_past=True)
    match_date = None
    if match_date_local:
        # Convert back to UTC
        from datetime import timedelta
        tz_val = settings.get('timezone', 'GMT+3')
        offset = 3
        tm_match = re.search(r"GMT([+-]?\d+)", str(tz_val))
        if tm_match: offset = int(tm_match.group(1))
        match_date = match_date_local - timedelta(hours=offset)

    # Check for existing match to prevent duplicates
    championship = settings.get('championship_name')
    # get_match_by_criteria expects raw date or string? MySQL driver handles datetime.
    # We pass 'match_date' which is a datetime object (UTC).
    existing_match = db.get_match_by_criteria(cid, tid, match_date, championship)
    
    if existing_match:
        # Match exists! Ask user what to do.
        await message.answer(
            tr.t("match_exists_warning", lang_id),
            reply_markup=kb.get_match_exists_kb(existing_match['id'], score, lang_id)
        )
        return

    lang_id = settings.get('language_id', 1)
    skill_id = settings.get('skill_level_id')
    skill = db.get_label_by_id("skill_levels", skill_id, lang_id) if skill_id else "—"
    match_id = db.create_match(cid, tid, skill, score, match_date=match_date)
    # Parse score
    g1, g2 = map(int, score.split(":"))
    total_goals = g1 + g2
    
    draft_data = db.get_draft_state(cid, tid)
    if not draft_data:
        return await message.answer(tr.t("error_no_teams_data", lang_id))
    draft_data['match_id'] = match_id
    draft_data['rated_teams'] = []
    db.set_draft_state(cid, tid, draft_data)
    season_match_num = db.get_season_match_number(cid, tid, match_id)
    match_saved_msg = tr.t("match_saved", lang_id).format(score=score, id=season_match_num)
    
    # If this was called from callback (Duplicate decision), message is message to edit. 
    # If from text handlers, message is the user message (we should answer).
    # simplest way: just try to edit if possible, else answer. 
    # Actually, we can just use message.answer/edit_text appropriately before calling this or handle here.
    # Let's assume message is suitable for answering (a Message object).
    # If we came from callback, we might want to edit the warning message.
    
    # Let's just send a new message "Match saved" in all cases for simplicity and consistency.
    await message.answer(match_saved_msg)
    
    # Send payment reminder if enabled AND cost is set
    cost = settings.get('cost', '0')
    is_cost_set = cost and str(cost) != "0" and str(cost) != "—"
    
    if settings.get('remind_after_game', 1) and is_cost_set:
        regs = db.get_registrations(cid, tid)
        if regs:
            # Build payment reminder message
            text = f"**{tr.t('payment_reminder_title', lang_id)}**\n\n"
            
            # Group players by payment status
            unpaid = []  # is_paid = 0
            pending = []  # is_paid = 1
            paid = []  # is_paid = 2
            
            for r in regs:
                if r[8] == 0:
                    unpaid.append(r)
                elif r[8] == 1:
                    pending.append(r)
                else:
                    paid.append(r)
            
            # Unpaid players - with tags
            if unpaid:
                text += f"**{tr.t('payment_reminder_unpaid', lang_id)}:**\n"
                mentions = []
                for r in unpaid:
                    if r[1]:  # has user_id
                        mentions.append(f"[{r[2]}](tg://user?id={r[1]})")
                    else:
                        mentions.append(r[2])
                text += ", ".join(mentions) + "\n\n"
            
            # Pending confirmation - with 💰
            if pending:
                text += f"**{tr.t('payment_reminder_pending', lang_id)}:**\n"
                names = [f"{r[2]} 💰" for r in pending]
                text += ", ".join(names) + "\n\n"
            
            # Paid - with ✅
            if paid:
                text += f"**{tr.t('payment_reminder_paid', lang_id)}:**\n"
                names = [f"{r[2]} ✅" for r in paid]
                text += ", ".join(names) + "\n\n"
            
            # Get keyboard
            require_confirmation = settings.get('require_payment_confirmation', 0)
            reminder_kb = kb.get_payment_reminder_kb(regs, require_confirmation=require_confirmation, lang_id=lang_id)
            
            await message.answer(text, reply_markup=reminder_kb, parse_mode="Markdown")
            
    if total_goals > 0:
        all_players = []
        for t_key in draft_data['draft_teams']:
            all_players.extend(draft_data['draft_teams'][t_key])
        scoring_data = {
            "match_id": match_id,
            "total_goals": total_goals,
            "current_goal": 1,
            "is_autogol_mode": False,
            "players": all_players
        }
        await state.set_state(MatchScoring.waiting_for_scorers)
        # Initialize last_minute to 0
        await state.update_data(scoring_data=scoring_data, last_minute=0)
        await message.answer(
            tr.t("goal_scorer_prompt", lang_id).format(n=1),
            reply_markup=kb.get_goal_scorer_kb(all_players, lang_id=lang_id),
            parse_mode="Markdown"
        )
    else:
        await start_rating_phase(cid, tid, draft_data)

@router.message(MatchResult.waiting_for_score)
async def process_match_score(message: Message, state: FSMContext):
    if not await utils.is_admin(message, state):
        data = await state.get_data()
        cid = data.get('chat_id') or message.chat.id
        tid = data.get('thread_id') or 0
        lang_id = utils.get_chat_lang(cid, tid)
        sent = await message.answer(tr.t("no_admin_rights", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    import re
    if not re.match(r'^\d+[:\- ]\d+$', message.text):
        sent = await message.answer(tr.t("error_score_format", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    score = message.text.replace("-", ":").replace(" ", ":")
    await state.update_data(chat_id=cid, thread_id=tid)
    settings = db.get_match_settings(cid, tid)
    
    # Calculate match date (UTC)
    match_date_local = utils.get_match_date(settings.get('match_times'), settings.get('timezone'), find_past=True)
    match_date = None
    if match_date_local:
        # Convert back to UTC
        from datetime import timedelta
        tz_val = settings.get('timezone', 'GMT+3')
        offset = 3
        tm_match = re.search(r"GMT([+-]?\d+)", str(tz_val))
        if tm_match: offset = int(tm_match.group(1))
        match_date = match_date_local - timedelta(hours=offset)

    lang_id = settings.get('language_id', 1)
    # Check for existing match
    championship_name = settings.get('championship_name')
    existing_match = None
    if match_date:
        existing_match = db.get_match_by_criteria(cid, tid, match_date, championship_name)
    
    if existing_match:
        # Ask what to do
        await state.update_data(
            pending_match_data={
                "score": score,
                "match_date": str(match_date) if match_date else None,
                "championship_name": championship_name,
                "existing_match_id": existing_match['id']
            }
        )
        await state.set_state(MatchResult.waiting_for_exists_decision)
        text = tr.t("match_exists_warning", lang_id).format(score=existing_match['score'])
        await message.answer(text, reply_markup=kb.get_match_exists_kb(lang_id))
        return

    skill_id = settings.get('skill_level_id')
    skill = db.get_label_by_id("skill_levels", skill_id, lang_id) if skill_id else "—"
    
    match_id = db.create_match(cid, tid, skill, score, match_date=match_date, championship_name=championship_name)
    
    await finalize_match_setup(message, state, match_id, score, settings, lang_id, cid, tid)

@router.callback_query(F.data.startswith("match_decision_"), MatchResult.waiting_for_exists_decision)
async def process_match_exists_decision(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[2] # overwrite, new, cancel
    data = await state.get_data()
    pending = data.get('pending_match_data')
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    
    if action == "cancel":
        await state.clear()
        await callback.message.edit_text(tr.t("match_creation_cancelled", lang_id))
        await callback.answer()
        return
        
    skill_id = settings.get('skill_level_id')
    skill = db.get_label_by_id("skill_levels", skill_id, lang_id) if skill_id else "—"
    score = pending['score']
    championship_name = pending['championship_name']
    match_date = pending['match_date']
    
    match_id = None
    
    if action == "overwrite":
        match_id = pending['existing_match_id']
        db.clear_match_stats(match_id)
        db.update_match_score(match_id, score, skill, championship_name)
        await callback.answer(tr.t("match_overwritten", lang_id))
        await callback.message.delete() # Remove warning message
    elif action == "new":
        match_id = db.create_match(cid, tid, skill, score, match_date=match_date, championship_name=championship_name)
        await callback.answer()
        await callback.message.delete()

    # Pass callback.message or send a new message? 
    # finalize_match_setup sends a message using message.answer. 
    # We can use callback.message to send answer.
    await finalize_match_setup(callback.message, state, match_id, score, settings, lang_id, cid, tid)


async def finalize_match_setup(message, state, match_id, score, settings, lang_id, cid, tid):
    # Parse score
    g1, g2 = map(int, score.split(":"))
    total_goals = g1 + g2
    
    draft_data = db.get_draft_state(cid, tid)
    if not draft_data:
        return await message.answer(tr.t("error_no_teams_data", lang_id))
    draft_data['match_id'] = match_id
    draft_data['rated_teams'] = []
    db.set_draft_state(cid, tid, draft_data)
    season_match_num = db.get_season_match_number(cid, tid, match_id)
    match_saved_msg = tr.t("match_saved", lang_id).format(score=score, id=season_match_num)
    
    await message.answer(match_saved_msg)
    
    # Send payment reminder if enabled AND cost is set
    cost = settings.get('cost', '0')
    is_cost_set = cost and str(cost) != "0" and str(cost) != "—"
    
    if settings.get('remind_after_game', 1) and is_cost_set:
        regs = db.get_registrations(cid, tid)
        if regs:
            # Build payment reminder message
            text = f"**{tr.t('payment_reminder_title', lang_id)}**\n\n"
            
            # Group players by payment status
            unpaid = []  # is_paid = 0
            pending = []  # is_paid = 1
            paid = []  # is_paid = 2
            
            for r in regs:
                if r[8] == 0:
                    unpaid.append(r)
                elif r[8] == 1:
                    pending.append(r)
                else:
                    paid.append(r)
            
            # Unpaid players - with tags
            if unpaid:
                text += f"**{tr.t('payment_reminder_unpaid', lang_id)}:**\n"
                mentions = []
                for r in unpaid:
                    if r[1]:  # has user_id
                        mentions.append(f"[{r[2]}](tg://user?id={r[1]})")
                    else:
                        mentions.append(r[2])
                text += ", ".join(mentions) + "\n\n"
            
            # Pending confirmation - with 💰
            if pending:
                text += f"**{tr.t('payment_reminder_pending', lang_id)}:**\n"
                names = [f"{r[2]} 💰" for r in pending]
                text += ", ".join(names) + "\n\n"
            
            # Paid - with ✅
            if paid:
                text += f"**{tr.t('payment_reminder_paid', lang_id)}:**\n"
                names = [f"{r[2]} ✅" for r in paid]
                text += ", ".join(names) + "\n\n"
            
            # Get keyboard
            require_confirmation = settings.get('require_payment_confirmation', 0)
            reminder_kb = kb.get_payment_reminder_kb(regs, require_confirmation=require_confirmation, lang_id=lang_id)
            
            await message.answer(text, reply_markup=reminder_kb, parse_mode="Markdown")
            
    if total_goals > 0:
        all_players = []
        for t_key in draft_data['draft_teams']:
            all_players.extend(draft_data['draft_teams'][t_key])
        scoring_data = {
            "match_id": match_id,
            "total_goals": total_goals,
            "current_goal": 1,
            "is_autogol_mode": False,
            "players": all_players
        }
        await state.set_state(MatchScoring.waiting_for_scorers)
        # Initialize last_minute to 0
        await state.update_data(scoring_data=scoring_data, last_minute=0)
        await message.answer(
            tr.t("goal_scorer_prompt", lang_id).format(n=1),
            reply_markup=kb.get_goal_scorer_kb(all_players, lang_id=lang_id),
            parse_mode="Markdown"
        )
    else:
        await start_rating_phase(cid, tid, draft_data)

async def start_rating_phase(chat_id, thread_id, draft_data):
    # Check if rating is enabled
    settings = db.get_match_settings(chat_id, thread_id)
    rating_mode = settings.get('rating_mode', 'ranked')
    
    if rating_mode == 'disabled':
        # Skip rating entirely - check payment and finish match
        lang_id = utils.get_chat_lang(chat_id, thread_id)
        
        # Check if payment is complete
        if utils.is_payment_complete(chat_id, thread_id):
            # Match fully complete - clean everything up
            db.update_match_settings(chat_id, thread_id, "is_active", 0)
            db.clear_draft_state(chat_id, thread_id)
            db.clear_registrations(chat_id, thread_id)
            await bot.send_message(
                chat_id,
                tr.t("match_finished_full", lang_id),
                message_thread_id=thread_id if thread_id != 0 else None
            )
        else:
            # Waiting for payment - keep draft_data but mark ratings as done
            draft_data['ratings_done'] = True
            db.set_draft_state(chat_id, thread_id, draft_data)
            await bot.send_message(
                chat_id,
                tr.t("rating_done_waiting_payment", lang_id),
                message_thread_id=thread_id if thread_id != 0 else None
            )
        return
    
    caps = draft_data['draft_caps']
    teams = draft_data['draft_teams']
    lang_id = utils.get_chat_lang(chat_id, thread_id)
    for i, cap_id in enumerate(caps):
        team_color = tr.t("rating_team_red", lang_id) if i == 0 else tr.t("rating_team_white", lang_id)
        team_key = str(caps[0]) if i == 0 else str(caps[1])
        cap_obj = teams[team_key][0]
        if isinstance(cap_obj, dict):
            name = cap_obj.get('name', 'Unknown')
            tg_id = cap_obj.get('user_id')
        else:
            name = cap_obj[2] if len(cap_obj) > 2 else 'Unknown'
            tg_id = cap_obj[1] if len(cap_obj) > 1 else None
        tag = f"[{name}](tg://user?id={tg_id})" if tg_id else name
        await bot.send_message(
            chat_id,
            tr.t("cap_rating_invite", lang_id).format(tag=tag, team_color=team_color),
            reply_markup=kb.get_start_rating_kb(team_key, lang_id=lang_id),
            parse_mode="Markdown",
            message_thread_id=thread_id if thread_id != 0 else None
        )

@router.callback_query(F.data.startswith("rate_start_"))
async def process_rate_start(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    team_key = callback.data.split("_")[2]
    draft_data = db.get_draft_state(cid, tid)
    lang_id = utils.get_chat_lang(cid, tid)
    if not draft_data: return await callback.answer(tr.t("error_data_load", lang_id))
    teams = draft_data['draft_teams']
    team_players = [p for p in teams[team_key]]
    cap_obj = team_players[0]
    if cap_obj.get('user_id') and callback.from_user.id != cap_obj['user_id']:
        return await callback.answer(tr.t("error_only_captain_rate", lang_id), show_alert=True)
    points = len(team_players) - 1
    rateable = team_players[1:]
    rating_key = f"rating_{callback.message.chat.id}_{team_key}"
    temp_rating = {
        "points": points,
        "players": rateable,
        "results": [],
        "team_key": team_key,
        "match_id": draft_data['match_id'],
        "team_name": "Red" if team_key == str(draft_data['draft_caps'][0]) else "White"
    }
    await state.update_data({rating_key: temp_rating})
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    await callback.message.edit_text(
        tr.t("rating_title", lang_id) + "\n" + tr.t("rating_ask_points", lang_id).format(points=points),
        reply_markup=kb.get_rating_pick_kb(rateable),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("rate_pick_"))
async def process_rate_pick(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    data = await state.get_data()
    rating_key = None
    for k in data:
        if k.startswith("rating_") and isinstance(data[k], dict) and "players" in data[k]:
             if any(p['id'] == pid for p in data[k]['players']):
                rating_key = k
                break
    if not rating_key: 
        cid, tid = get_ids(callback)
        lang_id = utils.get_chat_lang(cid, tid)
        return await callback.answer(tr.t("error_session_expired", lang_id))
    curr = data[rating_key]
    picked = [p for p in curr['players'] if p['id'] == pid][0]
    curr['results'].append({"id": pid, "points": curr['points']})
    curr['players'] = [p for p in curr['players'] if p['id'] != pid]
    curr['points'] -= 1
    if curr['points'] > 0:
        await state.update_data({rating_key: curr})
        cid, tid = get_ids(callback)
        lang_id = utils.get_chat_lang(cid, tid)
        await callback.message.edit_text(
            tr.t("rating_title", lang_id) + "\n" + tr.t("rating_ask_points", lang_id).format(points=curr['points']),
            reply_markup=kb.get_rating_pick_kb(curr['players']),
            parse_mode="Markdown"
        )
    else:
        await state.update_data({rating_key: curr})
        cid, tid = get_ids(callback)
        lang_id = utils.get_chat_lang(cid, tid)
        draft_data = db.get_draft_state(cid, tid)
        
        # Check if best defender selection is enabled
        settings = db.get_match_settings(cid, tid)
        if settings.get('track_best_defender', 1):
            # Show defender selection
            all_team = draft_data['draft_teams'][curr['team_key']]
            await callback.message.edit_text(
                tr.t("defender_pick_title", lang_id) + "\n" + tr.t("defender_pick_prompt", lang_id),
                reply_markup=kb.get_defender_pick_kb(all_team),
                parse_mode="Markdown"
            )
        else:
            # Skip defender selection, finish rating
            await finalize_team_rating(callback, state, rating_key, None)


async def finalize_team_rating(callback, state, rating_key, defender_pid=None):
    """Finalize team rating with optional defender selection"""
    data = await state.get_data()
    curr = data[rating_key]
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Save player ratings
    for res in curr['results']:
        is_def = 1 if defender_pid and res['id'] == defender_pid else 0
        db.save_player_rating(curr['match_id'], res['id'], res['points'], curr['team_name'], is_def, is_captain=0)
    
    # Save captain rating
    draft_data = db.get_draft_state(cid, tid)
    cap_id = draft_data['draft_caps'][0] if curr['team_name'] == "Red" else draft_data['draft_caps'][1]
    if defender_pid and cap_id == defender_pid:
        db.save_player_rating(curr['match_id'], cap_id, 0, curr['team_name'], 1, is_captain=1)
    else:
        db.save_player_rating(curr['match_id'], cap_id, 0, curr['team_name'], 0, is_captain=1)
    
    await callback.message.edit_text(tr.t("rating_done", lang_id))
    
    # Track rated teams
    rated_teams = draft_data.get('rated_teams', [])
    if curr['team_key'] not in rated_teams:
        rated_teams.append(curr['team_key'])
        draft_data['rated_teams'] = rated_teams
        db.set_draft_state(cid, tid, draft_data)
    
    # Check if all teams rated
    if len(rated_teams) >= len(draft_data['draft_teams']):
        draft_data['ratings_done'] = True
        db.set_draft_state(cid, tid, draft_data)
        
        # Check payment completion
        if utils.is_payment_complete(cid, tid):
            db.update_match_settings(cid, tid, "is_active", 0)
            db.clear_draft_state(cid, tid)
            db.clear_registrations(cid, tid)
            await callback.message.answer(tr.t("match_finished_full", lang_id))
        else:
            await callback.message.answer(tr.t("rating_done_waiting_payment", lang_id))
    
    # Clear state
    del data[rating_key]
    await state.set_data(data)

@router.callback_query(F.data.startswith("def_pick_"))
async def process_def_pick(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    data = await state.get_data()
    rating_key = None
    for k in data:
        if k.startswith("rating_"):
             rating_key = k
             break
    if not rating_key: 
        cid, tid = get_ids(callback)
        lang_id = utils.get_chat_lang(cid, tid)
        return await callback.answer(tr.t("error_generic", lang_id))
    
    await finalize_team_rating(callback, state, rating_key, defender_pid=pid)


@router.callback_query(F.data == "goal_autogol_toggle", MatchScoring.waiting_for_scorers)
async def process_goal_autogol_toggle(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    s = data['scoring_data']
    s['is_autogol_mode'] = not s['is_autogol_mode']
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    await state.update_data(scoring_data=s)
    text = tr.t("goal_scorer_prompt", lang_id).format(n=s['current_goal'])
    if s['is_autogol_mode']:
        text += tr.t("goal_autogol_label", lang_id)
    await callback.message.edit_text(text, reply_markup=kb.get_goal_scorer_kb(s['players'], s['is_autogol_mode'], lang_id), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("goal_pick_"), MatchScoring.waiting_for_scorers)
async def process_goal_pick(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    data = await state.get_data()
    s = data['scoring_data']
    is_ag = s['is_autogol_mode']
    
    # Prefer cid/tid from state to ensure group context (useful for topics/PM)
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    if not cid:
        cid, tid = get_ids(callback)
        
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    draft_data = db.get_draft_state(cid, tid)
    
    player_team = "Unknown"
    for t_key in draft_data['draft_teams']:
        if any(p['id'] == pid for p in draft_data['draft_teams'][t_key]):
            player_team = "Red" if t_key == str(draft_data['draft_caps'][0]) else "White"
            break
    
    # Determine if scorer is captain
    draft_caps = draft_data.get('draft_caps', [])
    is_captain = 1 if pid in draft_caps else 0

    # Save goal/autogoal
    db.save_player_rating(
        match_id=s['match_id'],
        player_id=pid,
        points=0,
        team=player_team,
        goals=0 if is_ag else 1,
        autogoals=1 if is_ag else 0,
        is_captain=is_captain
    )
    
    # Check if we need to ask for goal time
    if settings.get('track_goal_times', 0):
        # Store current goal info and ask for minute
        await state.update_data(
            scoring_data=s,
            current_goal_player_id=pid,
            current_goal_is_autogoal=is_ag,
            current_goal_match_id=s['match_id']
        )
        
        event_type = "autogoal" if is_ag else "goal"
        goal_num = s['current_goal']
        last_minute = data.get('last_minute', 0)
        
        await callback.message.edit_text(
            tr.t(f"ask_{'autogoal' if is_ag else 'goal'}_minute", lang_id).format(num=goal_num),
            reply_markup=kb.get_minute_input_kb(pid, s['match_id'], event_type, goal_num, lang_id, min_val=last_minute)
        )
        await callback.answer()
        return
    
    # Check if we need to ask for assist
    if settings.get('track_assists', 0) and not is_ag:
        # We need an event to attach assist to. Since time is not tracked, we add event with NULL minute.
        # But wait, save_player_rating already updated stats? 
        # save_player_rating updates match_history. match_events is separate.
        # logic: if track_goal_times was OFF, we didn't add event before. Now we MUST add it to link assist.
        mh_id = db.get_match_history_id(s['match_id'], pid)
        if mh_id:
            event_id = db.add_match_event(mh_id, "goal", minute=None)
            
            # Ask for assist
            await state.update_data(
                scoring_data=s,
                current_goal_player_id=pid,
                current_goal_match_id=s['match_id'],
                current_event_id=event_id
            )
            
            await state.set_state(MatchScoring.waiting_for_assist)
            await callback.message.edit_text(
                tr.t("select_assist", lang_id),
                reply_markup=kb.get_assist_selection_kb(s['players'], pid, s['match_id'], lang_id)
            )
            await callback.answer()
            return
    
    # No time/assist tracking - proceed to next goal
    s['current_goal'] += 1
    s['is_autogol_mode'] = False
    if s['current_goal'] > s['total_goals']:
        await callback.message.edit_text(tr.t("all_goals_saved", lang_id))
        
        # Check if cards tracking is enabled
        if settings.get('track_cards', 0):
            # Start card input phase - DON'T clear state yet
            await start_card_input_phase(callback.message, draft_data, cid, tid, state)
        else:
            await state.clear()
            await start_rating_phase(cid, tid, draft_data)
    else:
        await state.update_data(scoring_data=s)
        text = tr.t("goal_scorer_prompt", lang_id).format(n=s['current_goal'])
        await callback.message.edit_text(text, reply_markup=kb.get_goal_scorer_kb(s['players'], lang_id=lang_id), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("event_minute_goal"), MatchScoring.waiting_for_scorers)
@router.callback_query(F.data.startswith("event_minute_autogoal"), MatchScoring.waiting_for_scorers)
async def process_goal_minute(callback: CallbackQuery, state: FSMContext):
    """Handle minute input for goal/autogoal during scoring phase"""
    parts = callback.data.split("_")
    # event_minute_{goal|autogoal}_{pid}_{match_id}_{num}_{minute}
    event_type = parts[2]  # "goal" or "autogoal"
    minute = int(parts[6]) if len(parts) > 6 else 0
    
    data = await state.get_data()
    s = data['scoring_data']
    pid = data.get('current_goal_player_id')
    match_id = data.get('current_goal_match_id')
    
    # Context from state
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    if not cid:
        cid, tid = get_ids(callback)
        
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    draft_data = db.get_draft_state(cid, tid)
    
    # Get match_history_id and save event with minute
    mh_id = db.get_match_history_id(match_id, pid)
    if mh_id:
        event_id = db.add_match_event(mh_id, event_type, minute=minute if minute > 0 else None)
        
    if minute > 0:
        await state.update_data(last_minute=minute)
    
    # Check for assist
    if settings.get('track_assists', 0) and event_type == "goal" and event_id:
        await state.update_data(current_event_id=event_id)
        await state.set_state(MatchScoring.waiting_for_assist)
        await callback.message.edit_text(
            tr.t("select_assist", lang_id),
            reply_markup=kb.get_assist_selection_kb(s['players'], pid, match_id, lang_id)
        )
        await callback.answer()
        return

    # Proceed to next goal
    s['current_goal'] += 1
    s['is_autogol_mode'] = False
    
    if s['current_goal'] > s['total_goals']:
        await callback.message.edit_text(tr.t("all_goals_saved", lang_id))
        
        # Check if cards tracking is enabled
        if settings.get('track_cards', 0):
            await start_card_input_phase(callback.message, draft_data, cid, tid, state)
        else:
            await state.clear()
            await start_rating_phase(cid, tid, draft_data)
    else:
        await state.update_data(scoring_data=s)
        text = tr.t("goal_scorer_prompt", lang_id).format(n=s['current_goal'])
        await callback.message.edit_text(text, reply_markup=kb.get_goal_scorer_kb(s['players'], lang_id=lang_id), parse_mode="Markdown")
    
    await callback.answer()

@router.callback_query(F.data.startswith("assist_pick_"), MatchScoring.waiting_for_assist)
@router.callback_query(F.data.startswith("assist_none_"), MatchScoring.waiting_for_assist)
@router.callback_query(F.data.startswith("assist_penalty_"), MatchScoring.waiting_for_assist)
async def process_assist_pick(callback: CallbackQuery, state: FSMContext):
    """Handle assist selection"""
    try:
        logger.info(f"PROCESS_ASSIST_PICK: {callback.data}")
        data = await state.get_data()
        s = data['scoring_data']
        event_id = data.get('current_event_id')
        
        # Context from state
        cid = data.get('chat_id')
        tid = data.get('thread_id', 0)
        if not cid:
            cid, tid = get_ids(callback)
            
        lang_id = utils.get_chat_lang(cid, tid)
        settings = db.get_match_settings(cid, tid)
        draft_data = db.get_draft_state(cid, tid)
        
        if callback.data.startswith("assist_pick_"):
            assist_pid = int(callback.data.split("_")[2])
            logger.info(f"Adding assist for pid={assist_pid}, event_id={event_id}")
            
            # Determine assisting player's team
            assist_team = "Unknown"
            for t_key in draft_data['draft_teams']:
                if any(p['id'] == assist_pid for p in draft_data['draft_teams'][t_key]):
                    assist_team = "Red" if t_key == str(draft_data['draft_caps'][0]) else "White"
                    break
            
            # Update event with assist_player_id
            if event_id:
                try:
                    db.update_match_event_assist(event_id, assist_pid)
                    logger.info("DB match event updated")
                except Exception as e:
                    logger.error(f"Error updating match event assist: {e}", exc_info=True)
            
            # Increment assist count in match_history
            try:
                db.save_assist(s['match_id'], assist_pid, assist_team)
                logger.info("DB assist saved")
            except Exception as e:
                logger.error(f"Error saving assist stats: {e}", exc_info=True)
                
            await callback.answer(tr.t("assist_added", lang_id))
        elif callback.data.startswith("assist_penalty_"):
             if event_id:
                 try:
                     db.mark_event_as_penalty(event_id)
                     logger.info("DB match event marked as penalty")
                 except Exception as e:
                     logger.error(f"Error marking penalty: {e}", exc_info=True)
             await callback.answer(tr.t("penalty_added", lang_id))
        else:
            logger.info("No assist selected")
            await callback.answer()
            
        # Return to scorers state
        await state.set_state(MatchScoring.waiting_for_scorers)

        # Proceed to next goal (Duplicate logic from process_goal_pick/minute)
        s['current_goal'] += 1
        s['is_autogol_mode'] = False
        
        # Log before proceeding
        logger.info(f"Proceeding to next goal. Current: {s['current_goal']}, Total: {s['total_goals']}")
        
        if s['current_goal'] > s['total_goals']:
            logger.info("All goals saved.")
            await callback.message.edit_text(tr.t("all_goals_saved", lang_id))
            
            if settings.get('track_cards', 0):
                await start_card_input_phase(callback.message, draft_data, cid, tid, state)
            else:
                await state.clear()
                await start_rating_phase(cid, tid, draft_data)
        else:
            await state.update_data(scoring_data=s)
            
            # We need to construct message for next goal
            text = tr.t("goal_scorer_prompt", lang_id).format(n=s['current_goal'])
            
            # Check if callback.message is editable (it should be)
            # If previous step was text input (process_goal_minute_text), it sent a NEW message.
            # So callback.message is that new message. Edit it.
            logger.info("Editing message for next goal scorer")
            await callback.message.edit_text(text, reply_markup=kb.get_goal_scorer_kb(s['players'], lang_id=lang_id), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"CRITICAL ERROR IN PROCESS_ASSIST_PICK: {e}", exc_info=True)
        await callback.answer("Error processing assist. See logs.", show_alert=True)

@router.message(MatchScoring.waiting_for_scorers, F.text.regexp(r'^\d+$'))
async def process_goal_minute_text(message: Message, state: FSMContext):
    """Handle text input for goal minute"""
    minute = int(message.text)
    data = await state.get_data()
    
    # Verify we are expecting a minute input
    pid = data.get('current_goal_player_id')
    if not pid:
         # Check if we are just selecting scorers (no player selected yet)
         # If no player selected, ignore or treat as error
         return 
         
    # Check bounds
    last_minute = data.get('last_minute', 0)
    if minute < last_minute:
        # Ideally warn user, but for now just ignore or accept? 
        # User requirement: "don't show buttons < last". "If user types, accept it as minutes."
        # Usually text input overrides UI constraints, but logically time flows forward.
        # Let's simple accept it but update last_minute.
        pass
        
    match_id = data.get('current_goal_match_id')
    s = data['scoring_data']
    is_ag = data.get('current_goal_is_autogoal')
    event_type = "autogoal" if is_ag else "goal"
    
    # Reuse logic from process_goal_minute callback? 
    # It's better to refactor, but for now duplicate logic to avoid changing too much.
    
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    draft_data = db.get_draft_state(cid, tid)

    mh_id = db.get_match_history_id(match_id, pid)
    event_id = None
    if mh_id:
        event_id = db.add_match_event(mh_id, event_type, minute=minute)
        
    await state.update_data(last_minute=minute)
    
    # Cleanup invalid message
    asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))

     # Check for assist
    if settings.get('track_assists', 0) and event_type == "goal" and event_id:
        await state.update_data(current_event_id=event_id)
        await state.set_state(MatchScoring.waiting_for_assist)
        await message.answer(
            tr.t("select_assist", lang_id),
            reply_markup=kb.get_assist_selection_kb(s['players'], pid, match_id, lang_id)
        )
        return

    # Proceed to next goal
    s['current_goal'] += 1
    s['is_autogol_mode'] = False
    
    if s['current_goal'] > s['total_goals']:
        await message.answer(tr.t("all_goals_saved", lang_id))
        
        if settings.get('track_cards', 0):
            await start_card_input_phase(message, draft_data, cid, tid, state)
        else:
            await state.clear()
            await start_rating_phase(cid, tid, draft_data)
    else:
        await state.update_data(scoring_data=s)
        text = tr.t("goal_scorer_prompt", lang_id).format(n=s['current_goal'])
        await message.answer(text, reply_markup=kb.get_goal_scorer_kb(s['players'], lang_id=lang_id), parse_mode="Markdown")

@router.message(MatchEvents.entering_cards, F.text.regexp(r'^\d+$'))
async def process_card_minute_text(message: Message, state: FSMContext):
    """Handle text input for card minute"""
    minute = int(message.text)
    data = await state.get_data()
    
    # Verify we are expecting minute
    card_type = data.get('current_card_type')
    mh_id = data.get('current_mh_id')
    
    if not card_type or not mh_id:
        return
        
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)

    # Save card with minute
    db.add_match_event(mh_id, card_type, minute=minute)
    await state.update_data(last_minute=minute)
    
    # Cleanup invalid message
    asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
    
    # Also save to match_history for aggregated stats
    draft_data = db.get_draft_state(cid, tid)
    pid = data.get('current_card_player_id')
    player_team = "Unknown"
    for t_key in draft_data['draft_teams']:
        if any(p['id'] == pid for p in draft_data['draft_teams'][t_key]):
            player_team = "Red" if t_key == str(draft_data['draft_caps'][0]) else "White"
            break
            
    # Increment card count
    match_id = data.get('match_id') 
    if card_type == "yellow_card":
        db.save_player_rating(match_id, pid, 0, player_team, yellow_cards=1)
    else:  # red_card
        db.save_player_rating(match_id, pid, 0, player_team, red_cards=1)
    
    await message.answer(tr.t("event_added", lang_id))
    
    # Return to player selection
    regs = db.get_registrations(cid, tid)
    await message.answer(
        tr.t("ask_card_player", lang_id),
        reply_markup=kb.get_card_player_kb(regs, match_id, lang_id),
        parse_mode="Markdown"
    )

async def start_card_input_phase(message, draft_data, cid, tid, state):
    """Start the card input phase for entering yellow/red cards"""
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Get all players from both teams
    all_players = []
    for t_key in draft_data['draft_teams']:
        all_players.extend(draft_data['draft_teams'][t_key])
    
    # Store state for card input
    await state.update_data(
        card_players=all_players,
        match_id=draft_data['match_id'],
        chat_id=cid,
        thread_id=tid,
        draft_data=draft_data
    )
    await state.set_state(MatchEvents.entering_cards)
    
    # Get registrations for player list
    regs = db.get_registrations(cid, tid)
    
    await message.answer(
        tr.t("ask_card_player", lang_id),
        reply_markup=kb.get_card_player_kb(regs, draft_data['match_id'], lang_id),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("event_card_player_"))
async def process_card_player_select(callback: CallbackQuery, state: FSMContext):
    """Handle player selection for card"""
    parts = callback.data.split("_")
    pid = int(parts[3])
    match_id = int(parts[4])
    
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Get player info
    p = db.get_player_by_id(pid, cid, tid)
    name = p[2] if p else "Unknown"
    
    await state.update_data(current_card_player_id=pid, current_card_player_name=name)
    
    await callback.message.edit_text(
        tr.t("ask_card_type", lang_id).format(name=name),
        reply_markup=kb.get_card_type_kb(pid, match_id, lang_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("event_card_"))
async def process_card_type_select(callback: CallbackQuery, state: FSMContext):
    """Handle card type selection (yellow/red)"""
    parts = callback.data.split("_")
    # event_card_{pid}_{match_id}_{card_type}
    # card_type is "yellow_card" or "red_card" (contains underscore!)
    if len(parts) < 6:
        return await callback.answer("Invalid data")
    
    pid = int(parts[2])
    match_id = int(parts[3])
    card_type = f"{parts[4]}_{parts[5]}"  # yellow_card or red_card
    
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    
    # Get match_history_id for this player
    mh_id = db.get_match_history_id(match_id, pid)
    if not mh_id:
        await callback.answer("Player not in match history", show_alert=True)
        return
    
    # Check if we need to ask for minute
    if settings.get('track_card_times', 0):
        last_minute = data.get('last_minute', 0)
        await state.update_data(
            current_card_type=card_type,
            current_mh_id=mh_id
        )
        await callback.message.edit_text(
            tr.t("ask_card_minute", lang_id),
            reply_markup=kb.get_minute_input_kb(pid, match_id, card_type, 1, lang_id, min_val=last_minute)
        )
    else:
        # Save card without minute
        db.add_match_event(mh_id, card_type, minute=None)
        
        # Also save to match_history for aggregated stats
        draft_data = db.get_draft_state(cid, tid)
        player_team = "Unknown"
        for t_key in draft_data['draft_teams']:
            if any(p['id'] == pid for p in draft_data['draft_teams'][t_key]):
                player_team = "Red" if t_key == str(draft_data['draft_caps'][0]) else "White"
                break
        
        # Increment card count
        if card_type == "yellow_card":
            db.save_player_rating(match_id, pid, 0, player_team, yellow_cards=1)
        else:  # red_card
            db.save_player_rating(match_id, pid, 0, player_team, red_cards=1)
        
        await callback.answer(tr.t("event_added", lang_id))
        
        # Return to player selection
        regs = db.get_registrations(cid, tid)
        await callback.message.edit_text(
            tr.t("ask_card_player", lang_id),
            reply_markup=kb.get_card_player_kb(regs, match_id, lang_id),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("event_minute_"))
async def process_card_minute(callback: CallbackQuery, state: FSMContext):
    """Handle minute input for card"""
    parts = callback.data.split("_")
    # event_minute_{card_type}_{pid}_{match_id}_{num}_{minute}
    # card_type can be "yellow_card" or "red_card" (contains underscore!)
    
    # Reconstruct card_type (parts[2] + "_" + parts[3])
    card_type = f"{parts[2]}_{parts[3]}"  # yellow_card or red_card
    pid = int(parts[4])
    match_id = int(parts[5])
    # event_num is parts[6], not used here
    minute = int(parts[7]) if len(parts) > 7 else 0
    
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    mh_id = data.get('current_mh_id')
    
    if not mh_id:
        mh_id = db.get_match_history_id(match_id, pid)
    
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Card event: type='{card_type}', mh_id={mh_id}, minute={minute}")
    
    
    # Save card with minute
    db.add_match_event(mh_id, card_type, minute=minute if minute > 0 else None)
    
    if minute > 0:
        await state.update_data(last_minute=minute)
    
    # Also save to match_history for aggregated stats
    draft_data = db.get_draft_state(cid, tid)
    player_team = "Unknown"
    for t_key in draft_data['draft_teams']:
        if any(p['id'] == pid for p in draft_data['draft_teams'][t_key]):
            player_team = "Red" if t_key == str(draft_data['draft_caps'][0]) else "White"
            break
    
    # Increment card count
    if card_type == "yellow_card":
        db.save_player_rating(match_id, pid, 0, player_team, yellow_cards=1)
    else:  # red_card
        db.save_player_rating(match_id, pid, 0, player_team, red_cards=1)
    
    await callback.answer(tr.t("event_added", lang_id))
    
    # Return to player selection
    regs = db.get_registrations(cid, tid)
    await callback.message.edit_text(
        tr.t("ask_card_player", lang_id),
        reply_markup=kb.get_card_player_kb(regs, match_id, lang_id),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("event_cards_done_"))
async def process_cards_done(callback: CallbackQuery, state: FSMContext):
    """Handle completion of card input"""
    data = await state.get_data()
    cid = data.get('chat_id')
    tid = data.get('thread_id', 0)
    draft_data = data.get('draft_data')
    
    await state.clear()
    lang_id = utils.get_chat_lang(cid, tid)
    await callback.message.edit_text(tr.t("cards_saved", lang_id))
    
    # Proceed to rating phase
    if draft_data:
        await start_rating_phase(cid, tid, draft_data)

# --- PAIRS CONTEST ---

@router.callback_query(F.data == "confirm_payment_all")
async def process_payment_confirm_all(callback: CallbackQuery, state: FSMContext):
    """Handle 'Paid All' button click"""
    # Check admin rights
    if not await utils.is_admin(callback, state):
        return await callback.answer(tr.t("no_admin_rights", 1), show_alert=True)
        
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    
    # Get registrations
    regs = db.get_registrations(cid, tid)
    if not regs:
        return await callback.answer()
        
    # Mark all valid registrations as paid (is_paid=2)
    for r in regs:
        pid = r[0]
        db.update_payment_status(pid, cid, tid, 2)
        
    # Refresh payment reminder message
    await refresh_payment_reminder(callback.message, cid, tid, lang_id)

    # Check for match completion
    if utils.is_payment_complete(cid, tid):
        settings = db.get_match_settings(cid, tid)
        draft_data = db.get_draft_state(cid, tid)
        rating_mode = settings.get('rating_mode', 'ranked')
        
        # Consider match finished if:
        # A) Rating is disabled
        # B) Ratings are already marked as done (waiting for payment)
        if rating_mode == 'disabled' or (draft_data and draft_data.get('ratings_done')):
             # Match fully complete - clean everything up
            db.update_match_settings(cid, tid, "is_active", 0)
            db.clear_draft_state(cid, tid)
            db.clear_registrations(cid, tid)
            await callback.message.answer(
                tr.t("match_finished_full", lang_id),
                message_thread_id=tid if tid != 0 else None
            )

@router.callback_query(F.data.startswith("pairs_sel_"))
async def pairs_sel_cb(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    data = await state.get_data()
    sel = data.get("selected_ids", [])
    if pid in sel:
        sel.remove(pid)
    else:
        sel.append(pid)
    await state.update_data(selected_ids=sel)
    avail = data.get("avail_players", [])
    phase = "left" if await state.get_state() == PairsBuilder.selecting_left else "right"
    can_proceed = len(sel) > 0
    if phase == "right":
        left = data.get("left_side", [])
        if len(sel) != len(left):
            can_proceed = False
    await callback.message.edit_reply_markup(reply_markup=kb.get_pairs_builder_kb(avail, sel, phase, can_proceed))
    await callback.answer()

@router.callback_query(F.data == "pairs_next")
async def pairs_next_cb(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    sel_ids = data.get("selected_ids", [])
    if not sel_ids: return await callback.answer(tr.t("error_select_someone", lang_id))
    avail = data.get("avail_players", [])
    left_players = [p for p in avail if p['id'] in sel_ids]
    remaining = [p for p in avail if p['id'] not in sel_ids]
    if not remaining:
        return await callback.answer(tr.t("error_no_players_remaining", lang_id), show_alert=True)
    await state.update_data(left_side=left_players, avail_players=remaining, selected_ids=[])
    await state.set_state(PairsBuilder.selecting_right)
    txt_left = ", ".join([p['name'] for p in left_players])
    await callback.message.edit_text(
        tr.t("pairs_select_right", lang_id).format(left=txt_left),
        reply_markup=kb.get_pairs_builder_kb(remaining, [], "right", False)
    )
    await callback.answer()

@router.callback_query(F.data == "pairs_save")
async def pairs_save_cb(callback: CallbackQuery, state: FSMContext):
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    data = await state.get_data()
    sel_ids = data.get("selected_ids", [])
    left = data.get("left_side", [])
    if len(sel_ids) != len(left):
        return await callback.answer(tr.t("error_select_exact", lang_id).format(n=len(left)), show_alert=True)
    avail = data.get("avail_players", [])
    right_players = [p for p in avail if p['id'] in sel_ids]
    remaining = [p for p in avail if p['id'] not in sel_ids]
    pairs = data.get("finished_pairs", [])
    pairs.append({"left": left, "right": right_players})
    if not remaining:
        await finish_pairs_contest(callback, state, pairs, data['chat_id'], data['thread_id'])
        return
    await state.update_data(avail_players=remaining, finished_pairs=pairs, left_side=[], right_side=[], selected_ids=[])
    await state.set_state(PairsBuilder.selecting_left)
    await callback.message.edit_text(
        tr.t("pairs_recorded", lang_id).format(n=len(remaining)),
        reply_markup=kb.get_pairs_builder_kb(remaining, [], "left", False)
    )
    await callback.answer()

async def finish_pairs_contest(callback, state, pairs, cid, tid):
    lang_id = utils.get_chat_lang(cid, tid)
    t1 = []
    t2 = []
    for p in pairs:
        t1.extend(p['left'])
        t2.extend(p['right'])
    s1 = sum(p['ovr'] for p in t1)
    s2 = sum(p['ovr'] for p in t2)
    draft_data = db.get_draft_state(cid, tid)
    if not draft_data:
        draft_data = {"draft_teams": {}, "draw_variants": {}, "variant_msg_ids": {}, "rated_teams": []}
    import time
    v_id = int(time.time()) % 1000 + 1000
    existing_vars = draft_data.get("draw_variants", {})
    existing_vars[str(v_id)] = {"t1": t1, "t2": t2, "s1": s1, "s2": s2, "mode": "contest", "pairs": pairs}
    draft_data["draw_variants"] = existing_vars
    db.set_draft_state(cid, tid, draft_data)
    user_name = callback.from_user.full_name
    text = tr.t("pairs_variant_title", lang_id).format(name=user_name) + "\n"
    for i, p in enumerate(pairs, 1):
        l_names = ", ".join(x['name'] for x in p['left'])
        r_names = ", ".join(x['name'] for x in p['right'])
        text += tr.t("pairs_pair_label", lang_id).format(i=i, left=l_names, right=r_names) + "\n"
    text += "\n"
    text += tr.t("team_red", lang_id) + f" ({tr.t('total_players', lang_id)}: {int(s1)})\n"
    text += tr.t("team_white", lang_id) + f" ({tr.t('total_players', lang_id)}: {int(s2)})"
    group_msg = await bot.send_message(
        cid, 
        text, 
        message_thread_id=tid if tid != 0 else None,
        reply_markup=kb.get_vote_kb(v_id),
        parse_mode="Markdown"
    )
    draft_data = db.get_draft_state(cid, tid)
    msg_ids = draft_data.get("variant_msg_ids", {})
    msg_ids[str(v_id)] = group_msg.message_id
    draft_data["variant_msg_ids"] = msg_ids
    db.set_draft_state(cid, tid, draft_data)
    await callback.message.edit_text(f"{tr.t('pairs_sent_group', lang_id)}\n[{tr.t('pairs_go_to_msg', lang_id)}]({group_msg.get_url()})", parse_mode="Markdown")
    await state.clear()

@router.callback_query(F.data == "contest_finish_best")
async def process_contest_finish_best(callback: CallbackQuery, state: FSMContext):
    if not await utils.is_admin(callback, state): return
    cid, tid = get_ids(callback)
    lang_id = utils.get_chat_lang(cid, tid)
    votes_stats = db.get_all_variant_votes(cid, tid)
    draft_data = db.get_draft_state(cid, tid)
    if not draft_data or "draw_variants" not in draft_data:
        return await callback.answer(tr.t("error_contest_no_variants", lang_id), show_alert=True)
    variants = draft_data["draw_variants"]
    contest_vars = []
    for row in votes_stats:
        vid = str(row[0])
        if vid in variants and variants[vid].get("mode") == "contest":
            contest_vars.append({"id": vid, "count": row[1], "time": row[2], "data": variants[vid]})
    if not contest_vars:
        return await callback.answer(tr.t("error_contest_no_votes", lang_id), show_alert=True)
    contest_vars.sort(key=lambda x: (-x['count'], x['time']))
    winner = contest_vars[0]
    w_data = winner['data']
    pairs = w_data.get("pairs", [])
    if not pairs:
        return await callback.answer(tr.t("error_contest_data_lost", lang_id), show_alert=True)
    t1 = []
    t2 = []
    import random
    for p in pairs:
        left = p['left']
        right = p['right']
        if random.random() < 0.5:
            t1.extend(left)
            t2.extend(right)
        else:
            t1.extend(right)
            t2.extend(left)
    s1 = sum(p['ovr'] for p in t1)
    s2 = sum(p['ovr'] for p in t2)
    if t1 and t2:
        caps = [t1[0]['id'], t2[0]['id']]
    else:
        caps = []
    final_data = {"draft_teams": {str(caps[0]): t1, str(caps[1]): t2}, "draft_caps": caps, "admin_id": callback.from_user.id}
    draft_data.update(final_data)
    db.set_draft_state(cid, tid, draft_data)
    await send_draw_variant(callback.message, t1, t2, s1, s2, mode="best_contest", v_id=0, is_vote=False, type_label=tr.t("pairs_result_label", lang_id).format(id=winner['id']), captains=caps, kb_markup=kb.get_score_entry_kb(lang_id))
    await callback.answer()

# --- POLL & SETUP ---

@router.message(Command("poll"))
async def cmd_poll(message: Message, state: FSMContext):
    if message.chat.type == 'private':
        return  # Ignore in private chat
    if not await utils.is_admin(message, state):
        cid, tid = get_ids(message)
        lang_id = utils.get_chat_lang(cid, tid)
        sent = await message.answer(tr.t("no_admin_rights", lang_id))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        return
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    if settings.get('is_active'):
        sent1 = await message.answer(tr.t("finish_match_first", lang_id))
        sent2 = await message.answer(tr.t("restore_poll", lang_id), link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        db.update_match_settings(cid, tid, "poll_message_id", sent2.message_id)
        await utils.update_poll_message(sent2)
        asyncio.create_task(utils.auto_delete_message(message.chat.id, sent1.message_id, delay_seconds=15))
        asyncio.create_task(utils.auto_delete_message(message.chat.id, message.message_id, delay_seconds=15))
        # Don't auto-delete poll message (sent2) - it should stay visible
        return
    
    # Check if initial setup is needed (settings record doesn't exist = new chat/topic)
    # We check the database directly because get_match_settings returns defaults even if no record exists
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT language_id FROM settings WHERE chat_id = %s AND thread_id = %s", (cid, tid))
    existing_settings = cursor.fetchone()
    conn.close()
    
    if not existing_settings or not existing_settings[0]:
        # Start initial setup with language selection
        await message.answer(
            tr.t("welcome_select_lang", 1),
            reply_markup=kb.get_language_selection_kb(cid, tid)
        )
        return
    
    settings = db.get_match_settings(cid, tid)
    await state.clear()
    await state.update_data(setup_mode=True, chat_id=cid, thread_id=tid)
    await utils.track_msg(state, message.message_id)
    await proceed_from_player_count(message, state, settings['player_count'])

@router.message(MatchSettings.waiting_for_player_count)
async def process_player_count(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    try:
        count = int(message.text)
        data = await state.get_data()
        cid = data.get('chat_id') or message.chat.id
        tid = data.get('thread_id') or (message.message_thread_id or 0)
        db.update_match_settings(cid, tid, "player_count", count)
        await proceed_from_player_count(message, state, count)
    except ValueError:
        sent = await message.answer(tr.t("enter_number_error", lang_id))
        await utils.track_msg(state, sent.message_id)

async def proceed_from_player_count(message: Message, state: FSMContext, count: int):
    data = await state.get_data()
    cid = data.get('chat_id') or (message.chat.id if isinstance(message, Message) else message.message.chat.id)
    tid = data.get('thread_id') or 0
    lang_id = utils.get_chat_lang(cid, tid)
    settings = db.get_match_settings(cid, tid)
    is_setup = data.get('setup_mode', False)
    if not is_setup:
        return await show_admin_settings_menu(message if isinstance(message, Message) else message.message, state)
    if settings['skill_level_id'] is None:
        try:
            sent = await message.answer(tr.t("ask_skill", lang_id), reply_markup=kb.get_skill_level_kb(lang_id))
            await utils.track_msg(state, sent.message_id)
            await state.set_state(MatchSettings.waiting_for_skill_level)
        except TelegramBadRequest as e:
            if "TOPIC_CLOSED" in str(e):
                return  # Exit gracefully if topic is closed
            raise
    elif settings['age_group_id'] is None:
        sent = await message.answer(tr.t("ask_age", lang_id), reply_markup=kb.get_age_group_kb(lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(MatchSettings.waiting_for_age_group)
    elif settings['gender_id'] is None:
        sent = await message.answer(tr.t("ask_gender", lang_id), reply_markup=kb.get_gender_kb(lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(MatchSettings.waiting_for_gender)
    elif settings['venue_type_id'] is None:
        sent = await message.answer(tr.t("ask_venue", lang_id), reply_markup=kb.get_venue_type_kb(lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(MatchSettings.waiting_for_venue) 
    elif settings['cost'] in [None, "—"]:
        sent = await message.answer(tr.t("ask_cost", lang_id))
        await utils.track_msg(state, sent.message_id)
        await state.set_state(MatchSettings.waiting_for_cost)
    else:
        await finish_poll_setup(message, state)

@router.callback_query(F.data.startswith("skill_"), MatchSettings.waiting_for_skill_level)
async def process_skill_level(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get('chat_id') or callback.message.chat.id
    tid = data.get('thread_id', 0)
    lang_id = utils.get_chat_lang(cid, tid)
    val_id = int(callback.data.split("_")[1])
    db.update_match_settings(cid, tid, "skill_level_id", val_id)
    label = db.get_label_by_id("skill_levels", val_id, lang_id)
    await utils.track_msg(state, callback.message.message_id)
    await proceed_from_player_count(callback.message, state, 0)
    await callback.answer(tr.t("set_installed", lang_id).format(val=label))

@router.callback_query(F.data.startswith("age_"), MatchSettings.waiting_for_age_group)
async def process_age_group(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id', callback.message.chat.id), data.get('thread_id', 0))
    val_id = int(callback.data.split("_")[1])
    db.update_match_settings(data.get('chat_id', callback.message.chat.id), data.get('thread_id', 0), "age_group_id", val_id)
    label = db.get_label_by_id("age_groups", val_id, lang_id)
    await utils.track_msg(state, callback.message.message_id)
    await proceed_from_player_count(callback.message, state, 0)
    await callback.answer(tr.t("set_installed", lang_id).format(val=label))

@router.callback_query(F.data.startswith("gender_"), MatchSettings.waiting_for_gender)
async def process_gender(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id', callback.message.chat.id), data.get('thread_id', 0))
    val_id = int(callback.data.split("_")[1])
    db.update_match_settings(data.get('chat_id', callback.message.chat.id), data.get('thread_id', 0), "gender_id", val_id)
    label = db.get_label_by_id("genders", val_id, lang_id)
    await utils.track_msg(state, callback.message.message_id)
    await proceed_from_player_count(callback.message, state, 0)
    await callback.answer(tr.t("set_installed", lang_id).format(val=label))

@router.callback_query(F.data.startswith("venue_"), MatchSettings.waiting_for_venue)
async def process_venue_type(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_id = utils.get_chat_lang(data.get('chat_id', callback.message.chat.id), data.get('thread_id', 0))
    val_id = int(callback.data.split("_")[1])
    db.update_match_settings(data.get('chat_id', callback.message.chat.id), data.get('thread_id', 0), "venue_type_id", val_id)
    label = db.get_label_by_id("venue_types", val_id, lang_id)
    await utils.track_msg(state, callback.message.message_id)
    await proceed_from_player_count(callback.message, state, 0)
    await callback.answer(tr.t("set_installed", lang_id).format(val=label))

@router.message(MatchSettings.waiting_for_cost)
async def process_match_cost_handler(message: Message, state: FSMContext):
    await utils.track_msg(state, message.message_id)
    data = await state.get_data()
    cid = data.get('chat_id') or message.chat.id
    tid = data.get('thread_id') or 0
    db.update_match_settings(cid, tid, "cost", message.text)
    
    cost_from = data.get("cost_from")
    if cost_from == "payment":
        await state.update_data(cost_from=None)
        # Send payment menu as a new message instead of editing
        lang_id = utils.get_chat_lang(cid, tid)
        settings = db.get_match_settings(cid, tid)
        text = f"**{tr.t('admin_payment', lang_id)}**\n\n"
        text += f"{tr.t('setting_cost', lang_id)}: {settings.get('cost', '—')}\n"
        text += f"{tr.t('admin_reminders_settings', lang_id)}:\n"
        text += f"  - {tr.t('remind_before_game', lang_id)}: {'✅' if settings.get('remind_before_game') else '❌'}\n"
        text += f"  - {tr.t('remind_after_game', lang_id)}: {'✅' if settings.get('remind_after_game') else '❌'}\n"
        await message.answer(text, reply_markup=kb.get_admin_payment_kb(cid, tid, lang_id, settings), parse_mode="Markdown")
    else:
        await proceed_from_player_count(message, state, 0)

async def finish_poll_setup(message: Message, state: FSMContext):
    cid, tid = get_ids(message)
    lang_id = utils.get_chat_lang(cid, tid)
    db.update_match_settings(cid, tid, "is_active", 1)
    settings = db.get_match_settings(cid, tid) or {}
    data = await state.get_data()
    poll_id = data.get('poll_msg_id')
    exclude = [poll_id] if poll_id else []
    await utils.cleanup_msgs(cid, state, exclude_ids=exclude)
    await state.clear()
    sent = await message.answer(tr.t("start_poll_msg", lang_id), reply_markup=kb.get_registration_kb(0, lang_id, lat=settings.get('location_lat'), lon=settings.get('location_lon')), link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    db.update_match_settings(cid, tid, "poll_message_id", sent.message_id)
    await utils.update_poll_message(sent)

