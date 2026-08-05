#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import random
import requests
import time
from datetime import datetime
from urllib.parse import unquote

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ===== КОНФИГ =====
SMALL_SUB_URL = "https://raw.githubusercontent.com/Ilyacom4ik/free-v2ray-2026/refs/heads/main/subscriptions/FreeCFGHub1.txt"
BIG_SUB_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"
KEYS_SOURCE_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"

PROXY_RU_URL = "https://raw.githubusercontent.com/Ilyacom4ik/TGPROXY/refs/heads/main/proxy_ru.txt"
PROXY_EU_URL = "https://raw.githubusercontent.com/Ilyacom4ik/TGPROXY/refs/heads/main/proxy_eu.txt"
PROXY_ALL_URL = "https://raw.githubusercontent.com/Ilyacom4ik/TGPROXY/refs/heads/main/proxy_all.txt"

SUPPORT_URL = "https://pay.cloudtips.ru/p/2486fa1a"
CHANNEL_URL = "https://t.me/FreeCFGHub"
CHANNEL_MIX_URL = "https://t.me/FreeCFGHubMIX"
LITE_KEYS_COUNT = 5
FULL_KEYS_COUNT = 7

STATS_FILE = "stats.json"
ADMIN_ID = 1321104939  # Твой Telegram ID

# ===== КАНАЛЫ ДЛЯ ПРОВЕРКИ =====
REQUIRED_CHANNELS = [
    {"id": "@FreeCFGHub", "url": "https://t.me/FreeCFGHub"},
    {"id": "@FreeCFGHubMIX", "url": "https://t.me/FreeCFGHubMIX"}
]

# ===== ССЫЛКИ =====
PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-FreeCFGHub-06-03"
TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-FreeCFGHub-06-03"

# ===== КЭШ ПОДПИСОК (запоминаем проверенных пользователей) =====
# <--- НОВОЕ
verified_users = set()

# ===== ЛОГГЕР =====
def log_action(user, action, details=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = user.get("id", "?")
    username = user.get("username", "")
    first_name = user.get("first_name", "")
    user_str = f"{first_name} (@{username}) [{user_id}]" if username else f"{first_name} [{user_id}]"
    log_entry = f"[{timestamp}] 👤 {user_str} ➜ {action}"
    if details:
        log_entry += f" | {details}"
    print(log_entry, flush=True)

# ===== СТАТИСТИКА =====
def load_stats():
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            "lite_requests": 0, 
            "full_requests": 0, 
            "sub_small": 0, 
            "sub_big": 0, 
            "proxy_ru": 0, 
            "proxy_eu": 0, 
            "proxy_all": 0,
            "ratings": [],
            "avg_rating": 0,
            "users": [],
            "donations": []
        }

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except:
        pass

def increment_stat(key):
    stats = load_stats()
    stats[key] = stats.get(key, 0) + 1
    save_stats(stats)

def get_all_users():
    stats = load_stats()
    users = stats.get("users", [])
    if not users:
        users = [ADMIN_ID]
    return users

def add_user(user_id):
    stats = load_stats()
    users = stats.get("users", [])
    if user_id not in users:
        users.append(user_id)
        stats["users"] = users
        save_stats(stats)

# ===== ПРОВЕРКА ПОДПИСКИ (с кэшем) =====
# <--- ИЗМЕНЕНО
def is_user_verified(user_id):
    """Проверяет, есть ли пользователь в кэше已验证"""
    return user_id in verified_users

def check_subscription(user_id):
    """Проверяет подписку на каналы (с кэшированием)"""
    # Если уже проверен — пропускаем
    if is_user_verified(user_id):
        return True
    
    for channel in REQUIRED_CHANNELS:
        channel_id = channel["id"]
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
            params = {"chat_id": channel_id, "user_id": user_id}
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            if not data.get("ok"):
                return False
            status = data.get("result", {}).get("status")
            if status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"Ошибка проверки подписки на {channel_id}: {e}", flush=True)
            return False
    
    # Если дошли сюда — подписка есть, добавляем в кэш
    verified_users.add(user_id)
    return True

