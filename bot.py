import logging
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Arabic messages
MESSAGES = {
    'start': """أهلاً وسهلاً! 👋

هذا بوت للتواصل مع صاحب الحساب.
يمكنك إرسال رسالتك مباشرة وستصل إليه فوراً.

فقط اكتب رسالتك وأرسلها! 💬""",
    'error': "حدث خطأ، يرجى المحاولة مرة أخرى.",
    'owner_only': "هذا الأمر للمالك فقط.",
    'stats_header': "📊 إحصائيات البوت:\n\n",
    'user_not_found': "المستخدم غير موجود أو لم يرسل رسائل من قبل.",
    'no_conversations': "لا توجد محادثات حتى الآن.",
    'select_user_to_reply': "اختر مستخدم للرد عليه:",
    'owner_help': """أوامر المالك:
/stats - عرض الإحصائيات
/conversations - عرض قائمة المحادثات"""
}

class MessageBot:
    def __init__(self):
        self.message_count = 0
        self.users = set()
        self.conversations = {}
        self.user_info = {}
        self.owner_threads = {}
        self.load_data()

    def save_data(self):
        try:
            with open('bot_data.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'message_count': self.message_count,
                    'users': list(self.users),
                    'conversations': self.conversations,
                    'user_info': self.user_info,
                    'owner_threads': self.owner_threads
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def load_data(self):
        try:
            if os.path.exists('bot_data.json'):
                with open('bot_data.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.message_count = data.get('message_count', 0)
                    self.users = set(data.get('users', []))
                    self.conversations = data.get('conversations', {})
                    self.user_info = data.get('user_info', {})
                    self.owner_threads = data.get('owner_threads', {})
        except Exception as e:
            logger.error(f"Error loading data: {e}")

    def add_to_conversation(self, user_id: int, message: dict):
        user_id_str = str(user_id)
        if user_id_str not in self.conversations:
            self.conversations[user_id_str] = []
        self.conversations[user_id_str].append({
            'timestamp': datetime.now().isoformat(),
            **message
        })
        if len(self.conversations[user_id_str]) > 100:
            self.conversations[user_id_str] = self.conversations[user_id_str][-100:]
        self.save_data()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.users.add(user.id)
        self.user_info[str(user.id)] = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'last_active': datetime.now().isoformat()
        }
        self.save_data()
        await update.message.reply_text(MESSAGES['start'])

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id == OWNER_ID:
            await update.message.reply_text(MESSAGES['owner_help'])
        else:
            await self.start_command(update, context)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text(MESSAGES['owner_only'])
            return
        stats_text = MESSAGES['stats_header']
        stats_text += f"عدد المستخدمين: {len(self.users)}\n"
        stats_text += f"إجمالي الرسائل: {self.message_count}\n"
        stats_text += f"المحادثات النشطة: {len(self.conversations)}\n"
        await update.message.reply_text(stats_text)

    async def conversations_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text(MESSAGES['owner_only'])
            return
        if not self.conversations:
            await update.message.reply_text(MESSAGES['no_conversations'])
            return
        keyboard = []
        for user_id, messages in self.conversations.items():
            info = self.user_info.get(user_id, {})
            name = info.get('first_name', f'مستخدم {user_id}')
            if info.get('last_name'):
                name += f" {info['last_name']}"
            last_message = messages[-1]['text'] if messages else ""
            preview = (last_message[:30] + "...") if len(last_message) > 30 else last_message
            keyboard.append([InlineKeyboardButton(f"👤 {name} - {preview}", callback_data=f"reply_{user_id}")])
        await update.message.reply_text(MESSAGES['select_user_to_reply'], reply_markup=InlineKeyboardMarkup(keyboard))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text

        if user_id == OWNER_ID:
            await self.handle_owner_message(update, context)
            return

        self.users.add(user_id)
        user = update.effective_user
        self.user_info[str(user_id)] = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'last_active': datetime.now().isoformat()
        }
        self.message_count += 1

        # Store the message
        self.add_to_conversation(user_id, {
            'text': text,
            'sender': 'user',
            'tg_message_id': update.message.message_id
        })

        await self.send_to_owner(update, text, update.message.message_id)

    async def handle_owner_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            replied_id = update.message.reply_to_message.message_id
            # Find the user this message belongs to
            for uid, messages in self.conversations.items():
                for msg in messages:
                    if msg.get('tg_owner_message_id') == replied_id:
                        await self.send_reply_to_user(
                            update,
                            int(uid),
                            update.message.text,
                            reply_to_msg_id=msg.get('tg_message_id')
                        )
                        return
        await update.message.reply_text("❗ يجب الرد على رسالة مستخدم موجودة.")

    async def send_reply_to_user(self, update: Update, target_user_id: int, message_text: str, reply_to_msg_id=None):
        try:
            sent_msg = await update.get_bot().send_message(
                chat_id=target_user_id,
                text=message_text,
                reply_to_message_id=reply_to_msg_id
            )
            self.add_to_conversation(target_user_id, {
                'text': message_text,
                'sender': 'owner',
                'tg_message_id': sent_msg.message_id
            })
        except Exception as e:
            logger.error(f"Error sending reply: {e}")
            await update.message.reply_text(MESSAGES['error'])

    async def send_to_owner(self, update: Update, message_text: str, user_msg_id: int):
        try:
            user = update.effective_user
            user_id = user.id
            username = f"@{user.username}" if user.username else "لا يوجد معرف"
            header_text = f"📨 محادثة مع {user.first_name or ''} {user.last_name or ''}\n🆔 {username} | ID: {user.id}"

            if str(user_id) not in self.owner_threads:
                msg = await update.get_bot().send_message(chat_id=OWNER_ID, text=header_text)
                self.owner_threads[str(user_id)] = msg.message_id
                self.save_data()

            owner_msg = await update.get_bot().send_message(
                chat_id=OWNER_ID,
                text=message_text,
                reply_to_message_id=self.owner_threads[str(user_id)]
            )

            self.add_to_conversation(user_id, {
                'text': message_text,
                'sender': 'user',
                'tg_message_id': user_msg_id,
                'tg_owner_message_id': owner_msg.message_id
            })

        except Exception as e:
            logger.error(f"Error sending to owner: {e}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Update {update} caused error {context.error}")

def main():
    bot = MessageBot()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", bot.start_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("stats", bot.stats_command))
    app.add_handler(CommandHandler("conversations", bot.conversations_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    app.add_error_handler(bot.error_handler)
    print("🤖 البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
