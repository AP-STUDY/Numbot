"""
💎 AP NUMBER X INFO BOT 💎
Owner: @ap_ultimate07
Complete Bot with Credit System, Referral, Admin Panel, Giveaway
"""

import json
import os
import logging
import asyncio
import secrets
import string
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import requests

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8674712607:AAFcxHswNr71gP36Yx__aIB4gYHaNiTeP7g"
OWNER_ID = 8505983842
OWNER_USERNAME = "@ap_ultimate07"
BOT_NAME = "💎 𝐀𝐏 𝐍𝐔𝐌𝐁𝐄𝐑 𝐗 𝐈𝐍𝐅𝐎 💎"
BOT_URL = "http://t.me/apnumxinfobot"
FORCE_SUB_GROUP = "https://t.me/apnumxinfoofficial"
FORCE_SUB_GROUP_ID = "@apnumxinfoofficial"
FORCE_SUB_CHANNEL = "https://t.me/apnumxinfo"
FORCE_SUB_CHANNEL_ID = "@apnumxinfo"
API_URL = "https://free.proapis.bond/num?number={}"

# Daily credits settings
DAILY_CREDITS = 5
REFERRAL_POINTS = 2
CREDIT_RESET_HOURS = 24
CREDIT_PER_SEARCH = 1

# Database file
DB_FILE = "database.json"
GIVEAWAY_FILE = "giveaways.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ==================== DATABASE FUNCTIONS ====================
def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "banned": [], "admins": [], "referrals": {}}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def load_giveaways():
    if not os.path.exists(GIVEAWAY_FILE):
        return {}
    with open(GIVEAWAY_FILE, "r") as f:
        return json.load(f)

def save_giveaways(gw):
    with open(GIVEAWAY_FILE, "w") as f:
        json.dump(gw, f, indent=2)


def get_user(user_id):
    """Get or create user"""
    db = load_db()
    user_id = str(user_id)
    if user_id not in db["users"]:
        db["users"][user_id] = {
            "credits": DAILY_CREDITS,
            "referral_points": 0,
            "referred_by": None,
            "total_searches": 0,
            "last_credit_reset": datetime.now().isoformat(),
            "joined_at": datetime.now().isoformat(),
            "first_name": "",
            "username": ""
        }
        save_db(db)
    return db["users"][user_id]


def update_user(user_id, data):
    db = load_db()
    user_id = str(user_id)
    db["users"][user_id] = data
    save_db(db)


def is_banned(user_id):
    db = load_db()
    return str(user_id) in db["banned"]


def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    db = load_db()
    return str(user_id) in db.get("admins", [])


def check_and_reset_credits(user_id):
    """Reset credits if 24 hours passed AND credits left is less than DAILY_CREDITS
       but only reset if user still has some from old batch (< DAILY_CREDITS)"""
    user = get_user(user_id)
    last_reset = datetime.fromisoformat(user["last_credit_reset"])
    now = datetime.now()
    
    if now - last_reset >= timedelta(hours=CREDIT_RESET_HOURS):
        # Only reset if current credits < DAILY_CREDITS (old leftover)
        if user["credits"] < DAILY_CREDITS:
            user["credits"] = DAILY_CREDITS
        user["last_credit_reset"] = now.isoformat()
        update_user(user_id, user)
    return user


# ==================== FORCE SUBSCRIBE ====================
async def check_force_sub(bot, user_id):
    """Check if user joined force subscribe channels"""
    channels = [FORCE_SUB_GROUP_ID, FORCE_SUB_CHANNEL_ID]
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logger.warning(f"Force sub check error for {ch}: {e}")
            # If bot is not admin, allow (don't block)
            continue
    return True


async def send_force_sub_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=FORCE_SUB_CHANNEL)],
        [InlineKeyboardButton("👥 Join Group", url=FORCE_SUB_GROUP)],
        [InlineKeyboardButton("✅ I Have Joined", callback_data="check_sub")]
    ]
    text = (
        "⚠️ *You Must Join Our Channel & Group To Use This Bot!*\n\n"
        f"📢 Channel: {FORCE_SUB_CHANNEL}\n"
        f"👥 Group: {FORCE_SUB_GROUP}\n\n"
        "After joining click *I Have Joined* button."
    )
    if update.callback_query:
        await update.callback_query.message.edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


