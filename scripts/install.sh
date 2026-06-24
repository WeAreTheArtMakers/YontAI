#!/bin/bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
checkmark="${GREEN}✅${NC}"; arrow="${CYAN}➜${NC}"

echo -e "\n${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      YontAI - AI Coding Lab Kurulum     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}\n"

# Python 3.11 öncelikli tespit (macOS Tahoe'de 3.12 expat hatası var)
PYTHON=""
for cmd in python3.11 python3 python3.12; do
    if command -v $cmd &>/dev/null; then
        VER=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        MAJOR=$(echo $VER | cut -d. -f1); MINOR=$(echo $VER | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            # expat test (macOS Tahoe bug)
            if $cmd -c "import xml.parsers.expat; print('ok')" &>/dev/null; then
                PYTHON=$cmd; break
            else
                echo -e "  ${YELLOW}⚠️ Python $VER expat uyumsuz, diğer versiyon deneniyor...${NC}"
            fi
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}❌ Python 3.11+ gerekli!${NC}"
    echo "  brew install python@3.11"
    exit 1
fi
echo -e "  ${checkmark} Python $($PYTHON --version 2>&1) ($PYTHON)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/apps/backend"
cd "$PROJECT_DIR"

echo -e "${arrow} Sanal ortam oluşturuluyor..."
rm -rf "$BACKEND_DIR/.venv"
$PYTHON -m venv "$BACKEND_DIR/.venv"
source "$BACKEND_DIR/.venv/bin/activate"
echo -e "  ${checkmark} Sanal ortam hazır ($PYTHON)"

echo -e "${arrow} Bağımlılıklar yükleniyor..."
cd "$BACKEND_DIR"
pip install --upgrade pip setuptools wheel -q
pip install -e "." -q
pip install -e ".[mlx,rag]" -q 2>/dev/null || true
pip install "numpy<2" -q
echo -e "  ${checkmark} Bağımlılıklar tamam"

if [ "$(uname -m)" = "arm64" ]; then
    echo -e "  ${checkmark} Apple Silicon M1/M2/M3/M4"
    pip install mlx mlx-lm -q 2>/dev/null && echo -e "  ${checkmark} MLX yüklendi" || echo -e "  ${YELLOW}⚠️ MLX yüklenemedi, brew install mlx dene${NC}"
else
    echo -e "  ${YELLOW}⚠️ Intel Mac - Ollama kullan: brew install ollama${NC}"
fi

echo -e "\n${arrow} Testler çalıştırılıyor..."
$PYTHON -m pytest tests/ -v --tb=short -q 2>&1 | tail -3 || echo -e "  ${YELLOW}⚠️ Test detayı için: pytest tests/ -v${NC}"

echo -e "\n${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        ✅ KURULUM TAMAMLANDI!           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo -e "\n🚀 Başlat: cd apps/backend && source .venv/bin/activate && uvicorn yontai.main:app --host 127.0.0.1 --port 8765 --reload"
echo -e "🌐 Web:   http://localhost:8765"
echo -e "📖 Repo:  https://github.com/WeAreTheArtMakers/YontAI\n"