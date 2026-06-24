#!/bin/bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'
checkmark="${GREEN}✅${NC}"
arrow="${CYAN}➜${NC}"

echo -e "\n${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      YontAI - AI Coding Lab Kurulum     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}\n"

PYTHON=""
for cmd in python3.12 python3.11 python3; do
    if command -v $cmd &>/dev/null; then
        VER=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        MAJOR=$(echo $VER | cut -d. -f1); MINOR=$(echo $VER | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON=$cmd
            echo -e "  ${checkmark} Python $VER ($PYTHON)"
            break
        fi
    fi
done
[ -z "$PYTHON" ] && { echo -e "  ${RED}❌ Python 3.11+ gerekli!${NC}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/apps/backend"
cd "$PROJECT_DIR"

echo -e "${arrow} Sanal ortam oluşturuluyor..."
$PYTHON -m venv "$BACKEND_DIR/.venv" 2>/dev/null || true
source "$BACKEND_DIR/.venv/bin/activate"
echo -e "  ${checkmark} Sanal ortam hazır"

echo -e "${arrow} Bağımlılıklar yükleniyor..."
cd "$BACKEND_DIR"
pip install --upgrade pip -q
pip install -e "." -q
pip install -e ".[mlx,rag]" -q 2>/dev/null || true
pip install "numpy<2" -q
echo -e "  ${checkmark} Bağımlılıklar tamam"

if [ "$(uname -m)" = "arm64" ]; then
    echo -e "  ${checkmark} Apple Silicon M1/M2/M3/M4 tespit edildi"
    pip install mlx mlx-lm -q 2>/dev/null && echo -e "  ${checkmark} MLX yüklendi"
else
    echo -e "  ${YELLOW}⚠️ Intel Mac - MLX desteklenmez. Ollama kullanın.${NC}"
fi

echo -e "\n${arrow} Testler çalıştırılıyor..."
$PYTHON -m pytest tests/ -v --tb=short -q 2>&1 | tail -3

echo -e "\n${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        ✅ KURULUM TAMAMLANDI!           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo -e "\n🚀 Başlat: cd apps/backend && uvicorn yontai.main:app --host 127.0.0.1 --port 8765 --reload"
echo -e "🌐 Web:   http://localhost:8765"
echo -e "📖 Repo:  https://github.com/WeAreTheArtMakers/YontAI\n"