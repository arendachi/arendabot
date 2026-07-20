const https = require('https');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = path.join(__dirname, 'data');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'listings.json');

// Создаём папку
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

function log(msg, emoji = '📝') {
  console.log(`${emoji} [${new Date().toLocaleTimeString()}] ${msg}`);
}

function makeRequest(url, timeout = 15000) {
  return new Promise((resolve, reject) => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      controller.abort();
      reject(new Error(`Timeout after ${timeout}ms`));
    }, timeout);

    https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      timeout: timeout
    }, (res) => {
      clearTimeout(timer);
      
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode}`));
        res.resume();
        return;
      }

      let data = '';
      res.on('data', chunk => {
        data += chunk;
        if (data.length > 5000000) { // Макс 5MB
          res.destroy();
          reject(new Error('Response too large'));
        }
      });

      res.on('end', () => {
        clearTimeout(timer);
        resolve(data);
      });

      res.on('error', (err) => {
        clearTimeout(timer);
        reject(err);
      });
    }).on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

function parseHTML(html) {
  const listings = [];
  const seen = new Set();

  // Простой парсинг HTML с регексом
  const linkMatches = html.matchAll(/href="([^"]*joyestate[^"]*)"/gi);
  
  for (const match of linkMatches) {
    const url = match[1];
    
    if (seen.has(url) || !url || url.length > 300) continue;
    
    seen.add(url);

    // Пытаемся найти название и цену рядом с ссылкой
    const startIdx = Math.max(0, match.index - 200);
    const endIdx = Math.min(html.length, match.index + 300);
    const context = html.substring(startIdx, endIdx);

    let title = '';
    let price = '';

    // Ищем текст ссылки
    const textMatch = context.match(/>([^<]{5,150})<\/a/);
    if (textMatch) {
      title = textMatch[1].trim().replace(/\s+/g, ' ');
    }

    // Ищем цену
    const priceMatch = context.match(/[\d,]+\s*(сум|sum|сўм|$|usd)/i);
    if (priceMatch) {
      price = priceMatch[0];
    }

    if (title && title.length > 5) {
      listings.push({
        title: title.substring(0, 150),
        price: price || 'Не указана',
        url: url,
        timestamp: new Date().toISOString()
      });
    }

    if (listings.length >= 100) break; // Хватит 100 объявлений
  }

  return listings;
}

async function scrape() {
  try {
    log('🕷️ Запускаю скрейпер...', '🚀');
    log('Версия: FAST SIMPLE (no puppeteer)', '⚡');

    const url = 'https://olmazor.joyestate.uz/';
    
    log(`Загружаю ${url}`, '📥');
    const html = await makeRequest(url, 20000); // 20 сек макс

    log(`HTML загружен: ${(html.length / 1024).toFixed(2)} KB`, '✅');

    log('Парсинг HTML...', '🔍');
    const listings = parseHTML(html);

    log(`Найдено ${listings.length} объявлений`, '📌');

    if (listings.length === 0) {
      log('⚠️ Объявлений не найдено! Возможно сайт изменил структуру', '⚠️');
      
      // Сохраняем пустой файл чтобы не было ошибки
      const empty = { listings: [], timestamp: new Date().toISOString(), error: 'No listings found' };
      fs.writeFileSync(OUTPUT_FILE, JSON.stringify(empty, null, 2));
      process.exit(0);
    }

    // Удаляем дубликаты
    const unique = [];
    const seen = new Set();
    for (const item of listings) {
      if (!seen.has(item.url)) {
        seen.add(item.url);
        unique.push(item);
      }
    }

    log(`Уникальных: ${unique.length}`, '✨');

    // Сохраняем
    fs.writeFileSync(
      OUTPUT_FILE,
      JSON.stringify(unique, null, 2),
      'utf-8'
    );

    log(`✅ Сохранено в ${OUTPUT_FILE}`, '💾');
    log(`ГОТОВО! Всего объявлений: ${unique.length}`, '🎉');

    process.exit(0);

  } catch (error) {
    log(`❌ Ошибка: ${error.message}`, '🚨');
    
    // Сохраняем ошибку в файл
    const errorData = {
      error: error.message,
      listings: [],
      timestamp: new Date().toISOString()
    };
    
    try {
      fs.writeFileSync(OUTPUT_FILE, JSON.stringify(errorData, null, 2));
    } catch (e) {
      // Игнорируем если не удалось
    }

    process.exit(1);
  }
}

// Запуск
log('╔════════════════════════════════════════╗', '');
log('║  🤖 SIMPLE FAST SCRAPER (NO PUPPETEER) ║', '');
log('║  Максимум 100 объявлений за 20 сек    ║', '');
log('╚════════════════════════════════════════╝', '');
log('', '');

scrape();
