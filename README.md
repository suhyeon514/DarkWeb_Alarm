# 🕵️‍♂️ DarkWeb Leak Hunter (DarkWeb & GitHub Crawler)

이 프로젝트는 트위터, 깃허브, 구글을 크롤링하여 정보 유출 신호를 탐지합니다.

## 🚀 시작하기 (Quick Start)

### 1. 환경 설정 파일 준비 (.env)
`env.example` 파일을 복사하여 `.env` 파일을 만들고, 본인의 토큰을 입력하세요.

```bash
cp .env.example .env

.env 파일 내용 수정:

GITHUB_TOKEN: 본인의 GitHub 토큰 입력 (Settings -> Developer settings -> Personal access tokens)

DB_ 관련 설정은 Docker 사용 시 그대로 두셔도 됩니다.

2. 트위터 인증 파일 준비 (필수! 🔥)
트위터 크롤링을 위해 로그인 세션 파일(twitter_auth.json)이 필요합니다.


[생성 방법]

PC 크롬 브라우저에서 X.com(트위터) 로그인

F12 (개발자 도구) -> Application 탭 -> Storage -> Cookies -> https://twitter.com -> 모든 쿠키 복사

프로젝트 폴더에 twitter_auth.json 파일을 만들고 모든 쿠키를 붙여넣기

※로그아웃 시 세션 종료