def get_subscription_keyboard():
    buttons = []
    for channel in REQUIRED_CHANNELS:
        buttons.append([{"text": f"📢 Подписаться на {channel['id']}", "url": channel["url"]}])
    buttons.append([{"text": "🔄 Проверить подписку", "callback_data": "check_sub"}])
    return {"inline_keyboard": buttons}

# ===== РАССЫЛКА =====
def broadcast_message(text):
    users = get_all_users()
    sent = 0
    failed = 0
    for user_id in users:
        try:
            send_message(user_id, f"📢 {text}")
            sent += 1
        except Exception as e:
            print(f"Не удалось отправить {user_id}: {e}", flush=True)
            failed += 1
    return sent, failed

# ===== API ФУНКЦИИ =====
def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(f"{API}/getUpdates", params=params, timeout=35)
        return r.json().get("result", [])
    except Exception as e:
        print(f"Ошибка get_updates: {e}", flush=True)
        return []

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(f"{API}/sendMessage", json=data, timeout=10)
    except Exception as e:
        print(f"Ошибка send_message: {e}", flush=True)

def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(f"{API}/editMessageText", json=data, timeout=10)
    except Exception as e:
        print(f"Ошибка edit_message: {e}", flush=True)

def answer_callback(callback_id, text=""):
    try:
        requests.post(f"{API}/answerCallbackQuery", json={
            "callback_query_id": callback_id,
            "text": text
        }, timeout=10)
    except Exception as e:
        print(f"Ошибка answer_callback: {e}", flush=True)

def set_bot_commands():
    commands = [
        {"command": "start", "description": "🏠 Главное меню"},
        {"command": "sub", "description": "📁 Получить подписку"},
        {"command": "keys", "description": "🔑 Получить ключи"},
        {"command": "proxy", "description": "🌍 Прокси для Telegram"},
        {"command": "donate", "description": "💝 Добровольная помощь"},
        {"command": "support", "description": "🆘 Поддержка"},
        {"command": "status", "description": "📡 Статус"},
        {"command": "help", "description": "ℹ️ Справка"},
        {"command": "broadcast", "description": "📢 Рассылка (админ)"},
        {"command": "admin", "description": "⚙️ Панель администратора (админ)"},
    ]
    requests.post(f"{API}/setMyCommands", json={"commands": commands}, timeout=10)
    print("✅ Команды меню установлены", flush=True)

# ===== ТЕКСТЫ =====
def text_welcome(name):
    return (
        f"Привет, {name} 👋\n\n"
        "🆓 Здесь ты получишь ключи, подписки и прокси для Telegram.\n\n"
        "📁 <b>Команды:</b>\n"
        "/sub — получить подписку\n"
        "/keys — получить ключи\n"
        "/proxy — прокси для Telegram\n"
        "/donate — добровольная помощь\n"
        "/status — статус подписки\n"
        "/support — поддержка\n"
        "/help — справка\n\n"
        f"📢 {CHANNEL_URL}"
    )

TEXT_SUB_MENU = "🔶 <b>Выберите тип подписки</b>"
TEXT_KEYS_MENU = "🔷 <b>Выберите тип ключа</b>"
TEXT_STATUS_LOADING = "⏳ Проверяю..."

TEXT_HELP = (
    "ℹ️ <b>Справка</b>\n\n"
    "📁 <b>Команды:</b>\n"
    "/sub — получить подписку\n"
    "/keys — получить ключи\n"
    "/proxy — прокси для Telegram\n"
    "/donate — добровольная помощь\n"
    "/support — поддержка\n"
    "/status — статус подписки\n"
    "/help — эта справка\n\n"
    "📜 <b>Документы:</b>\n"
    f"• <a href='{PRIVACY_URL}'>Политика конфиденциальности</a>\n"
    f"• <a href='{TERMS_URL}'>Пользовательское соглашение</a>\n\n"
    f"📢 {CHANNEL_URL}"
)

