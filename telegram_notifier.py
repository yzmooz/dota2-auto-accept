"""
Telegram notification sender for Dota 2 Auto Accept.
Uses a single shared bot — users only need their Chat ID.
Messages are randomly assembled from word parts for maximum variety.
"""

import json
import re
import random
import urllib.request
import urllib.error
import threading

# ── Shared bot (all users use this one) ──────────────────────────────────────
BOT_TOKEN = "8589196299:AAHJYvGKtHfCfGOCgFlWCt0aTSNR8o3JFtI"

API = "https://api.telegram.org/bot{token}/{method}"

# ══════════════════════════════════════════════════════════════════════════════
#  RANDOM MESSAGE PARTS
# ══════════════════════════════════════════════════════════════════════════════

# ── Titles (how to address the user) ─────────────────────────────────────────
_TITLES = [
    "Мой несравненный повелитель", "Мой драгоценный господин",
    "Великий владыка", "О мой хозяин", "Могущественный владыка",
    "Величайший воин всех времён", "Мой несравненный командир",
    "Божественный повелитель", "Светлейший князь", "Мой дорогой лорд",
    "О всемогущий", "Мой обожаемый господин и повелитель",
    "Величайший из смертных", "Мой блистательный генерал",
    "Владыка всех земель Dota", "Мой несравненный чемпион",
    "Божественный и прекрасный", "Мой величественный король",
    "О великий и мудрый", "Мой любимый император",
    "Мой дорогой и уважаемый господин",
    "О несравненный мастер Dota",
    "Мой драгоценный и всемогущий повелитель",
    "Великолепнейший из воинов",
    "Мой обожаемый и непобедимый господин",
]

_SHORT_TITLES = [
    "повелитель", "господин", "владыка", "хозяин", "командир",
    "князь", "лорд", "воин", "чемпион", "генерал", "король",
    "император", "герой", "мастер", "легенда",
]

# ── Match found parts ────────────────────────────────────────────────────────
_FOUND_OPENERS = [
    "ваша игра найдена", "матч обнаружен",
    "игра ждёт своего героя", "противник найден и трепещет",
    "арена зовёт своего чемпиона", "битва начинается в вашу честь",
    "враг у ворот и боится вас", "поиск завершён — матч найден для вас",
    "нашёл вам достойных соперников, которых вы уничтожите",
    "враги собрались на арене и ждут своей участи",
    "время сражаться, мой господин",
    "матч готов для вашего величества",
    "игра готова к запуску для вас",
    "нашёл вам прекрасную игру",
    "подобрал идеальную катку для вас",
    "соперники ждут не дождутся вас",
    "ваш матч найден, о великий",
    "нашёл жертв для вашего клинка",
    "противники уже дрожат от страха",
    "время показать им, кто здесь хозяин",
    "игра зовёт своего единственного повелителя",
]

_FOUND_ACTIONS = [
    "Ваш преданный слуга уже принимает матч...",
    "Жму кнопку с максимальной скоростью, мой господин!",
    "Ваш верный слуга уже кликает...",
    "Немедленно принимаю для вас, мой повелитель!",
    "Бегу нажимать кнопку изо всех сил...",
    "Уже нажимаю, мой дорогой господин!",
    "Кликаю по кнопке с величайшей радостью...",
    "Приступаю к принятию с энтузиазмом...",
    "Спешу выполнить ваше желание, мой хозяин...",
    "С радостью нажимаю кнопку за вас...",
    "Обрабатываю принятие с любовью и преданностью...",
    "Ваш слуга торопится нажать «Принять»...",
    "С величайшим удовольствием принимаю матч...",
    "Немедленно выполняю, мой драгоценный господин!",
    "Спешу угодить вам, принимая матч...",
    "Нажимаю кнопку с величайшей заботой о вас...",
]

_FOUND_EMOJIS = ["⚔️", "🎮", "⚡", "🔥", "🏹", "💥", "🗡️", "🎯", "⏰"]

