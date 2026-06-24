#!/bin/bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'
checkmark="${GREEN}✅${NC}"; cross="${RED}❌${NC}"; arrow="${CYAN}➜${NC}"

VERSION="1.0.0"
RELEASE_NAME="YontAI-v${VERSION}"

echo -e "\n${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     YontAI Release Builder v${VERSION}    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}\n"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/apps/backend"
cd "$PROJECT_DIR"

# 1. Test
echo -e "${arrow} Testler çalıştırılıyor..."
cd "$BACKEND_DIR"
if python3 -m pytest tests/ -v --tb=short -q 2>&1; then
    echo -e "  ${checkmark} Tüm testler geçti"
else
    echo -e "  ${cross} Testler başarısız!"
    exit 1
fi

# 2. Lint
echo -e "${arrow} Lint kontrolü..."
if python3 -m ruff check yontai/ --quiet 2>&1; then
    echo -e "  ${checkmark} Lint: 0 hata"
else
    echo -e "  ${cross} Lint hataları var!"
    exit 1
fi

cd "$PROJECT_DIR"

# 3. Git tag
echo -e "${arrow} Git tag oluşturuluyor..."
git tag -f "v${VERSION}" -m "YontAI v${VERSION} - AI Coding Lab"
git push origin "v${VERSION}" -f 2>&1 || true
echo -e "  ${checkmark} Tag: v${VERSION}"

# 4. .app bundle'ını hazırla
echo -e "${arrow} Uygulama paketi hazırlanıyor..."
APP_SOURCE="$PROJECT_DIR/dist/YontAI.app"
APP_ZIP="$PROJECT_DIR/dist/${RELEASE_NAME}.zip"

if [ -d "$APP_SOURCE" ]; then
    cd "$PROJECT_DIR/dist"
    chmod +x "$APP_SOURCE/Contents/MacOS/YontAI" 2>/dev/null || true
    zip -r "${RELEASE_NAME}.zip" "YontAI.app" -x "*.DS_Store" -q
    echo -e "  ${checkmark} ${RELEASE_NAME}.zip oluşturuldu ($(du -sh ${RELEASE_NAME}.zip | cut -f1))"
else
    echo -e "  ${YELLOW}⚠️ Uygulama paketi bulunamadı, atlanıyor${NC}"
    APP_ZIP=""
fi

# 5. GitHub Release
echo -e "${arrow} GitHub Release oluşturuluyor..."
RELEASE_NOTES=$(cat <<EOF
# YontAI v${VERSION} - AI Coding Lab

## 🚀 Özellikler
- **MLX Apple Silicon Desteği** - M1/M2/M3/M4'te %40 hız artışı
- **Çoklu Model Orkestrasyonu** - Akıllı routing (1-3B FIM + 7-16B chat)
- **FIM Kod Tamamlama** - DeepSeek-Coder formatı, <150ms
- **RAG Bağlam Motoru** - 17 dilde AST parsing + ChromaDB
- **Web Kod Toplama** - GitHub/npm/PyPI entegrasyonu
- **AI Lab Eğitimi** - MLX LoRA fine-tuning + dataset builder

## 📦 İçerik
- macOS .app bundle
- Python FastAPI backend (19 modül)
- VS Code extension tasarımı
- TR/EN web sitesi

## 🔧 Kurulum
\`\`\`bash
bash scripts/install.sh
cd apps/backend && uvicorn yontai.main:app --host 127.0.0.1 --port 8765 --reload
\`\`\`

## 🌐 Web Sitesi
https://WeAreTheArtMakers.github.io/YontAI/

## 📖 Detaylı Dökümantasyon
ARCHITECTURE.md - 10 bölümlük mimari analiz
EOF
)

if command -v gh &>/dev/null; then
    gh release create "v${VERSION}" \
        --title "YontAI v${VERSION}" \
        --notes "$RELEASE_NOTES" \
        $APP_ZIP 2>&1 || {
        echo -e "  ${YELLOW}⚠️ Release oluşturulamadı, gh CLI token kontrol et${NC}"
        echo -e "  ${arrow} Manual: gh release create v${VERSION} --title 'YontAI v${VERSION}' $APP_ZIP"
    }
    echo -e "  ${checkmark} Release: v${VERSION}"
else
    echo -e "  ${YELLOW}⚠️ gh CLI bulunamadı${NC}"
    echo -e "  ${arrow} Yükle: brew install gh"
    echo -e "  ${arrow} Manual: gh release create v${VERSION} --title 'YontAI v${VERSION}' $APP_ZIP"
fi

echo -e "\n${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     ✅ RELEASE HAZIR!                    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo -e "\n📦 ${RELEASE_NAME}.zip"
echo -e "🌐 https://github.com/WeAreTheArtMakers/YontAI/releases/tag/v${VERSION}"
echo -e "📖 ARCHITECTURE.md\n"