# 1. Playwright 공식 이미지 (브라우저 포함됨)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 2. 작업 폴더 설정
WORKDIR /app

# 3. 라이브러리 설치 (캐시 활용을 위해 requirements 먼저 복사)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install python-dotenv  # 혹시 requirements에 빠졌을까봐 안전장치

# 4. 소스코드 복사
COPY . .

# 5. 실행 명령 (기본값은 깃허브 스캐너, 컴포즈에서 덮어쓰기 가능)
CMD ["python", "github_scanner.py"]