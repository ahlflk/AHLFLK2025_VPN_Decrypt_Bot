# All-in-One VPN APK VIP & Telegram VIP Management Bot (With Decrypt Features)
# Py By @AHLFLK2025

import os
import re
import sqlite3
import requests
import json
import struct
import base64
import urllib.request
from threading import Thread
from datetime import datetime, timedelta
from flask import Flask, request, abort
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("TGC_ID")) if os.environ.get("TGC_ID") else None
SCRIPT_URL = os.environ.get("SCRIPT_URL")
PUBLIC_URL = os.environ.get("PUBLIC_URL")
VPN_CONFIGS = os.environ.get("VPN_CONFIGS")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
vip_temp_data = {}

ADMIN_BUTTONS = [
    ["🌐 VPN Decrypt List"],
    ["➕ Add VIP User", "✏️ Edit VIP", "🗑 Delete VIP"],
    ["🌐 View All VIPs"],
    ["👤 Create Reseller", "✏️ Edit Reseller", "🗑 Delete Reseller"],
    ["🔑 My VIP Users", "📊 Reseller List"],
    ["💰 My Balance"]
]

RESELLER_BUTTONS = [
    ["🌐 VPN Decrypt List"],
    ["🔑 My VIP Users"],
    ["➕ Add VIP User", "✏️ Edit VIP", "🗑 Delete VIP"],
    ["💰 My Balance"]
]

VIP_ACTIVE_BUTTONS = [
    ["🌐 VPN Decrypt List"],
    ["💰 My Balance"]
]

