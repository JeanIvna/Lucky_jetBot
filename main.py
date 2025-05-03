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

# Charger les variables d'environnement à partir du fichier .env
load_dotenv()

# === Ton token ici ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# === Ton ID Telegram pour accès Admin ===
ADMIN_ID = 6491165519  # Ton vrai ID Telegram ici

# === API ===
url = "https://crash-gateway-cc-cr.gamedev-tech.cc/history"
params = {
    "id_n": "1play_luckyjet",
    "id_i": "1"
}
headers = {
    "Cookie": os.getenv("API_COOKIE")  # Ton cookie API depuis les variables d'environnement
}

# === Variables de gestion des signaux ===
signaux_activés = True  # Initialement les signaux sont activés
last_signal_time = {}  # Dictionnaire pour stocker le dernier envoi de signal par utilisateur
signaux_restants = {}  # Dictionnaire pour stocker le nombre de signaux restants par utilisateur

# === Ton ID pour vérification ===
MON_ID = 6908816326  # Ton ID utilisateur spécifique pour les signaux

# === Variables du modèle de Machine Learning ===
model = None  # Modèle de machine learning
scaler = StandardScaler()  # Scaler pour normaliser les données
model_file = "lucky_jet_model.pkl"

# === Menu de démarrage ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🎯 Signal"), KeyboardButton("👤 Mon compte"))
    markup.add(KeyboardButton("🛡️ Admin"))
    bot.send_message(message.chat.id, "Bienvenue dans le bot ! Choisis une option :", reply_markup=markup)

# === Gestion du menu ===
@bot.message_handler(func=lambda message: message.text in ["🎯 Signal", "👤 Mon compte", "🛡️ Admin"])
def handle_menu(message):
    if message.text == "🎯 Signal":
        if signaux_activés:
            # Vérifier l'anti-spam (2 minutes)
            user_id = message.from_user.id
            if user_id in last_signal_time:
                time_since_last_signal = datetime.now() - last_signal_time[user_id]
                if time_since_last_signal < timedelta(minutes=2):
                    bot.reply_to(message, "Veuillez patienter encore quelques minutes avant de demander un nouveau signal.")
                    return

            send_prediction(message)
            # Mettre à jour le dernier envoi de signal
            last_signal_time[user_id] = datetime.now()
        else:
            bot.reply_to(message, "Les signaux sont actuellement désactivés.")
    elif message.text == "👤 Mon compte":
        # Afficher le nombre de signaux restants
        user_id = message.from_user.id
        remaining_signals = signaux_restants.get(user_id, 0)
        bot.reply_to(message, f"Ton ID Telegram est : {user_id}\nSignaux restants : {remaining_signals}")
    elif message.text == "🛡️ Admin":
        # Vérification de l'ID Admin
        if message.from_user.id == ADMIN_ID:
            send_admin_options(message)
        else:
            bot.reply_to(message, f"Accès refusé : réservé à l’administrateur. Ton ID : {message.from_user.id}")
    else:
        bot.reply_to(message, "Commande inconnue.")