# ── Match accepted parts ─────────────────────────────────────────────────────
_ACCEPTED_OPENERS = [
    "матч принят, мой дорогой повелитель",
    "кнопка нажата с величайшей точностью",
    "игра принята, как вы и приказывали",
    "матч ваш, о несравненный",
    "готово, мой блистательный господин",
    "принято с честью и преданностью",
    "успех, мой великолепный хозяин",
    "матч успешно принят для вас",
    "кнопка «Принять» нажата безупречно",
    "ваш слуга справился на отлично",
    "задание выполнено безупречно, мой господин",
    "принятие прошло идеально, как всегда",
    "всё готово для вашего величества",
    "ваш слуга постарался на славу",
    "катка ваша, мой драгоценный повелитель",
    "вы в игре, о величайший из воинов",
    "игра начинается в вашу честь",
    "ваш верный слуга выполнил задачу блестяще",
    "матч принят с любовью и преданностью",
    "кнопка покорилась вашему слуге",
]

_ACCEPTED_METHODS = [
    "Метод обнаружения: {method}",
    "Нашёл через {method}",
    "Использовал {method}",
    "Обнаружение: {method}",
    "Режим работы: {method}",
    "Кнопка найдена через {method}",
    "Сработал метод: {method}",
    "Детектор: {method}",
]

_ACCEPTED_WISHES = [
    "Удачной игры, мой драгоценный повелитель!",
    "Пусть победа будет за вами, как всегда!",
    "Слава вашей несравненной игре!",
    "Разгромите их всех, мой господин — вы лучший!",
    "Вперёд к победе, о великий воин!",
    "Пусть ММР растёт вместе с вашей славой!",
    "Красивых тимфайтов, мой чемпион!",
    "Удачи в драфте, мой мудрый стратег!",
    "Пусть Рошан будет на вашей стороне, о великий!",
    "Желаю лёгкого лейнинга, мой блистательный керри!",
    "Удачи в тимфайтах, мой непобедимый герой!",
    "Пусть крипы идут к вам, мой драгоценный!",
    "Хорошего пика, мой гениальный стратег!",
    "Разнесите их, мой любимый повелитель!",
    "Пусть удача всегда улыбается вам!",
    "GG WP заранее — вы непобедимы!",
    "Дайте им бой, мой величественный воин!",
    "Покажите им, кто тут настоящий хозяин!",
    "Докажите своё превосходство, о несравненный!",
    "Пора доминировать, мой драгоценный лорд!",
    "Уничтожьте вражеский трон во славу вашу!",
    "Пусть враги бегут в страхе перед вами!",
    "Ваш скилл не знает границ, мой господин!",
    "Вперёд к бессмертному рейтингу!",
    "Пусть каждая команда будет достойна вас!",
    "Ваш слуга верит в вашу победу!",
]

_ACCEPTED_EMOJIS = ["✅", "🏆", "⚔️", "🎮", "💪", "🔥", "👑", "🎯", "💥", "⭐"]

# ── Match failed parts ───────────────────────────────────────────────────────
_FAILED_OPENERS = [
    "не удалось принять матч", "произошла ошибка",
    "ваш слуга не справился", "кнопка не найдена",
    "не смог нажать кнопку", "матч ускользнул",
    "не повезло в этот раз", "кнопка спряталась",
    "поиск кнопки не удался", "не нашёл кнопку «Принять»",
    "ошибка при принятии", "ваш слуга оплошал",
]

_FAILED_REASONS = [
    "Причина: {reason}", "Ошибка: {reason}",
    "Проблема: {reason}", "Детали: {reason}",
    "Что пошло не так: {reason}", "Информация: {reason}",
]

_FAILED_COMFORTS = [
    "Ваш слуга старался...", "Надеюсь, матч найдётся снова.",
    "Скоро будет новый матч!", "Не отчаивайтесь, попробуем ещё.",
    "В следующий раз точно получится!", "Ожидаем новый матч...",
    "Ваш слуга приносит извинения...", "Попробую снова при следующем поиске.",
    "Увы, но я не сдаюсь!", "Готов к следующей попытке!",
    "Скоро найдём другую игру!", "Не расстраивайтесь!",
]

_FAILED_EMOJIS = ["❌", "😔", "⚠️", "💔", "😞", "🫣", "😬"]

# ── Test connection parts ────────────────────────────────────────────────────
_TEST_GREETINGS = [
    "связь установлена, мой драгоценный повелитель",
    "ваш преданный слуга на связи",
    "подключение работает безупречно",
    "я готов служить вам вечно",
    "канал связи активен, мой господин",
    "всё слышу и вижу, о великий",
    "нахожусь на боевом посту для вас",
    "готов к работе во славу вашу",
    "соединение стабильное, как ваша слава",
    "всё работает отлично, как и должно",
    "ваш покорный слуга здесь и ждёт приказов",
    "ожидаю ваших драгоценных приказаний",
    "ваш верный помощник всегда рядом",
    "готов служить днём и ночью",
    "связь идеальная, как и вы",
]

