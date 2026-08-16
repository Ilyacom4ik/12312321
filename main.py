#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import random
import socket
import subprocess
import threading
import time
import base64
import urllib.parse as urlparse
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ===== ПОДПИСКИ И КЛЮЧИ =====
SMALL_SUB_URL = "https://raw.githubusercontent.com/Ilyacom4ik/free-v2ray-2026/refs/heads/main/subscriptions/FreeCFGHub1.txt"
BIG_SUB_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"
KEYS_SOURCE_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"

SUPPORT_URL = "https://pay.cloudtips.ru/p/2486fa1a"
CHANNEL_URL = "https://t.me/FreeCFGHub"
CHANNEL_MIX_URL = "https://t.me/FreeCFGHubMIX"
LITE_KEYS_COUNT = 5
FULL_KEYS_COUNT = 7

# ===== ПЕРСИСТЕНТНОЕ ХРАНИЛИЩЕ =====
# Смонтируй volume на этот путь в docker-compose (например ./bot-data:/data),
# иначе после каждого пересобранного образа данные снова обнулятся.
DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

STATS_FILE = os.path.join(DATA_DIR, "stats.json")
SHARED_KEYS_FILE = os.path.join(DATA_DIR, "shared_keys.txt")
BOT_STATUS_FILE = os.path.join(DATA_DIR, "bot_status.json")
CHECKED_KEYS_FILE = os.path.join(DATA_DIR, "checked_keys.json")

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

KEY_PROTOCOL_RE = re.compile(r'^(vless|vmess|trojan|ss|tuic|hysteria2)://', re.IGNORECASE)

user_state = {}

# ===== ПРОВЕРКА КЛЮЧЕЙ (sing-box) =====
SING_BOX_BIN = os.environ.get("SINGBOX_BIN", "sing-box")
CHECK_TIMEOUT = 8          # секунд на один тест
CHECK_CONCURRENCY = 5      # сколько ключей тестировать параллельно
SINGBOX_STARTUP_DELAY = 1.5
PING_TEST_URL = "http://www.gstatic.com/generate_204"
SPEEDTEST_URL = "https://speed.cloudflare.com/__down?bytes=8000000"
SHOW_KEYS_LIMIT = 15
MAX_COUNTRY_BUTTONS = 12

# ⚠️ ОТРЕДАКТИРУЙ под свои реальные "белые" SNI-домены (маскировка под доверенные/
# незаблокированные домены). Это заглушка — я не берусь утверждать, какие домены
# сейчас в белом списке, сверяйся с актуальным реестром/своими проверенными SNI.
WHITE_SNI_DOMAINS = {
    "gosuslugi.ru",
    "sberbank.ru",
    "yandex.ru",
    "vk.com",
    "mos.ru",
}

def is_white_sni(sni):
    if not sni:
        return False
    sni = sni.lower().strip()
    return any(sni == d or sni.endswith("." + d) for d in WHITE_SNI_DOMAINS)

# ===== СОСТОЯНИЕ БОТА =====
def load_bot_status():
    try:
        with open(BOT_STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("enabled", True)
    except Exception:
        return True

def save_bot_status(enabled):
    try:
        with open(BOT_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"enabled": enabled}, f)
    except Exception:
        pass

BOT_ENABLED = load_bot_status()

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
    data.setdefault("users", [])
    data.setdefault("ratings", {"sum": 0, "count": 0, "users": {}})
    data.setdefault("checks_run", 0)
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
        f"🧪 Проверок ключей: {stats.get('checks_run', 0)}\n"
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

def broadcast_raw(text):
    """Рассылка готового HTML-сообщения без добавления префикса 📢."""
    users = get_all_users()
    sent = 0
    failed = 0
    for user_id in users:
        try:
            send_message(user_id, text)
            sent += 1
        except Exception as e:
            print(f"Не удалось отправить {user_id}: {e}", flush=True)
            failed += 1
    return sent, failed

def build_update_broadcast_text():
    keys_data, error = fetch_and_parse_keys()
    if error:
        return None
    lite_count = len(keys_data.get("lite", []))
    full_count = len(keys_data.get("full", []))
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    return (
        f"🔄 <b>Обновление подписки!</b>\n\n"
        f"🏳️ Lite ключей: {lite_count}\n"
        f"🏴 Full ключей: {full_count}\n\n"
        f"🕐 Время обновления: {now}\n\n"
        f"💳 Поддержать канал: {SUPPORT_URL}\n\n"
        f"@FreeCFGHubMIX\n"
        f"@FreeCFGHub"
    )

# ===== API =====
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
            return None
        return data["result"].get("status")
    except Exception:
        return None