# === Fonction de gestion des options Admin ===
def send_admin_options(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Activer les signaux"), KeyboardButton("Désactiver les signaux"))
    markup.add(KeyboardButton("État des signaux"), KeyboardButton("Retour"))
    bot.send_message(message.chat.id, "Bienvenue Admin ! Choisis une option :", reply_markup=markup)

# === Fonction pour activer/désactiver les signaux ===
@bot.message_handler(func=lambda message: message.text in ["Activer les signaux", "Désactiver les signaux", "État des signaux", "Retour"])
def handle_admin_actions(message):
    global signaux_activés

    if message.text == "Activer les signaux":
        signaux_activés = True
        bot.reply_to(message, "Les signaux sont maintenant activés.")
    
    elif message.text == "Désactiver les signaux":
        signaux_activés = False
        bot.reply_to(message, "Les signaux sont maintenant désactivés.")
    
    elif message.text == "État des signaux":
        state = "activés" if signaux_activés else "désactivés"
        bot.reply_to(message, f"Les signaux sont actuellement {state}.")
    
    elif message.text == "Retour":
        send_welcome(message)

# === Fonction pour prédire et gérer les signaux ===
def send_prediction(message):
    try:
        if message.from_user.id != MON_ID:
            bot.reply_to(message, "Vous n'avez pas accès aux signaux.")
            return

        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            bot.reply_to(message, "Erreur API : impossible de récupérer les données.")
            return

        data = response.json()
        coefs = [float(game.get("top_coefficient", 0)) for game in data[:20] if game.get("top_coefficient")]

        if len(coefs) < 20:
            bot.reply_to(message, "Pas assez de données pour générer un signal.")
            return

        # Vérification des coefficients inférieurs à 2X
        low_coefficients_count = sum(1 for coef in coefs if coef < 2)

        # Si plus de la moitié des coefficients sont inférieurs à 2, la prédiction est rejetée
        if low_coefficients_count >= 10:
            bot.reply_to(message, "Trop de coefficients inférieurs à 2X détectés. Prédiction rejetée.")
            
            # Augmenter le délai d'attente en fonction de l'anomalie
            wait_time = 10 + low_coefficients_count  # Plus il y a de faibles coefficients, plus l'attente est longue
            heure_prediction = (datetime.now() + timedelta(minutes=wait_time)).strftime("%H:%M")
            bot.reply_to(message, f"Veuillez patienter davantage. Nouvelle prédiction dans : {heure_prediction}")
            return  # Fin de la fonction pour ne pas envoyer de signal

        # Normaliser les données
        coefs_scaled = scaler.fit_transform(np.array(coefs).reshape(-1, 1)).flatten()

        # Charger le modèle existant ou en créer un nouveau si nécessaire
        global model
        if model is None:
            model = joblib.load(model_file) if os.path.exists(model_file) else train_model(coefs_scaled)

        # Effectuer la prédiction pour les coefficients futurs
        prediction = model.predict([coefs_scaled[-5:]])[0]  # Utiliser les 5 derniers coefficients pour la prédiction
        prediction = max(2.1, min(prediction, 7.0))  # Limiter la plage de la prédiction

        # Calculer l'assurance
        assurance = 1.9 + (prediction - 2.1) * (3.5 - 1.9) / (max(coefs) - min(coefs))
        assurance = round(min(assurance, prediction - 0.1), 2)

        # Durée d'attente entre 2 et 7 minutes
        wait_time = 2 + int((prediction - 2.1) * 1.5)

        # Calculer l'heure de prédiction
        heure_prediction = (datetime.now() + timedelta(minutes=wait_time)).strftime("%H:%M")

        # Message de signal avec les 5 derniers tours visibles
        last_five_tours = "\n".join([f"Tour {i+1}: {coef}X" for i, coef in enumerate(coefs[-5:])])

        signal = f"""
♣︎ SIGNAL LUCKY JET ♣︎

➣ 𝐇𝐄𝐔𝐑𝐄 : {heure_prediction}🇨🇮

➣ 𝐂𝐎𝐄𝐅𝐅𝐈𝐂𝐈𝐄𝐍𝐓 : {prediction}X
➣ 𝐀𝐒𝐒𝐔𝐑𝐀𝐍𝐂𝐄 : {assurance}X

➣ 𝐋𝐄𝐒 𝟓 𝐃𝐄𝐑𝐍𝐈𝐄𝐑𝐒 𝐓𝐎𝐔𝐑𝐒 :
{last_five_tours}

𝙿𝚕𝚊𝚝𝚎𝚏𝚘𝚛𝚎: 1WIN🔔
𝙲𝚘𝚍𝚎 𝚙𝚛𝚘𝚖𝚘: DIVINEJET 🔑
"""
        bot.reply_to(message, signal)

        # Sauvegarder le modèle mis à jour
        joblib.dump(model, model_file)

        # Décrémenter les signaux restants
        user_id = message.from_user.id
        signaux_restants[user_id] = signaux_restants.get(user_id, 10) - 1
        if signaux_restants[user_id] < 0:
            signaux_restants[user_id] = 0

    except Exception as e:
        bot.reply_to(message, f"Erreur : {e}")

# === Fonction pour entraîner le modèle ===
def train_model(coefs_scaled):
    # Créer un modèle de Machine Learning pour la prédiction
    model = xgb.XGBRegressor(objective="reg:squarederror")
    model.fit(coefs_scaled[:-1].reshape(-1, 1), coefs_scaled[1:])
    return model

# === Démarrage du bot ===
bot.polling(non_stop=True)
