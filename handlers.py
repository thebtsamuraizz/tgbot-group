import logging
from telegram import Update, Bot, __version__ as bot_version
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from keyboards import main_menu, users_list_kb, profile_actions_kb, confirm_delete_kb, report_categories_kb, new_profile_preview_kb, edit_profile_preview_kb, profile_menu_kb, admin_review_kb, admin_manage_profiles_kb, admin_profile_action_kb, afk_reason_kb, admin_app_reason_kb
from templates.messages import *
import db
import utils
import config
from utils import iso_now, parse_profile_text, short_profile_card
from typing import Dict, Any
from functools import lru_cache
from time import time
from cache_manager import profile_cache
from rate_limiter import check_rate_limit, retry_telegram_request
from validators import validate_profile_text, sanitize_text, sanitize_profile_data

logger = logging.getLogger(__name__)

# Simple in-memory cache for frequently accessed data with TTL
_cache = {}
_cache_ttl = 60  # Cache timeout in seconds


def _get_cached(key: str, default=None):
    """Get value from cache if not expired"""
    if key in _cache:
        value, timestamp = _cache[key]
        if time() - timestamp < _cache_ttl:
            return value
        else:
            del _cache[key]
    return default


def _set_cache(key: str, value):
    """Set value in cache with current timestamp"""
    _cache[key] = (value, time())


### MAIN MENU

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.full_name if user else 'пользователь'
    welcome_msg = WELCOME.format(name=name)
    credit = "\n\n━━━━━━━━━━━━━━━━━━\n📱 Разработано от @thebitsamuraiizz"
    await update.message.reply_text(welcome_msg + credit, reply_markup=main_menu())


### USERS LIST

async def users_list_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # send single message with inline keyboard
    # Always get fresh list from DB (don't cache for accuracy)
    profiles = db.get_all_profiles(status='approved')
    
    usernames = [p['username'] for p in profiles]
    await update.message.reply_text(USERS_LIST_PROMPT, reply_markup=users_list_kb(usernames))


async def admins_list_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # send admins list
    await update.message.reply_text(ADMINS_LIST)


async def view_profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data.split(':', 1)[1]
    profile = db.get_profile_by_username(data)
    if not profile:
        await q.message.reply_text(PROFILE_NOT_FOUND)
        return
    is_admin = (q.from_user.id in config.ADMIN_IDS)
    card = short_profile_card(profile)
    await q.message.reply_text(card, reply_markup=profile_actions_kb(data, is_admin, q.from_user.id, profile.get('added_by_id')))


async def back_to_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    
    # Check if going back to profiles
    if q.data == 'back:profiles':
        await admin_manage_profiles(update, context)
        return
    
    # Always get fresh list from DB (don't cache for accuracy)
    profiles = db.get_all_profiles()
    
    usernames = [p['username'] for p in profiles]
    # send list again
    await q.message.reply_text(USERS_LIST_PROMPT, reply_markup=users_list_kb(usernames))


### PROFILE EDIT / DELETE (admin)

async def edit_profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    username = q.data.split(':', 1)[1]
    user = q.from_user
    # Allow user to edit their own profile or admins to edit any
    profile = db.get_profile_by_username(username)
    if not profile:
        await q.message.reply_text("Профиль не найден.")
        return -1
    
    if user.id != profile['added_by_id'] and user.id not in config.ADMIN_IDS:
        await q.message.reply_text("Доступ запрещён: вы можете редактировать только свою анкету.")
        return -1
    
    context.user_data['edit_username'] = username
    current_text = profile.get('note', '')
    await q.message.reply_text(f"Редактируете @{username}.\n\nТекущая анкета:\n{current_text}\n\nОтправьте новый текст анкеты:")
    return EP_WAIT_TEXT


async def edit_profile_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    username = context.user_data.get('edit_username')
    if not username:
        return -1
    
    text = update.message.text or ""
    logger.info("edit_profile_receive: user=%s username=%s text=%s", user.id if user else None, username, text[:120])
    
    # Show preview of edited profile
    profile = db.get_profile_by_username(username)
    if not profile:
        await update.message.reply_text("Профиль не найден.")
        return -1
    
    # Update the note field in preview
    profile['note'] = text
    context.user_data['edit_profile_preview'] = profile
    await update.message.reply_text(short_profile_card(profile), reply_markup=edit_profile_preview_kb())
    return -1


async def edit_profile_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    profile = context.user_data.get('edit_profile_preview')
    username = context.user_data.get('edit_username')
    if not profile or not username:
        await q.message.reply_text("Нет данных для сохранения.")
        return
    
    try:
        logger.info('edit_profile_confirm_cb: user %s updated profile %s', q.from_user and q.from_user.id, username)
        # Update existing profile with new note
        changes = {'note': profile.get('note')}
        ok = db.update_profile(username, changes)
        if ok:
            await q.message.reply_text("✅ Ваши изменения отправлены на проверку администратору!")
            
            # Notify super-admin for review of the change
            try:
                admin_id = config.SUPER_ADMIN_ID
                card = short_profile_card(profile)
                await context.bot.send_message(chat_id=admin_id, text=f"Обновление анкеты @{username} на ревью:\n{card}")
                logger.info('edit_profile_confirm_cb: sent review message to super_admin=%s for user=%s', admin_id, username)
            except Exception:
                logger.exception("Failed to notify super admin about profile update for %s", username)
        else:
            await q.message.reply_text("Ошибка при обновлении анкеты.")
        
        context.user_data.pop('edit_profile_preview', None)
        context.user_data.pop('edit_username', None)
    except Exception as e:
        logger.exception("Failed to update profile: %s", e)
        await q.message.reply_text("Ошибка при обновлении анкеты.")


