# Деплой на mchost (Python 3.6)

**Цель:** запустить ветку `prod-py36` (Django 3.2 LTS) на сервере без sudo.

## 1) Подготовка проекта
- Залейте код ветки `prod-py36` (или скачайте ZIP артефакт).
- В корне проекта создайте `.env` по образцу `.env.example` и заполните:
  - `SECRET_KEY=...`
  - `DEBUG=false`
  - `ALLOWED_HOSTS=tentoriumrb.ru`
  - `DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME` (если Postgres)
  - `LOG_DIR=logs`

## 2) Виртуальное окружение (Python 3.6)