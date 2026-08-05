#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import random
import requests
from datetime import datetime

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ===== ПОДПИСКИ И КЛЮЧИ =====
SMALL_SUB_URL = "https://raw.githubusercontent.com/Ilyacom4ik/free-v2ray-2026/refs/heads/main/subscriptions/FreeCFGHub1.txt"
BIG_SUB_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"
KEYS_SOURCE_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"

# ===== ПРОКСИ =====
PROXY_RU_URL = "https://raw.githubusercontent.com/Ilyacom4ik/TGPROXY/refs/heads/main/proxy_ru.txt"
PROXY_EU_URL = "https://raw.githubusercontent.com/Ilyacom4ik/TGPROXY/refs/heads/main/proxy_eu.txt"
PROXY_ALL_URL = "https://raw.githubusercontent.com/Ilyacom4ik/TGPROXY/refs/heads/main/proxy_all.txt"

SUPPORT_URL = "https://pay.cloudtips.ru/p/2486fa1a"
CHANNEL_URL = "https://t.me/FreeCFGHub"
LITE_KEYS_COUNT = 5
FULL_KEYS_COUNT = 7

STATS_FILE = "stats.json"
SHARED_KEYS_FILE = "shared_keys.txt"
ADMIN_ID = 1321104939  # Твой Telegram ID

# ===== ОБЯЗАТЕЛЬНАЯ ПОДПИСКА =====
REQUIRED_CHANNELS = [
    {"username": "@FreeCFGHub", "title": "📢 FreeCFGHub", "url": "https://t.me/FreeCFGHub"},
    {"username": "@FreeCFGHubMIX", "title": "📢 FreeCFGHub MIX", "url": "https://t.me/FreeCFGHubMIX"},
]

# ===== ПОДДЕРЖКА / ДОКУМЕНТЫ =====
SUPPORT_USERNAME = "@Ilyacom4ik"
SUPPORT_EMAIL = "FreeCFGHub@Gmail.com"
PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-FreeCFGHub-06-03"
TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-FreeCFGHub-06-03"

# Ключи-протоколы, которые принимаем при добровольной отправке
KEY_PROTOCOL_RE = re.compile(r'^(vless|vmess|trojan|ss|tuic|hysteria2)://', re.IGNORECASE)

# Временное состояние пользователей в памяти (не переживает перезапуск)
# uid -> "waiting_key" | None
user_state = {}

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

def user_str_from(user):
    user_id = user.get("id", "?")
    username = user.get("username", "")
    first_name = user.get("first_name", "")
    return f"{first_name} (@{username}) [{user_id}]" if username else f"{first_name} [{user_id}]"

# ===== СТАТИСТИКА =====
def load_stats():
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    data.setdefault("lite_requests", 0)
    data.setdefault("full_requests", 0)
    data.setdefault("sub_small", 0)
    data.setdefault("sub_big", 0)
    data.setdefault("proxy_ru", 0)
    data.setdefault("proxy_eu", 0)
    data.setdefault("proxy_all", 0)
    data.setdefault("users", [])
    data.setdefault("ratings", {"sum": 0, "count": 0, "users": {}})
    return data

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception:
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

def save_rating(user_id, score):
    stats = load_stats()
    ratings = stats["ratings"]
    prev = ratings["users"].get(str(user_id))
    if prev is not None:
        ratings["sum"] += (score - prev)
    else:
        ratings["sum"] += score
        ratings["count"] += 1
    ratings["users"][str(user_id)] = score
    stats["ratings"] = ratings
    save_stats(stats)

def get_rating_text():
    stats = load_stats()
    ratings = stats["ratings"]
    count = ratings.get("count", 0)
    total = ratings.get("sum", 0)
    avg = (total / count) if count else 0
    stars_full = "⭐" * round(avg)
    return (
        f"⭐ <b>Оценка проекта</b>\n\n"
        f"Средняя оценка: {avg:.2f} / 5 {stars_full}\n"
        f"Голосов: {count}"
    )

