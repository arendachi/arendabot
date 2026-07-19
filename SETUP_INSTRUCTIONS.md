# 🤖 Интеграция парсера JoyEstate в arendabot

## Выбор варианта

### Вариант 1️⃣ **Node.js + Puppeteer** (Рекомендуется)
✅ Быстрее  
✅ Меньше памяти  
✅ Легче деплоить  

### Вариант 2️⃣ **Python + Selenium**
✅ Проще настроить  
✅ Больше гибкости  
✅ Легче дебажить  

---

## 📋 Установка (Вариант 1 - Node.js)

### Шаг 1: Клонируем ваш repo
```bash
cd /path/to/arendabot
```

### Шаг 2: Копируем файлы
```bash
# Скрипт парсера
cp scraper_joyestate.js .

# package.json
cp package.json .

# Или обновляем имеющийся package.json добавив зависимости и scripts
```

### Шаг 3: Устанавливаем зависимости
```bash
npm install
```

### Шаг 4: Запускаем парсер
```bash
npm run scrape
```

Данные сохранятся в `data/listings.json`

---

## 📋 Установка (Вариант 2 - Python)

### Шаг 1: Проверяем Python
```bash
python3 --version  # должно быть 3.8+
```

### Шаг 2: Копируем файлы
```bash
cp scraper_joyestate.py .
cp requirements.txt .
```

### Шаг 3: Создаём виртуальное окружение
```bash
python3 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

### Шаг 4: Устанавливаем зависимости
```bash
pip install -r requirements.txt
```

### Шаг 5: Запускаем парсер
```bash
python3 scraper_joyestate.py
```

Данные сохранятся в `data/listings.json`

---

## 🔄 Автоматизация обновления

### Вариант A: Cron для Linux/Mac
```bash
# Открываем crontab
crontab -e

# Добавляем (каждый день в 03:00)
0 3 * * * cd /path/to/arendabot && npm run scrape >> logs/scraper.log 2>&1
```

### Вариант B: GitHub Actions
Создайте файл `.github/workflows/scrape.yml`:

```yaml
name: Daily Scrape

on:
  schedule:
    - cron: '0 3 * * *'  # Каждый день в 03:00

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm run scrape
      - name: Commit changes
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/listings.json
          git commit -m "Update listings: $(date)" || echo "No changes"
          git push
```

### Вариант C: Systemd сервис (Linux)
```bash
# /etc/systemd/system/arendabot-scraper.service
[Unit]
Description=JoyEstate Bot Scraper
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/arendabot
ExecStart=/usr/bin/npm run scrape
User=your_user

[Install]
WantedBy=multi-user.target
```

Запуск по расписанию:
```bash
# /etc/systemd/system/arendabot-scraper.timer
[Unit]
Description=Run JoyEstate Scraper daily
Requires=arendabot-scraper.service

[Timer]
OnCalendar=daily
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

---

## 📁 Структура проекта после интеграции

```
arendabot/
├── scraper_joyestate.js      # Парсер (Node.js)
├── scraper_joyestate.py      # Парсер (Python)
├── package.json              # Зависимости Node.js
├── requirements.txt          # Зависимости Python
├── data/
│   ├── listings.json         # Данные (генерируется)
│   └── listings_backup.json  # Резервная копия
├── logs/
│   └── scraper.log          # Логи
├── .github/
│   └── workflows/
│       └── scrape.yml       # GitHub Actions
└── README.md
```

---

## 🐛 Решение проблем

### Ошибка: "Puppeteer не может найти браузер"
```bash
# Переустанавливаем с явной установкой Chromium
npm install --save puppeteer@latest --no-save
```

### Ошибка: "Chrome не запускается"
Добавьте `--no-sandbox` в опции (уже добавлено в скрипт):
```javascript
args: ['--no-sandbox', '--disable-setuid-sandbox']
```

### Ошибка: "Селектор не найден"
Сайт может изменить структуру HTML. Нужно:
1. Открыть сайт в браузере
2. Нажать F12 (Инспектор)
3. Найти элементы с объявлениями
4. Обновить селекторы в скрипте

### Ошибка Python: "Не найден ChromeDriver"
```bash
# webdriver-manager скачает его автоматически, но если не работает:
pip install --upgrade webdriver-manager
```

---

## 📊 Использование данных

### Чтение данных в Node.js
```javascript
const fs = require('fs');
const listings = JSON.parse(fs.readFileSync('./data/listings.json', 'utf-8'));

listings.forEach(item => {
  console.log(`${item.title} - ${item.price}`);
});
```

### Чтение данных в Python
```python
import json

with open('data/listings.json', 'r', encoding='utf-8') as f:
    listings = json.load(f)

for item in listings:
    print(f"{item['title']} - {item['price']}")
```

### Загрузка в БД
```python
import json
import sqlite3

with open('data/listings.json') as f:
    listings = json.load(f)

conn = sqlite3.connect('listings.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS listings
    (id INTEGER PRIMARY KEY, title TEXT, price TEXT, address TEXT, url TEXT, timestamp TEXT)''')

for item in listings:
    c.execute('INSERT INTO listings VALUES (NULL, ?, ?, ?, ?, ?)',
        (item['title'], item['price'], item['address'], item['url'], item['timestamp']))

conn.commit()
conn.close()
```

---

## 🚀 Деплой

### Heroku
```bash
# Добавляем buildpack для Node.js/Python
heroku buildpacks:add heroku/nodejs

# Добавляем Procfile
echo "web: npm start
release: npm run scrape" > Procfile

# Дeплоим
git push heroku main
```

### Docker
```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

CMD ["npm", "run", "scrape"]
```

---

## 💡 Советы

✅ **Запускайте ночью** - сайт медленнее нагружается днём  
✅ **Сохраняйте резервные копии** - скопируйте данные перед обновлением  
✅ **Проверяйте логи** - смотрите ошибки в логах  
✅ **Тестируйте локально** - перед деплоем на сервер  

---

## 📞 Поддержка

Если есть вопросы - проверьте:
- Открыт ли сайт в браузере?
- Работает ли интернет?
- Правильные ли селекторы?
- Не изменилась ли структура HTML?

**Дебаг:**
```bash
# Добавьте в скрипт:
console.log(process.version);  // Node.js версия
console.log(html.substring(0, 500));  // Первые 500 символов HTML
```

---

Удачи! 🚀
