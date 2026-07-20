const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');

// ⚠️ ЗАМЕНИТЕ НА ВАШЕ ЗНАЧЕНИЕ!
const TOKEN = process.env.TELEGRAM_BOT_TOKEN || 'YOUR_BOT_TOKEN_HERE';

const bot = new TelegramBot(TOKEN, { polling: true });
const DATA_FILE = path.join(__dirname, 'data', 'listings.json');

// Хранилище пользователей и их подписок
const userPreferences = new Map();

console.log('🤖 Telegram бот запускается...');
console.log(`📝 TOKEN: ${TOKEN ? '✅ Установлен' : '❌ НЕ установлен!'}`);

// ========================================
// ФУНКЦИИ
// ========================================

function loadListings() {
  try {
    if (!fs.existsSync(DATA_FILE)) {
      return [];
    }
    const data = fs.readFileSync(DATA_FILE, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    console.error('❌ Ошибка при загрузке данных:', error.message);
    return [];
  }
}

function formatListing(item, index = '') {
  const indexStr = index ? `[${index}] ` : '';
  return `
${indexStr}📍 ${item.title}
💰 Цена: ${item.price}
📍 Адрес: ${item.address}
🔗 ${item.url}
`;
}

function getLatestListings(count = 10) {
  const listings = loadListings();
  return listings.slice(0, count);
}

function searchListings(query) {
  const listings = loadListings();
  const results = listings.filter(item => 
    item.title.toLowerCase().includes(query.toLowerCase()) ||
    item.address.toLowerCase().includes(query.toLowerCase())
  );
  return results.slice(0, 10);
}

// ========================================
// КОМАНДЫ
// ========================================

// /start
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const firstName = msg.chat.first_name || 'Пользователь';

  const welcomeText = `
👋 Добро пожаловать в JoyEstate бот, ${firstName}!

🏠 Я помогу вам найти объявления на joyestate.uz

📋 Доступные команды:
/list - Показать последние 10 объявлений
/top5 - Топ 5 объявлений
/top20 - Топ 20 объявлений
/search <текст> - Поиск по названию
/count - Количество объявлений
/help - Помощь
/subscribe - Подписаться на обновления
/unsubscribe - Отписаться

💡 Пример: /search апартаменты
  `;

  bot.sendMessage(chatId, welcomeText, {
    parse_mode: 'HTML',
    reply_markup: {
      keyboard: [
        [{ text: '📋 Последние 10' }, { text: '🔝 Топ 5' }],
        [{ text: '🔍 Поиск' }],
        [{ text: '📊 Статистика' }]
      ],
      resize_keyboard: true,
      one_time_keyboard: false
    }
  });

  console.log(`✅ /start от ${firstName} (${chatId})`);
});

// /help
bot.onText(/\/help/, (msg) => {
  const chatId = msg.chat.id;
  const helpText = `
🆘 ПОМОЩЬ

📋 /list - Последние 10 объявлений
/top5 - Топ 5
/top20 - Топ 20
/count - Всего объявлений
/search <текст> - Поиск

💬 Просто отправьте текст для поиска

📞 Контакты разработчика:
GitHub: github.com/arendachi/arendabot
Telegram: @ENTRNCEE

🤖 Этот бот автоматически обновляется каждый день в 03:00 UTC
  `;

  bot.sendMessage(chatId, helpText);
});

// /list - Последние 10
bot.onText(/\/list|📋 Последние 10/, (msg) => {
  const chatId = msg.chat.id;
  const listings = getLatestListings(10);

  if (listings.length === 0) {
    bot.sendMessage(chatId, '❌ Нет доступных объявлений');
    return;
  }

  let message = `📋 ПОСЛЕДНИЕ ${listings.length} ОБЪЯВЛЕНИЙ\n\n`;
  listings.forEach((item, index) => {
    message += formatListing(item, index + 1);
    message += '\n' + '─'.repeat(40) + '\n\n';
  });

  bot.sendMessage(chatId, message, { 
    parse_mode: 'HTML',
    disable_web_page_preview: true 
  });

  console.log(`✅ /list от ${msg.chat.id} (${listings.length} объявлений)`);
});

// /top5
bot.onText(/\/top5|🔝 Топ 5/, (msg) => {
  const chatId = msg.chat.id;
  const listings = getLatestListings(5);

  if (listings.length === 0) {
    bot.sendMessage(chatId, '❌ Нет доступных объявлений');
    return;
  }

  let message = `🔝 ТОП 5 ОБЪЯВЛЕНИЙ\n\n`;
  listings.forEach((item, index) => {
    message += formatListing(item, index + 1);
    message += '\n' + '─'.repeat(40) + '\n\n';
  });

  bot.sendMessage(chatId, message, { 
    parse_mode: 'HTML',
    disable_web_page_preview: true 
  });

  console.log(`✅ /top5 от ${msg.chat.id}`);
});

