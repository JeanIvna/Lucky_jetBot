import os
import requests
from datetime import datetime, timedelta
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
import joblib
from dotenv import load_dotenv
import threading
import time

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 6491165519

url = "https://crash-gateway-cc-cr.gamedev-tech.cc/history"
params = {
    "id_n": "1play_luckyjet",
    "id_i": "1"
}
headers = {
    "Cookie": os.getenv("API_COOKIE")
}

users_signaux = {}
last_signal_time = {}

model = None
scaler = StandardScaler()
model_file = "lucky_jet_model.pkl"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🎯 Signal"), KeyboardButton("👤 Mon compte"))
    if message.from_user.id == ADMIN_ID:
        markup.add(KeyboardButton("🛡️ Admin"))
    bot.send_message(message.chat.id, "Bienvenue dans le bot ! Choisis une option :", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["🎯 Signal", "👤 Mon compte", "🛡️ Admin"])
def handle_menu(message):
    user_id = message.from_user.id
    if message.text == "🎯 Signal":
        user_data = users_signaux.get(user_id, {"active": False, "count": 0})
        if not user_data["active"] or user_data["count"] <= 0:
            bot.reply_to(message, "Vous n'avez pas accès aux signaux.")
            return
        if user_id in last_signal_time and datetime.now() - last_signal_time[user_id] < timedelta(minutes=2):
            bot.reply_to(message, "Veuillez patienter encore avant de demander un nouveau signal.")
            return
        send_prediction(message)
        last_signal_time[user_id] = datetime.now()

    elif message.text == "👤 Mon compte":
        data = users_signaux.get(user_id, {"active": False, "count": 0})
        status = "Activé" if data["active"] else "Désactivé"
        bot.reply_to(message, f"ID : {user_id}\nSignaux restants : {data['count']}\nÉtat : {status}")

    elif message.text == "🛡️ Admin":
        if message.from_user.id == ADMIN_ID:
            show_admin_menu(message)
        else:
            bot.reply_to(message, f"Accès refusé. Ton ID : {user_id}")

def show_admin_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Activer les signaux"), KeyboardButton("Désactiver les signaux"))
    markup.add(KeyboardButton("État des signaux"), KeyboardButton("Retour"))
    bot.send_message(message.chat.id, "Bienvenue Admin, choisis une option :", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["Retour", "Activer les signaux", "Désactiver les signaux", "État des signaux"])
def handle_admin_commands(message):
    if message.text == "Retour":
        send_welcome(message)
    elif message.text == "Activer les signaux":
        bot.reply_to(message, "Envoie l'ID de l'utilisateur à activer.")
        bot.register_next_step_handler(message, get_id_for_activation)
    elif message.text == "Désactiver les signaux":
        bot.reply_to(message, "Envoie l'ID de l'utilisateur à désactiver.")
        bot.register_next_step_handler(message, get_id_for_deactivation)
    elif message.text == "État des signaux":
        bot.reply_to(message, "Envoie l'ID de l'utilisateur à consulter.")
        bot.register_next_step_handler(message, get_id_for_status)

def get_id_for_activation(message):
    try:
        user_id = int(message.text)
        bot.reply_to(message, "Combien de signaux accorder ?")
        bot.register_next_step_handler(message, lambda m: activate_user(m, user_id))
    except ValueError:
        bot.reply_to(message, "ID invalide. Réessaye.")

def activate_user(message, user_id):
    try:
        count = int(message.text)
        users_signaux[user_id] = {"active": True, "count": count}
        bot.reply_to(message, f"Utilisateur {user_id} activé avec {count} signaux.")
        bot.send_message(user_id, f"Tu as maintenant accès aux signaux ! ({count} restants)")
    except Exception as e:
        bot.reply_to(message, f"Erreur : {e}")

def get_id_for_deactivation(message):
    try:
        user_id = int(message.text)
        users_signaux[user_id] = {"active": False, "count": 0}
        bot.reply_to(message, f"Signaux désactivés pour {user_id}.")
        bot.send_message(user_id, "Ton accès aux signaux a été désactivé.")
    except Exception as e:
        bot.reply_to(message, f"Erreur : {e}")

