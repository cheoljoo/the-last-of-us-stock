#!/bin/bash
# 로컬 nginx 서버에 배포 (이 PC = 웹 서버)
# stock_candle/ 은 절대 건드리지 않습니다.
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HTML_DIR="$PROJECT_DIR/reports/html"

echo "=== 무한매수법 대시보드 배포 ==="
echo "HTML 소스: $HTML_DIR"
echo "⚠️  stock_candle/ 은 변경하지 않습니다."
echo ""

# nginx alias 가 이미 reports/html/ 를 직접 바라보므로
# 파일이 올바른 위치에 있는지만 확인합니다.
if [ ! -f "$HTML_DIR/index.html" ]; then
    echo "✗ index.html 이 없습니다. 먼저 'make dashboard' 를 실행하세요."
    exit 1
fi

echo "✓ index.html 확인 ($(du -sh "$HTML_DIR/index.html" | cut -f1))"
echo ""
echo "nginx 설정(/etc/nginx/conf.d/candle.conf)에 아래 블록이 있으면 바로 접근 가능합니다:"
echo ""
echo "  location /infinite_buying/ {"
echo "      alias $HTML_DIR/;"
echo "      index index.html;"
echo "      try_files \$uri \$uri/ =404;"
echo "      charset utf-8;"
echo "  }"
echo ""
echo "설정 추가 후: sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "URL: http://psncs.iptime.org/infinite_buying/index.html"
