"""
nginx candle.conf 에 /infinite_buying/ 블록을 추가합니다.
sudo python3 scripts/setup_nginx.py
"""
import sys
from pathlib import Path

CONF = Path("/etc/nginx/conf.d/candle.conf")
PROJECT = Path("/home/cheoljoo/code/the-last-of-us-stock")

NEW_BLOCK = f"""
    # ── /infinite_buying — 라오어 무한매수법 백테스트 대시보드 ─────────────
    location = /infinite_buying {{
        return 301 /infinite_buying/;
    }}

    location /infinite_buying/ {{
        alias {PROJECT}/reports/html/;
        index index.html;
        try_files $uri $uri/ =404;
        charset utf-8;
        add_header Cache-Control "no-cache, must-revalidate";
        add_header Pragma no-cache;
    }}

"""

INSERT_BEFORE = "    # ── /news — News Arcade"

def main():
    content = CONF.read_text()

    if "/infinite_buying/" in content:
        print("✓ /infinite_buying/ 블록이 이미 존재합니다.")
        return

    if INSERT_BEFORE not in content:
        print(f"✗ '{INSERT_BEFORE}' 를 찾을 수 없습니다. candle.conf 구조가 변경된 것 같습니다.")
        sys.exit(1)

    updated = content.replace(INSERT_BEFORE, NEW_BLOCK + INSERT_BEFORE)
    CONF.write_text(updated)
    print("✓ /infinite_buying/ 블록 추가 완료")
    print()
    print("다음 명령으로 nginx를 재로드하세요:")
    print("  sudo nginx -t && sudo systemctl reload nginx")

if __name__ == "__main__":
    main()
