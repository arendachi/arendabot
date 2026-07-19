const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const SITE_URL = 'https://olmazor.joyestate.uz/';
const OUTPUT_FILE = path.join(__dirname, 'data', 'listings.json');

// Создаём папку data если её нет
const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

async function scrapeJoyEstate() {
  console.log('🚀 Запуск парсера JoyEstate...');
  
  let browser;
  try {
    // Запускаем браузер
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    
    // Устанавливаем таймаут
    page.setDefaultNavigationTimeout(30000);
    page.setDefaultTimeout(10000);

    // Переходим на сайт
    console.log('📖 Загружаю страницу...');
    await page.goto(SITE_URL, { waitUntil: 'networkidle2' });

    // Ждём загрузки объявлений
    console.log('⏳ Жду загрузки объявлений...');
    await page.waitForSelector('[class*="card"], [class*="listing"], [class*="item"]', {
      timeout: 15000
    }).catch(() => {
      console.log('⚠️  Селектор не найден, пытаюсь альтернативный...');
    });

    // Скроллим для загрузки больше объявлений
    console.log('📜 Скроллю страницу для загрузки всех данных...');
    let previousHeight = await page.evaluate(() => document.body.scrollHeight);
    
    for (let i = 0; i < 5; i++) {
      await page.evaluate(() => window.scrollBy(0, window.innerHeight));
      await page.waitForTimeout(1000);
      
      let newHeight = await page.evaluate(() => document.body.scrollHeight);
      if (newHeight === previousHeight) break;
      previousHeight = newHeight;
    }

    // Извлекаем данные
    console.log('🔍 Извлекаю данные объявлений...');
    const listings = await page.evaluate(() => {
      const items = [];
      
      // Ищем все возможные элементы с объявлениями
      const elements = document.querySelectorAll('a, div[class*="card"], div[class*="listing"]');
      
      elements.forEach((el) => {
        try {
          const title = el.textContent?.trim();
          const href = el.href || el.getAttribute('href');
          const price = el.querySelector('[class*="price"]')?.textContent;
          const address = el.querySelector('[class*="address"], [class*="location"]')?.textContent;
          
          if (title && title.length > 5) {
            items.push({
              title: title.substring(0, 150),
              price: price?.trim() || 'Не указана',
              address: address?.trim() || 'Не указан',
              url: href || 'N/A',
              timestamp: new Date().toISOString()
            });
          }
        } catch (e) {
          // Игнорируем ошибки парсинга отдельных элементов
        }
      });

      // Удаляем дубликаты
      return [...new Set(items.map(i => JSON.stringify(i)))].map(i => JSON.parse(i));
    });

    // Сохраняем данные
    if (listings.length > 0) {
      fs.writeFileSync(OUTPUT_FILE, JSON.stringify(listings, null, 2), 'utf-8');
      console.log(`✅ Сохранено ${listings.length} объявлений в ${OUTPUT_FILE}`);
    } else {
      console.log('⚠️  Объявления не найдены');
    }

    return listings;

  } catch (error) {
    console.error('❌ Ошибка:', error.message);
    process.exit(1);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

// Запускаем парсер
scrapeJoyEstate().then(() => {
  console.log('✨ Готово!');
  process.exit(0);
});
