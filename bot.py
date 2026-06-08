# # All-in-One Safe Decryptor & Telegram VIP Management Bot (Google Sheet Sync Mode)
# Py By @AHLFLK2025 (Integrated Google Sheet Sync from Bot2 & Decryption from Bot1)

# ==========================================
# 1. CONFIGURATION & CORE BOT SETUP
# ==========================================
import os
import re
import json
import struct
import base64
import sqlite3
import requests
import urllib.request
from threading import Thread
from datetime import datetime, timedelta
from flask import Flask, request, abort
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("TGC_ID")) if os.environ.get("TGC_ID") else None
 # Google Sheets Apps Script Web App URL
SCRIPT_URL = os.environ.get("SCRIPT_URL")
VPN_CONFIGS = os.environ.get("VPN_CONFIGS")
PUBLIC_URL = os.environ.get("PUBLIC_URL")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
vip_temp_data = {}

ADMIN_BUTTONS = [
    "🌐 VPN Decrypt List", "➕ Add VPN APK VIP", "✏️ Edit VPN APK", "🗑 Delete VPN APK", 
    "🌐 View All VIPs", "👤 Create Reseller", "📊 Reseller List", "✏️ Edit Reseller", 
    "🗑 Delete Reseller", "💰 My Balance"
]

RESELLER_BUTTONS = [
    "🌐 VPN Decrypt List", "➕ Add VPN APK VIP", "✏️ Edit VPN APK", "🗑 Delete VPN APK", 
    "🔑 My VIP Users", "💰 My Balance"
]

MENU_BUTTONS = ADMIN_BUTTONS + RESELLER_BUTTONS + ["💰 My Balance"]

def get_admin_contact_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
    return markup

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return "Bot is running with Google Sheet Sync Mode", 200