USER_BUTTONS = [
    ["💰 My Balance"]
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
        valid, role_str, _ = is_access_valid(user_id)
        if valid and role_str == "VIP User ✨":
            for row in VIP_ACTIVE_BUTTONS:
                markup.add(*[types.KeyboardButton(b) for b in row])
        else:
            for row in USER_BUTTONS:
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
# CRYPTOGRAPHY & DECRYPTION ENGINE (XXTEA)
# ==========================================
def u32(x): return x & 0xFFFFFFFF

def _longs_to_bytes(n, include_length):
    length = len(n)
    res = struct.pack('<%dI' % length, *n)
    if include_length:
        expected_length = n[-1]
        max_len = len(res) - 4
        min_len = len(res) - 7
        if expected_length < min_len or expected_length > max_len:
            return res[:-4].rstrip(b'\x00')
        res = res[:expected_length]
    return res

def _bytes_to_longs(s):
    padding = (4 - len(s) % 4) % 4
    s += b'\x00' * padding
    return list(struct.unpack('<%dI' % (len(s) // 4), s))

def _fix_key(key_bytes):
    if len(key_bytes) == 16: return key_bytes
    return key_bytes[:16] if len(key_bytes) > 16 else key_bytes + b'\x00' * (16 - len(key_bytes))

def decrypt_xxtea(data, key, delta):
    if len(data) == 0: return b''
    v = _bytes_to_longs(data)
    k = _bytes_to_longs(_fix_key(key))
    n = len(v)
    if n < 2: return data 

    q = 52 // n + 6
    sum_val = u32(q * delta)

    while sum_val != 0:
        e = u32(sum_val >> 2) & 3
        y = v[0]
        for p in range(n - 1, 0, -1):
            z = v[p - 1]
            mx = u32(((z >> 5) ^ u32(y << 2)) + ((y >> 3) ^ u32(z << 4))) ^ u32((sum_val ^ y) + (k[(p & 3) ^ e] ^ z))
            y = u32(v[p] - mx)
            v[p] = y
        z = v[n - 1]
        mx = u32(((z >> 5) ^ u32(y << 2)) + ((y >> 3) ^ u32(z << 4))) ^ u32((sum_val ^ y) + (k[(0 & 3) ^ e] ^ z))
        y = u32(v[0] - mx)
        v[0] = y
        sum_val = u32(sum_val - delta)
    return _longs_to_bytes(v, True)

def parse_delta(delta_val):
    if isinstance(delta_val, int): return delta_val
    try:
        if isinstance(delta_val, str) and delta_val.strip().startswith('-'):
            clean_hex = delta_val.replace('-', '').strip()
            return -int(clean_hex, 16)
        else: return int(delta_val, 16)
    except: return 0x2e0ba747

def decrypt_inner_base64_recursive(encrypted_str):
    if not isinstance(encrypted_str, str) or len(encrypted_str) < 4: return encrypted_str
    try:
        clean_str = encrypted_str.replace('\n', '').replace('\r', '').strip()
        if not re.match(r'^[A-Za-z0-9+/=]+$', clean_str): return encrypted_str
        missing_padding = len(clean_str) % 4
        if missing_padding: clean_str += '=' * (4 - missing_padding)
        decoded_bytes = base64.b64decode(clean_str)
        decoded_str = decoded_bytes.decode('utf-8')
        if len(decoded_str) > 4 and re.match(r'^[A-Za-z0-9+/=]+$', decoded_str.replace('\n','').strip()):
            if any(x in decoded_str for x in ["HTTP/", "vless://", "vmess://", "trojan://", "ss://"]): return decoded_str
            return decrypt_inner_base64_recursive(decoded_str)
        return decoded_str
    except: return encrypted_str

def decrypt_inner_bamar(encrypted_str):
    if not encrypted_str or len(encrypted_str) < 10: return encrypted_str
    try:
        data = base64.b64decode(encrypted_str)
        decrypted_bytes = decrypt_xxtea(data, b"9488362782103982762188", 0x2e0ba747)
        return decrypted_bytes.decode('utf-8', errors='ignore') if decrypted_bytes else encrypted_str
    except: return encrypted_str

def decrypt_inner_pnt(encrypted_str):
    if not encrypted_str or len(encrypted_str) < 15: return encrypted_str
    try:
        data = base64.b64decode(encrypted_str, validate=True)
        decrypted_bytes = decrypt_xxtea(data, b"7361", 0x2e0ba747)
        if not decrypted_bytes: return encrypted_str
        intermediate_str = decrypted_bytes.decode('utf-8')
        key_int = 7361
        final_str = []
        for char in intermediate_str:
            val = (ord(char) - key_int - key_int) & 0xFFFF
            final_str.append(chr(val))
        return "".join(final_str)
    except: return encrypted_str

def process_json_structure(data, method):
    if isinstance(data, dict): return {k: process_json_structure(v, method) for k, v in data.items()}
    elif isinstance(data, list): return [process_json_structure(i, method) for i in data]
    elif isinstance(data, str):
        if method == "bamar": return decrypt_inner_bamar(data)
        elif method == "pnt_special": return decrypt_inner_pnt(data)
        elif method == "base64_recursive": return decrypt_inner_base64_recursive(data)
        return data
    return data

def perform_decryption(config_url, outer_key, outer_delta_raw, method):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    req = urllib.request.Request(config_url, headers=headers)
    with urllib.request.urlopen(req) as response:
        enc_base64 = response.read().decode('utf-8').replace('\n', '').replace('\r', '').strip()
        
    outer_delta = parse_delta(outer_delta_raw)
    enc_data = base64.b64decode(enc_base64)
    dec_bytes = decrypt_xxtea(enc_data, outer_key.encode('utf-8'), outer_delta)
    raw_json_str = dec_bytes.decode('utf-8', errors='ignore').replace('\\/', '/')
    json_obj = json.loads(raw_json_str)
    return {"AHLFLK": "Decrypted By @AHLFLK2025", **process_json_structure(json_obj, method)}

def get_vpn_configs():
    try: 
        return json.loads(VPN_CONFIGS) if VPN_CONFIGS else []
    except Exception as e: 
        print(f"[-] VPN Configs Parse Error: {str(e)}")
        return []

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
            created_at TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, 
            username TEXT, 
            role TEXT,
            token_balance INTEGER DEFAULT 0,
            expire_date TEXT DEFAULT '31/12/2099',
            last_known_role TEXT DEFAULT 'Normal User 🙂'
        )''')

        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'last_known_role' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_known_role TEXT DEFAULT 'Normal User 🙂'")
            
        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date, last_known_role) VALUES (?, ?, ?, ?, ?, ?)", 
                       (ADMIN_ID, 'Main_Admin', 'admin', -1, '31/12/2099', 'Main Admin 👑'))
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

                cursor.execute("SELECT tg_id, last_known_role FROM users")
                old_roles = {r[0]: r[1] for r in cursor.fetchall()}
                
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

                            clean_months = int(float(m_val)) if str(m_val).replace('.','',1).isdigit() else 0
                            c_at_str = str(c_at).strip()
                            
                            start_dt = None
                            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
                                try:
                                    start_dt = datetime.strptime(c_at_str, fmt)
                                    break
                                except ValueError:
                                    continue
                            
                            if not start_dt:
                                start_dt = datetime.utcnow() + timedelta(hours=7)
                                
                            exp_date = (start_dt + timedelta(days=clean_months * 30)).strftime("%d/%m/%Y")

                            u_id = int(col_a)
                            saved_lk_role = old_roles.get(u_id, 'Reseller Staff 💼')
                            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date, last_known_role) VALUES (?, ?, ?, ?, ?, ?)", 
                                           (u_id, clean_name, 'reseller', token_val, exp_date, saved_lk_role))
                        except: pass
                    else:
                        try:
                            clean_months = int(float(m_val)) if str(m_val).replace('.','',1).isdigit() else 1
                            final_creator = int(col_a) if col_a.isdigit() else ADMIN_ID
                            
                            cursor.execute("INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)", 
                                           (key_apk, k_str, str(clean_months), "m", final_creator, str(c_at).strip()))
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
# HELPER FUNCTIONS & ACCESS CONTROL
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

def is_vip_exists(target_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT target_id FROM auth_keys WHERE target_id = ?", (str(target_id).strip(),))
        res = cursor.fetchone()
    finally:
        conn.close()
    return res is not None

def is_reseller_exists(tg_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id FROM users WHERE tg_id = ? AND role = 'reseller'", (int(tg_id) if str(tg_id).isdigit() else 0,))
        res = cursor.fetchone()
    finally:
        conn.close()
    return res is not None

def is_access_valid(user_id):
    if is_admin(user_id): return True, "Main Admin 👑", "Unlimited ♾️"
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    current_date = datetime.utcnow() + timedelta(hours=7)
    try:
        cursor = conn.cursor()
        # Check Reseller Expiry
        cursor.execute("SELECT expire_date FROM users WHERE tg_id = ? AND role = 'reseller'", (user_id,))
        res = cursor.fetchone()
        if res:
            exp_date = res[0]
            fmt = "%d/%m/%Y" if '/' in exp_date else "%Y-%m-%d"
            try:
                if datetime.strptime(exp_date, fmt).date() >= current_date.date():
                    return True, "Reseller Staff 💼", exp_date
            except: pass
        
        # Check VIP Expiry
        cursor.execute("SELECT unit_val, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
        vip_res = cursor.fetchone()
        if vip_res:
            months = int(vip_res[0])
            c_at = vip_res[1]
            fmt = "%d/%m/%Y" if '/' in c_at else "%Y-%m-%d"
            try:
                exp_date_obj = datetime.strptime(c_at, fmt) + timedelta(days=months*30)
                if exp_date_obj.date() >= current_date.date():
                    return True, "VIP User ✨", exp_date_obj.strftime("%d/%m/%Y")
            except: pass
    finally:
        conn.close()
    return False, "Expired or Not Found", "-"

def check_and_update_user_role(user_id, current_role_str):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT last_known_role FROM users WHERE tg_id = ?", (user_id,))
        res = cursor.fetchone()
        if res:
            old_role = res[0]
            if old_role != current_role_str:
                cursor.execute("UPDATE users SET last_known_role = ? WHERE tg_id = ?", (current_role_str, user_id))
                conn.commit()
                return True
            return False
        else:
            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date, last_known_role) VALUES (?, ?, ?, ?, ?, ?)",
                           (user_id, 'User', 'normal', 0, '01/01/2000', current_role_str))
            conn.commit()
            return True
    finally:
        conn.close()

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

    valid, role_str, exp_date = is_access_valid(user_id)
    current_role_name = role_str if valid else "Expired or Normal"
    check_and_update_user_role(user_id, current_role_name)

    if not valid:
        welcome_text = f"👋 <b>{bot_name} မှ ကြိုဆိုပါတယ်!</b>\n\n" \
                       f"📊 <b>အကောင့်အခြေအနေ:</b>\n" \
                       f"👑 အဆင့်အတန်း: <b>Normal User 🙂 (သို့မဟုတ်) သက်တမ်းကုန်ဆုံး</b>\n" \
                       f"👤 အမည်: <b>{first_name}</b>\n" \
                       f"🆔 Telegram ID: <code>{user_id}</code>\n\n" \
                       f"🚫 <b>ခွင့်ပြုချက်မရှိပါ (သို့မဟုတ်) သက်တမ်းကုန်ဆုံးနေပါသည်။</b>\n\n" \
                       f"⚠️ သင့် VIP သက်တမ်းကုန်ဆုံးသွားပြီဖြစ်သဖြင့် အသုံးပြု၍မရတော့ပါ။ Admin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။"
        bot.reply_to(message, welcome_text, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
        return bot.send_message(message.chat.id, "👇 Admin အား ဆက်သွယ်ရန် ခလုတ်ကိုနှိပ်ပါ-", reply_markup=get_admin_contact_markup())

    tokens_line = ""
    if is_admin(user_id):
        tokens_line = "🪙 Credit Balance: <code>Unlimited ♾️</code>\n"
    elif is_reseller(user_id):
        tokens_line = f"🪙 Credit Balance: <code>{get_reseller_tokens(user_id)}</code> Tokens\n"

    welcome_text = f"👋 <b>{bot_name} မှ ကြိုဆိုပါတယ်!</b>\n\n" \
                   f"📊 <b>အကောင့်အခြေအနေ:</b>\n" \
                   f"👑 အဆင့်အတန်း: <b>{role_str}</b>\n" \
                   f"👤 အမည်: <b>{first_name}</b>\n" \
                   f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                   f"{tokens_line}" \
                   f"⏳ သက်တမ်းကုန်ဆုံးမည့်ရက်: <code>{exp_date}</code>\n\n" \
                   f"💡 အောက်ပါ Panel Keyboard ကို အသုံးပြုပြီး လုပ်ငန်းများကို ဆောင်ရွက်နိုင်ပါသည်။"    
    bot.reply_to(message, welcome_text, reply_markup=get_menu_markup(user_id), parse_mode="HTML")

# ==========================================
# MY BALANCE BUTTON ENGINE
# ==========================================
@bot.message_handler(func=lambda msg: msg.text == "💰 My Balance")
def handle_balance_click(message):
    user_id = message.from_user.id
    pull_data_from_google_sheet()
    
    valid, role_str, exp_date = is_access_valid(user_id)
    
    if is_admin(user_id):
        res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
              f"👑 အဆင့်အတန်း: <b>Main Admin 👑</b>\n" \
              f"🆔 TG ID: <code>{user_id}</code>\n" \
              f"🪙 လက်ကျန် Credit: <code>Unlimited ♾️</code>"
        return bot.reply_to(message, res, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
        
    elif is_reseller(user_id):
        current_tokens = get_reseller_tokens(user_id)
        if not valid:
            res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
                  f"👑 အဆင့်အတန်း: <b>Reseller Staff 💼</b>\n" \
                  f"🆔 TG ID: <code>{user_id}</code>\n" \
                  f"🪙 လက်ကျန် Credit: <code>{current_tokens} Tokens</code>\n" \
                  f"⏳ သက်တမ်း: <code>{exp_date} (Expired)</code>\n\n" \
                  f"⚠️ သင့်အကောင့် သက်တမ်းကုန်ဆုံးသွားပြီဖြစ်သဖြင့် အသုံးပြု၍မရတော့ပါ။ Admin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။"
            bot.reply_to(message, res, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
            return bot.send_message(message.chat.id, "👇 Admin အား ဆက်သွယ်ရန် ခလုတ်ကိုနှိပ်ပါ-", reply_markup=get_admin_contact_markup())
        else:
            res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
                  f"👑 အဆင့်အတန်း: <b>Reseller Staff 💼</b>\n" \
                  f"🆔 TG ID: <code>{user_id}</code>\n" \
                  f"🪙 လက်ကျန် Credit: <code>{current_tokens} Tokens</code>\n" \
                  f"⏳ သက်တမ်းကုန်ဆုံးရက်: <code>{exp_date}</code>"
            return bot.reply_to(message, res, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
            
    else:
        if not valid:
            res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
                  f"👑 အဆင့်အတန်း: <b>VIP User ✨ (Expired)</b>\n" \
                  f"🆔 TG ID: <code>{user_id}</code>\n" \
                  f"⏳ သက်တမ်း: <code>Expired (ကုန်ဆုံး)</code>\n\n" \
                  f"⚠️ သင့် VIP သက်တမ်းကုန်ဆုံးသွားပြီဖြစ်သဖြင့် အသုံးပြု၍မရတော့ပါ။ Admin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။"
            bot.reply_to(message, res, reply_markup=get_menu_markup(user_id), parse_mode="HTML")
            return bot.send_message(message.chat.id, "👇 Admin အား ဆက်သွယ်ရန် ခလုတ်ကိုနှိပ်ပါ-", reply_markup=get_admin_contact_markup())
        else:
            res = f"💰 <b>သင့်ရဲ့ လက်ကျန် Balance အခြေအနေ:</b>\n\n" \
                  f"👑 အဆင့်အတန်း: <b>VIP User ✨</b>\n" \
                  f"🆔 TG ID: <code>{user_id}</code>\n" \
                  f"⏳ သက်တမ်းကုန်ဆုံးရက်: <code>{exp_date}</code>"
            return bot.reply_to(message, res, reply_markup=get_menu_markup(user_id), parse_mode="HTML")

# ==========================================
# GENERAL PANEL BUTTONS & DECRYPT
# ==========================================
@bot.message_handler(func=lambda msg: any(msg.text in row for row in ADMIN_BUTTONS + RESELLER_BUTTONS + VIP_ACTIVE_BUTTONS + USER_BUTTONS))
def handle_menu_clicks(message):
    user_id = message.from_user.id
    text = message.text
    pull_data_from_google_sheet()

    valid, role_str, exp_date = is_access_valid(user_id)

    if text == "🌐 VPN Decrypt List":
        current_role_name = role_str if valid else "Expired or Normal"
        check_and_update_user_role(user_id, current_role_name)

        if not valid:
            bot.reply_to(message, "🚫 <b>ခွင့်ပြုချက် မရှိပါ (သို့မဟုတ်) သက်တမ်းကုန်နေပါသည်။</b>\n\n⚠️ သင့် VIP သက်တမ်းကုန်ဆုံးသွားပြီဖြစ်၍ Decrypt List ကို ပိတ်ထားပါသည်။", parse_mode="HTML")
            return bot.send_message(message.chat.id, "👇 Admin အား ဆက်သွယ်ရန် ခလုတ်ကိုနှိပ်ပါ-", reply_markup=get_admin_contact_markup())
            
        configs = get_vpn_configs()

        config_text = f"--- <b>Decrypt Configurations List</b> ---\n" \
                      f"🛠️ Decrypt လုပ်ချင်တဲ့ VPN Config ကို\n" \
                      f"💡 အောက်ပါ Panel မှာ ရွေးချယ်ပေးပါ-"

        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(f"[{i}] {vpn['name']}", callback_data=f"dec_{vpn['id']}") for i, vpn in enumerate(configs, 1)]
        for i in range(0, len(buttons), 2):
            markup.row(*buttons[i:i+2])

        return bot.reply_to(message, config_text, reply_markup=markup, parse_mode="HTML")

    if text == "💰 My Balance":
        return handle_balance_click(message)

    if text in ["➕ Add VIP User", "🔑 My VIP Users", "✏️ Edit VIP", "🗑 Delete VIP", "👤 Create Reseller", "📊 Reseller List", "✏️ Edit Reseller", "🗑 Delete Reseller", "🌐 View All VIPs"]:

        if not is_reseller(user_id):
            return bot.reply_to(message, "❌ <b>ခွင့်ပြုချက် မရှိပါ!</b>", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

        if not valid and not is_admin(user_id):
            return bot.reply_to(message, "⚠️ သင့်အကောင့် သက်တမ်းကုန်ဆုံးသွားပြီဖြစ်၍\nဆက်လက်အသုံးပြု၍ မရတော့ပါ။\nAdmin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

    if text == "➕ Add VIP User":
        user_states[user_id] = "ADD_VIP_ID"
        bot.reply_to(message, "👤 ထည့်သွင်းမည့် VIP အသုံးပြုသူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "✏️ Edit VIP":
        user_states[user_id] = "EDIT_VIP_ID"
        bot.reply_to(message, "✏️ ပြင်ဆင်မည့် VIP အသုံးပြုသူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🗑 Delete VIP":
        user_states[user_id] = "DEL_VIP_ID"
        bot.reply_to(message, "🗑 ဖျက်ထုတ်မည့် VIP အသုံးပြုသူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "👤 Create Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "ADD_RES_ID"
        bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "✏️ Edit Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "EDIT_RES_ID"
        bot.reply_to(message, "✏️ ပြင်ဆင်မည့် Reseller ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🗑 Delete Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "DEL_RES_ID"
        bot.reply_to(message, "🗑 ဖျက်ထုတ်မည့် Reseller ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")
        
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
            res += f"🆔 Telegram ID: <code>{r[0]}</code> | 👤 Name: <code>{r[1]}</code> | 📅 Expired: <code>{exp}</code>\n"
        bot.reply_to(message, res, parse_mode="HTML")

    elif text == "📊 Reseller List":
        if not is_admin(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role = 'reseller' AND tg_id != ''")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 Reseller စာရင်း မရှိသေးပါ။")
        res = f"📊 <b>Reseller စာရင်းအားလုံး ({len(rows)} ဦး):</b>\n\n"
        for r in rows:
            tk_display = "Unlimited ♾️" if r[2] == -1 else f"{r[2]} Tk"
            res += f"🆔 TG ID: <code>{r[0]}</code> | 👤 Name: {r[1]}\n🪙 Token: {tk_display} | ⏳ Expired: {r[3]}\n\n"
        bot.reply_to(message, res, parse_mode="HTML")

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
            res += f"🆔 Telegram ID: <code>{r[0]}</code> | 👤 Name: <code>{r[1]}</code> | 📅 Expired: <code>{exp}</code>\n"
        bot.reply_to(message, res, parse_mode="HTML")

# ==========================================
# DECRYPT CALLBACK HANDLER (FIXED)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('dec_'))
def handle_decrypt_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    pull_data_from_google_sheet()
    valid, _, _ = is_access_valid(user_id)
    
    if not valid:
        bot.answer_callback_query(call.id)

        bot.send_message(
            chat_id, 
            "🚫 <b>သင်သည် သက်တမ်း ကုန်ဆုံးသွားပြီ ဖြစ်သဖြင့် ဤ Config အား အသုံးပြု၍ မရတော့ပါ။</b>\n\n" \
            "ကျေးဇူးပြု၍ သက်တမ်းတိုးရန် အောက်ပါ ခလုတ်မှတစ်ဆင့် Admin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။", 
            parse_mode="HTML",
            reply_markup=get_admin_contact_markup()
        )
        return

    vpn_id = call.data.split('_')[1]
    configs = get_vpn_configs()
    selected_vpn = next((item for item in configs if item["id"] == vpn_id), None)
    if not selected_vpn: 
        bot.answer_callback_query(call.id, "❌ Config မတွေ့ရှိပါ။")
        return

    bot.answer_callback_query(call.id, "🔄 Processing...")

    status_msg = bot.send_message(chat_id, f"⏳ <b>{selected_vpn['name']} Config ကို Decrypt လုပ်နေပါတယ်...</b>", parse_mode="HTML")
    try:
        result_json = perform_decryption(selected_vpn["url"], selected_vpn["outer_key"], selected_vpn["outer_delta"], selected_vpn["method"])
        temp_file_path = f"{vpn_id}_decrypted.json"
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, indent=4, ensure_ascii=False)
            
        bot.delete_message(chat_id, status_msg.message_id)
        with open(temp_file_path, 'rb') as doc:
            bot.send_document(chat_id, doc, caption=f"✅ <b>{selected_vpn['name']} Config Decrypted Successfully!</b>", parse_mode="HTML")
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
    except Exception as e:
        bot.delete_message(chat_id, status_msg.message_id)
        bot.send_message(chat_id, f"❌ <b>Error:</b> <code>{str(e)}</code>\nပြဿနာ တစ်စုံတစ်ရာရှိခဲ့ပါက Admin ထံသို့ မေးမြန်းနိုင်ပါသည်။", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

# ==========================================
# INPUT HANDLERS (STATE MANAGEMENT)
# ==========================================
@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) is not None)
def handle_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text.strip()
    
    valid, _, _ = is_access_valid(user_id)
    
    if not is_reseller(user_id):
        user_states[user_id] = None
        return bot.reply_to(message, "❌ <b>ခွင့်ပြုချက် မရှိပါ!</b>", reply_markup=get_menu_markup(user_id), parse_mode="HTML")

    if not valid and not is_admin(user_id):
        user_states[user_id] = None
        return bot.reply_to(message, "⚠️ သင့်အကောင့် သက်တမ်းကုန်ဆုံးသွားပြီဖြစ်၍\nဆက်လက်အသုံးပြု၍ မရတော့ပါ။\nAdmin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

    # --- ADD VIP ---
    if state == "ADD_VIP_ID":
        if is_vip_exists(text):
            vip_temp_data[user_id] = {"apk_id": text, "name": "Edit_VIP"}
            user_states[user_id] = "ADD_VIP_MONTH"
            bot.reply_to(message, "⚠️ <b>ယခု Telegram ID သည် VIP User ဖြစ်ပြီးသားဖြစ်ပါသဖြင့် သက်တမ်းတိုးမြှင့်ရန်</b>\n\nလအရေအတွက် (ဥပမာ- 1) ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")
        else:
            vip_temp_data[user_id] = {"apk_id": text}
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
                      f"Token ပြန်လည်ဖြည့်သွင်းရန် Admin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။"
            return bot.reply_to(message, err_msg, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            
        apk_id = vip_temp_data[user_id]["apk_id"]
        name = vip_temp_data[user_id]["name"]
        start_date = get_current_date_string()
        
        success = push_to_google_sheet("sync", users="", added_by=user_id, name=name, key=apk_id, start=start_date, month=months)
        if success:
            pull_data_from_google_sheet()
            if name == "Edit_VIP":
                bot.reply_to(message, f"✅ VIP အကောင့် သက်တမ်း တိုးမြှင့်ပြီးပါပြီ။\n🆔 Telegram ID: <code>{apk_id}</code>\n⏳ Expired: <code>{months}</code> Months", parse_mode="HTML")
            else:
                bot.reply_to(message, f"✅ VIP အကောင့် အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။\n🆔 Telegram ID: <code>{apk_id}</code>\n👤 VIP Name: <code>{name}</code>\n⏳ Expired: <code>{months}</code> Months", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Sheet သို့ ပို့ဆောင်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # --- EDIT VIP ---
    elif state == "EDIT_VIP_ID":
        if not is_vip_exists(text):
            user_states[user_id] = None
            return bot.reply_to(message, "❌ <b>အဆိုပါ Telegram ID အား ရှာမတွေ့ပါ။</b>", parse_mode="HTML")
        vip_temp_data[user_id] = {"apk_id": text}
        user_states[user_id] = "EDIT_VIP_MONTH"
        bot.reply_to(message, "✏️ တိုးမြှင့်မည့် <b>လအရေအတွက် (Month)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif state == "EDIT_VIP_MONTH":
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပေးပါ-")
        months = int(text)
        
        current_bal = get_reseller_tokens(user_id)
        if not deduct_reseller_tokens_by_days(user_id, months):
            user_states[user_id] = None
            err_msg = f"❌ <b>သင့်မှာ လုံလောက်တဲ့ Token မရှိပါ။</b>\n\n" \
                      f"⚠️ လိုအပ်သောပမာဏ: <code>{months}</code> Tokens\n" \
                      f"🪙 သင့်လက်ကျန်: <code>{current_bal}</code> Tokens\n\n" \
                      f"Token ပြန်လည်ဖြည့်သွင်းရန် Admin ထံသို့ ဆက်သွယ်နိုင်ပါသည်။"
            return bot.reply_to(message, err_msg, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            
        apk_id = vip_temp_data[user_id]["apk_id"]
        start_date = get_current_date_string()
        success = push_to_google_sheet("sync", users="", added_by=user_id, name="Edit_VIP", key=apk_id, start=start_date, month=months)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, "✅ VIP အကောင့် သက်တမ်း တိုးမြှင့်ပြီးပါပြီ။", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ ပြင်ဆင်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # --- DELETE VIP ---
    elif state == "DEL_VIP_ID":
        apk_id = text
        if not is_vip_exists(apk_id):
            user_states[user_id] = None
            return bot.reply_to(message, "❌ <b>အဆိုပါ Telegram ID အား ရှာမတွေ့ပါ။</b>", parse_mode="HTML")
            
        success = push_to_google_sheet("delete", users="", name="Delete", key=apk_id, start="", month=0)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ VIP Telegram ID: <code>{apk_id}</code> အား ဖျက်သိမ်းပြီးပါပြီ။", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ ဖျက်သိမ်းမှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # --- CREATE RESELLER ---
    elif state == "ADD_RES_ID":
        if not is_admin(user_id): return
        if is_reseller_exists(text):
            reseller_temp_data[user_id] = {"tg_id": text, "is_edit_mode": True}
            user_states[user_id] = "ADD_RES_TOKENS"
            bot.reply_to(message, "⚠️ <b>ယခု Telegram ID သည် Reseller ဖြစ်ပြီးသားဖြစ်ပါသဖြင့် တိုကင်တိုးမြှင့်ရန်</b>\n\nထပ်မံပေါင်းထည့်ပေးမည့် <b>Token ပမာဏ (Credits)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")
        else:
            reseller_temp_data[user_id] = {"tg_id": text, "is_edit_mode": False}
            user_states[user_id] = "ADD_RES_NAME"
            bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller အမည် ကို ရိုက်ထည့်ပေးပါ-")

    elif state == "ADD_RES_NAME":
        if not is_admin(user_id): return
        reseller_temp_data[user_id]["username"] = text
        user_states[user_id] = "ADD_RES_TOKENS"
        bot.reply_to(message, "🪙 ထည့်သွင်းပေးမည့် <b>Token ပမာဏ (Credit)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif state == "ADD_RES_TOKENS":
        if not is_admin(user_id): return
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပေးပါ-")
        reseller_temp_data[user_id]["tokens"] = int(text)
        user_states[user_id] = "ADD_RES_MONTH"
        bot.reply_to(message, "⏳ သတ်မှတ်မည့် <b>လအရေအတွက် (Month)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif state == "ADD_RES_MONTH":
        if not is_admin(user_id): return
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းသီးသန့်ပဲ ရိုက်ထည့်ပေးပါ-")
        months = int(text)
        tokens = reseller_temp_data[user_id]["tokens"]
        r_id = reseller_temp_data[user_id]["tg_id"]
        is_edit_mode = reseller_temp_data[user_id].get("is_edit_mode", False)
        
        if is_edit_mode:
            r_name = "Update_Mode"
        else:
            r_name = reseller_temp_data[user_id]["username"] + "_Reseller"
            
        start_date = get_current_date_string()
        success = push_to_google_sheet("sync_reseller", users=r_id, name=r_name, key=str(tokens), start=start_date, month=0, reseller_months=months)
        
        if success:
            pull_data_from_google_sheet()
            if is_edit_mode:
                bot.reply_to(message, f"✅ Reseller (ID: <code>{r_id}</code>) အား Token <b>+{tokens} Tk</b> နှင့် သက်တမ်း <b>+{months} Months</b> ထပ်မံပေါင်းထည့်ပေးမှု အောင်မြင်ပါသည်။", parse_mode="HTML")
            else:
                bot.reply_to(message, f"✅ Reseller (ID: <code>{r_id}</code>) အား ဖန်တီးပြီးပါပြီ။\n🆔 Telegram ID: <code>{r_id}</code>\n👤 Name: {reseller_temp_data[user_id]['username']}\n🪙 Token Count: {tokens} Tk\n⏳ Expired: {months} Months", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Google Sheet ချက်ဆက်မှု လွဲချော်နေပါသည်။")
        user_states[user_id] = None

    # --- EDIT RESELLER ---
    elif state == "EDIT_RES_ID":
        if not is_admin(user_id): return
        if not is_reseller_exists(text):
            user_states[user_id] = None
            return bot.reply_to(message, "❌ <b>အဆိုပါ Reseller Telegram ID အား ရှာမတွေ့ပါ။</b>", parse_mode="HTML")
        
        reseller_temp_data[user_id] = {"tg_id": text, "is_edit_mode": True}
        user_states[user_id] = "ADD_RES_TOKENS"
        bot.reply_to(message, f"🆔 Reseller ID: <b>{text}</b>\n\n<b>ထပ်မံတိုးမြှင့် ပေါင်းထည့်ပေးမည့်</b> Token ပမာဏကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    # --- DELETE RESELLER ---
    elif state == "DEL_RES_ID":
        if not is_admin(user_id): return
        r_id = text
        if not is_reseller_exists(r_id):
            user_states[user_id] = None
            return bot.reply_to(message, "❌ <b>အဆိုပါ Reseller Telegram ID အား ရှာမတွေ့ပါ။</b>", parse_mode="HTML")
            
        success = push_to_google_sheet("delete_reseller", users=r_id, name="RESELLER_ACCOUNT", key="RESELLER_ACCOUNT", start="", month=0)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ Reseller (ID: <code>{r_id}</code>) အား ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ ဖျက်သိမ်းမှု လွဲချော်ခဲ့သည်။")
        user_states[user_id] = None

# ==========================================
# FLASK WEB SERVER RUNNERS
# ==========================================
@app.route('/')
def home():
    return "VPN Decrypt Bot is running smoothly!"

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
