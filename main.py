import asyncio
from datetime import datetime, timezone
import os
import sqlite3
from contextlib import closing

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

# Tabbatar cewa waɗannan suna aiki daidai
from config import BOT_TOKEN, CHANNEL_ID, CHANNEL_LINK, ADMINS, OTP_GROUP_LINK, DB_PATH
import db 

# === Initialization ===
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
db.init_db()

# === Helper Functions ===
async def is_subscribed(user_id: int) -> bool:
    """Checks if a user is a member of the required channel."""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in {"member", "administrator", "creator"}
    except Exception:
        return False

async def get_number_handler(target: types.Message | types.CallbackQuery):
    """Handles the logic for displaying available countries and numbers, ciki har da adadin."""
    user_id = target.from_user.id
    # Saki lambar mai aiki idan akwai
    if db.get_active(user_id):
        old_number = db.get_active(user_id)[0]
        db.release_number(old_number)
        
    countries_with_counts = {}
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        # Zabi dukkan kasashe tare da adadin lambobin da basu yi amfani ba (used=0)
        cursor.execute("""
            SELECT country, COUNT(number) 
            FROM numbers 
            WHERE used=0 
            GROUP BY country
        """)
        # Ajiye bayanai a dictionary (misali: {'🇳🇬 Nigeria FB': 5000})
        countries_with_counts = {row[0]: row[1] for row in cursor.fetchall()}

    if not countries_with_counts:
        msg = "⚠️ **No unused numbers available right now.** Please wait for the admin to upload new numbers."
        if isinstance(target, Message):
            await target.answer(msg)
        else:
            await bot.send_message(target.from_user.id, msg)
        return

    kb = InlineKeyboardBuilder()
    # Ƙirƙirar maɓallin tare da ƙididdigar (count)
    for ctry, count in sorted(countries_with_counts.items()):
        # Idan adadin ya zama 0, kar ka nuna
        if count > 0:
            # Sabon rubutu: 🇳🇬 Nigeria FB (5000)
            button_text = f"{ctry} ({count})"
            # Callback_data ya kasance kamar da (misali: country:🇳🇬 Nigeria FB)
            kb.button(text=button_text, callback_data=f"country:{ctry}")
    
    kb.adjust(2)
    
    if not kb.buttons:
        msg = "⚠️ **No unused numbers available right now.** Please wait for the admin to upload new numbers."
        if isinstance(target, Message):
            await target.answer(msg)
        else:
            await bot.send_message(target.from_user.id, msg)
        return

    text = "🌍 Select a country to get a number (Count = Available Numbers):"
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb.as_markup())
    else:
        await target.message.edit_text(text, reply_markup=kb.as_markup())

# === Keyboards ===
def menu_keyboard():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📱 Get Number")
    kb.button(text="📊 Active Number")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def active_keyboard():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🔄 Change Number")
    kb.button(text="🏠 Main Menu")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def otp_keyboard():
    kb = InlineKeyboardBuilder()
    # Bayan an karɓi lamba, wannan 'Change Country' zai sake kira ga 'get_number_handler'
    # wanda zai nuna sabon adadin da ya ragu.
    kb.button(text="🌍 Change Country", callback_data="get_number_action") 
    kb.button(text="🔄 Change Number", callback_data="change_number_action")
    kb.button(text="📨 OTP Group", url=OTP_GROUP_LINK)
    kb.adjust(1)
    return kb.as_markup()

def verify_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Join Channel", url=CHANNEL_LINK)  # ✅ yanzu ana amfani da CHANNEL_LINK
    kb.button(text="✅ Verified", callback_data="verify")
    kb.adjust(1)
    return kb.as_markup()

# === Handlers ===
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    if not await is_subscribed(msg.from_user.id):
        await msg.answer(
            "👋 Welcome!\n\nPlease join our channel first:",
            reply_markup=verify_keyboard()
        )
        return
    await msg.answer(
        f"Welcome {msg.from_user.full_name}! 🎉\nThis is Bulk SMS.\n\nUse the keyboard below:",
        reply_markup=menu_keyboard()
    )

@dp.callback_query(F.data == "verify")
async def verify_user(cb: CallbackQuery):
    if await is_subscribed(cb.from_user.id):
        await cb.message.delete()
        await bot.send_message(
            cb.from_user.id,
            f"Welcome {cb.from_user.full_name}! 🎉\nThis is Bulk SMS.\n\nUse the keyboard below:",
            reply_markup=menu_keyboard()
        )
    else:
        await cb.answer("❌ You are not a member of the channel!", show_alert=True)
        await cb.message.edit_text(
            "❌ Not Verified\n\nPlease join our channel first:",
            reply_markup=verify_keyboard()
        )