def get_id_for_status(message):
    try:
        user_id = int(message.text)
        data = users_signaux.get(user_id, {"active": False, "count": 0})
        status = "Activé" if data["active"] else "Désactivé"
        bot.reply_to(message, f"ID : {user_id}\nSignaux restants : {data['count']}\nÉtat : {status}")
    except Exception as e:
        bot.reply_to(message, f"Erreur : {e}")

def send_prediction(message):
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            bot.reply_to(message, "Erreur API.")
            return

        data = response.json()
        coefs = [float(game.get("top_coefficient", 0)) for game in data[:20] if game.get("top_coefficient")]

        if len(coefs) < 20:
            bot.reply_to(message, "Pas assez de données.")
            return

        low_count = sum(1 for c in coefs if c < 2)
        if low_count >= 10:
            heure = (datetime.now() + timedelta(minutes=10 + low_count)).strftime("%H:%M")
            bot.reply_to(message, f"Trop de coefficients bas. Reviens à : {heure}")

            # Fonction de surveillance
            def monitor_user(user_id, chat_id):
                while True:
                    try:
                        response = requests.get(url, params=params, headers=headers)
                        data = response.json()
                        coefs = [float(game.get("top_coefficient", 0)) for game in data[:20] if game.get("top_coefficient")]
                        if len(coefs) < 20:
                            time.sleep(60)
                            continue

                        low_count = sum(1 for c in coefs if c < 2)
                        if low_count < 10:
                            fake_message = type('obj', (object,), {'chat': type('chat', (object,), {'id': chat_id}), 'from_user': type('user', (object,), {'id': user_id})})()
                            send_prediction(fake_message)
                            break

                        time.sleep(60)
                    except Exception as e:
                        print(f"Erreur monitoring : {e}")
                        time.sleep(60)

            user_id = message.from_user.id
            chat_id = message.chat.id
            thread = threading.Thread(target=monitor_user, args=(user_id, chat_id))
            thread.start()

            return

        coefs_scaled = scaler.fit_transform(np.array(coefs).reshape(-1, 1)).flatten()

        global model
        if model is None:
            model = joblib.load(model_file) if os.path.exists(model_file) else train_model(coefs_scaled)

        # Ajuster ici, transformer les 5 derniers coefficients en une matrice (1, 5)
        prediction_input = np.array(coefs_scaled[-5:]).reshape(1, -1)  # Résolution de l'erreur en ajoutant reshape
        prediction = model.predict(prediction_input)[0]
        prediction = max(2.1, min(prediction, 7.0))

        assurance = round(1.9 + (prediction - 2.1) * (3.5 - 1.9) / (max(coefs) - min(coefs)), 2)
        assurance = min(assurance, prediction - 0.1)

        heure_prediction = (datetime.now() + timedelta(minutes=2 + int((prediction - 2.1) * 1.5))).strftime("%H:%M")
        last_five = "\n".join([f"Tour {i+1} : {coef}X" for i, coef in enumerate(coefs[-5:])])

        signal = f"""
♣︎ SIGNAL LUCKY JET ♣︎

➣ 𝐇𝐄𝐔𝐑𝐄 : {heure_prediction}🇨🇮
➣ 𝐂𝐎𝐄𝐅𝐅𝐈𝐂𝐈𝐄𝐍𝐓 : {round(prediction, 2)}X
➣ 𝐀𝐒𝐒𝐔𝐑𝐀𝐍𝐂𝐄 : {assurance}X

➣ 𝐋𝐄𝐒 𝟓 𝐃𝐄𝐑𝐍𝐈𝐄𝐑𝐒 𝐓𝐎𝐔𝐑𝐒 :
{last_five}

𝙿𝚕𝚊𝚝𝚎𝚏𝚘𝚛𝚖𝚎: 1WIN🔔
𝙲𝚘𝚍𝚎 𝚙𝚛𝚘𝚖𝚘: DIVINEJET 🔑
"""
        bot.reply_to(message, signal)
        user_id = message.from_user.id
        users_signaux[user_id]["count"] = max(users_signaux[user_id]["count"] - 1, 0)

        joblib.dump(model, model_file)

    except Exception as e:
        bot.reply_to(message, f"Erreur : {e}")

# Démarrer le bot
bot.polling()
