import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        # 1. 브라우저 실행 (GPU 끄기 등 옵션 유지)
        browser = await p.firefox.launch(
            headless=False, 
            args=[
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        # 2. 컨텍스트 생성 (한글 설정 등)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 720}
        )
        
        # ★ 핵심: 라이브러리 대신 직접 스크립트 주입 (Stealth 기능 수동 구현)
        # 이 스크립트들이 "나 봇 아니야"라고 브라우저를 속입니다.
        await context.add_init_script("""
            // 1. webdriver 속성 숨기기 (가장 중요)
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // 2. 크롬 플러그인 정보 가짜로 만들기
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // 3. 언어 설정 강제
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko']
            });
            
            // 4. 권한 요청 자동 통과 흉내
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)

        page = await context.new_page()

        print("[-] 트위터 로그인 페이지로 이동합니다...")
        try:
            await page.goto("https://twitter.com/i/flow/login", timeout=60000)
        except Exception as e:
            print(f"접속 시간 초과 또는 에러 (무시하고 진행): {e}")

        print("\n" + "="*50)
        print("   [사용자 행동 필요]")
        print("   1. ID 입력 후 엔터 (또는 탭 -> 엔터)")
        print("   2. 비밀번호 입력 후 엔터")
        print("   3. 로그인 완료되면 터미널로 돌아와서 엔터 키 누르기")
        print("="*50 + "\n")
        
        input(">>> 로그인 완료했으면 여기서 엔터 누르세요 <<<")

        # 세션 저장
        await context.storage_state(path="twitter_auth.json")
        print("\n[Success] 'twitter_auth.json' 생성 완료! 이제 가상환경 끄셔도 됩니다.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