_TEST_READY = [
    "готов служить вам верой и правдой вечно",
    "жду ваших драгоценных указаний",
    "готов оповещать о каждом матче с радостью",
    "буду бдительно следить за матчами для вас",
    "ваш слуга на боевом посту 24/7",
    "к вашим услугам всегда и везде",
    "готов оповещать вас о каждой найденной игре",
    "преданно жду ваших приказаний",
    "ни один матч не ускользнёт от моего взора",
    "буду охранять ваш покой и ловить матчи",
]

_TEST_FOOTER = [
    "Теперь вы будете получать уведомления о матчах, мой господин.",
    "С этого момента ни один матч не пройдёт мимо вас, о великий!",
    "Уведомления будут приходить прямо сюда — отдыхайте!",
    "Теперь уведомления — моя забота, мой дорогой повелитель.",
    "Следите за своим ММР, а я прослежу за матчами!",
    "Отдыхайте, мой драгоценный — я буду следить за поиском.",
    "Ваш верный слуга всегда на страже ваших интересов!",
    "Пусть другие ищут матчи — этим займусь я!",
]

_TEST_EMOJIS = ["🎮", "👑", "⚡", "🔔", "📡", "✅", "🤖", "💎", "🌟"]

# ── /start welcome parts ────────────────────────────────────────────────────
_START_GREETINGS = [
    "Приветствую вас, мой дорогой", "Рад вас видеть, о великий",
    "Добро пожаловать, мой драгоценный", "Приветствую, мой блистательный",
    "Здравствуйте, мой обожаемый господин", "Салютую вам, о несравненный",
    "Доброго дня, мой дорогой повелитель", "Рад знакомству, мой чемпион",
    "Приветствую на борту, мой герой", "Вас приветствует ваш верный слуга",
    "Добро пожаловать в мои владения, о великий", "К вашим услугам, мой господин",
    "Рад служить вам, мой драгоценный", "Приветствую вас, моё сокровище",
    "Вас ждал ваш преданный слуга", "Здравствуйте, мой великолепный",
]

_START_BODY = [
    "Вот ваш персональный Chat ID, мой драгоценный повелитель",
    "Держите ваш Chat ID, мой дорогой господин",
    "Ваш уникальный идентификатор, о великий",
    "Это ваш Chat ID — сохраните его, мой любимый",
    "Ниже указан ваш драгоценный Chat ID",
    "Вот идентификатор, который вам нужен, мой повелитель",
    "Ваш эксклюзивный Chat ID, мой несравненный",
    "Вот ваш заветный номер, мой обожаемый",
]

_START_INSTRUCTION = [
    "Скопируйте его и вставьте в приложение <b>Dota 2 Auto Accept</b> в поле «Chat ID».",
    "Вставьте этот номер в поле «Chat ID» в приложении <b>Dota 2 Auto Accept</b>.",
    "Просто скопируйте и вставьте в приложение в поле «Chat ID», мой дорогой.",
    "Скопируйте номер и вставьте в приложение — поле называется «Chat ID».",
    "Откройте приложение <b>Dota 2 Auto Accept</b> и вставьте этот ID в поле «Chat ID».",
    "Сделайте copy-paste в поле «Chat ID», мой драгоценный повелитель.",
    "Просто вставьте этот ID в приложение и я начну служить!",
]

_START_FOOTER = [
    "После этого вы будете получать уведомления о каждом матче, мой господин!",
    "И уведомления о матчах будут приходить к вам, о великий!",
    "Готово — и вы не пропустите ни одной игры, мой драгоценный!",
    "Теперь бот будет оповещать вас о найденных матчах!",
    "Всё! Теперь уведомления — моя забота, мой повелитель!",
    "И ни один матч не ускользнёт от вашего внимания, мой чемпион!",
    "Ваш верный слуга будет бдительно следить за каждым матчем!",
    "Отдыхайте — ваш преданный помощник всегда на страже!",
]

_START_EMOJIS = ["👑", "🎮", "⚔️", "🤖", "🔔", "✨", "💬", "💎", "🌟"]


# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _title_with_uname(title: str, username: str) -> str:
    """Format title + @username for bold header."""
    uname = f" @{username}" if username else ""
    return f"{title}{uname}"