async def delete_profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    username = q.data.split(':', 1)[1]
    if q.from_user.id not in config.ADMIN_IDS:
        await q.message.reply_text("Доступ запрещён: только админ может удалять.")
        return
    await q.message.reply_text(DELETE_CONFIRM_PROMPT.format(username=username), reply_markup=confirm_delete_kb(username))


async def delete_profile_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    username = q.data.split(':', 1)[1]
    ok = db.delete_profile(username)
    if ok:
        # Clear from persistent cache
        profile_cache.delete(username)
        # Clear from local cache
        _cache.pop('all_profiles', None)
        _cache.pop('all_approved_profiles', None)
        await q.message.reply_text(f"Пользователь @{username} удалён.")
        logger.info('delete_profile_confirm_cb: profile @%s deleted and cleared from cache', username)
    else:
        await q.message.reply_text(f"Не удалось удалить @{username} — возможно пользователь отсутствует.")


### PROFILE MENU (check if user has profile)

async def profile_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show menu: Create new or Edit existing profile"""
    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text(NO_USERNAME_ERROR)
        return
    
    # Check if user already has an APPROVED profile
    profile = db.get_profile_by_username(user.username)
    has_profile = profile is not None and profile.get('status') == 'approved'
    
    if has_profile:
        await update.message.reply_text(f"У вас уже есть анкета (@{user.username}). Что вы хотите сделать?", 
                                       reply_markup=profile_menu_kb(has_profile=True))
    else:
        await update.message.reply_text("Создайте свою анкету:", 
                                       reply_markup=profile_menu_kb(has_profile=False))


async def profile_new_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start creating new profile (only for users without one)"""
    q = update.callback_query
    await q.answer()
    
    user = update.effective_user
    if not user or not user.username:
        await q.message.reply_text(NO_USERNAME_ERROR)
        return -1
    
    # Check if user already has an APPROVED profile
    profile = db.get_profile_by_username(user.username)
    if profile and profile.get('status') == 'approved':
        await q.message.reply_text("У вас уже есть одобренная анкета! Используйте кнопку 'Редактировать' для её изменения.")
        return -1
    
    logger.info("profile_new_start_cb invoked from user=%s", user.id)
    await q.message.reply_text("Напишите свою анкету (всё что угодно):")
    await q.message.reply_text(PROFILE_EXAMPLE)
    return NP_WAIT_TEXT


async def profile_edit_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start editing existing profile (only for users with one) - send to review"""
    q = update.callback_query
    await q.answer()
    
    user = update.effective_user
    if not user or not user.username:
        await q.message.reply_text(NO_USERNAME_ERROR)
        return -1
    
    # Check if user has an APPROVED profile
    profile = db.get_profile_by_username(user.username)
    if not profile or profile.get('status') != 'approved':
        await q.message.reply_text("У вас ещё нет одобренной анкеты. Создайте новую!")
        return -1
    
    context.user_data['edit_username'] = user.username
    current_text = profile.get('note', '')
    logger.info("profile_edit_start_cb invoked from user=%s", user.id)
    await q.message.reply_text(f"Редактируете свою анкету.\n\nТекущий текст:\n{current_text}\n\nОтправьте новый текст анкеты:")
    return EP_WAIT_TEXT


### NEW PROFILE flow (Conversation)

NP_WAIT_TEXT = 1
EP_WAIT_TEXT = 3


async def new_profile_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text(NO_USERNAME_ERROR)
        return -1

    text = update.message.text or ""
    logger.info("new_profile_receive: user=%s text=%s", user.id if user else None, (text or '')[:120])
    
    # Just save the raw text as note, no parsing required
    profile = {
        'username': user.username,
        'age': None,
        'name': None,
        'country': None,
        'city': None,
        'timezone': None,
        'tz_offset': None,
        'languages': None,
        'note': text,
        'added_by': user.username,
        'added_by_id': user.id,
        'added_at': iso_now(),
        'status': 'pending',  # NEW PROFILES REQUIRE REVIEW
    }
    context.user_data['new_profile_preview'] = profile
    await update.message.reply_text(short_profile_card(profile), reply_markup=new_profile_preview_kb())
    return -1


async def new_profile_receive_single(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function is no longer needed with simplified flow, but keep it to avoid breaking handlers
    return -1


async def try_auto_profile_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect free-form profile messages and auto-submit to review.

    This allows users to paste a profile in any chat and it will be treated as a new profile submission.
    """
    chat = update.effective_chat
    if not chat:
        return

    text = (update.message.text or '').strip()
    logger.info('try_auto_profile_submit: incoming message chat=%s user=%s text=%s', update.effective_chat and update.effective_chat.id, update.effective_user and update.effective_user.id, text[:120])
    if not text or len(text) < 10:
        return

    user = update.effective_user
    if not user or not user.username:
        return

    # Simple heuristic: if message is reasonably long (10+ chars), treat it as a profile
    profile = {
        'username': user.username,
        'age': None,
        'name': None,
        'country': None,
        'city': None,
        'timezone': None,
        'tz_offset': None,
        'languages': None,
        'note': text,
        'added_by': user.username,
        'added_by_id': user.id,
        'added_at': iso_now(),
    }
    context.user_data['new_profile_preview'] = profile
    logger.info('try_auto_profile_submit: prepared preview for user=%s username=%s', user and user.id, profile.get('username'))
    await update.message.reply_text(short_profile_card(profile), reply_markup=new_profile_preview_kb())
    return


