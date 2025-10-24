## Деплой на mchost (Python 3.6)
- Прод-ветка: `prod-py36` (Django 3.2 LTS).
- Создать venv на сервере `python3 -m venv .venv`, активировать и поставить зависимости из `requirements-py36.txt`.
- Использовать `.env` (секреты, ALLOWED_HOSTS, DATABASE_URL).
- После обновления кода: `python manage.py collectstatic --noinput`, перезапуск приложения (touch `myapp/wsgi.py` или перезапуск процесса — зависит от конфигурации хостинга).
