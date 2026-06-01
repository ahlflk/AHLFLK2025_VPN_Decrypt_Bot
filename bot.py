# # All-in-One Safe Decryptor & Telegram VIP Management Bot (1 Day = 1 Token System)
# Py By @AHLFLK2025 (Optimized with Dynamic Token Deduction & Anti-Loop Interceptor)
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

# ==========================================
# 1. CONFIGURATION & CORE BOT SETUP
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 5376544115
DEFAULT_CREDITS = 100  # Reseller အသစ်ဆောက်ရင် ပေးမယ့် အခြေခံ Token

GITHUB_TOKEN = os.getenv("GH_TOKEN") 
REPO_OWNER = "ahlflk" 
REPO_NAME = "AHLFLK2025_VPN_Decrypt_Bot" 
FILE_PATH = "key.txt" 
RESELLER_FILE_PATH = "resellers.txt" 

PUBLIC_URL = os.environ.get("PUBLIC_URL")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
MENU_BUTTONS = ["🌐 VPN Decrypt List", "➕ Add VIP User", "🔑 My VIP Users", "✏️ Edit VIP", "🗑 Delete VIP", "👤 Create Reseller", "📊 Reseller List", "🗑 Delete Reseller", "🌐 View All VIPs", "💰 My Balance"]

# ==========================================
# 2. FLASK SERVER & WEBHOOK CONTROLLER
# ==========================================
@app.route('/')
def home():
    return "VIP Bot (1 Day = 1 Token System) is Active!"

@app.route('/' + BOT_TOKEN, methods=['POST'])
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

# ==========================================
# 3. CORE MATH & XXTEA DECRYPTION ALGORITHM
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

# ==========================================
# 4. MULTI-METHOD INNER LAYER PROCESSORS
# ==========================================
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
    try: return json.loads(os.environ.get('VPN_CONFIGS', '[]'))
    except: return []