# ==================== START COMMAND ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    
    # Force sub check
    if not await check_force_sub(context.bot, user_id):
        await send_force_sub_msg(update, context)
        return
    
    # Handle referral
    args = context.args
    db = load_db()
    user_data = get_user(user_id)
    
    if args and args[0].startswith("ref_"):
        referrer_id = args[0].replace("ref_", "")
        if (referrer_id != str(user_id) and 
            user_data.get("referred_by") is None and
            referrer_id in db["users"]):
            
            user_data["referred_by"] = referrer_id
            referrer = db["users"][referrer_id]
            referrer["referral_points"] += REFERRAL_POINTS
            db["users"][str(user_id)] = user_data
            db["users"][referrer_id] = referrer
            save_db(db)
            
            try:
                await context.bot.send_message(
                    chat_id=int(referrer_id),
                    text=f"🎉 *New Referral!*\n\n"
                         f"👤 {user.first_name} joined using your link\n"
                         f"💰 You earned *{REFERRAL_POINTS}* points!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
    
    user_data["first_name"] = user.first_name or ""
    user_data["username"] = user.username or ""
    update_user(user_id, user_data)
    
    check_and_reset_credits(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search Number", callback_data="search_menu")],
        [InlineKeyboardButton("👤 My Account", callback_data="my_account"),
         InlineKeyboardButton("🔗 Referral", callback_data="referral")],
        [InlineKeyboardButton("💎 Premium", callback_data="premium"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")],
        [InlineKeyboardButton("📢 Join Channel", url=FORCE_SUB_CHANNEL)]
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    
    text = (
        f"╔══════════════════════════╗\n"
        f"   💎 *𝐀𝐏 𝐍𝐔𝐌𝐁𝐄𝐑 𝐗 𝐈𝐍𝐅𝐎* 💎\n"
        f"╚══════════════════════════╝\n\n"
        f"👋 Welcome *{user.first_name}*!\n\n"
        f"🔍 Get Complete Information of any Mobile Number!\n\n"
        f"📌 *Features:*\n"
        f"• Mobile Number Info\n"
        f"• Owner Name & Address\n"
        f"• Circle & Network\n"
        f"• ADHAR Info (Premium)\n\n"
        f"💰 Credits: *{user_data['credits']}*\n"
        f"🎁 Referral Points: *{user_data['referral_points']}*\n\n"
        f"👑 Owner: {OWNER_USERNAME}"
    )
    
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


# ==================== CALLBACK HANDLER ====================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if is_banned(user_id):
        await query.edit_message_text("🚫 You are banned from using this bot.")
        return
    
    # Force sub recheck
    if data == "check_sub":
        if await check_force_sub(context.bot, user_id):
            await query.edit_message_text(
                "✅ *Verification Successful!*\n\nSend /start again to continue.",
                parse_mode="Markdown"
            )
        else:
            await send_force_sub_msg(update, context)
        return
    
    if not await check_force_sub(context.bot, user_id):
        await send_force_sub_msg(update, context)
        return
    
    # ========== SEARCH MENU ==========
    if data == "search_menu":
        await query.edit_message_text(
            "🔍 *Send me a 10-digit mobile number to search.*\n\n"
            "Example: `9876543210`\n\n"
            f"💳 Cost: *{CREDIT_PER_SEARCH} credit* per search",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ])
        )
    
    elif data == "back_home":
        user = query.from_user
        user_data = get_user(user_id)
        keyboard = [
            [InlineKeyboardButton("🔍 Search Number", callback_data="search_menu")],
            [InlineKeyboardButton("👤 My Account", callback_data="my_account"),
             InlineKeyboardButton("🔗 Referral", callback_data="referral")],
            [InlineKeyboardButton("💎 Premium", callback_data="premium"),
             InlineKeyboardButton("ℹ️ Help", callback_data="help")],
        ]
        if is_admin(user_id):
            keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
        await query.edit_message_text(
            f"🏠 *Main Menu*\n\n💰 Credits: *{user_data['credits']}*\n🎁 Points: *{user_data['referral_points']}*",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    
    # ========== MY ACCOUNT ==========
    elif data == "my_account":
        user_data = check_and_reset_credits(user_id)
        user = query.from_user
        text = (
            f"╔══════════════════════════╗\n"
            f"   👤 *MY ACCOUNT*\n"
            f"╚══════════════════════════╝\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"👤 Name: {user.first_name}\n"
            f"🔗 Username: @{user.username or 'N/A'}\n\n"
            f"💰 *Credits:* {user_data['credits']}\n"
            f"🎁 *Referral Points:* {user_data['referral_points']}\n"
            f"🔍 *Total Searches:* {user_data['total_searches']}\n"
            f"👥 *Referred By:* {user_data.get('referred_by') or 'None'}\n"
            f"📅 Joined: {user_data['joined_at'][:10]}\n\n"
            f"⏰ Credits reset every {CREDIT_RESET_HOURS}h (if leftover)"
        )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ])
        )
    
    # ========== REFERRAL ==========
    elif data == "referral":
        user_data = get_user(user_id)
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        text = (
            f"╔══════════════════════════╗\n"
            f"   🔗 *REFERRAL SYSTEM*\n"
            f"╚══════════════════════════╝\n\n"
            f"💰 *Earn {REFERRAL_POINTS} Points per successful referral!*\n"
            f"📌 Referral points never reset.\n\n"
            f"🔗 *Your Referral Link:*\n`{ref_link}`\n\n"
            f"📊 *Your Stats:*\n"
            f"🎁 Points: *{user_data['referral_points']}*\n"
            f"👥 Referrals: *{len([u for u in load_db()['users'].values() if u.get('referred_by') == str(user_id)])}*"
        )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={ref_link}&text=Get%20Mobile%20Number%20Info!")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ])
        )
    
    # ========== PREMIUM ==========
    elif data == "premium":
        text = (
            f"╔══════════════════════════╗\n"
            f"   💎 *PREMIUM PLANS*\n"
            f"╚══════════════════════════╝\n\n"
            f"🆓 *FREE PLAN:*\n"
            f"• {DAILY_CREDITS} credits daily\n"
            f"• Basic Number Info\n"
            f"• {CREDIT_PER_SEARCH} credit per search\n\n"
            f"💎 *PREMIUM PLAN:*\n"
            f"• Unlimited Credits ♾️\n"
            f"• Full Owner Details\n"
            f"• ADHAR Info Access\n"
            f"• Priority Support\n"
            f"• No Daily Limits\n\n"
            f"💰 *Price:* Contact Owner\n\n"
            f"👑 Owner: {OWNER_USERNAME}\n\n"
            f"📩 DM for Premium Purchase"
        )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Owner", url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ])
        )
    
    # ========== HELP ==========
    elif data == "help":
        text = (
            f"╔══════════════════════════╗\n"
            f"   ℹ️ *HELP & GUIDE*\n"
            f"╚══════════════════════════╝\n\n"
            f"📌 *How To Use:*\n\n"
            f"1️⃣ Send /start to begin\n"
            f"2️⃣ Join our channels\n"
            f"3️⃣ Send any 10-digit mobile number\n"
            f"4️⃣ Get complete info instantly!\n\n"
            f"💰 *Credits System:*\n"
            f"• You get {DAILY_CREDITS} credits every {CREDIT_RESET_HOURS}h\n"
            f"• Leftover credits reset after {CREDIT_RESET_HOURS}h\n"
            f"• {CREDIT_PER_SEARCH} credit used per search\n"
            f"• Referral points never reset\n\n"
            f"🔗 *Referral:*\n"
            f"• Share your link\n"
            f"• Earn {REFERRAL_POINTS} points per join\n\n"
            f"📞 *Support:* {OWNER_USERNAME}"
        )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ])
        )
    
    # ========== ADMIN PANEL ==========
    elif data == "admin_panel":
        if not is_admin(user_id):
            await query.answer("❌ Not authorized!", show_alert=True)
            return
        await admin_panel_view(query, context)
    
    elif data.startswith("admin_"):
        if not is_admin(user_id):
            await query.answer("❌ Not authorized!", show_alert=True)
            return
        await admin_callback(update, context, data)


