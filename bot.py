# # All-in-One Safe Decryptor & Telegram VIP Management Bot (Google Sheet Sync Version)
# Py By @AHLFLK2025 (Fully Fixed Reseller Bypass Leak - Google Sheet Version)

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
SCRIPT_URL = os.environ.get("SCRIPT_URL")  # Google Apps Script Web App URL
VPN_CONFIGS = os.environ.get("VPN_CONFIGS")
PUBLIC_URL = os.environ.get("PUBLIC_URL")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
vip_temp_data = {}

MENU_BUTTONS = [
    "🌐 VPN Decrypt List", "➕ Add VIP User", "🔑 My VIP Users", 
    "✏️ Edit VIP", "🗑 Delete VIP", "👤 Create Reseller", 
    "📊 Reseller List", "✏️ Edit Reseller", "🗑 Delete Reseller", 
    "🌐 View All VIPs", "💰 My Balance"
]

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
    return "Decrypt & VPN VIP Sheet Bot is Active!", 200

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
# 3. DATABASE INITIALIZATION & GOOGLE SHEET SYNC
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        # auth_keys Structure aligned with Bot2 for Sheet Compatibility
        cursor.execute('''CREATE TABLE IF NOT EXISTS auth_keys (
            target_id TEXT,
            key_string TEXT, 
            vpn_key TEXT PRIMARY KEY,
            unit_val INTEGER, 
            created_at TEXT,
            added_by TEXT
        )''')
        
        # Resellers table from Bot2
        cursor.execute('''CREATE TABLE IF NOT EXISTS resellers (
            reseller_id TEXT PRIMARY KEY, 
            username TEXT, 
            credits INTEGER,
            created_by TEXT
        )''')
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
                    except: pass
                
                elif key_apk and key_apk != "RESELLER_ACCOUNT":
                    try:
                        clean_months = int(float(m_val)) if str(m_val).replace('.','',1).isdigit() else 1
                        owner_id = existing_vip_owners.get(str(key_apk).strip(), str(ADMIN_ID))
                        cursor.execute(
                            "INSERT OR REPLACE INTO auth_keys (target_id, key_string, vpn_key, unit_val, created_at, added_by) VALUES (?, ?, ?, ?, ?, ?)",
                            (t_id, str(k_str).strip(), str(key_apk).strip(), clean_months, str(c_at).strip(), str(owner_id))
                        )
                    except: pass
                        
            conn.commit()
            conn.close()
    except Exception as e: print(f"[-] Pull Sheet Error: {str(e)}")

def push_to_google_sheet(action, users, name, key, start, month, is_reseller_mode=False):
    if not SCRIPT_URL: return False
    payload = {
        "action": "sync_reseller" if is_reseller_mode else action,
        "users": str(users),
        "name": str(name),
        "key": str(key),
        "start": str(start),
        "month": int(month),
        "added_by": str(users) if is_reseller_mode else ""
    }
    try:
        res = requests.post(SCRIPT_URL, json=payload, timeout=15)
        return res.status_code == 200
    except:
        return False

# ==========================================
# 4. AUTHENTICATION & ROLE LOGIC
# ==========================================
def is_admin(user_id):
    return int(user_id) == ADMIN_ID

def is_reseller(user_id):
    if int(user_id) == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT reseller_id FROM resellers WHERE reseller_id = ?", (str(user_id),))
        return cursor.fetchone() is not None
    except: return False
    finally: conn.close()

def get_reseller_tokens(user_id):
    if int(user_id) == ADMIN_ID: return 999999
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT credits FROM resellers WHERE reseller_id = ?", (str(user_id),))
        row = cursor.fetchone()
        return row[0] if row else 0
    except: return 0
    finally: conn.close()

def check_vip_status(user_id):
    """ Returns (is_vip, status_string/expire_date) """
    if int(user_id) == ADMIN_ID: return True, "Unlimited (Admin)"
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key_string, vpn_key, unit_val, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
        rows = cursor.fetchall()
        if rows:
            last_row = rows[-1]
            exp = get_expired_date_string(last_row[3], last_row[2])
            if exp != "သက်တမ်းမရှိပါ":
                try:
                    exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
                    if datetime.now().date() > exp_date:
                        return False, "Expired"
                except: pass
            return True, exp
        return False, "Not VIP"
    except: return False, "Error Check"
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
    except:
        return "သက်တမ်းမရှိပါ"

