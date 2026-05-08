from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import logging

class TelegramChannel:
    def __init__(self, token: str, agent_instance):
        self.token = token
        self.agent = agent_instance
        self.app = ApplicationBuilder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("CESARE attivo. In attesa di ordini, Creatore.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_input = update.message.text
        # Qui invochiamo il grafo di LangGraph
        response = self.agent.run(user_input)
        ai_reply = response["messages"][-1].content
        await update.message.reply_text(ai_reply)

    def run(self):
        logging.info("Telegram Channel avviato.")
        self.app.run_polling()