async def new_profile_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    profile = context.user_data.get('new_profile_preview')
    if not profile:
        await q.message.reply_text("Нет данных для сохранения.")
        return
    
    # Validate profile text
    profile_text = profile.get('note', '')
    is_valid, error_msg = validate_profile_text(profile_text) if profile_text else (True, None)
    if not is_valid:
        await q.message.reply_text(f"❌ {error_msg}")
        return
    
    # Sanitize profile data
    profile = sanitize_profile_data(profile)
    
    # Check if username already exists with APPROVED status
    username = profile.get('username')
    existing_profile = db.get_profile_by_username(username)
    if existing_profile and existing_profile.get('status') == 'approved':
        await q.message.reply_text(f"У вас уже есть одобренная анкета @{username}. Используйте кнопку 'Редактировать' для её изменения.")
        context.user_data.pop('new_profile_preview', None)
        return
    
    # If profile exists but not approved, delete it first to allow recreation
    if existing_profile and existing_profile.get('status') != 'approved':
        db.delete_profile(username)
        profile_cache.delete(username)
        logger.info('new_profile_confirm_cb: deleted old non-approved profile @%s before creating new one', username)
    
    try:
        logger.info('new_profile_confirm_cb: user %s confirmed new profile @%s', q.from_user and q.from_user.id, username)
        pid = db.add_profile(profile)
        
        # Cache the new profile for quick access
        profile_with_id = dict(profile)
        profile_with_id['id'] = pid
        profile_cache.set(pid, profile_with_id)
        
        # Send to admins for review
        await q.message.reply_text(
            "✅ Анкета отправлена на проверку администраторам!\n\n"
            "После одобрения вы появитесь в списке пользователей."
        )
        
        # Notify admins about new profile for review
        card = short_profile_card(profile)
        notified_ids = set(config.ADMIN_IDS or [])
        if config.SUPER_ADMIN_ID:
            notified_ids.add(config.SUPER_ADMIN_ID)
        
        if notified_ids:
            text = f"📝 Новая анкета на проверку от @{username} ({q.from_user.id}):\n\n{card}"
            for aid in notified_ids:
                try:
                    await retry_telegram_request(
                        context.bot.send_message,
                        chat_id=aid,
                        text=text,
                        reply_markup=admin_review_kb(pid)
                    )
                except Exception:
                    logger.exception("Failed to notify admin %s about new profile", aid)
        
        context.user_data.pop('new_profile_preview', None)
    except Exception as e:
        logger.exception("Failed to save profile: %s", e)
        await q.message.reply_text("Ошибка при сохранении анкеты.")


async def new_profile_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    context.user_data.pop('new_profile_preview', None)
    await q.message.reply_text("Отмена")


async def edit_profile_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    context.user_data.pop('edit_profile_preview', None)
    context.user_data.pop('edit_username', None)
    await q.message.reply_text("Редактирование отменено")


### REPORT flow (Conversation)

RP_WAIT_REASON = 2


async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    # Check if user has a profile
    if user and user.username:
        profile = db.get_profile_by_username(user.username)
        if not profile:
            await update.message.reply_text("❌ Вы можете подать репорт только если у вас есть анкета.\n\nСначала создайте анкету в разделе 'Анкета'.")
            return -1
    
    logger.info('report_start invoked by user=%s chat=%s', update.effective_user and update.effective_user.id, update.effective_chat and update.effective_chat.id)
    await update.message.reply_text("Что хотите репортить?", reply_markup=report_categories_kb())
    return RP_WAIT_REASON


