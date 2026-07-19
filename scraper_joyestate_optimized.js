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

// Настройки оптимизации
const CONFIG = {
  maxListingsPerFile: 5000, // Разделяем на части по 5000
  timeout: 60000, // 60 сек
  navigationTimeout: 45000,
  headless: 'new',
  maxRetries: 3,
  delayBetweenPages: 2000, // 2 сек между страницами
};

class JoyEstateScraper {
  constructor() {
    this.allListings = [];
    this.browser = null;
    this.page = null;
    this.totalPages = 0;
    this.currentPage = 0;
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
        '--disable-dev-shm-usage', // Для экономии памяти
        '--disable-gpu',
        '--single-process', // Экономит память
      ]
    });

    this.page = await this.browser.newPage();
    
    // Устанавливаем таймауты
    this.page.setDefaultNavigationTimeout(CONFIG.navigationTimeout);
    this.page.setDefaultTimeout(CONFIG.timeout);

    // Устанавливаем User-Agent чтобы сайт не блокировал
    await this.page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    );

    // Отключаем загрузку ненужных ресурсов
    await this.page.on('request', (request) => {
      const resourceType = request.resourceType();
      if (['image', 'stylesheet', 'font'].includes(resourceType)) {
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
      this.log(`Загружаю страницу ${pageNum}...`, '📖');
      
      await this.page.goto(url, { 
        waitUntil: 'networkidle2',
        timeout: CONFIG.navigationTimeout 
      });

      this.log(`Страница ${pageNum} загружена`, '✅');
      return true;
    } catch (error) {
      this.log(`Ошибка при загрузке страницы ${pageNum}: ${error.message}`, '❌');
      return false;
    }
  }

  async getTotalPages() {
    try {
      this.log('Определяю количество страниц...', '🔍');
      
      const totalPages = await this.page.evaluate(() => {
        // Ищем информацию о пагинации
        const paginationText = document.body.innerText;
        
        // Проверяем разные варианты селекторов пагинации
        const pageInfo = document.querySelector('[class*="pagination"]') || 
                        document.querySelector('[class*="page"]') ||
                        document.querySelector('[class*="paging"]');
        
        if (pageInfo) {
          const text = pageInfo.innerText;
          const match = text.match(/(\d+)/g);
          if (match) {
            return Math.max(...match.map(Number));
          }
        }

        // Альтернативный способ: подсчитать объявления
        const listings = document.querySelectorAll('a, div[class*="card"], div[class*="item"]');
        // Примерная оценка: 20 объявлений на страницу
        return Math.ceil(listings.length / 20);
      });

      this.totalPages = Math.min(totalPages || 1, 100); // Макс 100 страниц
      this.log(`Всего страниц: ${this.totalPages}`, '📊');
      return this.totalPages;
    } catch (error) {
      this.log(`Ошибка при определении количества страниц: ${error.message}`, '❌');
      return 1;
    }
  }

  async extractListings() {
    try {
      this.log('Извлекаю объявления...', '🔍');
      
      const listings = await this.page.evaluate(() => {
        const items = [];
        const seen = new Set();

        // Более точные селекторы
        const selectors = [
          'a[href*="/listings/"]',
          'a[href*="/property/"]',
          'div[class*="card"] a',
          'div[class*="listing"] a',
          'div[class*="item"] a',
        ];

        for (const selector of selectors) {
          document.querySelectorAll(selector).forEach((el) => {
            try {
              const title = el.textContent?.trim();
              const href = el.href;

              // Получаем родительский элемент для цены и адреса
              const card = el.closest('div[class*="card"]') || 
                          el.closest('div[class*="listing"]') ||
                          el.closest('[class*="item"]') ||
                          el.parentElement;

              const price = card?.querySelector('[class*="price"], [class*="cost"]')?.textContent;
              const address = card?.querySelector('[class*="address"], [class*="location"]')?.textContent;

              if (title && title.length > 5 && href && !seen.has(href)) {
                seen.add(href);
                items.push({
                  title: title.substring(0, 150),
                  price: price?.trim() || 'Не указана',
                  address: address?.trim() || 'Не указан',
                  url: href,
                  timestamp: new Date().toISOString()
                });
              }
            } catch (e) {
              // Игнорируем ошибки отдельных элементов
            }
          });

          if (items.length > 0) break; // Если нашли - выходим
        }

        return items;
      });

      this.log(`Найдено ${listings.length} объявлений на странице`, '📌');
      return listings;
    } catch (error) {
      this.log(`Ошибка при извлечении: ${error.message}`, '❌');
      return [];
    }
  }

  async saveListings(listings, isFinal = false) {
    if (listings.length === 0) return;

    try {
      // Объединяем с предыдущими
      this.allListings = [...this.allListings, ...listings];

      // Удаляем дубликаты по URL
      const unique = [];
      const seen = new Set();
      for (const item of this.allListings) {
        if (!seen.has(item.url)) {
          seen.add(item.url);
          unique.push(item);
        }
      }
      this.allListings = unique;

      // Сохраняем если конец или достаточно данных
      if (isFinal || this.allListings.length >= CONFIG.maxListingsPerFile) {
        // Создаём резервную копию
        if (fs.existsSync(OUTPUT_FILE)) {
          fs.copyFileSync(OUTPUT_FILE, BACKUP_FILE);
          this.log('Резервная копия создана', '💾');
        }

        // Сохраняем основной файл
        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(this.allListings, null, 2), 'utf-8');
        this.log(`Сохранено ${this.allListings.length} объявлений`, '💾');
      }
    } catch (error) {
      this.log(`Ошибка при сохранении: ${error.message}`, '❌');
    }
  }

  async scrapeAllPages() {
    try {
      await this.initBrowser();

      // Загружаем первую страницу
      const pageLoaded = await this.loadPage(1);
      if (!pageLoaded) throw new Error('Не удалось загрузить первую страницу');

      // Определяем количество страниц
      const totalPages = await this.getTotalPages();

      // Скрейпим все страницы
      for (let page = 1; page <= totalPages; page++) {
        this.currentPage = page;
        this.log(`Обработка страницы ${page}/${totalPages}...`, '📄');

        // Загружаем страницу если не первая
        if (page > 1) {
          const loaded = await this.loadPage(page);
          if (!loaded) {
            this.log(`Пропускаю страницу ${page}`, '⏭️');
            continue;
          }
          await this.page.waitForTimeout(CONFIG.delayBetweenPages); // Задержка между запросами
        }

        // Извлекаем объявления
        const listings = await this.extractListings();
        
        // Сохраняем
        await this.saveListings(listings, page === totalPages);

        // Показываем прогресс
        const progress = Math.round((page / totalPages) * 100);
        this.log(`Прогресс: ${progress}% (${this.allListings.length} объявлений)`, '📈');
      }

      this.log(`\n✨ ГОТОВО! Всего объявлений: ${this.allListings.length}`, '🎉');
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

  async scrapeOptimized() {
    /**
     * Альтернативный способ - если пагинация не работает,
     * используем infinite scroll
     */
    try {
      await this.initBrowser();

      this.log('Загружаю сайт...', '📖');
      await this.page.goto(SITE_URL, { waitUntil: 'networkidle2' });

      this.log('Начинаю infinite scroll...', '📜');

      let previousHeight = 0;
      let scrolls = 0;
      const maxScrolls = 50; // Макс 50 скроллов

      while (scrolls < maxScrolls) {
        // Скроллим
        await this.page.evaluate(() => {
          window.scrollBy(0, window.innerHeight);
        });

        await this.page.waitForTimeout(1000);

        // Проверяем если достигли конца
        const newHeight = await this.page.evaluate(() => document.body.scrollHeight);
        if (newHeight === previousHeight) {
          this.log('Достигнут конец страницы', '🏁');
          break;
        }

        previousHeight = newHeight;
        scrolls++;

        if (scrolls % 10 === 0) {
          this.log(`Скроллов: ${scrolls}`, '📊');
        }
      }

      // Извлекаем все объявления
      const listings = await this.extractListings();
      await this.saveListings(listings, true);

      this.log(`✨ Всего собрано: ${this.allListings.length} объявлений`, '🎉');
      return this.allListings;

    } catch (error) {
      this.log(`Ошибка: ${error.message}`, '❌');
      throw error;
    } finally {
      if (this.browser) {
        await this.browser.close();
      }
    }
  }
}

// Запуск
async function main() {
  console.log(`
╔════════════════════════════════════════╗
║  🤖 JoyEstate Scraper (Optimized)      ║
║  Загрузка всех объявлений              ║
╚════════════════════════════════════════╝
  `);

  const scraper = new JoyEstateScraper();

  try {
    // Пробуем сначала с пагинацией
    await scraper.scrapeAllPages();
  } catch (error) {
    console.log('\n⚠️  Пагинация не сработала, переходу на infinite scroll...\n');
    
    const scraper2 = new JoyEstateScraper();
    try {
      await scraper2.scrapeOptimized();
    } catch (err) {
      console.error('Критическая ошибка:', err);
      process.exit(1);
    }
  }
}

main().then(() => {
  console.log('\n✅ Скрейпинг завершён!');
  process.exit(0);
}).catch(error => {
  console.error('Ошибка:', error);
  process.exit(1);
});