def get_stats_text():
    stats = load_stats()
    return (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {len(stats.get('users', []))}\n"
        f"🏳️ Lite запросов: {stats.get('lite_requests', 0)}\n"
        f"🏴 Full запросов: {stats.get('full_requests', 0)}\n"
        f"📦 Небольшая подписка: {stats.get('sub_small', 0)}\n"
        f"🗂 Большая подписка: {stats.get('sub_big', 0)}\n"
        f"🇷🇺 Прокси RU: {stats.get('proxy_ru', 0)}\n"
        f"🇪🇺 Прокси EU: {stats.get('proxy_eu', 0)}\n"
        f"🌍 Прокси ALL: {stats.get('proxy_all', 0)}\n"
    )

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

# ===== ФУНКЦИИ TELEGRAM API =====

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

def answer_callback(callback_id, text="", show_alert=False):
    try:
        requests.post(f"{API}/answerCallbackQuery", json={
            "callback_query_id": callback_id,
            "text": text,
            "show_alert": show_alert
        }, timeout=10)
    except Exception as e:
        print(f"Ошибка answer_callback: {e}", flush=True)

def get_chat_member(channel_username, user_id):
    try:
        r = requests.get(f"{API}/getChatMember", params={
            "chat_id": channel_username,
            "user_id": user_id
        }, timeout=10)
        data = r.json()
        if not data.get("ok"):
            print(f"getChatMember ошибка для {channel_username}: {data}", flush=True)
            return None
        return data["result"].get("status")
    except Exception as e:
        print(f"Ошибка get_chat_member: {e}", flush=True)
        return None

def is_subscribed(user_id):
    """Проверяет подписку пользователя на все обязательные каналы."""
    for ch in REQUIRED_CHANNELS:
        status = get_chat_member(ch["username"], user_id)
        if status not in ("member", "administrator", "creator"):
            return False
    return True

def set_bot_commands():
    commands = [
        {"command": "start", "description": "🏠 Главное меню"},
        {"command": "sub", "description": "📁 Получить подписку"},
        {"command": "keys", "description": "🔑 Получить ключи"},
        {"command": "proxy", "description": "🌍 Прокси для Telegram"},
        {"command": "status", "description": "📡 Статус"},
        {"command": "support", "description": "🆘 Поддержка"},
        {"command": "help", "description": "ℹ️ Справка"},
        {"command": "broadcast", "description": "📢 Рассылка (админ)"},
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
        "/status — статус подписки\n"
        "/support — поддержка\n\n"
        f"📢 {CHANNEL_URL}"
    )

TEXT_SUB_MENU = "🔶 <b>Выберите тип подписки</b>"
TEXT_KEYS_MENU = "🔷 <b>Выберите тип ключа</b>"
TEXT_HELP = "📜 <b>Справка</b>\n\n/sub — подписка\n/keys — ключи\n/proxy — прокси\n/support — поддержка\n/status — статус"
TEXT_STATUS_LOADING = "⏳ Проверяю..."

TEXT_NEED_SUBSCRIPTION = (
    "🔒 <b>Доступ ограничен</b>\n\n"
    "Чтобы пользоваться ботом, подпишись на наши каналы, а затем нажми "
    "«✅ Я подписался»."
)

TEXT_SHARE_KEY_PROMPT = (
    "🎁 <b>Поделиться ключом</b>\n\n"
    "Пришли ключ одним сообщением. Поддерживаются протоколы:\n"
    "<code>vless://</code>, <code>vmess://</code>, <code>trojan://</code>, "
    "<code>ss://</code>, <code>tuic://</code>, <code>hysteria2://</code>\n\n"
    "Чтобы отменить — нажми «◀️ Назад»."
)

TEXT_SHARE_KEY_THANKS = "🙏 Спасибо! Ключ отправлен на проверку админу."
TEXT_SHARE_KEY_BAD_FORMAT = (
    "⚠️ Не похоже на ключ поддерживаемого протокола. Пришли ссылку, "
    "начинающуюся с vless://, vmess://, trojan://, ss://, tuic:// или hysteria2://, "
    "либо нажми «◀️ Назад»."
)

