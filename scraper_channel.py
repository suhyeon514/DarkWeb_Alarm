import os
import random
import asyncio
from datetime import timedelta

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
import psycopg2
import socks

# ============== 설정 ==============
CHANNEL_NAME_FILE = "channel_name.txt"

# .env 파일 정보 로드
load_dotenv() 

# Telegram API
api_id = int(os.environ["TG_API_ID"])
api_hash = os.environ["TG_API_HASH"]

# PostgreSQL 연결 정보
PG_CONFIG = dict(
    host=os.environ.get("PG_HOST", "localhost"),
    port=int(os.environ.get("PG_PORT", 5432)),
    dbname=os.environ.get("PG_DB", "postgres"),
    user=os.environ.get("PG_USER", "postgres"),
    password=os.environ.get("PG_PASSWORD", ""),
)

# 모드: event | poll | hybrid
CRAWL_MODE = os.environ.get("CRAWL_MODE", "event").strip().lower()
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))          # poll 주기(초)
CATCHUP_INTERVAL = int(os.environ.get("CATCHUP_INTERVAL", "300"))   # hybrid 보정 주기(초)

# 컨테이너 최초 실행 시 채널별 최근 메시지 몇 개 저장할지(.env)
RECENT_MESSAGE_LIMIT_AT_FIRST = int(os.environ.get("RECENT_MESSAGE_LIMIT_AT_FIRST", "10"))

# ============== 프록시 ==============
"""프록시 목록 파싱 (없으면 빈 리스트) => 사실 이 부분은 데이터를 너무 많이 한 번에 들고 오면 api 거부 당해서 proxy 를 여러개를 만들어서 크롤링을 여유롭게 할 수 있었으면 했음"""
def parse_proxies(env_value: str):
    proxies = []
    if not env_value:
        return proxies

    # 형식: host:port 또는 host:port:user:pass 를 ,로 여러 개
    for item in env_value.split(","):
        item = item.strip()
        if not item:
            continue

        parts = item.split(":")
        if len(parts) == 2:
            host, port = parts
            proxies.append(
                dict(proxy_type=socks.SOCKS5, addr=host, port=int(port), rdns=True)
            )
        elif len(parts) == 4:
            host, port, username, password = parts
            proxies.append(
                dict(
                    proxy_type=socks.SOCKS5,
                    addr=host,
                    port=int(port),
                    username=username,
                    password=password,
                    rdns=True,
                )
            )
    return proxies

PROXY_LIST = parse_proxies(os.environ.get("TG_PROXIES", ""))

def choose_proxy():
    if not PROXY_LIST:
        return None
    proxy = random.choice(PROXY_LIST)
    print(f"[INFO] 선택된 프록시: {proxy['addr']}:{proxy['port']}")
    return proxy

proxy = choose_proxy()

SESSION_PATH = os.environ.get("TG_SESSION_PATH", "/app/sessions/anon")

if proxy:
    client = TelegramClient(SESSION_PATH, api_id, api_hash, proxy=proxy)
else:
    client = TelegramClient(SESSION_PATH, api_id, api_hash)


# ============== 유틸 ==============

#Telegram 채널들 중에서 추출하고 싶은 채널 작성한 channel_name.txt 에서 정보 가져 오기
def load_channel_names(path: str):
    names = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if not name or name.startswith("#"):
                continue
            names.append(name)
    return names

