import logging
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['task_management_bot']
tasks_collection = db['tasks']

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

TASK_TITLE, TASK_DESCRIPTION = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! you can create a task now by entering tast title first. Or you can simply skip it,"
        "or /skip it and /cancel again.",

    )

    return TASK_TITLE


async def task_title(update, context):
    context.user_data['title'] = update.message.text
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Please enter the task description:",
    )

    return TASK_DESCRIPTION


async def skip_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("User %s did not send a title.", user.first_name)
    await update.message.reply_text(
        "Enter task title, or send /skip."
    )

    return TASK_DESCRIPTION


async def task_description(update, context):
    context.user_data['description'] = update.message.text

    task = {
        'title': context.user_data['title'],
        'description': context.user_data['description']
    }
    tasks_collection.insert_one(task)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Okay, Your task is saved")
    print('good for you!')
    return ConversationHandler.END


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skips the photo and asks for a location."""
    user = update.message.from_user
    logger.info("User %s did not send a description.", user.first_name)
    await update.message.reply_text(
        "Enter task description, or send /skip."
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day."
    )

    return ConversationHandler.END


def main() -> None:
    """Run the bot."""

    application = Application.builder().token(
        "TOKEN").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TASK_TITLE: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT, task_title)],
            TASK_DESCRIPTION: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT, task_description)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
