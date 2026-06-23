#!/usr/bin/env bash
set -e

echo "=========================================="
echo "    YontAI Studio Başlatıcı (Launcher)    "
echo "=========================================="
echo ""

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/apps/backend"
VENV_DIR="$ROOT_DIR/.venv"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "-> HATA: Root .venv bulunamadı. Önce ./start-backend.sh ile backend ortamını kurun."
    exit 1
fi

if ! "$VENV_DIR/bin/python" -c "import sys; exit(0 if (3, 12) <= sys.version_info < (3, 13) else 1)" 2>/dev/null; then
    echo "-> HATA: .venv Python >=3.12,<3.13 ile oluşturulmalı."
    echo "-> Çözüm: rm -rf .venv && python3.12 -m venv .venv"
    exit 1
fi

# 1. Start the FastAPI backend in the background
echo "-> FastAPI Backend başlatılıyor (Port 8765)..."
cd "$BACKEND_DIR" || exit
source "$VENV_DIR/bin/activate"
uvicorn yontai.main:app --port 8765 &
BACKEND_PID=$!
cd "$ROOT_DIR" || exit

cleanup() {
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "-> Backend başarıyla başlatıldı (PID: $BACKEND_PID)."
echo "-> Birkaç saniye bekleniyor..."
sleep 3

# 2. Open the Tauri Desktop App
echo "-> YontAI Desktop App açılıyor..."
APP_PATH="$ROOT_DIR/apps/desktop/src-tauri/target/release/bundle/macos/YontAI.app"

if [ -d "$APP_PATH" ]; then
    open "$APP_PATH"
else
    echo "-> HATA: YontAI.app bulunamadı. Lütfen önce derleme (build) işleminin bittiğinden emin olun."
    exit 1
fi

echo "=========================================="
echo "    YontAI Studio Başarıyla Açıldı!       "
echo "=========================================="
echo "Çıkmak ve backend'i kapatmak için bu terminalde CTRL+C tuşlarına basabilirsiniz."

# Wait for user to kill the script to also kill the backend
wait $BACKEND_PID