@dp.message(F.text == "📱 Get Number")
@dp.callback_query(F.data == "get_number_action")
async def get_number_cmd(event: Message | CallbackQuery):
    await get_number_handler(event)

@dp.callback_query(F.data == "change_number_action")
async def change_number_handler(cb: CallbackQuery):
    user_id = cb.from_user.id
    active_number_data = db.get_active(user_id)

    if not active_number_data:
        await cb.answer("⚠️ Ba ku da lambar da ke aiki da za ku canza!", show_alert=True)
        return

    await cb.message.edit_text("⏳ Please wait for 3 seconds before changing number...")
    await asyncio.sleep(3)

    old_number = active_number_data[0]
    # Saki tsohuwar lamba
    db.release_number(old_number) 

    # Karbi sabuwar lamba
    new_number_data = db.get_random_unused()
    if not new_number_data:
        await cb.message.edit_text(
            f"⚠️ Babu sabuwar lamba yanzu.\n"
            f"An saki tsohuwar lambar ku ({old_number})."
        )
        return

    new_number, new_country = new_number_data
    db.set_active(user_id, new_number, new_country)

    await cb.message.edit_text(
        f"📞 **Sabuwar Lambar Ku!**\n\n"
        f"Danna don kwafa: `{(new_number)}`\n\n"
        f"✅ Sabuwar lambar ku tana aiki!\n\n"
        f"❗️Ku shiga 'OTP Group' don ganin sakonni masu shigowa.",
        reply_markup=otp_keyboard()
    )

@dp.callback_query(F.data.startswith("country:"))
async def select_country(cb: CallbackQuery):
    country = cb.data.split(":")[1]
    number_data = db.get_unused_number(country)
    
    # Sake dubawa don tabbatar da akwai lamba (duk da cewa count ya nuna akwai)
    if not number_data: 
        await cb.message.edit_text(f"⚠️ **No unused number left for {country}.** Please try another country or press 'Change Country' to refresh.")
        return

    number = number_data[0]
    
    # Saita lambar a matsayin mai aiki da 'used=1'
    db.set_active(cb.from_user.id, number, country) 
    
    await cb.message.edit_text(
        f"📞 **Your Number is Ready!**\n\n"
        f"Tap to copy: `{(number)}`\n\n"
        f"✅ Your number is active!\n\n"
        f"❗️Go to our OTP Group to see your incoming SMS.",
        reply_markup=otp_keyboard()
    )

@dp.message(F.text == "📊 Active Number")
async def active_number(msg: Message):
    row = db.get_active(msg.from_user.id)
    if not row:
        await msg.answer("⚠️ You don’t have any active number.\nUse 📱 Get Number first.")
        return
    number, country, assigned_at = row
    assigned_dt = datetime.fromisoformat(assigned_at)
    mins = int((datetime.now(timezone.utc) - assigned_dt.replace(tzinfo=timezone.utc)).total_seconds() // 60)
    await msg.answer(
        f"📊 **Your Active Number**\n\n"
        f"📞 Number: `{(number)}`\n"
        f"🌍 Country: {country}\n"
        f"🧭 Active for: {mins} minutes",
        reply_markup=active_keyboard()
    )

@dp.message(F.text == "🏠 Main Menu")
async def back_main(msg: Message):
    await msg.answer("🏠 Main Menu", reply_markup=menu_keyboard())

# === Admin Functions ===
@dp.message(F.document)
async def handle_file(msg: Message):
    if msg.from_user.id not in ADMINS:
        return
    if not msg.caption:
        await msg.answer("⚠️ Please add a country name as the caption for the file.")
        return
    
    file_id = msg.document.file_id
    file_info = await bot.get_file(file_id)
    download_path = f"temp_{msg.document.file_name}"

    try:
        await bot.download_file(file_info.file_path, download_path)
        with open(download_path, "r") as f:
            numbers = f.read().splitlines()
        db.add_numbers(msg.caption.strip(), numbers)
        await msg.answer(f"✅ Added {len(numbers)} numbers for {msg.caption.strip()}")
    except Exception as e:
        await msg.answer(f"❌ Error while adding numbers: {e}")
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)

@dp.message(Command("delete"))
async def delete_cmd(msg: Message):
    if msg.from_user.id not in ADMINS:
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /delete <Country>")
        return
    deleted_count = db.delete_numbers(args[1].strip())
    await msg.answer(f"🗑 Deleted {deleted_count} numbers for {args[1].strip()}.")

# === Run ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
