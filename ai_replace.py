"""
AI Text Replace — замена выделенного текста ответом от ИИ.
При запуске: копирует выделенный текст → отправляет в ИИ с промтом → вставляет ответ.
Предназначен для привязки к кнопке мыши MX Master 3S через Logitech Options+.
"""

import os
import sys
import json
import time
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# === Логирование ===
SCRIPT_DIR = Path(__file__).parent.resolve()
LOG_PATH = SCRIPT_DIR / "ai_replace.log"

def log(msg: str):
    """Пишет сообщение в лог-файл с временной меткой (с retry при блокировке)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    # Ротация лога если больше 500 КБ
    if LOG_PATH.exists() and LOG_PATH.stat().st_size > 500_000:
        try:
            bak = LOG_PATH.with_suffix(".log.bak")
            bak.write_text("", encoding="utf-8")  # очищаем старый бэкап
            LOG_PATH.replace(bak)
        except Exception:
            pass
    # Retry до 5 попыток при блокировке файла
    for attempt in range(5):
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            break
        except PermissionError:
            if attempt < 4:
                time.sleep(0.2)
            else:
                # Последняя попытка — пишем в альтернативный файл
                alt = LOG_PATH.with_name(f"ai_replace_{os.getpid()}.log")
                try:
                    with open(alt, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                except Exception:
                    pass
        except OSError:
            if attempt < 4:
                time.sleep(0.2)

# === Загрузка конфигурации ===
CONFIG_PATH = SCRIPT_DIR / "config.json"


def load_config():
    """Загружает config.json."""
    if not CONFIG_PATH.exists():
        log(f"[ОШИБКА] config.json не найден: {CONFIG_PATH}")
        log("Создайте config.json на основе примера ниже.")
        show_example_config()
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def show_example_config():
    """Показывает пример конфигурации."""
    example = {
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4o",
        "prompt": "Перепиши текст ниже так, чтобы он звучал живо и естественно — как пишет реальный человек, а не бездушная машина. При этом сохрани деловой, официальный тон там, где он уместен. Поправь грамматику, синтаксис и смысл, если где-то съехало. Улучши структуру и flow повествования, чтобы текст читался легко и выглядел профессионально. Не добавляй ничего от себя сверх того, что уже сказано — только переработай форму.\n\n{text}",
        "system_prompt": "Ты — опытный редактор, который умеет превращать сухие или корявые тексты в живую, человеческую речь, не теряя серьёзности и делового тона. Ты работаешь только с формой, не меняя сути. На выходе — ТОЛЬКО готовый переработанный текст. Никаких вступлений, пояснений, markdown-разметки, кавычек-обёрток. Просто исправленный текст.",
        "temperature": 0.7,
        "max_tokens": 4096,
        "api_base": "https://api.openai.com/v1",
        "delay_before_copy": 0.2,
        "delay_before_paste": 0.3,
    }
    log(json.dumps(example, ensure_ascii=False, indent=2))


# === Загрузка .env ===
def load_env():
    """Загружает переменные из .env файла."""
    env_path = SCRIPT_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value


# === Работа с буфером обмена ===
def get_clipboard_text():
    """Получает текст из буфера обмена."""
    # Сначала пробуем через tkinter (надёжно, без проблем с кодировкой)
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text
    except Exception:
        pass

    # Fallback: PowerShell через временный файл (избегаем проблем с кодировкой в pipe)
    tmp = SCRIPT_DIR / "_clipboard_get_temp.txt"
    ps_cmd = f'Get-Clipboard -Raw | Out-File -FilePath "{tmp}" -Encoding UTF8'
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        timeout=10,
    )
    if result.returncode == 0 and tmp.exists():
        text = tmp.read_text(encoding="utf-8-sig")
        tmp.unlink(missing_ok=True)
        return text

    log(f"[ОШИБКА] Не удалось прочитать буфер обмена")
    sys.exit(1)


def set_clipboard_text(text: str):
    """Устанавливает текст в буфер обмена через временный файл (избегаем проблем с кодировкой)."""
    tmp = SCRIPT_DIR / "_clipboard_temp.txt"
    tmp.write_text(text, encoding="utf-8")

    ps_cmd = f'$t = Get-Content -Path "{tmp}" -Encoding UTF8 -Raw; Set-Clipboard -Value $t'
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        timeout=10,
    )
    tmp.unlink(missing_ok=True)

    if result.returncode != 0:
        log(f"[ОШИБКА] Не удалось записать в буфер обмена (код {result.returncode})")
        sys.exit(1)


# === Эмуляция клавиш ===
def send_ctrl_c():
    """Отправляет Ctrl+C для копирования выделенного текста."""
    import ctypes

    # Используем Win32 API через keyboard (если установлен) или ctypes
    try:
        import keyboard

        keyboard.send("ctrl+c")
    except ImportError:
        # Fallback через PowerShell + SendKeys
        script = """
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.SendKeys]::SendWait("^c")
        """
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
        )


def send_ctrl_v():
    """Отправляет Ctrl+V для вставки текста."""
    try:
        import keyboard

        keyboard.send("ctrl+v")
    except ImportError:
        script = """
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.SendKeys]::SendWait("^v")
        """
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
        )


# === AI API клиенты ===
def call_openai(config: dict, text: str, api_key: str) -> str:
    """Отправляет запрос к OpenAI API."""
    from urllib import request, error
    import json as json_mod

    api_base = config.get("api_base", "https://api.openai.com/v1").rstrip("/")
    url = f"{api_base}/chat/completions"

    system_prompt = config.get("system_prompt", "")
    prompt_template = config.get("prompt", "{text}")
    prompt = prompt_template.replace("{text}", text)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = json_mod.dumps(
        {
            "model": config.get("model", "gpt-4o"),
            "messages": messages,
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4096),
        }
    ).encode("utf-8")

    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with request.urlopen(req, timeout=config.get("timeout", 60)) as resp:
            data = json_mod.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        log(f"[ОШИБКА] HTTP {e.code}: {error_body}")
        sys.exit(1)
    except Exception as e:
        log(f"[ОШИБКА] Ошибка соединения: {e}")
        sys.exit(1)


def call_anthropic(config: dict, text: str, api_key: str) -> str:
    """Отправляет запрос к Anthropic Claude API."""
    from urllib import request, error
    import json as json_mod

    url = "https://api.anthropic.com/v1/messages"

    prompt_template = config.get("prompt", "{text}")
    prompt = prompt_template.replace("{text}", text)

    system_prompt = config.get("system_prompt", "")

    body = json_mod.dumps(
        {
            "model": config.get("model", "claude-sonnet-4-20250514"),
            "max_tokens": config.get("max_tokens", 4096),
            "temperature": config.get("temperature", 0.7),
            "system": system_prompt if system_prompt else None,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")

    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with request.urlopen(req, timeout=config.get("timeout", 60)) as resp:
            data = json_mod.loads(resp.read().decode("utf-8"))
            # Claude возвращает content в виде списка блоков
            content = data.get("content", [])
            if content and isinstance(content, list):
                return "".join(
                    block.get("text", "") for block in content if block.get("type") == "text"
                ).strip()
            return str(content)
    except error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        log(f"[ОШИБКА] HTTP {e.code}: {error_body}")
        sys.exit(1)
    except Exception as e:
        log(f"[ОШИБКА] Ошибка соединения: {e}")
        sys.exit(1)


# === Уведомления ===
def show_notification(title: str, message: str):
    """Показывает всплывающее уведомление в Windows."""
    try:
        # Используем PowerShell для показа toast-уведомления
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("AI Replace").Show($toast)
        """
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass  # Уведомления — не критично


