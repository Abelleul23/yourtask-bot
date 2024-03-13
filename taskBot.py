import logging
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    Updater,
    CallbackContext,
)
from pymongo import MongoClient
from datetime import datetime, time, timezone, timedelta
import asyncio
import queue
import datetime as dt

import motor.motor_asyncio


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

TASK_TITLE, TASK_DESCRIPTION, SET_DUE_DATE, SET_PRIORITY = range(4)


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

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Okay, set due date")
    return SET_DUE_DATE


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("User %s did not send a description.", user.first_name)
    await update.message.reply_text(
        "Enter task description, or send /skip."
    )

    return SET_DUE_DATE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day."
    )

    return ConversationHandler.END


async def save_task(context):
    due_date = datetime.combine(context.user_data['due_date'], time())
    task = {
        'title': context.user_data['title'],
        'description': context.user_data['description'],
        'due_date': due_date,
        'chat_id': context._chat_id,
    }
    tasks_collection.insert_one(task)


async def set_due_date(update, context):
    if update.message.text:
        due_date = datetime.strptime(
            update.message.text, '%Y-%m-%d').date()
        context.user_data['due_date'] = due_date

        # Save the task to the database
        

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Task due date set to {due_date}. Now chose the task priority: high, medium or low"
        )

    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Invalid due date format. Please enter the due date for the task (YYYY-MM-DD):"
        )

    return SET_PRIORITY


async def remind_tasks(context):
    while True:
        # Get the current date and time
        current_date = dt.date.today()

        # Retrieve tasks from the database
        tasks = tasks_collection.find()

        # Iterate over tasks and send reminders if due date is reached
        for task in tasks:
            due_date = task['due_date'].date()
            if due_date == current_date:
                chat_id = task['chat_id']
                task_title = task['title']
                message = f"Reminder: Task '{task_title}' is due today!"
                await context.bot.send_message(chat_id=chat_id, text=message)

        # Wait for some time before checking tasks again
        await asyncio.sleep(600)  # Check every minute


async def connect_to_mongodb():
    client = motor.motor_asyncio.AsyncIOMotorClient(
        "mongodb://localhost:27017/")
    db = client['task_management_bot']
    tasks_collection = db['tasks']
    return tasks_collection

# Function to retrieve tasks from the database


async def get_tasks(tasks_collection) -> list:
    tasks = await tasks_collection.find().to_list(None)
    return tasks

# Command handler for retrieving tasks


async def view_tasks(update: Update, context: CallbackContext):
    tasks_collection = await connect_to_mongodb()
    tasks = await get_tasks(tasks_collection)

    if tasks:
        message = "Tasks:\n"
        for task in tasks:
            message += f"- {task['title']}\n"
    else:
        message = "No tasks found."

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


async def set_priority(update: Update, context: CallbackContext):
    if update.message.text:
        priority = update.message.text.lower()
        if priority in ['high', 'medium', 'low']:
            context.user_data['priority'] = priority

            # Save the task to the database
            await save_task(context)

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Task priority set to {priority}."
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid priority. Please enter 'high', 'medium', or 'low':"
            )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Invalid input. Please try again."
        )

    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    bot_token = "6427831805:AAEDbX7HuYZ1nXI_SC9-cmgkH7NQLQeY0Rk"
    bot = Bot(token=bot_token)
    update_queue = queue.Queue()

    updater = Updater(bot=bot, update_queue=update_queue)

    context = updater

    loop = asyncio.get_event_loop()
    loop.create_task(remind_tasks(context))

    application = Application.builder().token(
        "6427831805:AAEDbX7HuYZ1nXI_SC9-cmgkH7NQLQeY0Rk").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TASK_TITLE: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT, task_title)],
            TASK_DESCRIPTION: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT, task_description)],
            SET_DUE_DATE: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT, set_due_date)],
            SET_PRIORITY: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT, set_priority)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add the command handler to the dispatcher
    application.add_handler(CommandHandler("tasks", view_tasks))

    application.add_handler(conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
