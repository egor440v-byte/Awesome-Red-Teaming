# Конор — голосовой помощник для ПК

## Быстрый старт

1. Установите зависимости:
   ```bash
   pip install -r requirements-conor.txt
   ```

2. Задайте API-ключ GigaChat через переменную окружения:
   ```bash
   export GIGACHAT_API_KEY='ВАШ_BASE64_КЛЮЧ'
   ```
   Для Windows PowerShell:
   ```powershell
   setx GIGACHAT_API_KEY "ВАШ_BASE64_КЛЮЧ"
   ```

3. Запустите помощника:
   ```bash
   python assistant_conor.py
   ```

## Примеры команд

- `Конор выключи громкость`
- `Конор включи громкость`
- `Конор громкость на 30`
- `Конор запусти браузер`
- `Конор запусти https://ya.ru`
- `Конор заблокируй`
- `Конор выключи пк`

## Важно

- Полное управление громкостью реализовано для **Windows** через `pycaw`.
- На Linux/macOS можно расширить функции в методах `_set_volume` и `_mute`.
- Список приложений для запуска находится в `self.apps` в `assistant_conor.py`.
