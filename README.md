# 🧠 YontAI — Local LLM Fine-Tuning Platform

**YontAI**, açık kaynak LLM'leri yerel ortamınızda **fine-tune** etmek, **benchmark** yapmak, **deploy** etmek ve **export** etmek için tasarlanmış, **Türkçe öncelikli** profesyonel masaüstü AI platformudur.

> 🎯 **Hedef:** Kurumsal kullanıcıların kendi verileriyle, kendi donanımlarında, bulut maliyeti olmadan, gizlilik odaklı AI modelleri geliştirmesini sağlamak.

---

## ✨ Öne Çıkan Özellikler

| Özellik | Açıklama |
|---|---|
| **Model Hub** | HuggingFace, Ollama, yerel GGUF modellerini keşfedin ve yönetin |
| **Fine-Tuning & RL** | LoRA, QLoRA, DPO, PPO, GRPO, ORPO, KTO — 7+ eğitim yöntemi |
| **Chat & Workspace** | Modellerinizle gerçek zamanlı sohbet ve test |
| **Benchmark** | Latans, token/s, GPU/CPU performans karşılaştırmaları |
| **Export** | GGUF, safetensors formatlarında dışa aktarma |
| **Deploy** | Modeli yerel API endpoint'i olarak yayınlama |
| **Model Doctor** | Donanım uyumluluk testi, sorun giderme |
| **Observability** | MLflow ile eğitim metrikleri, loss grafikleri |
| **Data Recipes** | Veri kümesi analizi, kalite skoru, augmentasyon |

### Teknoloji Yığını

```
Frontend:    React 18 · TypeScript · TailwindCSS · shadcn/ui
Desktop:     Tauri v2 (Rust)
Backend:     FastAPI · Python 3.12 · SQLAlchemy · Alembic
AI Runtime:  🤗 Transformers · PEFT · TRL · Unsloth · Sentence-Transformers
Tracking:    MLflow
Database:    SQLite (PostgreSQL hazır)
```

---

## 📸 Ekran Görüntüleri

*(Ekran görüntüleri yakında eklenecek)*

---

## 🚀 Kurulum

### Gereksinimler

- **Python 3.12+** (zorunlu)
- **Node.js 18+** ve **pnpm**
- **Ollama** (chat özellikleri için opsiyonel)
- **Rust toolchain** (Tauri build için)

### Hızlı Başlangıç

```bash
# Repo'yu klonla
git clone https://github.com/WeAreTheArtMakers/YontAI.git
cd YontAI

# Backend kurulumu
python3.12 -m venv .venv
source .venv/bin/activate
cd apps/backend
pip install -e ".[ai,dev]"
cp .env.example .env
alembic upgrade head
cd ../..

# Frontend kurulumu
pnpm install

# Backend'i başlat (Terminal 1)
./start-backend.sh

# Desktop uygulamasını başlat (Terminal 2)
cd apps/desktop
pnpm tauri dev
```

### API Dokümantasyonu

Backend çalışırken: [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs)

---

## 🏗️ Proje Mimarisi

```
YontAI/
├── apps/
│   ├── backend/          # FastAPI backend servisi
│   │   ├── yontai/
│   │   │   ├── api/      # REST API route'ları (11 grup)
│   │   │   ├── training/ # Fine-tuning servisi
│   │   │   ├── runtime/  # AI runtime'lar (6 adet)
│   │   │   ├── jobs/     # İş kuyruğu sistemi
│   │   │   ├── db/       # Veritabanı modelleri (11 tablo)
│   │   │   └── core/     # Konfigürasyon, güvenlik, logging
│   │   └── tests/        # Pytest testleri
│   └── desktop/          # Tauri v2 masaüstü uygulaması
├── packages/
│   ├── shared-types/     # Paylaşılan TypeScript tipleri
│   ├── ui/               # UI component kütüphanesi
│   └── config/           # Ortak konfigürasyon
├── models/               # Model depolama
├── datasets/             # Dataset depolama
└── runs/                 # MLflow run kayıtları
```

---

## 💼 Neden YontAI?

| Karşılaştırma | **YontAI** | LM Studio | Ollama | Axolotl |
|---|---|---|---|---|
| Fine-Tuning | ✅ **7+ yöntem** | ❌ | ❌ | ✅ |
| GUI Masaüstü | ✅ **Tauri** | ✅ | ❌ CLI | ❌ |
| Benchmark | ✅ | ✅ | ❌ | ❌ |
| Export/Deploy | ✅ | ⚠️ Kısmi | ✅ | ❌ |
| Türkçe UI | ✅ **Evet** | ❌ | ❌ | ❌ |
| Lokal Çalışma | ✅ | ✅ | ✅ | ✅ |
| Maliyet | **Tek seferlik lisans** | Ücretsiz | Ücretsiz | Ücretsiz |

---

## 📋 API Rotaları

| Route Grubu | Açıklama |
|---|---|
| `/api/v1/system` | Sistem durumu, donanım bilgisi |
| `/api/v1/models` | Model CRUD, HuggingFace/Ollama keşif |
| `/api/v1/datasets` | Veri kümesi yönetimi |
| `/api/v1/training` | Fine-tuning planlama ve çalıştırma |
| `/api/v1/benchmarks` | Performans testleri |
| `/api/v1/diagnostics` | Sistem tanılama (Model Doctor) |
| `/api/v1/exports` | Model dışa aktarma |
| `/api/v1/deployments` | Model dağıtım |
| `/api/v1/jobs` | İş kuyruğu yönetimi |

---

## 🧪 Test Durumu

```bash
# Backend testleri (8/8 geçiyor)
cd apps/backend && source .venv/bin/activate && pytest -v

# Frontend lint
cd apps/desktop && pnpm lint
```

---

## 📄 Lisans

Ticari lisans. Detaylı bilgi için iletişime geçin.

---

## 📞 İletişim

- GitHub: [WeAreTheArtMakers](https://github.com/WeAreTheArtMakers)
- Web: yakında

---

> ⚠️ **Not:** Bu depo kaynak kod içermektedir. Kurulum ve çalıştırma için gerekli bağımlılıkların tamamı kullanıcı tarafından sağlanmalıdır. Hazır binary paketler için lisanslı sürümü edinin.