import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWNER_ID = int(os.environ.get('OWNER_ID', '0'))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found! Please add it to your .env file")
    exit(1)

if OWNER_ID == 0:
    logger.error("OWNER_ID not found! Please add it to your .env file")
    exit(1)

print("✅ Bot configuration loaded successfully!")

# Arabic messages
MESSAGES = {
    'start': """أهلاً وسهلاً! 👋

هذا بوت للتواصل مع صاحب الحساب.
يمكنك إرسال رسالتك وستصل إليه مباشرة.

اختر كيف تريد إرسال رسالتك:""",
    
    'choose_mode': "اختر طريقة الإرسال:",
    'anonymous': "إرسال مجهول 🕶️",
    'with_name': "إرسال باسمي 👤",
    'send_message': "الآن اكتب رسالتك:",
    'message_sent': "تم إرسال رسالتك بنجاح! ✅",
    'message_sent_anonymous': "تم إرسال رسالتك المجهولة بنجاح! ✅",
    'cancel': "إلغاء ❌",
    'cancelled': "تم إلغاء العملية.",
    'error': "حدث خطأ، يرجى المحاولة مرة أخرى.",
    'owner_only': "هذا الأمر للمالك فقط.",
    'stats_header': "📊 إحصائيات البوت:\n\n",
    'back_to_menu': "العودة للقائمة الرئيسية 🏠"
}

class MessageBot:
    def __init__(self):
        self.user_states = {}
        self.message_count = 0
        self.anonymous_count = 0
        self.named_count = 0
        self.users = set()

    async def start_command(self, update: Update, context):
        user_id = update.effective_user.id
        self.users.add(user_id)
        
        keyboard = [
            [KeyboardButton(MESSAGES['anonymous'])],
            [KeyboardButton(MESSAGES['with_name'])],
            [KeyboardButton(MESSAGES['back_to_menu'])]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(MESSAGES['start'], reply_markup=reply_markup)

    async def stats_command(self, update: Update, context):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text(MESSAGES['owner_only'])
            return
        
        stats_text = MESSAGES['stats_header']
        stats_text += f"عدد المستخدمين: {len(self.users)}\n"
        stats_text += f"إجمالي الرسائل: {self.message_count}\n"
        stats_text += f"الرسائل المجهولة: {self.anonymous_count}\n"
        stats_text += f"الرسائل المعرّفة: {self.named_count}\n"
        
        await update.message.reply_text(stats_text)

    async def handle_message(self, update: Update, context):
        user_id = update.effective_user.id
        message_text = update.message.text
        
        self.users.add(user_id)
        
        if message_text == MESSAGES['anonymous']:
            self.user_states[user_id] = 'waiting_anonymous_message'
            keyboard = [[KeyboardButton(MESSAGES['cancel'])]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(MESSAGES['send_message'], reply_markup=reply_markup)
            
        elif message_text == MESSAGES['with_name']:
            self.user_states[user_id] = 'waiting_named_message'
            keyboard = [[KeyboardButton(MESSAGES['cancel'])]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(MESSAGES['send_message'], reply_markup=reply_markup)
            
        elif message_text == MESSAGES['cancel']:
            if user_id in self.user_states:
                del self.user_states[user_id]
            await self.show_main_menu(update)
            await update.message.reply_text(MESSAGES['cancelled'])
            
        elif message_text == MESSAGES['back_to_menu']:
            if user_id in self.user_states:
                del self.user_states[user_id]
            await self.show_main_menu(update)
            
        elif user_id in self.user_states:
            state = self.user_states[user_id]
            
            if state == 'waiting_anonymous_message':
                await self.send_to_owner(update, message_text, anonymous=True)
                self.anonymous_count += 1
                self.message_count += 1
                del self.user_states[user_id]
                await self.show_main_menu(update)
                await update.message.reply_text(MESSAGES['message_sent_anonymous'])
                
            elif state == 'waiting_named_message':
                await self.send_to_owner(update, message_text, anonymous=False)
                self.named_count += 1
                self.message_count += 1
                del self.user_states[user_id]
                await self.show_main_menu(update)
                await update.message.reply_text(MESSAGES['message_sent'])
        else:
            await self.show_main_menu(update)

    async def show_main_menu(self, update: Update):
        keyboard = [
            [KeyboardButton(MESSAGES['anonymous'])],
            [KeyboardButton(MESSAGES['with_name'])]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(MESSAGES['choose_mode'], reply_markup=reply_markup)

    async def send_to_owner(self, update: Update, message_text: str, anonymous: bool = True):
        try:
            user = update.effective_user
            
            if anonymous:
                forward_text = f"📩 رسالة مجهولة جديدة:\n\n{message_text}"
            else:
                username = f"@{user.username}" if user.username else "لا يوجد معرف"
                forward_text = f"📨 رسالة جديدة من:\n"
                forward_text += f"الاسم: {user.first_name}"
                if user.last_name:
                    forward_text += f" {user.last_name}"
                forward_text += f"\nالمعرف: {username}\n"
                forward_text += f"الID: {user.id}\n\n"
                forward_text += f"الرسالة:\n{message_text}"
            
            await update.get_bot().send_message(chat_id=OWNER_ID, text=forward_text)
            
        except Exception as e:
            logger.error(f"Error sending message to owner: {e}")
            await update.message.reply_text(MESSAGES['error'])

def main():
    bot = MessageBot()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("stats", bot.stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("🤖 البوت يعمل الآن...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
