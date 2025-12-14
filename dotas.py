#!/usr/bin/env python3
"""
DOTAS v1.3
(Dark-web OSINT Threat Alert System)

기능:
- Tor 프록시(socks5h)를 이용해 다크웹(.onion) 인덱스 + 일반 OSINT 소스 수집
- 텍스트에서 이메일/도메인 인디케이터 추출
- 관심 키워드 기반 필터링
- CSV로 탐지 내역 저장
- Telegram 봇으로 실시간 알림 전송
- seen_indicators.txt로 중복 알림 방지

주의:
- 보안 연구/방어 목적 외의 용도로 사용 금지
- 실제 운영 시에는 합법적인 범위의 소스와 키워드만 사용해야 함
"""

import requests
import time
import csv
import os
import re
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import urllib3

# SSL 경고 숨기기 (verify=False 사용 시 콘솔 깨끗하게)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================
# 1. 기본 설정
# ==========================

# [중요] 텔레그램 봇 설정
# - BotFather 에서 받은 토큰
# - @userinfobot 이 알려주는 본인 chat_id
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN_HERE"
CHAT_ID = "YOUR_CHAT_ID_HERE"  # 숫자 형태 문자열

# Tor SOCKS5 프록시 설정 (Kali: sudo service tor start 필수)
TOR_PROXIES = {
    "http": "socks5h://127.0.0.1:9050",
    "https": "socks5h://127.0.0.1:9050",
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"
}

# 관심 키워드 (본인/조직에 맞게 수정)
WATCH_KEYWORDS = [
    "example.com",
    "password",
    "leak",
    "admin",
    "internal",
]

# ─────────────────────
# 다크웹 인덱스 / 디렉토리 (Tor 필수)
# ─────────────────────
DARKWEB_SOURCES = [
    {
        # Ahmia 공식 onion (ahmia.fi에서 경고와 함께 안내하는 v3 주소)
        "name": "Ahmia Onion Search",
        "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/",
        "use_tor": True,
    },
    {
        # dark.fail: clearnet에서 직접 공개한 onion 주소
        "name": "DarkFail Onion Directory",
        "url": "http://darkfailenbsdla5mal2mxn2uz66od5vtzd5qozslagrfzachha3f3id.onion/",
        "use_tor": True,
    },
]

# ─────────────────────
# 일반 OSINT 소스 (clearnet)
# ─────────────────────
OSINT_SOURCES = [
    {
        "name": "DeepDarkCTI Ransomware Index",
        "url": "https://raw.githubusercontent.com/fastfire/deepdarkCTI/main/ransomware_gang.md",
        "use_tor": False,
    },
    {
        "name": "DeepDarkCTI Telegram Threat Actors",
        "url": "https://raw.githubusercontent.com/fastfire/deepdarkCTI/main/telegram_threat_actors.md",
        "use_tor": False,
    },
]

OUTPUT_CSV = "findings.csv"
HISTORY_FILE = "seen_indicators.txt"  # 중복 알림 방지용


# ==========================
# 2. 텔레그램 알림
# ==========================

def send_telegram_alert(msg: str) -> None:
    """
    Telegram 봇으로 메시지 전송.
    토큰이 기본값이면 (설정 안 했으면) 콘솔 출력만 하고 스킵.
    """
    if TELEGRAM_TOKEN.startswith("YOUR_") or CHAT_ID.startswith("YOUR_"):
        print("\n[텔레그램 비활성화 모드]")
        print(msg)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    try:
        res = requests.post(url, data=data, timeout=5)
        if res.status_code != 200:
            print(f"[!] 텔레그램 전송 실패 (status={res.status_code})")
    except Exception as e:
        print(f"[!] 텔레그램 전송 예외: {e}")


# ==========================
# 3. 중복 알림 방지
# ==========================

def is_new_indicator(indicator: str) -> bool:
    """이미 알림 보낸 인디케이터인지 확인"""
    if not os.path.exists(HISTORY_FILE):
        return True
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        seen = f.read().splitlines()
    return indicator not in seen


def mark_as_seen(indicator: str) -> None:
    """알림 보낸 인디케이터를 기록"""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(indicator + "\n")


# ==========================
# 4. HTTP 수집
# ==========================

