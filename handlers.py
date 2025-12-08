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
from keyboards import main_menu, users_list_kb, profile_actions_kb, confirm_delete_kb, report_categories_kb, new_profile_preview_kb, edit_profile_preview_kb, profile_menu_kb, admin_review_kb, admin_manage_profiles_kb
from templates.messages import *
import db
import utils
import config
from utils import iso_now, parse_profile_text, short_profile_card
from typing import Dict, Any

logger = logging.getLogger(__name__)


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
        await q.message.reply_text(f"Пользователь @{username} удалён.")
    else:
        await q.message.reply_text(f"Не удалось удалить @{username} — возможно пользователь отсутствует.")


### PROFILE MENU (check if user has profile)

async def profile_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show menu: Create new or Edit existing profile"""
    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text(NO_USERNAME_ERROR)
        return
    
    # Check if user already has a profile
    profile = db.get_profile_by_username(user.username)
    has_profile = profile is not None
    
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
    
    # Check if user already has a profile
    profile = db.get_profile_by_username(user.username)
    if profile:
        await q.message.reply_text("У вас уже есть анкета! Используйте кнопку 'Редактировать' для её изменения.")
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
    
    # Check if user has a profile
    profile = db.get_profile_by_username(user.username)
    if not profile:
        await q.message.reply_text("У вас ещё нет анкеты. Создайте новую!")
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
        'status': 'approved',  # Direct creation without review
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
    
    # Check if username already exists
    username = profile.get('username')
    if username and db.get_profile_by_username(username):
        await q.message.reply_text(f"Пользователь @{username} уже существует. Пожалуйста, используйте другой username.")
        context.user_data.pop('new_profile_preview', None)
        return
    
    try:
        logger.info('new_profile_confirm_cb: user %s confirmed new profile', q.from_user and q.from_user.id)
        pid = db.add_profile(profile)
        # Directly save profile without review
        await q.message.reply_text("✅ Анкета успешно создана!")
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
    logger.info('report_start invoked by user=%s chat=%s', update.effective_user and update.effective_user.id, update.effective_chat and update.effective_chat.id)
    await update.message.reply_text("Что хотите репортить?", reply_markup=report_categories_kb())
    return RP_WAIT_REASON


async def try_auto_report_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parse messages like 'репорт чат: причина' in one message and submit directly.

    If message contains a category and a reason, create the report immediately.
    If only category is found, ask the user for a reason (start the flow manually by prompting categories).
    """
    text = (update.message.text or '').strip()
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
    # button visible to all, but only SUPER admin can access
    if not user or user.id != config.SUPER_ADMIN_ID:
        await update.message.reply_text("Доступ к админ-панели ограничен.")
        return

    # prepare admin inline menu
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Посмотреть репорты", callback_data="admin:reports")],
            [InlineKeyboardButton(text="Новые анкеты (user-added)", callback_data="admin:new_profiles")],
            [InlineKeyboardButton(text="Управление анкетами", callback_data="admin:manage_profiles")],
            [InlineKeyboardButton(text="Закрыть", callback_data="back:menu")],
        ]
    )
    await update.message.reply_text("Админ-панель — выберите действие:", reply_markup=kb)


async def admin_reports_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or user.id != config.SUPER_ADMIN_ID:
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return

    reports = db.get_reports()
    if not reports:
        await q.message.reply_text("Репортов пока нет.")
        return
    # show last 10 reports summary
    lines = []
    for r in reports[:10]:
        lines.append(f"ID: {r['id']} | @{r.get('reporter_username') or 'unknown'} | {r.get('category')} | {r.get('created_at')}. Причина: {r.get('reason')[:80]}")
    text = "Последние репорты:\n" + "\n---\n".join(lines)
    await q.message.reply_text(text)


async def admin_new_profiles_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or user.id != config.SUPER_ADMIN_ID:
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
    """Admin can delete any profile from this view"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or user.id != config.SUPER_ADMIN_ID:
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return
    
    # Get all approved profiles
    all_profiles = db.get_all_profiles(status='approved')
    if not all_profiles:
        await q.message.reply_text("Нет одобренных анкет.")
        return
    
    usernames = [p['username'] for p in all_profiles]
    await q.message.reply_text(f"Всего анкет: {len(all_profiles)}\n\nВыберите анкету для удаления:", 
                               reply_markup=admin_manage_profiles_kb(usernames))


async def admin_delete_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete profile from admin panel"""
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if not user or user.id != config.SUPER_ADMIN_ID:
        await q.message.reply_text("Доступ к админ-панели ограничен.")
        return
    
    username = q.data.split(':', 1)[1]
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
    if not user or user.id != config.SUPER_ADMIN_ID:
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

    if action == 'accept':
        ok = db.update_profile_status_by_id(pid, 'approved')
        if ok:
            await q.message.reply_text(f'Анкета #{pid} принята.')
            # notify submitter if we know their user id
            try:
                aid = profile.get('added_by_id')
                if aid:
                    await context.bot.send_message(chat_id=aid, text=f'Ваша анкета @{profile.get("username")} принята администратором.')
            except Exception:
                logger.exception('Failed to notify submitter about acceptance for %s', pid)
        else:
            await q.message.reply_text('Ошибка при принятии анкеты.')
    elif action == 'reject':
        ok = db.update_profile_status_by_id(pid, 'rejected')
        if ok:
            await q.message.reply_text(f'Анкета #{pid} отклонена.')
            try:
                aid = profile.get('added_by_id')
                if aid:
                    await context.bot.send_message(chat_id=aid, text=f'Ваша анкета @{profile.get("username")} отклонена администратором.')
            except Exception:
                logger.exception('Failed to notify submitter about rejection for %s', pid)
        else:
            await q.message.reply_text('Ошибка при отклонении анкеты.')
    elif action == 'delete':
        username = profile.get('username')
        ok = db.delete_profile(username)
        if ok:
            await q.message.reply_text(f'Анкета @{username} удалена из списка.')
            logger.info('admin_review_cb: admin deleted profile @%s (id=%s)', username, pid)
        else:
            await q.message.reply_text(f'Ошибка при удалении анкеты @{username}.')
    else:
        await q.message.reply_text('Неизвестное действие.')
