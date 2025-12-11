import asyncio
from playwright.async_api import async_playwright
import psycopg2
import re
import random
from datetime import datetime
import os
from dotenv import load_dotenv

# ==========================================
# 1. Configuration & Targets
# ==========================================
# Expanded Target List (Coverage: Ransomware, Hacktivism, Data Sales)
TARGET_ACCOUNTS = [
    "DarkWebInformer", 
    "FalconFeedsio", 
    "DailyDarkWeb", 
    "vxunderground",
    "H4ckManac",       # New: Statistics & Trends
    "SOSIntel"         # New: Deep Web Monitor
]

# .env 파일 활성화 (같은 폴더에 있는 .env를 읽어옴)
load_dotenv()

# 기존의 하드코딩된 부분을 이렇게 변경
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),      # .env에서 가져오되, 없으면 localhost
    "database": os.getenv("DB_NAME", "darkweb_project"),
    "user": os.getenv("DB_USER", "kali_user"),
    "password": os.getenv("DB_PASSWORD")            # 비밀번호는 기본값 없이 필수!
}

# ==========================================
# 2. Helper Functions
# ==========================================
def extract_signals(text):
    """Extract URLs and Hashtags from text"""
    url_pattern = r'(https?://[^\s]+)'
    links = re.findall(url_pattern, text)
    
    hashtag_pattern = r'(#\w+)'
    hashtags = re.findall(hashtag_pattern, text)
    
    return links, hashtags

async def human_scroll(page):
    """Scroll smoothly like a human"""
    for _ in range(random.randint(2, 4)): 
        scroll_amount = random.randint(300, 700)
        await page.mouse.wheel(0, scroll_amount)
        # Random wait after scroll (1~3s)
        await page.wait_for_timeout(random.randint(1000, 3000))

# ==========================================
# 3. Main Logic
# ==========================================
async def run():
    async with async_playwright() as p:
        # Browser Launch Options (Safety Mode)
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-gpu", 
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        # Context Setup (User-Agent, Viewport)
        context = await browser.new_context(
            storage_state="twitter_auth.json", # Load Session
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US", # English Locale
            viewport={"width": 1920, "height": 1080}
        )
        
        # Inject Stealth Script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        page = await context.new_page()

        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
        except Exception as e:
            print(f"[Error] DB Connection failed: {e}")
            await browser.close()
            return

        print("[Start] Starting crawler in safety mode...\n")

        for target in TARGET_ACCOUNTS:
            print(f"[Target] Accessing {target}...")
            
            try:
                # Go to Profile
                await page.goto(f"https://twitter.com/{target}", timeout=60000)
                
                # Random Wait for Loading
                wait_time = random.uniform(3, 6)
                print(f"   L Waiting for loading... ({wait_time:.1f}s)")
                await page.wait_for_timeout(wait_time * 1000)
                
                # Wait for tweets to appear
                try:
                    await page.wait_for_selector("article", timeout=15000)
                except:
                    print(f"   [Skip] Failed to load {target} or no tweets found.")
                    continue

                # Scroll like a human
                await human_scroll(page)

                # Extract Data
                tweets = await page.query_selector_all("article")
                print(f"   [Found] {len(tweets)} tweets found. Starting analysis...")

                saved_count = 0
                for tweet in tweets:
                    try:
                        # Extract Text
                        text_el = await tweet.query_selector('div[data-testid="tweetText"]')
                        if not text_el: continue
                        content = await text_el.inner_text()
                        
                        # Extract Date
                        time_el = await tweet.query_selector('time')
                        post_date = await time_el.get_attribute('datetime') if time_el else str(datetime.now())
                        
                        # Extract Signals (Links/Hashtags)
                        links, tags = extract_signals(content)

                        # Generate Temporary ID
                        temp_id = f"{target}_{post_date}"

                        # Insert into DB
                        cur.execute(
                            """
                            INSERT INTO raw_twitter 
                            (tweet_id, author, content, external_links, hashtags, post_date) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (tweet_id) DO NOTHING
                            """,
                            (temp_id, target, content, links, tags, post_date)
                        )
                        saved_count += 1
                        
                    except Exception as e:
                        continue
                
                conn.commit()
                print(f"   [Saved] {saved_count} tweets saved to DB.")
                
                # Long Rest between accounts
                rest_time = random.uniform(10, 20)
                print(f"   [Rest] Resting for {rest_time:.1f}s before next target...\n")
                await page.wait_for_timeout(rest_time * 1000)

            except Exception as e:
                print(f"   [Error] Error crawling {target}: {e}")

        cur.close()
        conn.close()
        await browser.close()
        print("[Done] All tasks completed.")

if __name__ == "__main__":
    asyncio.run(run())
