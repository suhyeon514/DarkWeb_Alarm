
import os
from dotenv import load_dotenv

from telethon import TelegramClient

# 1) .env 읽어오기
load_dotenv()  # 현재 폴더의 .env 파일을 환경변수로 로드

api_id = int(os.environ["TG_API_ID"])
api_hash = os.environ["TG_API_HASH"]

# ✅ 세션을 볼륨 마운트된 폴더에 저장 (중요)
SESSION_PATH = os.environ.get("TG_SESSION_PATH", "/app/sessions/anon")

# 2) 세션 이름 'anon' 으로 클라이언트 생성
client = TelegramClient(SESSION_PATH, api_id, api_hash)

async def main():
    # ✅ 대화형 로그인 트리거 (폰번호/코드/2FA 비번 입력)
    await client.start()
    me = await client.get_me()
    print("로그인 계정:", me.username, me.id)

    # 테스트 메시지
    await client.send_message("me", "✅ Telethon session 연결 테스트 완료!")

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