async def try_auto_report_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parse messages like 'репорт чат: причина' in one message and submit directly.

    If message contains a category and a reason, create the report immediately.
    If only category is found, ask the user for a reason (start the flow manually by prompting categories).
    """
    text = (update.message.text or '').strip()
    user = update.effective_user
    
    # Check if user has a profile
    if user and user.username:
        profile = db.get_profile_by_username(user.username)
        if not profile:
            await update.message.reply_text("❌ Вы можете подать репорт только если у вас есть анкета.\n\nСначала создайте анкету в разделе 'Анкета'.")
            return
    
    logger.info('try_auto_report_submit: incoming message chat=%s user=%s text=%s', update.effective_chat and update.effective_chat.id, update.effective_user and update.effective_user.id, text[:120])
    if not text:
        return

    # quick check — must contain 'репорт' or 'жалоб' keyword
    import re
    # accept various inflected forms: 'репорт', 'репорты', 'репортить', 'жалоб', 'жалобу', 'жалоба'
    if not re.search(r'(?i)\b(репорт\w*|жалоб\w*)', text):
        return

    # try to find category words
    cat_map = {
        'бот': 'bot',
        'bot': 'bot',
        'канал': 'channel',
        'channel': 'channel',
        'группа': 'chat',
        'чат': 'chat',
        'group': 'chat',
        'chat': 'chat',
    }
    m = re.search(r'(?i)\b(bot|бот|канал|channel|группа|чат|group|chat)\b', text)
    if not m:
        logger.debug('try_auto_report_submit: no category found in text, prompting categories')
        # no category found — show category selector to the user
        await report_start(update, context)
        return

    raw_cat = m.group(1).lower()
    cat = cat_map.get(raw_cat, 'chat')

    # try to capture reason after a separator ':' or '-' or after the category token
    reason = None
    # split after the category occurrence
    parts = re.split(re.escape(m.group(0)), text, maxsplit=1, flags=re.I)
    if len(parts) > 1:
        tail = parts[1].strip()
        # strip leading separators
        tail = re.sub(r'^[\s:—\-]+', '', tail)
        if tail:
            reason = tail

    # If we have no explicit reason, try to find after keywords like 'причина' or 'почему'
    if not reason:
        m2 = re.search(r'(?i)(?:причина[:\-]?\s*)(.+)$', text)
        if m2:
            reason = m2.group(1).strip()

    # If we still have no reason, prompt the user to input a reason via normal flow
    if not reason:
        # ask for reason — reuse the normal report_start flow to choose category first
        await update.message.reply_text("Я понял категорию: %s. Пожалуйста, укажите причину репорта (коротко):" % cat)
        # store category to user_data so next message is handled by report_reason_received
        context.user_data['report_category'] = cat
        return

    # build report and save it
    user = update.effective_user
    r = {
        'reporter_id': user.id if user else None,
        'reporter_username': user.username if user else None,
        'category': cat,
        'target_identifier': None,
        'reason': reason[:400],
        'attachments': None,
        'created_at': iso_now(),
    }
    rid = db.add_report(r)
    logger.info('try_auto_report_submit: added report id=%s for user=%s category=%s', rid, user and user.id, cat)
    stamp = str(int(__import__('time').time()))
    rid_text = f"R-{stamp}-{rid}"
    await update.message.reply_text(REPORT_ACCEPTED.format(rid=rid_text))

    # notify admins and super admin
    notified_ids = set(config.ADMIN_IDS or [])
    if config.SUPER_ADMIN_ID:
        notified_ids.add(config.SUPER_ADMIN_ID)
    if notified_ids:
        text2 = f"Новый репорт {rid_text}\nКатегория: {cat}\nОт: @{r.get('reporter_username')} ({r.get('reporter_id')})\nПричина: {reason}"
        for aid in notified_ids:
            try:
                await context.bot.send_message(chat_id=aid, text=text2)
            except Exception:
                logger.exception("Failed to notify admin %s", aid)


async def report_select_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    cat = q.data.split(':', 1)[1]
    if cat == 'cancel' or cat == 'menu':
        await q.message.reply_text(REPORT_CANCELLED)
        return -1
    context.user_data['report_category'] = cat
    await q.message.reply_text("Опишите причину репорта (коротко):")
    return RP_WAIT_REASON


async def report_reason_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info('report_reason_received: user=%s chat=%s text=%s', user and user.id, update.effective_chat and update.effective_chat.id, (update.message.text or '')[:120])
    cat = context.user_data.get('report_category')
    if not cat:
        await update.message.reply_text("Не выбрана категория — начните снова")
        return -1
    reason = update.message.text or ""
    r = {
        'reporter_id': user.id if user else None,
        'reporter_username': user.username if user else None,
        'category': cat,
        'target_identifier': None,
        'reason': reason[:400],
        'attachments': None,
        'created_at': iso_now(),
    }
    rid = db.add_report(r)
    stamp = str(int(__import__('time').time()))
    rid_text = f"R-{stamp}-{rid}"
    await update.message.reply_text(REPORT_ACCEPTED.format(rid=rid_text))
    # notify configured admins and the super-admin for visibility
    notified_ids = set(config.ADMIN_IDS or [])
    if config.SUPER_ADMIN_ID:
        notified_ids.add(config.SUPER_ADMIN_ID)

    if notified_ids:
        text = f"Новый репорт {rid_text}\nКатегория: {cat}\nОт: @{r.get('reporter_username')} ({r.get('reporter_id')})\nПричина: {reason}"
        for aid in notified_ids:
            try:
                await context.bot.send_message(chat_id=aid, text=text)
            except Exception:
                logger.exception("Failed to notify admin %s", aid)
    return -1


### Export CSV (admin only)

async def export_csv_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("Доступ запрещён: только админ может экспортировать CSV.")
        return
    profiles = db.get_all_profiles()
    import csv, io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'username', 'age', 'name', 'country', 'city', 'timezone', 'tz_offset', 'languages', 'note', 'added_by', 'added_at'])
    for p in profiles:
        writer.writerow([p.get('id'), p.get('username'), p.get('age'), p.get('name'), p.get('country'), p.get('city'), p.get('timezone'), p.get('tz_offset'), p.get('languages'), p.get('note'), p.get('added_by'), p.get('added_at')])
    output.seek(0)
    await update.message.reply_document(document=('profiles.csv', output.read().encode('utf-8')))


### Chat info

async def chat_info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat:
        title = chat.title or chat.first_name or ''
        t = f"Информация о чате:\nНазвание: {title}\nID: {chat.id}\nТип: {chat.type}"
    else:
        t = "Информация о чате: Добавьте бота в группу или используйте в личке."
    await update.message.reply_text(t)


### ADMIN PANEL (visible to all, accessible to single user only)

async def admin_panel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # button visible to all, but only SUPER admin or ADMIN_IDS can access
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await update.message.reply_text("Доступ к админ-панели ограничен.")
        return

    # prepare admin inline menu
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Посмотреть репорты", callback_data="admin:reports")],
            [InlineKeyboardButton(text="Новые анкеты (user-added)", callback_data="admin:new_profiles")],
            [InlineKeyboardButton(text="Управление анкетами", callback_data="admin:manage_profiles")],
            [InlineKeyboardButton(text="AFK заявки", callback_data="admin:afk_requests")],
            [InlineKeyboardButton(text="Заявки на админа", callback_data="admin:admin_applications")],
            [InlineKeyboardButton(text="Закрыть", callback_data="back:menu")],
        ]
    )
    await update.message.reply_text("Админ-панель — выберите действие:", reply_markup=kb)


async def admin_reports_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return

    reports = db.get_reports()
    if not reports:
        await q.message.reply_text("Репортов пока нет.")
        return
    
    # show last 10 reports summary with clear button
    lines = []
    for r in reports[:10]:
        lines.append(f"ID: {r['id']} | @{r.get('reporter_username') or 'unknown'} | {r.get('category')} | {r.get('created_at')}. Причина: {r.get('reason')[:80]}")
    text = f"Последние репорты (всего: {len(reports)}):\n" + "\n---\n".join(lines)
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🗑️ Очистить все репорты", callback_data="admin:clear_reports")],
        [InlineKeyboardButton(text="Назад", callback_data="back:menu")],
    ])
    await q.message.reply_text(text, reply_markup=kb)


async def admin_clear_reports(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all reports from database"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return
    
    ok = db.clear_reports()
    if ok:
        logger.info('admin_clear_reports: all reports cleared by admin %s', user.id)
        await q.message.reply_text("✅ Все репорты очищены.")
    else:
        await q.message.reply_text("Репортов не было для очистки.")


async def admin_new_profiles_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return

    # fetch pending user-added profiles
    added_user_profiles = db.get_profiles_by_status('pending')
    # filter out any seed items (just in case)
    added_user_profiles = [p for p in added_user_profiles if p.get('added_by') and p.get('added_by') != 'seed']
    if not added_user_profiles:
        await q.message.reply_text("Новых (пользовательских) анкет пока нет.")
        return
    # send each pending profile as a preview + review buttons
    for p in added_user_profiles[:20]:
        card = short_profile_card(p)
        try:
            await q.message.reply_text(card, reply_markup=admin_review_kb(p.get('id')))
        except Exception:
            logger.exception("Failed to send profile preview to admin for id %s", p.get('id'))


async def admin_manage_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin can view and manage profiles"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return
    
    # Get all approved profiles - always fresh from DB
    all_profiles = db.get_all_profiles(status='approved')
    if not all_profiles:
        await q.message.reply_text("Нет одобренных анкет.")
        return
    
    logger.info('admin_manage_profiles: loaded %d approved profiles', len(all_profiles))
    usernames = [p['username'] for p in all_profiles]
    await q.message.reply_text(f"Всего анкет: {len(all_profiles)}\n\nВыберите анкету для управления:", 
                               reply_markup=admin_manage_profiles_kb(usernames))


async def admin_back_to_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Go back to profiles list"""
    q = update.callback_query
    await q.answer()
    await admin_manage_profiles(update, context)