# ==========================================
# 5. DATABASE & GITHUB SYNC
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
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
        token_balance INTEGER DEFAULT 0
    )''')
    cursor.execute("INSERT OR IGNORE INTO users (tg_id, username, role, token_balance) VALUES (?, ?, ?, ?)", (ADMIN_ID, 'Main_Admin', 'admin', 9999999))
    conn.commit()
    conn.close()

def pull_data_from_github():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        url_keys = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        res_k = requests.get(url_keys, headers=headers)
        file_content_keys = res_k.json().get("content", "") if res_k.status_code == 200 else None
        if file_content_keys: file_content_keys = base64.b64decode(file_content_keys).decode("utf-8")
        else:
            res_raw = requests.get(f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{FILE_PATH}")
            if res_raw.status_code == 200: file_content_keys = res_raw.text

        if file_content_keys:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth_keys")
            for line in file_content_keys.split("\n"):
                if " | " in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 4:
                        owner = int(parts[4]) if len(parts) >= 5 and parts[4].isdigit() else ADMIN_ID
                        cdate = parts[5] if len(parts) == 6 else datetime.now().strftime("%Y-%m-%d")
                        cursor.execute("INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)", (parts[0], parts[1], parts[2], parts[3], owner, cdate))
            conn.commit()
            conn.close()
    except Exception as e: print(f"[-] Pull Keys Error: {str(e)}")

    try:
        url_resellers = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{RESELLER_FILE_PATH}"
        res_r = requests.get(url_resellers, headers=headers)
        file_content_resellers = res_r.json().get("content", "") if res_r.status_code == 200 else None
        if file_content_resellers: file_content_resellers = base64.b64decode(file_content_resellers).decode("utf-8")
        else:
            res_raw = requests.get(f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{RESELLER_FILE_PATH}")
            if res_raw.status_code == 200: file_content_resellers = res_raw.text

        if file_content_resellers:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
            for line in file_content_resellers.split("\n"):
                if " | " in line:
                    parts = [p.strip() for p in line.split("|")]
                    if parts[0].isdigit():
                        tg_id_val = int(parts[0])
                        tokens = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else DEFAULT_CREDITS
                        role_val = 'admin' if tg_id_val == ADMIN_ID else 'reseller'
                        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance) VALUES (?, ?, ?, ?)", (tg_id_val, parts[1], role_val, tokens))
            conn.commit()
            conn.close()
    except Exception as e: print(f"[-] Pull Resellers Error: {str(e)}")

def sync_db_to_github():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type, added_by, created_at FROM auth_keys")
        rows = cursor.fetchall()
        conn.close()
        
        content = "\n".join([f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]}" for r in rows])
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        res = requests.get(url, headers=headers)
        sha = res.json().get('sha') if res.status_code == 200 else None
        payload = {"message": "Sync VIP Keys", "content": base64.b64encode(content.encode('utf-8')).decode('utf-8')}
        if sha: payload["sha"] = sha
        requests.put(url, headers=headers, json=payload)
    except Exception as e: print(f"[-] Sync Error: {str(e)}")

def sync_resellers_to_github():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        content = "\n".join([f"{r[0]} | {r[1]} | {r[2]}" for r in rows])
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{RESELLER_FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        res = requests.get(url, headers=headers)
        sha = res.json().get('sha') if res.status_code == 200 else None
        payload = {"message": "Sync Resellers", "content": base64.b64encode(content.encode('utf-8')).decode('utf-8')}
        if sha: payload["sha"] = sha
        requests.put(url, headers=headers, json=payload)
    except Exception as e: print(f"[-] Reseller Sync Error: {str(e)}")

def calculate_days(unit, duration_type):
    if duration_type.lower() == 'm':
        return int(unit) * 30
    return int(unit)

def is_admin(user_id): 
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE tg_id = ? AND role = 'admin'", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def is_reseller(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE tg_id = ? AND (role = 'reseller' OR role = 'admin')", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def check_vip_status(user_id):
    if is_admin(user_id) or is_reseller(user_id): return True, "Unlimited (Staff)"
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT unit_val, duration_type, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
    row = cursor.fetchone()
    conn.close()
    
    if not row: return False, "Not VIP"
    
    unit_val, duration_type, created_at_str = row
    try:
        created_date = datetime.strptime(created_at_str, "%Y-%m-%d")
        days_to_add = calculate_days(unit_val, duration_type)
        expire_date = created_date + timedelta(days=days_to_add)
        
        if datetime.now() <= expire_date:
            return True, expire_date.strftime("%Y-%m-%d")
        else:
            return False, "Expired"
    except: return False, "Error Check"

def get_reseller_tokens(user_id):
    if user_id == ADMIN_ID: return 9999999
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT token_balance FROM users WHERE tg_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def deduct_reseller_tokens_by_days(user_id, required_tokens):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT token_balance FROM users WHERE tg_id = ?", (user_id,))
    res = cursor.fetchone()
    if res and res[0] >= required_tokens:
        cursor.execute("UPDATE users SET token_balance = token_balance - ? WHERE tg_id = ?", (required_tokens, user_id))
        conn.commit()
        conn.close()
        sync_resellers_to_github()
        return True
    conn.close()
    return False

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🌐 VPN Decrypt List"))
    
    if is_reseller(user_id):
        markup.add("➕ Add VIP User", "🔑 My VIP Users", "✏️ Edit VIP", "🗑 Delete VIP", "💰 My Balance")
    if is_admin(user_id):
        markup.add("👤 Create Reseller", "📊 Reseller List", "🗑 Delete Reseller", "🌐 View All VIPs")
    return markup

# ==========================================
# 6. TELEGRAM BOT HANDLERS & EVENTS
# ==========================================

# 🛡️ ANTI-LOOP INTERCEPTOR (အဓိကပြင်ဆင်ချက်)
# User က ဘယ် flow ထဲရောက်ရောက် မီနူးခလုတ်တွေကို လာနှိပ်လိုက်ရင် လက်ရှိ လုပ်လက်စ flow (State) အားလုံးကို အရင် ဖျက်သိမ်း (Reset) ပေးမည့်စနစ်
@bot.message_handler(func=lambda msg: msg.text in MENU_BUTTONS)
def handle_menu_buttons(message):
    user_id = message.from_user.id
    user_states[user_id] = None  # လက်ရှိပိတ်မိနေတဲ့ flow အားလုံးကို အတင်းအဓမ္မ Reset ချပေးသည်
    if user_id in reseller_temp_data: 
        del reseller_temp_data[user_id] # ယာယီသိမ်းထားတဲ့ data တွေကိုပါ အကုန်ရှင်းထုတ်သည်
    
    if message.text == "🌐 VPN Decrypt List":
        display_decrypt_list(message, user_id, message.chat.id)
    elif message.text == "➕ Add VIP User":
        cmd_add_vip(message)
    elif message.text == "🔑 My VIP Users":
        cmd_my_vips(message)
    elif message.text == "💰 My Balance":
        cmd_my_balance(message)
    elif message.text == "✏️ Edit VIP":
        admin_reseller_edit_vip_menu(message)
    elif message.text == "🗑 Delete VIP":
        admin_reseller_delete_vip_menu(message)
    elif message.text == "👤 Create Reseller":
        admin_create_reseller(message)
    elif message.text == "📊 Reseller List":
        admin_view_resellers(message)
    elif message.text == "🗑 Delete Reseller":
        admin_delete_reseller_menu(message)
    elif message.text == "🌐 View All VIPs":
        admin_view_all_keys(message)

def display_decrypt_list(message_or_call, user_id, chat_id):
    pull_data_from_github()
    is_vip, exp_status = check_vip_status(user_id)
    
    if not is_vip:
        no_vip_text = f"🚫 **သင်သည် VIP စနစ်အသုံးပြုခွင့် မရှိသေးပါ!**\n\nသင့်ရဲ့ Telegram ID: `{user_id}` အား Admin ထံပေးပို့၍ VIP သက်တမ်းဝယ်ယူပါ။"
        admin_markup = types.InlineKeyboardMarkup()
        admin_markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
        
        if isinstance(message_or_call, types.Message):
            bot.reply_to(message_or_call, no_vip_text, reply_markup=admin_markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, no_vip_text, reply_markup=admin_markup, parse_mode="Markdown")
        return

    configs = get_vpn_configs()
    welcome_text = f"👋 **Safe Decryptor & VIP Center မှ ကြိုဆိုပါတယ်!**\n\n⌛ **သင့် VIP သက်တမ်းကုန်မည့်ရက်:** `{exp_status}`\n\nDecrypt လုပ်ချင်တဲ့ VPN Config အမျိုးအစားကို အောက်မှာ ရွေးချယ်ပါ -"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for index, vpn in enumerate(configs, start=1):
        btn = types.InlineKeyboardButton(f"[{index}] {vpn['name']}", callback_data=f"dec_{vpn['id']}")
        buttons.append(btn)
    
    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])
        
    if isinstance(message_or_call, types.Message):
        bot.reply_to(message_or_call, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
    else:
        bot.send_message(chat_id, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        
    if configs: 
        bot.send_message(chat_id, "👇 Decrypt Configurations List:", reply_markup=markup)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    display_decrypt_list(message, user_id, message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dec_'))
def handle_decrypt_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    is_vip, _ = check_vip_status(user_id)
    if not is_vip:
        bot.answer_callback_query(call.id, "🚫 သင်သည် VIP သက်တမ်း ကုန်ဆုံးသွားပြီ ဖြစ်သည်။")
        return

    vpn_id = call.data.split('_')[1]
    configs = get_vpn_configs()
    selected_vpn = next((item for item in configs if item["id"] == vpn_id), None)
    if not selected_vpn: return

    status_msg = bot.send_message(chat_id, f"⏳ **{selected_vpn['name']} VPN Config ကို Decrypt လုပ်နေပါတယ်...**", parse_mode="Markdown")
    try:
        result_json = perform_decryption(selected_vpn["url"], selected_vpn["outer_key"], selected_vpn["outer_delta"], selected_vpn["method"])
        temp_file_path = f"{vpn_id}_decrypted.json"
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, indent=4, ensure_ascii=False)
            
        bot.delete_message(chat_id, status_msg.message_id)
        with open(temp_file_path, 'rb') as doc:
            bot.send_document(chat_id, doc, caption=f"✅ **{selected_vpn['name']} Decrypted Successfully!**", parse_mode="Markdown")
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
    except Exception as e:
        bot.send_message(chat_id, f"❌ **Error:** `{str(e)}`", parse_mode="Markdown")

# ----------------- VIP MANAGEMENT SYSTEMS -----------------
def cmd_add_vip(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_github()
    
    current_tokens = get_reseller_tokens(user_id)
    user_states[user_id] = 'w_vip'
    bot.reply_to(message, f"✍️ VIP အသစ်ဆောက်ရန် ပို့ပေးပါ-\n🪙 နှုန်းထား: `1 Day = 1 Token` (လက်ကျန်: `{current_tokens}` Tokens)\n\n`TelegramID | VIP_Name | Unit | Duration`\n\n💡 ဥပမာ- `0123456789 | AHLFLK2025 | 30 | d` (ရက် ၃၀ အတွက် 30 Tokens နှုတ်ပါမည်)", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_vip')
def process_vip_add(message):
    user_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4 or not parts[0].isdigit() or not parts[2].isdigit() or parts[3].lower() not in ['d', 'm']:
        return bot.reply_to(message, "❌ ပုံစံမှားနေပါသည်။ `TelegramID | VIP_Name | Unit | Duration` အတိုင်း သေချာပြန်ပို့ပေးပါ။")
    
    required_tokens = calculate_days(parts[2], parts[3])
    current_tokens = get_reseller_tokens(user_id)
    
    if not is_admin(user_id) and current_tokens < required_tokens:
        bot.reply_to(message, f"❌ Token မလုံလောက်ပါ။ ဤသက်တမ်းအတွက် `{required_tokens}` Tokens လိုအပ်သော်လည်း သင့်ထံတွင် `{current_tokens}` Tokens သာရှိသည်။")
        user_states[user_id] = None
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)", (parts[0], parts[1], parts[2], parts[3], user_id, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        
        if deduct_reseller_tokens_by_days(user_id, required_tokens):
            new_balance = get_reseller_tokens(user_id)
            bot.reply_to(message, f"✅ VIP အကောင့် အောင်မြင်စွာ ဆောက်ပြီးပါပြီ။\n🪙 နှုတ်ယူခဲ့သော တိုကင်: `{required_tokens}` Tokens\n💰 လက်ကျန်တိုကင်: `{new_balance}` Tokens", parse_mode="Markdown")
            sync_db_to_github()
    except Exception as e: bot.reply_to(message, f"❌ Error: {str(e)}")
    user_states[user_id] = None

def cmd_my_vips(message):
    if not is_reseller(message.from_user.id): return
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys WHERE added_by = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 သင်ထည့်သွင်းထားသော VIP အကောင့်မရှိသေးပါ။")
    res = "👥 **သင်ထည့်ထားသော VIP အသုံးပြုသူများ:**\n\n"
    for r in rows: res += f"• ID: `{r[0]}` -> နာမည်: `{r[1]}` (သက်တမ်း: `{r[2]} {r[3]}`)\n"
    bot.reply_to(message, res, parse_mode="Markdown")

def cmd_my_balance(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_github()
    tokens = get_reseller_tokens(user_id)
    bot.reply_to(message, f"💰 **လက်ကျန် Token စာရင်း (1 Day = 1 Token):**\n\n👤 Reseller: {message.from_user.first_name}\n📊 Credit Balance: {tokens} Tokens (ရက်ပေါင်း {tokens} စာ ဆောက်နိုင်သည်)", reply_markup=get_main_keyboard(user_id))

def admin_reseller_edit_vip_menu(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if is_admin(user_id):
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys")
    else:
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys WHERE added_by = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: return bot.reply_to(message, "📭 ပြင်ဆင်ရန် VIP အသုံးပြုသူ လုံးဝမရှိသေးပါ။")
    
    res_list = "📝 *လက်ရှိ VIP အသုံးပြုသူ စာရင်းများ*\n\n"
    res_list += "💡 _(Telegram ID ကို နှိပ်ပြီး အလွယ်တကူ Copy ကူးယူနိုင်ပါသည်)_\n"
    res_list += "--------------------------------------\n"
    for r in rows: 
        res_list += f"🆔 `{r[0]}` | 👤 *{r[1]}* ({r[2]}{r[3]})\n"
    res_list += "--------------------------------------\n\n"
    res_list += "✍️ *သက်တမ်းပြင်ဆင်/တိုးမြှင့်လိုသော VIP ၏ Telegram ID ကို ရိုက်ပို့ပေးပါ-*"
    
    user_states[user_id] = 'w_edit_vip_id'
    bot.send_message(message.chat.id, res_list, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_edit_vip_id')
def process_edit_vip_id(message):
    user_id = message.from_user.id
    target_id_str = message.text.strip()
    if not target_id_str.isdigit(): return bot.reply_to(message, "❌ Telegram ID အမှန်ကို ရိုက်ပို့ပေးပါ။")
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if is_admin(user_id):
        cursor.execute("SELECT key_string, unit_val, duration_type FROM auth_keys WHERE target_id = ?", (int(target_id_str),))
    else:
        cursor.execute("SELECT key_string, unit_val, duration_type FROM auth_keys WHERE target_id = ? AND added_by = ?", (int(target_id_str), user_id))
    row = cursor.fetchone()
    conn.close()
    
    if not row: return bot.reply_to(message, "❌ ဤ ID ဖြင့် VIP အား ရှာမတွေ့ပါ သို့မဟုတ် ပြင်ဆင်ခွင့်မရှိပါ။")
        
    reseller_temp_data[user_id] = {'target_id': int(target_id_str), 'name': row[0]}
    user_states[user_id] = 'w_edit_vip_duration'
    bot.reply_to(message, f"👤 အကောင့်: **{row[0]}**\n\n✍️ ပြောင်းလဲသတ်မှတ်လိုသော **သက်တမ်းအသစ်** ကို `Unit | Duration` ပုံစံဖြင့် ပို့ပေးပါ-\n(ဥပမာ- `60 | d` ဟု ထည့်ပါက သက်တမ်း ရက် ၆၀ သို့ ပြောင်းသွားပြီး လိုအပ်သော Token ကို ထပ်မံနှုတ်ယူပါမည်။)")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_edit_vip_duration')
def process_edit_vip_duration(message):
    user_id = message.from_user.id
    temp = reseller_temp_data.get(user_id)
    if not temp: return
        
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 2 or not parts[0].isdigit() or parts[1].lower() not in ['d', 'm']:
        return bot.reply_to(message, "❌ Format မှားယွင်းနေပါသည်။ ဥပမာ- `30 | d` ဟု ပို့ပေးပါ။")
        
    new_days = calculate_days(parts[0], parts[1])
    current_tokens = get_reseller_tokens(user_id)
    
    if not is_admin(user_id) and current_tokens < new_days:
        bot.reply_to(message, f"❌ သက်တမ်းတိုးရန် Token မလုံလောက်ပါ။ တိုကင် `{new_days}` ခု လိုအပ်သည်။")
        user_states[user_id] = None
        return
        
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE auth_keys SET unit_val = ?, duration_type = ?, created_at = ? WHERE target_id = ?", (int(parts[0]), parts[1].lower(), datetime.now().strftime("%Y-%m-%d"), temp['target_id']))
    conn.commit()
    conn.close()
    
    if deduct_reseller_tokens_by_days(user_id, new_days):
        sync_db_to_github()
        new_balance = get_reseller_tokens(user_id)
        bot.reply_to(message, f"✅ VIP User: **{temp['name']}** ကို သက်တမ်း အသစ်လဲလှယ်ပြီးပါပြီ။\n🪙 နှုတ်ယူခဲ့သော Token: `{new_days}` Tokens\n💰 လက်ကျန်တိုကင်: `{new_balance}` Tokens", parse_mode="Markdown")
    
    user_states[user_id] = None
    if user_id in reseller_temp_data: del reseller_temp_data[user_id]

def admin_reseller_delete_vip_menu(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if is_admin(user_id):
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys")
    else:
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys WHERE added_by = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: return bot.reply_to(message, "📭 ဖျက်ရန် VIP မရှိပါ။")
    
    res_list = "🗑 *လက်ရှိ VIP အသုံးပြုသူ စာရင်းများ*\n\n"
    res_list += "💡 _(Telegram ID ကို နှိပ်ပြီး အလွယ်တကူ Copy ကူးယူနိုင်ပါသည်)_\n"
    res_list += "--------------------------------------\n"
    for r in rows: 
        res_list += f"🆔 `{r[0]}` | 👤 *{r[1]}*\n"
    res_list += "--------------------------------------\n\n"
    res_list += "✍️ *ဖျက်ထုတ်လိုသော VIP ၏ Telegram ID ကို ရိုက်ပို့ပေးပါ-*"
    
    user_states[user_id] = 'w_del_vip'
    bot.send_message(message.chat.id, res_list, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_del_vip')
def process_delete_vip_by_id(message):
    user_id = message.from_user.id
    id_to_del = message.text.strip()
    if not id_to_del.isdigit(): return bot.reply_to(message, "❌ ID မှားယွင်းနေပါသည်။")
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if is_admin(user_id):
        cursor.execute("SELECT key_string FROM auth_keys WHERE target_id = ?", (int(id_to_del),))
    else:
        cursor.execute("SELECT key_string FROM auth_keys WHERE target_id = ? AND added_by = ?", (int(id_to_del), user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return bot.reply_to(message, "❌ ရှာမတွေ့ပါ သို့မဟုတ် ဖျက်ခွင့်မရှိပါ။")
    cursor.execute("DELETE FROM auth_keys WHERE target_id = ?", (int(id_to_del),))
    conn.commit()
    conn.close()
    sync_db_to_github()
    bot.reply_to(message, f"✅ VIP User: **{row[0]}** ကို ဖျက်ထုတ်ပြီးပါပြီ။ (မှတ်ချက်။ ။ တိုကင်များ ပြန်အမ်းမည်မဟုတ်ပါ)", parse_mode="Markdown")
    user_states[user_id] = None

# ----------------- ADMIN COMMANDS (RESELLERS) -----------------
def admin_create_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'w_r_id'
    bot.reply_to(message, "👤 Reseller ရဲ့ **Telegram User ID** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_r_id')
def process_r_id(message):
    admin_id = message.from_user.id
    try:
        reseller_id = int(message.text.strip())
        reseller_temp_data[admin_id] = {'id': reseller_id}
        user_states[admin_id] = 'w_r_name'
        bot.reply_to(message, "✍️ သတ်မှတ်မည့် **Reseller နာမည်** ပို့ပေးပါ-")
    except: 
        bot.reply_to(message, "❌ ID မှားယွင်းနေပါသည်။")
        user_states[admin_id] = None

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_r_name')
def process_r_name(message):
    admin_id = message.from_user.id
    if admin_id not in reseller_temp_data: return
    reseller_temp_data[admin_id]['name'] = message.text.strip()
    user_states[admin_id] = 'w_r_limit'
    bot.reply_to(message, "🪙 ထည့်သွင်းပေးမည့် **Token အရေအတွက် (1 Token = 1 Day)** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_r_limit')
def process_r_limit(message):
    admin_id = message.from_user.id
    if admin_id not in reseller_temp_data: return
    try:
        r_tokens = int(message.text.strip())
        r_id = reseller_temp_data[admin_id]['id']
        r_name = reseller_temp_data[admin_id]['name']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance) VALUES (?, ?, 'reseller', ?)", (r_id, r_name, r_tokens))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Reseller: `{r_name}` အား Token `{r_tokens}` ခု (ရက်ပေါင်း {r_tokens} စာ) ဖြင့် ဖန်တီးပြီးပါပြီ။")
        sync_resellers_to_github()
    except: bot.reply_to(message, "❌ : မှားယွင်းနေပါသည်။")
    user_states[admin_id] = None
    if admin_id in reseller_temp_data: del reseller_temp_data[admin_id]

def admin_view_resellers(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username, token_balance FROM users WHERE role='reseller' AND tg_id != ?", (ADMIN_ID,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 Reseller စာရင်း လုံးဝမရှိသေးပါ။")
    res = "👥 **Reseller စာရင်းနှင့် လက်ကျန် Token များ:**\n\n"
    for r in rows: res += f"🆔 `{r[0]}` | 👤 **{r[1]}** (လက်ကျန်: `{r[2]} Tokens`)\n"
    bot.reply_to(message, res, parse_mode="Markdown")

def admin_delete_reseller_menu(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username, token_balance FROM users WHERE role = 'reseller' AND tg_id != ?", (ADMIN_ID,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 ဖျက်ရန် Reseller မရှိပါ။")
    res_list = "👥 **လက်ရှိ Reseller စာရင်းများ:**\n\n"
    for r in rows: res_list += f"🆔 `{r[0]}` | 👤 **{r[1]}**\n"
    res_list += "\n✍️ **ဖျက်ထုတ်လိုသော Reseller ၏ Telegram ID ကို ရိုက်ပို့ပေးပါ-**"
    user_states[message.from_user.id] = 'w_del_reseller'
    bot.send_message(message.chat.id, res_list, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_del_reseller')
def process_delete_reseller_by_id(message):
    user_id = message.from_user.id
    id_to_del = message.text.strip()
    if not id_to_del.isdigit(): return bot.reply_to(message, "❌ ID မှားယွင်းနေပါသည်။")
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE tg_id = ? AND role = 'reseller'", (int(id_to_del),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return bot.reply_to(message, "❌ ရှာမတွေ့ပါ။")
    cursor.execute("DELETE FROM users WHERE tg_id = ?", (int(id_to_del),))
    conn.commit()
    conn.close()
    sync_resellers_to_github()
    bot.reply_to(message, f"✅ Reseller: **{row[0]}** ကို ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="Markdown")
    user_states[user_id] = None

def admin_view_all_keys(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 VIP အကောင့် မရှိသေးပါ။")
    res = f"🌐 **VIP အသုံးပြုသူ အားလုံးစာရင်း ({len(rows)} ဦး):**\n\n"
    for r in rows: res += f"🆔 `{r[0]}` | 👤 `{r[1]}` | {r[2]} {r[3]}\n"
    bot.reply_to(message, res, parse_mode="Markdown")

# ==========================================
# 7. WEBHOOK INITIALIZATION & RUN ENGINE
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_github()
    if PUBLIC_URL:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=f"{PUBLIC_URL}/{BOT_TOKEN}")
        except Exception as e: print(f"[-] Webhook Error: {str(e)}")
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
    else:
        bot.remove_webhook()
        bot.infinity_polling()