# === Основной рабочий процесс ===
def main():
    # Загружаем .env и конфиг
    load_env()
    config = load_config()

    # Получаем API ключ
    api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        log(f"[ОШИБКА] API-ключ не найден. Установите переменную {api_key_env} в файле .env")
        log(f"Путь к .env: {SCRIPT_DIR / '.env'}")
        sys.exit(1)

    log("[СТАРТ] Запуск AI Replace")
    delay_copy = config.get("delay_before_copy", 0.2)
    delay_paste = config.get("delay_before_paste", 0.3)

    # Шаг 1: Копируем выделенный текст
    log(f"[ШАГ 1] Пауза {delay_copy}с, затем Ctrl+C...")
    time.sleep(delay_copy)
    send_ctrl_c()
    log("[ШАГ 1] Ctrl+C отправлен")
    time.sleep(0.3)

    # Шаг 2: Читаем текст из буфера
    log("[ШАГ 2] Чтение буфера обмена...")
    selected_text = get_clipboard_text().strip()

    if not selected_text:
        show_notification("AI Replace", "Нет выделенного текста!")
        log("[ОШИБКА] Буфер обмена пуст — возможно, не был выделен текст или Ctrl+C не сработал")
        sys.exit(0)

    log(f"[ШАГ 2] Получен текст ({len(selected_text)} симв.): {selected_text[:100]}...")

    # Шаг 3: Отправляем в ИИ
    provider = config.get("provider", "openai")
    model = config.get("model", "?")
    log(f"[ШАГ 3] Отправка запроса к {provider} (модель: {model})...")
    show_notification("AI Replace", f"Запрос к {model}...")

    try:
        if provider == "openai":
            response = call_openai(config, selected_text, api_key)
        elif provider == "anthropic":
            response = call_anthropic(config, selected_text, api_key)
        else:
            log(f"[ОШИБКА] Неизвестный провайдер: {provider}")
            log("Поддерживаются: openai, anthropic")
            sys.exit(1)
    except Exception as e:
        log(f"[ОШИБКА] Ошибка при обращении к API: {e}")
        show_notification("AI Replace", f"Ошибка: {e}")
        sys.exit(1)

    if not response:
        log("[ОШИБКА] Пустой ответ от API")
        show_notification("AI Replace", "Пустой ответ от API")
        sys.exit(1)

    log(f"[ШАГ 3] Ответ получен ({len(response)} симв.): {response[:100]}...")

    # Шаг 4: Вставляем ответ вместо выделенного текста
    log("[ШАГ 4] Вставка ответа...")
    set_clipboard_text(response)
    time.sleep(delay_paste)
    send_ctrl_v()

    log("[OK] Текст успешно заменён!")
    show_notification("AI Replace", "Текст заменён!")


if __name__ == "__main__":
    main()