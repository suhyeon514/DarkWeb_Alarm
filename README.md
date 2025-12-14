# 🕵️ DOTAS v1.3

## Dark-web OSINT Threat Alert System (Tor + OSINT 기반 위협 인텔 자동화)

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat\&logo=python\&logoColor=white)
![Network](https://img.shields.io/badge/Network-Tor%20Onion-7D4698?style=flat\&logo=tor-browser\&logoColor=white)
![Focus](https://img.shields.io/badge/Focus-Threat%20Intelligence-red?style=flat)
![Platform](https://img.shields.io/badge/Platform-Kali%20Linux-blue?style=flat\&logo=linux)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

> **DOTAS는 Tor 기반 `.onion` 인덱스(검색/디렉토리) + clearnet OSINT 소스에서
> IOC(Indicator of Compromise)를 자동 수집하고
> CSV 저장 + Telegram 실시간 경고를 제공하는 경량 Threat Intel 엔진입니다.**

---

# 📌 주요 기능 (Features)

### ✔ 1. Tor 기반 Onion Intelligence 수집

* `.onion` 주소에 직접 접근하여 데이터 수집
* Tor SOCKS5h 프록시 사용 → **DNS까지 Tor 내부에서 처리 (완전한 익명성)**
* 사용 소스:

  * **Ahmia onion 인덱스**
  * **dark.fail onion 디렉토리**

### ✔ 2. OSINT Collector (Clearnet)

* deepdarkCTI GitHub 프로젝트 기반
* 랜섬웨어 그룹 / 텔레그램 위협 행위자 정보 자동 수집

### ✔ 3. IOC 자동 분석

* 이메일 / 도메인 자동 추출 (Regex 기반)
* 키워드 기반 필터링
* HTML → Plain text 변환

### ✔ 4. 중복 알림 방지 (De-duplication)

* 탐지된 IOC는 `seen_indicators.txt`에 기록
* 이미 본 IOC는 Telegram 알림 재발송 없음

### ✔ 5. Telegram 실시간 알림

* Bot API 직접 호출
* 경보 형식으로 즉시 전달
* CSV(`findings.csv`) 자동 업데이트

---

# ⚙ 시스템 아키텍처 (Architecture Diagram)

```text
            +------------------+
            |   DARK WEB       |
            |   (.onion)       |
            +------------------+
       (Tor SOCKS5h: 127.0.0.1:9050)
                      |
                      v
            +------------------+
            |   Collector      |
            | (fetch_url)      |
            +------------------+
                      |
            +--------------------------+
            |      Analyzer            |
            | - HTML -> Text clean     |
            | - Keyword filter         |
            | - Email/Domain extract   |
            +--------------------------+
                      |
        +-------------+--------------+
        |                            |
        v                            v
+-------------------+      +-----------------------+
|   CSV Logger      |      |  Telegram Alert Bot   |
|  findings.csv     |      |  send_telegram()      |
+-------------------+      +-----------------------+
                  |
                  v
         +-----------------------+
         |  seen_indicators.txt  |
         |  (Duplicate Filter)   |
         +-----------------------+
```

---

# 🌐 사용 중인 데이터 소스

## 🧅 Tor 기반 (use_tor = True)

| Source Name                  | URL                                                                      |
| ---------------------------- | ------------------------------------------------------------------------ |
| **Ahmia Onion Search**       | `http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/` |
| **DarkFail Onion Directory** | `http://darkfailenbsdla5mal2mxn2uz66od5vtzd5qozslagrfzachha3f3id.onion/` |

## 🌐 Clearnet OSINT

| Source Name                          | URL                                                                                     |
| ------------------------------------ | --------------------------------------------------------------------------------------- |
| DeepDarkCTI – Ransomware Index       | `https://raw.githubusercontent.com/fastfire/deepdarkCTI/main/ransomware_gang.md`        |
| DeepDarkCTI – Telegram Threat Actors | `https://raw.githubusercontent.com/fastfire/deepdarkCTI/main/telegram_threat_actors.md` |

---

# 📁 디렉토리 구조 (Project Structure)

```text
DOTAS/
│── dotas_v1_3.py        # 메인 실행 파일
│── findings.csv         # 수집된 IOC 로그
│── seen_indicators.txt  # 중복 알림 방지 DB
│── README.md            # 설명 문서
└── requirements.txt     # 패키지 목록
```

---

# 🧩 Requirements (환경 요구사항)

```
Python 3.9+
Tor service (0.4.x 이상)
Linux 계열 환경 권장 (Kali / Ubuntu)
안정적인 인터넷 + SOCKS Proxy 환경
```

필수 패키지:

```text
requests
beautifulsoup4
pysocks
urllib3
python-telegram-bot
```

설치:

```bash
pip install -r requirements.txt
```

---

# 🔧 설치 및 실행 방법

### 1) Tor 설치 및 실행

```bash
sudo apt update
sudo apt install tor -y
sudo service tor start
```

### 2) Telegram 설정

```python
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN_HERE"
CHAT_ID        = "YOUR_CHAT_ID"
```

### 3) 실행

```bash
python3 dotas_v1_3.py
```

---

# 📌 실행 로그 예시 (Example Output)

```text
>> [DOTAS] 다크웹 & OSINT 위협 모니터링 시스템 가동
   - CSV 파일   : findings.csv
   - History 파일: seen_indicators.txt

[Cycle 시작] 2025-12-04 11:20:18
[*] 소스 처리 시작: Ahmia Onion Search (http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/) [TOR=True]
[+] Fetch 성공: ... (size=182034)
[탐지] Ahmia Onion Search에서 domain 발견: leaked-admin-panel.com
🚨 [DOTAS Threat Alert]
Source : Ahmia Onion Search
Type   : domain
Value  : leaked-admin-panel.com
Snippet: ...
------------------------------------
```

---

# 🩺 Troubleshooting (트러블슈팅)

### 1️⃣ `.onion` 접속 실패 (`General SOCKS server failure`)

```bash
sudo systemctl status tor@default
torsocks curl https://check.torproject.org
```

* Tor 데몬 상태 및 네트워크 부트스트랩 여부 확인

### 2️⃣ `Invalid onion site address`

* `.onion` 주소 자체가 종료되었거나 잘못된 경우
* v3 주소(56자)인지 확인 필요

### 3️⃣ 중복 알림이 안 막힐 때

* `seen_indicators.txt` 내용 확인
* 파일 삭제 시, 모든 IOC를 새로 보는 것으로 인식

### 4️⃣ HTML 파싱 문제

* BeautifulSoup의 `.get_text()`로 HTML → 텍스트 변환 중
* 특수 포맷(md, json 등)이 많다면 추가 파서 구현 가능

---

# 📄 License (MIT)

본 프로젝트는 MIT 라이센스를 따릅니다.
누구나 자유롭게 수정 및 재사용할 수 있습니다.

---

# ⚠️ Legal Disclaimer

> DOTAS는 **보안 연구·교육·위협 인텔리전스 학습용**으로 제작되었습니다.
> 무단 크롤링·불법 침투·허가되지 않은 onion/웹 자원 접근은
> 관련 법률에 의해 처벌될 수 있습니다.
>
> 반드시 **본인이 소유한 자산 또는 명확한 허가를 받은 환경에서만** 사용하십시오.
