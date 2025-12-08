import logging
import config
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters
import handlers
import db


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def main():
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error('TELEGRAM_BOT_TOKEN is not set. Please set env var or .env file.')
        return

    logger.info('Starting bot (python-telegram-bot)')
    app = ApplicationBuilder().token(token).build()

    db.init_db()

    # ========== CONVERSATION HANDLERS (HIGH PRIORITY) ==========
    # These MUST come before other TEXT handlers so they can manage their internal states.
    
    # New profile conversation
    new_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.profile_new_start_cb, pattern=r'^profile:new_start$')],
        states={
            handlers.NP_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.new_profile_receive), MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.new_profile_receive_single)],
        },
        fallbacks=[],
        per_message=True,
    )
    app.add_handler(new_conv)

    # Report conversation (handles /report flow: category selection → reason input)
    report_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^Репорт$'), handlers.report_start),
            MessageHandler(filters.Regex(r'(?i)\b(репорт\w*|жалоб\w*)'), handlers.report_start),
        ],
        states={
            handlers.RP_WAIT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.report_reason_received)],
        },
        fallbacks=[],
    )
    app.add_handler(report_conv)

    # Edit profile conversation
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.profile_edit_start_cb, pattern=r'^profile:edit_start$')],
        states={
            handlers.EP_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.edit_profile_receive)],
        },
        fallbacks=[],
        per_message=True,
    )
    app.add_handler(edit_conv)

    # ========== COMMAND HANDLERS ==========
    # Command handlers
    app.add_handler(CommandHandler('start', handlers.start))
    app.add_handler(CommandHandler('export_csv', handlers.export_csv_cmd))

    # ========== MENU BUTTON HANDLERS (fixed strings only) ==========
    # Menu messages
    app.add_handler(MessageHandler(filters.Regex('^Информация о пользователях$'), handlers.users_list_entry))
    app.add_handler(MessageHandler(filters.Regex('^Информация о чате$'), handlers.chat_info_cmd))
    app.add_handler(MessageHandler(filters.Regex('^Админы$'), handlers.admins_list_entry))
    app.add_handler(MessageHandler(filters.Regex('^Анкета$'), handlers.profile_menu_entry))
    app.add_handler(MessageHandler(filters.Regex('^Админ панель$'), handlers.admin_panel_entry))

    # ========== CALLBACK QUERY HANDLERS ==========
    # Callback handlers
    app.add_handler(CallbackQueryHandler(handlers.view_profile_cb, pattern=r'^view:'))
    app.add_handler(CallbackQueryHandler(handlers.back_to_users, pattern=r'^back:users$|^back:menu$|^back:add_new$'))
    app.add_handler(CallbackQueryHandler(handlers.delete_profile_cb, pattern=r'^delete:'))
    app.add_handler(CallbackQueryHandler(handlers.delete_profile_confirm_cb, pattern=r'^delete_confirm:'))
    # Profile menu callbacks
    app.add_handler(CallbackQueryHandler(handlers.profile_new_start_cb, pattern=r'^profile:new_start$'))
    app.add_handler(CallbackQueryHandler(handlers.profile_edit_start_cb, pattern=r'^profile:edit_start$'))
    # Admin panel callbacks
    app.add_handler(CallbackQueryHandler(handlers.admin_reports_view, pattern=r'^admin:reports$'))
    app.add_handler(CallbackQueryHandler(handlers.admin_new_profiles_view, pattern=r'^admin:new_profiles$'))
    app.add_handler(CallbackQueryHandler(handlers.admin_manage_profiles, pattern=r'^admin:manage_profiles$'))
    app.add_handler(CallbackQueryHandler(handlers.admin_delete_profile, pattern=r'^admin:delete:'))
    # review callbacks (accept/reject)
    app.add_handler(CallbackQueryHandler(handlers.admin_review_cb, pattern=r'^review:'))
    # callback for choosing category in report flow
    app.add_handler(CallbackQueryHandler(handlers.report_select_cb, pattern=r'^report:'))
    # new profile inline callbacks
    app.add_handler(CallbackQueryHandler(handlers.new_profile_confirm_cb, pattern=r'^new:confirm$'))
    app.add_handler(CallbackQueryHandler(handlers.new_profile_cancel_cb, pattern=r'^new:cancel$'))
    # edit profile inline callbacks
    app.add_handler(CallbackQueryHandler(handlers.edit_profile_confirm_cb, pattern=r'^edit:confirm$'))
    app.add_handler(CallbackQueryHandler(handlers.edit_profile_cancel_cb, pattern=r'^edit:cancel$'))

    # ========== GLOBAL TEXT HANDLERS (LOW PRIORITY) ==========
    # These are fallback handlers that process any remaining TEXT messages.

    # Try to auto-process freeform profile submissions (private chat) before generic admin edit hook
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.try_auto_profile_submit))

    # admin editing hook
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_receive_edit))

    logger.info('Bot ready, starting polling')
    app.run_polling()


if __name__ == '__main__':
    main()