async def admin_panel_view(query, context):
    db = load_db()
    total_users = len(db["users"])
    total_banned = len(db["banned"])
    total_admins = len(db.get("admins", []))
    total_gw = len(load_giveaways())
    
    text = (
        f"╔══════════════════════════╗\n"
        f"   ⚙️ *ADMIN PANEL*\n"
        f"╚══════════════════════════╝\n\n"
        f"📊 *Bot Statistics:*\n"
        f"👥 Total Users: *{total_users}*\n"
        f"🚫 Banned Users: *{total_banned}*\n"
        f"👑 Admins: *{total_admins}*\n"
        f"🎁 Active Giveaways: *{total_gw}*\n\n"
        f"Select an option below 👇"
    )
    keyboard = [
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users"),
         InlineKeyboardButton("🚫 Banned List", callback_data="admin_banned")],
        [InlineKeyboardButton("➕ Add Credits", callback_data="admin_add_credits"),
         InlineKeyboardButton("➖ Remove Credits", callback_data="admin_rm_credits")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
         InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton("👑 Add Admin", callback_data="admin_add_admin"),
         InlineKeyboardButton("❌ Remove Admin", callback_data="admin_rm_admin")],
        [InlineKeyboardButton("🎁 Create Giveaway", callback_data="admin_create_gw"),
         InlineKeyboardButton("📋 List Giveaways", callback_data="admin_list_gw")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def admin_callback(update, context, data):
    query = update.callback_query
    db = load_db()
    
    if data == "admin_users":
        users = db["users"]
        text = f"👥 *Total Users: {len(users)}*\n\n"
        for i, (uid, u) in enumerate(list(users.items())[:30], 1):
            text += f"{i}. `{uid}` - {u.get('first_name','N/A')} | 💰{u['credits']} | 🎁{u['referral_points']}\n"
        if len(users) > 30:
            text += f"\n_...and {len(users)-30} more_"
        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))
    
    elif data == "admin_banned":
        banned = db["banned"]
        text = f"🚫 *Banned Users: {len(banned)}*\n\n"
        for i, uid in enumerate(banned, 1):
            text += f"{i}. `{uid}`\n"
        if not banned:
            text += "_No banned users_"
        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))
    
    elif data in ["admin_add_credits", "admin_rm_credits", "admin_ban", "admin_unban",
                  "admin_add_admin", "admin_rm_admin", "admin_create_gw", "admin_broadcast"]:
        context.user_data["admin_action"] = data
        prompts = {
            "admin_add_credits": "➕ *Add Credits*\n\nSend: `user_id amount`\nExample: `123456789 10`",
            "admin_rm_credits": "➖ *Remove Credits*\n\nSend: `user_id amount`\nExample: `123456789 5`",
            "admin_ban": "🚫 *Ban User*\n\nSend: `user_id`",
            "admin_unban": "✅ *Unban User*\n\nSend: `user_id`",
            "admin_add_admin": "👑 *Add Admin*\n\nSend: `user_id`",
            "admin_rm_admin": "❌ *Remove Admin*\n\nSend: `user_id`",
            "admin_create_gw": "🎁 *Create Giveaway*\n\nSend: `credits amount`\nExample: `50 5` (50 credits, 5 uses)\n\nBot will generate a unique code.",
            "admin_broadcast": "📢 *Broadcast*\n\nSend the message to broadcast to all users."
        }
        await query.edit_message_text(prompts[data], parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_panel")]]))
    
    elif data == "admin_list_gw":
        gw = load_giveaways()
        text = f"🎁 *Active Giveaways: {len(gw)}*\n\n"
        for code, info in gw.items():
            text += f"🎟️ `{code}`\n   💰 {info['credits']} credits | Used: {info['used']}/{info['uses']}\n\n"
        if not gw:
            text += "_No active giveaways_"
        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))


