import time
import requests
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import os

# ==========================================
# 1. Configuration
# ==========================================
# [IMPORTANT] Paste your GitHub Personal Access Token below
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

SEARCH_KEYWORDS = [
    # 1. Whole File Leaks (High Probability)
    "filename:.env DB_HOST",         # .env file containing DB info
    "filename:.npmrc _auth",         # NPM deployment auth key leak
    "filename:docker-compose.yml POSTGRES_PASSWORD", # Hardcoded password in Docker config

    # 2. Key Patterns (Detects values regardless of variable names)
    "AKIAIO JP",                     # AWS Key Pattern (AKIA...)
    "sk_live_",                      # Stripe Live Key (Not test key)
    "xoxb-",                         # Slack Bot Token (Common leak)
    "-----BEGIN RSA PRIVATE KEY-----", # SSH Private Key leak

    # 3. Korean Ecosystem Targets (GitHub blind spots)
    "serviceKey filename:config.js", # Public Data Portal (Hardcoded in JS config)
    "imp_key filename:server",       # I'mport (Payment module) key
    "coolsms_api_key",               # Korean SMS service key
    "naver_client_secret filename:properties", # Java/Spring properties config error
    "kakao_admin_key"                # Kakao Admin Key
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
# 2. Main Logic (Stability Enhanced Version)
# ==========================================
def scan_github_final():
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
    except Exception as e:
        print(f"[Fatal Error] DB Connection failed: {e}")
        return

    print("[*] Starting GitHub Scanner (Final Stable Mode)...\n")

    for keyword in SEARCH_KEYWORDS:
        try:
            print(f"[Search] Query: '{keyword}'")
            
            # API Request
            url = "https://api.github.com/search/code"
            params = { "q": keyword, "sort": "indexed", "order": "desc", "per_page": 10 }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code in [403, 429]:
                print(f"[!] Rate Limit! Waiting 60s...")
                time.sleep(60)
                continue
            elif response.status_code != 200:
                print(f"[!] API Error: {response.status_code}")
                continue

            items = response.json().get("items", [])
            print(f"   L Found {len(items)} items.")

            for item in items:
                try:
                    repo_name = item["repository"]["full_name"]
                    file_path = item["path"]
                    html_url = item["html_url"]
                    
                    # Duplicate Check
                    cur.execute("SELECT id FROM raw_github WHERE file_url = %s", (html_url,))
                    if cur.fetchone():
                        print(f"   [Skip] Already exists: {repo_name}")
                        continue
                    
                    # Fetch Raw Content
                    # Convert HTML URL to Raw URL to get the actual code text
                    raw_url = item.get("html_url").replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                    code_res = requests.get(raw_url, timeout=5)
                    snippet = code_res.text[:1000] if code_res.status_code == 200 else "[Fail]"

                    # Save to DB
                    cur.execute(
                        """
                        INSERT INTO raw_github 
                        (keyword, repo_name, file_path, file_url, code_snippet, author_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (keyword, repo_name, file_path, html_url, snippet, item["repository"]["owner"]["login"])
                    )
                    conn.commit() # Commit on success
                    print(f"   [+] SAVED: {repo_name}")
                    time.sleep(1)

                except Exception as file_e:
                    # ★ Critical Fix: Rollback transaction on error
                    conn.rollback() 
                    print(f"   [-] DB Error (Rolled back): {file_e}")
                    time.sleep(1)

            print(f"   L Resting 5 seconds...\n")
            time.sleep(5)

        except Exception as e:
            # Rollback on outer loop error
            conn.rollback()
            print(f"[Error] {e}")
            time.sleep(5)

    cur.close()
    conn.close()
    print("\n[Done] Scan completed.")

if __name__ == "__main__":
    scan_github_final()
