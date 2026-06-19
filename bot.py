# All-in-One VPN APK VIP & Telegram VIP Management Bot
# Py By @AHLFLK2025

import os
import re
import sqlite3
import requests
from threading import Thread
from datetime import datetime, timedelta
from flask import Flask, request, abort
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("TGC_ID")) if os.environ.get("TGC_ID") else None
DEFAULT_CREDITS = 100

SCRIPT_URL = os.environ.get("SCRIPT_URL")
PUBLIC_URL = os.environ.get("PUBLIC_URL")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
vip_temp_data = {}

ADMIN_BUTTONS = [
    ["➕ Add VIP User", "🔑 My VIP Users"],
    ["✏️ Edit VIP", "🗑 Delete VIP"],
    ["👤 Create Reseller", "📊 Reseller List"],
    ["✏️ Edit Reseller", "🗑 Delete Reseller"],
    ["🌐 View All VIPs", "💰 My Balance"]
]

RESELLER_BUTTONS = [
    ["➕ Add VIP User", "🔑 My VIP Users"],
    ["✏️ Edit VIP", "🗑 Delete VIP"],
    ["💰 My Balance"]
]

NORMAL_BUTTONS = [
    ["💰 Balance"]
]

def get_menu_markup(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if user_id == ADMIN_ID:
        for row in ADMIN_BUTTONS:
            markup.add(*[types.KeyboardButton(b) for b in row])
    elif is_reseller(user_id):
        for row in RESELLER_BUTTONS:
            markup.add(*[types.KeyboardButton(b) for b in row])
    else:
        for row in NORMAL_BUTTONS:
            markup.add(*[types.KeyboardButton(b) for b in row])
    return markup

def get_admin_contact_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
    return markup

def get_current_date_string():
    utc_now = datetime.utcnow()
    mm_now = utc_now + timedelta(hours=7)
    return mm_now.strftime("%d/%m/%Y")

# ==========================================
# DATABASE SYNC ENGINE
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS auth_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            target_id TEXT UNIQUE,
            key_string TEXT, 
            unit_val TEXT, 
            duration_type TEXT, 
            added_by INTEGER,
            created_at TEXT,
            vip_tg_id TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, 
            username TEXT, 
            role TEXT,
            token_balance INTEGER DEFAULT 0,
            expire_date TEXT DEFAULT '31/12/2099'
        )''')
        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date) VALUES (?, ?, ?, ?, ?)", 
                       (ADMIN_ID, 'Main_Admin', 'admin', -1, '31/12/2099'))
        conn.commit()
    finally:
        conn.close()

def pull_data_from_google_sheet():
    if not SCRIPT_URL: return
    try:
        res = requests.get(SCRIPT_URL, timeout=15)
        if res.status_code == 200:
            data_list = res.json()
            if isinstance(data_list, dict) and "error" in data_list: return
            
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM auth_keys")
                cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
                
                for row in data_list:
                    col_a = str(row.get("Users") or "").strip() 
                    k_str = str(row.get("Name") or "").strip()  
                    key_apk = str(row.get("Key") or "").strip() 
                    c_at = row.get("Start") or get_current_date_string()
                    m_val = row.get("Month") or 0
                    
                    if k_str == "": continue
                    
                    if "_Reseller" in k_str:
                        try:
                            clean_name = k_str.replace("_Reseller", "").strip()
                            token_val = int(float(key_apk)) if '.' in key_apk else int(key_apk)
                            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date) VALUES (?, ?, ?, ?, ?)", 
                                           (int(col_a), clean_name, 'reseller', token_val, "31/12/2099"))
                        except: pass
                    else:
                        try:
                            clean_months = int(float(m_val)) if str(m_val).replace('.','',1).isdigit() else 1

                            # NEW: parse "Name_AddedBy_<reseller_id>" out of column B (Name).
                            # Column A now holds the VIP user's own Telegram ID instead of added_by.
                            display_name = k_str
                            final_creator = ADMIN_ID
                            m = re.search(r"_AddedBy_(\d+)$", k_str)
                            if m:
                                display_name = k_str[:m.start()]
                                final_creator = int(m.group(1))

                            vip_tg_id = col_a if col_a.isdigit() else ""

                            cursor.execute("INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at, vip_tg_id) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                           (key_apk, display_name, str(clean_months), "m", final_creator, str(c_at).strip(), vip_tg_id))
                        except: pass
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        print(f"[-] Pull Error: {str(e)}")

def push_to_google_sheet(action, users, name, key, start, month, reseller_months=0, added_by=""):
    if not SCRIPT_URL: return False
    payload = {
        "action": action,
        "users": str(users),
        "name": str(name),
        "key": str(key),
        "start": str(start),
        "month": int(month),
        "reseller_months": int(reseller_months),
        "added_by": str(added_by)
    }
    try:
        res = requests.post(SCRIPT_URL, json=payload, timeout=15)
        return res.status_code == 200
    except:
        return False

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def calculate_days(unit):
    return int(unit) * 30

def is_admin(user_id): 
    return user_id == ADMIN_ID

def is_reseller(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE tg_id = ? AND role = 'reseller'", (user_id,))
        res = cursor.fetchone()
    finally:
        conn.close()
    return res is not None

def get_reseller_tokens(user_id):
    if user_id == ADMIN_ID: return -1
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT token_balance FROM users WHERE tg_id = ?", (user_id,))
        res = cursor.fetchone()
    finally:
        conn.close()
    return res[0] if res else 0

def deduct_reseller_tokens_by_days(user_id, required_tokens):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT token_balance FROM users WHERE tg_id = ?", (user_id,))
        res = cursor.fetchone()
        if res:
            tokens = res[0]
            if tokens >= required_tokens:
                new_balance = tokens - required_tokens
                cursor.execute("UPDATE users SET token_balance = ? WHERE tg_id = ?", (new_balance, user_id))
                conn.commit()
                return True
        return False
    finally:
        conn.close()

def get_vip_status_by_tg_id(user_id):
    """
    Looks up all VPN APK VIP records for a Telegram user (vip_tg_id = column A).
    If multiple rows exist (multiple keys under same TG ID), picks the latest expiry date.
    Returns a dict: {"status": "active"/"expired"/"not_found", "expiry": "<date or None>"}
    """
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT unit_val, created_at FROM auth_keys WHERE vip_tg_id = ?",
            (str(user_id),)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return {"status": "not_found", "expiry": None}

    today_mm = datetime.strptime(get_current_date_string(), "%d/%m/%Y")
    best_expiry = None

    for unit_val, created_at in rows:
        try:
            days = calculate_days(unit_val)
            fmt = "%d/%m/%Y" if '/' in created_at else "%Y-%m-%d"
            expiry_dt = datetime.strptime(created_at, fmt) + timedelta(days=days)
            if best_expiry is None or expiry_dt > best_expiry:
                best_expiry = expiry_dt
        except Exception:
            continue

    if best_expiry is None:
        return {"status": "not_found", "expiry": None}

    expiry_str = best_expiry.strftime("%d/%m/%Y")
    if best_expiry.date() < today_mm.date():
        return {"status": "expired", "expiry": expiry_str}
    return {"status": "active", "expiry": expiry_str}

# ==========================================
# TELEGRAM MENU INTERFACE
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None
    pull_data_from_google_sheet()
    
    first_name = message.from_user.first_name
    bot_name = bot.get_me().first_name
    vip_info = get_vip_status_by_tg_id(user_id)

    if vip_info["status"] == "active":
        vip_line = f"📆 VPN APK VIP: <code>{vip_info['expiry']}</code> ✅\n"
    elif vip_info["status"] == "expired":
        vip_line = f"📆 VPN APK VIP: <code>{vip_info['expiry']}</code> (Expired) ⚠️\n"
    else:
        vip_line = f"📆 VPN APK VIP: <code>Non VPN APK VIP</code>\n"

    if not is_reseller(user_id):
        account_status = "Normal User 🙂"
        welcome_text = f"👋 <b>{bot_name} မှ ကြိုဆိုပါတယ်!</b>\n\n" \
                       f"📊 <b>အကောင့်အခြေအနေ:</b>\n" \
                       f"👑 အဆင့်အတန်း: <b>{account_status}</b>\n" \
                       f"👤 အမည်: <b>{first_name}</b>\n" \
                       f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                       f"{vip_line}\n" \
                       f"💡 အောက်ပါ Panel Keyboard ကို အသုံးပြုပြီး လုပ်ငန်းများကို ဆောင်ရွက်နိုင်ပါသည်။"

        if vip_info["status"] == "active":
            return bot.reply_to(message, welcome_text, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
        else:
            # Show Balance keyboard AND Contact Admin inline button together
            bot.reply_to(message, welcome_text, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
            bot.send_message(message.chat.id, "📞 VPN APK VIP ဝယ်ယူ/သက်တမ်းတိုးရန် Admin ထံ ဆက်သွယ်ပေးပါ-", reply_markup=get_admin_contact_markup())
            return

    if is_admin(user_id):
        account_status = "Main Admin 👑"
        tokens_line = "🪙 Credit Balance: <code>Unlimited ♾️</code>\n"
    else:
        account_status = "Reseller Staff 💼"
        tokens_line = f"🪙 Credit Balance: <code>{get_reseller_tokens(user_id)}</code> Tokens\n"

    welcome_text = f"👋 <b>{bot_name} မှ ကြိုဆိုပါတယ်!</b>\n\n" \
                   f"📊 <b>အကောင့်အခြေအနေ:</b>\n" \
                   f"👑 အဆင့်အတန်း: <b>{account_status}</b>\n" \
                   f"👤 အမည်: <b>{first_name}</b>\n" \
                   f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                   f"{tokens_line}" \
                   f"{vip_line}\n" \
                   f"💡 အောက်ပါ Panel Keyboard ကို အသုံးပြုပြီး လုပ်ငန်းများကို ဆောင်ရွက်နိုင်ပါသည်။"

    bot.reply_to(message, welcome_text, reply_markup=get_menu_markup(user_id), parse_mode="HTML")

@bot.message_handler(func=lambda msg: any(msg.text == btn for row in ADMIN_BUTTONS for btn in row))
def handle_menu_clicks(message):
    user_id = message.from_user.id
    text = message.text
    pull_data_from_google_sheet()
    
    if not is_reseller(user_id):
        user_states[user_id] = None
        return bot.reply_to(message, "❌ <b>ခွင့်ပြုချက် မရှိပါ!</b>\n\nသင့်ရဲ့ Reseller အကောင့်ကို Admin ကနေ ဖျက်သိမ်းထားပြီး ဖြစ်ပါသဖြင့် ဤ Panel အား ဆက်လက်အသုံးပြုခွင့် မရှိတော့ပါ။", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

    # Token 0 ဖြစ်နေချိန်တွင် Balance စစ်ဆေးခြင်းမှအပ အခြားခလုတ်များကို ပိတ်ရန်
    if is_reseller(user_id) and not is_admin(user_id) and text != "💰 My Balance":
        if get_reseller_tokens(user_id) <= 0:
            return bot.reply_to(message, "⚠️ <b>သင့်တွင် Token မလုံလောက်တော့ပါ!</b>\n\nသင့်အကောင့်မှာ Token ကုန်ဆုံးသွားပါသဖြင့် စနစ်အား ဆက်လက်အသုံးပြုနိုင်ရန်အတွက် Admin ထံသို့ ဆက်သွယ်ပြီး Token ပြန်လည်ဖြည့်သွင်းနိုင်ပါသည်။", reply_markup=get_admin_contact_markup())

    if text == "💰 My Balance":
        vip_info_b = get_vip_status_by_tg_id(user_id)
        if vip_info_b["status"] == "active":
            vip_line_b = f"📆 VPN APK VIP: <code>{vip_info_b['expiry']}</code> ✅"
        elif vip_info_b["status"] == "expired":
            vip_line_b = f"📆 VPN APK VIP: <code>{vip_info_b['expiry']}</code> (Expired) ⚠️"
        else:
            vip_line_b = f"📆 VPN APK VIP: <code>Non VPN APK VIP</code>"

        if is_admin(user_id):
            tokens_str = "Unlimited ♾️"
            role_str = "Main Admin 👑"
            res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
                  f"👑 အဆင့်အတန်း: <b>{role_str}</b>\n" \
                  f"🆔 TG ID: <code>{user_id}</code>\n" \
                  f"🪙 လက်ကျန် Credit: <code>{tokens_str}</code>\n" \
                  f"{vip_line_b}"
            bot.reply_to(message, res, parse_mode="HTML")
        else:
            current_tokens = get_reseller_tokens(user_id)
            role_str = "Reseller Staff 💼"
            
            # 🌟 [NEW LOGIC] Reseller Token က 0 ဖြစ်နေပါက Contact Admin ခလုတ် တွဲပြပေးမည်။
            if current_tokens <= 0:
                res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
                      f"👑 အဆင့်အတန်း: <b>{role_str}</b>\n" \
                      f"🆔 TG ID: <code>{user_id}</code>\n" \
                      f"🪙 လက်ကျန် Credit: <code>0 Tokens (ကုန်ဆုံး)</code>\n" \
                      f"{vip_line_b}\n\n" \
                      f"⚠️ သင့်အကောင့်တွင် တိုကင်ကုန်ဆုံးနေပါသဖြင့် ဆက်လက်အသုံးပြုနိုင်ရန် အောက်ပါခလုတ်မှတစ်ဆင့် Admin ဆီသို့ ဆက်သွယ်ပြီး Token ပြန်လည်ဖြည့်သွင်းနိုင်ပါသည်။"
                bot.reply_to(message, res, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            else:
                res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
                      f"👑 အဆင့်အတန်း: <b>{role_str}</b>\n" \
                      f"🆔 TG ID: <code>{user_id}</code>\n" \
                      f"🪙 လက်ကျန် Credit: <code>{current_tokens} Tokens</code>\n" \
                      f"{vip_line_b}"
                bot.reply_to(message, res, parse_mode="HTML")

    elif text == "➕ Add VIP User":
        user_states[user_id] = "ADD_VIP_TGID"
        bot.reply_to(message, "🆔 ထည့်သွင်းမည့် VIP အသုံးပြုသူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🔑 My VIP Users":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, created_at FROM auth_keys WHERE added_by = ? AND target_id != ''", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows: 
            return bot.reply_to(message, "📭 သင် ထည့်သွင်းထားသော VIP အသုံးပြုသူ စာရင်းမရှိသေးပါ။")
        
        res = f"🔑 <b>သင် ထည့်သွင်းထားသော VIP စာရင်း ({len(rows)} ဦး):</b>\n\n"
        for r in rows:
            days = calculate_days(r[2])
            try:
                fmt = "%d/%m/%Y" if '/' in r[3] else "%Y-%m-%d"
                exp = (datetime.strptime(r[3], fmt) + timedelta(days=days)).strftime("%d/%m/%Y")
            except: exp = "Error"
            res += f"🔑 APK ID: <code>{r[0]}</code> | 👤 Name: <code>{r[1]}</code> | 📅 Exp: <code>{exp}</code>\n"
        bot.reply_to(message, res, parse_mode="HTML")

    elif text == "✏️ Edit VIP":
        user_states[user_id] = "EDIT_VIP_ID"
        bot.reply_to(message, "✏️ ပြင်ဆင်မည့် VIP အသုံးပြုသူ၏ <b>VPN APK ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🗑 Delete VIP":
        user_states[user_id] = "DEL_VIP_ID"
        bot.reply_to(message, "🗑 ဖျက်ထုတ်မည့် VIP အသုံးပြုသူ၏ <b>VPN APK ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "👤 Create Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "ADD_RES_ID"
        bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "📊 Reseller List":
        if not is_admin(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance FROM users WHERE role = 'reseller' AND tg_id != ''")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 Reseller စာရင်း မရှိသေးပါ။")
        res = f"📊 <b>Reseller စာရင်းအားလုံး ({len(rows)} ဦး):</b>\n\n"
        for r in rows:
            tk_display = "Unlimited ♾️" if r[2] == -1 else f"{r[2]} Tk"
            res += f"🆔 TG ID: <code>{r[0]}</code> | 👤 Name: {r[1]} | 🪙 Tokens: {tk_display}\n"
        bot.reply_to(message, res, parse_mode="HTML")

    elif text == "✏️ Edit Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "EDIT_RES_ID"
        bot.reply_to(message, "✏️ ပြင်ဆင်မည့် Reseller ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🗑 Delete Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "DEL_RES_ID"
        bot.reply_to(message, "🗑 ဖျက်ထုတ်မည့် Reseller ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🌐 View All VIPs":
        if not is_admin(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, created_at FROM auth_keys WHERE target_id != ''")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 VIP အကောင့် မရှိသေးပါ။")
        res = f"🌐 <b>VIP အသုံးပြုသူ စာရင်းအားလုံး ({len(rows)} ဦး):</b>\n\n"
        for r in rows:
            days = calculate_days(r[2])
            try:
                fmt = "%d/%m/%Y" if '/' in r[3] else "%Y-%m-%d"
                exp = (datetime.strptime(r[3], fmt) + timedelta(days=days)).strftime("%d/%m/%Y")
            except: exp = "Error"
            res += f"🔑 APK ID: <code>{r[0]}</code> | 👤 Name: <code>{r[1]}</code> | 📅 Exp: <code>{exp}</code>\n"
        bot.reply_to(message, res, parse_mode="HTML")

# ==========================================
# NORMAL USER VIP CHECK (Balance button)
# ==========================================
@bot.message_handler(func=lambda msg: msg.text == "💰 Balance")
def handle_normal_balance_check(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pull_data_from_google_sheet()

    if is_reseller(user_id):
        return  # Admin/Reseller already use "💰 My Balance" via the panel keyboard

    vip_info = get_vip_status_by_tg_id(user_id)
    if vip_info["status"] == "active":
        vip_line = f"📆 VPN APK VIP: <code>{vip_info['expiry']}</code> ✅"
    elif vip_info["status"] == "expired":
        vip_line = f"📆 VPN APK VIP: <code>{vip_info['expiry']}</code> (Expired) ⚠️"
    else:
        vip_line = f"📆 VPN APK VIP: <code>Non VPN APK VIP</code>"

    res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
          f"👑 အဆင့်အတန်း: <b>Normal User 🙂</b>\n" \
          f"👤 အမည်: <b>{first_name}</b>\n" \
          f"🆔 TG ID: <code>{user_id}</code>\n" \
          f"{vip_line}"

    if vip_info["status"] == "active":
        bot.reply_to(message, res, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
    else:
        bot.reply_to(message, res, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
        bot.send_message(message.chat.id, "📞 VPN APK VIP ဝယ်ယူ/သက်တမ်းတိုးရန် Admin ထံ ဆက်သွယ်ပေးပါ-", reply_markup=get_admin_contact_markup())

# ==========================================
# INPUT HANDLERS (STATE MANAGEMENT)
# ==========================================
@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) is not None)
def handle_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text.strip()
    
    if not is_reseller(user_id):
        user_states[user_id] = None
        return bot.reply_to(message, "❌ <b>ခွင့်ပြုချက်မရှိပါ!</b>\n\nသင့်ရဲ့ Reseller အကောင့်ကို Admin ကနေ ဖျက်သိမ်းထားပြီး ဖြစ်ပါသဖြင့် ဆက်လက်လုပ်ဆောင်၍ မရတော့ပါ။", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

    # --- ADD VIP ---
    if state == "ADD_VIP_TGID":
        if not text.isdigit(): return bot.reply_to(message, "⚠️ Telegram ID ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပေးပါ-")
        vip_temp_data[user_id] = {"vip_tg_id": text}
        user_states[user_id] = "ADD_VIP_ID"
        bot.reply_to(message, "🔑 VIP အသုံးပြုသူ၏ <b>VPN APK Key</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif state == "ADD_VIP_ID":
        apk_id = text
        vip_temp_data[user_id]["apk_id"] = apk_id

        # Check if key already exists in DB
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT key_string FROM auth_keys WHERE target_id = ?", (apk_id,))
        existing = cursor.fetchone()
        conn.close()

        if existing:
            # Key already exists — skip Name, go straight to Month (renewal flow)
            existing_name = existing[0]
            vip_temp_data[user_id]["name"] = existing_name
            user_states[user_id] = "ADD_VIP_MONTH"
            bot.reply_to(message,
                f"⚠️ ယခု VPN APK Key သည် <b>{existing_name}</b> VIP User ဖြစ်ပါသဖြင့် သက်တမ်းတိုးမြှင့်ရန်\n"
                f"⏳ <b>လအရေအတွက်</b> ထည့်ပေးပါ-",
                parse_mode="HTML")
        else:
            user_states[user_id] = "ADD_VIP_NAME"
            bot.reply_to(message, "👤 အသုံးပြုသူ၏ <b>အမည် (Name)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")
        
    elif state == "ADD_VIP_NAME":
        vip_temp_data[user_id]["name"] = text
        user_states[user_id] = "ADD_VIP_MONTH"
        bot.reply_to(message, "⏳ သက်တမ်းသတ်မှတ်ရန် <b>လအရေအတွက် (ဥပမာ- 1)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")
        
    elif state == "ADD_VIP_MONTH":
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပေးပါ-")
        months = int(text)
        
        current_bal = get_reseller_tokens(user_id)
        if not deduct_reseller_tokens_by_days(user_id, months):
            user_states[user_id] = None
            err_msg = f"❌ <b>သင့်မှာ လုံလောက်တဲ့ Token မရှိပါ။</b>\n\n" \
                      f"⚠️ လိုအပ်သောပမာဏ: <code>{months}</code> Tokens\n" \
                      f"🪙 သင့်လက်ကျန်: <code>{current_bal}</code> Tokens\n\n" \
                      f"Token ပြန်လည်ဖြည့်သွင်းရန် အောက်ပါခလုတ်မှတစ်ဆင့် Admin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။"
            return bot.reply_to(message, err_msg, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            
        apk_id = vip_temp_data[user_id]["apk_id"]
        name = vip_temp_data[user_id]["name"]
        vip_tg_id = vip_temp_data[user_id]["vip_tg_id"]
        start_date = get_current_date_string()
        name_with_creator = f"{name}_AddedBy_{user_id}"
        
        success = push_to_google_sheet("sync", users=vip_tg_id, added_by=user_id, name=name_with_creator, key=apk_id, start=start_date, month=months)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ VIP အကောင့် အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။\n🆔 VIP Telegram ID: <code>{vip_tg_id}</code>\n🔑 VPN APK Key: <code>{apk_id}</code>\n👤 နာမည်: <code>{name}</code>\n⏳ သက်တမ်း: <code>{months}</code> လ", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Sheet သို့ ပို့ဆောင်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # --- EDIT VIP ---
    elif state == "EDIT_VIP_ID":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id FROM auth_keys WHERE target_id = ?", (text,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            user_states[user_id] = None
            return bot.reply_to(message, "❌ အဆိုပါ VPN APK ID အား ရှာမတွေ့ပါ။")
        vip_temp_data[user_id] = {"apk_id": text}
        user_states[user_id] = "EDIT_VIP_MONTH"
        bot.reply_to(message, "✏️ တိုးမြှင့်မည့် <b>လအရေအတွက်</b> ကို ရိုက်ထည့်ပါ-", parse_mode="HTML")

    elif state == "EDIT_VIP_MONTH":
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပေးပါ-")
        months = int(text)
        
        current_bal = get_reseller_tokens(user_id)
        if not deduct_reseller_tokens_by_days(user_id, months):
            user_states[user_id] = None
            err_msg = f"❌ <b>သင့်မှာ လုံလောက်တဲ့ Token မရှိပါ။</b>\n\n" \
                      f"⚠️ လိုအပ်သောပမာဏ: <code>{months}</code> Tokens\n" \
                      f"🪙 သင့်လက်ကျန်: <code>{current_bal}</code> Tokens\n\n" \
                      f"Token ပြန်လည်ဖြည့်သွင်းရန် အောက်ပါခလုတ်မှတစ်ဆင့် Admin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။"
            return bot.reply_to(message, err_msg, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            
        apk_id = vip_temp_data[user_id]["apk_id"]
        start_date = get_current_date_string()
        success = push_to_google_sheet("sync", users="", added_by=user_id, name="Edit_VIP", key=apk_id, start=start_date, month=months)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, "✅ VIP အကောင့် သက်တမ်း တိုးမြှင့်ပြီးပါပြီ။")
        else:
            bot.reply_to(message, "❌ ပြင်ဆင်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # --- DELETE VIP ---
    elif state == "DEL_VIP_ID":
        apk_id = text
        # Check existence first
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id FROM auth_keys WHERE target_id = ?", (apk_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            user_states[user_id] = None
            return bot.reply_to(message, "❌ အဆိုပါ VPN APK ID အား ရှာမတွေ့ပါ။")
        success = push_to_google_sheet("delete", users="", name="Delete", key=apk_id, start="", month=0)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ VIP APK ID: <code>{apk_id}</code> အား ဖျက်သိမ်းပြီးပါပြီ။", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ ဖျက်သိမ်းမှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # --- CREATE RESELLER ---
    elif state == "ADD_RES_ID":
        if not is_admin(user_id): return
        reseller_temp_data[user_id] = {"tg_id": text}
        user_states[user_id] = "ADD_RES_NAME"
        bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller အမည် ကို ရိုက်ထည့်ပေးပါ-")

    elif state == "ADD_RES_NAME":
        if not is_admin(user_id): return
        reseller_temp_data[user_id]["username"] = text
        user_states[user_id] = "ADD_RES_TOKENS"
        bot.reply_to(message, "🪙 ထည့်သွင်းပေးမည့် <b>Token ပမာဏ (Credits)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif state == "ADD_RES_TOKENS":
        if not is_admin(user_id): return
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပေးပါ-")
        tokens = int(text)
        r_id = reseller_temp_data[user_id]["tg_id"]
        r_name = reseller_temp_data[user_id]["username"] + "_Reseller"
        start_date = get_current_date_string()
        
        success = push_to_google_sheet("sync_reseller", users=r_id, name=r_name, key=str(tokens), start=start_date, month=0)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ Reseller အကောင့် ဖန်တီးပြီးပါပြီ။\n🆔 Telegram ID: <code>{r_id}</code>\n👤 အမည်: {reseller_temp_data[user_id]['username']}\n🪙 တိုကင်: {tokens} Tk", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Google Sheet ချိတ်ဆက်မှု လွဲချော်နေပါသည်။")
        user_states[user_id] = None

    # --- EDIT RESELLER ---
    elif state == "EDIT_RES_ID":
        if not is_admin(user_id): return
        reseller_temp_data[user_id] = {"tg_id": text}
        user_states[user_id] = "EDIT_RES_TOKENS"
        bot.reply_to(message, "🪙 တိုးမြှင့်ထည့်သွင်းမည့် <b>Token အရေအတွက်</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif state == "EDIT_RES_TOKENS":
        if not is_admin(user_id): return
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပေးပါ-")
        tokens = int(text)
        r_id = reseller_temp_data[user_id]["tg_id"]
        start_date = get_current_date_string()
        success = push_to_google_sheet("sync_reseller", users=r_id, name="Edit_Reseller", key=str(tokens), start=start_date, month=0)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, "✅ Reseller တိုကင် ဖြည့်သွင်းမှု အောင်မြင်ပါသည်။")
        else:
            bot.reply_to(message, "❌ ပြင်ဆင်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # --- DELETE RESELLER ---
    elif state == "DEL_RES_ID":
        if not is_admin(user_id): return
        r_id = text
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id FROM users WHERE tg_id = ? AND role = 'reseller'", (r_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            user_states[user_id] = None
            return bot.reply_to(message, "❌ အဆိုပါ Reseller Telegram ID အား ရှာမတွေ့ပါ။")
        success = push_to_google_sheet("delete_reseller", users=r_id, name="RESELLER_ACCOUNT", key="RESELLER_ACCOUNT", start="", month=0)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ Reseller ID: <code>{r_id}</code> အား ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ ဖျက်သိမ်းမှု လွဲချော်ခဲ့သည်။")
        user_states[user_id] = None

# ==========================================
# FLASK WEB SERVER RUNNERS
# ==========================================
@app.route('/')
def home():
    return "VPN Bot is running smoothly with Contact Admin Auto-attacher Engine!"

@app.route('/' + BOT_TOKEN if BOT_TOKEN else '/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    init_db()
    pull_data_from_google_sheet()
    
    if PUBLIC_URL and BOT_TOKEN:
        bot.remove_webhook()
        bot.set_webhook(url=f"{PUBLIC_URL}/{BOT_TOKEN}")
        run_server()
    else:
        bot.remove_webhook()
        Thread(target=run_server).start()
        bot.infinity_polling(skip_pending=True)
