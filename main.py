import os
import re
import json
import struct
import base64
import urllib.request
from threading import Thread
from flask import Flask
import telebot

# --- Flask Server for Render (Keep Alive) ---
app = Flask('')

@app.route('/')
def home():
    return "All-in-One Safe Decryptor Bot is Active!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- Telegram Bot Setup ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 1. CORE MATH & XXTEA DECRYPTION ALGORITHM
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
    v, k = _bytes_to_longs(data), _bytes_to_longs(_fix_key(key))
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

# ==========================================
# 2. HELPER TO PARSE STR/HEX DELTA TO INT
# ==========================================
def parse_delta(delta_val):
    if isinstance(delta_val, int):
        return delta_val
    try:
        val_str = str(delta_val).strip()
        # အကယ်၍ အနှုတ်လက္ခဏာပါသော Hex ဖြစ်ခဲ့လျှင် (ဥပမာ - "-0x2e0405f5")
        if val_str.startswith('-'):
            clean_hex = val_str.replace('-', '').strip()
            return -int(clean_hex, 16)
        else:
            return int(val_str, 16)
    except:
        return 0x2e0ba747  # Error ဖြစ်သွားပါက default delta သုံးမည်

# ==========================================
# 3. MULTI-METHOD INNER LAYER PROCESSORS
# ==========================================

# Method A: Base64 Recursive (Duck, Daisy, Sathu, Pukang)
def decrypt_inner_base64_recursive(encrypted_str):
    if not isinstance(encrypted_str, str) or len(encrypted_str) < 4:
        return encrypted_str
    try:
        clean_str = encrypted_str.replace('\n', '').replace('\r', '').strip()
        if not re.match(r'^[A-Za-z0-9+/=]+$', clean_str): return encrypted_str
        missing_padding = len(clean_str) % 4
        if missing_padding: clean_str += '=' * (4 - missing_padding)
            
        decoded_bytes = base64.b64decode(clean_str)
        decoded_str = decoded_bytes.decode('utf-8')
        
        if len(decoded_str) > 4 and re.match(r'^[A-Za-z0-9+/=]+$', decoded_str.replace('\n','').strip()):
            if any(x in decoded_str for x in ["HTTP/", "vless://", "vmess://", "trojan://", "ss://"]):
                return decoded_str
            return decrypt_inner_base64_recursive(decoded_str)
        return decoded_str
    except:
        return encrypted_str

# Method B: Bamar Inner XXTEA Key
def decrypt_inner_bamar(encrypted_str):
    if not encrypted_str or len(encrypted_str) < 10: return encrypted_str
    try:
        data = base64.b64decode(encrypted_str)
        decrypted_bytes = decrypt_xxtea(data, b"9488362782103982762188", 0x2e0ba747)
        return decrypted_bytes.decode('utf-8', errors='ignore') if decrypted_bytes else encrypted_str
    except: 
        return encrypted_str

# Method C: PNT Special Character Math Formula
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
    except:
        return encrypted_str

# JSON Object Hierarchy Walker
def process_json_structure(data, method):
    if isinstance(data, dict):
        return {k: process_json_structure(v, method) for k, v in data.items()}
    elif isinstance(data, list):
        return [process_json_structure(i, method) for i in data]
    elif isinstance(data, str):
        if method == "bamar":
            return decrypt_inner_bamar(data)
        elif method == "pnt_special":
            return decrypt_inner_pnt(data)
        elif method == "base64_recursive":
            return decrypt_inner_base64_recursive(data)
        return data
    else:
        return data

# ==========================================
# 4. MAIN DECRYPT CONTROLLER
# ==========================================
def perform_decryption(config_url, outer_key, outer_delta_raw, method):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    req = urllib.request.Request(config_url, headers=headers)
    with urllib.request.urlopen(req) as response:
        enc_base64 = response.read().decode('utf-8').replace('\n', '').replace('\r', '').strip()
    
    # Hex String သို့မဟုတ် Int တန်ဖိုးကို parse လုပ်ယူခြင်း
    outer_delta = parse_delta(outer_delta_raw)
    
    enc_data = base64.b64decode(enc_base64)
    dec_bytes = decrypt_xxtea(enc_data, outer_key.encode('utf-8'), outer_delta)
    raw_json_str = dec_bytes.decode('utf-8', errors='ignore').replace('\\/', '/')
    
    json_obj = json.loads(raw_json_str)
    dec_json = process_json_structure(json_obj, method)
    
    return {"AHLFLK": "Decrypted By @AHLFLK2025", **dec_json}

def get_vpn_configs():
    env_data = os.environ.get('VPN_CONFIGS', '[]')
    try:
        return json.loads(env_data)
    except:
        return []

# ==========================================
# 5. TELEGRAM BOT EVENT HANDLERS
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    configs = get_vpn_configs()
    if not configs:
        bot.reply_to(message, "❌ Render Env ထဲမှာ VPN Config Data ထည့်သွင်းထားခြင်း မရှိသေးပါ။")
        return

    welcome_text = "👋 **VPN Decrypted Center မှ ကြိုဆိုပါတယ်!**\n\nDecrypt လုပ်ချင်တဲ့ VPN အမျိုးအစားကို ရွေးချယ်ပေးပါ -"
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for index, vpn in enumerate(configs, start=1):
        button_text = f"[{index}] {vpn['name']}"
        markup.add(telebot.types.InlineKeyboardButton(button_text, callback_data=f"dec_{vpn['id']}"))
        
    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dec_'))
def handle_decrypt_callback(call):
    vpn_id = call.data.split('_')[1]
    chat_id = call.message.chat.id
    
    configs = get_vpn_configs()
    selected_vpn = next((item for item in configs if item["id"] == vpn_id), None)
    
    if not selected_vpn:
        bot.send_message(chat_id, "❌ ရွေးချယ်ထားသော VPN Config ကို စနစ်ထဲမှာ ရှာမတွေ့ပါ။")
        return

    status_msg = bot.send_message(chat_id, f"⏳ **{selected_vpn['name']} Config ကို လှမ်းခေါ်ပြီး Decrypt လုပ်နေပါတယ်...**", parse_mode="Markdown")
    
    try:
        # JSON ထဲက တန်ဖိုးများကို Dynamic ယူသုံးပြီး Decrypt ပြုလုပ်ခြင်း
        result_json = perform_decryption(
            selected_vpn["url"], 
            selected_vpn["outer_key"], 
            selected_vpn["outer_delta"],
            selected_vpn["method"]
        )
        
        temp_file_path = f"{vpn_id}_decrypted.json"
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, indent=4, ensure_ascii=False)
            
        bot.delete_message(chat_id, status_msg.message_id)
        
        with open(temp_file_path, 'rb') as doc:
            bot.send_document(
                chat_id, 
                doc, 
                caption=f"✅ **{selected_vpn['name']} Decrypted Successfully!**\n\n📌 *By @AHLFLK2025*",
                parse_mode="Markdown"
            )
            
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
    except Exception as e:
        bot.edit_message_text(f"❌ **Error Occurred:** `{str(e)}`", chat_id, status_msg.message_id, parse_mode="Markdown")

# ==========================================
# 6. START SERVER AND BOT
# ==========================================
if __name__ == "__main__":
    server_thread = Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    print("Bot is up and polling...")
    bot.infinity_polling()
