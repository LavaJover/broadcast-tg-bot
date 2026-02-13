import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()  # до импорта config, чтобы ADMIN_USER_IDS подхватился из .env

from telegram import Chat, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import OWNER_USER_IDS
from database import (
    add_admin,
    add_chat,
    get_all_chat_ids,
    init_db,
    is_admin,
    is_owner,
    list_admin_ids,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("Не задан токен бота. Установите переменную окружения BOT_TOKEN или добавьте её в .env")


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start в личке с ботом. Ответ только для админов."""
    user = update.effective_user
    if user is None or update.message is None:
        return
    if not is_admin(user.id):
        return
    await update.message.reply_text(
        "Привет! Я бот для рассылки сообщений по беседам.\n\n"
        "1) Добавьте меня в нужные чаты/беседы.\n"
        "2) Убедитесь, что я вижу сообщения (разрешите доступ к сообщениям в настройках чата).\n"
        "3) Пишите мне в личку текст — я разошлю его во все сохранённые беседы.\n\n"
        "Владелец: /add_admin <id> — выдать право рассылки, /list_admins — список админов."
    )


def _register_chat(chat: Chat) -> None:
    """Сохраняет ID беседы, если это group/supergroup."""
    if chat.type in ("group", "supergroup"):
        title = chat.title or str(chat.id)
        add_chat(chat.id, title, chat.type)
        logger.info("Registered chat %s (%s)", chat.id, title)


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Любое сообщение в беседе регистрирует эту беседу в БД."""
    chat = update.effective_chat
    if chat is None:
        return
    _register_chat(chat)
    # Ничего не отвечаем, просто запоминаем беседу


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Личный текстовый запрос от администратора:
    бот разошлёт это сообщение во все сохранённые беседы.
    """
    user = update.effective_user
    chat = update.effective_chat

    if user is None or chat is None or update.message is None:
        return

    # Разрешаем рассылку только из личного чата
    if chat.type != "private":
        return

    # Рассылку могут делать только владельцы и выданные админы. Остальным — без ответа.
    if not is_admin(user.id):
        return

    text = update.message.text
    if not text:
        await update.message.reply_text("Отправьте текстовое сообщение, которое нужно разослать.")
        return

    chat_ids = get_all_chat_ids()
    if not chat_ids:
        await update.message.reply_text("Нет сохранённых бесед для рассылки. "
                                        "Добавьте бота в беседы и напишите там любое сообщение.")
        return

    sent = 0
    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось отправить сообщение в чат %s: %s", chat_id, exc)

    await update.message.reply_text(f"Сообщение отправлено в {sent} бесед(ы).")


async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда для владельца бота: выдача прав на рассылку.

    Использование (в личке с ботом):
    /add_admin <telegram_id>
    """
    user = update.effective_user
    chat = update.effective_chat

    if user is None or chat is None or update.message is None:
        return

    if chat.type != "private":
        return

    if not is_owner(user.id):
        return

    if not context.args:
        await update.message.reply_text("Использование: /add_admin <telegram_id>\n"
                                        "ID можно узнать, например, через @userinfobot.")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Пример: /add_admin 123456789")
        return

    add_admin(target_id, is_owner=False)
    await update.message.reply_text(f"Пользователь с ID {target_id} теперь может делать рассылку.")


async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список ID всех админов (для владельца)."""
    user = update.effective_user
    chat = update.effective_chat

    if user is None or chat is None or update.message is None:
        return

    if chat.type != "private":
        return

    if not is_owner(user.id):
        return

    ids = list_admin_ids()
    if not ids:
        await update.message.reply_text("Администраторов рассылки пока нет.")
        return

    text = "ID администраторов рассылки:\n" + "\n".join(str(i) for i in ids)
    await update.message.reply_text(text)


def main() -> None:
    init_db()
    # Владельцы из конфига — главные админы, могут выдавать права через /add_admin
    for uid in OWNER_USER_IDS:
        add_admin(uid, is_owner=True)

    # Для Python 3.14 явно создаём и устанавливаем event loop,
    # чтобы python-telegram-bot корректно работал.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = Application.builder().token(BOT_TOKEN).build()

    # Команда /start в личке
    application.add_handler(CommandHandler("start", start, filters.ChatType.PRIVATE))

    # Команды управления правами (только в личке)
    application.add_handler(CommandHandler("add_admin", add_admin_command, filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("list_admins", list_admins_command, filters.ChatType.PRIVATE))

    # Любые сообщения в группах/супергруппах — регистрируем беседу
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.ALL,
            handle_group_message,
        )
    )

    # Любые текстовые сообщения без команды в личке — попытка рассылки от администратора
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            admin_broadcast,
        )
    )

    logger.info("Бот запущен. Ожидание сообщений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