def is_subscribed(user_id):
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
        {"command": "check", "description": "🧪 Проверка ключей"},
        {"command": "support", "description": "🆘 Поддержка"},
        {"command": "status", "description": "📡 Статус"},
        {"command": "help", "description": "ℹ️ Справка"},
        {"command": "broadcast", "description": "📢 Рассылка (админ)"},
    ]
    requests.post(f"{API}/setMyCommands", json={"commands": commands}, timeout=10)
    print("✅ Команды меню установлены", flush=True)

# ===== ТЕКСТЫ =====
def text_welcome(name):
    return (
        f"Привет, {name} 👋\n\n"
        "🆓 Здесь ты получишь качественные конфигурации для обхода блокировок от канала FreeCFGHub.\n\n"
        "📁 <b>Команды:</b>\n"
        "/sub — получить подписку\n"
        "/keys — получить ключи\n"
        "/check — проверка ключей\n"
        "/support — поддержка\n"
        "/status — статус подписки\n"
        "/help — справка\n\n"
        "💡 Все конфигурации обновляются вручную и проверяются на работоспособность.\n\n"
        f"📢 {CHANNEL_URL}"
    )

TEXT_SUB_MENU = (
    "🔶 <b>Выберите тип подписки</b>\n\n"
    "📦 <b>Небольшая подписка</b>\n"
    "✅ Подходит для всех известных клиентов и устройств\n"
    "✅ Оптимальна для повседневного использования\n\n"
    "🗂 <b>Большая подписка</b>\n"
    "⚠️ Не подходит для слабых устройств\n"
    "⚠️ Не подходит для клиентов: v2rayTun, HAPP, Incy\n"
    "✅ Рекомендуемые клиенты: Hiddify, v2rayNG, NekoBox и др.\n"
    "✅ Для продвинутых пользователей\n\n"
    "💡 <i>Выберите подходящий вариант:</i>"
)

TEXT_KEYS_MENU = (
    "🔷 <b>Выберите тип ключей</b>\n\n"
    "🏳️ <b>Lite</b> — 5 ключей\n"
    "📱 Только для мобильного интернета\n"
    "✅ Используются при ограничении мобильного трафика\n"
    "✅ Экономичный режим\n\n"
    "🏴 <b>Full</b> — 7 ключей\n"
    "🌍 Как обычный зарубежный трафик\n"
    "✅ Максимальная скорость и стабильность\n"
    "✅ Для любых задач\n\n"
    "💡 <i>Выберите подходящий вариант:</i>"
)

TEXT_CHECK_MENU = (
    "🧪 <b>Проверка ключей</b>\n\n"
    "Бот прогонит все актуальные ключи через sing-box, проверит доступность и разложит рабочие по категориям:\n\n"
    "🏳️ <b>Белый SNI</b> — маскировка под доверенные/незаблокированные домены\n"
    "🏴 <b>Обычный SNI</b> — стандартный/иностранный SNI\n"
    "🌍 <b>По странам</b> — фильтр по стране среди рабочих ключей\n\n"
    "📶 <b>Пинг</b> — только задержка отклика\n"
    "🚀 <b>Скорость</b> — только замер скорости\n"
    "🧪 <b>Всё вместе</b> — пинг + скорость + страна\n\n"
    "⚠️ Нерабочие ключи не сохраняются.\n"
    "⏱ Проверка может занять несколько минут."
)

TEXT_HELP = (
    "📜 <b>Справка</b>\n\n"
    "/sub — получить подписку\n"
    "/keys — получить ключи\n"
    "/check — проверка ключей (пинг/скорость, белые/черные)\n"
    "/support — поддержка\n"
    "/status — статус подписки\n"
    "/help — эта справка\n\n"
    f"📢 {CHANNEL_URL}"
)

TEXT_SUPPORT = (
    "🆘 <b>Поддержка</b>\n\n"
    f"По всем вопросам пиши: {SUPPORT_USERNAME}\n"
    f"Либо на почту: {SUPPORT_EMAIL}\n\n"
    "📜 <b>Документы:</b>\n"
    f"• <a href='{PRIVACY_URL}'>Политика конфиденциальности</a>\n"
    f"• <a href='{TERMS_URL}'>Пользовательское соглашение</a>"
)

TEXT_NEED_SUBSCRIPTION = (
    "🔒 <b>Доступ ограничен</b>\n\n"
    "Чтобы пользоваться ботом, подпишись на наши каналы:\n\n"
    f"📢 {CHANNEL_URL}\n"
    f"📢 {CHANNEL_MIX_URL}\n\n"
    "После подписки нажми «✅ Я подписался»."
)

TEXT_STATUS_LOADING = "⏳ Проверяю..."

TEXT_BOT_OFF = (
    "⛔ <b>Бот на техническом перерыве</b>\n\n"
    "Ведутся технические работы. Бот временно недоступен.\n"
    "Пожалуйста, зайдите позже.\n\n"
    "⏱ Ориентировочное время: до 1 часа\n\n"
    f"📢 {CHANNEL_URL}"
)