def db_insert_row(row):
    """
    psycopg2는 동기 I/O라 이벤트 루프를 막을 수 있음.
    그래서 asyncio.to_thread로 이 함수를 thread에서 실행.
    """
    conn = psycopg2.connect(**PG_CONFIG)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.raw_telegram
                        (channel_id, channel_name, message_id, content,
                         has_file, file_path, post_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (channel_id, message_id) DO NOTHING;
                    """,
                    row,
                )
    finally:
        conn.close()

def db_get_last_message_id(channel_id: int) -> int:
    conn = psycopg2.connect(**PG_CONFIG)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(MAX(message_id), 0) FROM public.raw_telegram WHERE channel_id=%s",
                    (channel_id,),
                )
                return int(cur.fetchone()[0] or 0)
    finally:
        conn.close()

async def process_and_save(channel_id: int, channel_name: str, message):
    if not message:
        return

    msg_id = int(message.id)
    text = message.message or ""
    post_date = message.date + timedelta(hours=9)  # KST

    has_file = bool(message.media)
    file_path = None

    if has_file:
        os.makedirs("downloads", exist_ok=True)
        filename_prefix = f"{channel_id}_{msg_id}"
        try:
            path = await message.download_media(file=f"downloads/{filename_prefix}")
            file_path = os.path.abspath(path) if path else None
        except Exception as e:
            print(f"[WARN] media download 실패: channel={channel_name} msg={msg_id} err={e}")

    row = (
        channel_id,
        channel_name[:100],
        msg_id,
        text,
        has_file,
        file_path,
        post_date,
    )

    await asyncio.to_thread(db_insert_row, row)

    preview = text.replace("\n", " ")[:80]
    print(f"[SAVE] {channel_name} | msg={msg_id} | {post_date} | {preview}")

# ============== ✅ 초기 동기화 (진짜 최초 1회만) ==============
async def initial_sync(found, limit: int):
    if limit <= 0:
        print("[INFO] 초기 동기화 스킵 (RECENT_MESSAGE_LIMIT_AT_FIRST<=0)")
        return

    print(f"\n[INFO] 초기 동기화(최초 1회만): 각 채널 최근 {limit}개 저장")

    for name, dialog in found.items():
        channel_id = int(dialog.id)

        # ✅ 이미 DB에 데이터가 있으면 최초 실행이 아니라고 보고 스킵
        last_id = await asyncio.to_thread(db_get_last_message_id, channel_id)
        if last_id > 0:
            print(f"[INFO] {name}: 이미 데이터 존재(last_id={last_id}) → 초기 동기화 스킵")
            continue

        try:
            # reverse=True: 오래된 것부터 저장
            async for message in client.iter_messages(dialog.entity, limit=limit, reverse=True):
                await process_and_save(channel_id, name, message)
        except FloodWaitError as e:
            print(f"[FLOOD] 초기 동기화 중 FloodWait {e.seconds}초 대기...")
            await asyncio.sleep(e.seconds)

# ============== (1) 이벤트 기반 수집 ==============
def setup_event_handler(id_to_name, entities):
    @client.on(events.NewMessage(chats=entities))
    async def on_new_message(event):
        try:
            channel_id = int(event.chat_id)
            channel_name = id_to_name.get(channel_id)

            if not channel_name:
                chat = await event.get_chat()
                channel_name = getattr(chat, "title", None) or str(channel_id)

            await process_and_save(channel_id, channel_name, event.message)

        except FloodWaitError as e:
            print(f"[FLOOD] 이벤트 처리 FloodWait {e.seconds}초 대기...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"[ERR] 이벤트 처리 실패: {e}")

# ============== (2) 폴링 기반 수집 ==============
async def poll_loop(found):
    print(f"\n[INFO] Polling 모드 시작: {POLL_INTERVAL}초 간격")
    while True:
        for name, dialog in found.items():
            channel_id = int(dialog.id)
            last_id = await asyncio.to_thread(db_get_last_message_id, channel_id)

            try:
                # last_id 이후의 메시지들만
                async for message in client.iter_messages(dialog.entity, min_id=last_id, reverse=True):
                    await process_and_save(channel_id, name, message)
            except FloodWaitError as e:
                print(f"[FLOOD] polling 중 FloodWait {e.seconds}초 대기...")
                await asyncio.sleep(e.seconds)

        await asyncio.sleep(POLL_INTERVAL)

async def catchup_loop(found):
    print(f"[INFO] Hybrid 보정 폴링 시작: {CATCHUP_INTERVAL}초 간격")
    while True:
        for name, dialog in found.items():
            channel_id = int(dialog.id)
            last_id = await asyncio.to_thread(db_get_last_message_id, channel_id)
            try:
                async for message in client.iter_messages(dialog.entity, min_id=last_id, reverse=True):
                    await process_and_save(channel_id, name, message)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)

        await asyncio.sleep(CATCHUP_INTERVAL)

# ============== 메인 ==============
async def main():
    target_names = load_channel_names(CHANNEL_NAME_FILE)
    print("[INFO] 대상 채널 목록:", target_names)

    found = {}
    print("\n[INFO] 대화 목록에서 대상 채널 찾는 중...")

    async for dialog in client.iter_dialogs():
        if dialog.name in target_names:
            found[dialog.name] = dialog
            print(f"  [FOUND] {dialog.name} -> ID: {dialog.id}")
            if len(found) == len(target_names):
                break

    missing = [name for name in target_names if name not in found]
    if missing:
        print("\n[WARN] 못 찾은 채널:", missing)

    if not found:
        print("[ERR] 찾은 채널이 없습니다. (채널 조인 여부/이름 정확도 확인)")
        return

    # ✅ 최초 실행(=DB에 해당 채널 데이터가 없을 때)만 limit개 저장
    await initial_sync(found, RECENT_MESSAGE_LIMIT_AT_FIRST)

    # 지속 수집 준비
    id_to_name = {int(d.id): name for name, d in found.items()}
    entities = [d.entity for d in found.values()]

    if CRAWL_MODE == "event":
        setup_event_handler(id_to_name, entities)
        print("\n[INFO] Event 모드: 새 메시지 실시간 수집 대기 중...")
        await client.run_until_disconnected()

    elif CRAWL_MODE == "poll":
        await poll_loop(found)

    elif CRAWL_MODE == "hybrid":
        setup_event_handler(id_to_name, entities)
        asyncio.create_task(catchup_loop(found))
        print("\n[INFO] Hybrid 모드: 이벤트 + 보정폴링 실행 중...")
        await client.run_until_disconnected()

    else:
        print(f"[ERR] CRAWL_MODE 값이 이상합니다: {CRAWL_MODE} (event|poll|hybrid)")

async def entry():
    await client.connect()
    try:
    	if not await client.is_user_authorized():
        	print("❌ 세션이 없습니다. 먼저 session_login.py를 -it로 실행해 세션을 생성하세요.")
        	return
    	await main()
    finally:
    	await clitent.disconnect()

if __name__ == "__main__":
    client.loop.run_until_complete(entry())