# ==================== MESSAGE HANDLER ====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    text = update.message.text.strip()
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return
    
    if not await check_force_sub(context.bot, user_id):
        await send_force_sub_msg(update, context)
        return
    
    # Admin action
    if is_admin(user_id) and context.user_data.get("admin_action"):
        await handle_admin_action(update, context, text)
        return
    
    # Check for giveaway code (uppercase alphanumeric)
    gw = load_giveaways()
    if text.upper() in gw:
        code = text.upper()
        gw_data = gw[code]
        if str(user_id) in gw_data.get("claimed_by", []):
            await update.message.reply_text("❌ You already claimed this giveaway code!")
            return
        if gw_data["used"] >= gw_data["uses"]:
            await update.message.reply_text("❌ This giveaway code has expired!")
            return
        user_data = get_user(user_id)
        user_data["credits"] += gw_data["credits"]
        update_user(user_id, user_data)
        gw_data["used"] += 1
        gw_data.setdefault("claimed_by", []).append(str(user_id))
        save_giveaways(gw)
        await update.message.reply_text(
            f"🎉 *Giveaway Claimed!*\n\n💰 You received *{gw_data['credits']}* credits!\n"
            f"💳 New Balance: *{user_data['credits']}*",
            parse_mode="Markdown"
        )
        return
    
    # Check mobile number
    if text.isdigit() and len(text) == 10:
        await search_number(update, context, text)
        return
    
    await update.message.reply_text(
        "❌ Invalid input!\n\nSend a valid *10-digit mobile number* or use /start",
        parse_mode="Markdown"
    )


