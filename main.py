import logging
import config
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, Application, ContextTypes
from telegram.error import TelegramError
import handlers
import db
from cache_manager import profile_cache
from rate_limiter import retry_telegram_request
import sys


# Configure logging with both file and console output
logging.basicConfig(
    level=logging.DEBUG,  # Capture all levels
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        # Console output - only INFO and above in production
        logging.StreamHandler(sys.stdout),
        # File output - all levels
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

# Set appropriate levels for specific loggers
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, config.LOG_LEVEL))

# Reduce noise from telegram library
logging.getLogger('telegram.ext._application').setLevel(logging.WARNING)
logging.getLogger('telegram.ext._dispatcher').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)


async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for the bot"""
    logger.error(f'Error: {context.error}', exc_info=context.error)
    
    # Notify user about error
    if update and update.effective_chat:
        try:
            error_msg = '❌ Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже или обратитесь к администратору.'
            await retry_telegram_request(
                context.bot.send_message,
                chat_id=update.effective_chat.id,
                text=error_msg
            )
        except Exception as e:
            logger.error(f'Failed to send error message: {e}')
    
    # Notify super admin about critical errors
    if config.SUPER_ADMIN_ID and isinstance(context.error, (TelegramError, Exception)):
        try:
            error_msg = f'🚨 Bot Error:\n\n{type(context.error).__name__}: {context.error}'
            await retry_telegram_request(
                context.bot.send_message,
                chat_id=config.SUPER_ADMIN_ID,
                text=error_msg[:4000]  # Telegram message limit
            )
        except Exception as e:
            logger.error(f'Failed to notify admin about error: {e}')


def main():
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error('TELEGRAM_BOT_TOKEN is not set. Please set env var or .env file.')
        return

    # Print banner
    print("\n" + "="*70)
    print("🤖 TELEGRAM BOT STARTING UP")
    print("="*70)
    
    logger.info(f'🚀 Starting bot in {config.BOT_ENV.value} environment')
    logger.info(f'📊 Log level: {config.LOG_LEVEL}')
    logger.info('📦 Loading cached profiles from disk...')
    
    try:
        # Оптимизация для одновременной работы с несколькими пользователями
        app = (
            ApplicationBuilder()
            .token(token)
            .read_timeout(20)
            .write_timeout(20)
            .connect_timeout(15)
            .build()
        )

        # Add global error handler
        app.add_error_handler(handle_error)

        db.init_db()
        
        logger.info(f'✅ Database initialized')
        logger.info(f'💾 Cached profiles loaded: {len(profile_cache.cache)} profiles')
        logger.info(f'👥 Admin IDs: {config.ADMIN_IDS}')
        logger.info(f'👑 Super admin ID: {config.SUPER_ADMIN_ID}')

        # ========== CONVERSATION HANDLERS (HIGH PRIORITY) ==========
        # These MUST come before other TEXT handlers so they can manage their internal states.
        
        # New profile conversation
        new_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(handlers.profile_new_start_cb, pattern=r'^profile:new_start$')],
            states={
                handlers.NP_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.new_profile_receive), MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.new_profile_receive_single)],
            },
            fallbacks=[],
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

        # AFK conversation (handles AFK request flow: reason + days)
        afk_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^AFK$'), handlers.afk_start)],
            states={
                handlers.AFK_WAIT_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.afk_receive_days)],
                handlers.AFK_WAIT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.afk_receive_reason)],
            },
            fallbacks=[
                MessageHandler(filters.Regex('^Отмена$|^отмена$|^Cancel$|^cancel$'), handlers.afk_cancel),
                CallbackQueryHandler(handlers.afk_cancel_inline, pattern=r'^afk:cancel$'),
            ],
        )
        app.add_handler(afk_conv)

        # Admin application conversation (handles admin application flow)
        admin_app_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^Заявка на админа$'), handlers.admin_app_start)],
            states={
                handlers.AA_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_app_receive)],
            },
            fallbacks=[
                MessageHandler(filters.Regex('^Отмена$|^отмена$|^Cancel$|^cancel$'), handlers.admin_app_cancel),
                CallbackQueryHandler(handlers.admin_app_cancel_inline, pattern=r'^admin_app:cancel$'),
            ],
        )
        app.add_handler(admin_app_conv)

        # Edit profile conversation
        edit_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(handlers.profile_edit_start_cb, pattern=r'^profile:edit_start$')],
            states={
                handlers.EP_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.edit_profile_receive)],
            },
            fallbacks=[],
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
        app.add_handler(MessageHandler(filters.Regex('^AFK$'), handlers.afk_start))
        app.add_handler(MessageHandler(filters.Regex('^Заявка на админа$'), handlers.admin_app_start))

        # ========== CALLBACK QUERY HANDLERS ==========
        # Callback handlers
        app.add_handler(CallbackQueryHandler(handlers.view_profile_cb, pattern=r'^view:'))
        app.add_handler(CallbackQueryHandler(handlers.back_to_users, pattern=r'^back:users$|^back:menu$|^back:add_new$|^back:profiles$'))
        app.add_handler(CallbackQueryHandler(handlers.delete_profile_cb, pattern=r'^delete:'))
        app.add_handler(CallbackQueryHandler(handlers.delete_profile_confirm_cb, pattern=r'^delete_confirm:'))
        # Profile menu callbacks
        app.add_handler(CallbackQueryHandler(handlers.profile_new_start_cb, pattern=r'^profile:new_start$'))
        app.add_handler(CallbackQueryHandler(handlers.profile_edit_start_cb, pattern=r'^profile:edit_start$'))
        # Admin panel callbacks
        app.add_handler(CallbackQueryHandler(handlers.admin_reports_view, pattern=r'^admin:reports$'))
        app.add_handler(CallbackQueryHandler(handlers.admin_clear_reports, pattern=r'^admin:clear_reports$'))
        app.add_handler(CallbackQueryHandler(handlers.admin_new_profiles_view, pattern=r'^admin:new_profiles$'))
        app.add_handler(CallbackQueryHandler(handlers.admin_manage_profiles, pattern=r'^admin:manage_profiles$'))
        app.add_handler(CallbackQueryHandler(handlers.admin_profile_action, pattern=r'^admin:profile:'))
        app.add_handler(CallbackQueryHandler(handlers.admin_edit_profile_start, pattern=r'^admin:edit:'))
        app.add_handler(CallbackQueryHandler(handlers.admin_delete_profile, pattern=r'^admin:delete:'))
        app.add_handler(CallbackQueryHandler(handlers.admin_afk_requests, pattern=r'^admin:afk_requests$'))
        app.add_handler(CallbackQueryHandler(handlers.admin_admin_applications, pattern=r'^admin:admin_applications$'))
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

        # admin profile editing hook
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_receive_profile_edit))

        # admin editing hook
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_receive_edit))

        logger.info('Bot ready, starting polling with optimizations')
        print("\n" + "="*70)
        print("✅ BOT CONNECTED AND RUNNING")
        print("="*70)
        print("📢 Press Ctrl+C to stop the bot")
        print("📊 Logs saved to: bot.log")
        print("="*70 + "\n")
        
        app.run_polling(allowed_updates=['message', 'callback_query', 'edited_message'])
        
    except KeyboardInterrupt:
        print("\n" + "="*70)
        print("🛑 BOT STOPPED BY USER")
        print("="*70)
        logger.info('Bot interrupted by user')
    except Exception as e:
        print("\n" + "="*70)
        print("❌ BOT ERROR")
        print("="*70)
        logger.error(f'Failed to start bot: {e}', exc_info=True)


if __name__ == '__main__':
    main()