def get_status_text():
    keys_data, error = fetch_and_parse_keys()
    if error:
        return f"❌ Ошибка: {error}"
    stats = load_stats()
    ratings = stats.get("ratings", {})
    avg = (ratings.get("sum", 0) / ratings.get("count", 1)) if ratings.get("count", 0) else 0
    return (
        f"📊 <b>Статус подписки</b>\n\n"
        f"🏳️ Lite ключей: {len(keys_data.get('lite', []))}\n"
        f"🏴 Full ключей: {len(keys_data.get('full', []))}\n"
        f"⭐ Рейтинг: {avg:.1f} / 5.0\n"
        f"👥 Пользователей: {len(stats.get('users', []))}\n\n"
        f"📢 {CHANNEL_URL}"
    )

# ===== ЗАГРУЗКА =====
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

# ============================================================
# ===== ПРОВЕРКА КЛЮЧЕЙ ЧЕРЕЗ SING-BOX =====
# ============================================================

def _split_remark(link):
    if '#' in link:
        base, frag = link.split('#', 1)
        return base, urlparse.unquote(frag)
    return link, ""

def _parse_vless(link):
    base, remark = _split_remark(link)
    u = urlparse.urlparse(base)
    qs = dict(urlparse.parse_qsl(u.query))
    host, port = u.hostname, u.port
    outbound = {
        "type": "vless",
        "tag": "proxy",
        "server": host,
        "server_port": port,
        "uuid": u.username,
        "flow": qs.get("flow", ""),
    }
    security = qs.get("security", "")
    if security in ("tls", "reality"):
        tls = {
            "enabled": True,
            "server_name": qs.get("sni") or qs.get("host") or host,
            "insecure": qs.get("allowInsecure") == "1",
        }
        if security == "reality":
            tls["reality"] = {"enabled": True, "public_key": qs.get("pbk", ""), "short_id": qs.get("sid", "")}
        if qs.get("fp"):
            tls["utls"] = {"enabled": True, "fingerprint": qs.get("fp")}
        outbound["tls"] = tls
    net = qs.get("type", "tcp")
    if net == "ws":
        outbound["transport"] = {"type": "ws", "path": qs.get("path", "/"), "headers": {"Host": qs.get("host", host)}}
    elif net == "grpc":
        outbound["transport"] = {"type": "grpc", "service_name": qs.get("serviceName", "")}
    return host, port, remark, outbound

def _parse_vmess(link):
    b64 = link[len("vmess://"):].split('#')[0]
    padded = b64 + '=' * (-len(b64) % 4)
    data = json.loads(base64.b64decode(padded).decode('utf-8', errors='ignore'))
    host = data.get("add")
    port = int(data.get("port", 443))
    remark = data.get("ps", "")
    outbound = {
        "type": "vmess",
        "tag": "proxy",
        "server": host,
        "server_port": port,
        "uuid": data.get("id"),
        "security": data.get("scy", "auto"),
        "alter_id": int(data.get("aid", 0) or 0),
    }
    if str(data.get("tls", "")).lower() == "tls":
        outbound["tls"] = {"enabled": True, "server_name": data.get("sni") or data.get("host") or host, "insecure": False}
    net = data.get("net", "tcp")
    if net == "ws":
        outbound["transport"] = {"type": "ws", "path": data.get("path", "/"), "headers": {"Host": data.get("host", host)}}
    elif net == "grpc":
        outbound["transport"] = {"type": "grpc", "service_name": data.get("path", "")}
    return host, port, remark, outbound

def _parse_trojan(link):
    base, remark = _split_remark(link)
    u = urlparse.urlparse(base)
    qs = dict(urlparse.parse_qsl(u.query))
    host, port = u.hostname, u.port
    outbound = {
        "type": "trojan",
        "tag": "proxy",
        "server": host,
        "server_port": port,
        "password": u.username,
        "tls": {"enabled": True, "server_name": qs.get("sni") or host, "insecure": qs.get("allowInsecure") == "1"},
    }
    net = qs.get("type", "tcp")
    if net == "ws":
        outbound["transport"] = {"type": "ws", "path": qs.get("path", "/"), "headers": {"Host": qs.get("host", host)}}
    elif net == "grpc":
        outbound["transport"] = {"type": "grpc", "service_name": qs.get("serviceName", "")}
    return host, port, remark, outbound