// /top20
bot.onText(/\/top20/, (msg) => {
  const chatId = msg.chat.id;
  const listings = getLatestListings(20);

  if (listings.length === 0) {
    bot.sendMessage(chatId, '❌ Нет доступных объявлений');
    return;
  }

  let message = `🔝 ТОП 20 ОБЪЯВЛЕНИЙ\n\n`;
  listings.forEach((item, index) => {
    message += formatListing(item, index + 1);
    message += '\n' + '─'.repeat(40) + '\n\n';
  });

  // Отправляем по частям если очень длинно
  const maxLength = 4000;
  if (message.length > maxLength) {
    let part = '';
    for (const char of message) {
      part += char;
      if (part.length >= maxLength) {
        bot.sendMessage(chatId, part, { 
          parse_mode: 'HTML',
          disable_web_page_preview: true 
        });
        part = '';
      }
    }
    if (part.length > 0) {
      bot.sendMessage(chatId, part, { 
        parse_mode: 'HTML',
        disable_web_page_preview: true 
      });
    }
  } else {
    bot.sendMessage(chatId, message, { 
      parse_mode: 'HTML',
      disable_web_page_preview: true 
    });
  }

  console.log(`✅ /top20 от ${msg.chat.id}`);
});

// /count - Количество объявлений
bot.onText(/\/count|📊 Статистика/, (msg) => {
  const chatId = msg.chat.id;
  const listings = loadListings();
  
  let priceRange = { min: Infinity, max: 0 };
  listings.forEach(item => {
    const price = parseInt(item.price?.match(/\d+/)?.[0] || 0);
    if (price > 0) {
      priceRange.min = Math.min(priceRange.min, price);
      priceRange.max = Math.max(priceRange.max, price);
    }
  });

  const stats = `
📊 СТАТИСТИКА

📈 Всего объявлений: ${listings.length}
📅 Обновлено: ${new Date().toLocaleString('ru-RU', {timeZone: 'Asia/Tashkent'})}
⏰ Автообновление: 03:00 UTC (05:00 Ташкент)

💰 Диапазон цен:
   Минимум: ${priceRange.min === Infinity ? 'N/A' : priceRange.min}
   Максимум: ${priceRange.max}

🤖 Бот работает автоматически
  `;

  bot.sendMessage(chatId, stats);
  console.log(`✅ /count от ${msg.chat.id}`);
});

// /search - Поиск
bot.onText(/\/search (.+)/, (msg, match) => {
  const chatId = msg.chat.id;
  const query = match[1];
  const results = searchListings(query);

  if (results.length === 0) {
    bot.sendMessage(chatId, `❌ По запросу "${query}" ничего не найдено`);
    return;
  }

  let message = `🔍 РЕЗУЛЬТАТЫ ПОИСКА ПО "${query}"\n(найдено: ${results.length})\n\n`;
  results.forEach((item, index) => {
    message += formatListing(item, index + 1);
    message += '\n' + '─'.repeat(40) + '\n\n';
  });

  bot.sendMessage(chatId, message, { 
    parse_mode: 'HTML',
    disable_web_page_preview: true 
  });

  console.log(`✅ /search "${query}" от ${msg.chat.id} (найдено ${results.length})`);
});

// /subscribe
bot.onText(/\/subscribe/, (msg) => {
  const chatId = msg.chat.id;
  userPreferences.set(chatId, { subscribed: true });

  bot.sendMessage(chatId, `✅ Вы подписались на обновления!\n\nВы будете получать новые объявления каждый день в 03:00 UTC`);
  console.log(`✅ /subscribe от ${chatId}`);
});

// /unsubscribe
bot.onText(/\/unsubscribe/, (msg) => {
  const chatId = msg.chat.id;
  userPreferences.set(chatId, { subscribed: false });

  bot.sendMessage(chatId, `❌ Вы отписались от обновлений`);
  console.log(`❌ /unsubscribe от ${chatId}`);
});

// Обработка обычных сообщений
bot.on('message', (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text?.trim();

  // Пропускаем команды (они обработаны выше)
  if (!text || text.startsWith('/')) {
    return;
  }

  // Поиск по обычному тексту
  const results = searchListings(text);

  if (results.length === 0) {
    bot.sendMessage(chatId, `❌ По запросу "${text}" ничего не найдено\n\nПопробуйте: /search ${text}`);
    return;
  }

  let message = `🔍 НАЙДЕНО ${results.length} РЕЗУЛЬТАТОВ\n\n`;
  results.slice(0, 5).forEach((item, index) => {
    message += formatListing(item, index + 1);
    message += '\n' + '─'.repeat(40) + '\n\n';
  });

  if (results.length > 5) {
    message += `\n📌 Показано 5 из ${results.length}\nИспользуйте /search для полного поиска`;
  }

  bot.sendMessage(chatId, message, { 
    parse_mode: 'HTML',
    disable_web_page_preview: true 
  });

  console.log(`✅ Поиск "${text}" от ${chatId} (найдено ${results.length})`);
});

// Обработка ошибок
bot.on('polling_error', (error) => {
  console.error('❌ Ошибка polling:', error);
});

bot.on('error', (error) => {
  console.error('❌ Ошибка бота:', error);
});

console.log('✅ Бот готов к работе!');
console.log('💬 Отправьте /start в Telegram боте');