async def admin_profile_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show action menu for a profile (edit or delete)"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ ограничен.")
        return
    
    # Parse callback: admin:profile:USERNAME
    parts = q.data.split(':')
    if len(parts) < 3:
        await q.message.reply_text("Ошибка: неверная команда.")
        return
    username = parts[2]
    
    profile = db.get_profile_by_username(username)
    if not profile:
        await q.message.reply_text(f"Профиль @{username} не найден.")
        return
    
    # Show profile info and action buttons
    card = short_profile_card(profile)
    await q.message.reply_text(f"Профиль @{username}:\n\n{card}\n\nВыберите действие:",
                               reply_markup=admin_profile_action_kb(username))


async def admin_edit_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start editing profile"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ ограничен.")
        return
    
    # Parse callback: admin:edit:USERNAME
    parts = q.data.split(':')
    if len(parts) < 3:
        await q.message.reply_text("Ошибка: неверная команда.")
        return
    username = parts[2]
    
    profile = db.get_profile_by_username(username)
    if not profile:
        await q.message.reply_text(f"Профиль @{username} не найден.")
        return
    
    # Store profile info in context for editing
    context.user_data['admin_edit_username'] = username
    context.user_data['admin_edit_profile'] = dict(profile)
    
    # Show current profile info and ask what to edit
    card = short_profile_card(profile)
    edit_info = (
        f"📝 Редактирование профиля @{username}\n\n"
        f"Текущие данные:\n{card}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 СПОСОБ РЕДАКТИРОВАНИЯ:\n\n"
        f"Вы можете отправить новые данные в одном из форматов:\n\n"
        f"1️⃣ СТРУКТУРИРОВАННЫЙ ФОРМАТ (рекомендуется):\n"
        f"age:25\n"
        f"name:Иван Петров\n"
        f"country:Россия\n"
        f"city:Москва\n"
        f"timezone:Europe/Moscow\n"
        f"languages:Русский, Английский, Французский\n"
        f"note:Любой текст с любой информацией\n\n"
        f"2️⃣ ПРОИЗВОЛЬНЫЙ ТЕКСТ:\n"
        f"Просто напишите что угодно! Это будет сохранено в поле 'note':\n"
        f"\"Я люблю путешествовать и программирование. "
        f"Говорю на 3 языках. Живу в Москве, но часто путешествую.\"\n\n"
        f"3️⃣ СМЕШАННЫЙ ФОРМАТ:\n"
        f"age:30\n"
        f"note:Добавьте сюда всю остальную информацию о себе\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 СОВЕТЫ:\n"
        f"• Отправьте только те поля, которые хотите изменить\n"
        f"• Если поле не указано, оно не будет изменено\n"
        f"• Напишите что угодно в 'note' - это может быть описание, интересы, опыт\n"
        f"• Пустые строки игнорируются"
    )
    await q.message.reply_text(edit_info)


