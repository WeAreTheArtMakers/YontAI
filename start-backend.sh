#!/bin/bash

# YontAI Backend Başlatma Scripti
# Bu script backend'i doğru Python versiyonu ile başlatır

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/apps/backend"

echo "🚀 YontAI Backend Başlatılıyor..."
echo "📁 Backend dizini: $BACKEND_DIR"

# Python versiyonunu kontrol et
UV_BIN="${UV_BIN:-uv}"
if ! command -v "$UV_BIN" >/dev/null 2>&1 && [ -x "$HOME/.local/bin/uv" ]; then
    UV_BIN="$HOME/.local/bin/uv"
fi
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ] && [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    if "$SCRIPT_DIR/.venv/bin/python" -c "import sys; exit(0 if (3, 12) <= sys.version_info < (3, 13) else 1)" 2>/dev/null; then
        PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
    fi
fi
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if command -v "$UV_BIN" >/dev/null 2>&1; then
        "$UV_BIN" python install 3.12 >/dev/null
        PYTHON_BIN="$("$UV_BIN" python find 3.12)"
    elif command -v python3 >/dev/null 2>&1 && python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
        PYTHON_BIN="python3"
    else
        echo "❌ HATA: Python 3.12 bulunamadı!"
        echo ""
        echo "📦 Python 3.12 kurulum önerileri:"
        echo "   • Homebrew: brew install python@3.12"
        echo "   • pyenv: pyenv install 3.12 && pyenv local 3.12"
        echo "   • uv: uv python install 3.12"
        exit 1
    fi
fi

PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}')
echo "🐍 Seçilen Python: $PYTHON_BIN ($PYTHON_VERSION)"

if ! "$PYTHON_BIN" -c "import sys; exit(0 if (3, 12) <= sys.version_info < (3, 13) else 1)" 2>/dev/null; then
    echo "❌ HATA: Proje Python >=3.12,<3.13 gerektiriyor!"
    echo "   Mevcut versiyon: $PYTHON_VERSION"
    echo ""
    echo "📦 Python 3.12 kurulum önerileri:"
    echo "   • Homebrew: brew install python@3.12"
    echo "   • pyenv: pyenv install 3.12 && pyenv local 3.12"
    echo "   • uv: uv python install 3.12"
    exit 1
fi

# Virtual environment kontrolü
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "📦 Virtual environment bulunamadı, oluşturuluyor..."
    if command -v "$UV_BIN" >/dev/null 2>&1; then
        "$UV_BIN" venv --python 3.12 "$SCRIPT_DIR/.venv"
    else
        "$PYTHON_BIN" -m venv "$SCRIPT_DIR/.venv"
    fi
fi

# Virtual environment'ı aktifleştir
echo "🔧 Virtual environment aktifleştiriliyor..."
source "$SCRIPT_DIR/.venv/bin/activate"

if ! python -c "import sys; exit(0 if (3, 12) <= sys.version_info < (3, 13) else 1)" 2>/dev/null; then
    echo "❌ HATA: Mevcut .venv Python 3.12 ile oluşturulmamış."
    echo "   Çözüm: rm -rf .venv && $PYTHON_BIN -m venv .venv"
    exit 1
fi

# Bağımlılıkları yükle
echo "📥 Backend bağımlılıkları kontrol ediliyor..."
cd "$BACKEND_DIR"

if ! python -c "import pydantic_settings" 2>/dev/null; then
    echo "📦 Bağımlılıklar yükleniyor..."
    if command -v "$UV_BIN" >/dev/null 2>&1; then
        "$UV_BIN" pip install -e .
    else
        pip install -e .
    fi
else
    echo "✅ Bağımlılıklar zaten yüklü"
fi

# .env dosyasını kontrol et
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "⚠️  .env dosyası bulunamadı, .env.example'dan kopyalanıyor..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
fi

# Database migration kontrolü
echo "🗄️  Database migration kontrol ediliyor..."
if [ ! -f "$BACKEND_DIR/yontai.db" ]; then
    echo "📊 Database oluşturuluyor..."
    alembic upgrade head
fi

# Backend'i başlat
echo ""
echo "✨ Backend başlatılıyor: http://127.0.0.1:8765"
echo "📚 API Docs: http://127.0.0.1:8765/docs"
echo ""
echo "Durdurmak için: Ctrl+C"
echo ""

if [ "${YONTAI_RELOAD:-0}" = "1" ]; then
    uvicorn yontai.main:app --host 127.0.0.1 --port 8765 --reload
else
    uvicorn yontai.main:app --host 127.0.0.1 --port 8765
fi
