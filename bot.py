# All-in-One Safe Decryptor & Telegram VIP Management Bot
# Py By @AHLFLK2025
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
from flask import Flask
import telebot
from telebot import types

# ==========================================
# 1. FLASK SERVER FOR RENDER (KEEP ALIVE)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "All-in-One Safe Decryptor & VIP Bot is Active!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. CONFIGURATION & CONFIG READERS
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 5376544115
DEFAULT_LIMIT = 5 

GITHUB_TOKEN = os.getenv("GH_TOKEN") 
REPO_OWNER = "ahlflk" 
REPO_NAME = "AHLFLK2025_VPN_Decrypt_Bot" 
FILE_PATH = "key.txt" 
RESELLER_FILE_PATH = "resellers.txt" 

bot = telebot.TeleBot(BOT_TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
MENU_BUTTONS = ["🌐 VPN Decrypt List", "➕ Add VIP User", "🔑 My VIP Users", "✏️ Edit VIP", "🗑 Delete VIP", "👤 Create Reseller", "📊 Reseller List", "🗑 Delete Reseller", "🌐 View All VIPs"]

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
    headers = {'User-Agent': 'Mozilla/5.0'}
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
# 5. DATABASE & GITHUB SYNC (VIP LOGIC)
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
        daily_limit INTEGER DEFAULT 5
    )''')
    cursor.execute("INSERT OR IGNORE INTO users (tg_id, username, role, daily_limit) VALUES (?, ?, ?, ?)", (ADMIN_ID, 'Main_Admin', 'admin', 999999))
    conn.commit()
    conn.close()

def pull_data_from_github():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    # Sync VIP Keys
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

    # Sync Resellers
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
                        r_limit = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else DEFAULT_LIMIT
                        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, daily_limit) VALUES (?, ?, 'reseller', ?)", (int(parts[0]), parts[1], r_limit))
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
        cursor.execute("SELECT tg_id, username, daily_limit FROM users")
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

# --- VIP Logic Checks ---
def is_admin(user_id): return user_id == ADMIN_ID

def is_reseller(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE tg_id = ? AND role = 'reseller'", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def check_vip_status(user_id):
    """ အသုံးပြုသူသည် VIP စာရင်းထဲရှိပြီး သက်တမ်းကျန်မကျန် စစ်ဆေးပေးသည် """
    if is_admin(user_id) or is_reseller(user_id): return True, "Unlimited"
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT unit_val, duration_type, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
    row = cursor.fetchone()
    conn.close()
    
    if not row: return False, "Not VIP"
    
    unit_val, duration_type, created_at_str = row
    try:
        created_date = datetime.strptime(created_at_str, "%Y-%m-%d")
        days_to_add = int(unit_val) * (30 if duration_type.lower() == 'm' else 1)
        expire_date = created_date + timedelta(days=days_to_add)
        
        if datetime.now() <= expire_date:
            return True, expire_date.strftime("%Y-%m-%d")
        else:
            return False, "Expired"
    except: return False, "Error Check"

def get_reseller_daily_limit(user_id):
    if user_id == ADMIN_ID: return 999999
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT daily_limit FROM users WHERE tg_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else DEFAULT_LIMIT

def get_today_added_count(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auth_keys WHERE added_by = ? AND created_at = ?", (user_id, datetime.now().strftime("%Y-%m-%d")))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # အပေါ်ဆုံးမှာ "🌐 VPN Decrypt List" ခလုတ်ကို နေရာအပြည့် ထားပေးထားပါတယ်
    markup.add(types.KeyboardButton("🌐 VPN Decrypt List"))
    
    if is_reseller(user_id):
        markup.add("➕ Add VIP User", "🔑 My VIP Users", "✏️ Edit VIP", "🗑 Delete VIP")
    if is_admin(user_id):
        markup.add("👤 Create Reseller", "📊 Reseller List", "🗑 Delete Reseller", "🌐 View All VIPs")
    return markup

# ==========================================
# 6. TELEGRAM BOT HANDLERS & EVENTS
# ==========================================
def display_decrypt_list(message_or_call, user_id, chat_id):
    """ Decrypt List ကို ထုတ်ပြပေးသည့် ဘုံ Function """
    pull_data_from_github()
    is_vip, exp_status = check_vip_status(user_id)
    
    if not is_vip:
        if isinstance(message_or_call, types.Message):
            bot.reply_to(message_or_call, f"🚫 **သင်သည် VIP စနစ်အသုံးပြုခွင့် မရှိသေးပါ!**\n\nသင့်ရဲ့ Telegram ID: `{user_id}` အား Admin ထံပေးပို့၍ VIP သက်တမ်းဝယ်ယူပါ။")
        else:
            bot.send_message(chat_id, f"🚫 **သင်သည် VIP စနစ်အသုံးပြုခွင့် မရှိသေးပါ!**\n\nသင့်ရဲ့ Telegram ID: `{user_id}` အား Admin ထံပေးပို့၍ VIP သက်တမ်းဝယ်ယူပါ။")
        return

    configs = get_vpn_configs()
    welcome_text = f"👋 **Safe Decryptor & VIP Center မှ ကြိုဆိုပါတယ်!**\n\n⌛ **သင့် VIP သက်တမ်းကုန်မည့်ရက်:** `{exp_status}`\n\nDecrypt လုပ်ချင်တဲ့ VPN Config အမျိုးအစားကို အောက်မှာ ရွေးချယ်ပါ -"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for index, vpn in enumerate(configs, start=1):
        markup.add(types.InlineKeyboardButton(f"[{index}] {vpn['name']}", callback_data=f"dec_{vpn['id']}"))
        
    if isinstance(message_or_call, types.Message):
        bot.reply_to(message_or_call, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
    else:
        bot.send_message(chat_id, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        
    if configs: 
        bot.send_message(chat_id, "👇 Decrypt Configurations List:", reply_markup=markup)
    else:
        bot.send_message(chat_id, "❌ စနစ်ထဲတွင် VPN Config များ ထည့်သွင်းထားခြင်း မရှိသေးပါ။")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    display_decrypt_list(message, user_id, message.chat.id)

# ခလုတ်အသစ် "🌐 VPN Decrypt List" ကို နှိပ်လိုက်ရင် ဖမ်းပေးမယ့်နေရာ
@bot.message_handler(func=lambda msg: msg.text == "🌐 VPN Decrypt List")
def handle_decrypt_list_button(message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    display_decrypt_list(message, user_id, message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dec_'))
def handle_decrypt_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    
    is_vip, _ = check_vip_status(user_id)
    if not is_vip:
        bot.answer_callback_query(call.id, "🚫 သင်သည် VIP သက်တမ်း ကုန်ဆုံးသွားပြီ ဖြစ်သဖြင့် နှိပ်ခွင့်မရှိတော့ပါ။")
        return

    vpn_id = call.data.split('_')[1]
    configs = get_vpn_configs()
    selected_vpn = next((item for item in configs if item["id"] == vpn_id), None)
    
    if not selected_vpn:
        bot.send_message(chat_id, "❌ ရွေးချယ်ထားသော VPN Config ကို စနစ်ထဲမှာ ရှာမတွေ့ပါ။")
        return

    status_msg = bot.send_message(chat_id, f"⏳ **{selected_vpn['name']} Config ကို Decrypt လုပ်နေပါတယ်...**", parse_mode="Markdown")
    try:
        result_json = perform_decryption(selected_vpn["url"], selected_vpn["outer_key"], selected_vpn["outer_delta"], selected_vpn["method"])
        temp_file_path = f"{vpn_id}_decrypted.json"
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, indent=4, ensure_ascii=False)
            
        bot.delete_message(chat_id, status_msg.message_id)
        with open(temp_file_path, 'rb') as doc:
            bot.send_document(chat_id, doc, caption=f"✅ **{selected_vpn['name']} Decrypted Successfully!**\n\n📌 *By @AHLFLK2025*", parse_mode="Markdown")
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
    except Exception as e:
        bot.edit_message_text(f"❌ **Error:** `{str(e)}`", chat_id, status_msg.message_id, parse_mode="Markdown")

# ----------------- VIP MANAGEMENT SYSTEMS -----------------
@bot.message_handler(func=lambda msg: msg.text == "➕ Add VIP User" and is_reseller(msg.from_user.id))
def cmd_add_vip(message):
    user_id = message.from_user.id
    pull_data_from_github()
    if not is_admin(user_id):
        if get_today_added_count(user_id) >= get_reseller_daily_limit(user_id):
            bot.reply_to(message, "❌ ယနေ့အတွက် သင့်ရဲ့ VIP ထည့်သွင်းခွင့် Limit ပြည့်သွားပါပြီ။")
            return
    user_states[user_id] = 'w_vip'
    bot.reply_to(message, "✍️ VIP ဖြစ်စေချင်သူ၏ အချက်အလက်ကို အောက်ပါအတိုင်း ပို့ပေးပါ-\n\n`TelegramID | VIP_Name | Unit | Duration`\n\n💡 ဥပမာ- `5376544115 | AHLFLK2025 | 30 | d` (d = ရက်၊ m = လ)", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_vip' and msg.text not in MENU_BUTTONS)
def process_vip_add(message):
    user_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4 or not parts[0].isdigit():
        return bot.reply_to(message, "❌ ပုံစံမှားနေပါသည်။ `TelegramID | VIP_Name | Unit | Duration` အတိုင်း သေချာပြန်ပို့ပေးပါ။")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)", (parts[0], parts[1], parts[2], parts[3], user_id, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ VIP အကောင့် သိမ်းဆည်းပြီးပါပြီ။ Cloud သို့ ပို့နေသည်...")
        sync_db_to_github()
    except Exception as e: bot.reply_to(message, f"❌ Error: {str(e)}")
    user_states[user_id] = None

@bot.message_handler(func=lambda msg: msg.text == "🔑 My VIP Users" and is_reseller(msg.from_user.id))
def cmd_my_vips(message):
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, created_at FROM auth_keys WHERE added_by = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 သင်ထည့်သွင်းထားသော VIP အကောင့်မရှိသေးပါ။")
    res = "👥 **သင်ထည့်ထားသော VIP အသုံးပြုသူများ:**\n\n"
    for r in rows: res += f"• ID: `{r[0]}` -> နာမည်: `{r[1]}` (ရက်စွဲ: `{r[2]}`)\n"
    bot.reply_to(message, res, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "✏️ Edit VIP" and is_reseller(msg.from_user.id))
def cmd_edit_vip(message):
    user_states[message.from_user.id] = 'w_edit_vip'
    bot.reply_to(message, "✏️ **ပြင်ဆင်ရန် ပုံစံအတိုင်း ပို့ပေးပါ-**\n\n`TelegramID | နာမည်သစ် | Unitသစ် | Durationသစ်`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_edit_vip' and msg.text not in MENU_BUTTONS)
def process_edit_vip(message):
    user_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4: user_states[user_id] = None; return bot.reply_to(message, "❌ ပုံစံမမှန်ပါ။")
    
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT added_by FROM auth_keys WHERE target_id = ?", (parts[0],))
    row = cursor.fetchone()
    if not row: conn.close(); user_states[user_id] = None; return bot.reply_to(message, "❌ ဤ VIP ID အား ရှာမတွေ့ပါ။")
    if row[0] != user_id and not is_admin(user_id): conn.close(); user_states[user_id] = None; return bot.reply_to(message, "🚫 ပြင်ဆင်ခွင့်မရှိပါ။")
    
    cursor.execute("UPDATE auth_keys SET key_string=?, unit_val=?, duration_type=? WHERE target_id=?", (parts[1], parts[2], parts[3], parts[0]))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✏️ VIP အချက်အလက် ပြင်ဆင်ပြီးပါပြီ။ Cloud သို့ သိမ်းနေပါသည်...")
    sync_db_to_github()
    user_states[user_id] = None

@bot.message_handler(func=lambda msg: msg.text == "🗑 Delete VIP" and is_reseller(msg.from_user.id))
def cmd_delete_vip(message):
    user_states[message.from_user.id] = 'w_del_vip'
    bot.reply_to(message, "🗑 ဖျက်လိုသော **VIP ရဲ့ Telegram ID** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_del_vip' and msg.text not in MENU_BUTTONS)
def process_delete_vip(message):
    user_id = message.from_user.id
    id_to_del = message.text.strip()
    pull_data_from_github()
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT added_by FROM auth_keys WHERE target_id = ?", (id_to_del,))
    row = cursor.fetchone()
    if not row: conn.close(); return bot.reply_to(message, "❌ ID ရှာမတွေ့ပါ။")
    if row[0] != user_id and not is_admin(user_id): conn.close(); return bot.reply_to(message, "🚫 ဖျက်ခွင့်မရှိပါ။")
    
    cursor.execute("DELETE FROM auth_keys WHERE target_id = ?", (id_to_del,))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✅ VIP အကောင့်အား ဖျက်ထုတ်ပြီးပါပြီ။")
    sync_db_to_github()
    user_states[user_id] = None

# ----------------- ADMIN COMMANDS (RESELLERS) -----------------
@bot.message_handler(func=lambda msg: msg.text == "👤 Create Reseller" and is_admin(msg.from_user.id))
def admin_create_reseller(message):
    user_states[message.from_user.id] = 'w_r_id'
    bot.reply_to(message, "👤 Reseller ရဲ့ **Telegram User ID** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(message.from_user.id) == 'w_r_id' and msg.text not in MENU_BUTTONS)
def process_r_id(message):
    try:
        reseller_id = int(message.text.strip())
        reseller_temp_data[message.from_user.id] = {'id': reseller_id}
        user_states[message.from_user.id] = 'w_r_name'
        bot.reply_to(message, "✍️ သတ်မှတ်မည့် **Reseller နာမည်** ပို့ပေးပါ-")
    except: bot.reply_to(message, "❌ ID မှားယွင်းနေပါသည်။")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_r_name' and msg.text not in MENU_BUTTONS)
def process_r_name(message):
    admin_id = message.from_user.id
    reseller_temp_data[admin_id]['name'] = message.text.strip()
    user_states[admin_id] = 'w_r_limit'
    bot.reply_to(message, "📊 တစ်ရက်လျှင် Add ခွင့်ပြုမည့် **VIP အရေအတွက် (Limit)** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(admin_id := msg.from_user.id) == 'w_r_limit' and msg.text not in MENU_BUTTONS)
def process_r_limit(message):
    admin_id = message.from_user.id
    try:
        r_limit = int(message.text.strip())
        r_id = reseller_temp_data[admin_id]['id']
        r_name = reseller_temp_data[admin_id]['name']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, daily_limit) VALUES (?, ?, 'reseller', ?)", (r_id, r_name, r_limit))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Reseller: `{r_name}` အား ဖန်တီးပြီးပါပြီ။ Cloud သို့ တင်နေပါသည်...")
        sync_resellers_to_github()
    except: bot.reply_to(message, "❌ အကန့်အသတ် မှားယွင်းနေပါသည်။")
    user_states[admin_id] = None

@bot.message_handler(func=lambda msg: msg.text == "📊 Reseller List")
def admin_view_resellers(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username, daily_limit FROM users WHERE role='reseller'")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 Reseller စာရင်း လုံးဝမရှိသေးပါ။")
    res = "👥 **Reseller စာရင်းစုစုပေါင်း:**\n\n"
    for r in rows: res += f"• {r[1]} (ID: `{r[0]}`) - Limit: `{r[2]} ခု/ရက်`\n"
    bot.reply_to(message, res, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🗑 Delete Reseller" and is_admin(msg.from_user.id))
def admin_delete_reseller_menu(message):
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username FROM users WHERE role = 'reseller'")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 ဖျက်ရန် Reseller မရှိပါ။")
    markup = types.InlineKeyboardMarkup()
    for r in rows: markup.add(types.InlineKeyboardButton(text=f"❌ {r[1]}", callback_data=f"del_reseller_{r[0]}"))
    bot.send_message(message.chat.id, "🗑 **ဖျက်ထုတ်လိုသော Reseller အား နှိပ်ပါ-**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_reseller_"))
def callback_delete_reseller(call):
    if not is_admin(call.from_user.id): return
    reseller_id = int(call.data.replace("del_reseller_", ""))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE tg_id = ?", (reseller_id,))
    conn.commit()
    conn.close()
    sync_resellers_to_github()
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🗑 Reseller အား အောင်မြင်စွာ ဖျက်ထုတ်ပြီးပါပြီ။")

@bot.message_handler(func=lambda msg: msg.text == "🌐 View All VIPs" and is_admin(msg.from_user.id))
def admin_view_all_keys(message):
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 Database ထဲတွင် VIP အကောင့် မရှိသေးပါ။")
    res = f"🌐 **VIP အသုံးပြုသူ အားလုံးစာရင်း ({len(rows)} ဦး):**\n\n"
    for r in rows: res += f"🆔 `{r[0]}` | 👤 `{r[1]}` | {r[2]} {r[3]}\n"
    bot.reply_to(message, res, parse_mode="Markdown")

# ==========================================
# 8. START SERVER AND BOT POLING
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_github()
    server_thread = Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    print("Bot is up and polling...")
    bot.infinity_polling()
