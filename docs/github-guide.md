# 🧭 GitHub by Vetoshkin — Полное руководство

> Практическая шпаргалка для работы с Git и GitHub.  
> Подходит для проектов 	entoriumrb, vbook, 1vetoshkin и других Django-проектов.

---

## ⚙️ 1. Настройка Git (один раз)

`powershell
git config --global user.name "Vyacheslav Vetoshkin"
git config --global user.email "12345678+vvalterer@users.noreply.github.com"
git config --global init.defaultBranch main
2. Настройка SSH-ключа
ssh-keygen -t ed25519 -C "12345678+vvalterer@users.noreply.github.com"
Get-Content C:\Users\Vyacheslav\.ssh\id_ed25519.pub | Set-Clipboard
→ вставь ключ на https://github.com/settings/keys
Проверить подключение:
ssh -T git@github.com
3. Создание нового репозитория
cd C:\Work\Sites\project_name
git init
git branch -M main
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:vvalterer/project_name.git
git push -u origin main
4. Основные команды
ДействиеКоманда
Проверить статусgit status
Добавить файлыgit add .
Сделать коммитgit commit -m "сообщение"
Отправить на GitHubgit push
Получить обновленияgit pull
Создать веткуgit checkout -b prod-py36
Переключитьсяgit switch prod-py36
Историяgit log --oneline --graph --decorate
🌿 5. Ветки и публикация
git checkout -b prod-py36
git push -u origin prod-py36


Для переключения:

git switch main
git switch prod-py36

🚀 6. Обновление проекта на сервере (без sudo)
cd /path/to/project
source .venv/bin/activate
git pull origin prod-py36
pip install -r requirements-py36.txt
python manage.py migrate
python manage.py collectstatic --noinput
touch myapp/wsgi.py

🧩 7. Игнорируемые файлы (.gitignore)
__pycache__/
*.py[cod]
venv/
.env
*.env
db.sqlite3
/staticfiles/
/media/
logs/

📦 8. Создание ZIP-артефакта (для загрузки на mchost)
git archive --format=zip --output ..\project-prod.zip HEAD

💬 9. Полезные alias-сокращения
git config --global alias.s "status -sb"
git config --global alias.cm "commit -m"
git config --global alias.co "checkout"
git config --global alias.br "branch"
git config --global alias.ll "log --oneline --graph --decorate --all"

🧹 10. Удаление или переинициализация

Удалить файл:

git rm путь/к/файлу
git commit -m "remove лишний файл"
git push


Полное переинициализирование:

rm -r .git
git init
git add .
git commit -m "reinit"
git remote add origin git@github.com:vvalterer/project_name.git
git push -u origin main --force

🧠 11. Мини-глоссарий
ТерминЗначение
commitсохранение версии проекта
pushотправка коммитов на GitHub
pullполучение изменений
branchветка
mergeслияние
.gitignoreсписок игнорируемых файлов
repositoryпроект на GitHub
remoteудалённый репозиторий
originимя по умолчанию для GitHub-репо

© Вячеслав Ветошкин • 1vetoshkin.ru
 • t.me/TkAs007bot

