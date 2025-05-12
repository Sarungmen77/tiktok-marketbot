
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests
import schedule
import time
import csv
from datetime import datetime
import os
import re
from collections import defaultdict
import pandas as pd

# Token dan chat_id pengguna
BOT_TOKEN = '7279588943:AAENa5zL4bhPsQJFtxKD93MYreFqQHHthQQ'
CHAT_ID = '6047349188'

CSV_FILE = 'log_trending_tiktok.csv'
EXCEL_FILE = 'log_trending_tiktok.xlsx'

def parse_price(text):
    text = text.replace('Rp', '').replace('.', '').replace(',', '').strip()
    return int(re.findall(r'\d+', text)[0]) if text else 0

def parse_sold(text):
    text = text.lower()
    if 'rb' in text:
        return int(float(text.replace('rb', '').strip()) * 1000)
    elif 'jt' in text:
        return int(float(text.replace('jt', '').strip()) * 1_000_000)
    else:
        return int(re.findall(r'\d+', text)[0]) if re.findall(r'\d+', text) else 0

def get_creator_name(product_url, playwright):
    try:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(product_url, timeout=60000)
        page.wait_for_timeout(5000)
        html = page.content()
        browser.close()
        soup = BeautifulSoup(html, 'html.parser')
        creator_tag = soup.find('a', attrs={'data-e2e': 'store-name'})
        if not creator_tag:
            creator_tag = soup.find('a', class_='tiktok-t7d3y0-ALink')
        return creator_tag.get_text(strip=True) if creator_tag else 'Tidak diketahui'
    except:
        return 'Tidak diketahui'

def get_trending_products():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.tiktok.com/shop/trending", timeout=60000)
        page.wait_for_timeout(8000)
        html = page.content()
        browser.close()

        soup = BeautifulSoup(html, 'html.parser')
        products = []
        items = soup.select('a[data-e2e="product-item"]')
        for item in items[:5]:
            title = item.select_one('[data-e2e="product-name"]')
            price = item.select_one('[data-e2e="product-price"]')
            sold = item.select_one('[data-e2e="product-sold"]')
            link = item['href']
            if title and price and sold:
                full_link = f"https://www.tiktok.com{link}" if link.startswith("/") else link
                creator = get_creator_name(full_link, p)
                price_int = parse_price(price.text)
                sold_int = parse_sold(sold.text)
                gmv = price_int * sold_int
                products.append({
                    'timestamp': datetime.now().isoformat(),
                    'title': title.text.strip(),
                    'price': price.text.strip(),
                    'sold': sold.text.strip(),
                    'creator': creator,
                    'gmv': gmv,
                    'link': full_link
                })
        return products

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=data)

def log_to_csv_and_excel(products):
    df = pd.DataFrame(products)

    # Simpan ke CSV
    if os.path.exists(CSV_FILE):
        df.to_csv(CSV_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(CSV_FILE, index=False)

    # Simpan/append ke Excel
    if os.path.exists(EXCEL_FILE):
        existing_df = pd.read_excel(EXCEL_FILE)
        combined_df = pd.concat([existing_df, df], ignore_index=True)
        combined_df.to_excel(EXCEL_FILE, index=False)
    else:
        df.to_excel(EXCEL_FILE, index=False)

def job():
    products = get_trending_products()
    if not products:
        send_telegram_message("❌ Gagal mengambil data trending TikTok.")
        return

    msg = "🔥 <b>Produk Trending TikTok Hari Ini:</b>\n\n"
    for p in products:
        msg += f"🛍️ <b>{p['title']}</b>\n💰 {p['price']} | {p['sold']}\n👤 {p['creator']}\n🔗 {p['link']}\n\n"

    gmv_per_creator = defaultdict(int)
    for p in products:
        gmv_per_creator[p['creator']] += p['gmv']

    msg += "\n💸 <b>GMV Creator Hari Ini:</b>\n"
    for creator, total_gmv in sorted(gmv_per_creator.items(), key=lambda x: x[1], reverse=True):
        msg += f"👤 {creator}: Rp {total_gmv:,.0f}\n"

    send_telegram_message(msg)
    log_to_csv_and_excel(products)

# Jadwal harian
schedule.every().day.at("09:00").do(job)

print("Bot berjalan... (CTRL+C untuk berhenti)")
while True:
    schedule.run_pending()
    time.sleep(60)