async def admin_receive_profile_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive edited profile data from admin - supports both structured and free text"""
    username = context.user_data.get('admin_edit_username')
    if not username:
        return
    
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await update.message.reply_text("Доступ ограничен.")
        return
    
    text = update.message.text or ''
    if not text or text.strip() == '':
        await update.message.reply_text("Ошибка: отправьте текст.")
        return
    
    try:
        changes = {}
        has_structured_format = False
        
        # Try to parse as structured format (key:value)
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if ':' in line:
                has_structured_format = True
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if not key or not value:
                    continue
                
                if key == 'age':
                    try:
                        changes['age'] = int(value)
                    except ValueError:
                        await update.message.reply_text(f"❌ Ошибка: возраст должен быть числом.\n\nПример: age:30")
                        return
                elif key == 'name':
                    changes['name'] = value
                elif key == 'country':
                    changes['country'] = value
                elif key == 'city':
                    changes['city'] = value
                elif key == 'timezone':
                    changes['timezone'] = value
                elif key == 'languages':
                    changes['languages'] = value
                elif key == 'note':
                    changes['note'] = value
        
        # If no structured format found, treat entire text as note (free text mode)
        if not has_structured_format or (not changes and text.strip()):
            changes['note'] = text.strip()
        
        if not changes:
            await update.message.reply_text("❌ Ошибка: не найдены изменения.")
            return
        
        # Update profile
        ok = db.update_profile(username, changes)
        if ok:
            # Update cache
            profile_cache.update(username, changes)
            
            changed_fields = ', '.join(changes.keys())
            await update.message.reply_text(
                f"✅ Профиль @{username} успешно обновлён!\n\n"
                f"Изменены поля: {changed_fields}"
            )
            logger.info('admin_receive_profile_edit: admin %s edited profile %s, fields: %s', user.id, username, changed_fields)
        else:
            await update.message.reply_text(f"❌ Ошибка при обновлении профиля.")
    except Exception as e:
        logger.exception("Error editing profile")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        context.user_data.pop('admin_edit_username', None)
        context.user_data.pop('admin_edit_profile', None)


async def admin_delete_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete profile from admin panel"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return
    
    # Parse callback: admin:delete:USERNAME
    parts = q.data.split(':')
    if len(parts) < 3:
        await q.message.reply_text("Ошибка: неверная команда.")
        return
    username = parts[2]
    
    profile = db.get_profile_by_username(username)
    if not profile:
        await q.message.reply_text(f"Профиль @{username} не найден.")
        return
    
    # Show confirmation
    await q.message.reply_text(f"Вы уверены, что хотите удалить анкету @{username}?", 
                               reply_markup=confirm_delete_kb(username))


### Hook for edited profile text (admin simple update)

async def admin_receive_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = context.user_data.get('edit_username')
    # only handle if edit session active and user is admin
    if not username:
        return
    if update.effective_user.id not in config.ADMIN_IDS:
        # ignore silently for non-admins
        return
    text = update.message.text or ''
    parsed = parse_profile_text(text)
    data = parsed['data']
    changes = {}
    for k in ('age', 'name', 'country', 'city', 'timezone', 'tz_offset', 'languages', 'note'):
        if k in data and data.get(k) is not None:
            changes[k] = data.get(k)
    ok = db.update_profile(username, changes)
    if ok:
        await update.message.reply_text('Профиль обновлён.')
    else:
        await update.message.reply_text('Ошибка обновления.')
    context.user_data.pop('edit_username', None)


async def admin_review_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text('Доступ ограничен.')
        return

    parts = q.data.split(':')
    # expected format: review:{id}:accept or review:{id}:reject
    if len(parts) < 3:
        await q.message.reply_text('Неверная команда.')
        return
    try:
        pid = int(parts[1])
    except Exception:
        await q.message.reply_text('Неправильный ID.')
        return
    action = parts[2]
    profile = db.get_profile_by_id(pid)
    if not profile:
        await q.message.reply_text('Анкета не найдена.')
        return

    # Check if profile has already been reviewed
    if profile.get('reviewed_by_id') is not None:
        await q.message.reply_text('❌ Эта анкета уже была проверена. Повторное решение невозможно.\n\nПользователь должен отправить новую анкету для повторной проверки.')
        return

    if action == 'accept':
        ok = db.update_profile_status_and_review(pid, 'approved', user.id)
        if ok:
            # Update cache
            profile_cache.update(pid, {'status': 'approved', 'reviewed_by_id': user.id})
            # Clear local cache lists
            _cache.pop('all_profiles', None)
            _cache.pop('all_approved_profiles', None)
            
            await q.message.reply_text(f'✅ Анкета @{profile.get("username")} принята.')
            # notify submitter if we know their user id
            try:
                aid = profile.get('added_by_id')
                if aid:
                    await retry_telegram_request(
                        context.bot.send_message,
                        chat_id=aid,
                        text=f'✅ Ваша анкета @{profile.get("username")} принята администратором! Теперь вы в списке.'
                    )
            except Exception:
                logger.exception('Failed to notify submitter about acceptance for %s', pid)
        else:
            await q.message.reply_text('Ошибка при принятии анкеты.')
    elif action == 'reject':
        username = profile.get('username')
        # COMPLETELY DELETE the profile when rejected - so user can create new one
        ok = db.delete_profile(username)
        if ok:
            # Clear from persistent cache
            profile_cache.delete(username)
            # Clear from local cache lists
            _cache.pop('all_profiles', None)
            _cache.pop('all_approved_profiles', None)
            
            await q.message.reply_text(f'❌ Анкета @{username} отклонена и удалена.')
            try:
                aid = profile.get('added_by_id')
                if aid:
                    await retry_telegram_request(
                        context.bot.send_message,
                        chat_id=aid,
                        text=f'❌ Ваша анкета @{username} отклонена администратором. Вы можете создать новую.'
                    )
            except Exception:
                logger.exception('Failed to notify submitter about rejection for %s', pid)
            logger.info('admin_review_cb: admin %s rejected and deleted profile @%s (id=%s)', user.id, username, pid)
        else:
            await q.message.reply_text('Ошибка при отклонении анкеты.')
    elif action == 'delete':
        username = profile.get('username')
        ok = db.delete_profile(username)
        if ok:
            # Clear from persistent cache by username
            profile_cache.delete(username)
            # Clear from local cache
            _cache.pop('all_profiles', None)
            _cache.pop('all_approved_profiles', None)
            
            await q.message.reply_text(f'Анкета @{username} удалена из списка.')
            logger.info('admin_review_cb: admin deleted profile @%s (id=%s)', username, pid)
        else:
            await q.message.reply_text(f'Ошибка при удалении анкеты @{username}.')
    else:
        await q.message.reply_text('Неизвестное действие.')


### AFK flow (Conversation)

AFK_WAIT_DAYS = 4
AFK_WAIT_REASON = 5


async def afk_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start AFK request flow"""
    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text("⚠️ Установите username в профиле Telegram.")
        return -1
    
    # Check if user has a profile
    profile = db.get_profile_by_username(user.username)
    if not profile:
        await update.message.reply_text("❌ Вы можете подать заявку на AFK только если у вас есть анкета.\n\nСначала создайте анкету в разделе 'Анкета'.")
        return -1
    
    logger.info('afk_start invoked by user=%s', user.id)
    await update.message.reply_text(AFK_INFO)
    await update.message.reply_text(AFK_PROMPT_DAYS, reply_markup=afk_reason_kb())
    return AFK_WAIT_DAYS


