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
LTE_KEYS_COUNT = 5
FULL_KEYS_COUNT = 7

STATS_FILE = "stats.json"

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
        return {"lte_requests": 0, "full_requests": 0, "sub_small": 0, "sub_big": 0, "proxy_ru": 0, "proxy_eu": 0, "proxy_all": 0}

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

# ===== ФУНКЦИИ =====

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
        {"command": "status", "description": "📡 Статус"},
        {"command": "help", "description": "ℹ️ Справка"},
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
        "/status — статус подписки\n\n"
        f"📢 {CHANNEL_URL}"
    )

TEXT_SUB_MENU = "🔶 <b>Выберите тип подписки</b>"
TEXT_KEYS_MENU = "🔷 <b>Выберите тип ключа</b>"
TEXT_HELP = "📜 <b>Справка</b>\n\n/sub — подписка\n/keys — ключи\n/proxy — прокси\n/status — статус"
TEXT_STATUS_LOADING = "⏳ Проверяю..."

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
        lte_keys = []
        full_keys = []
        for line in r.text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if not re.match(r'^(vless|vmess|trojan|ss|tuic|hysteria2)://', line):
                continue
            if re.search(r'\bLTE\b', line, re.IGNORECASE):
                lte_keys.append(line)
            else:
                full_keys.append(line)
        return {"lte": lte_keys, "full": full_keys}, None
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
        f"🏳️ LTE ключей: {len(keys_data.get('lte', []))}\n"
        f"🏴 Full ключей: {len(keys_data.get('full', []))}\n\n"
        f"📢 {CHANNEL_URL}"
    )

# ===== КЛАВИАТУРЫ =====

def kb_main():
    return {
        "inline_keyboard": [
            [{"text": "📁 Получить подписку", "callback_data": "menu_sub"}],
            [{"text": "🔑 Получить ключи", "callback_data": "menu_keys"}],
            [{"text": "🌍 Прокси для Telegram", "callback_data": "menu_proxy"}],
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
            [{"text": "LTE", "callback_data": "keys_lte"}, {"text": "Full", "callback_data": "keys_full"}],
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

# ===== ОБРАБОТКА =====

def handle_message(msg):
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    user = msg.get("from", {})
    name = user.get("first_name") or "друг"

    if not chat_id:
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
    elif text in ("/help", "/info"):
        log_action(user, "ℹ️ ОТКРЫЛ СПРАВКУ")
        send_message(chat_id, TEXT_HELP, reply_markup=kb_back())

def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    data = cb.get("data", "")
    user = cb.get("from", {})
    name = user.get("first_name") or "друг"

    answer_callback(cb["id"])

    if data == "back_main":
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
    elif data in ("keys_lte", "keys_full"):
        key_type = "lte" if data == "keys_lte" else "full"
        count = LTE_KEYS_COUNT if key_type == "lte" else FULL_KEYS_COUNT
        label = "LTE" if key_type == "lte" else "Full"
        log_action(user, f"🔑 ЗАПРОСИЛ КЛЮЧИ {label}")
        increment_stat("lte_requests" if key_type == "lte" else "full_requests")
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

    elif data == "menu_help":
        log_action(user, "ℹ️ ОТКРЫЛ СПРАВКУ")
        edit_message(chat_id, message_id, TEXT_HELP, reply_markup=kb_back())

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
