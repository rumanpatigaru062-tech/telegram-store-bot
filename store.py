import os
import sqlite3
from datetime import datetime
import telebot
from telebot import types

# ---------------------------------------------------------------------------
# CONFIGURATION & RAILWAY PERSISTENT DATABASE SETUP
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8905156053:AAGg9iaD3jOBC9hAzmviD-Voy4I6TiMvm5A")
ADMINS = [8168424848]  # Replace with your numeric Telegram User ID

BINANCE_PAY_ID = ""      # Replace with your Binance Pay ID / USDT Address
GPAY_PAYMENT_INFO = "patigarooruman@okaxis"   # Replace with your UPI ID or GPay phone number

# Railway Persistent Volume database path check
DB_DIR = "/app/data" if os.environ.get("RAILWAY_ENVIRONMENT") else "."
DB_PATH = os.path.join(DB_DIR, "marko_cpm.db")

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

def escape_md(text):
    """Escapes special characters so Telegram Markdown parsing never breaks."""
    if not text:
        return ""
    s = str(text)
    for char in ['_', '*', '`', '[']:
        s = s.replace(char, f'\\{char}')
    return s

# ---------------------------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------------------------
def get_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, joined_date TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS garage_cars (car_id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT NOT NULL, owner TEXT NOT NULL, price_stars INTEGER NOT NULL, price_binance REAL NOT NULL, price_gpay REAL NOT NULL, photo_file_id TEXT NOT NULL, date_added TEXT, time_added TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (review_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT, rating INTEGER NOT NULL, comment TEXT NOT NULL, date_added TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stock_metadata (product_type TEXT PRIMARY KEY, last_restock_date TEXT, last_restock_time TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS coupons (code TEXT PRIMARY KEY, discount_percent REAL NOT NULL, max_uses INTEGER NOT NULL, current_uses INTEGER DEFAULT 0)''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER NOT NULL, 
            item_type TEXT NOT NULL, 
            item_id INTEGER NOT NULL, 
            payment_method TEXT NOT NULL, 
            status TEXT DEFAULT 'PENDING', 
            proof_file_id TEXT, 
            timestamp TEXT,
            quantity INTEGER DEFAULT 1,
            coupon_code TEXT,
            injection_details TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            category_id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            price_stars INTEGER,
            price_binance REAL,
            price_gpay REAL,
            cat_type TEXT DEFAULT 'account'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bulk_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id TEXT,
            credentials TEXT,
            is_sold INTEGER DEFAULT 0
        )
    ''')

    # Schema migrations for existing databases
    try: cursor.execute("ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE orders ADD COLUMN coupon_code TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE orders ADD COLUMN injection_details TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE categories ADD COLUMN cat_type TEXT DEFAULT 'account'")
    except sqlite3.OperationalError: pass

    default_cats = [
        ("cpm3", "CPM 2 Accounts", "High quality CPM2 accounts with premium cars.", 500, 5.0, 450.0, "account"),
        ("cpm2_random", "CPM 2: Random Cars", "Accounts packed with random premium cars.", 600, 6.0, 500.0, "account"),
        ("cpm2_12k", "CPM 2: 12k Coins", "Accounts pre-loaded with 12,000 Coins.", 800, 8.0, 700.0, "account")
    ]
    for cat in default_cats:
        cursor.execute("INSERT OR IGNORE INTO categories (category_id, title, description, price_stars, price_binance, price_gpay, cat_type) VALUES (?, ?, ?, ?, ?, ?, ?)", cat)
    
    conn.commit()
    conn.close()

init_db()

def register_user(user_id, username):
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username, joined_date) VALUES (?, ?, ?)", 
                   (user_id, username or "Unknown", today))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else None

def set_setting(key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def is_service(cat_id):
    if not cat_id or cat_id.startswith("car_"):
        return False
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT cat_type FROM categories WHERE category_id = ?", (cat_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row['cat_type']:
        return row['cat_type'] == "service"
    return "injection" in cat_id.lower()

# ---------------------------------------------------------------------------
# MAIN MENU
# ---------------------------------------------------------------------------
def send_main_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("ð MARKO CPM Garage", callback_data="view_garage"),
        types.InlineKeyboardButton("ð CPM Accounts & Services", callback_data="view_accounts"),
        types.InlineKeyboardButton("ð¤ My Profile", callback_data="view_profile"),
        types.InlineKeyboardButton("â­ Customer Reviews", callback_data="view_reviews"),
        types.InlineKeyboardButton("âï¸ Leave a Review", callback_data="add_review"),
        types.InlineKeyboardButton("ð¬ Support / Tickets", callback_data="support_menu")
    )
    text = "ð¥ *Welcome to MARKO CPM Store!* ð¥\n\nYour official shop for custom Car Parking Multiplayer (CPM) cars, pre-made accounts, and premium services.\n\nSelect an option below:"
    
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start_command(message):
    register_user(message.from_user.id, message.from_user.username)
    send_main_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def main_menu_callback(call):
    send_main_menu(call.message.chat.id, call.message.message_id)

# ---------------------------------------------------------------------------
# USER PROFILE & SUPPORT
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data == "view_profile")
def view_profile(call):
    user_id = call.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'APPROVED'", (user_id,))
    completed_orders = cursor.fetchone()[0]
    conn.close()

    name = escape_md(call.from_user.first_name)
    username = f"@{escape_md(call.from_user.username)}" if call.from_user.username else "No Username"

    text = (f"ð¤ *MY PROFILE*\n\n"
            f"ð *Name:* {name}\n"
            f"ð *Username:* {username}\n"
            f"ð *User ID:* `{user_id}`\n\n"
            f"ð¦ *Total Orders Placed:* {total_orders}\n"
            f"â *Orders Completed:* {completed_orders}")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("ð View Previous Orders", callback_data="my_orders"),
        types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "my_orders")
def my_orders(call):
    user_id = call.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT order_id, item_type, status, timestamp, quantity FROM orders WHERE user_id = ? ORDER BY order_id DESC LIMIT 10", (user_id,))
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        text = "ð *Your Orders*\n\nYou haven't placed any orders yet."
    else:
        text = "ð *Your Last 10 Orders*\n\n"
        for o in orders:
            status_emoji = "â" if o['status'] == 'APPROVED' else "â" if o['status'] == 'REJECTED' else "â³"
            item_display = escape_md(o['item_type'].replace('_', ' ').upper())
            qty_str = f" (x{o['quantity']})" if o['quantity'] > 1 else ""
            text += f"*{status_emoji} Order #{o['order_id']}* | {item_display}{qty_str}\nð {o['timestamp']}\n\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("ð Back to Profile", callback_data="view_profile"),
        types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "support_menu")
def support_menu(call):
    text = "ð¬ *SUPPORT & TICKETS*\n\nIf you have a faulty order or need admin assistance, open a ticket below.\n\nð¨âð» *Direct Admin Contact:* @markocpm"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("ð« Open a Ticket", callback_data="open_ticket"),
        types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "open_ticket")
def open_ticket(call):
    msg = bot.send_message(call.message.chat.id, "ð« Please type your issue in a single message (include Order ID if applicable):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_ticket)

def process_ticket(message):
    user_info = f"{escape_md(message.from_user.first_name)} (@{escape_md(message.from_user.username)})" if message.from_user.username else escape_md(message.from_user.first_name)
    ticket_text = f"ð¨ *NEW SUPPORT TICKET*\n\nð¤ *From:* {user_info}\nð *User ID:* `{message.from_user.id}`\n\nð¬ *Issue:* {escape_md(message.text)}"
    
    for admin in ADMINS:
        try: bot.send_message(admin, ticket_text, parse_mode="Markdown")
        except Exception: pass
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu"))
    bot.send_message(message.chat.id, "â *Ticket Submitted!* @markocpm will review it and contact you shortly.", parse_mode="Markdown", reply_markup=markup)

# ---------------------------------------------------------------------------
# CATALOG & SELECTION (GARAGE & DYNAMIC ACCOUNTS/SERVICES)
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data == "view_garage")
def view_garage(call):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM garage_cars ORDER BY car_id DESC")
    cars = cursor.fetchall()
    cursor.execute("SELECT * FROM stock_metadata WHERE product_type = 'GARAGE'")
    meta = cursor.fetchone()
    conn.close()

    if not cars:
        bot.answer_callback_query(call.id, "No cars available in Marko CPM Garage right now!")
        return

    restock_info = f"ð *Last Restock:* {meta['last_restock_date']} at {meta['last_restock_time']}\n\n" if meta else ""
    back_markup = types.InlineKeyboardMarkup()
    back_markup.add(types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu"))
    bot.send_message(call.message.chat.id, f"ð *MARKO CPM GARAGE CATALOG*\n{restock_info}Browse available builds below:", parse_mode="Markdown", reply_markup=back_markup)

    for car in cars:
        caption = (f"ð *Car ID:* #{car['car_id']}\nð *Model:* {escape_md(car['brand'])}\nð *Owner/Designer:* {escape_md(car['owner'])}\n\nð³ *PRICING & PAYMENT OPTIONS:*\nâ­ *Telegram Stars:* {car['price_stars']} Stars\nð¡ *Binance Pay:* ${car['price_binance']:.2f} USDT\nð± *Google Pay:* {car['price_gpay']:.2f}\n\nð *Added:* {car['date_added']} ({car['time_added']})")
        buy_markup = types.InlineKeyboardMarkup()
        btn_buy = types.InlineKeyboardButton(f"ð Buy Car #{car['car_id']}", callback_data=f"buy_car:{car['car_id']}")
        buy_markup.add(btn_buy)
        try: bot.send_photo(call.message.chat.id, car['photo_file_id'], caption=caption, parse_mode="Markdown", reply_markup=buy_markup)
        except Exception: bot.send_message(call.message.chat.id, caption, parse_mode="Markdown", reply_markup=buy_markup)

@bot.callback_query_handler(func=lambda call: call.data == "view_accounts")
def view_accounts(call):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT category_id, title, cat_type FROM categories")
    categories = cursor.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        prefix = "ð " if cat['cat_type'] == "service" else "ð®"
        markup.add(types.InlineKeyboardButton(f"{prefix} {cat['title']}", callback_data=f"cat_{cat['category_id']}"))
    
    markup.add(types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu"))
    bot.edit_message_text("ð *CPM ACCOUNTS & SERVICES*\n\nSelect an option below to browse prices and stock:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def view_category(call):
    cat_id = call.data.replace("cat_", "")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories WHERE category_id = ?", (cat_id,))
    cat = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM bulk_accounts WHERE category_id = ? AND is_sold = 0", (cat_id,))
    stock = cursor.fetchone()[0]
    conn.close()

    if not cat: return

    is_serv = is_service(cat_id)
    text = f"ð¦ *{escape_md(cat['title'])}*\n\nð {escape_md(cat['description'])}\n\n"
    
    if not is_serv:
        text += f"ð *In Stock:* {stock} available\n\n"
    
    text += (f"ð³ *PRICING (PER UNIT/SERVICE):*\n"
             f"â­ *Telegram Stars:* {cat['price_stars']} Stars\n"
             f"ð¡ *Binance Pay:* ${cat['price_binance']:.2f} USDT\n"
             f"ð± *Google Pay:* {cat['price_gpay']:.2f}")

    markup = types.InlineKeyboardMarkup(row_width=1)
    if is_serv or stock > 0:
        markup.add(types.InlineKeyboardButton("ð Buy Now", callback_data=f"start_buy:{cat_id}"))
    else:
        markup.add(types.InlineKeyboardButton("â Out of Stock", callback_data="out_of_stock"))
        
    markup.add(types.InlineKeyboardButton("â¬ï¸ Back to Categories", callback_data="view_accounts"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

# ---------------------------------------------------------------------------
# SINGLE VS BULK ACCOUNTS & QUANTITY SELECTION
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("start_buy:"))
def start_buy_selection(call):
    cat_id = call.data.replace("start_buy:", "")
    
    if is_service(cat_id):
        show_coupon_prompt(call.message.chat.id, cat_id, qty=1, message_id=call.message.message_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("1ï¸â£ Single Account", callback_data=f"qty_set:{cat_id}:1"),
        types.InlineKeyboardButton("ð¦ Bulk Accounts (2-100)", callback_data=f"qty_bulk:{cat_id}")
    )
    markup.add(types.InlineKeyboardButton("ð Cancel", callback_data="main_menu"))
    
    bot.edit_message_text("ð *Select Purchase Type:*\n\nWould you like to buy a single account or multiple accounts in bulk?", 
                           call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("qty_bulk:"))
def ask_bulk_quantity(call):
    cat_id = call.data.replace("qty_bulk:", "")
    msg = bot.send_message(call.message.chat.id, "ð¦ *How many accounts do you need?*\n\nPlease reply with a number between **2** and **100**:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_bulk_quantity_input, cat_id)

def process_bulk_quantity_input(message, cat_id):
    try:
        qty = int(message.text.strip())
        if qty < 2 or qty > 100: raise ValueError
    except ValueError:
        msg = bot.send_message(message.chat.id, "â Invalid number. Please reply with a valid number between **2 and 100**:")
        bot.register_next_step_handler(msg, process_bulk_quantity_input, cat_id)
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM bulk_accounts WHERE category_id = ? AND is_sold = 0", (cat_id,))
    stock = cursor.fetchone()[0]
    conn.close()

    if qty > stock:
        bot.send_message(message.chat.id, f"â *Insufficient Stock!*\nOnly `{stock}` accounts are currently in stock for this category. Please re-enter a smaller quantity.", parse_mode="Markdown")
        ask_bulk_quantity_direct(message.chat.id, cat_id)
        return

    show_coupon_prompt(message.chat.id, cat_id, qty)

def ask_bulk_quantity_direct(chat_id, cat_id):
    msg = bot.send_message(chat_id, "ð¦ *Enter desired bulk quantity (2-100):*", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_bulk_quantity_input, cat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("qty_set:"))
def set_single_quantity(call):
    parts = call.data.split(":")
    cat_id = parts[1]
    qty = int(parts[2])
    show_coupon_prompt(call.message.chat.id, cat_id, qty, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_car:"))
def buy_garage_car(call):
    car_id = call.data.replace("buy_car:", "")
    show_coupon_prompt(call.message.chat.id, f"car_{car_id}", qty=1)

# ---------------------------------------------------------------------------
# COUPON SYSTEM & PRICING SUMMARY
# ---------------------------------------------------------------------------
def show_coupon_prompt(chat_id, item_key, qty=1, applied_code=None, discount_pct=0, message_id=None):
    conn = get_db()
    cursor = conn.cursor()
    
    if item_key.startswith("car_"):
        car_id = item_key.replace("car_", "")
        cursor.execute("SELECT * FROM garage_cars WHERE car_id = ?", (car_id,))
        item = cursor.fetchone()
        title = item['brand'] if item else "Garage Car"
        raw_stars, raw_binance, raw_gpay = item['price_stars'], item['price_binance'], item['price_gpay']
    else:
        cursor.execute("SELECT * FROM categories WHERE category_id = ?", (item_key,))
        item = cursor.fetchone()
        title = item['title'] if item else "Account"
        raw_stars, raw_binance, raw_gpay = item['price_stars'], item['price_binance'], item['price_gpay']
    conn.close()

    multiplier = (1 - (discount_pct / 100.0))
    tot_stars = int(raw_stars * qty * multiplier)
    tot_binance = round(raw_binance * qty * multiplier, 2)
    tot_gpay = round(raw_gpay * qty * multiplier, 2)

    code_str = applied_code or "NONE"
    
    text = (f"ð *ORDER SUMMARY*\n\n"
            f"ð¦ *Item:* {escape_md(title)}\n"
            f"ð¢ *Quantity:* {qty}\n")
    
    if applied_code:
        text += f"ð *Coupon Applied:* `{applied_code}` ({discount_pct}% OFF)\n\n"
    else:
        text += "\n"

    text += (f"ð° *TOTAL PRICING:*\n"
             f"â­ *Telegram Stars:* {tot_stars} Stars\n"
             f"ð¡ *Binance Pay:* ${tot_binance:.2f} USDT\n"
             f"ð± *Google Pay:* {tot_gpay:.2f}")

    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if not applied_code:
        markup.add(types.InlineKeyboardButton("ð Do you have a coupon code?", callback_data=f"use_coupon:{item_key}:{qty}"))
    
    markup.add(types.InlineKeyboardButton("ð³ Continue to Payment", callback_data=f"checkout:{item_key}:{qty}:{code_str}"))
    markup.add(types.InlineKeyboardButton("â Cancel Order", callback_data="main_menu"))

    if message_id:
        try: bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("use_coupon:"))
def prompt_coupon_code(call):
    parts = call.data.split(":")
    item_key = parts[1]
    qty = parts[2]
    
    msg = bot.send_message(call.message.chat.id, "ð *Please enter your coupon code:*", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_coupon_verification, item_key, qty)

def process_coupon_verification(message, item_key, qty):
    code_entered = message.text.strip().upper()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM coupons WHERE code = ?", (code_entered,))
    coupon = cursor.fetchone()
    conn.close()

    if not coupon or coupon['current_uses'] >= coupon['max_uses']:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("ð Try Code Again", callback_data=f"use_coupon:{item_key}:{qty}"),
            types.InlineKeyboardButton("ð³ Proceed without Coupon", callback_data=f"checkout:{item_key}:{qty}:NONE")
        )
        bot.send_message(message.chat.id, "â *Invalid or Expired Coupon Code!*", parse_mode="Markdown", reply_markup=markup)
    else:
        discount = coupon['discount_percent']
        bot.send_message(message.chat.id, f"ð *Coupon Applied!* You saved **{discount}%** on your order.", parse_mode="Markdown")
        show_coupon_prompt(message.chat.id, item_key, int(qty), applied_code=code_entered, discount_pct=discount)

# ---------------------------------------------------------------------------
# PAYMENT SELECTION & PROOF SUBMISSION
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("checkout:"))
def checkout_payment_selection(call):
    parts = call.data.split(":")
    item_key = parts[1]
    qty = int(parts[2])
    coupon_code = parts[3]

    discount_pct = 0
    if coupon_code != "NONE":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT discount_percent FROM coupons WHERE code = ?", (coupon_code,))
        row = cursor.fetchone()
        conn.close()
        if row: discount_pct = row['discount_percent']

    if item_key.startswith("car_"):
        car_id = item_key.replace("car_", "")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM garage_cars WHERE car_id = ?", (car_id,))
        item = cursor.fetchone()
        conn.close()
        title = item['brand']
        stars, binance, gpay = item['price_stars'], item['price_binance'], item['price_gpay']
        item_type = "car"
        item_id = car_id
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE category_id = ?", (item_key,))
        item = cursor.fetchone()
        conn.close()
        title = item['title']
        stars, binance, gpay = item['price_stars'], item['price_binance'], item['price_gpay']
        item_type = item_key
        item_id = 0

    multiplier = (1 - (discount_pct / 100.0))
    tot_stars = int(stars * qty * multiplier)
    tot_binance = round(binance * qty * multiplier, 2)
    tot_gpay = round(gpay * qty * multiplier, 2)

    payment_markup = types.InlineKeyboardMarkup(row_width=1)
    payment_markup.add(
        types.InlineKeyboardButton(f"â­ Pay with Telegram Stars ({tot_stars} Stars)", callback_data=f"pay:stars:{item_type}:{item_id}:{qty}:{coupon_code}"),
        types.InlineKeyboardButton(f"ð¡ Pay via Binance (${tot_binance:.2f} USDT)", callback_data=f"pay:binance:{item_type}:{item_id}:{qty}:{coupon_code}"),
        types.InlineKeyboardButton(f"ð± Pay via Google Pay ({tot_gpay:.2f})", callback_data=f"pay:gpay:{item_type}:{item_id}:{qty}:{coupon_code}"),
        types.InlineKeyboardButton("ð Cancel", callback_data="main_menu")
    )

    bot.send_message(call.message.chat.id, f"ð³ *Select Payment Method for {escape_md(title)} (x{qty}):*", parse_mode="Markdown", reply_markup=payment_markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay:"))
def process_payment_option(call):
    parts = call.data.split(":")
    method = parts[1]       
    item_type = parts[2]    
    item_id = parts[3]      
    qty = int(parts[4])
    coupon_code = parts[5]

    user_id = call.from_user.id

    if method == "stars":
        bot.send_message(call.message.chat.id, f"â­ *Telegram Stars Payment*\n\nTo pay with Stars, please contact @markocpm directly with Item ID `#{escape_md(item_type.upper())}-{item_id}`.", parse_mode="Markdown")
        return

    pay_name = "Binance Pay" if method == "binance" else "Google Pay"
    user_states[f"pay_{user_id}"] = {
        "item_type": item_type, 
        "item_id": item_id, 
        "quantity": qty, 
        "coupon_code": coupon_code, 
        "method": pay_name
    }

    text_suffix = "\n\nð After sending payment, reply to this message with a **screenshot/photo of your payment receipt**."

    if method == "gpay":
        qr_file_id = get_setting("gpay_qr_file_id")
        text = f"ð± *Google Pay Payment*\n\nScan the QR code above or send payment to UPI ID: `{GPAY_PAYMENT_INFO}`" + text_suffix
        if qr_file_id:
            try: msg = bot.send_photo(call.message.chat.id, qr_file_id, caption=text, parse_mode="Markdown")
            except Exception: msg = bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        else:
            msg = bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    else:
        text = f"ð¡ *Binance Pay Instructions*\n\nSend payment to Binance Pay ID: `{BINANCE_PAY_ID}`" + text_suffix
        msg = bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    bot.register_next_step_handler(msg, process_payment_proof)

def process_payment_proof(message):
    user_id = message.from_user.id
    pay_data = user_states.get(f"pay_{user_id}")
    if not pay_data:
        bot.reply_to(message, "â Order session expired. Please start over from the main menu.")
        return

    pay_data["proof_message_id"] = message.message_id

    if is_service(pay_data["item_type"]):
        msg = bot.send_message(message.chat.id, "â Payment proof received.\n\nð© **Now, please reply with your Account ID / Gmail and Password for this service.**\n\nFormat: `Gmail:Password`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_injection_credentials)
    else:
        finalize_order(message, user_id, pay_data)

def process_injection_credentials(message):
    user_id = message.from_user.id
    pay_data = user_states.get(f"pay_{user_id}")
    if not pay_data: return
    
    pay_data["credentials"] = message.text.strip()
    bot.send_message(message.chat.id, "â³ *Request Submitted!*\n\nYour account details have been securely sent to the admin. **Estimated waiting time: 10 minutes.** Please do not log into the game during this time.", parse_mode="Markdown")
    finalize_order(message, user_id, pay_data, notify_user=False)

def finalize_order(message, user_id, pay_data, notify_user=True):
    register_user(user_id, message.from_user.username)
    d_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    creds = pay_data.get("credentials", "")
    proof_msg_id = pay_data.get("proof_message_id", message.message_id)
    coupon_str = None if pay_data["coupon_code"] == "NONE" else pay_data["coupon_code"]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, item_type, item_id, payment_method, proof_file_id, timestamp, quantity, coupon_code, injection_details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, pay_data["item_type"], pay_data["item_id"], pay_data["method"], str(proof_msg_id), d_str, pay_data["quantity"], coupon_str, creds)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    user_states.pop(f"pay_{user_id}", None)

    if notify_user:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu"))
        bot.send_message(message.chat.id, f"â *Order #{order_id} Submitted!*\nOur admins (@markocpm) are verifying your payment and will deliver your item shortly.", parse_mode="Markdown", reply_markup=markup)

    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(
        types.InlineKeyboardButton("â Approve & Deliver", callback_data=f"order_approve_{order_id}"),
        types.InlineKeyboardButton("â Reject", callback_data=f"order_reject_{order_id}")
    )

    clean_first_name = escape_md(message.from_user.first_name or "Customer")
    raw_username = message.from_user.username
    username_str = f"@{escape_md(raw_username)}" if raw_username else "No Username"
    clean_item = escape_md(pay_data['item_type'].replace('_', ' ').upper())

    admin_text = (f"ð¨ *NEW ORDER #{order_id}*\n\n"
                  f"ð¤ *Customer:* {clean_first_name}\n"
                  f"ð *Username:* {username_str}\n"
                  f"ð *User ID:* `{user_id}`\n"
                  f"ð¦ *Item:* {clean_item} (x{pay_data['quantity']})\n"
                  f"ð *Coupon:* `{coupon_str or 'None'}`\n"
                  f"ð³ *Method:* {escape_md(pay_data['method'])}\n"
                  f"ð *Time:* {d_str}")
    
    if creds: admin_text += f"\n\nð *SERVICE / INJECTION CREDENTIALS:*\n`{escape_md(creds)}`"

    for admin_id in ADMINS:
        try:
            bot.forward_message(admin_id, message.chat.id, proof_msg_id)
            bot.send_message(admin_id, admin_text, parse_mode="Markdown", reply_markup=admin_markup)
        except Exception as e: print(f"Admin Notify Error: {e}")

# ---------------------------------------------------------------------------
# ADMIN CONTROL PANEL & DYNAMIC CATEGORY CREATOR
# ---------------------------------------------------------------------------
@bot.message_handler(commands=['admin'])
def admin_panel_cmd(message):
    if message.from_user.id not in ADMINS: return
    send_admin_panel(message.chat.id, message.message_id, edit=False)

def send_admin_panel(chat_id, message_id=None, edit=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("â Add New Service/Category", callback_data="adm_addcategory"),
        types.InlineKeyboardButton("â³ Pending Orders", callback_data="adm_orders"),
        types.InlineKeyboardButton("ð Order History", callback_data="adm_allorders"),
        types.InlineKeyboardButton("ð Manage Reviews", callback_data="adm_delreviews"),
        types.InlineKeyboardButton("ð· Edit Prices", callback_data="adm_editprices"),
        types.InlineKeyboardButton("ð Coupons", callback_data="adm_coupons"),
        types.InlineKeyboardButton("ð¦ Check Stock", callback_data="adm_stock"),
        types.InlineKeyboardButton("â Restock Accounts", callback_data="adm_addstock"),
        types.InlineKeyboardButton("ð Add Garage Car", callback_data="adm_addcar"),
        types.InlineKeyboardButton("ð¼ Update GPay QR", callback_data="adm_updateqr"),
        types.InlineKeyboardButton("ð¢ Broadcast", callback_data="adm_broadcast")
    )
    text = "ð  *MARKO CPM ADMIN CONTROL PANEL*\n\nSelect a tool or menu below:"
    if edit and message_id:
        try: bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_panel_callbacks(call):
    if call.from_user.id not in ADMINS: return
    action = call.data.replace("adm_", "")
    
    if action == "addcategory":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("ð Account", callback_data="addcat_type:account"),
            types.InlineKeyboardButton("ð  Service / Injection", callback_data="addcat_type:service")
        )
        bot.edit_message_text("â *CREATE NEW CATEGORY/SERVICE*\n\nSelect the type of item you want to add:", 
                               call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    # ð¢ FEATURE 1: VIEW ALL PREVIOUS ORDERS WITH USER DETAILS & TIMESTAMP
    elif action.startswith("allorders"):
        page = 0
        if ":" in action:
            try: page = int(action.split(":")[1])
            except ValueError: page = 0

        limit = 5
        offset = page * limit

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.order_id, o.user_id, u.username, o.item_type, o.quantity, o.payment_method, o.status, o.timestamp 
            FROM orders o 
            LEFT JOIN users u ON o.user_id = u.user_id 
            ORDER BY o.order_id DESC LIMIT ? OFFSET ?
        """, (limit, offset))
        orders = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders = cursor.fetchone()[0]
        conn.close()

        if not orders:
            bot.answer_callback_query(call.id, "No orders found in database!")
            return

        text = f"ð *ALL ORDERS HISTORY (Page {page + 1})*\nð Total Orders: {total_orders}\n\n"
        for o in orders:
            status_emoji = "â Approved" if o['status'] == 'APPROVED' else "â Rejected" if o['status'] == 'REJECTED' else "â³ Pending"
            username = f"@{escape_md(o['username'])}" if o['username'] and o['username'] != "Unknown" else "No Username"
            item_name = escape_md(o['item_type'].replace('_', ' ').upper())

            text += (f"ð¦ *Order #{o['order_id']}* | {status_emoji}\n"
                     f"ð¤ *Buyer:* {username} (`{o['user_id']}`)\n"
                     f"ð *Item:* {item_name} (x{o['quantity']})\n"
                     f"ð³ *Method:* {escape_md(o['payment_method'])}\n"
                     f"ð *Date & Time:* `{o['timestamp']}`\n"
                     f"ââââââââââââââââââââââââ\n")

        markup = types.InlineKeyboardMarkup(row_width=2)
        nav_btns = []
        if page > 0:
            nav_btns.append(types.InlineKeyboardButton("â¬ï¸ Prev", callback_data=f"adm_allorders:{page-1}"))
        if offset + limit < total_orders:
            nav_btns.append(types.InlineKeyboardButton("Next â¡ï¸", callback_data=f"adm_allorders:{page+1}"))
        if nav_btns:
            markup.add(*nav_btns)

        markup.add(types.InlineKeyboardButton("ð Back to Panel", callback_data="adm_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    # ð¢ FEATURE 2: MANAGE & DELETE UNWANTED REVIEWS
    elif action == "delreviews":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reviews ORDER BY review_id DESC LIMIT 10")
        reviews = cursor.fetchall()
        conn.close()

        if not reviews:
            bot.answer_callback_query(call.id, "No reviews found in database!")
            return

        text = "ð *MANAGE CUSTOMER REVIEWS*\n\nTap a delete button below to remove an unwanted review:\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for r in reviews:
            stars = "â­" * r['rating']
            uname = escape_md(r['username'] or 'User')
            short_comment = escape_md(r['comment'][:40]) + ("..." if len(r['comment']) > 40 else "")
            
            text += f"ð *Review #{r['review_id']}* | ð¤ *{uname}* ({stars})\nð¬ _{short_comment}_\nð {r['date_added']}\n\n"
            markup.add(types.InlineKeyboardButton(f"â Delete Review #{r['review_id']}", callback_data=f"delrev_{r['review_id']}"))

        markup.add(types.InlineKeyboardButton("ð Back to Panel", callback_data="adm_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif action == "coupons":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM coupons")
        coupons = cursor.fetchall()
        conn.close()

        text = "ð *ACTIVE COUPON CODES*\n\n"
        if not coupons:
            text += "No active coupon codes found."
        else:
            for c in coupons:
                text += f"â¢ `{c['code']}` â **{c['discount_percent']}% OFF** ({c['current_uses']}/{c['max_uses']} uses)\n"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("â Create New Coupon", callback_data="create_coupon"),
            types.InlineKeyboardButton("ð Back to Panel", callback_data="adm_panel")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif action == "editprices":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories")
        cats = cursor.fetchall()
        conn.close()

        markup = types.InlineKeyboardMarkup(row_width=1)
        for c in cats:
            markup.add(types.InlineKeyboardButton(f"ð· {c['title']}", callback_data=f"price_edit_{c['category_id']}"))
        markup.add(types.InlineKeyboardButton("ð Back to Panel", callback_data="adm_panel"))

        bot.edit_message_text("ð· *PRICE MANAGER*\n\nSelect a category to modify its prices:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif action == "stock":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT category_id, COUNT(*) FROM bulk_accounts WHERE is_sold = 0 GROUP BY category_id")
        counts = dict(cursor.fetchall())
        cursor.execute("SELECT category_id, cat_type FROM categories")
        all_cats = cursor.fetchall()
        conn.close()

        text = "ð *CURRENT ACCOUNT STOCK*\n\n"
        for cat in all_cats:
            if cat['cat_type'] != "service" and not is_service(cat['category_id']):
                text += f"â¢ `{cat['category_id']}`: {counts.get(cat['category_id'], 0)} available\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("ð Back to Panel", callback_data="adm_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif action == "orders":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE status = 'PENDING' ORDER BY order_id DESC LIMIT 5")
        orders = cursor.fetchall()
        conn.close()
        if not orders:
            bot.answer_callback_query(call.id, "No pending orders right now!")
            return
        bot.send_message(call.message.chat.id, f"â³ Found {len(orders)} pending orders. Check your direct messages for payment details and action panels.")
        bot.answer_callback_query(call.id)

    elif action == "addstock":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT category_id, title, cat_type FROM categories")
        cats = cursor.fetchall()
        conn.close()

        markup = types.InlineKeyboardMarkup(row_width=1)
        for c in cats:
            if c['cat_type'] != "service" and not is_service(c['category_id']):
                markup.add(types.InlineKeyboardButton(f"ð¦ {c['title']}", callback_data=f"addstock_{c['category_id']}"))
        markup.add(types.InlineKeyboardButton("ð Back to Panel", callback_data="adm_panel"))
        bot.edit_message_text("ð¦ *Select account category to restock:*", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif action == "addcar":
        bot.send_message(call.message.chat.id, "ð¸ Send the **Photo** of the car you want to add to the Garage:")
        bot.register_next_step_handler(call.message, process_car_photo)
        bot.answer_callback_query(call.id)

    elif action == "updateqr":
        msg = bot.send_message(call.message.chat.id, "ð¼ Send the new Google Pay QR Code image:")
        bot.register_next_step_handler(msg, process_gpay_qr_upload)
        bot.answer_callback_query(call.id)

    elif action == "broadcast":
        msg = bot.send_message(call.message.chat.id, "ð¢ Send the message you want to broadcast to all users:")
        bot.register_next_step_handler(msg, process_broadcast)

    elif action == "panel":
        send_admin_panel(call.message.chat.id, call.message.message_id)

# Handler to actually execute Review Deletion
@bot.callback_query_handler(func=lambda call: call.data.startswith("delrev_"))
def process_delete_review_callback(call):
    if call.from_user.id not in ADMINS: return
    review_id = call.data.replace("delrev_", "")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE review_id = ?", (review_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, f"â Review #{review_id} deleted successfully!", show_alert=True)
    
    # Refresh the manage reviews menu
    call.data = "adm_delreviews"
    admin_panel_callbacks(call)

# Handler for selecting Account vs Service type
@bot.callback_query_handler(func=lambda call: call.data.startswith("addcat_type:"))
def prompt_category_details(call):
    if call.from_user.id not in ADMINS: return
    cat_type = call.data.split(":")[1]
    
    type_str = "Service / Injection" if cat_type == "service" else "Account"
    msg = bot.send_message(
        call.message.chat.id, 
        f"â *ADDING NEW {type_str.upper()}*\n\n"
        f"Please enter details in this format:\n"
        f"`category_id | Title | Description | StarsPrice | BinancePrice | GPayPrice`\n\n"
        f"Example:\n"
        f"`cpm2_vinyl | CPM 2 Custom Vinyl | Custom vinyl injection for your account | 1500 | 15.0 | 1300.0`", 
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_add_category, cat_type)

def process_add_category(message, cat_type):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        cat_id = parts[0].lower().replace(" ", "_")
        title = parts[1]
        desc = parts[2]
        stars = int(parts[3])
        binance = float(parts[4])
        gpay = float(parts[5])

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO categories (category_id, title, description, price_stars, price_binance, price_gpay, cat_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (cat_id, title, desc, stars, binance, gpay, cat_type))
        conn.commit()
        conn.close()

        type_label = "ð  Service / Injection" if cat_type == "service" else "ð Account"
        bot.send_message(message.chat.id, f"â *New {type_label} Created Successfully!*\n\nð *ID:* `{cat_id}`\nð *Title:* {title}\nð *Description:* {desc}\nâ­ *Stars:* {stars} | ð¡ *Binance:* ${binance:.2f} | ð± *GPay:* {gpay:.2f}\n\nIt is now live in the main user menu!", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"â *Error creating category:* {e}\n\nPlease make sure to use the exact format `cat_id | Title | Description | Stars | Binance | GPay`.")

# Admin Coupon Creation Flow
@bot.callback_query_handler(func=lambda call: call.data == "create_coupon")
def create_coupon_prompt(call):
    if call.from_user.id not in ADMINS: return
    msg = bot.send_message(call.message.chat.id, "ð *Enter coupon details:*\n\nFormat: `CODE | DISCOUNT_PERCENT | MAX_USES`\nExample: `SAVE20 | 20 | 50`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_coupon_creation)

def process_coupon_creation(message):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        code, discount, max_uses = parts[0].upper(), float(parts[1]), int(parts[2])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO coupons (code, discount_percent, max_uses, current_uses) VALUES (?, ?, ?, 0)", (code, discount, max_uses))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"â *Coupon Created!*\n\nCode: `{code}`\nDiscount: **{discount}%**\nMax Usages: **{max_uses}**", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"â Error creating coupon: {e}")

# Admin Price Edit Flow
@bot.callback_query_handler(func=lambda call: call.data.startswith("price_edit_"))
def edit_price_prompt(call):
    if call.from_user.id not in ADMINS: return
    cat_id = call.data.replace("price_edit_", "")
    msg = bot.send_message(call.message.chat.id, f"ð· *Enter new prices for `{cat_id}`:*\n\nFormat: `StarsPrice | BinancePrice | GPayPrice`\nExample: `500 | 5.0 | 450.0`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_price_update, cat_id)

def process_price_update(message, cat_id):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        stars, binance, gpay = int(parts[0]), float(parts[1]), float(parts[2])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE categories SET price_stars = ?, price_binance = ?, price_gpay = ? WHERE category_id = ?", (stars, binance, gpay, cat_id))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"â *Prices Updated for `{cat_id}`!*", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"â Error updating price: {e}")

# Admin QR / Restock / Car Handlers
def process_gpay_qr_upload(message):
    if message.from_user.id not in ADMINS: return
    if not message.photo: return
    file_id = message.photo[-1].file_id
    set_setting("gpay_qr_file_id", file_id)
    bot.send_message(message.chat.id, "â *Google Pay QR Code saved successfully!*", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("addstock_"))
def process_addstock_category(call):
    if call.from_user.id not in ADMINS: return
    cat_id = call.data.replace("addstock_", "")
    msg = bot.send_message(call.message.chat.id, f"ð¥ Send the credentials for `{cat_id}`.\n\nFormat (one per line):\n`email1:pass1`\n`email2:pass2`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_bulk_restock, cat_id)

def process_bulk_restock(message, cat_id):
    lines = message.text.strip().split("\n")
    added = 0
    conn = get_db()
    cursor = conn.cursor()
    for line in lines:
        if ":" in line:
            cursor.execute("INSERT INTO bulk_accounts (category_id, credentials) VALUES (?, ?)", (cat_id, line.strip()))
            added += 1
    d, t = datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S")
    cursor.execute("INSERT OR REPLACE INTO stock_metadata (product_type, last_restock_date, last_restock_time) VALUES (?, ?, ?)", (cat_id, d, t))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"â Successfully added {added} accounts to `{cat_id}`.")

def process_car_photo(message):
    if not message.photo: return
    file_id = message.photo[-1].file_id
    user_states[f"newcar_{message.from_user.id}"] = {"photo": file_id}
    msg = bot.send_message(message.chat.id, "ð Enter car details.\nFormat: `Brand | Owner | StarsPrice | BinancePrice | GpayPrice`\nExample: `BMW M5 | @markocpm | 500 | 5.0 | 450.0`")
    bot.register_next_step_handler(msg, process_car_details)

def process_car_details(message):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        brand, owner, stars, binance, gpay = parts[0], parts[1], int(parts[2]), float(parts[3]), float(parts[4])
        file_id = user_states[f"newcar_{message.from_user.id}"]["photo"]
        
        conn = get_db()
        cursor = conn.cursor()
        d, t = datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S")
        cursor.execute("INSERT INTO garage_cars (brand, owner, price_stars, price_binance, price_gpay, photo_file_id, date_added, time_added) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (brand, owner, stars, binance, gpay, file_id, d, t))
        cursor.execute("INSERT OR REPLACE INTO stock_metadata (product_type, last_restock_date, last_restock_time) VALUES (?, ?, ?)", ('GARAGE', d, t))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "â Car added to Garage successfully!")
    except Exception as e:
        bot.send_message(message.chat.id, f"â Error: {e}")

def process_broadcast(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    success = 0
    for u in users:
        try:
            if message.photo: bot.send_photo(u['user_id'], message.photo[-1].file_id, caption=message.caption, parse_mode="Markdown")
            else: bot.send_message(u['user_id'], message.text, parse_mode="Markdown")
            success += 1
        except Exception: pass
    bot.send_message(message.chat.id, f"â Broadcast sent to {success}/{len(users)} users.")

# ---------------------------------------------------------------------------
# AUTOMATIC ACCOUNT DELIVERY & DECISION LOGIC
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("order_"))
def process_admin_order_decision(call):
    if call.from_user.id not in ADMINS: return
    
    parts = call.data.split("_")
    action = parts[1] 
    order_id = parts[2]
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    order = cursor.fetchone()
    
    if not order or order['status'] != 'PENDING':
        bot.answer_callback_query(call.id, "Order processing error or already finalized.")
        conn.close()
        return

    if action == "reject":
        cursor.execute("UPDATE orders SET status = 'REJECTED' WHERE order_id = ?", (order_id,))
        conn.commit()
        bot.edit_message_text(f"â *ORDER #{order_id} REJECTED*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
        try: bot.send_message(order['user_id'], f"â *Order #{order_id} Rejected*\nYour payment could not be verified. Contact @markocpm for support.", parse_mode="Markdown")
        except Exception: pass

    elif action == "approve":
        item_type = order['item_type']
        qty = order['quantity']
        coupon_code = order['coupon_code']

        if coupon_code:
            cursor.execute("UPDATE coupons SET current_uses = current_uses + 1 WHERE code = ?", (coupon_code,))

        if item_type == "car":
            car_id = order['item_id']
            cursor.execute("DELETE FROM garage_cars WHERE car_id = ?", (car_id,))
            cursor.execute("UPDATE orders SET status = 'APPROVED' WHERE order_id = ?", (order_id,))
            conn.commit()
            bot.edit_message_text(f"â *ORDER #{order_id} APPROVED (GARAGE CAR)*\nCar #{car_id} removed from inventory.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
            try: bot.send_message(order['user_id'], f"â *Payment Confirmed for Order #{order_id}!*\n\nPlease message @markocpm to arrange in-game delivery of your car.", parse_mode="Markdown")
            except Exception: pass
            
        elif is_service(item_type):
            cursor.execute("UPDATE orders SET status = 'APPROVED' WHERE order_id = ?", (order_id,))
            conn.commit()
            bot.edit_message_text(f"â *ORDER #{order_id} APPROVED (SERVICE COMPLETED)*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
            try: bot.send_message(order['user_id'], f"â *Service Completed!* (Order #{order_id})\n\nYour request has been processed successfully.", parse_mode="Markdown")
            except Exception: pass
            
        else:
            # AUTOMATED BULK / SINGLE ACCOUNT DELIVERY
            cursor.execute("SELECT * FROM bulk_accounts WHERE category_id = ? AND is_sold = 0 ORDER BY account_id ASC LIMIT ?", (item_type, qty))
            accs = cursor.fetchall()
            
            if len(accs) < qty:
                bot.answer_callback_query(call.id, f"ð¨ OUT OF STOCK for category '{item_type}'! Restock first.", show_alert=True)
                conn.close()
                return
                
            acc_ids = [a['account_id'] for a in accs]
            cursor.execute(f"UPDATE bulk_accounts SET is_sold = 1 WHERE account_id IN ({','.join('?'*len(acc_ids))})", acc_ids)
            cursor.execute("UPDATE orders SET status = 'APPROVED' WHERE order_id = ?", (order_id,))
            conn.commit()
            
            bot.edit_message_text(f"â *ORDER #{order_id} APPROVED*\nAutomated delivery of {qty} account(s) completed!", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
            
            creds_text = "\n".join([f"`{escape_md(a['credentials'])}`" for a in accs])
            try:
                bot.send_message(order['user_id'], f"â *Payment Confirmed!* (Order #{order_id})\n\nHeres your account credentials (x{qty}):\n\n{creds_text}\n\nPlease log in and change passwords immediately.", parse_mode="Markdown")
            except Exception as e: print(f"Delivery failed: {e}")
            
    conn.close()

# ---------------------------------------------------------------------------
# REVIEWS SYSTEM
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data == "view_reviews")
def view_reviews(call):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews ORDER BY review_id DESC LIMIT 5")
    reviews = cursor.fetchall()
    conn.close()
    
    if not reviews:
        bot.answer_callback_query(call.id, "No reviews yet!")
        return
        
    text = "â­ *LATEST CUSTOMER REVIEWS*\n\n"
    for r in reviews:
        stars = "â­" * r['rating']
        text += f"ð¤ *{escape_md(r['username'])}* ({r['date_added']})\nRating: {stars}\nð¬ _{escape_md(r['comment'])}_\n\n"
        
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_review")
def add_review(call):
    msg = bot.send_message(call.message.chat.id, "â­ Please send a rating from 1 to 5:")
    bot.register_next_step_handler(msg, process_rating)

def process_rating(message):
    try:
        rating = int(message.text.strip())
        if rating < 1 or rating > 5: raise ValueError
        user_states[f"review_{message.from_user.id}"] = {"rating": rating}
        msg = bot.send_message(message.chat.id, "ð¬ Now, please type your review comment:")
        bot.register_next_step_handler(msg, process_review_comment)
    except ValueError:
        bot.send_message(message.chat.id, "â Invalid rating. Please start again from the main menu.")

def process_review_comment(message):
    user_id = message.from_user.id
    data = user_states.get(f"review_{user_id}")
    if not data: return
    
    rating = data['rating']
    comment = message.text.strip()
    name = message.from_user.first_name
    d = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reviews (user_id, username, rating, comment, date_added) VALUES (?, ?, ?, ?, ?)", (user_id, name, rating, comment, d))
    conn.commit()
    conn.close()
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("ð Back to Main Menu", callback_data="main_menu"))
    bot.send_message(message.chat.id, "â Thank you! Your review has been added.", reply_markup=markup)

# Start Polling
bot.polling(none_stop=True)