# ==========================================
# 5. TELEGRAM INTERFACE & KEYBOARDS
# ==========================================
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    is_vip, _ = check_vip_status(user_id)
    
    if is_admin(user_id):
        markup.row(types.KeyboardButton("🌐 VPN Decrypt List"))
        markup.row(types.KeyboardButton("➕ Add VIP User"), types.KeyboardButton("🔑 My VIP Users"))
        markup.row(types.KeyboardButton("✏️ Edit VIP"), types.KeyboardButton("🗑 Delete VIP"))
        markup.row(types.KeyboardButton("👤 Create Reseller"), types.KeyboardButton("📊 Reseller List"))
        markup.row(types.KeyboardButton("✏️ Edit Reseller"), types.KeyboardButton("🗑 Delete Reseller"))
        markup.row(types.KeyboardButton("🌐 View All VIPs"), types.KeyboardButton("💰 My Balance"))
    elif is_reseller(user_id):
        markup.row(types.KeyboardButton("🌐 VPN Decrypt List"))
        markup.row(types.KeyboardButton("➕ Add VIP User"), types.KeyboardButton("🔑 My VIP Users"))
        markup.row(types.KeyboardButton("✏️ Edit VIP"), types.KeyboardButton("🗑 Delete VIP"))
        markup.row(types.KeyboardButton("💰 My Balance"))
    else:
        if is_vip:
            markup.row(types.KeyboardButton("🌐 VPN Decrypt List"))
        markup.row(types.KeyboardButton("💰 My Balance"))
    return markup

# ==========================================
# 6. BOT HANDLERS & NAVIGATION
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    pull_data_from_google_sheet()
    
    try:
        bot_info = bot.get_me()
        bot_name = bot_info.first_name
    except:
        bot_name = "AHLFLK Decrypt VIP Bot"
        
    is_vip, exp_status = check_vip_status(user_id)
    first_name = message.from_user.first_name
    account_status = "ရိုးရိုးအသုံးပြုသူ"
    tokens_line = ""
    
    if is_admin(user_id): 
        account_status = "Main Admin 👑"
    elif is_reseller(user_id):
        account_status = "Reseller Staff 💼"
        tokens = get_reseller_tokens(user_id)
        tokens_line = f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n"

    welcome_text = f"👋 <b>{bot_name} မှ ကြိုဆိုပါတယ်ဗျာ!</b>\n\n" \
                   f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                   f"👑 အဆင့်အတန်း: <b>{account_status}</b>\n" \
                   f"👤 အမည်: <b>{first_name}</b>\n" \
                   f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                   f"{tokens_line}" \
                   f"⏳ VIP သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>\n\n" \
                   f"အောက်ပါ Panel Keyboard ကို အသုံးပြုပြီး ထိန်းချုပ်နိုင်ပါသည်။"
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")