def _parse_ss(link):
    base, remark = _split_remark(link)
    rest = base[len("ss://"):]
    if '@' in rest:
        userinfo, hostport = rest.rsplit('@', 1)
        try:
            padded = userinfo + '=' * (-len(userinfo) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
            method, password = decoded.split(':', 1)
        except Exception:
            method, password = userinfo.split(':', 1)
        host_part = hostport.split('?')[0]
        host, port = (host_part.rsplit(':', 1) if ':' in host_part else (host_part, "8388"))
    else:
        padded = rest + '=' * (-len(rest) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
        creds, hostport = decoded.rsplit('@', 1)
        method, password = creds.split(':', 1)
        host, port = hostport.rsplit(':', 1)
    outbound = {
        "type": "shadowsocks",
        "tag": "proxy",
        "server": host,
        "server_port": int(port),
        "method": method,
        "password": password,
    }
    return host, int(port), remark, outbound

def _parse_tuic(link):
    base, remark = _split_remark(link)
    u = urlparse.urlparse(base)
    qs = dict(urlparse.parse_qsl(u.query))
    host, port = u.hostname, u.port
    outbound = {
        "type": "tuic",
        "tag": "proxy",
        "server": host,
        "server_port": port,
        "uuid": u.username or "",
        "password": u.password or "",
        "congestion_control": qs.get("congestion_control", "bbr"),
        "tls": {
            "enabled": True,
            "server_name": qs.get("sni") or host,
            "insecure": qs.get("allow_insecure") == "1",
            "alpn": [qs.get("alpn", "h3")],
        },
    }
    return host, port, remark, outbound

def _parse_hysteria2(link):
    base, remark = _split_remark(link)
    u = urlparse.urlparse(base)
    qs = dict(urlparse.parse_qsl(u.query))
    host, port = u.hostname, u.port
    outbound = {
        "type": "hysteria2",
        "tag": "proxy",
        "server": host,
        "server_port": port,
        "password": u.username or "",
        "tls": {"enabled": True, "server_name": qs.get("sni") or host, "insecure": qs.get("insecure") == "1"},
    }
    return host, port, remark, outbound

def parse_key_link(link):
    try:
        proto = link.split("://")[0].lower()
        if proto == "vless":
            res = _parse_vless(link)
        elif proto == "vmess":
            res = _parse_vmess(link)
        elif proto == "trojan":
            res = _parse_trojan(link)
        elif proto == "ss":
            res = _parse_ss(link)
        elif proto == "tuic":
            res = _parse_tuic(link)
        elif proto in ("hysteria2", "hy2"):
            res = _parse_hysteria2(link)
        else:
            return None
        host, port, remark, outbound = res
        if not host or not port:
            return None
        sni = (outbound.get("tls") or {}).get("server_name")
        return {"protocol": proto, "host": host, "port": port, "remark": remark, "outbound": outbound, "sni": sni}
    except Exception:
        return None

def _get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def _country_flag(code):
    if not code or len(code) != 2:
        return ""
    code = code.upper()
    return chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))

def _get_country_code(host):
    try:
        ip = socket.gethostbyname(host)
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=5)
        return r.json().get("countryCode", "")
    except Exception:
        return ""

def _build_singbox_config(outbound, local_port):
    return {
        "log": {"level": "error"},
        "inbounds": [{"type": "socks", "tag": "in", "listen": "127.0.0.1", "listen_port": local_port}],
        "outbounds": [outbound, {"type": "direct", "tag": "direct"}],
        "route": {"final": "proxy"},
    }