async def afk_receive_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive number of days for AFK"""
    user = update.effective_user
    text = update.message.text or ""
    
    try:
        days = int(text.strip())
        if days < 1 or days > 14:
            await update.message.reply_text("❌ Количество дней должно быть от 1 до 14.", reply_markup=afk_reason_kb())
            return AFK_WAIT_DAYS
        context.user_data['afk_days'] = days
        logger.info('afk_receive_days: user=%s days=%d', user.id if user else None, days)
        await update.message.reply_text(AFK_PROMPT_REASON, reply_markup=afk_reason_kb())
        return AFK_WAIT_REASON
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите число (1-14).", reply_markup=afk_reason_kb())
        return AFK_WAIT_DAYS


async def afk_receive_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive reason for AFK and submit to admin panel"""
    user = update.effective_user
    reason = (update.message.text or "").strip()
    days = context.user_data.get('afk_days', 1)
    
    if not reason:
        await update.message.reply_text("❌ Пожалуйста, укажите причину.", reply_markup=None)
        return AFK_WAIT_REASON
    
    if len(reason) > 500:
        reason = reason[:500]
    
    logger.info('afk_receive_reason: user=%s username=%s days=%d reason=%s', user.id if user else None, user.username if user else None, days, reason[:100])
    
    # Store in database (use reports with category 'afk')
    r = {
        'reporter_id': user.id if user else None,
        'reporter_username': user.username if user else None,
        'category': 'afk_request',
        'target_identifier': None,
        'reason': f"AFK на {days} дней. Причина: {reason}",
        'attachments': None,
        'created_at': iso_now(),
    }
    db.add_report(r)
    
    await update.message.reply_text(AFK_SUBMITTED, reply_markup=None)
    
    # Notify admins
    notified_ids = set(config.ADMIN_IDS or [])
    if config.SUPER_ADMIN_ID:
        notified_ids.add(config.SUPER_ADMIN_ID)
    
    if notified_ids:
        text = f"🌙 Новая AFK заявка от @{user.username} ({user.id})\n\n⏰ Срок: {days} дней\n\n📝 Причина:\n{reason}"
        for aid in notified_ids:
            try:
                await context.bot.send_message(chat_id=aid, text=text)
            except Exception:
                logger.exception("Failed to notify admin %s about AFK request", aid)
    
    context.user_data.pop('afk_days', None)
    return -1


