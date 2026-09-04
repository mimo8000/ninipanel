"""
NiniPanel Telegram Bot
 """
import os
import sys
import json
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.models import db, Client, Inbound
from core.config import *
from core.xray_config import generate_config_uri

from flask import Flask

# Flask app for DB access
flask_app = Flask(__name__)
flask_app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(flask_app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ninibot")

ADMIN_IDS = []
if TELEGRAM_ADMIN_ID:
    ADMIN_IDS = [int(x.strip()) for x in TELEGRAM_ADMIN_ID.split(",") if x.strip()]

HELP_TEXT = """
🛡️ **NiniPanel Bot**

**دستورات ادمین:**
/add_client - اضافه کردن کاربر جدید
/list_clients - لیست کاربران
/server_stats - آمار سرور
/gen_config - ساخت کانفیگ

**دستورات کاربران:**
/start - شروع
/help - راهنما
/myconfig - کانفیگ من
/ping - تست پینگ سرور
/sub - لینک سابسکریپشن
"""

def is_admin(uid):
    return uid in ADMIN_IDS

def gen_email():
    chars = string.ascii_lowercase + string.digits
    return "user_" + ''.join(random.choices(chars, k=6))

# ═══════════════════════════════════════
#  HANDLERS
# ═══════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    keyboard = []
    if is_admin(uid):
        keyboard = [
            [InlineKeyboardButton("➕ اضافه کردن کاربر", callback_data="add_client")],
            [InlineKeyboardButton("👥 لیست کاربران", callback_data="list_clients")],
            [InlineKeyboardButton("📊 آمار سرور", callback_data="stats")],
            [InlineKeyboardButton("🔗 ساخت کانفیگ", callback_data="gen_config")],
        ]
    keyboard.append([InlineKeyboardButton("👤 کانفیگ من", callback_data="myconfig")])
    keyboard.append([InlineKeyboardButton("📶 تست پینگ", callback_data="ping")])
    keyboard.append([InlineKeyboardButton("❓ راهنما", callback_data="help")])

    await update.message.reply_text(
        "🛡️ **NiniPanel Bot**\n\nبه پنل مدیریت VPN خوش آمدید!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    if data == "help":
        await q.edit_message_text(HELP_TEXT, parse_mode="Markdown")

    elif data == "stats":
        if not is_admin(uid):
            return await q.edit_message_text("⛔ دسترسی ندارید")
        with flask_app.app_context():
            clients = Client.query.all()
            total = len(clients)
            active = len([c for c in clients if c.enable and not c.is_expired])
            upload = sum(c.upload for c in clients)
            download = sum(c.download for c in clients)
            def fmt(b):
                if b < 1024**2: return f"{b/1024:.1f} KB"
                if b < 1024**3: return f"{b/1024**2:.1f} MB"
                return f"{b/1024**3:.2f} GB"
        text = (
            f"📊 **آمار سرور**\n\n"
            f"👥 کل کاربران: `{total}`\n"
            f"✅ فعال: `{active}`\n"
            f"⬆️ آپلود: `{fmt(upload)}`\n"
            f"⬇️ دانلود: `{fmt(download)}`\n"
        )
        await q.edit_message_text(text, parse_mode="Markdown")

    elif data == "list_clients":
        if not is_admin(uid):
            return await q.edit_message_text("⛔ دسترسی ندارید")
        with flask_app.app_context():
            clients = Client.query.all()
        if not clients:
            return await q.edit_message_text("📭 کاربری نیست")
        text = "👥 **لیست کاربران:**\n\n"
        for i, c in enumerate(clients[:20], 1):
            status = "✅" if (c.enable and not c.is_expired) else "❌"
            text += f"{i}. {status} `{c.email}` | {c.protocol} | {c.traffic_display}\n"
        if len(clients) > 20:
            text += f"\n... و {len(clients)-20} کاربر دیگر"
        await q.edit_message_text(text, parse_mode="Markdown")

    elif data == "myconfig":
        with flask_app.app_context():
            # Find client by telegram_id
            client = Client.query.filter_by(telegram_id=str(uid)).first()
        if not client:
            return await q.edit_message_text(
                "❌ کانفیگی برای شما یافت نشد.\n\n"
                "برای دریافت کانفیگ با ادمین تماس بگیرید."
            )
        link = generate_config_uri(
            protocol=client.protocol, server="YOUR_SERVER",
            port=443, uuid_str=client.uuid, email=client.email,
            flow=client.flow
        )
        text = (
            f"🔗 **کانفیگ شما**\n\n"
            f"📧 ایمیل: `{client.email}`\n"
            f"🔌 پروتکل: `{client.protocol}`\n"
            f"📊 ترافیک: `{client.traffic_display}`\n"
            f"⏰ انقضا: `{client.expiry_display}`\n\n"
            f"📎 لینک اتصال:\n`{link}`\n\n"
            f"📋 لینک سابسکریپشن:\n`{SUB_BASE_URL}/sub/{client.uuid}`"
        )
        await q.edit_message_text(text, parse_mode="Markdown")

    elif data == "ping":
        msg = await q.edit_message_text("📶 تست پینگ...")
        import subprocess
        try:
            result = subprocess.run(
                ["ping", "-c", "4", "8.8.8.8"],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split("\n")
            ping_lines = [l for l in lines if "time=" in l]
            if ping_lines:
                times = [float(l.split("time=")[1].split(" ")[0]) for l in ping_lines]
                avg = sum(times) / len(times)
                text = (
                    f"📶 **نتیجه پینگ**\n\n"
                    f"ping: `{avg:.1f} ms`\n"
                    f"min: `{min(times):.1f} ms`\n"
                    f"max: `{max(times):.1f} ms`\n"
                    f"packet loss: `{4 - len(times)}/4`"
                )
            else:
                text = "❌ پینگ ناموفق بود"
        except Exception as e:
            text = f"❌ خطا: {e}"
        await q.edit_message_text(text, parse_mode="Markdown")

    elif data == "add_client":
        if not is_admin(uid):
            return await q.edit_message_text("⛔ دسترسی ندارید")
        with flask_app.app_context():
            email = gen_email()
            inbound = Inbound.query.first()
            if not inbound:
                return await q.edit_message_text("❌ هیچ Inbound ای تعریف نشده")
            client = Client(
                email=email,
                protocol=inbound.protocol,
                inbound_tag=inbound.tag,
                telegram_id="",
                expiry_time=int((datetime.utcnow() + timedelta(days=30)).timestamp()),
            )
            db.session.add(client)
            db.session.commit()
            link = generate_config_uri(
                protocol=client.protocol, server="YOUR_SERVER",
                port=443, uuid_str=client.uuid, email=client.email
            )
        text = (
            f"✅ **کاربر جدید ایجاد شد!**\n\n"
            f"📧 ایمیل: `{email}`\n"
            f"🔑 UUID: `{client.uuid}`\n"
            f"🔌 پروتکل: `{client.protocol}`\n"
            f"⏰ انقضا: ۳۰ روز\n\n"
            f"📎 لینک اتصال:\n`{link}`\n\n"
            f"📋 سابسکریپشن:\n`{SUB_BASE_URL}/sub/{client.uuid}`"
        )
        kb = [[InlineKeyboardButton("📋 کپی لینک", callback_data=f"copy_{client.uuid}")]]
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("copy_"):
        token = data[5:]
        await q.edit_message_text(f"📋 `{SUB_BASE_URL}/sub/{token}`", parse_mode="Markdown")


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ دسترسی ندارید")
    with flask_app.app_context():
        email = gen_email()
        inbound = Inbound.query.first()
        client = Client(
            email=email,
            protocol=inbound.protocol if inbound else "vless",
            inbound_tag=inbound.tag if inbound else "vless-ws",
            expiry_time=int((datetime.utcnow() + timedelta(days=30)).timestamp()),
        )
        db.session.add(client)
        db.session.commit()
    await update.message.reply_text(
        f"✅ کاربر `{email}` ایجاد شد\n"
        f"UUID: `{client.uuid}`\n"
        f"ساب: `{SUB_BASE_URL}/sub/{client.uuid}`",
        parse_mode="Markdown"
    )

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ دسترسی ندارید")
    with flask_app.app_context():
        clients = Client.query.all()
    if not clients:
        return await update.message.reply_text("📭 خالی")
    text = "👥 کاربران:\n\n"
    for i, c in enumerate(clients[:30], 1):
        s = "✅" if (c.enable and not c.is_expired) else "❌"
        text += f"{i}. {s} {c.email} | {c.protocol}\n"
    await update.message.reply_text(text)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔")
    with flask_app.app_context():
        clients = Client.query.all()
    total = len(clients)
    active = len([c for c in clients if c.enable and not c.is_expired])
    await update.message.reply_text(f"📊 کل: {total} | فعال: {active}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("add_client", cmd_add))
    app.add_handler(CommandHandler("list_clients", cmd_list))
    app.add_handler(CommandHandler("server_stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(cb_handler))

    print("🤖 NiniPanel Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
