#!/bin/bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
checkmark="${GREEN}✅${NC}"; arrow="${CYAN}➜${NC}"

echo -e "\n${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      YontAI - AI Coding Lab Kurulum     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}\n"

# Python 3.11 öncelikli (macOS Tahoe'de 3.12 expat hatası var)
PYTHON=""
for cmd in python3.11 python3 python3.12; do
    if command -v $cmd &>/dev/null; then
        VER=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        MAJOR=$(echo $VER | cut -d. -f1); MINOR=$(echo $VER | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            if $cmd -c "import xml.parsers.expat" &>/dev/null; then
                PYTHON=$cmd; break
            else
                echo -e "  ${YELLOW}⚠️ Python $VER expat uyumsuz, 3.11 deneniyor...${NC}"
            fi
        fi
    fi
done

[ -z "$PYTHON" ] && { echo -e "  ${RED}❌ Python 3.11+ gerekli! brew install python@3.11${NC}"; exit 1; }
echo -e "  ${checkmark} $($PYTHON --version 2>&1) ($PYTHON)"

cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
BACKEND_DIR="apps/backend"

echo -e "${arrow} Sanal ortam..."
rm -rf "$BACKEND_DIR/.venv"
$PYTHON -m venv "$BACKEND_DIR/.venv"
source "$BACKEND_DIR/.venv/bin/activate"
echo -e "  ${checkmark} .venv hazır"

echo -e "${arrow} Bağımlılıklar..."
cd "$BACKEND_DIR"
pip install --upgrade pip setuptools wheel -q
pip install -e "." -q
pip install -e ".[mlx,rag]" -q 2>/dev/null || true
pip install "numpy<2" -q
echo -e "  ${checkmark} Bağımlılıklar tamam"

[ "$(uname -m)" = "arm64" ] && { pip install mlx mlx-lm -q 2>/dev/null && echo -e "  ${checkmark} MLX yüklendi"; } || echo -e "  ${YELLOW}⚠️ Intel Mac: brew install ollama${NC}"

echo -e "\n${arrow} Testler..."
$PYTHON -m pytest tests/ -v --tb=short -q 2>&1 | tail -3 || true

echo -e "\n${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        ✅ KURULUM TAMAM!                ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo -e "\n🚀 cd apps/backend && source .venv/bin/activate && uvicorn yontai.main:app --host 127.0.0.1 --port 8765"
echo -e "🌐 http://localhost:8765\n"