async def admin_afk_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AFK requests from admin panel"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return
    
    # Get all AFK requests (stored as reports with category 'afk_request')
    reports = db.get_reports()
    afk_requests = [r for r in reports if r.get('category') == 'afk_request']
    
    if not afk_requests:
        await q.message.reply_text("AFK заявок пока нет.")
        return
    
    # Show last 10 AFK requests with details
    lines = []
    for r in afk_requests[-10:]:
        reason_text = r.get('reason', '')
        lines.append(f"📍 @{r.get('reporter_username')} ({r.get('reporter_id')})\n⏰ {r.get('created_at')}\n📝 {reason_text[:200]}")
    text = f"🌙 AFK заявки (всего: {len(afk_requests)}):\n\n" + "\n━━━\n".join(lines)
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:menu")],
    ])
    await q.message.reply_text(text, reply_markup=kb)


async def admin_admin_applications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin applications from admin panel"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or (user.id != config.SUPER_ADMIN_ID and user.id not in config.ADMIN_IDS):
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return
    
    # Get all admin applications (stored as reports with category 'admin_application')
    reports = db.get_reports()
    admin_apps = [r for r in reports if r.get('category') == 'admin_application']
    
    if not admin_apps:
        await q.message.reply_text("Заявок на админа пока нет.")
        return
    
    # Show last 10 admin applications with details
    lines = []
    for r in admin_apps[-10:]:
        app_text = r.get('reason', '')
        lines.append(f"👤 @{r.get('reporter_username')} ({r.get('reporter_id')})\n⏰ {r.get('created_at')}\n📝 {app_text[:200]}")
    text = f"📋 Заявки на админа (всего: {len(admin_apps)}):\n\n" + "\n━━━\n".join(lines)
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:menu")],
    ])
    await q.message.reply_text(text, reply_markup=kb)


### ADMIN APPLICATION flow (Conversation)

AA_WAIT_TEXT = 6


async def admin_app_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start admin application flow"""
    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text("⚠️ Установите username в профиле Telegram.")
        return -1
    
    # Check if user has a profile
    profile = db.get_profile_by_username(user.username)
    if not profile:
        await update.message.reply_text("❌ Вы можете подать заявку на админа только если у вас есть анкета.\n\nСначала создайте анкету в разделе 'Анкета'.")
        return -1
    
    logger.info('admin_app_start invoked by user=%s', user.id)
    await update.message.reply_text(ADMIN_APP_PROMPT, reply_markup=admin_app_reason_kb())
    return AA_WAIT_TEXT


async def admin_app_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive admin application text and submit to admin panel"""
    user = update.effective_user
    app_text = (update.message.text or "").strip()
    
    if not app_text:
        await update.message.reply_text("❌ Пожалуйста, опишите вашу заявку.", reply_markup=admin_app_reason_kb())
        return AA_WAIT_TEXT
    
    if len(app_text) > 1000:
        app_text = app_text[:1000]
    
    logger.info('admin_app_receive: user=%s username=%s text=%s', user.id if user else None, user.username if user else None, app_text[:100])
    
    # Store admin application to database (use reports table with category 'admin_application')
    r = {
        'reporter_id': user.id if user else None,
        'reporter_username': user.username if user else None,
        'category': 'admin_application',
        'target_identifier': None,
        'reason': app_text,
        'attachments': None,
        'created_at': iso_now(),
    }
    db.add_report(r)
    
    await update.message.reply_text(ADMIN_APP_SUBMITTED, reply_markup=None)
    
    # Notify admins
    notified_ids = set(config.ADMIN_IDS or [])
    if config.SUPER_ADMIN_ID:
        notified_ids.add(config.SUPER_ADMIN_ID)
    
    if notified_ids:
        text = f"📋 Новая заявка на админа от @{user.username} ({user.id})\n\n{app_text}"
        for aid in notified_ids:
            try:
                await context.bot.send_message(chat_id=aid, text=text)
            except Exception:
                logger.exception("Failed to notify admin %s about admin application", aid)
    
    return -1


### Cancel handlers for AFK and Admin Application

async def afk_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel AFK request via text message"""
    message = update.message
    if message:
        await message.reply_text("❌ Заявка на AFK отменена.")
    context.user_data.pop('afk_days', None)
    return -1


async def afk_cancel_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel AFK request via inline button"""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("❌ Заявка на AFK отменена.")
    context.user_data.pop('afk_days', None)
    return -1


async def admin_app_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel admin application via text message"""
    message = update.message
    if message:
        await message.reply_text("❌ Заявка на админа отменена.")
    return -1


async def admin_app_cancel_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel admin application via inline button"""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("❌ Заявка на админа отменена.")
    return -1