async def handle_admin_action(update, context, text):
    user_id = update.effective_user.id
    action = context.user_data.get("admin_action")
    db = load_db()
    
    try:
        if action in ["admin_add_credits", "admin_rm_credits"]:
            parts = text.split()
            uid, amt = parts[0], int(parts[1])
            if uid not in db["users"]:
                await update.message.reply_text("❌ User not found!")
                context.user_data.pop("admin_action", None)
                return
            if action == "admin_add_credits":
                db["users"][uid]["credits"] += amt
                msg = f"✅ Added {amt} credits to `{uid}`\nNew: {db['users'][uid]['credits']}"
            else:
                db["users"][uid]["credits"] = max(0, db["users"][uid]["credits"] - amt)
                msg = f"✅ Removed {amt} credits from `{uid}`\nNew: {db['users'][uid]['credits']}"
            save_db(db)
            await update.message.reply_text(msg, parse_mode="Markdown")
            try:
                await context.bot.send_message(int(uid), f"💰 Your credits updated! Balance: {db['users'][uid]['credits']}")
            except Exception:
                pass
        
        elif action == "admin_ban":
            uid = text.strip()
            if uid not in db["banned"]:
                db["banned"].append(uid)
                save_db(db)
            await update.message.reply_text(f"🚫 Banned `{uid}`", parse_mode="Markdown")
        
        elif action == "admin_unban":
            uid = text.strip()
            if uid in db["banned"]:
                db["banned"].remove(uid)
                save_db(db)
            await update.message.reply_text(f"✅ Unbanned `{uid}`", parse_mode="Markdown")
        
        elif action == "admin_add_admin":
            uid = text.strip()
            db.setdefault("admins", [])
            if uid not in db["admins"]:
                db["admins"].append(uid)
                save_db(db)
            await update.message.reply_text(f"👑 Added admin `{uid}`", parse_mode="Markdown")
        
        elif action == "admin_rm_admin":
            uid = text.strip()
            if uid in db.get("admins", []):
                db["admins"].remove(uid)
                save_db(db)
            await update.message.reply_text(f"❌ Removed admin `{uid}`", parse_mode="Markdown")
        
        elif action == "admin_create_gw":
            parts = text.split()
            credits, uses = int(parts[0]), int(parts[1])
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            gw = load_giveaways()
            gw[code] = {"credits": credits, "uses": uses, "used": 0, "claimed_by": []}
            save_giveaways(gw)
            await update.message.reply_text(
                f"🎁 *Giveaway Created!*\n\n🎟️ Code: `{code}`\n💰 Credits: {credits}\n🔢 Uses: {uses}\n\n"
                f"Share this code with users. Each code can only be used once per user.",
                parse_mode="Markdown"
            )
        
        elif action == "admin_broadcast":
            success, fail = 0, 0
            for uid in db["users"].keys():
                try:
                    await context.bot.send_message(int(uid), f"📢 *Broadcast*\n\n{text}", parse_mode="Markdown")
                    success += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    fail += 1
            await update.message.reply_text(f"📢 Broadcast sent!\n✅ Success: {success}\n❌ Failed: {fail}")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    
    context.user_data.pop("admin_action", None)