# ==========================================
# 2. CRYPTOGRAPHY & DECRYPTION ENGINE (XXTEA)
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
# 3. DATABASE INITIALIZATION & SHEET SYNC
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_keys (
                target_id TEXT,
                key_string TEXT,
                vpn_key TEXT PRIMARY KEY,
                unit_val INTEGER,
                created_at TEXT,
                added_by TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resellers (
                reseller_id TEXT PRIMARY KEY,
                username TEXT,
                credits INTEGER,
                created_by TEXT
            )
        """)
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
            cursor = conn.cursor()
            
            existing_vip_owners = {}
            cursor.execute("SELECT vpn_key, added_by FROM auth_keys WHERE added_by IS NOT NULL")
            for r in cursor.fetchall():
                existing_vip_owners[r[0]] = r[1]
                
            cursor.execute("DELETE FROM auth_keys")
            cursor.execute("DELETE FROM resellers")
            
            for row in data_list:
                t_id = row.get("Users")
                k_str = row.get("Name") or ""
                key_apk = row.get("Key") or ""
                c_at = row.get("Start") or ""
                m_val = row.get("Month") or 0
                
                if not t_id or t_id.strip() == "":
                    if "_Reseller" in str(k_str): t_id = "0" 
                    else: continue
                
                t_id = str(t_id).strip()
                
                if "_Reseller" in str(k_str):
                    try:
                        clean_name = str(k_str).replace("_Reseller", "").strip()
                        clean_months = int(float(m_val)) if '.' in str(m_val) else int(m_val)
                        cursor.execute("INSERT OR REPLACE INTO resellers VALUES (?, ?, ?, ?)", 
                                       (t_id, clean_name, clean_months, str(ADMIN_ID)))
                    except Exception as e: pass
                
                elif key_apk and key_apk != "RESELLER_ACCOUNT":
                    try:
                        clean_months = int(float(m_val)) if str(m_val).replace('.','',1).isdigit() else 1
                        owner_id = existing_vip_owners.get(str(key_apk).strip(), str(ADMIN_ID))
                        cursor.execute(
                            "INSERT OR REPLACE INTO auth_keys (target_id, key_string, vpn_key, unit_val, created_at, added_by) VALUES (?, ?, ?, ?, ?, ?)",
                            (t_id, str(k_str).strip(), str(key_apk).strip(), clean_months, str(c_at).strip(), str(owner_id))
                        )
                    except Exception as e: pass
                        
            conn.commit()
            conn.close()
    except Exception as e: pass

def push_to_google_sheet(action, users, name, key, start, month, is_reseller_mode=False):
    if not SCRIPT_URL: return False
    payload = {
        "action": "sync_reseller" if is_reseller_mode else action,
        "users": str(users),
        "name": str(name),
        "key": str(key),
        "start": str(start),
        "month": int(month)
    }
    try:
        res = requests.post(SCRIPT_URL, json=payload, timeout=15)
        return res.status_code == 200
    except:
        return False

# ==========================================
# 4. HELPER FUNCTIONS & AUTHENTICATION
# ==========================================
def is_admin(user_id):
    return int(user_id) == ADMIN_ID

def is_reseller(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT reseller_id FROM resellers WHERE reseller_id = ?", (str(user_id),))
        return cursor.fetchone() is not None
    except: return False
    finally: conn.close()

def get_reseller_tokens(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT credits FROM resellers WHERE reseller_id = ?", (str(user_id),))
        row = cursor.fetchone()
        return row[0] if row else 0
    except: return 0
    finally: conn.close()

def is_vpn_key_exists(vpn_key):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT vpn_key FROM auth_keys WHERE vpn_key = ?", (str(vpn_key).strip(),))
        return cursor.fetchone() is not None
    except: return False
    finally: conn.close()

def check_vip_status_by_tg(user_id):
    if int(user_id) == ADMIN_ID:
        return True, "Admin Unlimited", "Admin", False
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key_string, vpn_key, unit_val, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
        rows = cursor.fetchall()
        if rows:
            last_row = rows[-1]
            exp = get_expired_date_string(last_row[3], last_row[2])
            
            is_expired = False
            if exp != "သက်တမ်းမရှိပါ":
                try:
                    exp_date = datetime.strptime(exp, "%Y-%m-%d")
                    if datetime.now() > exp_date:
                        is_expired = True
                except: pass
                
            return True, exp, last_row[1], is_expired
        return False, "No VPN Account Locked", "မရှိပါ", True
    except: return False, "စစ်ဆေး၍မရပါ", "မရှိပါ", True
    finally: conn.close()

def get_expired_date_string(created_str, months_val):
    try:
        if not created_str or created_str.strip() == "":
            created_str = datetime.now().strftime("%Y-%m-%d")
        if "-" in created_str:
            dt = datetime.strptime(created_str.strip(), "%Y-%m-%d")
        elif "/" in created_str:
            dt = datetime.strptime(created_str.strip(), "%d/%m/%Y")
        else:
            dt = datetime.now()
        exp = dt + timedelta(days=int(months_val) * 30)
        return exp.strftime("%Y-%m-%d")
    except Exception:
        return "သက်တမ်းမရှိပါ"

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if is_admin(user_id):
        # Admin ခလုတ်များစီစဉ်မှု
        markup.row(types.KeyboardButton("🌐 VPN Decrypt List"))
        markup.row(types.KeyboardButton("➕ Add VPN APK VIP"), types.KeyboardButton("✏️ Edit VPN APK"))
        markup.row(types.KeyboardButton("🗑 Delete VPN APK"), types.KeyboardButton("🌐 View All VIPs"))
        markup.row(types.KeyboardButton("👤 Create Reseller"), types.KeyboardButton("📊 Reseller List"))
        markup.row(types.KeyboardButton("✏️ Edit Reseller"), types.KeyboardButton("🗑 Delete Reseller"))
        markup.row(types.KeyboardButton("💰 My Balance"))
    elif is_reseller(user_id):
        # Reseller ခလုတ်များစီစဉ်မှု
        markup.row(types.KeyboardButton("🌐 VPN Decrypt List"))
        markup.row(types.KeyboardButton("➕ Add VPN APK VIP"), types.KeyboardButton("✏️ Edit VPN APK"))
        markup.row(types.KeyboardButton("🗑 Delete VPN APK"), types.KeyboardButton("🔑 My VIP Users"))
        markup.row(types.KeyboardButton("💰 My Balance"))
    else:
        markup.add(types.KeyboardButton("💰 My Balance"))
    return markup

# ==========================================
# 5. TELEGRAM BOT HANDLERS & COMMANDS
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    pull_data_from_google_sheet()
    
    is_vip, exp_status, vpn_key, is_expired = check_vip_status_by_tg(user_id)
    first_name = message.from_user.first_name
    account_status = "ရိုးရိုးအသုံးပြုသူ"
    tokens_line = ""
    
    if is_admin(user_id): 
        account_status = "Main Admin 👑"
        exp_status = "Main Admin Account (Life_Time)"
    elif is_reseller(user_id):
        account_status = "Reseller Staff 💼"
        tokens = get_reseller_tokens(user_id)
        tokens_line = f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n"

    welcome_text = f"👋 <b>{bot.get_me().first_name} မှ ကြိုဆိုပါတယ်ဗျာ!</b>\n\n" \
                   f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                   f"👑 အဆင့်အတန်း: <b>{account_status}</b>\n" \
                   f"👤 အမည်: <b>{first_name}</b>\n" \
                   f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                   f"{tokens_line}" \
                   f"🔑 Last VPN Key: <code>{vpn_key}</code>\n" \
                   f"⏳ သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>\n\n" \
                   f"အောက်ပါ Panel Keyboard ကို အသုံးပြုပြီး ထိန်းချုပ်နိုင်ပါသည်။"
                   
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")

@bot.message_handler(func=lambda msg: msg.text in MENU_BUTTONS)
def handle_menu_clicks(message):
    user_id = message.from_user.id
    text = message.text
    user_states[user_id] = None
    
    if text == "💰 My Balance":
        pull_data_from_google_sheet()
        is_vip, exp_status, vpn_key, is_expired = check_vip_status_by_tg(user_id)
        first_name = message.from_user.first_name
        
        if is_admin(user_id):
            admin_text = f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                         f"👑 အဆင့်အတန်း: <b>Admin 👑</b>\n" \
                         f"👤 အမည်: <b>{first_name}</b>\n" \
                         f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                         f"🔑 Last VPN Key: <code>{vpn_key}</code>\n" \
                         f"⏳ သက်တမ်းကုန်မည့်ရက်: <code>Life_Time</code>"
            bot.reply_to(message, admin_text, parse_mode="HTML")
        elif is_reseller(user_id):
            tokens = get_reseller_tokens(user_id)
            reseller_text = f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                            f"👑 အဆင့်အတန်း: <b>Reseller Staff 💼</b>\n" \
                            f"👤 အမည်: <b>{first_name}</b>\n" \
                            f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                            f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n" \
                            f"🔑 Last VPN Key: <code>{vpn_key}</code>"
            if tokens <= 0:
                reseller_text += "\n\n🚫 <b>သင့်ရဲ့ Reseller Token ကုန်ဆုံးသွားပါပြီဗျာ။</b>"
                bot.reply_to(message, reseller_text, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            else:
                bot.reply_to(message, reseller_text, parse_mode="HTML")
        else:
            user_text = f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                        f"👑 အဆင့်အတန်း: <b>ရိုးရိုးအသုံးပြုသူ</b>\n" \
                        f"👤 အမည်: <b>{first_name}</b>\n" \
                        f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                        f"🔑 Last VPN Key: <code>{vpn_key}</code>\n" \
                        f"⏳ သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>"
            if is_expired or not is_vip:
                user_text += "\n\n⚠️ <b>သင့်အကောင့်သည် သက်တမ်းမရှိသေးပါ/ကုန်ဆုံးသွားပါပြီ။</b>"
                bot.reply_to(message, user_text, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            else:
                bot.reply_to(message, user_text, parse_mode="HTML")
        return

    # VPN Decrypt List ပြသခြင်းအပိုင်း
    if text == "🌐 VPN Decrypt List":
        pull_data_from_google_sheet()
        is_vip, exp_status, vpn_key, is_expired = check_vip_status_by_tg(user_id)
        if not is_admin(user_id) and (is_expired or not is_vip):
            return bot.reply_to(message, "🚫 <b>သင်သည် VIP စနစ်အသုံးပြုခွင့် မရှိသေးပါ (သို့မဟုတ်) သက်တမ်းကုန်သွားပါပြီ!</b>", reply_markup=get_admin_contact_markup(), parse_mode="HTML")
        
        configs = get_vpn_configs()
        if not configs:
            return bot.reply_to(message, "📭 Decrypt ပြုလုပ်ရန် Config မရှိသေးပါ။")
        
        welcome_text = f"👋 <b>{message.from_user.first_name}</b>\n" \
                       f"👑 Status: <b>VIP Authorized ✨</b>\n" \
                       f"⏳ Expiry: <code>{exp_status}</code>\n\n" \
                       f" decrypt ပြုလုပ်လိုသော Server အမျိုးအစားကို ရွေးချယ်ပါ -"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, cfg in enumerate(configs):
            markup.add(types.InlineKeyboardButton(text=cfg.get("name", f"Server {i+1}"), callback_data=f"dec_{i}"))
        bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="HTML")
        return

    # ကျန်ရှိသော Admin / Reseller Operations များ
    if not is_admin(user_id) and not is_reseller(user_id):
        return bot.reply_to(message, "🚫 ဤလုပ်ဆောင်ချက်ကို အသုံးပြုရန် ခွင့်ပြုချက်မရှိပါ။")

    if text == "➕ Add VPN APK VIP":
        if is_reseller(user_id) and get_reseller_tokens(user_id) <= 0:
            return bot.reply_to(message, "🚫 သင့်တွင် VIP ထည့်ရန် Credit/Token မလုံလောက်တော့ပါ။ Admin ထံ ဆက်သွယ်ပါ။")
        bot.reply_to(message, "👤 VIP အသစ်၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ -", parse_mode="HTML")
        user_states[user_id] = "ADD_VIP_TG"

    elif text == "✏️ Edit VPN APK":
        bot.reply_to(message, "✏️ ပြင်ဆင်မည့် VIP ရဲ့ <b>VPN Key (APK ID)</b> ကို ရိုက်ထည့်ပေးပါ -", parse_mode="HTML")
        user_states[user_id] = "EDIT_VIP_KEY"

    elif text == "🗑 Delete VPN APK":
        bot.reply_to(message, "🗑 ဖျက်ထုတ်မည့် VIP ရဲ့ <b>VPN Key (APK ID)</b> ကို ရိုက်ထည့်ပေးပါ -", parse_mode="HTML")
        user_states[user_id] = "DEL_VIP_KEY"

    elif text == "🔑 My VIP Users":
        view_reseller_vips(message)

    elif text == "🌐 View All VIPs":
        if not is_admin(user_id): return
        view_all_vips(message)

    elif text == "👤 Create Reseller":
        if not is_admin(user_id): return
        bot.reply_to(message, "👤 Reseller အသစ်၏ <b>Telegram ID</b> ကို ထည့်သွင်းပါ -", parse_mode="HTML")
        user_states[user_id] = "ADD_RS_TG"

    elif text == "📊 Reseller List":
        if not is_admin(user_id): return
        view_all_resellers(message)

    elif text == "✏️ Edit Reseller":
        if not is_admin(user_id): return
        bot.reply_to(message, "✏️ ပြင်ဆင်မည့် Reseller ရဲ့ <b>Telegram ID</b> ကို ထည့်သွင်းပါ -", parse_mode="HTML")
        user_states[user_id] = "EDIT_RS_TG"

    elif text == "🗑 Delete Reseller":
        if not is_admin(user_id): return
        bot.reply_to(message, "🗑 ဖြုတ်ချမည့် Reseller ရဲ့ <b>Telegram ID</b> ကို ထည့်သွင်းပါ -", parse_mode="HTML")
        user_states[user_id] = "DEL_RS_TG"

# ==========================================
# 6. INLINE CALLBACK HANDLER (DECRYPTION ENGINE)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("dec_"))
def handle_decryption_callback(call):
    user_id = call.from_user.id
    pull_data_from_google_sheet()
    is_vip, _, _, is_expired = check_vip_status_by_tg(user_id)
    
    if not is_admin(user_id) and (is_expired or not is_vip):
        bot.answer_callback_query(call.id, "🚫 သင့်အကောင့် သက်တမ်းကုန်ဆုံးသွားပါပြီ။", show_alert=True)
        return

    try:
        cfg_idx = int(call.data.split("_")[1])
        configs = get_vpn_configs()
        if cfg_idx >= len(configs):
            bot.answer_callback_query(call.id, "❌ Server ရှာမတွေ့ပါ။")
            return
        
        cfg = configs[cfg_idx]
        bot.answer_callback_query(call.id, "⏳ Decrypting... Please Wait...")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🔄 <i>Connecting to Server and Decrypting Payload...</i>", parse_mode="HTML")
        
        decrypted_data = perform_decryption(
            config_url=cfg.get("url"),
            outer_key=cfg.get("key"),
            outer_delta_raw=cfg.get("delta"),
            method=cfg.get("method")
        )
        
        formatted_json = json.dumps(decrypted_data, indent=2, ensure_ascii=False)
        filename = f"{cfg.get('name', 'Decrypted_Config')}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(formatted_json)
            
        with open(filename, "rb") as f:
            bot.send_document(
                call.message.chat.id, f, 
                caption=f"✅ <b>{cfg.get('name')} Decrypted Successfully!</b>\n👥 By @AHLFLK2025", 
                parse_mode="HTML"
            )
        try: os.remove(filename)
        except: pass
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ <b>Decryption Failed!</b>\nError: <code>{str(e)}</code>", parse_mode="HTML")

# ==========================================
# 7. CONVERSATION STATE FLOW (INPUTS PROCESS)
# ==========================================
@bot.message_handler(func=lambda msg: True)
def process_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text.strip()
    
    if not state: return

    # --- ADD VIP FLOW ---
    if state == "ADD_VIP_TG":
        vip_temp_data[user_id] = {"tg_id": text}
        bot.reply_to(message, "👤 VIP ရဲ့ <b>အမည် (Name)</b> ကို ထည့်သွင်းပါ -", parse_mode="HTML")
        user_states[user_id] = "ADD_VIP_NAME"
        
    elif state == "ADD_VIP_NAME":
        vip_temp_data[user_id]["name"] = text
        bot.reply_to(message, "🔑 VIP ရဲ့ <b>VPN Key (APK ID)</b> ကို ထည့်သွင်းပါ -", parse_mode="HTML")
        user_states[user_id] = "ADD_VIP_KEY"
        
    elif state == "ADD_VIP_KEY":
        if is_vpn_key_exists(text):
            bot.reply_to(message, "❌ ဤ VPN Key သည် စနစ်ထဲတွင် ရှိနှင့်ပြီးသားဖြစ်ပါသည်။ အခြားတစ်ခုထည့်ပါ။")
            return
        vip_temp_data[user_id]["key"] = text
        bot.reply_to(message, "📅 သက်တမ်းသတ်မှတ်မည့် <b>လအရေအတွက် (Months)</b> ကို ဂဏန်းသက်သက်ရိုက်ပါ (ဥပမာ: 1 သို့မဟုတ် 3) -", parse_mode="HTML")
        user_states[user_id] = "ADD_VIP_MONTH"
        
    elif state == "ADD_VIP_MONTH":
        if not text.isdigit():
            bot.reply_to(message, "⚠️ ဂဏန်းသက်သက်သာ ထည့်သွင်းပေးပါ -")
            return
        
        months = int(text)
        tg_id = vip_temp_data[user_id]["tg_id"]
        name = vip_temp_data[user_id]["name"]
        key_apk = vip_temp_data[user_id]["key"]
        start_date = datetime.now().strftime("%Y-%m-%d")
        
        bot.reply_to(message, "⏳ Google Sheets သို့ ချိတ်ဆက်သိမ်းဆည်းနေပါသည်...")
        
        success = push_to_google_sheet("insert", tg_id, name, key_apk, start_date, months)
        if success:
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            if is_reseller(user_id) and not is_admin(user_id):
                cursor.execute("UPDATE resellers SET credits = credits - 1 WHERE reseller_id = ?", (str(user_id),))
                # Reseller sheet update token deduction
                push_to_google_sheet("sync_reseller", user_id, f"{message.from_user.first_name}_Reseller", "RESELLER_ACCOUNT", start_date, get_reseller_tokens(user_id), is_reseller_mode=True)
            
            cursor.execute("INSERT OR REPLACE INTO auth_keys VALUES (?, ?, ?, ?, ?, ?)", 
                           (tg_id, name, key_apk, months, start_date, str(user_id)))
            conn.commit()
            conn.close()
            
            bot.reply_to(message, f"✅ <b>VIP User အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ။</b>\n\n🆔 TG ID: <code>{tg_id}</code>\n🔑 APK Key: <code>{key_apk}</code>\n📅 သက်တမ်း: <code>{months} လ</code>", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Google Sheet Sync ပျက်ကွက်ခဲ့ပါသည်။ စနစ်ကို ပြန်လည်စစ်ဆေးပါ။")
        user_states[user_id] = None

    # --- EDIT VIP FLOW ---
    elif state == "EDIT_VIP_KEY":
        if not is_vpn_key_exists(text):
            return bot.reply_to(message, "❌ ဤ VPN Key အား စနစ်ထဲတွင် ရှာမတွေ့ပါ။")
        vip_temp_data[user_id] = {"key": text}
        bot.reply_to(message, "✏️ သက်တမ်းတိုးမြှင့်မည့် <b>လအရေအတွက်အသစ်</b> ကို ထည့်ပါ -", parse_mode="HTML")
        user_states[user_id] = "EDIT_VIP_MONTH"
        
    elif state == "EDIT_VIP_MONTH":
        if not text.isdigit():
            return bot.reply_to(message, "⚠️ ဂဏန်းသာ ထည့်သွင်းပါ -")
        
        key_apk = vip_temp_data[user_id]["key"]
        months = int(text)
        
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string FROM auth_keys WHERE vpn_key = ?", (key_apk,))
        row = cursor.fetchone()
        
        if row:
            tg_id, name = row[0], row[1]
            start_date = datetime.now().strftime("%Y-%m-%d")
            bot.reply_to(message, "⏳ Sheet သို့ ပြင်ဆင်မှု ပို့လွှတ်နေသည်...")
            
            if push_to_google_sheet("update", tg_id, name, key_apk, start_date, months):
                cursor.execute("UPDATE auth_keys SET unit_val = ?, created_at = ? WHERE vpn_key = ?", (months, start_date, key_apk))
                conn.commit()
                bot.reply_to(message, f"✅ VPN Key: <code>{key_apk}</code> ကို {months} လ သို့ သက်တမ်းတိုးပြင်ဆင်ပြီးပါပြီ။", parse_mode="HTML")
            else:
                bot.reply_to(message, "❌ Sheet ပြင်ဆင်မှု မအောင်မြင်ပါ။")
        conn.close()
        user_states[user_id] = None

    # --- DELETE VIP FLOW ---
    elif state == "DEL_VIP_KEY":
        if not is_vpn_key_exists(text):
            return bot.reply_to(message, "❌ ဤ VPN Key အား စနစ်ထဲတွင် ရှာမတွေ့ပါ။")
        
        bot.reply_to(message, "⏳ Sheet မှ အချက်အလက်များ ဖျက်ထုတ်နေသည်...")
        if push_to_google_sheet("delete", "", "", text, "", 0):
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth_keys WHERE vpn_key = ?", (text,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑 VPN Key: <code>{text}</code> အား စနစ်မှ ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Sheet မှ ဒေတာဖျက်ထုတ်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # --- CREATE RESELLER FLOW ---
    elif state == "ADD_RS_TG":
        reseller_temp_data[user_id] = {"tg_id": text}
        bot.reply_to(message, "👤 Reseller ရဲ့ <b>အမည် (Name)</b> ကို ထည့်ပါ -", parse_mode="HTML")
        user_states[user_id] = "ADD_RS_NAME"
        
    elif state == "ADD_RS_NAME":
        reseller_temp_data[user_id]["name"] = text
        bot.reply_to(message, "🪙 ပေးအပ်မည့် <b>Credit/Token ပမာဏ</b> ကို ထည့်ပါ -", parse_mode="HTML")
        user_states[user_id] = "ADD_RS_CREDITS"
        
    elif state == "ADD_RS_CREDITS":
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းသာ ထည့်ပါ -")
        
        tg_id = reseller_temp_data[user_id]["tg_id"]
        name = reseller_temp_data[user_id]["name"] + "_Reseller"
        credits = int(text)
        
        bot.reply_to(message, "⏳ Reseller အချက်အလက်များကို Sheet သို့ သိမ်းဆည်းနေသည်...")
        if push_to_google_sheet("insert", tg_id, name, "RESELLER_ACCOUNT", datetime.now().strftime("%Y-%m-%d"), credits):
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO resellers VALUES (?, ?, ?, ?)", (tg_id, reseller_temp_data[user_id]["name"], credits, str(ADMIN_ID)))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ Reseller: <b>{reseller_temp_data[user_id]['name']}</b> ကို {credits} Tokens ဖြင့် ဖန်တီးပြီးပါပြီ။")
        else:
            bot.reply_to(message, "❌ Sheet သို့ Reseller သိမ်းဆည်းမှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

# ==========================================
# 8. DATA VIEW FUNCTIONS
# ==========================================
def view_reseller_vips(message):
    user_id = str(message.from_user.id)
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, vpn_key, unit_val, created_at FROM auth_keys WHERE added_by = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 သင်ကိုယ်တိုင် ထည့်သွင်းထားသော VIP အသုံးပြုသူ မရှိသေးပါ။")
    
    res = f"🔑 <b>သင့်ရဲ့ VIP အသုံးပြုသူ စာရင်း ({len(rows)} ဦး):</b>\n\n"
    for r in rows:
        exp_str = get_expired_date_string(r[4], r[3])
        res += f"🆔 TG ID: <code>{r[0]}</code>\n👤 အမည်: <code>{r[1]}</code>\n🔑 APK ID: <code>{r[2]}</code>\n📅 Expired: <code>{exp_str}</code>\n\n"
    bot.reply_to(message, res, parse_mode="HTML")

def view_all_vips(message):
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, vpn_key, unit_val, created_at FROM auth_keys")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 စနစ်ထဲတွင် VIP အသုံးပြုသူ မရှိသေးပါ။")
    
    res = f"🌐 <b>VIP အသုံးပြုသူ အားလုံးစာရင်း ({len(rows)} ဦး):</b>\n\n"
    for r in rows:
        exp_str = get_expired_date_string(r[4], r[3])
        res += f"🆔 TG ID: <code>{r[0]}</code>\n👤 အမည်: <code>{r[1]}</code>\n🔑 APK ID: <code>{r[2]}</code>\n📅 Expired: <code>{exp_str}</code>\n\n"
    bot.reply_to(message, res, parse_mode="HTML")

def view_all_resellers(message):
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT reseller_id, username, credits FROM resellers")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 Reseller စာရင်း မရှိသေးပါ။")
    
    res = f"📊 <b>Reseller အားလုံးစာရင်း ({len(rows)} ဦး):</b>\n\n"
    for r in rows:
        res += f"🆔 ID: <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | 🪙 <code>{r[2]}</code> Tokens\n"
    bot.reply_to(message, res, parse_mode="HTML")

# ==========================================
# 9. BOT EXECUTION
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_google_sheet()
    if PUBLIC_URL and BOT_TOKEN:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=PUBLIC_URL)
        except: pass
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
    else:
        bot.infinity_polling()
