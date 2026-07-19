const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const SITE_URL = 'https://olmazor.joyestate.uz/';
const OUTPUT_DIR = path.join(__dirname, 'data');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'listings.json');
const BACKUP_FILE = path.join(OUTPUT_DIR, 'listings_backup.json');

// Создаём папку data если её нет
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// ОПТИМИЗИРОВАННЫЕ настройки для GitHub Actions
const CONFIG = {
  maxListingsToCollect: 1000, // Собираем максимум 1000 объявлений
  maxPagesToScrape: 10, // Только 10 страниц вместо всех
  timeout: 30000, // 30 сек на операцию
  navigationTimeout: 30000,
  headless: 'new',
  delayBetweenPages: 500, // 500ms вместо 2 сек
  maxConcurrentRequests: 3,
};

class JoyEstateScraper {
  constructor() {
    this.allListings = [];
    this.browser = null;
    this.page = null;
  }

  log(message, emoji = '📝') {
    console.log(`${emoji} ${new Date().toLocaleTimeString()} - ${message}`);
  }

  async initBrowser() {
    this.log('Запускаю браузер...', '🚀');
    this.browser = await puppeteer.launch({
      headless: CONFIG.headless,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--single-process',
        '--disable-extensions',
        '--disable-plugins',
        '--disable-images', // ОТКЛЮЧАЕМ КАРТИНКИ
      ]
    });

    this.page = await this.browser.newPage();
    this.page.setDefaultNavigationTimeout(CONFIG.navigationTimeout);
    this.page.setDefaultTimeout(CONFIG.timeout);

    // User-Agent для избежания блокировки
    await this.page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    );

    // АГРЕССИВНО блокируем ненужные ресурсы
    await this.page.on('request', (request) => {
      const resourceType = request.resourceType();
      const url = request.url();
      
      // Блокируем: картинки, стили, шрифты, медиа, трекеры
      if (['image', 'stylesheet', 'font', 'media', 'xhr', 'fetch'].includes(resourceType) ||
          url.includes('google') || url.includes('analytics') || url.includes('ads')) {
        request.abort();
      } else {
        request.continue();
      }
    });

    this.log('Браузер запущен', '✅');
  }

  async loadPage(pageNum = 1) {
    try {
      const url = pageNum === 1 ? SITE_URL : `${SITE_URL}?page=${pageNum}`;
      
      await this.page.goto(url, { 
        waitUntil: 'domcontentloaded', // БЫСТРЕЕ чем networkidle2
        timeout: CONFIG.navigationTimeout 
      });

      return true;
    } catch (error) {
      this.log(`Ошибка на странице ${pageNum}: ${error.message}`, '❌');
      return false;
    }
  }

  async extractListings() {
    try {
      const listings = await this.page.evaluate(() => {
        const items = [];
        const seen = new Set();

        // Ищем все ссылки на объявления
        const links = document.querySelectorAll('a');
        
        for (const link of links) {
          try {
            const title = link.textContent?.trim();
            const href = link.href;

            // Пропускаем если это ссылка на сайт или не содержит полезной информации
            if (!title || title.length < 5 || !href || 
                !href.includes('joyestate') || seen.has(href)) {
              continue;
            }

            // Получаем информацию из родительского элемента
            const card = link.closest('div');
            let price = '';
            let address = '';

            if (card) {
              const textContent = card.textContent;
              const priceMatch = textContent.match(/[\d,]+\s*(сум|$|usd)/i);
              price = priceMatch ? priceMatch[0] : '';
              
              // Пытаемся извлечь адрес
              const addressEl = card.querySelector('[class*="address"], [class*="location"]');
              address = addressEl?.textContent?.trim() || '';
            }

            if (title.length > 300) continue; // Пропускаем длинные заголовки

            seen.add(href);
            items.push({
              title: title.substring(0, 150),
              price: price || 'Не указана',
              address: address.substring(0, 100) || 'Не указан',
              url: href,
              timestamp: new Date().toISOString()
            });
          } catch (e) {
            // Продолжаем
          }
        }

        return items;
      });

      return listings;
    } catch (error) {
      this.log(`Ошибка при извлечении: ${error.message}`, '❌');
      return [];
    }
  }

  async saveListings(listings) {
    if (listings.length === 0) return;

    try {
      // Добавляем новые объявления
      this.allListings = [...this.allListings, ...listings];

      // Удаляем дубликаты
      const unique = [];
      const seen = new Set();
      
      for (const item of this.allListings) {
        if (!seen.has(item.url)) {
          seen.add(item.url);
          unique.push(item);
        }
      }

      // Ограничиваем до максимума
      this.allListings = unique.slice(0, CONFIG.maxListingsToCollect);

      // Создаём резервную копию
      if (fs.existsSync(OUTPUT_FILE)) {
        fs.copyFileSync(OUTPUT_FILE, BACKUP_FILE);
      }

      // Сохраняем
      fs.writeFileSync(
        OUTPUT_FILE, 
        JSON.stringify(this.allListings, null, 2), 
        'utf-8'
      );

      this.log(`Сохранено ${this.allListings.length} объявлений`, '💾');
    } catch (error) {
      this.log(`Ошибка при сохранении: ${error.message}`, '❌');
    }
  }

  async scrape() {
    try {
      await this.initBrowser();

      this.log('Начинаю скрейпинг...', '🕷️');

      // Загружаем страницы
      for (let page = 1; page <= CONFIG.maxPagesToScrape; page++) {
        // Проверяем если собрали достаточно
        if (this.allListings.length >= CONFIG.maxListingsToCollect) {
          this.log(`Собрано ${this.allListings.length} объявлений - хватает!`, '✅');
          break;
        }

        this.log(`Страница ${page}/${CONFIG.maxPagesToScrape}...`, '📄');

        // Загружаем страницу
        const loaded = await this.loadPage(page);
        if (!loaded && page > 1) {
          this.log(`Все страницы обработаны`, '🏁');
          break;
        }

        // Небольшая задержка для загрузки контента
        await this.page.waitForTimeout(500);

        // Извлекаем объявления
        const listings = await this.extractListings();
        this.log(`Найдено ${listings.length} на странице ${page}`, '📌');

        // Сохраняем
        await this.saveListings(listings);

        // Задержка между страницами
        await this.page.waitForTimeout(CONFIG.delayBetweenPages);
      }

      this.log(`✨ ГОТОВО! Всего: ${this.allListings.length} объявлений`, '🎉');
      return this.allListings;

    } catch (error) {
      this.log(`Критическая ошибка: ${error.message}`, '🚨');
      throw error;
    } finally {
      if (this.browser) {
        await this.browser.close();
        this.log('Браузер закрыт', '🛑');
      }
    }
  }
}

// Запуск
async function main() {
  console.log(`
╔═══════════════════════════════════════════════╗
║  🤖 JoyEstate Scraper (FAST OPTIMIZED)        ║
║  ⚡ Быстрая версия для GitHub Actions         ║
║  Макс: ${CONFIG.maxPagesToScrape} страниц, ${CONFIG.maxListingsToCollect} объявлений   ║
╚═══════════════════════════════════════════════╝
  `);

  const scraper = new JoyEstateScraper();

  try {
    await scraper.scrape();
    console.log('\n✅ Скрейпинг успешно завершён!');
    process.exit(0);
  } catch (error) {
    console.error('\n❌ Критическая ошибка:', error.message);
    process.exit(1);
  }
}

main();
