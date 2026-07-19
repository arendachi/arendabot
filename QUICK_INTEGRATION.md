# ⚡ Быстрая интеграция (5 минут)

## 📋 Шаг за шагом

### 1️⃣ Копируем файлы в ваш repo

```bash
# В корень проекта скопируйте:
- scraper_joyestate.js      # Парсер
- scraper_joyestate.py      # Парсер (Python версия)
- package.json              # Обновить или создать
- requirements.txt          # Для Python
- .gitignore               # Обновить
```

### 2️⃣ GitHub Actions (автоматический запуск)

```bash
# Создаём папку и файл
mkdir -p .github/workflows
cp scrape.yml .github/workflows/scrape.yml

# Коммитим
git add .github/workflows/scrape.yml
git commit -m "Add automated scraper workflow"
git push
```

✅ Готово! Теперь парсер будет запускаться **ежедневно в 03:00 UTC** и автоматически коммитить результаты!

### 3️⃣ Запуск вручную (опционально)

```bash
# Если у вас Node.js:
npm install puppeteer
npm run scrape

# Если у вас Python:
pip install -r requirements.txt
python3 scraper_joyestate.py
```

---

## 🎯 Всё готово!

Теперь в вашем репо:

✅ **Автоматический парсинг** - каждый день в 03:00  
✅ **Все данные в Git** - полная история изменений  
✅ **Готов к деплою** - Docker, Heroku и т.д.  

---

## 📊 Проверка результатов

После первого запуска (или на следующий день):

```bash
# Скачиваем репо
git pull

# Проверяем данные
cat data/listings.json | head -20
```

Должны увидеть JSON с объявлениями:
```json
[
  {
    "title": "Квартира 2-комнатная",
    "price": "500 000 сум/месяц",
    "address": "Ташкент",
    ...
  }
]
```

---

## 🔧 Если что-то не работает

### Проблема: GitHub Actions не запустился
✅ **Решение:** Перейдите на `Actions` → выберите `Daily Scrape` → нажмите `Run workflow`

### Проблема: "permission denied" при коммите
✅ **Решение:** Проверьте, что у вас есть права на пушинг. Откройте `Settings` → `Actions` → `Read and write permissions`

### Проблема: Данные не обновляются
✅ **Решение:** Посмотрите логи:
- GitHub: `Actions` → `Daily Scrape` → посмотрите последний run
- Локально: запустите `npm run scrape` и посмотрите ошибки

---

## 📈 Мониторинг

### Где смотреть результаты?

1. **GitHub Actions** (автоматический запуск)
   - Перейдите на вкладку `Actions`
   - Выберите `Daily Scrape`
   - Смотрите статус запусков

2. **Коммиты** (результаты парсинга)
   - Перейдите на вкладку `Commits`
   - Ищите коммиты вида "🔄 Update listings: ..."
   - Кликните на коммит → посмотрите изменения в `data/listings.json`

3. **История изменений файла**
   ```bash
   git log --oneline data/listings.json | head -10
   ```

---

## 🚀 Дополнительные команды

```bash
# Просмотр первых 5 объявлений
jq '.[0:5]' data/listings.json

# Количество объявлений
jq 'length' data/listings.json

# Все уникальные цены
jq '.[].price' data/listings.json | sort -u

# Все адреса
jq '.[].address' data/listings.json | sort -u

# Последнее обновление
jq '.[-1].timestamp' data/listings.json
```

---

## 💡 Советы

📌 **Совет 1:** Если хотите изменить время запуска, отредактируйте `scrape.yml`:
```yaml
- cron: '0 3 * * *'  # 03:00 UTC → измените на нужное время
# Примеры:
# '0 9 * * *' - 09:00 UTC (11:00 Ташкент)
# '0 */6 * * *' - каждые 6 часов
# '0 0 * * 0' - по воскресеньям в 00:00
```

📌 **Совет 2:** Если нужна локальная БД, используйте:
```javascript
// После парсинга
const sqlite3 = require('sqlite3');
const db = new sqlite3.Database('listings.db');
// Загружайте данные из listings.json в БД
```

📌 **Совет 3:** Можно отправлять уведомления при обновлении:
```javascript
// Отправка на Telegram, Slack и т.д.
// Добавьте в конец скрипта
```

---

## ✨ Готово!

Наслаждайтесь автоматизацией! 🎉

Вопросы? Смотрите `SETUP_INSTRUCTIONS.md` для подробных инструкций.