def text_support():
    return (
        "🆘 <b>Поддержка</b>\n\n"
        f"По всем вопросам пиши сюда: {SUPPORT_USERNAME}\n"
        f"Либо на почту: {SUPPORT_EMAIL}"
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
    return (
        f"📊 <b>Статус подписки</b>\n\n"
        f"🏳️ Lite ключей: {len(keys_data.get('lite', []))}\n"
        f"🏴 Full ключей: {len(keys_data.get('full', []))}\n\n"
        f"📢 {CHANNEL_URL}"
    )

# ===== КЛАВИАТУРЫ =====

def kb_main(user_id=None):
    rows = [
        [{"text": "📁 Получить подписку", "callback_data": "menu_sub"}],
        [{"text": "🔑 Получить ключи", "callback_data": "menu_keys"}],
        [{"text": "🌍 Прокси для Telegram", "callback_data": "menu_proxy"}],
        [{"text": "🎁 Поделиться ключом", "callback_data": "share_key"}],
        [{"text": "💳 Поддержать канал", "url": SUPPORT_URL}],
        [{"text": "🆘 Поддержка", "callback_data": "menu_support"}, {"text": "ℹ️ Справка", "callback_data": "menu_help"}],
        [{"text": "🔒 Конфиденциальность", "url": PRIVACY_URL}, {"text": "📄 Соглашение", "url": TERMS_URL}],
    ]
    if user_id == ADMIN_ID:
        rows.append([{"text": "⚙️ Настройки (админ)", "callback_data": "admin_settings"}])
    return {"inline_keyboard": rows}

def kb_subscribe_required():
    rows = [[{"text": ch["title"], "url": ch["url"]}] for ch in REQUIRED_CHANNELS]
    rows.append([{"text": "✅ Я подписался", "callback_data": "check_sub"}])
    return {"inline_keyboard": rows}

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

def kb_back():
    return {"inline_keyboard": [[{"text": "🏠 В главное меню", "callback_data": "back_main"}]]}

def kb_share_key():
    return {"inline_keyboard": [[{"text": "◀️ Назад", "callback_data": "back_main"}]]}

def kb_rating():
    return {
        "inline_keyboard": [[
            {"text": "⭐", "callback_data": "rate_1"},
            {"text": "⭐⭐", "callback_data": "rate_2"},
            {"text": "⭐⭐⭐", "callback_data": "rate_3"},
            {"text": "⭐⭐⭐⭐", "callback_data": "rate_4"},
            {"text": "⭐⭐⭐⭐⭐", "callback_data": "rate_5"},
        ]]
    }

def kb_admin_settings():
    return {
        "inline_keyboard": [
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

# ===== ОБРАБОТКА =====

def send_rating_prompt(chat_id):
    send_message(chat_id, "Оцени проект, пожалуйста 🙏", reply_markup=kb_rating())

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

    # ===== АДМИН-КОМАНДЫ (без проверки подписки) =====
    if user_id == ADMIN_ID:
        if text.startswith("/broadcast "):
            msg_text = text[11:].strip()
            if msg_text:
                sent, failed = broadcast_message(msg_text)
                send_message(chat_id, f"✅ Рассылка отправлена: {sent} доставлено, {failed} не доставлено")
            else:
                send_message(chat_id, "⚠️ Используйте: /broadcast [текст сообщения]")
            return

    # ===== ОБРАБОТКА ОЖИДАЕМОГО ВВОДА (добровольная отправка ключа) =====
    if user_state.get(user_id) == "waiting_key" and text and not text.startswith("/"):
        if KEY_PROTOCOL_RE.match(text.strip()):
            user_state[user_id] = None
            try:
                with open(SHARED_KEYS_FILE, 'a', encoding='utf-8') as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {user_str_from(user)}: {text.strip()}\n")
            except Exception as e:
                print(f"Ошибка записи shared_keys: {e}", flush=True)
            log_action(user, "🎁 ПРЕДЛОЖИЛ КЛЮЧ", text.strip())
            send_message(ADMIN_ID, f"🎁 <b>Новый ключ от пользователя</b>\n\n{user_str_from(user)}\n\n<code>{text.strip()}</code>")
            send_message(chat_id, TEXT_SHARE_KEY_THANKS, reply_markup=kb_back())
        else:
            send_message(chat_id, TEXT_SHARE_KEY_BAD_FORMAT, reply_markup=kb_share_key())
        return

    # ===== ПРОВЕРКА ОБЯЗАТЕЛЬНОЙ ПОДПИСКИ =====
    if user_id != ADMIN_ID and text in ("/start", "/sub", "/keys", "/proxy", "/status", "/support", "/help", "/info"):
        if not is_subscribed(user_id):
            send_message(chat_id, TEXT_NEED_SUBSCRIPTION, reply_markup=kb_subscribe_required())
            return

    if text == "/start":
        log_action(user, "🚀 ЗАПУСТИЛ БОТА")
        send_message(chat_id, text_welcome(name), reply_markup=kb_main(user_id))
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
    elif text == "/support":
        log_action(user, "🆘 ОТКРЫЛ ПОДДЕРЖКУ")
        send_message(chat_id, text_support(), reply_markup=kb_back())
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

    if data == "check_sub":
        if is_subscribed(user_id):
            log_action(user, "✅ ПОДТВЕРДИЛ ПОДПИСКУ")
            edit_message(chat_id, message_id, text_welcome(name), reply_markup=kb_main(user_id))
        else:
            answer_callback(cb["id"], "❌ Подписка не найдена. Подпишись на оба канала и попробуй снова.", show_alert=True)
        return

    # Проверка подписки для всех остальных действий (кроме админа)
    if user_id != ADMIN_ID and not is_subscribed(user_id):
        edit_message(chat_id, message_id, TEXT_NEED_SUBSCRIPTION, reply_markup=kb_subscribe_required())
        return

    if data == "back_main":
        user_state[user_id] = None
        log_action(user, "🏠 ВЕРНУЛСЯ В ГЛАВНОЕ МЕНЮ")
        edit_message(chat_id, message_id, text_welcome(name), reply_markup=kb_main(user_id))

    elif data == "menu_sub":
        log_action(user, "📁 ОТКРЫЛ МЕНЮ ПОДПИСОК")
        edit_message(chat_id, message_id, TEXT_SUB_MENU, reply_markup=kb_subscriptions())
    elif data == "sub_small":
        log_action(user, "📦 ВЫБРАЛ НЕБОЛЬШУЮ ПОДПИСКУ")
        increment_stat("sub_small")
        edit_message(chat_id, message_id, f"📦 <b>Небольшая подписка</b>\n\n<code>{SMALL_SUB_URL}</code>", reply_markup=kb_back())
        send_rating_prompt(chat_id)
    elif data == "sub_big":
        log_action(user, "🗂 ВЫБРАЛ БОЛЬШУЮ ПОДПИСКУ")
        increment_stat("sub_big")
        edit_message(chat_id, message_id, f"🗂 <b>Большая подписка</b>\n\n<code>{BIG_SUB_URL}</code>", reply_markup=kb_back())
        send_rating_prompt(chat_id)

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
        send_rating_prompt(chat_id)

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
        send_rating_prompt(chat_id)

    elif data == "share_key":
        log_action(user, "🎁 ОТКРЫЛ ФОРМУ ОТПРАВКИ КЛЮЧА")
        user_state[user_id] = "waiting_key"
        edit_message(chat_id, message_id, TEXT_SHARE_KEY_PROMPT, reply_markup=kb_share_key())

    elif data == "menu_support":
        log_action(user, "🆘 ОТКРЫЛ ПОДДЕРЖКУ")
        edit_message(chat_id, message_id, text_support(), reply_markup=kb_back())

    elif data == "menu_help":
        log_action(user, "ℹ️ ОТКРЫЛ СПРАВКУ")
        edit_message(chat_id, message_id, TEXT_HELP, reply_markup=kb_back())

    elif data.startswith("rate_"):
        score = int(data.split("_")[1])
        save_rating(user_id, score)
        log_action(user, f"⭐ ОЦЕНИЛ ПРОЕКТ: {score}")
        edit_message(chat_id, message_id, f"🙏 Спасибо за оценку: {'⭐' * score}", reply_markup=None)

    elif data == "admin_settings":
        if user_id != ADMIN_ID:
            return
        text = get_rating_text() + "\n\n" + get_stats_text()
        edit_message(chat_id, message_id, text, reply_markup=kb_admin_settings())

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
