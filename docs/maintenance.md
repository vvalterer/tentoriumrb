# 🧰 Сопровождение проекта by Vetoshkin

Практический чек-лист для ежедневной работы с проектом (Git/GitHub + деплой на mchost).

---

## 1) Рабочий цикл (локально)

`powershell
git pull
git status
git add .
git commit -m "feat/fix/docs: кратко что сделал"
git push
Рекомендации по сообщениям:

feat: новая фича, fix: исправление, docs: правки документации, refactor: без изменения поведения.

2) Ветки

Основная разработка: main

Прод под Python 3.6: prod-py36

Создать/переключиться:

git checkout -b dev
git push -u origin dev
git switch prod-py36


Слияние (из dev в prod-py36 после тестов):

git switch prod-py36
git merge dev
git push

3) Что не коммитим (держит .gitignore)
.env
*.env
venv/
__pycache__/
db.sqlite3
/staticfiles/
/media/
logs/

4) Подготовка релиза

Локально протестировать (runserver, формы, авторизация, статика).

Собрать «чистый» архив из текущей ветки:

git archive --format=zip --output ..\tentoriumrb-REL.zip HEAD


(Опц.) Поставить тег:

git tag -a vX.Y.Z-py36 -m "описание"
git push origin vX.Y.Z-py36

5) Обновление на сервере (mchost, без sudo)
cd /path/to/tentoriumrb
source .venv/bin/activate || python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip==21.3.1
pip install -r requirements-py36.txt
python manage.py migrate
python manage.py collectstatic --noinput
touch myapp/wsgi.py   # перезапуск приложения


.env хранится на сервере и не попадает в Git. Минимум:

SECRET_KEY=...
DEBUG=false
ALLOWED_HOSTS=tentoriumrb.ru
# DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
LOG_DIR=logs

6) Резервные копии (минимум)

Код: метки-теги vX.Y.Z-py36 в GitHub.

Медиа: периодический архив /media/.

БД: дамп по расписанию (через инструменты хостинга или отдельный cron/скрипт).

Хранить последние 3–5 бэкапов.

7) Диагностика и частые проблемы

git push висит/падает: проверь ssh -T git@github.com, git remote -v, антивирус/фаервол, лишние большие файлы (Get-ChildItem -Recurse | Where Length -gt 20MB).

Django не стартует локально: проверь .env, путь LOG_DIR, миграции python manage.py migrate.

Статика не отдается: collectstatic, настройки STATIC_URL/STATIC_ROOT, конфигурация веб-сервера.

500 на проде: смотри логи logs/django_error.log, валидность .env, права на папки.

8) Безопасность (быстрый чек)

DEBUG=false на проде

Секреты только в .env

ALLOWED_HOSTS содержит домен

Регулярные обновления зависимостей (в рамках py3.6 - см. requirements-py36.txt)

Нет чувствительных данных в репозитории/истории

9) Полезные ссылки

Деплой на mchost: docs/deploy-mchost.md

Гайд по Git/GitHub: docs/github-guide.md

Репозиторий: GitHub → ветка prod-py36

© Вячеслав Ветошкин • 1vetoshkin.ru • t.me/TkAs007bot
