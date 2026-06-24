# 🧠 YontAI — Yerel Yapay Zeka Kod Asistanı

[English](#english) | [Türkçe](#turkish)

---

<a name="turkish"></a>
## 🇹🇷 Türkçe

**YontAI**, Apple Silicon (M1/M2/M3/M4) için optimize edilmiş, tamamen yerel çalışan bir yapay zeka kod asistanıdır. MLX, Ollama ve llama.cpp backend'lerini tek bir arayüzde birleştirir, proje bağlamını anlar (RAG) ve akıllı kod tamamlama (FIM) sağlar.

> 🚀 **M1 Pro 16 GB** için özel olarak optimize edilmiştir. Kuantize modellerde GPU'da %40'a varan hız artışı!

---

## 🚀 Özellikler

| Özellik | Açıklama |
|---------|----------|
| **MLX Desteği** | Apple Silicon için optimize edilmiş MLX formatında modelleri çalıştırır |
| **Çoklu Model** | Hızlı (1-3B FIM) + Akıllı (7-16B sohbet) katmanlı model stratejisi |
| **FIM Tamamlama** | DeepSeek-Coder formatında Fill-in-the-Middle kod tamamlama |
| **RAG Bağlam** | tree-sitter + ChromaDB ile proje kodunu indeksleme ve akıllı bağlam arama |
| **HF → MLX** | HuggingFace modellerini tek tıkla MLX formatına dönüştürme |
| **LRU Önbellek** | 16 GB RAM için optimize, otomatik model boşaltma |
| **Ollama Uyumlu** | Ollama ile tam uyumlu, mevcut modelleri kullanma |
| **Prompt Şablonları** | Türkçe kod açıklama, test yazma, refactoring, kod inceleme şablonları |
| **Donanım Tespiti** | Apple Silicon çip modeli, MLX/MPS/CUDA/ROCm otomatik tespit |
| **Gizlilik** | Tamamen yerel çalışma, bulut bağımlılığı yok |

---

## 📋 Gereksinimler

| Bileşen | Minimum | Önerilen |
|---------|---------|----------|
| **İşlemci** | Apple Silicon (M1) | Apple M1 Pro |
| **RAM** | 8 GB | 16 GB |
| **Python** | 3.11 | 3.12 |
| **Depolama** | 10 GB boş alan | 50 GB+ (modeller için) |
| **İşletim Sistemi** | macOS 14+ | macOS 15+ |

---

## ⚡ Hızlı Başlangıç

### 1. Repoyu Klonla

```bash
git clone https://github.com/WeAreTheArtMakers/YontAI.git
cd YontAI
```

### 2. Backend Kurulumu

```bash
cd apps/backend

# Temel bağımlılıklar
pip install -e .

# MLX desteği (Apple Silicon için önerilen)
pip install -e ".[mlx]"

# RAG desteği (kod bağlam motoru)
pip install -e ".[rag]"

# AI kütüphaneleri (transformers, torch, vs.)
pip install -e ".[ai]"
```

### 3. MLX Modelini İndir ve Dönüştür

```bash
# DeepSeek-Coder 1.3B (FIM için hızlı model ~2.5 GB)
python3 -m mlx_lm.convert \
  --hf-path deepseek-ai/deepseek-coder-1.3b-instruct \
  --mlx-path models/mlx/deepseek-coder-1.3b-instruct

# DeepSeek-Coder 6.7B (sohbet için akıllı model ~12 GB)
python3 -m mlx_lm.convert \
  --hf-path deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct \
  --mlx-path models/mlx/DeepSeek-Coder-V2-Lite-Instruct \
  --q-bits 4
```

### 4. Backend'i Başlat

```bash
cd apps/backend
uvicorn yontai.main:app --host 127.0.0.1 --port 8765 --reload
```

### 5. API'yi Test Et

```bash
# Donanım profilini görüntüle
curl http://localhost:8765/api/v1/system/hardware | python3 -m json.tool

# Sağlık kontrolü
curl http://localhost:8765/api/v1/system/health

# MLX modellerini listele
curl http://localhost:8765/api/v1/models/mlx/list

# FIM kod tamamlama (imleç öncesi/sonrası)
curl -X POST http://localhost:8765/api/v1/models/fim \
  -H "Content-Type: application/json" \
  -d '{"prefix": "def fibonacci(n):\\n    if n <= 1:", "suffix": "    return fib", "max_tokens": 100}'

# Sohbet
curl -X POST http://localhost:8765/api/v1/models/chat \
  -H "Content-Type: application/json" \
  -d '{"model_id": "deepseek-coder", "prompt": "Python ile async HTTP sunucusu nasıl yazılır?"}'
```

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────┐
│                    YontAI API                         │
│                    FastAPI + Uvicorn                   │
├─────────┬───────────┬────────────┬───────────────────┤
│  MLX    │  Ollama   │  llama.cpp │   Transformers     │
│ Runtime │  Client   │  (future)  │   Runtime          │
├─────────┴───────────┴────────────┴───────────────────┤
│              Model Orchestrator                       │
│     Hızlı (1-3B) · Akıllı (7-16B) · Derin (>16B)     │
│              LRU Cache · Bellek Yönetimi              │
├─────────────────────────────────────────────────────┤
│              RAG Context Engine                       │
│    tree-sitter AST · ChromaDB · Dinamik Bağlam       │
├─────────────────────────────────────────────────────┤
│              Prompt Templates                         │
│    FIM · Chat · Test · Refactoring · Türkçe          │
└─────────────────────────────────────────────────────┘
```

### Model Katmanı

| Katman | Model Boyutu | Backend | Sıcaklık | Kullanım |
|--------|-------------|---------|---------|----------|
| **Hızlı (Fast)** | 1-3B parametre | MLX | 0.1 | FIM, satır tamamlama, import ekleme |
| **Akıllı (Smart)** | 7-16B parametre | MLX / Ollama | 0.3 | Sohbet, refactoring, kod inceleme |
| **Derin (Large)** | >16B parametre | Ollama | 0.5 | Derin analiz, dökümantasyon |

### Kod Bağlam Motoru (RAG)

```
Proje Dizini → tree-sitter AST → Fonksiyon/Sınıf Çıkarma
                                   ↓
    Sorgu ← ChromaDB vektör arama ← Embedding (all-MiniLM-L6-v2)
       ↓
    Dinamik Prompt Bağlamı → LLM → Akıllı Tamamlama
```

**Desteklenen Diller:** Python, JavaScript, TypeScript, Rust, Go, Java, C/C++, Ruby, PHP, Swift, Kotlin, Scala (17 dil)

---

## 📡 API Dokümantasyonu

### 🎯 Model Yönetimi

| Metod | Endpoint | Açıklama |
|-------|----------|----------|
| `GET` | `/api/v1/models` | Tüm modelleri listele |
| `POST` | `/api/v1/models` | Yeni model kaydet |
| `GET` | `/api/v1/models/{id}` | Model detayı |
| `DELETE` | `/api/v1/models/{id}` | Model sil |
| `PATCH` | `/api/v1/models/{id}` | Model güncelle |
| `POST` | `/api/v1/models/{id}/analyze` | Model analizi |

### 🤖 MLX Modelleri

| Metod | Endpoint | Açıklama |
|-------|----------|----------|
| `GET` | `/api/v1/models/mlx/list` | MLX modellerini listele |
| `POST` | `/api/v1/models/mlx/load` | MLX modelini belleğe yükle |
| `POST` | `/api/v1/models/mlx/unload` | MLX modelini bellekten boşalt |
| `POST` | `/api/v1/models/mlx/convert` | HF modelini MLX'e dönüştür |
| `GET` | `/api/v1/models/mlx/info` | MLX model bilgisi |

### 💬 Kod Tamamlama

| Metod | Endpoint | Açıklama |
|-------|----------|----------|
| `POST` | `/api/v1/models/complete` | Metin tamamlama (hızlı model) |
| `POST` | `/api/v1/models/fim` | Fill-in-the-Middle kod tamamlama |
| `POST` | `/api/v1/models/chat` | Sohbet tamamlama (akıllı model) |

### 🔍 RAG / Bağlam

| Metod | Endpoint | Açıklama |
|-------|----------|----------|
| `POST` | `/api/v1/rag/index` | Proje indeksle |
| `POST` | `/api/v1/rag/search` | Kod ara |
| `POST` | `/api/v1/rag/context` | Prompt bağlamı oluştur |

### 🖥️ Sistem

| Metod | Endpoint | Açıklama |
|-------|----------|----------|
| `GET` | `/api/v1/system/health` | Sağlık kontrolü |
| `GET` | `/api/v1/system/hardware` | Donanım profili |
| `GET` | `/api/v1/system/info` | Sistem bilgisi |

### 📦 Diğer

| Metod | Endpoint | Açıklama |
|-------|----------|----------|
| `GET` | `/api/v1/projects` | Projeleri listele |
| `POST` | `/api/v1/projects` | Proje oluştur |
| `GET` | `/api/v1/datasets` | Verisetlerini listele |
| `POST` | `/api/v1/training/start` | Eğitim başlat |
| `GET` | `/api/v1/benchmarks/runs` | Benchmark sonuçları |
| `POST` | `/api/v1/jobs` | İş oluştur |

---

## 🔧 Yapılandırma

`.env` dosyası:

```env
YONTAI_ENV=development
YONTAI_HOST=127.0.0.1
YONTAI_PORT=8765
YONTAI_DATABASE_URL=sqlite:///./yontai.db
YONTAI_OLLAMA_HOST=http://127.0.0.1:11434
```

---

## 🧪 Test

```bash
cd apps/backend

# Tüm testleri çalıştır
pytest tests/ -v

# Belirli testleri çalıştır
pytest tests/test_health.py -v
pytest tests/test_model_chat.py -v
```

Test sonuçları: **✅ 8/8 passed**

---

## 📊 Performans (M1 Pro 16 GB)

| Model | Quantization | Token/s | RAM Kullanımı |
|-------|-------------|---------|---------------|
| DeepSeek-Coder 1.3B | Q4 | ~45-55 | ~2.5 GB |
| DeepSeek-Coder 6.7B | Q4 | ~15-22 | ~8 GB |
| CodeQwen-7B | Q4 | ~12-18 | ~7 GB |
| StarCoder2-3B | Q4 | ~30-40 | ~4 GB |
| FIM (1.3B) | Q4 | <200ms | ~2.5 GB |

---

## 📁 Proje Yapısı

```
YontAI/
├── apps/
│   ├── backend/
│   │   └── yontai/
│   │       ├── api/routes/       # API endpoint'leri
│   │       ├── core/             # Konfigürasyon, donanım, güvenlik
│   │       ├── db/               # Veritabanı modelleri
│   │       ├── integrations/     # MLX, Ollama entegrasyonları
│   │       ├── models/           # Model kaydı, orkestratör
│   │       ├── rag/              # RAG bağlam motoru
│   │       ├── runtime/          # MLX, HF, PEFT runtime'ları
│   │       └── training/         # LoRA eğitimi
│   └── desktop/                  # Tauri masaüstü uygulaması
├── models/                       # İndirilen modeller
├── datasets/                     # Verisetleri
└── exports/                      # Dışa aktarımlar
```

---

## 🤝 Katkıda Bulunma

1. Fork et
2. Feature branch oluştur (`git checkout -b feature/yeni-ozellik`)
3. Değişiklikleri commit et (`git commit -m 'feat: yeni özellik'`)
4. Branch'i push et (`git push origin feature/yeni-ozellik`)
5. Pull Request aç

### Commit Mesajı Formatı

```
feat: yeni özellik
fix: hata düzeltmesi
docs: dökümantasyon güncellemesi
refactor: kod iyileştirmesi
perf: performans iyileştirmesi
test: test ekleme/düzeltme
```

---

## 🗺️ Geliştirme Yol Haritası

- [x] **Faz 1** — MLX entegrasyonu, FIM tamamlama, model dönüşümü ✅
- [x] **Faz 2** — RAG bağlam motoru, kod indeksleme ✅
- [x] **Faz 3** — Çoklu model orkestrasyonu, bellek optimizasyonu ✅
- [x] **Faz 4** — Prompt şablonları, API iyileştirmeleri ✅
- [ ] **Faz 5** — VS Code eklentisi
- [ ] **Faz 6** — Kullanıcı alışkanlıklarından öğrenen prompt adaptasyonu
- [ ] **Faz 7** — DeepSeek V4 Flash entegrasyonu (yayınlandığında)

---

## 📝 Lisans

MIT License — Detaylar için [LICENSE](LICENSE) dosyasına bakın.

---

<a name="english"></a>
## 🇬🇧 English

**YontAI** is a privacy-first, local AI coding assistant optimized for Apple Silicon (M1/M2/M3/M4). It combines MLX, Ollama, and llama.cpp backends in a unified interface, understands project context (RAG), and provides intelligent code completion (FIM).

> 🚀 **Optimized for M1 Pro 16 GB**. Up to 40% speed improvement on GPU with quantized models!

### Key Features

| Feature | Description |
|---------|-------------|
| **MLX Support** | Apple Silicon-optimized MLX format model inference |
| **Multi-Model** | Tiered strategy: Fast (1-3B FIM) + Smart (7-16B chat) |
| **FIM Completion** | DeepSeek-Coder Fill-in-the-Middle format |
| **RAG Context** | tree-sitter + ChromaDB for code indexing and smart context retrieval |
| **HF → MLX** | One-click HuggingFace to MLX conversion |
| **LRU Cache** | 16 GB RAM optimized with automatic model unloading |
| **Ollama Compatible** | Full Ollama compatibility for existing models |
| **Turkish Prompts** | Turkish code explanation, testing, refactoring templates |

### Quick Start

```bash
git clone https://github.com/WeAreTheArtMakers/YontAI.git
cd YontAI/apps/backend
pip install -e ".[mlx,rag]"

# Start backend
uvicorn yontai.main:app --host 127.0.0.1 --port 8765 --reload
```

### Tech Stack

```
Frontend:    React 18 · TypeScript · TailwindCSS · shadcn/ui
Desktop:     Tauri v2 (Rust)
Backend:     FastAPI · Python 3.11+ · SQLAlchemy · Alembic
AI Runtime:  MLX · 🤗 Transformers · PEFT · TRL · Unsloth
Vector DB:   ChromaDB
Database:    SQLite