import psycopg2
from googlesearch import search
import requests
import re
import time
import random
import sys
import os
from dotenv import load_dotenv

# ==========================================
# 1. Configuration
# ==========================================

# .env 파일 활성화 (같은 폴더에 있는 .env를 읽어옴)
load_dotenv()

# 기존의 하드코딩된 부분을 이렇게 변경
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),      # .env에서 가져오되, 없으면 localhost
    "database": os.getenv("DB_NAME", "darkweb_project"),
    "user": os.getenv("DB_USER", "kali_user"),
    "password": os.getenv("DB_PASSWORD")            # 비밀번호는 기본값 없이 필수!
}

# Google Dorks (Search Queries)
DORKS = [
    'site:pastebin.com "password" "gmail.com"',  # Pastebin leaks
    'ext:env "DB_PASSWORD" -git',                # Environment files
    'ext:log "password" "username" -git',        # Log files
    'filetype:xls "password" OR "credential"',   # Excel files
    'intext:"BEGIN RSA PRIVATE KEY" ext:pem'     # Private keys
]

# Regex Patterns for Analysis
PATTERNS = {
    "AWS_ACCESS_KEY": r'AKIA[0-9A-Z]{16}',
    "RRN_KOREA": r'\d{6}[-][1-4]\d{6}',  # Korean Resident Registration Number
    "EMAIL_PASS_COMBO": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\s*[:]\s*\S+', # Email:Password
    "GENERIC_API_KEY": r'(api_key|apikey|secret|token)\s*[:=]\s*["\'][a-zA-Z0-9]{20,}["\']'
}

# User-Agent Header (To mimic a real browser)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# ==========================================
# 2. Helper Functions
# ==========================================

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"[!] Database Connection Failed: {e}")
        sys.exit(1)

def analyze_content(content):
    """
    Scans the content against regex patterns.
    Returns a list of detected risk names.
    """
    findings = []
    for risk_name, pattern in PATTERNS.items():
        if re.search(pattern, content):
            findings.append(risk_name)
    return findings

def save_leak(cursor, title, url, snippet, content, findings, dork):
    """
    Saves verified leaks to the database.
    Handles 'ON CONFLICT' to update existing records.
    """
    try:
        risk_summary = ", ".join(findings)
        
        sql = """
        INSERT INTO google_leaks 
        (title, link, snippet, full_content, has_pii, risk_details, keyword_used, status)
        VALUES (%s, %s, %s, %s, TRUE, %s, %s, 'verified')
        ON CONFLICT (link) DO UPDATE 
        SET risk_details = EXCLUDED.risk_details, 
            has_pii = TRUE,
            crawled_at = CURRENT_TIMESTAMP,
            status = 'verified';
        """
        
        # Handle missing snippet in basic search mode
        if snippet is None:
            snippet = "Collected via generic dorking"

        cursor.execute(sql, (title, url, snippet, content, risk_summary, dork))
        print(f"  [+] SUCCESS: Saved to DB! ({risk_summary})")
        
    except Exception as e:
        print(f"  [!] DB Insert Error: {e}")

# ==========================================
# 3. Main Execution Loop
# ==========================================

def main():
    conn = get_db_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    print("=== Google Leak Hunter Started ===")
    
    for dork in DORKS:
        print(f"\n[*] Searching Dork: {dork}")
        
        try:
            # 1. Perform Google Search
            # 'advanced=True' is removed to fix empty result issues.
            # Returns an iterator of URL strings.
            search_iterator = search(dork, num_results=5)
            
            # Convert iterator to list to check if results exist
            urls = []
            try:
                urls = list(search_iterator)
            except Exception as e:
                print(f"  [!] Error fetching results (Blocked?): {e}")

            if not urls:
                print("  [!] No results found (0 items).")
                print("  -> Possible causes: Google IP Ban or no matches for dork.")
                continue # Skip to next dork

            # 2. Crawl and Analyze
            for url in urls:
                print(f"  [-] Visiting: {url[:60]}...")
                
                title = "Unknown (Fetched via URL)"
                
                try:
                    # Request the page
                    response = requests.get(url, headers=HEADERS, timeout=10)
                    
                    if response.status_code == 200:
                        content = response.text
                        
                        # Analyze content
                        risks_found = analyze_content(content)
                        
                        # Save if risky
                        if risks_found:
                            print(f"  [!] VULNERABILITY DETECTED: {risks_found}")
                            save_leak(cursor, title, url, None, content, risks_found, dork)
                        else:
                            print("  [.] Safe or False Positive (Skipping DB save)")
                            
                    else:
                        print(f"  [x] Connection Failed: Status {response.status_code}")

                except requests.exceptions.SSLError:
                    print("  [x] SSL Error (Skipping)")
                except Exception as e:
                    print(f"  [x] Crawling Error: {e}")

                # Random delay to prevent blocking
                time.sleep(random.uniform(3, 7))

        except Exception as e:
            print(f"[!] Fatal Error in Dork loop: {e}")
            break 

    cursor.close()
    conn.close()
    print("\n=== Scan Finished ===")

if __name__ == "__main__":
    main()
