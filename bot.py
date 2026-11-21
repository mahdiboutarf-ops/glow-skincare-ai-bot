import os
import random
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai

# Read API keys safely from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Please set TELEGRAM_TOKEN and GEMINI_API_KEY environment variables.")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

PRODUCTS = {
    "p1": {"name": "Hydrating Face Serum", "price": 29, "desc": "Vitamin C + Hyaluronic Acid (30ml)"},
    "p2": {"name": "SPF 50 Daily Sunscreen", "price": 22, "desc": "Lightweight, non-greasy formula (50ml)"},
    "p3": {"name": "Night Repair Cream", "price": 35, "desc": "Deep moisture & retinol complex (50ml)"},
}

STORE_INFO = (
    "You are a helpful, concise customer support assistant for Glow Skincare online store. "
    "Products: Hydrating Face Serum ($29, Vitamin C + Hyaluronic Acid 30ml), "
    "SPF 50 Daily Sunscreen ($22, lightweight non-greasy 50ml), "
    "Night Repair Cream ($35, deep moisture & retinol 50ml). "
    "Shipping: 3-5 business days worldwide, free over $50. Payments: Card or USDT. "
    "Reply in a friendly, short, professional tone without using markdown asterisks."
)


def init_db():
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS orders ("
        "order_id TEXT PRIMARY KEY, customer TEXT, product TEXT, "
        "price INTEGER, status TEXT, tracking TEXT)"
    )
    conn.commit()
    conn.close()


def main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛍️ View Products", callback_data="products"))
    markup.add(InlineKeyboardButton("📦 Track My Order", callback_data="track"))
    return markup


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Welcome to *Glow Skincare*!\n"
        "Use the buttons below to browse & order, or ask any question and our AI assistant will reply instantly.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    bot.answer_callback_query(call.id)

    if call.data == "products":
        markup = InlineKeyboardMarkup()
        text = "🛍️ *Our Products:*\n\n"
        for pid, p in PRODUCTS.items():
            name, price, desc = p["name"], p["price"], p["desc"]
            text += f"• *{name}* — ${price}\n  _{desc}_\n\n"
            markup.add(InlineKeyboardButton(f"Order {name} (${price})", callback_data=f"buy_{pid}"))
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("buy_"):
        pid = call.data.split("_")[1]
        p = PRODUCTS[pid]
        name, price = p["name"], p["price"]
        order_id = f"ORD-{random.randint(1000, 9999)}"
        tracking = f"TRK-{random.randint(100000, 999999)}"
        customer = call.from_user.first_name or "Customer"

        conn = sqlite3.connect("orders.db")
        c = conn.cursor()
        c.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, customer, name, price, "Confirmed & Processing", tracking),
        )
        conn.commit()
        conn.close()

        msg_text = (
            f"✅ *Order Confirmed!*\n\n"
            f"🆔 Order ID: `{order_id}`\n"
            f"📦 Product: {name} (${price})\n"
            f"🚚 Tracking Number: `{tracking}`\n\n"
            f"Use the Track button anytime to check your order status."
        )
        bot.send_message(call.message.chat.id, msg_text, parse_mode="Markdown", reply_markup=main_menu())

    elif call.data == "track":
        msg = bot.send_message(
            call.message.chat.id,
            "🔎 Enter your Order ID (e.g., `ORD-1234`):",
            parse_mode="Markdown",
        )
        bot.register_next_step_handler(msg, check_order)


def check_order(message):
    if not message.text:
        return
    order_id = message.text.strip().upper()
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("SELECT product, status, tracking FROM orders WHERE order_id = ?", (order_id,))
    row = c.fetchone()
    conn.close()

    if row:
        details = (
            f"📦 *Order Details ({order_id})*\n"
            f"• Product: {row[0]}\n"
            f"• Status: {row[1]}\n"
            f"• Tracking: `{row[2]}`"
        )
        bot.send_message(message.chat.id, details, parse_mode="Markdown", reply_markup=main_menu())
    else:
        bot.send_message(
            message.chat.id,
            "❌ Order ID not found. Please check and try again.",
            reply_markup=main_menu(),
        )


@bot.message_handler(func=lambda message: True)
def ai_reply(message):
    try:
        response = ai_client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=f"{STORE_INFO}\n\nCustomer question: {message.text}",
        )
        bot.reply_to(message, response.text)
    except Exception as e:
        print("AI Error:", e)
        bot.reply_to(message, "Sorry, I could not process that right now. Try using the menu buttons!")


import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


def keep_alive():
    port = int(os.getenv("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


if __name__ == "__main__":
    init_db()
    threading.Thread(target=keep_alive, daemon=True).start()
    print("Bot is running...")
    bot.infinity_polling()