@bot.message_handler(func=lambda msg: msg.text in MENU_BUTTONS)
def handle_menu_buttons(message):
    user_id = message.from_user.id
    user_states[user_id] = None
    text = message.text
    
    pull_data_from_google_sheet()
    is_vip, exp_status = check_vip_status(user_id)
    
    if text != "💰 My Balance" and not is_vip and not is_admin(user_id) and not is_reseller(user_id):
        return bot.reply_to(message, "🚫 <b>သင့်အကောင့်သည် သက်တမ်းကုန်ဆုံးသွားပြီဖြစ်၍ ဤခလုတ်အား အသုံးပြုနိုင်ခြင်းမရှိပါ။</b>\n\nAdmin ထံ ဆက်သွယ်ရန် ခလုတ်ကို နှိပ်ပါ။", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

    if text == "💰 My Balance":
        first_name = message.from_user.first_name
        if is_admin(user_id):
            res = f"📊 <b>Admin Info:</b>\n👑 Role: Admin\n🆔 ID: <code>{user_id}</code>\n⏳ Expired: <code>Life_Time</code>"
        elif is_reseller(user_id):
            tokens = get_reseller_tokens(user_id)
            res = f"📊 <b>Reseller Balance:</b>\n👤 Name: {first_name}\n🪙 Credits: <code>{tokens}</code> Tokens\n⏳ Expired: <code>{exp_status}</code>"
        else:
            res = f"📊 <b>User Status:</b>\n👤 Name: {first_name}\n🆔 ID: <code>{user_id}</code>\n⏳ VIP Expired: <code>{exp_status}</code>"
        bot.reply_to(message, res, parse_mode="HTML")

    elif text == "🌐 VPN Decrypt List":
        configs = get_vpn_configs()
        if not configs: return bot.reply_to(message, "📭 VPN Configurations မရှိသေးပါ။ Admin အား ပြောကြားပေးပါ။")
        markup = types.InlineKeyboardMarkup(row_width=1)
        for idx, cfg in enumerate(configs):
            markup.add(types.InlineKeyboardButton(text=cfg.get("name", f"Config {idx+1}"), callback_data=f"dec_{idx}"))
        bot.reply_to(message, "🌐 **ကျေးဇူးပြု၍ Decrypt ပြုလုပ်လိုသော VPN Config ကို ရွေးချယ်ပေးပါ-**", reply_markup=markup, parse_mode="Markdown")

    elif text == "➕ Add VIP User":
        if not is_reseller(user_id): return
        if get_reseller_tokens(user_id) <= 0 and not is_admin(user_id):
            return bot.reply_to(message, "❌ သင့်မှာ Token လက်ကျန် မလုံလောက်တော့ပါသဖြင့် VIP မထည့်ပေးနိုင်ပါ။")
        user_states[user_id] = "ADD_VIP_TG"
        bot.reply_to(message, "👤 ထည့်သွင်းမည့်သူ၏ **Telegram ID** ကို ပေးပို့ပါ-")

    elif text == "🔑 My VIP Users":
        if not is_reseller(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, vpn_key, unit_val, created_at FROM auth_keys WHERE added_by = ?", (str(user_id),))
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 သင်ကိုယ်တိုင် ထည့်သွင်းထားသော VIP အသုံးပြုသူ မရှိသေးပါ။")
        res = f"🔑 <b>သင့်ရဲ့ VIP အသုံးပြုသူ စာရင်း ({len(rows)} ဦး):</b>\n\n"
        for r in rows:
            exp_str = get_expired_date_string(r[4], r[3])
            res += f"🆔 TG ID: <code>{r[0]}</code> | 👤 အမည်: <code>{r[1]}</code>\n🔑 APK ID: <code>{r[2]}</code> | 📅 Expired: <code>{exp_str}</code>\n\n"
        bot.reply_to(message, res, parse_mode="HTML")

    elif text == "✏️ Edit VIP":
        if not is_reseller(user_id): return
        user_states[user_id] = "EDIT_VIP_KEY"
        bot.reply_to(message, "✏️ ပြင်ဆင်လိုသော VIP အကောင့်၏ **APK Key (သို့မဟုတ်) TG ID** ကို ပေးပို့ပါ-")

    elif text == "🗑 Delete VIP":
        if not is_reseller(user_id): return
        user_states[user_id] = "DEL_VIP_KEY"
        bot.reply_to(message, "🗑 ဖျက်ထုတ်လိုသော VIP အကောင့်၏ **APK Key (သို့မဟုတ်) TG ID** ကို ပေးပို့ပါ-")

    elif text == "👤 Create Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "CREATE_R_ID"
        bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller Staff ၏ **Telegram ID** ကို ရိုက်ထည့်ပေးပါ-")

    elif text == "📊 Reseller List":
        if not is_admin(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT reseller_id, username, credits FROM resellers")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 Reseller Staff မရှိသေးပါ။")
        res = "💼 <b>Reseller Staff အားလုံးစာရင်း:</b>\n\n"
        for r in rows: res += f"🆔 <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | 🪙 <code>{r[2]}</code> Tokens\n"
        bot.reply_to(message, res, parse_mode="HTML")

    elif text == "✏️ Edit Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "EDIT_R_ID"
        bot.reply_to(message, "✏️ Token ပြင်ဆင်လိုသော Reseller Staff ၏ **Telegram ID** ကို ပေးပို့ပါ-")

    elif text == "🗑 Delete Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "DEL_R_ID"
        bot.reply_to(message, "🗑 ဖြုတ်ချလိုသော Reseller Staff ၏ **Telegram ID** ကို ပေးပို့ပါ-")

    elif text == "🌐 View All VIPs":
        if not is_admin(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, vpn_key, unit_val, created_at FROM auth_keys")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 VIP အကောင့် လုံးဝမရှိသေးပါ။")
        res = f"🌐 <b>VIP အသုံးပြုသူ အားလုံးစာရင်း ({len(rows)} ဦး):</b>\n\n"
        for r in rows:
            exp_str = get_expired_date_string(r[4], r[3])
            res += f"🆔 <code>{r[0]}</code> | 🔑 <code>{r[2]}</code> | 📅 <code>{exp_str}</code>\n"
        bot.reply_to(message, res, parse_mode="HTML")

# ==========================================
# 7. INLINE CALLBACK FOR DECRYPTION
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("dec_"))
def callback_decrypt(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id, "Processing Decryption...")
    idx = int(call.data.split("_")[1])
    configs = get_vpn_configs()
    if idx >= len(configs): return bot.send_message(call.message.chat.id, "❌ Invalid Selection.")
    
    cfg = configs[idx]
    try:
        dec_obj = perform_decryption(cfg["url"], cfg["key"], cfg["delta"], cfg["method"])
        pretty_json = json.dumps(dec_obj, indent=2, ensure_ascii=False)
        filename = f"Decrypted_{cfg.get('name','Config')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(pretty_json)
        with open(filename, "rb") as f:
            bot.send_document(call.message.chat.id, f, caption=f"✅ **{cfg.get('name','Config')}** အား အောင်မြင်စွာ Decrypt လုပ်ပြီးပါပြီ။\nPowered By @AHLFLK2025")
        os.remove(filename)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Decryption Failed: {str(e)}")

# ==========================================
# 8. STEP-BY-STEP CONVERSATION FLOW (STATE SYSTEM)
# ==========================================
@bot.message_handler(func=lambda msg: True)
def handle_state_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state: return

    # --- ADD VIP USER PROCESS ---
    if state == "ADD_VIP_TG":
        vip_temp_data[user_id] = {"tg_id": message.text.strip()}
        user_states[user_id] = "ADD_VIP_NAME"
        bot.reply_to(message, "👤 အသုံးပြုသူအမည် (Name) ကို ရိုက်ထည့်ပါ-")
    
    elif state == "ADD_VIP_NAME":
        vip_temp_data[user_id]["name"] = message.text.strip()
        user_states[user_id] = "ADD_VIP_KEY"
        bot.reply_to(message, "🔑 APK Key (Unique VPN Key) ကို ရိုက်ထည့်ပါ-")

    elif state == "ADD_VIP_KEY":
        v_key = message.text.strip()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT vpn_key FROM auth_keys WHERE vpn_key = ?", (v_key,))
        dup = cursor.fetchone()
        conn.close()
        if dup: return bot.reply_to(message, "❌ ဤ APK Key သည် စနစ်ထဲတွင် ရှိနှင့်ပြီးသားဖြစ်ပါသည်။ အခြားတစ်ခုထည့်ပါ။")
        
        vip_temp_data[user_id]["vpn_key"] = v_key
        user_states[user_id] = "ADD_VIP_MONTH"
        bot.reply_to(message, "⏳ သက်တမ်းမည်မျှထားရှိမည်နည်း? (ဥပမာ- 1 ဆိုလျှင် 1 လ၊ 12 ဆိုလျှင် 1 နှစ်)-")

    elif state == "ADD_VIP_MONTH":
        if not message.text.isdigit(): return bot.reply_to(message, "🔢 ဂဏန်းသီးသန့်သာ ထည့်သွင်းပေးပါ-")
        months = int(message.text)
        
        # Credit/Token Check
        if not is_admin(user_id):
            current_tokens = get_reseller_tokens(user_id)
            if current_tokens < months:
                return bot.reply_to(message, f"❌ သင့်မှာ Token {current_tokens} သာရှိသဖြင့် {months} လစာ မထည့်ပေးနိုင်ပါ။")

        vdata = vip_temp_data[user_id]
        now_str = datetime.now().strftime("%Y-%m-%d")
        
        # Push to Google Sheet
        success = push_to_google_sheet("sync", vdata["tg_id"], vdata["name"], vdata["vpn_key"], now_str, months)
        if success:
            # Reseller Token Deduct internally by syncing via sheet
            if not is_admin(user_id):
                push_to_google_sheet("sync_reseller", str(user_id), message.from_user.first_name + "_Reseller", "RESELLER_ACCOUNT", now_str, -months, is_reseller_mode=True)
            
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ VIP အကောင့် ထည့်သွင်းမှု အောင်မြင်ပြီး Google Sheet သို့ စင့်ခ်လုပ်ပြီးပါပြီ။", reply_markup=get_main_keyboard(user_id))
        else:
            bot.reply_to(message, "❌ Google Sheet သို့ ပို့ဆောင်မှု မအောင်မြင်ပါ။ SCRIPT_URL အား စစ်ဆေးပါ။")
        user_states[user_id] = None

    # --- EDIT VIP PROCESS ---
    elif state == "EDIT_VIP_KEY":
        search_val = message.text.strip()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, vpn_key, added_by FROM auth_keys WHERE vpn_key = ? OR target_id = ?", (search_val, search_val))
        row = cursor.fetchone()
        conn.close()
        
        if not row: return bot.reply_to(message, "❌ ရှာမတွေ့ပါ။ မှန်ကန်စွာ ပြန်ရိုက်ပါ။")
        if not is_admin(user_id) and row[3] != str(user_id):
            return bot.reply_to(message, "🚫 ဤအကောင့်သည် သင်ဖန်တီးထားခြင်းမဟုတ်သဖြင့် ပြင်ဆင်ခွင့်မရှိပါ။")
            
        vip_temp_data[user_id] = {"tg_id": row[0], "name": row[1], "vpn_key": row[2]}
        user_states[user_id] = "EDIT_VIP_MONTH"
        bot.reply_to(message, f"✏️ အကောင့်တွေ့ရှိပါပြီ: <b>{row[1]}</b>\nထပ်မံတိုးမြှင့်လိုသော လ အား ရိုက်ထည့်ပါ (ထပ်ပေါင်းမည့်လ)-", parse_mode="HTML")

    elif state == "EDIT_VIP_MONTH":
        if not message.text.isdigit(): return bot.reply_to(message, "🔢 ဂဏန်းသာ ထည့်ပါ-")
        months = int(message.text)
        
        if not is_admin(user_id) and get_reseller_tokens(user_id) < months:
            return bot.reply_to(message, "❌ Token မလုံလောက်ပါ။")
            
        vdata = vip_temp_data[user_id]
        now_str = datetime.now().strftime("%Y-%m-%d")
        
        success = push_to_google_sheet("sync", vdata["tg_id"], vdata["name"], vdata["vpn_key"], now_str, months)
        if success:
            if not is_admin(user_id):
                push_to_google_sheet("sync_reseller", str(user_id), message.from_user.first_name + "_Reseller", "RESELLER_ACCOUNT", now_str, -months, is_reseller_mode=True)
            pull_data_from_google_sheet()
            bot.reply_to(message, "✅ VIP သက်တမ်း တိုးမြှင့်ခြင်း အောင်မြင်ပါသည်။", reply_markup=get_main_keyboard(user_id))
        else:
            bot.reply_to(message, "❌ Google Sheet သို့ စင့်ခ်လုပ်ရန် ပျက်ကွက်သည်။")
        user_states[user_id] = None

    # --- DELETE VIP PROCESS ---
    elif state == "DEL_VIP_KEY":
        search_val = message.text.strip()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, vpn_key, added_by FROM auth_keys WHERE vpn_key = ? OR target_id = ?", (search_val, search_val))
        row = cursor.fetchone()
        conn.close()
        
        if not row: return bot.reply_to(message, "❌ ရှာမတွေ့ပါ။")
        if not is_admin(user_id) and row[3] != str(user_id):
            return bot.reply_to(message, "🚫 ဖျက်ခွင့်မရှိပါ။")
            
        success = push_to_google_sheet("delete", row[0], row[1], row[2], "", 0)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"🗑 VIP အကောင့်: {row[1]} အား Google Sheet မှ ဖျက်ထုတ်ပြီးပါပြီ။", reply_markup=get_main_keyboard(user_id))
        else:
            bot.reply_to(message, "❌ ဖျက်ရန် Google Sheet ပျက်ကွက်သည်။")
        user_states[user_id] = None

    # --- CREATE RESELLER PROCESS (ADMIN ONLY) ---
    elif state == "CREATE_R_ID":
        reseller_temp_data[user_id] = {"r_id": message.text.strip()}
        user_states[user_id] = "CREATE_R_NAME"
        bot.reply_to(message, "👤 Reseller ရဲ့ အမည် (Name) ကို ထည့်ပါ-")

    elif state == "CREATE_R_NAME":
        reseller_temp_data[user_id]["name"] = message.text.strip() + "_Reseller"
        user_states[user_id] = "CREATE_R_TOKEN"
        bot.reply_to(message, "🪙 သတ်မှတ်ပေးမည့် Token အရေအတွက်ကို ရိုက်ထည့်ပါ-")

    elif state == "CREATE_R_TOKEN":
        if not message.text.isdigit(): return bot.reply_to(message, "🔢 ဂဏန်းသာ ထည့်ပါ-")
        tokens = int(message.text)
        rdata = reseller_temp_data[user_id]
        
        success = push_to_google_sheet("sync_reseller", rdata["r_id"], rdata["name"], "RESELLER_ACCOUNT", datetime.now().strftime("%Y-%m-%d"), tokens, is_reseller_mode=True)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, "✅ Reseller Staff ဖန်တီးမှု အောင်မြင်ပြီး Sheet သို့ သိမ်းဆည်းပြီးပါပြီ။", reply_markup=get_main_keyboard(user_id))
        else:
            bot.reply_to(message, "❌ Google Sheet သို့ ပို့ဆောင်ရန် ပျက်ကွက်သည်။")
        user_states[user_id] = None

    # --- EDIT RESELLER PROCESS ---
    elif state == "EDIT_R_ID":
        r_id = message.text.strip()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT reseller_id, username FROM resellers WHERE reseller_id = ?", (r_id,))
        row = cursor.fetchone()
        conn.close()
        if not row: return bot.reply_to(message, "❌ ဤ Reseller ID အား ရှာမတွေ့ပါ။")
        
        reseller_temp_data[user_id] = {"r_id": row[0], "name": row[1] + "_Reseller"}
        user_states[user_id] = "EDIT_R_TOKEN"
        bot.reply_to(message, f"💼 Reseller: {row[1]}\nပေါင်းထည့်လိုသော Token အရေအတွက် ရိုက်ထည့်ပါ (နှုတ်လိုပါက အနှုတ်လက္ခဏာ - ခံထည့်ပါ)-")

    elif state == "EDIT_R_TOKEN":
        try:
            tokens = int(message.text.strip())
        except:
            return bot.reply_to(message, "🔢 ဂဏန်းပုံစံသာ ရိုက်ထည့်ပေးပါ-")
            
        rdata = reseller_temp_data[user_id]
        success = push_to_google_sheet("sync_reseller", rdata["r_id"], rdata["name"], "RESELLER_ACCOUNT", "", tokens, is_reseller_mode=True)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, "✅ Reseller Token ပြင်ဆင်မှု အောင်မြင်ပါသည်။", reply_markup=get_main_keyboard(user_id))
        else:
            bot.reply_to(message, "❌ Sheet သို့ ပို့ဆောင်မှု ပျက်ကွက်သည်။")
        user_states[user_id] = None

    # --- DELETE RESELLER PROCESS ---
    elif state == "DEL_R_ID":
        r_id = message.text.strip()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT reseller_id, username FROM resellers WHERE reseller_id = ?", (r_id,))
        row = cursor.fetchone()
        conn.close()
        if not row: return bot.reply_to(message, "❌ ရှာမတွေ့ပါ။")
        
        success = push_to_google_sheet("delete", r_id, "", "RESELLER_ACCOUNT", "", 0)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"🗑 Reseller: {row[1]} အား အောင်မြင်စွာ ဖျက်ထုတ်ပြီးပါပြီ။", reply_markup=get_main_keyboard(user_id))
        else:
            bot.reply_to(message, "❌ Google Sheet ပျက်ကွက်သည်။")
        user_states[user_id] = None

# ==========================================
# 9. BOT RUNNING ENGINE
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_google_sheet()
    
    # Run Webhook Server inside a thread
    srv_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))))
    srv_thread.daemon = True
    srv_thread.start()
    
    # Remove webhook and reset
    bot.remove_webhook()
    if PUBLIC_URL:
        import time
        time.sleep(1)
        bot.set_webhook(url=f"{PUBLIC_URL}/{BOT_TOKEN}")
        print(f"[+] Webhook successfully set to: {PUBLIC_URL}")
    else:
        print("[!] PUBLIC_URL is missing, polling or manual setting required.")
    
    # Keep main alive
    while True:
        try:
            import time
            time.sleep(10)
        except KeyboardInterrupt:
            break
