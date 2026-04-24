@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================
echo   채팅방 인원 분석 시작
echo ==============================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Python이 설치되어 있지 않습니다.
    echo https://www.python.org 에서 설치 후 다시 실행해주세요.
    pause
    exit /b 1
)

echo.
echo 패키지 설치 확인 중...
python -m pip install -r requirements.txt -q

echo.
echo 브라우저에서 프로그램이 열립니다...
echo 종료하려면 이 창에서 Ctrl+C 를 누르세요.
echo.

python -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
pause
