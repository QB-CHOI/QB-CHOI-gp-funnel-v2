#!/bin/bash
# 이 파일을 더블클릭하면 채팅방 인원 분석 프로그램이 실행됩니다.

cd "$(dirname "$0")"

echo "=============================="
echo "  채팅방 인원 분석 시작"
echo "=============================="

# Python3 설치 확인
if ! command -v python3 &>/dev/null; then
    echo ""
    echo "Python3이 설치되어 있지 않습니다."
    echo "https://www.python.org 에서 설치 후 다시 실행해주세요."
    read -p "엔터를 눌러 종료..."
    exit 1
fi

echo ""
echo "패키지 설치 확인 중..."
python3 -m pip install -r requirements.txt -q

echo ""
echo "브라우저에서 프로그램이 열립니다..."
echo "종료하려면 이 창에서 Ctrl+C 를 누르세요."
echo ""

python3 -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
