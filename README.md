# 🧠 YontAI — Local LLM Fine-Tuning Platform

[English](#english) | [Türkçe](#turkish)

---

<a name="english"></a>
## 🇬🇧 English

**YontAI** is a professional desktop platform for **fine-tuning**, **benchmarking**, **deploying**, and **exporting** open-source LLMs locally. Built with privacy-first architecture, it enables enterprises and AI researchers to train models on their own hardware without cloud costs.

### ✨ Key Features

| Feature | Description |
|---|---|
| **Model Hub** | Discover and manage models from HuggingFace, Ollama, and local GGUF |
| **Fine-Tuning & RL** | LoRA, QLoRA, DPO, PPO, GRPO, ORPO, KTO — 7+ training methods |
| **Chat & Workspace** | Real-time chat and testing with your models |
| **Benchmark** | Performance comparison: latency, token/s, GPU/CPU |
| **Export** | Export to GGUF, safetensors formats |
| **Deploy** | Deploy model as local API endpoint |
| **Model Doctor** | Hardware compatibility testing, troubleshooting |
| **Observability** | MLflow integration for training metrics and loss curves |
| **Data Recipes** | Dataset analysis, quality scoring, augmentation |

### 🏗️ Tech Stack

```
Frontend:    React 18 · TypeScript · TailwindCSS · shadcn/ui
Desktop:     Tauri v2 (Rust)
Backend:     FastAPI · Python 3.12 · SQLAlchemy · Alembic
AI Runtime:  🤗 Transformers · PEFT · TRL · Unsloth · Sentence-Transformers
Tracking:    MLflow
Database:    SQLite (PostgreSQL ready)
```

### 🚀 Quick Start

#### Requirements

- **Python 3.12+** (mandatory)
- **Node.js 18+** and **pnpm**
- **Ollama** (optional, for chat features)
- **Rust toolchain** (for Tauri build)

#### Installation

```bash
# Clone the repo
git clone https://github.com/WeAreTheArtMakers/YontAI.git
cd YontAI

# Backend setup
python3.12 -m venv .venv
source .venv/bin/activate
cd apps/backend
pip install -e ".[ai,dev]"
cp .env.example .env
alembic upgrade head
cd ../..

# Frontend setup
pnpm install

# Start backend (Terminal 1)
./start-backend.sh

# Start desktop app (Terminal 2)
cd apps/desktop
pnpm tauri dev
```

#### API Documentation

When backend is running: [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs)

### 🏗️ Project Architecture

```
YontAI/
├── apps/
│   ├── backend/          # FastAPI backend service
│   │   ├── yontai/
│   │   │   ├── api/      # REST API routes (11 groups)
│   │   │   ├── training/ # Fine-tuning service
│   │   │   ├── runtime/  # AI runtimes (6 types)
│   │   │   ├── jobs/     # Job queue system
│   │   │   ├── db/       # Database models (11 tables)
│   │   │   └── core/     # Config, security, logging
│   │   └── tests/        # Pytest test suite
│   └── desktop/          # Tauri v2 desktop app
├── packages/
│   ├── shared-types/     # Shared TypeScript types
│   ├── ui/               # UI component library
│   └── config/           # Shared configuration
├── models/               # Model storage
├── datasets/             # Dataset storage
└── runs/                 # MLflow run records
```

### 📋 API Routes

| Route Group | Description |
|---|---|
| `/api/v1/system` | System status, hardware info |
| `/api/v1/models` | Model CRUD, HuggingFace/Ollama discovery |
| `/api/v1/datasets` | Dataset management |
| `/api/v1/training` | Fine-tuning planning and execution |
| `/api/v1/benchmarks` | Performance benchmarks |
| `/api/v1/diagnostics` | System diagnostics (Model Doctor) |
| `/api/v1/exports` | Model export |
| `/api/v1/deployments` | Model deployment |
| `/api/v1/jobs` | Job queue management |
| `/api/v1/files` | File browsing and extraction |

### 🧪 Test Status

```bash
# Backend tests (8/8 passing)
cd apps/backend && source .venv/bin/activate && pytest -v

# Frontend lint
cd apps/desktop && pnpm lint
```

### 💼 Why YontAI?

| Feature | **YontAI** | LM Studio | Ollama | Axolotl |
|---|---|---|---|---|
| Fine-Tuning | ✅ **7+ methods** | ❌ | ❌ | ✅ |
| Desktop GUI | ✅ **Tauri** | ✅ | ❌ CLI | ❌ |
| Benchmark | ✅ | ✅ | ❌ | ❌ |
| Export/Deploy | ✅ | ⚠️ Partial | ✅ | ❌ |
| Turkish UI | ✅ **Yes** | ❌ | ❌ | ❌ |
| Local Operation | ✅ | ✅ | ✅ | ✅ |
| Cost | **One-time license** | Free | Free | Free |

### 📄 License

Commercial license. Contact us for details.

### 📞 Contact

- GitHub: [WeAreTheArtMakers](https://github.com/WeAreTheArtMakers)

---

> ⚠️ **Note:** This repository contains source code. Users must provide all required dependencies. For pre-built binary packages, please obtain a licensed version.

---

<a name="turkish"></a>
## 🇹🇷 Türkçe

**YontAI**, açık kaynak LLM'leri yerel ortamınızda **fine-tune** etmek, **benchmark** yapmak, **deploy** etmek ve **export** etmek için tasarlanmış, **Türkçe öncelikli** profesyonel masaüstü AI platformudur. Gizlilik odaklı mimarisiyle, kurumsal kullanıcıların ve AI araştırmacılarının kendi donanımlarında, bulut maliyeti olmadan modeller geliştirmesini sağlar.

### ✨ Öne Çıkan Özellikler

| Özellik | Açıklama |
|---|---|
| **Model Hub** | HuggingFace, Ollama ve yerel GGUF modellerini keşfedin ve yönetin |
| **Fine-Tuning & RL** | LoRA, QLoRA, DPO, PPO, GRPO, ORPO, KTO — 7+ eğitim yöntemi |
| **Chat & Workspace** | Modellerinizle gerçek zamanlı sohbet ve test |
| **Benchmark** | Latans, token/s, GPU/CPU performans karşılaştırmaları |
| **Export** | GGUF, safetensors formatlarında dışa aktarma |
| **Deploy** | Modeli yerel API endpoint'i olarak yayınlama |
| **Model Doctor** | Donanım uyumluluk testi, sorun giderme |
| **Observability** | MLflow ile eğitim metrikleri, loss grafikleri |
| **Data Recipes** | Veri kümesi analizi, kalite skoru, augmentasyon |

### 🏗️ Teknoloji Yığını

```
Frontend:    React 18 · TypeScript · TailwindCSS · shadcn/ui
Desktop:     Tauri v2 (Rust)
Backend:     FastAPI · Python 3.12 · SQLAlchemy · Alembic
AI Runtime:  🤗 Transformers · PEFT · TRL · Unsloth · Sentence-Transformers
Tracking:    MLflow
Veritabanı:  SQLite (PostgreSQL hazır)
```

### 🚀 Hızlı Başlangıç

#### Gereksinimler

- **Python 3.12+** (zorunlu)
- **Node.js 18+** ve **pnpm**
- **Ollama** (chat özellikleri için opsiyonel)
- **Rust toolchain** (Tauri build için)

#### Kurulum

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

#### API Dokümantasyonu

Backend çalışırken: [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs)

### 🏗️ Proje Mimarisi

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

### 📋 API Rotaları

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
| `/api/v1/files` | Dosya gezinti ve çıkarma |

### 🧪 Test Durumu

```bash
# Backend testleri (8/8 geçiyor)
cd apps/backend && source .venv/bin/activate && pytest -v

# Frontend lint
cd apps/desktop && pnpm lint
```

### 💼 Neden YontAI?

| Özellik | **YontAI** | LM Studio | Ollama | Axolotl |
|---|---|---|---|---|
| Fine-Tuning | ✅ **7+ yöntem** | ❌ | ❌ | ✅ |
| GUI Masaüstü | ✅ **Tauri** | ✅ | ❌ CLI | ❌ |
| Benchmark | ✅ | ✅ | ❌ | ❌ |
| Export/Deploy | ✅ | ⚠️ Kısmi | ✅ | ❌ |
| Türkçe UI | ✅ **Evet** | ❌ | ❌ | ❌ |
| Lokal Çalışma | ✅ | ✅ | ✅ | ✅ |
| Maliyet | **Tek seferlik lisans** | Ücretsiz | Ücretsiz | Ücretsiz |

### 📄 Lisans

Ticari lisans. Detaylı bilgi için iletişime geçin.

### 📞 İletişim

- GitHub: [WeAreTheArtMakers](https://github.com/WeAreTheArtMakers)

---

> ⚠️ **Not:** Bu depo kaynak kod içermektedir. Kurulum ve çalıştırma için gerekli bağımlılıkların tamamı kullanıcı tarafından sağlanmalıdır. Hazır binary paketler için lisanslı sürümü edinin.