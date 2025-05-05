import json
import requests
import threading
import time
from datetime import datetime, timedelta
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8169631003:AAFDSF5La9djwpAjuIa74e4kNgL8q0gqFwQ"
ADMIN_ID = 6491165519
bot = telebot.TeleBot(TOKEN)

url = "https://crash-gateway-cc-cr.gamedev-tech.cc/history"
params = {
    "id_n": "1play_luckyjet",
    "id_i": "1"
}
headers = {
    "Cookie": "__cf_bm=lyMw8RfXgDB2LuhhCl9nQcj11pyREymk3oRKcW3SmnA-1744743542-1.0.1.1-ECZZzKvuE.SfTPY.WzRWMDzycV8aeg2gyzdAZ7Ue1YrAFXu.B5wRlIDGMc84l_69aSrCM6UhykF6JYSWCsfOx_oemK.38ISBozIBs2XrzEs"
}

user_signals = {}
historique_file = 'historique.json'

def load_historique():
    try:
        with open(historique_file, 'r') as f:
            return json.load(f)
    except:
        return []

def save_historique(h):
    with open(historique_file, 'w') as f:
        json.dump(h, f, indent=4)

def update_historique():
    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:
        print("Erreur API")
        return

    data = response.json()
    coefs = []
    for game in data[:20]:
        top = game.get("top_coefficient")
        if top:
            try:
                coefs.append(float(top))
            except:
                continue

    historique = load_historique()
    for coef in coefs:
        historique.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "coefficient": coef})

    if len(historique) > 50:
        historique = historique[-50:]

    save_historique(historique)

def calculate_wait_time(coefs):
    time_since_loss = 0
    for coef in reversed(coefs):
        if coef < 1.5:
            time_since_loss += 1
        else:
            break
    return max(2 + time_since_loss, 2)

def generate_signal():
    historique = load_historique()
    coefs = [e["coefficient"] for e in historique[-20:] if isinstance(e, dict) and "coefficient" in e]
    if len(coefs) < 20:
        return None

    moyenne = max(1.9, min(sum(coefs)/len(coefs), 7))
    min_coef = min(coefs)
    max_coef = max(coefs)
    ecart = max_coef - min_coef
    assurance = 1.9
    if ecart > 0:
        assurance += (moyenne - min_coef) * (3.5 - 1.9) / ecart
    assurance = round(min(assurance, moyenne - 0.1), 2)
    assurance = max(1.8, min(assurance, 3.7, moyenne - 0.1))
    heure_pred = (datetime.now() + timedelta(minutes=calculate_wait_time(coefs))).strftime("%H:%M")

    return f"""♣︎ SIGNAL LUCKY JET ♣︎

➣ 𝐇𝐄𝐔𝐑𝐄 : {heure_pred}🇨🇮  
➣ 𝐂𝐎𝐄𝐅𝐅𝐈𝐂𝐈𝐄𝐍𝐓 : {round(moyenne, 2)}X  
➣ 𝐀𝐒𝐒𝐔𝐑𝐀𝐍𝐂𝐄 : {assurance}X

𝙿𝚕𝚊𝚝𝚎𝚏𝚘𝚛𝚖𝚎: 1WIN🔔 𝙲𝚘𝚍𝚎 𝚙𝚛𝚘𝚖𝚘: DIVINEJET 🔑"""

def background_checker():
    while True:
        update_historique()
        signal = generate_signal()
        if signal:
            for user_id, enabled in user_signals.items():
                if enabled:
                    try:
                        bot.send_message(user_id, signal)
                    except:
                        pass
        time.sleep(60)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🎯 Signal"), KeyboardButton("👤 Mon compte"))
    if message.from_user.id == ADMIN_ID:
        markup.add(KeyboardButton("⚙️ Admin"))
    bot.send_message(message.chat.id, "Bienvenue dans le bot ! Choisis une option :", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎯 Signal")
def handle_signal(message):
    if not user_signals.get(message.from_user.id):
        bot.reply_to(message, "Vous n'avez pas activé les signaux.")
        return
    signal = generate_signal()
    if signal:
        bot.reply_to(message, signal)
    else:
        bot.reply_to(message, "Pas assez de données pour générer un signal.")

@bot.message_handler(func=lambda m: m.text == "👤 Mon compte")
def handle_account(message):
    info = f"Nom : {message.from_user.first_name} {message.from_user.last_name or ''}\nID : {message.from_user.id}"
    bot.send_message(message.chat.id, info)

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin")
def admin_menu(message):
    if message.from_user.id == ADMIN_ID:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("✔️ Activer Signaux"), KeyboardButton("❌ Désactiver Signaux"))
        markup.add(KeyboardButton("📊 Statistiques"))
        bot.send_message(message.chat.id, "Menu Admin. Choisissez une option :", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "✔️ Activer Signaux")
def activate_user(message):
    if message.from_user.id == ADMIN_ID:
        user_signals[ADMIN_ID] = True
        bot.reply_to(message, "Signaux activés pour vous.")

@bot.message_handler(func=lambda m: m.text == "❌ Désactiver Signaux")
def deactivate_user(message):
    if message.from_user.id == ADMIN_ID:
        user_signals[ADMIN_ID] = False
        bot.reply_to(message, "Signaux désactivés pour vous.")

# Démarrer le remplissage de l'historique et le thread de fond
update_historique()
threading.Thread(target=background_checker, daemon=True).start()
bot.polling(non_stop=True)
