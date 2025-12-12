from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Iterable


def main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        ["Информация о пользователях"],
        ["Анкета"],
        ["Репорт"],
        ["AFK"],
        ["Заявка на админа"],
        ["Правила", "Информация о чате"],
        ["Админы"],
        ["Админ панель"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def users_list_kb(usernames: Iterable[str]) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"@{u}", callback_data=f"view:{u}")] for u in usernames]
    buttons.append([
        InlineKeyboardButton(text="Добавить новую", callback_data="back:add_new"),
        InlineKeyboardButton(text="Назад", callback_data="back:menu"),
    ])
    return InlineKeyboardMarkup(buttons)


def profile_actions_kb(username: str, is_admin: bool = False, user_id: int = None, profile_owner_id: int = None) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="Назад", callback_data="back:users")]]
    
    can_edit = is_admin or (user_id and profile_owner_id and user_id == profile_owner_id)
    if can_edit:
        buttons[0].append(InlineKeyboardButton(text="Редактировать", callback_data=f"edit:{username}"))
    
    if is_admin:
        buttons[0].append(InlineKeyboardButton(text="Удалить", callback_data=f"delete:{username}"))
    return InlineKeyboardMarkup(buttons)


def confirm_delete_kb(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="Подтвердить удаление", callback_data=f"delete_confirm:{username}")],
        [InlineKeyboardButton(text="Отмена", callback_data="back:users")],
    ])


def report_categories_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="TG-бот", callback_data="report:bot")],
        [InlineKeyboardButton(text="TG-канал/группа", callback_data="report:channel")],
        [InlineKeyboardButton(text="Чат", callback_data="report:chat")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="report:cancel")],
    ])


def new_profile_preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="Подтвердить", callback_data="new:confirm")],
        [InlineKeyboardButton(text="Редактировать", callback_data="new:edit")],
        [InlineKeyboardButton(text="Отмена", callback_data="new:cancel")],
    ])


def profile_menu_kb(has_profile: bool) -> InlineKeyboardMarkup:
    """Menu to create new profile or edit existing one"""
    if has_profile:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(text="Редактировать", callback_data="profile:edit_start")],
            [InlineKeyboardButton(text="Назад", callback_data="back:menu")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(text="Новая анкета", callback_data="profile:new_start")],
            [InlineKeyboardButton(text="Назад", callback_data="back:menu")],
        ])


def edit_profile_preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="Подтвердить", callback_data="edit:confirm")],
        [InlineKeyboardButton(text="Отмена", callback_data="edit:cancel")],
    ])


def admin_review_kb(profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="Принять", callback_data=f"review:{profile_id}:accept")],
        [InlineKeyboardButton(text="Отклонить", callback_data=f"review:{profile_id}:reject")],
    ])


def admin_manage_profiles_kb(usernames: Iterable[str]) -> InlineKeyboardMarkup:
    """List of profiles for admin to manage"""
    # usernames here are only the page slice
    buttons = [[InlineKeyboardButton(text=f"@{u}", callback_data=f"admin:profile:{u}")] for u in usernames]
    # default back to admin panel
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="back:menu")])
    return InlineKeyboardMarkup(buttons)


def admin_manage_profiles_kb_paged(usernames: Iterable[str], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Paged list of profiles with navigation buttons"""
    buttons = [[InlineKeyboardButton(text=f"@{u}", callback_data=f"admin:profile:{u}")] for u in usernames]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin:manage_profiles:page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="admin:manage_profiles:page:info"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin:manage_profiles:page:{page+1}"))
    buttons.append(nav)
    # Back to admin panel
    buttons.append([InlineKeyboardButton(text="Закрыть", callback_data="back:menu")])
    return InlineKeyboardMarkup(buttons)


def admin_profile_action_kb(username: str) -> InlineKeyboardMarkup:
    """Action buttons for profile management"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:edit:{username}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin:delete:{username}")],
        [InlineKeyboardButton(text="Назад", callback_data="back:manage_profiles")],
    ])


def afk_days_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for selecting AFK days"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="1 день", callback_data="afk:days:1"),
         InlineKeyboardButton(text="3 дня", callback_data="afk:days:3")],
        [InlineKeyboardButton(text="7 дней", callback_data="afk:days:7"),
         InlineKeyboardButton(text="14 дней", callback_data="afk:days:14")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="afk:cancel")],
    ])


def afk_reason_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for AFK reason input - only cancel button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="❌ Отмена", callback_data="afk:cancel")],
    ])


def admin_app_reason_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for admin application with cancel button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_app:cancel")],
    ])


def admin_add_profile_cancel_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for admin adding profile with cancel button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_add_profile:cancel")],
    ])
