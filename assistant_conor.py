#!/usr/bin/env python3
"""Голосовой помощник "Конор" для ПК с интеграцией GigaChat.

Возможности:
- Управление громкостью (mute/unmute/set).
- Запуск приложений и открытие ссылок в браузере.
- Простые системные команды (блокировка/выключение/перезагрузка).
- Резервный ответ через GigaChat для произвольных запросов.

Важно: токен GigaChat нужно передавать через переменную окружения
GIGACHAT_API_KEY (или в .env, если установлен python-dotenv).
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from typing import Dict, Optional
from urllib import error, request

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except ImportError:
    CLSCTX_ALL = None
    AudioUtilities = None
    IAudioEndpointVolume = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


@dataclass
class Config:
    name: str = "конор"
    model: str = "GigaChat"
    api_key: Optional[str] = None
    scope: str = "GIGACHAT_API_PERS"


class ConorAssistant:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.os_name = platform.system().lower()
        self.recognizer = sr.Recognizer() if sr else None
        self.tts = pyttsx3.init() if pyttsx3 else None
        self.access_token: Optional[str] = None

        self.apps: Dict[str, str] = {
            "браузер": "start msedge" if self.os_name == "windows" else "xdg-open https://www.google.com",
            "блокнот": "notepad" if self.os_name == "windows" else "gedit",
            "калькулятор": "calc" if self.os_name == "windows" else "gnome-calculator",
            "проводник": "explorer" if self.os_name == "windows" else "nautilus",
        }

    def speak(self, text: str) -> None:
        print(f"Конор: {text}")
        if self.tts:
            self.tts.say(text)
            self.tts.runAndWait()

    def listen(self) -> str:
        if not self.recognizer:
            return input("Вы (текст): ").strip().lower()

        with sr.Microphone() as source:
            print("Слушаю...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=8)

        try:
            text = self.recognizer.recognize_google(audio, language="ru-RU")
            print(f"Вы: {text}")
            return text.lower()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as exc:
            self.speak(f"Ошибка распознавания речи: {exc}")
            return ""

    def _set_volume(self, percent: int) -> bool:
        if self.os_name != "windows" or not AudioUtilities:
            return False
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        volume.SetMasterVolumeLevelScalar(max(0, min(100, percent)) / 100.0, None)
        return True

    def _mute(self, mute: bool) -> bool:
        if self.os_name != "windows" or not AudioUtilities:
            return False
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        volume.SetMute(1 if mute else 0, None)
        return True

    def _open_url(self, text: str) -> bool:
        match = re.search(r"https?://\S+", text)
        if not match:
            return False
        webbrowser.open(match.group(0))
        return True

    def _launch_app(self, app_name: str) -> bool:
        cmd = self.apps.get(app_name)
        if not cmd:
            return False
        subprocess.Popen(cmd, shell=True)
        return True

    def _run_system_command(self, text: str) -> bool:
        if "перезагрузи" in text:
            if self.os_name == "windows":
                subprocess.Popen("shutdown /r /t 0", shell=True)
            else:
                subprocess.Popen("systemctl reboot", shell=True)
            return True
        if "выключи компьютер" in text or "выключи пк" in text:
            if self.os_name == "windows":
                subprocess.Popen("shutdown /s /t 0", shell=True)
            else:
                subprocess.Popen("systemctl poweroff", shell=True)
            return True
        if "заблокируй" in text:
            if self.os_name == "windows":
                subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            else:
                subprocess.Popen("loginctl lock-session", shell=True)
            return True
        return False

    def _giga_auth(self) -> Optional[str]:
        if not self.config.api_key:
            return None

        data = "scope=" + self.config.scope
        req = request.Request(
            GIGACHAT_AUTH_URL,
            data=data.encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": "conor-desktop-assistant",
                "Authorization": f"Basic {self.config.api_key}",
            },
        )
        try:
            with request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload.get("access_token")
        except error.URLError as exc:
            self.speak(f"Не удалось авторизоваться в GigaChat: {exc}")
            return None

    def ask_gigachat(self, prompt: str) -> str:
        if not self.access_token:
            self.access_token = self._giga_auth()

        if not self.access_token:
            return "Я не смог подключиться к GigaChat. Проверь API ключ."

        body = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты голосовой помощник по имени Конор для управления ПК. Отвечай кратко на русском.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
        }

        req = request.Request(
            GIGACHAT_CHAT_URL,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
        )

        try:
            with request.urlopen(req, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            return f"Ошибка GigaChat: {exc}"

    def handle_command(self, text: str) -> None:
        if not text:
            self.speak("Не расслышал, повторите.")
            return

        if self.config.name not in text:
            return

        command = text.replace(self.config.name, "", 1).strip()

        if "выключи громкость" in command or "без звука" in command:
            if self._mute(True):
                self.speak("Готово, звук выключен.")
            else:
                self.speak("Управление громкостью пока доступно только на Windows с pycaw.")
            return

        if "включи громкость" in command or "верни звук" in command:
            if self._mute(False):
                self.speak("Звук включен.")
            else:
                self.speak("Управление громкостью пока доступно только на Windows с pycaw.")
            return

        vol_match = re.search(r"громкость\s+на\s+(\d{1,3})", command)
        if vol_match:
            level = int(vol_match.group(1))
            if self._set_volume(level):
                self.speak(f"Установил громкость на {max(0, min(100, level))} процентов.")
            else:
                self.speak("Не удалось изменить громкость. Убедитесь что установлены pycaw и comtypes.")
            return

        app_match = re.search(r"запусти\s+(.+)", command)
        if app_match:
            target = app_match.group(1).strip()
            if target.startswith("http://") or target.startswith("https://"):
                webbrowser.open(target)
                self.speak("Открыл ссылку в браузере.")
                return
            if self._launch_app(target):
                self.speak(f"Запускаю {target}.")
            else:
                self.speak(f"Я не знаю приложение {target}. Добавь его в словарь apps.")
            return

        if self._open_url(command):
            self.speak("Открыл ссылку.")
            return

        if self._run_system_command(command):
            self.speak("Выполняю системную команду.")
            return

        answer = self.ask_gigachat(command)
        self.speak(answer)


def main() -> None:
    if load_dotenv:
        load_dotenv()

    api_key = os.getenv("GIGACHAT_API_KEY")
    config = Config(api_key=api_key)
    assistant = ConorAssistant(config)

    assistant.speak(
        "Привет! Я Конор. Скажи команду, например: Конор выключи громкость, "
        "Конор громкость на 30, Конор запусти браузер. Для выхода скажи Конор стоп."
    )

    while True:
        text = assistant.listen()
        if not text:
            continue
        if config.name in text and "стоп" in text:
            assistant.speak("До встречи!")
            break
        assistant.handle_command(text)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