TEXT_SUPPORT = (
    "🆘 <b>Поддержка</b>\n\n"
    "Если у вас возникли проблемы или вопросы, вы можете связаться со мной:\n\n"
    "📱 <b>Telegram:</b> @Ilyacom4ik\n"
    "📧 <b>Email:</b> FreeCFGHub@Gmail.com\n\n"
    "⏱ Время ответа: до 24 часов\n\n"
    f"📢 {CHANNEL_URL}"
)

TEXT_DONATE = (
    "💝 <b>Добровольная помощь</b>\n\n"
    "Если вам нравится наш проект и вы хотите поддержать его развитие, "
    "вы можете отправить конфигурационные ключи (vless://, vmess://, trojan://, ss://, tuic://, hysteria2://)\n\n"
    "📤 Отправьте ключ или подписку в ответ на это сообщение, и мы добавим его в общую базу.\n\n"
    "🔗 Также вы можете поддержать нас материально:\n"
    f"{SUPPORT_URL}\n\n"
    "Спасибо за вашу поддержку! ❤️"
)

# ===== ЗАГРУЗКА =====
def fetch_proxies_from_url(url):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            proxies = []
            for line in r.text.splitlines():
                line = line.strip()
                if line.startswith("tg://proxy?"):
                    proxies.append(line)
            return proxies
        return []
    except Exception as e:
        print(f"Ошибка загрузки прокси: {e}", flush=True)
        return []

def fetch_and_parse_keys():
    try:
        r = requests.get(KEYS_SOURCE_URL, timeout=15)
        if r.status_code != 200:
            return None, f"Ошибка загрузки: {r.status_code}"
        lite_keys = []
        full_keys = []
        for line in r.text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if not re.match(r'^(vless|vmess|trojan|ss|tuic|hysteria2)://', line):
                continue
            if re.search(r'\bLite\b', line, re.IGNORECASE):
                lite_keys.append(line)
            else:
                full_keys.append(line)
        return {"lite": lite_keys, "full": full_keys}, None
    except Exception as e:
        return None, str(e)

def get_random_keys(keys_list, count):
    if not keys_list:
        return []
    return random.sample(keys_list, min(count, len(keys_list)))

def get_status_text():
    keys_data, error = fetch_and_parse_keys()
    if error:
        return f"❌ Ошибка: {error}"
    stats = load_stats()
    avg_rating = stats.get("avg_rating", 0)
    return (
        f"📊 <b>Статус подписки</b>\n\n"
        f"🏳️ Lite ключей: {len(keys_data.get('lite', []))}\n"
        f"🏴 Full ключей: {len(keys_data.get('full', []))}\n"
        f"⭐ Рейтинг проекта: {avg_rating:.1f} / 5.0\n"
        f"👥 Пользователей: {len(stats.get('users', []))}\n\n"
        f"📢 {CHANNEL_URL}"
    )

# ===== КЛАВИАТУРЫ =====
def kb_main():
    return {
        "inline_keyboard": [
            [{"text": "📁 Получить подписку", "callback_data": "menu_sub"}],
            [{"text": "🔑 Получить ключи", "callback_data": "menu_keys"}],
            [{"text": "🌍 Прокси для Telegram", "callback_data": "menu_proxy"}],
            [{"text": "💝 Добровольная помощь", "callback_data": "menu_donate"}],
            [{"text": "⭐ Оценить проект", "callback_data": "rate_project"}],
            [{"text": "💳 Поддержать канал", "url": SUPPORT_URL}],
            [{"text": "ℹ️ Справка", "callback_data": "menu_help"}],
        ]
    }