def fetch_url(url: str, use_tor: bool = False, timeout: int = 30) -> Optional[str]:
    """
    URL에서 텍스트 데이터를 가져오는 함수.
    use_tor=True 이면 Tor SOCKS5 프록시 사용.
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    proxies = TOR_PROXIES if use_tor else None

    try:
        res = session.get(url, proxies=proxies, timeout=timeout, verify=False)
        if res.status_code == 200:
            print(f"[+] Fetch 성공: {url} (size={len(res.text)})")
            return res.text
        else:
            print(f"[!] Fetch 실패: {url} (status={res.status_code})")
            return None
    except Exception as e:
        print(f"[!] Fetch 예외: {url} -> {e}")
        if use_tor:
            print("    - Tor 서비스가 실행 중인지(sudo service tor start) 확인하세요.")
        return None


# ==========================
# 5. 인디케이터 추출 및 필터
# ==========================

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9_.-]+\.[a-zA-Z0-9_.-]+")
DOMAIN_REGEX = re.compile(r"\b([a-zA-Z0-9-]{4,}\.[a-zA-Z]{2,})\b")


def extract_indicators(text: str) -> Dict[str, List[str]]:
    """
    텍스트에서 이메일 / 도메인을 추출.
    """
    emails = set(EMAIL_REGEX.findall(text))
    domains = set(DOMAIN_REGEX.findall(text))

    return {
        "emails": list(emails),
        "domains": list(domains),
    }


def filter_by_keywords(text: str, keywords: List[str]) -> bool:
    """텍스트에 관심 키워드가 하나라도 포함되어 있는지 확인"""
    lowered = text.lower()
    for kw in keywords:
        if kw.lower() in lowered:
            return True
    return False


def get_snippet(text: str, indicator: str, window: int = 60) -> str:
    """인디케이터 주변 문맥 일부 추출 (snippet)"""
    lowered_text = text.lower()
    lowered_indicator = indicator.lower()
    idx = lowered_text.find(lowered_indicator)
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(indicator) + window)
    return text[start:end].replace("\n", " ").strip()


# ==========================
# 6. CSV 초기화/저장
# ==========================

def init_csv(path: str) -> None:
    """CSV 파일이 없으면 헤더 생성"""
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "source", "type", "indicator", "snippet"])


def save_finding(path: str,
                 source: str,
                 i_type: str,
                 indicator: str,
                 snippet: str) -> None:
    """탐지 결과 한 건을 CSV에 저장"""
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.utcnow().isoformat(), source, i_type, indicator, snippet])


# ==========================
# 7. 소스 처리 로직
# ==========================

def process_source(source: Dict, keywords: List[str]) -> None:
    """
    단일 소스 처리:
    - URL fetch
    - HTML → 텍스트 변환
    - 키워드 필터
    - 이메일/도메인 추출
    - 키워드 연관 인디케이터만 알림/저장
    """
    name = source["name"]
    url = source["url"]
    use_tor = source.get("use_tor", False)

    print(f"\n[*] 소스 처리 시작: {name} ({url}) [TOR={use_tor}]")

    raw = fetch_url(url, use_tor=use_tor)
    if not raw:
        print(f"[-] {name}: 데이터 없음 또는 실패, 스킵.")
        return

    # HTML/Markdown → 텍스트 정제
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator="\n")

    # 1차 필터: 텍스트에 관심 키워드가 하나도 없으면 스킵
    if not filter_by_keywords(text, keywords):
        print(f"[-] {name}: 관심 키워드 미발견, 스킵.")
        return

    indicators = extract_indicators(text)

    # 이메일 + 도메인을 하나의 리스트로 묶어서 처리
    all_found = []
    for email in indicators["emails"]:
        all_found.append(("email", email))
    for domain in indicators["domains"]:
        all_found.append(("domain", domain))

    for i_type, value in all_found:
        # 인디케이터 값 자체에도 키워드가 포함되어 있는지 추가 확인
        if not any(kw.lower() in value.lower() for kw in keywords):
            continue

        # 새 인디케이터인지 확인
        if not is_new_indicator(value):
            print(f"[중복] {name}: 이미 처리한 인디케이터: {value}")
            continue

        snippet = get_snippet(text, value)
        log_msg = f"[탐지] {name}에서 {i_type} 발견: {value}"
        print(log_msg)

        # CSV 저장
        save_finding(OUTPUT_CSV, name, i_type, value, snippet)

        # 텔레그램 알림 메시지 구성
        alert_msg = (
            "🚨 [DOTAS Threat Alert]\n"
            f"Source : {name}\n"
            f"Type   : {i_type}\n"
            f"Value  : {value}\n"
            f"Snippet: {snippet[:200]}..."
        )
        send_telegram_alert(alert_msg)

        # 중복 방지를 위해 기록
        mark_as_seen(value)


# ==========================
# 8. 메인 루프
# ==========================

def main_loop(interval_sec: int = 300) -> None:
    """
    전체 소스를 주기적으로 모니터링하는 메인 루프.
    interval_sec: 한 사이클 끝난 후 대기 시간 (초)
    """
    print(">> [DOTAS] 다크웹 & OSINT 위협 모니터링 시스템 가동")
    print(f"   - CSV 파일   : {OUTPUT_CSV}")
    print(f"   - History 파일: {HISTORY_FILE}")
    print(f"   - Interval    : {interval_sec}초\n")

    init_csv(OUTPUT_CSV)

    all_sources = DARKWEB_SOURCES + OSINT_SOURCES

    try:
        while True:
            print(f"\n[Cycle 시작] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            for src in all_sources:
                process_source(src, WATCH_KEYWORDS)
                time.sleep(2)  # 소스 간 간단한 딜레이 (예의 + 부하 방지)

            print(f"[Cycle 종료] 대기 {interval_sec}초...\n")
            time.sleep(interval_sec)

    except KeyboardInterrupt:
        print("\n[!] 사용자 종료 요청. DOTAS 종료.")


if __name__ == "__main__":
    # 예: 300초(5분)마다 전체 소스 재검사
    main_loop(interval_sec=300)