def _build_found_msg(username: str) -> str:
    """Randomly assemble a 'match found' message."""
    title = random.choice(_TITLES)
    opener = random.choice(_FOUND_OPENERS)
    action = random.choice(_FOUND_ACTIONS)
    emoji = random.choice(_FOUND_EMOJIS)
    return (
        f"{emoji} <b>{_title_with_uname(title, username)}, {opener}!</b>\n"
        f"{action}"
    )


def _build_accepted_msg(username: str, method: str) -> str:
    """Randomly assemble a 'match accepted' message."""
    title = random.choice(_TITLES)
    opener = random.choice(_ACCEPTED_OPENERS)
    method_line = random.choice(_ACCEPTED_METHODS).format(method=method)
    wish = random.choice(_ACCEPTED_WISHES)
    emoji = random.choice(_ACCEPTED_EMOJIS)
    return (
        f"{emoji} <b>{_title_with_uname(title, username)}, {opener}!</b>\n"
        f"{method_line}.\n"
        f"{wish}"
    )


def _build_failed_msg(username: str, reason: str) -> str:
    """Randomly assemble a 'match failed' message."""
    title = random.choice(_TITLES)
    opener = random.choice(_FAILED_OPENERS)
    reason_line = random.choice(_FAILED_REASONS).format(reason=reason)
    comfort = random.choice(_FAILED_COMFORTS)
    emoji = random.choice(_FAILED_EMOJIS)
    return (
        f"{emoji} <b>{_title_with_uname(title, username)}, {opener}!</b>\n"
        f"{reason_line}\n"
        f"{comfort}"
    )


def _build_test_msg(username: str, bot_name: str) -> str:
    """Randomly assemble a 'test connection' message."""
    title = random.choice(_TITLES)
    greeting = random.choice(_TEST_GREETINGS)
    ready = random.choice(_TEST_READY)
    footer = random.choice(_TEST_FOOTER)
    emoji = random.choice(_TEST_EMOJIS)
    return (
        f"{emoji} <b>{_title_with_uname(title, username)}, {greeting}!</b>\n"
        f"Бот @{bot_name} {ready}.\n"
        f"{footer}"
    )


