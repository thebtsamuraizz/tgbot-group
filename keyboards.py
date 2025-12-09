from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Iterable


def main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        ["Информация о пользователях"],
        ["Анкета"],
        ["Репорт"],
        ["AFK"],
        ["Заявка на админа"],
        ["Информация о чате"],
        ["Админы"],
        ["Админ панель"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def users_list_kb(usernames: Iterable[str]) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"@{u}", callback_data=f"view:{u}")] for u in usernames]
    # add bottom row: Add new and Back
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
        [InlineKeyboardButton(text="Отмена", callback_data="back:menu")],
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
    buttons = [[InlineKeyboardButton(text=f"@{u}", callback_data=f"admin:profile:{u}")] for u in usernames]
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="back:menu")])
    return InlineKeyboardMarkup(buttons)


def admin_profile_action_kb(username: str) -> InlineKeyboardMarkup:
    """Action buttons for profile management"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:edit:{username}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin:delete:{username}")],
        [InlineKeyboardButton(text="Назад", callback_data="back:profiles")],
    ])


def afk_reason_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for AFK request reason with cancel button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="❌ Отмена", callback_data="afk:cancel")],
    ])


def admin_app_reason_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for admin application with cancel button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_app:cancel")],
    ])
