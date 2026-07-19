#!/usr/bin/env python3
"""
Парсер для сайта JoyEstate (olmazor.joyestate.uz)
Требует: pip install selenium beautifulsoup4 webdriver-manager
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

SITE_URL = 'https://olmazor.joyestate.uz/'
OUTPUT_DIR = Path(__file__).parent / 'data'
OUTPUT_FILE = OUTPUT_DIR / 'listings.json'

def create_driver():
    """Создаём Selenium драйвер"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def scroll_page(driver, scrolls=5):
    """Скроллим страницу для загрузки всех объявлений"""
    print("📜 Скроллю страницу...")
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(1)

def extract_listings(html):
    """Извлекаем объявления из HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    listings = []
    
    # Ищем все ссылки и элементы с информацией об аренде
    links = soup.find_all('a', recursive=True)
    
    for link in links:
        try:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            
            # Фильтруем нерелевантные ссылки
            if len(text) < 5 or not text:
                continue
            
            # Ищем цену и адрес неподалеку
            parent = link.find_parent('div')
            price = 'N/A'
            address = 'N/A'
            
            if parent:
                price_elem = parent.find(string=lambda x: x and ('сум' in x.lower() or '₽' in x))
                if price_elem:
                    price = price_elem.strip()
                
                address_elem = parent.find(class_=['address', 'location', 'region'])
                if address_elem:
                    address = address_elem.get_text(strip=True)
            
            listings.append({
                'title': text[:150],
                'price': price,
                'address': address,
                'url': href[:200] if href else 'N/A',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            continue
    
    # Удаляем дубликаты
    unique_listings = []
    seen = set()
    for item in listings:
        key = (item['title'], item['price'], item['address'])
        if key not in seen:
            seen.add(key)
            unique_listings.append(item)
    
    return unique_listings

def main():
    print("🚀 Запуск парсера JoyEstate...")
    print(f"🌐 Сайт: {SITE_URL}")
    
    # Создаём папку для данных
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    driver = None
    try:
        print("🔧 Запускаю браузер...")
        driver = create_driver()
        
        print("📖 Загружаю страницу...")
        driver.get(SITE_URL)
        
        # Ждём загрузки контента
        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except:
            print("⚠️  Таймаут ожидания, продолжаю...")
        
        # Скроллим для загрузки больше данных
        scroll_page(driver, scrolls=5)
        
        # Получаем HTML
        print("🔍 Извлекаю данные...")
        html = driver.page_source
        
        # Парсим объявления
        listings = extract_listings(html)
        
        if listings:
            # Сохраняем
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(listings, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Сохранено {len(listings)} объявлений")
            print(f"📁 Файл: {OUTPUT_FILE}")
            
            # Показываем примеры
            print("\n📋 Примеры объявлений:")
            for i, item in enumerate(listings[:3], 1):
                print(f"{i}. {item['title'][:50]}")
                print(f"   Цена: {item['price']}")
                print(f"   Адрес: {item['address']}\n")
        else:
            print("⚠️  Объявления не найдены")
        
        return len(listings)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 0
    finally:
        if driver:
            driver.quit()

if __name__ == '__main__':
    try:
        count = main()
        print("\n✨ Готово!")
        sys.exit(0 if count > 0 else 1)
    except KeyboardInterrupt:
        print("\n⛔ Прервано пользователем")
        sys.exit(1)