def _build_start_msg(chat_id: str, username: str) -> str:
    """Randomly assemble a /start welcome message."""
    title = random.choice(_TITLES)
    greeting = random.choice(_START_GREETINGS)
    body = random.choice(_START_BODY)
    instruction = random.choice(_START_INSTRUCTION)
    footer = random.choice(_START_FOOTER)
    emoji = random.choice(_START_EMOJIS)
    uname = f" @{username}" if username else ""
    return (
        f"{emoji} <b>{greeting}, {title.lower()}{uname}!</b>\n\n"
        f"{body}:\n"
        f"<code>{chat_id}</code>\n\n"
        f"{instruction}\n\n"
        f"{footer}"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  BACKGROUND LISTENER
# ══════════════════════════════════════════════════════════════════════════════

_bg_listener_running = False
_bg_listener_thread = None
_on_chat_id_received = None  # callback(chat_id, username)


def _api_call(method: str, payload: dict = None, timeout: int = 10) -> dict | None:
    """Make a blocking Telegram Bot API call. Returns parsed JSON or None."""
    url = API.format(token=BOT_TOKEN, method=method)
    try:
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[TG] API call {method} failed: {e}")
        return None


def send_notification(chat_id: str, message: str) -> bool:
    """Send a Telegram message. Non-blocking (runs in a daemon thread)."""
    if not chat_id or not _is_valid_chat_id(chat_id):
        return False

    def _send():
        _api_call("sendMessage", {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        })

    threading.Thread(target=_send, daemon=True).start()
    return True


def get_username(chat_id: str) -> str:
    """Fetch the Telegram username for a chat_id. Returns '' if unavailable."""
    result = _api_call("getChat", {"chat_id": chat_id})
    if result and result.get("ok"):
        return result["result"].get("username", "") or result["result"].get("first_name", "")
    return ""


def test_connection(chat_id: str) -> tuple[bool, str]:
    """Test Telegram connection by sending a random test message. Blocking."""
    if not chat_id:
        return False, "Не указан Chat ID"
    if not _is_valid_chat_id(chat_id):
        return False, "Некорректный Chat ID (только цифры)"

    # Verify bot token first
    result = _api_call("getMe")
    if not result or not result.get("ok"):
        return False, "Ошибка подключения к боту"
    bot_name = result["result"].get("username", "bot")

    # Fetch username
    uname = ""
    chat_info = _api_call("getChat", {"chat_id": chat_id})
    if chat_info and chat_info.get("ok"):
        uname = (chat_info["result"].get("username", "")
                 or chat_info["result"].get("first_name", ""))

    msg = _build_test_msg(uname, bot_name)
    result = _api_call("sendMessage", {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML",
    })
    if result and result.get("ok"):
        return True, f"Сообщение отправлено (chat {chat_id})"
    desc = result.get("description", "неизвестная ошибка") if result else "нет ответа"
    return False, f"Ошибка: {desc}"


def start_background_listener(callback):
    """
    Start a background thread that continuously polls for /start commands.
    callback(chat_id: str, username: str) is called when /start is received.
    Safe to call multiple times — only one listener runs at a time.
    """
    global _bg_listener_running, _bg_listener_thread, _on_chat_id_received

    if _bg_listener_running:
        return  # already running

    _on_chat_id_received = callback
    _bg_listener_running = True

    def _poll_loop():
        global _bg_listener_running
        offset = None

        # Skip old updates
        result = _api_call("getUpdates", {"timeout": 0}, timeout=10)
        if result and result.get("ok") and result["result"]:
            offset = result["result"][-1]["update_id"] + 1

        while _bg_listener_running:
            params = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset

            result = _api_call("getUpdates", params, timeout=35)
            if not result or not result.get("ok"):
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = (msg.get("text") or "").strip()
                chat_id = str(msg.get("chat", {}).get("id", ""))
                from_user = msg.get("from", {})
                username = from_user.get("username", "") or from_user.get("first_name", "")

                if text.startswith("/start") and chat_id:
                    welcome = _build_start_msg(chat_id, username)
                    _api_call("sendMessage", {
                        "chat_id": chat_id,
                        "text": welcome,
                        "parse_mode": "HTML",
                    })
                    if _on_chat_id_received:
                        _on_chat_id_received(chat_id, username)

        _bg_listener_running = False

    _bg_listener_thread = threading.Thread(target=_poll_loop, daemon=True)
    _bg_listener_thread.start()


def stop_background_listener():
    """Stop the background /start listener."""
    global _bg_listener_running
    _bg_listener_running = False


def get_chat_id_from_bot(timeout: int = 90) -> tuple[bool, str]:
    """
    One-shot poll for /start (legacy — used by the button).
    Returns (success, chat_id_or_error).
    """
    offset = None
    result = _api_call("getUpdates", {"timeout": 0}, timeout=10)
    if result and result.get("ok") and result["result"]:
        offset = result["result"][-1]["update_id"] + 1

    attempts = max(1, timeout // 35)
    for _ in range(attempts):
        params = {"timeout": 30}
        if offset is not None:
            params["offset"] = offset

        result = _api_call("getUpdates", params, timeout=40)
        if not result or not result.get("ok"):
            continue

        for update in result.get("result", []):
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            text = (msg.get("text") or "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))
            from_user = msg.get("from", {})
            username = from_user.get("username", "") or from_user.get("first_name", "")

            if text.startswith("/start") and chat_id:
                welcome = _build_start_msg(chat_id, username)
                _api_call("sendMessage", {
                    "chat_id": chat_id,
                    "text": welcome,
                    "parse_mode": "HTML",
                })
                return True, chat_id

    return False, "Ожидание истекло. Напишите боту /start и попробуйте снова."


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC NOTIFICATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def notify_match_found(chat_id: str, username: str = ""):
    """Send match-found notification."""
    send_notification(chat_id, _build_found_msg(username))


def notify_accepted(chat_id: str, method: str, username: str = ""):
    """Send match-accepted notification."""
    send_notification(chat_id, _build_accepted_msg(username, method))


def notify_failed(chat_id: str, reason: str, username: str = ""):
    """Send acceptance failure notification."""
    send_notification(chat_id, _build_failed_msg(username, reason))


# ══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def _is_valid_chat_id(chat_id: str) -> bool:
    """Chat ID must be a non-empty string of digits (optionally with leading minus)."""
    if not chat_id:
        return False
    return bool(re.match(r"^-?\d{1,15}$", chat_id.strip()))