def test_key(link, mode="all"):
    """mode: ping | speed | all. Возвращает dict с результатом теста одного ключа."""
    parsed = parse_key_link(link)
    result = {"ok": False, "ping_ms": None, "speed_mbps": None, "country": "", "remark": "", "sni": None}
    if not parsed:
        result["error"] = "unsupported_protocol"
        return result
    result["remark"] = parsed["remark"]
    result["sni"] = parsed.get("sni")

    local_port = _get_free_port()
    config_path = os.path.join("/tmp", f"sb_{local_port}.json")
    config = _build_singbox_config(parsed["outbound"], local_port)
    proc = None
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f)

        proc = subprocess.Popen(
            [SING_BOX_BIN, "run", "-c", config_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(SINGBOX_STARTUP_DELAY)

        proxies = {
            "http": f"socks5h://127.0.0.1:{local_port}",
            "https": f"socks5h://127.0.0.1:{local_port}",
        }

        if mode in ("ping", "all"):
            t0 = time.time()
            r = requests.get(PING_TEST_URL, proxies=proxies, timeout=CHECK_TIMEOUT)
            if r.status_code in (200, 204):
                result["ping_ms"] = round((time.time() - t0) * 1000)
                result["ok"] = True

        if mode in ("speed", "all"):
            t0 = time.time()
            total = 0
            r = requests.get(SPEEDTEST_URL, proxies=proxies, timeout=CHECK_TIMEOUT, stream=True)
            for chunk in r.iter_content(chunk_size=65536):
                total += len(chunk)
                if time.time() - t0 > CHECK_TIMEOUT:
                    break
            elapsed = time.time() - t0
            if total > 0 and elapsed > 0:
                result["speed_mbps"] = round((total * 8 / elapsed) / 1_000_000, 1)
                result["ok"] = True

        if result["ok"]:
            result["country"] = _get_country_code(parsed["host"])

    except Exception as e:
        result["error"] = str(e)
        result["ok"] = False
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        try:
            os.remove(config_path)
        except Exception:
            pass
    return result

def build_tested_link(original_link, result):
    base = original_link.split('#')[0]
    parts = []
    if result.get("ping_ms") is not None:
        parts.append(f"⚡{result['ping_ms']}ms")
    if result.get("speed_mbps") is not None:
        parts.append(f"🚀{result['speed_mbps']}Mbps")
    flag = _country_flag(result.get("country", ""))
    if flag:
        parts.append(flag)
    orig = result.get("remark") or ""
    new_remark = " ".join(parts) + (f" {orig}" if orig else "")
    if not new_remark.strip():
        return original_link
    return f"{base}#{urlparse.quote(new_remark.strip())}"

def save_checked_keys(white, black, countries, mode, dead_count):
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "white": white,
        "black": black,
        "countries": countries,
        "dead_count": dead_count,
    }
    try:
        with open(CHECKED_KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_checked_keys():
    try:
        with open(CHECKED_KEYS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def run_key_check(chat_id, message_id, mode):
    keys_data, error = fetch_and_parse_keys()
    if error:
        edit_message(chat_id, message_id, f"❌ {error}", reply_markup=kb_back())
        return
    all_keys = list(dict.fromkeys(keys_data.get("lite", []) + keys_data.get("full", [])))
    total = len(all_keys)
    if total == 0:
        edit_message(chat_id, message_id, "😔 Ключи не найдены", reply_markup=kb_back())
        return

    edit_message(chat_id, message_id, f"⏳ Проверяю {total} ключей...\n🔧 Режим: {mode}\nЭто может занять пару минут.")

    white, black = [], []
    countries = {}
    dead_count = 0

    def worker(link):
        return link, test_key(link, mode=mode)

    with ThreadPoolExecutor(max_workers=CHECK_CONCURRENCY) as ex:
        futures = [ex.submit(worker, k) for k in all_keys]
        for fut in as_completed(futures):
            link, res = fut.result()
            if not res.get("ok"):
                # нерабочие ключи не сохраняем
                dead_count += 1
                continue
            tested_link = build_tested_link(link, res)
            if is_white_sni(res.get("sni")):
                white.append(tested_link)
            else:
                black.append(tested_link)
            code = (res.get("country") or "").upper() or "??"
            countries.setdefault(code, []).append(tested_link)

    increment_stat("checks_run")
    save_checked_keys(white, black, countries, mode, dead_count)

    text = (
        f"✅ <b>Проверка завершена</b>\n\n"
        f"🔧 Режим: {mode}\n"
        f"🏳️ Белый SNI: {len(white)}\n"
        f"🏴 Обычный SNI: {len(black)}\n"
        f"❌ Не рабочих (не сохранены): {dead_count}\n\n"
        f"🌍 Стран найдено: {len(countries)}"
    )
    edit_message(chat_id, message_id, text, reply_markup=kb_check_result(len(white), len(black)))

# ===== КЛАВИАТУРЫ =====
def kb_main(user_id=None):
    rows = [
        [{"text": "📁 Получить подписку", "callback_data": "menu_sub"}],
        [{"text": "🔑 Получить ключи", "callback_data": "menu_keys"}],
        [{"text": "🧪 Проверка ключей", "callback_data": "menu_check"}],
        [{"text": "🎁 Поделиться ключом", "callback_data": "share_key"}],
        [{"text": "⭐ Оценить проект", "callback_data": "rate_project"}],
        [{"text": "💳 Поддержать канал", "url": SUPPORT_URL}],
        [{"text": "🆘 Поддержка", "callback_data": "menu_support"}, {"text": "ℹ️ Справка", "callback_data": "menu_help"}],
        [{"text": "🔒 Конфиденциальность", "url": PRIVACY_URL}, {"text": "📄 Соглашение", "url": TERMS_URL}],
    ]
    if user_id == ADMIN_ID:
        status_text = "🔴 Выключить" if BOT_ENABLED else "🟢 Включить"
        rows.append([
            {"text": "⚙️ Настройки (админ)", "callback_data": "admin_settings"},
            {"text": status_text, "callback_data": "admin_toggle"}
        ])
        rows.append([{"text": "📢 Разослать обновление подписки", "callback_data": "admin_broadcast_update"}])
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
            [{"text": "🏳️ Lite", "callback_data": "keys_lite"}, {"text": "🏴 Full", "callback_data": "keys_full"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def kb_check_menu():
    return {
        "inline_keyboard": [
            [{"text": "📶 Проверить пинг", "callback_data": "check_ping"}],
            [{"text": "🚀 Проверить скорость", "callback_data": "check_speed"}],
            [{"text": "🧪 Проверить всё", "callback_data": "check_all"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def kb_check_result(white_count, black_count):
    return {
        "inline_keyboard": [
            [
                {"text": f"🏳️ Белый SNI ({white_count})", "callback_data": "show_white"},
                {"text": f"🏴 Обычный SNI ({black_count})", "callback_data": "show_black"},
            ],
            [{"text": "🌍 По странам", "callback_data": "show_countries"}],
            [{"text": "🔁 Проверить снова", "callback_data": "menu_check"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def kb_countries(countries):
    rows = []
    ordered = sorted(countries.items(), key=lambda x: -len(x[1]))[:MAX_COUNTRY_BUTTONS]
    for code, keys in ordered:
        flag = _country_flag(code) or "🌐"
        rows.append([{"text": f"{flag} {code} ({len(keys)})", "callback_data": f"country_{code}"}])
    rows.append([{"text": "◀️ Назад", "callback_data": "menu_check"}])
    return {"inline_keyboard": rows}

def kb_back():
    return {"inline_keyboard": [[{"text": "🏠 В главное меню", "callback_data": "back_main"}]]}

def kb_share_key():
    return {"inline_keyboard": [[{"text": "◀️ Назад", "callback_data": "back_main"}]]}

def kb_rating():
    return {
        "inline_keyboard": [
            [{"text": "⭐", "callback_data": "rate_1"}, {"text": "⭐⭐", "callback_data": "rate_2"}],
            [{"text": "⭐⭐⭐", "callback_data": "rate_3"}, {"text": "⭐⭐⭐⭐", "callback_data": "rate_4"}],
            [{"text": "⭐⭐⭐⭐⭐", "callback_data": "rate_5"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def kb_admin_settings():
    return {
        "inline_keyboard": [
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

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

    # ===== АДМИН (всегда работает, даже при выключенном боте) =====
    if user_id == ADMIN_ID:
        if text.startswith("/broadcast "):
            msg_text = text[11:].strip()
            if msg_text:
                sent, failed = broadcast_message(msg_text)
                send_message(chat_id, f"✅ Рассылка: {sent} доставлено, {failed} не доставлено")
            else:
                send_message(chat_id, "⚠️ Используйте: /broadcast [текст]")
            return

    # ===== ПРОВЕРКА СОСТОЯНИЯ БОТА =====
    global BOT_ENABLED
    if not BOT_ENABLED and user_id != ADMIN_ID:
        send_message(chat_id, TEXT_BOT_OFF)
        return

    # ===== ОЖИДАНИЕ КЛЮЧА =====
    if user_state.get(user_id) == "waiting_key" and text and not text.startswith("/"):
        if KEY_PROTOCOL_RE.match(text.strip()):
            user_state[user_id] = None
            with open(SHARED_KEYS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {user_str_from(user)}: {text.strip()}\n")
            log_action(user, "🎁 ПРЕДЛОЖИЛ КЛЮЧ", text.strip())
            send_message(ADMIN_ID, f"🎁 <b>Новый ключ</b>\n\n{user_str_from(user)}\n\n<code>{text.strip()}</code>")
            send_message(chat_id, "🙏 Спасибо! Ключ отправлен на проверку админу.", reply_markup=kb_back())
        else:
            send_message(chat_id, "⚠️ Не похоже на ключ. Пришли vless://, vmess://, trojan://, ss://, tuic:// или hysteria2://", reply_markup=kb_share_key())
        return

    # ===== ПРОВЕРКА ПОДПИСКИ =====
    if user_id != ADMIN_ID and text in ("/start", "/sub", "/keys", "/check", "/support", "/status", "/help"):
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
    elif text == "/check":
        log_action(user, "🧪 ОТКРЫЛ ПРОВЕРКУ КЛЮЧЕЙ")
        send_message(chat_id, TEXT_CHECK_MENU, reply_markup=kb_check_menu())
    elif text == "/support":
        log_action(user, "🆘 ОТКРЫЛ ПОДДЕРЖКУ")
        send_message(chat_id, TEXT_SUPPORT, reply_markup=kb_back())
    elif text == "/status":
        log_action(user, "📡 ЗАПРОСИЛ СТАТУС")
        send_message(chat_id, TEXT_STATUS_LOADING)
        send_message(chat_id, get_status_text())
    elif text in ("/help", "/info"):
        log_action(user, "ℹ️ ОТКРЫЛ СПРАВКУ")
        send_message(chat_id, TEXT_HELP, reply_markup=kb_back())

def handle_callback(cb):
    global BOT_ENABLED
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    data = cb.get("data", "")
    user = cb.get("from", {})
    user_id = user.get("id")
    name = user.get("first_name") or "друг"

    answer_callback(cb["id"])

    # ===== АДМИН: ВКЛЮЧЕНИЕ/ВЫКЛЮЧЕНИЕ БОТА =====
    if data == "admin_toggle" and user_id == ADMIN_ID:
        BOT_ENABLED = not BOT_ENABLED
        save_bot_status(BOT_ENABLED)
        status_text = "🔴 ВЫКЛЮЧЕН" if not BOT_ENABLED else "🟢 ВКЛЮЧЕН"
        log_action(user, f"⚙️ ИЗМЕНИЛ СТАТУС БОТА: {status_text}")
        edit_message(chat_id, message_id, text_welcome(name), reply_markup=kb_main(user_id))
        send_message(chat_id, f"⚙️ <b>Статус бота изменён</b>\n\nБот {status_text}")
        if not BOT_ENABLED:
            broadcast_message("⛔ <b>Технический перерыв</b>\n\nБот временно недоступен. Ведутся технические работы. Приносим извинения за неудобства.")
        else:
            broadcast_message("🟢 <b>Бот снова в сети!</b>\n\nВсе технические работы завершены. Бот доступен для использования.")
        return

    if data == "check_sub":
        if is_subscribed(user_id):
            log_action(user, "✅ ПОДТВЕРДИЛ ПОДПИСКУ")
            edit_message(chat_id, message_id, text_welcome(name), reply_markup=kb_main(user_id))
        else:
            answer_callback(cb["id"], "❌ Подписка не найдена.", show_alert=True)
        return

    # ===== БОТ ВЫКЛЮЧЕН =====
    if not BOT_ENABLED and user_id != ADMIN_ID:
        edit_message(chat_id, message_id, TEXT_BOT_OFF)
        return

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
        edit_message(chat_id, message_id, f"📦 <b>Небольшая подписка</b>\n\n<code>{SMALL_SUB_URL}</code>\n\n✅ Подходит для всех клиентов и устройств.", reply_markup=kb_back())
    elif data == "sub_big":
        log_action(user, "🗂 ВЫБРАЛ БОЛЬШУЮ ПОДПИСКУ")
        increment_stat("sub_big")
        edit_message(chat_id, message_id, f"🗂 <b>Большая подписка</b>\n\n<code>{BIG_SUB_URL}</code>\n\n⚠️ Не подходит для v2rayTun, HAPP, Incy\n✅ Рекомендуемые клиенты: Hiddify, v2rayNG, NekoBox", reply_markup=kb_back())

    elif data == "menu_keys":
        log_action(user, "🔑 ОТКРЫЛ МЕНЮ КЛЮЧЕЙ")
        edit_message(chat_id, message_id, TEXT_KEYS_MENU, reply_markup=kb_keys())
    elif data in ("keys_lite", "keys_full"):
        key_type = "lite" if data == "keys_lite" else "full"
        count = LITE_KEYS_COUNT if key_type == "lite" else FULL_KEYS_COUNT
        label = "Lite" if key_type == "lite" else "Full"
        desc = "📱 Только для мобильного интернета. Используются при ограничении мобильного трафика." if key_type == "lite" else "🌍 Как обычный зарубежный трафик. Максимальная скорость."
        log_action(user, f"🔑 ЗАПРОСИЛ КЛЮЧИ {label}")
        increment_stat("lite_requests" if key_type == "lite" else "full_requests")
        edit_message(chat_id, message_id, "⏳ Загружаю...")
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
        edit_message(chat_id, message_id, f"🔑 <b>{label} — {len(selected)} шт.</b>\n\n{desc}\n\n{keys_block}\n\n📢 {CHANNEL_URL}", reply_markup=kb_back())

    elif data == "menu_check":
        log_action(user, "🧪 ОТКРЫЛ ПРОВЕРКУ КЛЮЧЕЙ")
        edit_message(chat_id, message_id, TEXT_CHECK_MENU, reply_markup=kb_check_menu())
    elif data in ("check_ping", "check_speed", "check_all"):
        mode = {"check_ping": "ping", "check_speed": "speed", "check_all": "all"}[data]
        log_action(user, f"🧪 ЗАПУСТИЛ ПРОВЕРКУ КЛЮЧЕЙ: {mode}")
        threading.Thread(target=run_key_check, args=(chat_id, message_id, mode), daemon=True).start()
    elif data in ("show_white", "show_black"):
        checked = load_checked_keys()
        if not checked:
            edit_message(chat_id, message_id, "😔 Нет данных проверки. Сначала запусти проверку ключей.", reply_markup=kb_back())
            return
        keys_list = checked["white"] if data == "show_white" else checked["black"]
        label = "🏳️ Ключи с белым SNI" if data == "show_white" else "🏴 Ключи с обычным SNI"
        if not keys_list:
            edit_message(chat_id, message_id, f"{label}\n\nСписок пуст.", reply_markup=kb_back())
            return
        shown = keys_list[:SHOW_KEYS_LIMIT]
        block = "\n\n".join(f"<code>{k}</code>" for k in shown)
        more = f"\n\n…и ещё {len(keys_list) - SHOW_KEYS_LIMIT}" if len(keys_list) > SHOW_KEYS_LIMIT else ""
        edit_message(chat_id, message_id, f"{label} ({len(keys_list)} шт.)\n\n{block}{more}", reply_markup=kb_back())

    elif data == "show_countries":
        checked = load_checked_keys()
        countries = (checked or {}).get("countries") or {}
        if not countries:
            edit_message(chat_id, message_id, "😔 Нет данных проверки. Сначала запусти проверку ключей.", reply_markup=kb_back())
            return
        edit_message(chat_id, message_id, "🌍 <b>Выбери страну</b>\n\nПоказаны только страны рабочих ключей:", reply_markup=kb_countries(countries))

    elif data.startswith("country_"):
        code = data[len("country_"):]
        checked = load_checked_keys()
        countries = (checked or {}).get("countries") or {}
        keys_list = countries.get(code, [])
        flag = _country_flag(code) or "🌐"
        label = f"{flag} Ключи — {code}"
        if not keys_list:
            edit_message(chat_id, message_id, f"{label}\n\nСписок пуст.", reply_markup=kb_back())
            return
        shown = keys_list[:SHOW_KEYS_LIMIT]
        block = "\n\n".join(f"<code>{k}</code>" for k in shown)
        more = f"\n\n…и ещё {len(keys_list) - SHOW_KEYS_LIMIT}" if len(keys_list) > SHOW_KEYS_LIMIT else ""
        edit_message(chat_id, message_id, f"{label} ({len(keys_list)} шт.)\n\n{block}{more}", reply_markup=kb_back())

    elif data == "share_key":
        log_action(user, "🎁 ОТКРЫЛ ФОРМУ ОТПРАВКИ КЛЮЧА")
        user_state[user_id] = "waiting_key"
        edit_message(chat_id, message_id, "🎁 <b>Поделиться ключом</b>\n\nПришли ключ одним сообщением. Поддерживаются протоколы:\n<code>vless://</code>, <code>vmess://</code>, <code>trojan://</code>, <code>ss://</code>, <code>tuic://</code>, <code>hysteria2://</code>", reply_markup=kb_share_key())

    elif data == "menu_support":
        log_action(user, "🆘 ОТКРЫЛ ПОДДЕРЖКУ")
        edit_message(chat_id, message_id, TEXT_SUPPORT, reply_markup=kb_back())

    elif data == "menu_help":
        log_action(user, "ℹ️ ОТКРЫЛ СПРАВКУ")
        edit_message(chat_id, message_id, TEXT_HELP, reply_markup=kb_back())

    elif data == "rate_project":
        log_action(user, "⭐ ОТКРЫЛ ОЦЕНКУ")
        edit_message(chat_id, message_id, "⭐ <b>Оцените наш проект</b>\n\nНасколько вам нравится бот? Выберите оценку от 1 до 5:", reply_markup=kb_rating())

    elif data.startswith("rate_"):
        score = int(data.split("_")[1])
        save_rating(user_id, score)
        log_action(user, f"⭐ ПОСТАВИЛ ОЦЕНКУ: {score}")
        edit_message(chat_id, message_id, f"🙏 <b>Спасибо за оценку!</b>\n\n{'⭐' * score} {score}/5\n\nВаше мнение очень важно для нас! ❤️", reply_markup=kb_back())

    elif data == "admin_settings" and user_id == ADMIN_ID:
        text = get_rating_text() + "\n\n" + get_stats_text()
        edit_message(chat_id, message_id, text, reply_markup=kb_admin_settings())

    elif data == "admin_broadcast_update" and user_id == ADMIN_ID:
        edit_message(chat_id, message_id, "⏳ Собираю данные и рассылаю...")
        text = build_update_broadcast_text()
        if not text:
            edit_message(chat_id, message_id, "❌ Не удалось получить данные по ключам", reply_markup=kb_back())
            return
        sent, failed = broadcast_raw(text)
        log_action(user, f"📢 РАЗОСЛАЛ ОБНОВЛЕНИЕ ПОДПИСКИ: {sent} доставлено, {failed} не доставлено")
        edit_message(chat_id, message_id, f"✅ <b>Рассылка отправлена</b>\n\nДоставлено: {sent}\nНе доставлено: {failed}", reply_markup=kb_back())

# ===== MAIN =====
def main():
    print("🤖 Бот FreeCFGHub запущен", flush=True)
    print(f"📊 Статус бота: {'ВКЛЮЧЕН' if BOT_ENABLED else 'ВЫКЛЮЧЕН'}", flush=True)
    print(f"💾 Каталог данных: {DATA_DIR}", flush=True)
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