def kb_subscriptions():
    return {
        "inline_keyboard": [
            [{"text": "📦 Небольшая подписка", "callback_data": "sub_small"}],
            [{"text": "🗂 Большая подписка", "callback_data": "sub_big"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def kb_keys():
    return {
        "inline_keyboard": [
            [{"text": "Lite", "callback_data": "keys_lite"}, {"text": "Full", "callback_data": "keys_full"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def kb_proxy_countries():
    return {
        "inline_keyboard": [
            [{"text": "🇷🇺 Россия", "callback_data": "proxy_ru"}],
            [{"text": "🇪🇺 Европа", "callback_data": "proxy_eu"}],
            [{"text": "🌍 Все страны", "callback_data": "proxy_all"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def kb_rating():
    buttons = []
    for i in range(5, 0, -1):
        stars = "⭐" * i
        buttons.append([{"text": f"{stars} {i}", "callback_data": f"rate_{i}"}])
    buttons.append([{"text": "◀️ Назад", "callback_data": "back_main"}])
    return {"inline_keyboard": buttons}

def kb_admin():
    stats = load_stats()
    avg_rating = stats.get("avg_rating", 0)
    ratings_count = len(stats.get("ratings", []))
    return {
        "inline_keyboard": [
            [{"text": f"⭐ Рейтинг: {avg_rating:.1f} ({ratings_count} оценок)", "callback_data": "admin_rating"}],
            [{"text": "📊 Статистика", "callback_data": "admin_stats"}],
            [{"text": "👥 Пользователи", "callback_data": "admin_users"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def kb_back():
    return {"inline_keyboard": [[{"text": "🏠 В главное меню", "callback_data": "back_main"}]]}

# ===== ОБРАБОТКА =====
def handle_message(msg):
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    user = msg.get("from", {})
    user_id = user.get("id")
    name = user.get("first_name") or "друг"

    if not chat_id:
        return

    if user_id:
        add_user(user_id)

    # ===== АДМИН-КОМАНДЫ (всегда работают) =====
    if user_id == ADMIN_ID:
        if text.startswith("/broadcast "):
            msg_text = text[11:].strip()
            if msg_text:
                sent, failed = broadcast_message(msg_text)
                send_message(chat_id, f"✅ Рассылка отправлена: {sent} доставлено, {failed} не доставлено")
            else:
                send_message(chat_id, "⚠️ Используйте: /broadcast [текст сообщения]")
            return
        if text == "/admin":
            log_action(user, "⚙️ ОТКРЫЛ ПАНЕЛЬ АДМИНИСТРАТОРА")
            send_message(chat_id, "⚙️ <b>Панель администратора</b>", reply_markup=kb_admin())
            return

    # <--- ИЗМЕНЕНО: проверка подписки с кэшем
    # Если пользователь уже верифицирован - пропускаем проверку
    if not is_user_verified(user_id):
        # Проверяем подписку
        if not check_subscription(user_id):
            # Если не подписан - показываем кнопки подписки
            if text != "/start":
                send_message(
                    chat_id,
                    "⚠️ <b>Для использования бота необходимо подписаться на каналы:</b>\n\n"
                    f"📢 {CHANNEL_URL}\n"
                    f"📢 {CHANNEL_MIX_URL}\n\n"
                    "После подписки нажмите кнопку ниже 👇",
                    reply_markup=get_subscription_keyboard()
                )
            else:
                # Для /start показываем приветствие с кнопками подписки
                send_message(
                    chat_id,
                    f"Привет, {name} 👋\n\n"
                    "⚠️ <b>Для использования бота необходимо подписаться на каналы:</b>\n\n"
                    f"📢 {CHANNEL_URL}\n"
                    f"📢 {CHANNEL_MIX_URL}\n\n"
                    "После подписки нажмите кнопку ниже 👇",
                    reply_markup=get_subscription_keyboard()
                )
            return

    # Добровольная помощь (отправка ключей)
    if text.startswith(("vless://", "vmess://", "trojan://", "ss://", "tuic://", "hysteria2://")):
        log_action(user, "💝 ОТПРАВИЛ КЛЮЧ ДЛЯ ПОМОЩИ")
        stats = load_stats()
        donations = stats.get("donations", [])
        donations.append({
            "user": user_id,
            "username": user.get("username", ""),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "key": text[:50] + "..." if len(text) > 50 else text
        })
        stats["donations"] = donations
        save_stats(stats)
        send_message(chat_id, "💝 <b>Спасибо за вашу помощь!</b>\n\nКлюч принят и будет добавлен в общую базу.\n\nСпасибо, что поддерживаете проект! ❤️")
        send_message(ADMIN_ID, f"📥 Получен ключ от @{user.get('username', 'Unknown')}\n\n<code>{text[:100]}...</code>")
        return

    if text == "/start":
        log_action(user, "🚀 ЗАПУСТИЛ БОТА")
        send_message(chat_id, text_welcome(name), reply_markup=kb_main())
    elif text == "/sub":
        log_action(user, "📁 ОТКРЫЛ МЕНЮ ПОДПИСОК")
        send_message(chat_id, TEXT_SUB_MENU, reply_markup=kb_subscriptions())
    elif text == "/keys":
        log_action(user, "🔑 ОТКРЫЛ МЕНЮ КЛЮЧЕЙ")
        send_message(chat_id, TEXT_KEYS_MENU, reply_markup=kb_keys())
    elif text == "/proxy":
        log_action(user, "🌍 ОТКРЫЛ МЕНЮ ПРОКСИ")
        send_message(chat_id, "🌍 Выберите регион:", reply_markup=kb_proxy_countries())
    elif text == "/status":
        log_action(user, "📡 ЗАПРОСИЛ СТАТУС")
        send_message(chat_id, TEXT_STATUS_LOADING)
        send_message(chat_id, get_status_text())
    elif text == "/donate":
        log_action(user, "💝 ОТКРЫЛ МЕНЮ ПОМОЩИ")
        send_message(chat_id, TEXT_DONATE, reply_markup=kb_back())
    elif text == "/support":
        log_action(user, "🆘 ОТКРЫЛ ПОДДЕРЖКУ")
        send_message(chat_id, TEXT_SUPPORT, reply_markup=kb_back())
    elif text in ("/help", "/info"):
        log_action(user, "ℹ️ ОТКРЫЛ СПРАВКУ")
        send_message(chat_id, TEXT_HELP, reply_markup=kb_back())

def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    data = cb.get("data", "")
    user = cb.get("from", {})
    user_id = user.get("id")
    name = user.get("first_name") or "друг"

    answer_callback(cb["id"])

    # <--- ИЗМЕНЕНО: проверка подписки с кэшем
    if not is_user_verified(user_id):
        if data != "check_sub":
            send_message(
                chat_id,
                "⚠️ <b>Для использования бота необходимо подписаться на каналы:</b>\n\n"
                f"📢 {CHANNEL_URL}\n"
                f"📢 {CHANNEL_MIX_URL}\n\n"
                "После подписки нажмите кнопку ниже 👇",
                reply_markup=get_subscription_keyboard()
            )
            return

    if data == "check_sub":
        if check_subscription(user_id):
            # <--- НОВОЕ: добавляем в кэш
            verified_users.add(user_id)
            edit_message(chat_id, message_id, "✅ <b>Подписка подтверждена!</b>\n\n" + text_welcome(name), reply_markup=kb_main())
        else:
            edit_message(chat_id, message_id, "❌ <b>Вы не подписаны на все каналы!</b>\n\nПожалуйста, подпишитесь:", reply_markup=get_subscription_keyboard())

    elif data == "back_main":
        log_action(user, "🏠 ВЕРНУЛСЯ В ГЛАВНОЕ МЕНЮ")
        edit_message(chat_id, message_id, text_welcome(name), reply_markup=kb_main())

    elif data == "menu_sub":
        log_action(user, "📁 ОТКРЫЛ МЕНЮ ПОДПИСОК")
        edit_message(chat_id, message_id, TEXT_SUB_MENU, reply_markup=kb_subscriptions())
    elif data == "sub_small":
        log_action(user, "📦 ВЫБРАЛ НЕБОЛЬШУЮ ПОДПИСКУ")
        increment_stat("sub_small")
        edit_message(chat_id, message_id, f"📦 <b>Небольшая подписка</b>\n\n<code>{SMALL_SUB_URL}</code>", reply_markup=kb_back())
    elif data == "sub_big":
        log_action(user, "🗂 ВЫБРАЛ БОЛЬШУЮ ПОДПИСКУ")
        increment_stat("sub_big")
        edit_message(chat_id, message_id, f"🗂 <b>Большая подписка</b>\n\n<code>{BIG_SUB_URL}</code>", reply_markup=kb_back())

    elif data == "menu_keys":
        log_action(user, "🔑 ОТКРЫЛ МЕНЮ КЛЮЧЕЙ")
        edit_message(chat_id, message_id, TEXT_KEYS_MENU, reply_markup=kb_keys())
    elif data in ("keys_lite", "keys_full"):
        key_type = "lite" if data == "keys_lite" else "full"
        count = LITE_KEYS_COUNT if key_type == "lite" else FULL_KEYS_COUNT
        label = "Lite" if key_type == "lite" else "Full"
        log_action(user, f"🔑 ЗАПРОСИЛ КЛЮЧИ {label}")
        increment_stat("lite_requests" if key_type == "lite" else "full_requests")
        edit_message(chat_id, message_id, f"⏳ Загружаю...")
        keys_data, error = fetch_and_parse_keys()
        if error:
            edit_message(chat_id, message_id, f"❌ {error}", reply_markup=kb_back())
            return
        keys = keys_data.get(key_type, [])
        if not keys:
            edit_message(chat_id, message_id, "😔 Ключи временно недоступны", reply_markup=kb_back())
            return
        selected = get_random_keys(keys, count)
        keys_block = "\n\n".join(f"<code>{k}</code>" for k in selected)
        edit_message(chat_id, message_id, f"🔑 <b>{label} — {len(selected)} шт.</b>\n\n{keys_block}\n\n📢 {CHANNEL_URL}", reply_markup=kb_back())

    elif data == "menu_proxy":
        log_action(user, "🌍 ОТКРЫЛ МЕНЮ ПРОКСИ")
        edit_message(chat_id, message_id, "🌍 Выберите регион:", reply_markup=kb_proxy_countries())
    elif data.startswith("proxy_"):
        region = data.split("_")[1]
        if region == "ru":
            url, label = PROXY_RU_URL, "🇷🇺 Россия"
            increment_stat("proxy_ru")
        elif region == "eu":
            url, label = PROXY_EU_URL, "🇪🇺 Европа"
            increment_stat("proxy_eu")
        else:
            url, label = PROXY_ALL_URL, "🌍 Все страны"
            increment_stat("proxy_all")
        log_action(user, f"🌍 ЗАПРОСИЛ ПРОКСИ {label}")
        proxies = fetch_proxies_from_url(url)
        if not proxies:
            edit_message(chat_id, message_id, f"❌ Прокси для {label} временно недоступны", reply_markup=kb_proxy_countries())
            return
        proxies = proxies[:5]
        keyboard = [[{"text": f"🔵 Подключиться #{i}", "url": p}] for i, p in enumerate(proxies, 1)]
        keyboard.append([{"text": "◀️ Назад", "callback_data": "menu_proxy"}])
        edit_message(chat_id, message_id, f"🌍 <b>MTProto прокси для Telegram</b>\n\n📍 {label}\n📦 Доступно: {len(proxies)}\n\n📢 {CHANNEL_URL}", reply_markup={"inline_keyboard": keyboard})

    elif data == "menu_donate":
        log_action(user, "💝 ОТКРЫЛ МЕНЮ ПОМОЩИ")
        edit_message(chat_id, message_id, TEXT_DONATE, reply_markup=kb_back())

    elif data == "rate_project":
        log_action(user, "⭐ ОТКРЫЛ ОЦЕНКУ ПРОЕКТА")
        edit_message(chat_id, message_id, "⭐ <b>Оцените наш проект</b>\n\nНасколько вам нравится бот? Выберите оценку от 1 до 5:", reply_markup=kb_rating())

    elif data.startswith("rate_"):
        rating = int(data.split("_")[1])
        log_action(user, f"⭐ ПОСТАВИЛ ОЦЕНКУ {rating}")
        stats = load_stats()
        ratings = stats.get("ratings", [])
        ratings.append({"user": user_id, "rating": rating, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        stats["ratings"] = ratings
        avg_rating = sum(r["rating"] for r in ratings) / len(ratings) if ratings else 0
        stats["avg_rating"] = avg_rating
        save_stats(stats)
        stars = "⭐" * rating
        edit_message(chat_id, message_id, f"✅ <b>Спасибо за вашу оценку!</b>\n\n{stars} {rating}/5\n\nВаше мнение очень важно для нас! ❤️", reply_markup=kb_back())

    elif data == "menu_help":
        log_action(user, "ℹ️ ОТКРЫЛ СПРАВКУ")
        edit_message(chat_id, message_id, TEXT_HELP, reply_markup=kb_back())

    # АДМИН-КОМАНДЫ
    elif data == "admin_rating":
        stats = load_stats()
        ratings = stats.get("ratings", [])
        avg = stats.get("avg_rating", 0)
        text = f"⭐ <b>Рейтинг проекта</b>\n\nСредняя оценка: {avg:.1f} / 5.0\nВсего оценок: {len(ratings)}\n\n"
        if ratings:
            text += "📊 <b>Распределение:</b>\n"
            for i in range(5, 0, -1):
                count = sum(1 for r in ratings if r["rating"] == i)
                percent = count / len(ratings) * 100 if ratings else 0
                text += f"{'⭐' * i} {i} — {count} ({percent:.1f}%)\n"
        edit_message(chat_id, message_id, text, reply_markup=kb_admin())
    elif data == "admin_stats":
        stats = load_stats()
        text = (
            "📊 <b>Статистика бота</b>\n\n"
            f"👥 Пользователей: {len(stats.get('users', []))}\n"
            f"📁 Запросов подписок (маленькая): {stats.get('sub_small', 0)}\n"
            f"📁 Запросов подписок (большая): {stats.get('sub_big', 0)}\n"
            f"🔑 Запросов Lite ключей: {stats.get('lite_requests', 0)}\n"
            f"🔑 Запросов Full ключей: {stats.get('full_requests', 0)}\n"
            f"🌍 Прокси Россия: {stats.get('proxy_ru', 0)}\n"
            f"🌍 Прокси Европа: {stats.get('proxy_eu', 0)}\n"
            f"🌍 Прокси Все страны: {stats.get('proxy_all', 0)}\n"
            f"💝 Пожертвований ключей: {len(stats.get('donations', []))}\n"
            f"⭐ Оценок проекта: {len(stats.get('ratings', []))}\n"
        )
        edit_message(chat_id, message_id, text, reply_markup=kb_admin())
    elif data == "admin_users":
        stats = load_stats()
        users = stats.get("users", [])
        text = f"👥 <b>Пользователи</b>\n\nВсего: {len(users)}\n\n"
        if users:
            for u in users[:20]:
                text += f"• {u}\n"
            if len(users) > 20:
                text += f"\n... и еще {len(users) - 20} пользователей"
        edit_message(chat_id, message_id, text, reply_markup=kb_admin())

# ===== MAIN =====
def main():
    print("🤖 Бот FreeCFGHub запущен", flush=True)
    set_bot_commands()
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            try:
                if "message" in update:
                    handle_message(update["message"])
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])
            except Exception as e:
                print(f"Ошибка: {e}", flush=True)

if __name__ == "__main__":
    main()
