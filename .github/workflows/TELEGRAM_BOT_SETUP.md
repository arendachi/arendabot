# 🤖 Telegram Bot для JoyEstate

Telegram бот для получения объявлений из listings.json

## 📋 Требования

- Node.js 14+
- Telegram Bot Token (от @BotFather)

## 🔑 Шаг 1: Получить Token от @BotFather

1. Откройте Telegram
2. Найдите **@BotFather**
3. Отправьте команду: `/newbot`
4. Следуйте инструкциям:
   - Дайте боту имя (например: "JoyEstate Bot")
   - Дайте боту username (например: "joyestate_bot")
5. 📌 **Скопируйте TOKEN** (выглядит: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

## 💻 Шаг 2: Установка локально (для тестирования)

### На Windows:
```bash
# Откройте командную строку
git clone https://github.com/YOUR_USERNAME/arendabot.git
cd arendabot

# Установите зависимости
npm install node-telegram-bot-api

# Запустите бота
set TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE
node telegram_bot.js
```

### На Mac/Linux:
```bash
git clone https://github.com/YOUR_USERNAME/arendabot.git
cd arendabot

npm install node-telegram-bot-api

export TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE
node telegram_bot.js
```

## ☁️ Шаг 3: Запуск на сервере (24/7)

### Вариант A: Heroku (бесплатно)

1. Создайте аккаунт на heroku.com
2. Установите Heroku CLI
3. В папке проекта создайте файл `Procfile`:
```
worker: node telegram_bot.js
```

4. Создайте `runtime.txt`:
```
node-18.x
```

5. Запустите:
```bash
heroku create your-app-name
heroku config:set TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE
git push heroku main
heroku ps:scale worker=1
```

### Вариант B: VPS (Digital Ocean, Linode, etc)

1. SSH на сервер
2. Установите Node.js
3. Скопируйте файлы проекта
4. Установите PM2:
```bash
npm install -g pm2
```

5. Запустите бота:
```bash
TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE pm2 start telegram_bot.js
pm2 startup
pm2 save
```

### Вариант C: GitHub Actions (24/7 на GitHub)

Можно использовать GitHub Actions для запуска бота, но нужно использовать webhook вместо polling.

## 📝 Структура файлов

```
arendabot/
├── telegram_bot.js          # Основной файл бота
├── scraper_joyestate.js     # Парсер данных
├── .github/
│   └── workflows/
│       └── scrape.yml       # GitHub Actions для парсера
├── data/
│   └── listings.json        # Данные объявлений
└── package.json
```

## 🎮 Команды бота

| Команда | Описание |
|---------|---------|
| `/start` | Начать работу |
| `/list` | Показать 10 последних объявлений |
| `/top5` | Топ 5 объявлений |
| `/top20` | Топ 20 объявлений |
| `/search <текст>` | Поиск по названию |
| `/count` | Статистика |
| `/help` | Помощь |
| `/subscribe` | Подписаться на обновления |
| `/unsubscribe` | Отписаться |

Или просто отправьте текст для поиска!

## 🔗 Как объединить с парсером

GitHub Actions парсер каждый день в 03:00 UTC обновляет `listings.json`

Telegram бот читает этот файл и отправляет данные пользователям

## 🐛 Решение проблем

### Бот не отвечает
- Проверьте TOKEN в переменной окружения: `echo $TELEGRAM_BOT_TOKEN`
- Убедитесь что бот запущен: `ps aux | grep telegram_bot.js`
- Проверьте интернет соединение

### "ошибка при загрузке данных"
- Проверьте что файл `data/listings.json` существует
- Запустите парсер: `node scraper_joyestate.js`

### Бот спамит
- Проверьте код в `telegram_bot.js`
- Может быть множественные экземпляры бота работают

## 🚀 Полный процесс

1. **Парсер** (GitHub Actions)
   - Каждый день в 03:00 UTC
   - Собирает объявления
   - Сохраняет в `listings.json`
   - Коммитит в GitHub

2. **Telegram Бот** (VPS/Heroku/Server)
   - Работает 24/7
   - Читает `listings.json` из GitHub
   - Отвечает пользователям в Telegram
   - Отправляет новые объявления

## 📞 Контакты

- GitHub: https://github.com/arendachi/arendabot
- Telegram: @ENTRNCEE

## 📄 Лицензия

MIT