# ==================== SEARCH NUMBER ====================
async def search_number(update: Update, context: ContextTypes.DEFAULT_TYPE, number: str):
    user_id = update.effective_user.id
    user_data = check_and_reset_credits(user_id)
    
    if user_data["credits"] < CREDIT_PER_SEARCH:
        await update.message.reply_text(
            f"❌ *Insufficient Credits!*\n\n"
            f"💰 Your Credits: *{user_data['credits']}*\n"
            f"💳 Required: *{CREDIT_PER_SEARCH}*\n\n"
            f"🔗 Invite friends to earn more credits!",
            parse_mode="Markdown"
        )
        return
    
    msg = await update.message.reply_text("🔍 *Searching... Please wait...*", parse_mode="Markdown")
    
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: requests.get(API_URL.format(number), timeout=20)
        )
        data = response.json()
    except Exception as e:
        await msg.edit_text(f"❌ API Error: {e}")
        return
    
    # Deduct credit
    user_data["credits"] -= CREDIT_PER_SEARCH
    user_data["total_searches"] += 1
    update_user(user_id, user_data)
    
    # Format result
    result = data.get("result", {})
    records = result.get("Main_Records", [])
    
    if not records:
        await msg.edit_text(
            f"❌ *No Data Found* for `{number}`\n\n"
            f"💳 Credits left: *{user_data['credits']}*",
            parse_mode="Markdown"
        )
        return
    
    def val(x):
        return "Not Available" if x is None or x == "" or x == "null" else x
    
    text = f"╔══════════════════════════╗\n   📱 *NUMBER INFO* 📱\n╚══════════════════════════╝\n\n"
    text += f"📞 *Number:* `{number}`\n\n"
    
    for i, rec in enumerate(records, 1):
        if len(records) > 1:
            text += f"━━━ *Record {i}* ━━━\n"
        text += f"👤 *Name:* {val(rec.get('name'))}\n"
        text += f"👨 *Father Name:* {val(rec.get('fname'))}\n"
        text += f"🏠 *Address:* {val(rec.get('address'))}\n"
        text += f"📡 *Circle:* {val(rec.get('circle'))}\n"
        text += f"🆔 *ID:* {val(rec.get('id'))}\n"
        text += f"📧 *Email:* {val(rec.get('email'))}\n"
        text += f"📱 *Alt Number:* {val(rec.get('alt'))}\n\n"
    
    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"💳 *Credits Left:* {user_data['credits']}\n"
    text += f"👑 *Owner:* {OWNER_USERNAME}"
    
    await msg.edit_text(text, parse_mode="Markdown")


# ==================== EXTRA COMMANDS ====================
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Your ID: `{update.effective_user.id}`", parse_mode="Markdown")


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Not authorized!")
        return
    class FakeQuery:
        async def edit_message_text(self, *a, **kw):
            await update.message.reply_text(*a, **kw)
        async def answer(self, *a, **kw): pass
    await admin_panel_view(FakeQuery(), context)


async def add_credits_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick command: /addcredits user_id amount"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Not authorized!")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: `/addcredits user_id amount`", parse_mode="Markdown")
        return
    db = load_db()
    uid, amt = args[0], int(args[1])
    if uid not in db["users"]:
        await update.message.reply_text("❌ User not found!")
        return
    db["users"][uid]["credits"] += amt
    save_db(db)
    await update.message.reply_text(f"✅ Added {amt} credits to `{uid}`\nNew Balance: {db['users'][uid]['credits']}", parse_mode="Markdown")


# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("addcredits", add_credits_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("🤖 Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()