import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import TelegramError

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION (via Environment Variables) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@YourChannelUsername")  # Include @

# In-memory storage for user balances (Use SQLite/Postgres for persistent data)
user_balances = {}

def get_balance(user_id: int) -> int:
    return user_balances.get(user_id, 1000)

def set_balance(user_id: int, amount: int):
    user_balances[user_id] = max(0, amount)

async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verifies if the user is a subscriber of the target channel."""
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@YourChannelUsername":
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramError as e:
        logger.error(f"Membership check error: {e}")
        return True

def get_sub_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("✅ Verify Subscription", callback_data="check_sub")]
    ])

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Roll Dice", callback_data="play_dice"), InlineKeyboardButton("🎰 Slot Machine", callback_data="play_slots")],
        [InlineKeyboardButton("🪙 Coin Flip", callback_data="play_coinflip"), InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_daily")],
        [InlineKeyboardButton("💰 My Balance", callback_data="show_balance"), InlineKeyboardButton("🏆 Leaderboard", callback_data="show_leaderboard")]
    ])

# --- COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id not in user_balances:
        user_balances[user_id] = 1000

    is_subscribed = await check_membership(user_id, context)
    
    if not is_subscribed:
        await update.message.reply_text(
            f"👋 Welcome {user.first_name}!\n\n"
            f"To access the Casino and earn free tokens, you must join our channel first!",
            reply_markup=get_sub_keyboard()
        )
        return

    await update.message.reply_text(
        f"🎰 **Welcome to the Channel Boost Casino, {user.first_name}!** 🎲\n\n"
        f"Current Balance: **{get_balance(user_id)} coins**\n"
        f"Choose a game or action below to start playing:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# --- CALLBACK QUERY HANDLERS ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data

    # Always enforce subscription check before any interaction
    if not await check_membership(user_id, context):
        await query.edit_message_text(
            "⚠️ You must join our channel to play games and claim rewards!",
            reply_markup=get_sub_keyboard()
        )
        return

    if data == "check_sub":
        await query.edit_message_text(
            "🎉 Thank you for subscribing! Choose an option below:",
            reply_markup=get_main_keyboard()
        )

    elif data == "show_balance":
        balance = get_balance(user_id)
        await query.edit_message_text(
            f"💳 **Your Current Balance:** {balance} coins",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

    elif data == "claim_daily":
        reward = 250
        current = get_balance(user_id)
        set_balance(user_id, current + reward)
        await query.edit_message_text(
            f"🎁 **Daily Reward Claimed!**\n"
            f"Added +{reward} coins to your balance.\n"
            f"New Balance: {get_balance(user_id)} coins",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

    elif data == "play_dice":
        bet = 100
        balance = get_balance(user_id)
        if balance < bet:
            await query.edit_message_text("❌ Not enough coins! Minimum bet for dice is 100 coins.", reply_markup=get_main_keyboard())
            return
        
        # Send Telegram native animated dice
        msg = await context.bot.send_dice(chat_id=query.message.chat_id, emoji="🎲")
        dice_val = msg.dice.value
        
        # Win if roll is 4, 5, or 6
        if dice_val >= 4:
            win_amt = bet * 2
            set_balance(user_id, balance + bet)
            result_txt = f"🎉 **You Rolled {dice_val}!** You won {win_amt} coins!"
        else:
            set_balance(user_id, balance - bet)
            result_txt = f"📉 **You Rolled {dice_val}!** You lost {bet} coins."

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"{result_txt}\nNew Balance: **{get_balance(user_id)} coins**",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

    elif data == "play_slots":
        bet = 100
        balance = get_balance(user_id)
        if balance < bet:
            await query.edit_message_text("❌ Not enough coins! Minimum bet for slots is 100 coins.", reply_markup=get_main_keyboard())
            return
        
        # Send Telegram native animated slot machine
        msg = await context.bot.send_dice(chat_id=query.message.chat_id, emoji="🎰")
        slot_val = msg.dice.value
        
        # In Telegram slots, 64 is Jackpot (7-7-7)
        if slot_val == 64:
            win_amt = bet * 10
            set_balance(user_id, balance + win_amt)
            result_txt = f"💥 **JACKPOT! 7-7-7!** You won {win_amt} coins!"
        elif slot_val in [1, 22, 43]: # Partial win combinations
            win_amt = bet * 2
            set_balance(user_id, balance + bet)
            result_txt = f"✨ **Nice Spin!** You won {win_amt} coins!"
        else:
            set_balance(user_id, balance - bet)
            result_txt = f"❌ **No Match!** You lost {bet} coins."

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"{result_txt}\nNew Balance: **{get_balance(user_id)} coins**",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

    elif data == "play_coinflip":
        bet = 50
        balance = get_balance(user_id)
        if balance < bet:
            await query.edit_message_text("❌ Not enough coins! Minimum bet for Coin Flip is 50 coins.", reply_markup=get_main_keyboard())
            return

        outcome = random.choice(["Heads", "Tails"])
        user_choice = random.choice(["Heads", "Tails"])
        
        if outcome == user_choice:
            set_balance(user_id, balance + bet)
            res = f"🪙 Flipped **{outcome}**! You picked correctly and won {bet * 2} coins!"
        else:
            set_balance(user_id, balance - bet)
            res = f"🪙 Flipped **{outcome}**! You lost {bet} coins."

        await query.edit_message_text(
            f"{res}\nNew Balance: **{get_balance(user_id)} coins**",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

    elif data == "show_leaderboard":
        sorted_users = sorted(user_balances.items(), key=lambda item: item[1], reverse=True)[:5]
        lb_text = "🏆 **Top 5 Coin Leaders:**\n\n"
        for idx, (u_id, val) in enumerate(sorted_users, 1):
            lb_text += f"{idx}. User ID `{u_id}` — **{val} coins**\n"
        
        await query.edit_message_text(
            lb_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

# --- MAIN RUNNER ---

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot started successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
