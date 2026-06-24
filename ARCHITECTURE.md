# YontAI Mimari Analiz ve Geliştirme Raporu

> **Hedef:** YontAI'yi "Cursor benzeri IDE" değil, kullanıcının kendi coding AI modelini oluşturduğu, eğittiği ve geliştirdiği **yerel AI mühendislik laboratuvarı** seviyesine çıkarmak.
>
> **Platform:** Apple Silicon M1 Pro (16 GB RAM)
> **Mevcut Durum:** Tauri v2 masaüstü uygulaması + Python FastAPI backend

---

## İçindekiler

1. [Mevcut Mimari Analizi](#1-mevcut-mimari-analizi)
2. [VS Code Extension Mimarisi](#2-vs-code-extension-mimarisi)
3. [FIM (Fill-in-the-Middle) Sistemi](#3-fim-sistemi)
4. [Context Engine (RAG + AST + Memory Graph)](#4-context-engine)
5. [İnternetten Kod Toplama Sistemi](#5-internet-kod-toplama)
6. [Multi-Model Orchestration](#6-multi-model-orchestration)
7. [User Model Training System (AI Lab)](#7-user-model-training)
8. [VS Code UX Geliştirmeleri](#8-vs-code-ux)
9. [Prompt Engineering Mimarisi](#9-prompt-engineering)
10. [Geliştirme Fazları ve Timeline](#10-gelistirme-fazlari)

---

## 1. Mevcut Mimari Analizi

### Mevcut Yapı

```
┌──────────────────────────────────────────────────────────┐
│                    Tauri v2 Desktop                       │
│  React 18 + TypeScript + Vite 6 + TailwindCSS            │
│  Zustand (state) + TanStack Query (data fetching)        │
│  Tek sayfa monolithic App.tsx (3071 satır)               │
│  ❌ Router yok, ❌ Code editor yok, ❌ Streaming yok      │
├──────────────────────────────────────────────────────────┤
│                    HTTP REST (port 8765)                  │
├──────────────────────────────────────────────────────────┤
│                 Python FastAPI Backend                    │
│  Yeni: MLX Runtime + RAG Engine + Orchestrator          │
│  Mevcut: LoRA training, Dataset, Benchmark, Export       │
└──────────────────────────────────────────────────────────┘
```

### Kritik Tasarım Hataları

| # | Sorun | Etki | Çözüm |
|---|-------|------|-------|
| 1 | **App.tsx 3071 satır** | Bakım kabusu, ölçeklenemez | React Router + Lazy loading |
| 2 | **Chat sync/blocking** | Kullanıcı bloke olur | SSE streaming implementasyonu |
| 3 | **No code editor** | FIM/autocomplete test edilemez | Monaco Editor entegrasyonu |
| 4 | **No local state persistence** | Sayfa yenilenince kaybolur | Zustand persist middleware |
| 5 | **API client'da streaming yok** | Job events poll-based | SSE event source pattern |
| 6 | **Mono repo management zayıf** | pnpm workspace var ama kullanılmıyor | TurboRepo + workspace script |

### Ölçeklenebilirlik Sorunları

1. **Model yönetimi monolithic:** `ModelRegistryService` 697 satır, tüm logic tek sınıfta
2. **Router flat:** Tüm route'lar tek dosyada, middleware yok
3. **No caching layer:** API yanıtları cache'lenmiyor
4. **No background task queue:** Job worker basit asyncio task

---

## 2. VS Code Extension Mimarisi

### Extension Yapısı (Önerilen)

```
yontai-vscode/
├── package.json              # VS Code extension manifest
├── src/
│   ├── extension.ts          # Activation entry point
│   ├── completion/
│   │   ├── provider.ts       # InlineCompletionItemProvider
│   │   └── fim.ts            # FIM request builder
│   ├── chat/
│   │   ├── panel.ts          # Webview chat panel
│   │   └── provider.ts       # ChatViewProvider
│   ├── commands/
│   │   ├── explain.ts        # YontAI: Kodu Açıkla
│   │   ├── test.ts           # YontAI: Test Yaz
│   │   ├── refactor.ts       # YontAI: Refactor Et
│   │   ├── train.ts          # YontAI: Model Eğit
│   │   └── knowledge.ts      # YontAI: Bilgi Güncelle
│   ├── context/
│   │   ├── open-file.ts      # Açık dosya bağlamı
│   │   ├── workspace.ts      # Workspace indeksleme
│   │   └── snippet.ts        # Kod snippet yöneticisi
│   ├── api/
│   │   └── client.ts         # YontAI backend API client
│   └── utils/
│       └── tokenizer.ts      # Token sayma/kesme
└── test/
    └── extension.test.ts
```

### Activation Events

```json
// package.json
{
  "activationEvents": [
    "onLanguage:python",
    "onLanguage:javascript",
    "onLanguage:typescript",
    "onLanguage:rust",
    "onLanguage:go",
    "onStartupFinished"
  ],
  "contributes": {
    "commands": [
      {
        "command": "yontai.explainCode",
        "title": "YontAI: Kodu Açıkla"
      },
      {
        "command": "yontai.generateTests",
        "title": "YontAI: Test Yaz"
      },
      {
        "command": "yontai.refactorCode",
        "title": "YontAI: Kodu Refactor Et"
      },
      {
        "command": "yontai.addTypeHints",
        "title": "YontAI: Tip İpuçları Ekle"
      },
      {
        "command": "yontai.reviewCode",
        "title": "YontAI: Kod İncelemesi Yap"
      },
      {
        "command": "yontai.findBugs",
        "title": "YontAI: Hata Ara"
      },
      {
        "command": "yontai.chat",
        "title": "YontAI: Sohbet"
      },
      {
        "command": "yontai.trainModel",
        "title": "YontAI: Model Eğit"
      },
      {
        "command": "yontai.updateKnowledge",
        "title": "YontAI: Bilgi Güncelle"
      }
    ],
    "keybindings": [
      {
        "command": "yontai.chat",
        "key": "ctrl+shift+space",
        "mac": "cmd+shift+space"
      }
    ]
  }
}
```

### Extension Entry Point (extension.ts)

```typescript
import * as vscode from 'vscode';
import { YontAICompletionProvider } from './completion/provider';
import { YontAIChatPanel } from './chat/panel';
import { YontAIContextEngine } from './context/workspace';
import { YontAIAPI } from './api/client';

let api: YontAIAPI;
let contextEngine: YontAIContextEngine;

export async function activate(context: vscode.ExtensionContext) {
    console.log('YontAI activating...');

    // 1. Backend API client
    api = new YontAIAPI('http://127.0.0.1:8765/api/v1');

    // 2. Context engine (RAG + workspace index)
    contextEngine = new YontAIContextEngine(api);
    contextEngine.startWatching();

    // 3. Inline completion provider (FIM)
    const completionProvider = vscode.languages.registerInlineCompletionItemProvider(
        { pattern: '**' },
        new YontAICompletionProvider(api, contextEngine)
    );
    context.subscriptions.push(completionProvider);

    // 4. Chat panel (webview)
    const chatPanel = new YontAIChatPanel(context, api, contextEngine);
    context.subscriptions.push(chatPanel);

    // 5. Commands
    context.subscriptions.push(
        vscode.commands.registerCommand('yontai.explainCode', () => executeCodeAction('explain')),
        vscode.commands.registerCommand('yontai.generateTests', () => executeCodeAction('test')),
        vscode.commands.registerCommand('yontai.refactorCode', () => executeCodeAction('refactor')),
        vscode.commands.registerCommand('yontai.addTypeHints', () => executeCodeAction('typehints')),
        vscode.commands.registerCommand('yontai.reviewCode', () => executeCodeAction('review')),
        vscode.commands.registerCommand('yontai.findBugs', () => executeCodeAction('bugs')),
        vscode.commands.registerCommand('yontai.chat', () => chatPanel.show()),
        vscode.commands.registerCommand('yontai.trainModel', () => openTrainingUI()),
        vscode.commands.registerCommand('yontai.updateKnowledge', () => updateKnowledge()),
    );

    // 6. Status bar
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.text = "$(rocket) YontAI";
    statusBar.tooltip = "YontAI - Yerel AI Kod Asistanı";
    statusBar.command = 'yontai.chat';
    statusBar.show();
    context.subscriptions.push(statusBar);

    async function executeCodeAction(action: string) {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        const selection = editor.selection;
        const code = editor.document.getText(selection.isEmpty ? undefined : selection);
        const language = editor.document.languageId;

        // RAG context ekle
        const context = await contextEngine.getContext(code);
        
        // Backend'e gönder
        const response = await api.codeAction(action, code, language, context);
        
        // Sonucu yeni doküman veya snippet olarak göster
        const doc = await vscode.workspace.openTextDocument({
            content: response,
            language: 'markdown'
        });
        await vscode.window.showTextDocument(doc, vscode.ViewColumn.Beside);
    }

    async function openTrainingUI() {
        const panel = vscode.window.createWebviewPanel(
            'yontaiTraining',
            'YontAI - Model Eğitimi',
            vscode.ViewColumn.One,
            { enableScripts: true }
        );
        panel.webview.html = getTrainingWebviewContent();
    }

    async function updateKnowledge() {
        const url = await vscode.window.showInputBox({
            prompt: 'GitHub repo URL veya npm paket adı',
            placeHolder: 'ör: https://github.com/user/repo veya react'
        });
        if (!url) return;
        
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'YontAI: Bilgi güncelleniyor...',
            cancellable: true
        }, async () => {
            await api.ingestKnowledge(url);
            vscode.window.showInformationMessage('✅ Bilgi başarıyla güncellendi!');
        });
    }
}

export function deactivate() {
    contextEngine?.dispose();
}
```

### Inline Completion Provider (FIM)

```typescript
// completion/provider.ts
import * as vscode from 'vscode';
import { YontAIAPI } from '../api/client';
import { YontAIContextEngine } from '../context/workspace';

export class YontAICompletionProvider implements vscode.InlineCompletionItemProvider {
    private debounceTimer: NodeJS.Timeout | undefined;

    constructor(
        private api: YontAIAPI,
        private contextEngine: YontAIContextEngine
    ) {}

    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        // Debounce: 150ms içinde yeni istek gelirse öncekini iptal et
        return new Promise((resolve) => {
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }
            this.debounceTimer = setTimeout(async () => {
                try {
                    const result = await this.getCompletion(document, position, token);
                    resolve(result);
                } catch {
                    resolve(undefined);
                }
            }, 50); // 50ms debounce
        });
    }

    private async getCompletion(
        document: vscode.TextDocument,
        position: vscode.Position,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        // İmleç öncesi/sonrası metni al
        const lineUntilCursor = document.lineAt(position.line).text.substring(0, position.character);
        const lineAfterCursor = document.lineAt(position.line).text.substring(position.character);
        
        // Prefix: imlece kadar olan tüm metin
        const prefix = document.getText(
            new vscode.Range(new vscode.Position(0, 0), position)
        );
        
        // Suffix: imleçten sonraki metin (max 500 karakter)
        const suffix = document.getText(
            new vscode.Range(position, new vscode.Position(
                Math.min(position.line + 20, document.lineCount - 1),
                document.lineAt(Math.min(position.line + 20, document.lineCount - 1)).text.length
            ))
        ).substring(0, 500);

        // Token limit: 2048
        if (prefix.length + suffix.length > 8000) {
            const excess = (prefix.length + suffix.length) - 8000;
            const trimmedPrefix = prefix.substring(excess);
            return this.callFIM(trimmedPrefix, suffix, token);
        }

        return this.callFIM(prefix, suffix, token);
    }

    private async callFIM(
        prefix: string,
        suffix: string,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        try {
            const response = await this.api.fim(prefix, suffix, {
                maxTokens: 128,
                temperature: 0.1,
                timeout: 2000 // 2s timeout
            });

            if (token.isCancellationRequested) return undefined;

            // Yanıtı satırlara böl
            const lines = response.split('\n');
            if (lines.length === 0) return undefined;

            return [
                new vscode.InlineCompletionItem(
                    response,
                    new vscode.Range(
                        // İmleç pozisyonundan itibaren
                        vscode.window.activeTextEditor?.selection.active || new vscode.Position(0, 0),
                        // Tahmin edilen bitiş pozisyonu
                        new vscode.Position(
                            (vscode.window.activeTextEditor?.selection.active.line || 0) + lines.length - 1,
                            lines[lines.length - 1].length
                        )
                    )
                )
            ];
        } catch (error) {
            console.error('FIM error:', error);
            return undefined;
        }
    }
}
```

---

## 3. FIM Sistemi

### FIM Engine Mimarisi

```
Kullanıcı yazıyor
    │
    ▼
VS Code onChange event (50ms debounce)
    │
    ├── Prefix extraction (cursor'a kadar)
    ├── Suffix extraction (cursor'dan sonra, max 500 char)
    └── Context assembly (RAG + open tabs)
    │
    ▼
Token trimming (max 2048 token)
    │
    ▼
Prompt oluşturma:
<|fim_begin|>{prefix}<|fim_hole|>{suffix}<|fim_end|>
    │
    ▼
Model Routing (Intent Classification):
    ├── Kod mu? → FIM model (1-3B MLX) ← 150ms hedef
    ├── Yorum mu? → Chat model (7B MLX)
    └── Doğal dil mi? → Chat model
    │
    ▼
Generation (streaming):
    ├── MLX: MLXRuntime.generate() - Apple Silicon native
    └── Ollama: OllamaClient.generate() - fallback
    │
    ▼
Post-processing:
    ├── Stop string temizliği (<|fim_end|>, <|endoftext|>)
    ├── Indentation düzeltme
    └── Syntax validation (opsiyonel)
    │
    ▼
VS Code InlineCompletionItem
```

### Latency Budget (<150ms)

| Aşama | Süre | Açıklama |
|-------|------|----------|
| Context extraction | 5ms | Prefix/suffix hazırlığı |
| RAG query | 15ms | ChromaDB vektör arama |
| Token trimming | 2ms | Token sayma/kesme |
| Prompt build | 1ms | FIM formatına çevirme |
| **Model inference** | **100ms** | MLX 1.3B Q4 ~45 token/s |
| Post-processing | 2ms | Yanıt temizliği |
| Network/overhead | 25ms | HTTP + JSON serialization |
| **Total** | **~150ms** | ✅ Hedef içinde |

### Sliding Window Context Builder (Backend)

```python
# apps/backend/yontai/rag/fim_engine.py
"""FIM engine with sliding window context management."""


class FIMContextBuilder:
    """Sliding window context builder for FIM completions.
    
    Limits context to max_tokens while preserving:
    1. Current file imports (top of file)
    2. Related snippets from RAG
    3. Function signature context
    """
    
    def __init__(self, context_engine: ContextEngine, max_tokens: int = 2048):
        self.context_engine = context_engine
        self.max_tokens = max_tokens
        self._token_estimate_ratio = 4  # chars per token
        
    def build_fim_prompt(
        self,
        prefix: str,
        suffix: str,
        current_file: str | None = None,
    ) -> str:
        """Build FIM prompt with optimal context window."""
        # 1. RAG'den ilgili snippet'leri getir
        rag_context = self._get_relevant_context(prefix, current_file)
        
        # 2. Token budget hesapla
        # 70% prefix, 20% suffix, 10% RAG context
        total_chars = self.max_tokens * self._token_estimate_ratio
        
        # 3. Sliding window: prefix'i kısalt
        prefix_chars = int(total_chars * 0.70)
        if len(prefix) > prefix_chars:
            # En yakın fonksiyon başlangıcını bul
            prefix = self._trim_to_nearest_function(prefix, prefix_chars)
        
        # 4. Suffix'i kısalt
        suffix_chars = int(total_chars * 0.20)
        if len(suffix) > suffix_chars:
            suffix = suffix[:suffix_chars]
        
        # 5. RAG context
        rag_chars = int(total_chars * 0.10)
        if len(rag_context) > rag_chars:
            rag_context = rag_context[:rag_chars]
        
        # 6. FIM prompt'u oluştur
        parts = []
        if rag_context:
            parts.append(f"// Bağlam:\n{rag_context}\n")
        parts.append(f"<|fim_begin|>{prefix}<|fim_hole|>{suffix}<|fim_end|>")
        
        return "\n".join(parts)
    
    def _trim_to_nearest_function(self, text: str, max_chars: int) -> str:
        """En yakın fonksiyon başlangıcını bularak kırp."""
        if len(text) <= max_chars:
            return text
        
        trimmed = text[-max_chars:]
        
        # Fonksiyon/sınıf başlangıcını bul
        import re
        matches = list(re.finditer(
            r'^(def |class |function |func |async def |pub fn )',
            trimmed,
            re.MULTILINE
        ))
        
        if matches:
            # İkinci fonksiyon başlangıcına kadar al (bağlam için)
            if len(matches) >= 2:
                return trimmed[matches[-2].start():]
            return trimmed[matches[-1].start():]
        
        return trimmed
```

---

## 4. Context Engine

### RAG + AST + Memory Graph Mimarisi

```
Kullanıcı Sorgusu
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                    Context Engine                      │
├──────────────────────────────────────────────────────┤
│                                                        │
│  1. Intent Classification                              │
│     ├── completion?  → FIM pipeline                    │
│     ├── question?    → RAG search + chat               │
│     └── command?     → Code action pipeline            │
│                                                        │
│  2. Context Assembly                                   │
│     ├── Açık dosya: imports + fonksiyon imzaları       │
│     ├── Workspace: AST index → ilgili snippet'ler     │
│     ├── RAG: ChromaDB vektör arama (top 5)            │
│     ├── Memory Graph: dependency-aware retrieval       │
│     └── History: son 10 interaction                   │
│                                                        │
│  3. Priority Scoring                                   │
│     ├── Dosya skoru: açık dosya > workspace > RAG      │
│     ├── Token budget: 4096 toplam                      │
│     └── Dedup: aynı snippet'i tekrar ekleme           │
│                                                        │
└──────────────────────────────────────────────────────┘
    │
    ▼
Dynamic Prompt (Context + Query)
```

### Memory Graph Implementation

```python
# apps/backend/yontai/rag/memory_graph.py
"""Project memory graph for dependency-aware context retrieval."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DependencyNode:
    """Proje bağımlılık düğümü."""
    file_path: str
    imports: list[str] = field(default_factory=list)
    exported_symbols: list[str] = field(default_factory=list)
    used_by: list[str] = field(default_factory=list)  # reverse dependency
    depends_on: list[str] = field(default_factory=list)  # forward dependency
    last_modified: float = 0.0
    size_bytes: int = 0


class ProjectMemoryGraph:
    """Proje bağımlılık grafı.
    
    Hangi dosyanın hangi dosyayı import ettiğini takip eder.
    Sorgu anında sadece ilgili dosyayı değil, onun bağımlı
    olduğu dosyaları da context'e ekler.
    """
    
    def __init__(self):
        self._nodes: dict[str, DependencyNode] = {}
        self._symbol_index: dict[str, list[str]] = defaultdict(list)  # symbol -> [files]
    
    def add_file(self, file_path: str, imports: list[str], exports: list[str]) -> None:
        """Dosyayı grafa ekle."""
        path = Path(file_path).resolve()
        rel_path = str(path)
        
        node = DependencyNode(
            file_path=rel_path,
            imports=imports,
            exported_symbols=exports,
            last_modified=path.stat().st_mtime if path.exists() else 0,
            size_bytes=path.stat().st_size if path.exists() else 0,
        )
        
        # Import'ları çözümle
        for imp in imports:
            resolved = self._resolve_import(rel_path, imp)
            if resolved:
                node.depends_on.append(resolved)
        
        self._nodes[rel_path] = node
        
        # Symbol index'i güncelle
        for symbol in exports:
            self._symbol_index[symbol].append(rel_path)
    
    def get_context_for_file(
        self,
        file_path: str,
        max_files: int = 5,
    ) -> list[str]:
        """Bir dosya için context olarak eklenmesi gereken dosyaları döndür.
        
        Öncelik:
        1. Dosyanın import ettiği dosyalar (direct dependencies)
        2. Dosyayı import eden dosyalar (reverse dependencies)
        3. Aynı modüldeki kardeş dosyalar
        """
        path = Path(file_path).resolve()
        rel_path = str(path)
        
        if rel_path not in self._nodes:
            return []
        
        node = self._nodes[rel_path]
        context_files: list[str] = []
        seen = {rel_path}
        
        # 1. Direct dependencies (import ettikleri)
        for dep in node.depends_on:
            if dep not in seen and len(context_files) < max_files:
                context_files.append(dep)
                seen.add(dep)
        
        # 2. Reverse dependencies (onu import edenler)
        for dep in node.used_by:
            if dep not in seen and len(context_files) < max_files:
                context_files.append(dep)
                seen.add(dep)
        
        # 3. Aynı dizindeki dosyalar
        parent = path.parent
        if parent.exists():
            for sibling in parent.iterdir():
                if sibling.is_file() and sibling.suffix in ('.py', '.ts', '.js', '.rs'):
                    sib_path = str(sibling.resolve())
                    if sib_path not in seen and len(context_files) < max_files:
                        context_files.append(sib_path)
                        seen.add(sib_path)
        
        return context_files
    
    def search_by_symbol(self, symbol: str) -> list[str]:
        """Bir sembolün tanımlandığı dosyaları bul."""
        return self._symbol_index.get(symbol, [])
    
    def _resolve_import(self, current_file: str, import_stmt: str) -> str | None:
        """Import ifadesini dosya yoluna çözümle."""
        # Basit çözümleme: import X → X.py
        # Gerçek implementasyon tree-sitter ile yapılmalı
        current = Path(current_file)
        project_root = current.parent
        
        # Göreceli import
        if import_stmt.startswith('.'):
            parts = import_stmt.split('.')
            depth = len(parts) - 1
            base = current.parent
            for _ in range(depth):
                base = base.parent
            module_name = parts[-1]
            if module_name:
                return str(base / f"{module_name}.py")
        
        # Mutlak import
        for py_path in project_root.rglob(f"{import_stmt.split('.')[0]}.py"):
            return str(py_path)
        
        return None
```

---

## 5. İnternetten Kod Toplama Sistemi

### End-to-End Pipeline

```
Kullanıcı: "React 2026 best practices"
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│                 Web Fetcher Module                        │
├──────────────────────────────────────────────────────────┤
│  1. Intent Classification                                 │
│     ├── GitHub URL? → GitHub API crawler                  │
│     ├── npm package? → npm registry + GitHub source       │
│     ├── PyPI package? → PyPI + GitHub source              │
│     └── Free text? → Google search + GitHub search        │
│                                                           │
│  2. Fetch & Parse                                         │
│     ├── GitHub: /repos/{owner}/{repo}/contents            │
│     ├── npm: registry.npmjs.org/{package}                 │
│     ├── PyPI: pypi.org/pypi/{package}/json                │
│     └── Web: HTTP GET + HTML parse (beautifulsoup4)       │
│                                                           │
│  3. Code Extraction                                       │
│     ├── .py, .js, .ts, .jsx, .tsx, .rs, .go dosyaları    │
│     ├── README.md (dökümantasyon)                         │
│     └── Örnek kod blokları                                │
│                                                           │
│  4. Cleaning & Sanitization                               │
│     ├── Yorum satırlarını temizle (opsiyonel)             │
│     ├── Gereksiz dosyaları filtrele (test, build, dist)   │
│     ├── Deduplication (hash-based)                        │
│     └── Boyut limiti: max 100MB / sorgu                  │
│                                                           │
│  5. Chunking & Embedding                                  │
│     ├── Chunk: fonksiyon/sınıf bazında (tree-sitter)      │
│     ├── Embed: all-MiniLM-L6-v2 (384 dim)                │
│     ├── Store: ChromaDB veya LanceDB                     │
│     └── Metadata: source, language, license              │
│                                                           │
│  6. Training Dataset                                      │
│     ├── Instruction format: {instruction, input, output}  │
│     ├── FIM samples: {prefix, suffix, middle}            │
│     ├── Chat samples: {messages: [{role, content}]}      │
│     └── Export: JSONL format                             │
│                                                           │
└──────────────────────────────────────────────────────────┘
    │
    ▼
Vector DB ← RAG Pipeline 
    │
    ├── Sorgu anında kullan
    └── Veya training dataset'i olarak kullan → LoRA eğitimi
```

### Web Fetcher Implementation

```python
# apps/backend/yontai/knowledge/web_fetcher.py
"""Internet code ingestion system."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class FetchedCode:
    """İnternetten çekilen kod parçası."""
    source_url: str
    file_path: str
    content: str
    language: str
    license_info: str | None = None
    stars: int = 0
    hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionResult:
    """İndeksleme sonucu."""
    total_files: int = 0
    total_chunks: int = 0
    total_tokens: int = 0
    errors: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


class WebFetcher:
    """İnternetten kod çekme motoru.
    
    Desteklenen kaynaklar:
    - GitHub reposu (public)
    - npm paketleri
    - PyPI paketleri
    - Herhangi bir URL (HTML parse)
    """
    
    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "YontAI/1.0 (code ingestion)"}
        )
        self._temp_dir = Path(tempfile.mkdtemp(prefix="yontai_knowledge_"))
        
        # Desteklenen dosya uzantıları
        self._code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.rs', '.go',
            '.java', '.c', '.cpp', '.h', '.hpp', '.rb', '.php',
            '.swift', '.kt', '.scala', '.sh', '.bash', '.yml',
            '.yaml', '.json', '.toml', '.css', '.scss', '.html',
        }
        
        # Dışlanacak dizinler
        self._exclude_dirs = {
            'node_modules', '.git', '__pycache__', '.venv', 'venv',
            'dist', 'build', '.next', '.nuxt', 'target', 'vendor',
            '.DS_Store', 'env', '.env', 'migrations', '.pytest_cache',
            'test', 'tests', '__tests__', 'spec', 'e2e',
        }
    
    async def fetch_from_url(self, url: str) -> list[FetchedCode]:
        """Bir URL'den kod çek.
        
        Args:
            url: GitHub repo, npm package, PyPI package veya web sayfası
            
        Returns:
            FetchedCode listesi
        """
        parsed = urlparse(url)
        
        if 'github.com' in parsed.netloc:
            return await self._fetch_github(url)
        elif 'npmjs.com' in parsed.netloc or parsed.path.startswith('/package/'):
            return await self._fetch_npm(url)
        elif 'pypi.org' in parsed.netloc:
            return await self._fetch_pypi(url)
        else:
            return await self._fetch_webpage(url)
    
    async def search_and_fetch(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[FetchedCode]:
        """Arama sorgusuyla kod bul ve çek.
        
        Önce GitHub API'de ara, sonra npm/PyPI'de ara.
        """
        results: list[FetchedCode] = []
        
        # GitHub'da ara
        try:
            gh_results = await self._search_github(query, max_results)
            results.extend(gh_results)
        except Exception as exc:
            logger.warning("GitHub arama hatası: %s", exc)
        
        # npm'de ara (JavaScript/TypeScript)
        try:
            npm_results = await self._search_npm(query, max_results)
            results.extend(npm_results)
        except Exception as exc:
            logger.warning("npm arama hatası: %s", exc)
        
        # PyPI'de ara (Python)
        try:
            pypi_results = await self._search_pypi(query, max_results)
            results.extend(pypi_results)
        except Exception as exc:
            logger.warning("PyPI arama hatası: %s", exc)
        
        return results
    
    async def _fetch_github(self, url: str) -> list[FetchedCode]:
        """GitHub reposundan kod çek.
        
        GitHub API ile repo içeriğini listele ve
        desteklenen dosyaları indir.
        """
        # URL'den owner/repo çıkar
        match = re.match(r'github\.com[/:]([^/]+)/([^/]+)', url)
        if not match:
            raise ValueError(f"Geçersiz GitHub URL: {url}")
        
        owner, repo = match.group(1), match.group(2)
        repo = repo.replace('.git', '').strip('/')
        
        logger.info("GitHub reposu çekiliyor: %s/%s", owner, repo)
        
        # Repo içeriğini listele
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        response = await self._client.get(api_url)
        
        if response.status_code == 404:
            # main değilse master dene
            api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1"
            response = await self._client.get(api_url)
        
        response.raise_for_status()
        data = response.json()
        
        files: list[FetchedCode] = []
        for item in data.get('tree', []):
            if item['type'] != 'blob':
                continue
            
            path = item['path']
            ext = Path(path).suffix.lower()
            
            # Dil ve exclude kontrolü
            if ext not in self._code_extensions:
                continue
            if any(excluded in path.split('/') for excluded in self._exclude_dirs):
                continue
            
            # Dosyayı indir
            try:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
                file_response = await self._client.get(raw_url)
                
                if file_response.status_code == 404:
                    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{path}"
                    file_response = await self._client.get(raw_url)
                
                if file_response.status_code != 200:
                    continue
                
                content = file_response.text
                file_hash = hashlib.md5(content.encode()).hexdigest()
                
                files.append(FetchedCode(
                    source_url=url,
                    file_path=path,
                    content=content,
                    language=self._detect_language(ext),
                    hash=file_hash,
                    metadata={
                        'repo': f"{owner}/{repo}",
                        'type': 'github',
                    }
                ))
            except Exception as exc:
                logger.debug("Dosya indirme hatası: %s - %s", path, exc)
        
        logger.info("%d dosya çekildi: %s/%s", len(files), owner, repo)
        return files
    
    async def _search_github(self, query: str, max_results: int) -> list[FetchedCode]:
        """GitHub'da kod ara."""
        # Önce repo ara
        search_url = (
            f"https://api.github.com/search/repositories"
            f"?q={query}+language:python+language:javascript+language:typescript"
            f"&sort=stars&order=desc&per_page={min(max_results, 10)}"
        )
        
        response = await self._client.get(search_url)
        response.raise_for_status()
        data = response.json()
        
        results: list[FetchedCode] = []
        for repo in data.get('items', [])[:max_results]:
            try:
                repo_url = repo['html_url']
                files = await self._fetch_github(repo_url)
                for f in files:
                    f.stars = repo.get('stargazers_count', 0)
                    f.license_info = repo.get('license', {}).get('spdx_id')
                results.extend(files[:50])  # Repo başına max 50 dosya
            except Exception as exc:
                logger.debug("Repo çekme hatası: %s - %s", repo.get('full_name'), exc)
        
        return results
    
    async def _fetch_npm(self, url: str) -> list[FetchedCode]:
        """npm paketinden kod çek."""
        # Paket adını çıkar
        package_name = url.rstrip('/').split('/')[-1]
        return await self._fetch_npm_by_name(package_name)
    
    async def _fetch_npm_by_name(self, package_name: str) -> list[FetchedCode]:
        """npm paket adıyla kod çek."""
        logger.info("npm paketi çekiliyor: %s", package_name)
        
        # npm registry'den metadata al
        registry_url = f"https://registry.npmjs.org/{package_name}"
        response = await self._client.get(registry_url)
        response.raise_for_status()
        data = response.json()
        
        # GitHub URL'ini bul
        github_url = None
        if 'repository' in data:
            repo = data['repository']
            if isinstance(repo, dict):
                github_url = repo.get('url', '')
            elif isinstance(repo, str):
                github_url = repo
        
        if github_url and 'github.com' in github_url:
            # GitHub'dan çek
            return await self._fetch_github(github_url)
        
        # npm package'dan tarball indir
        latest_version = data.get('dist-tags', {}).get('latest')
        if not latest_version:
            return []
        
        tarball_url = data.get('versions', {}).get(latest_version, {}).get('dist', {}).get('tarball')
        if not tarball_url:
            return []
        
        # Tarball'ı indir ve çıkar
        response = await self._client.get(tarball_url)
        response.raise_for_status()
        
        # TODO: tar.gz extract et ve dosyaları parse et
        logger.info("npm tarball indirildi: %s", tarball_url)
        return []
    
    async def _search_npm(self, query: str, max_results: int) -> list[FetchedCode]:
        """npm'de paket ara."""
        search_url = (
            f"https://registry.npmjs.org/-/v1/search"
            f"?text={query}&size={min(max_results, 20)}"
        )
        
        response = await self._client.get(search_url)
        response.raise_for_status()
        data = response.json()
        
        results: list[FetchedCode] = []
        for pkg in data.get('objects', [])[:max_results]:
            package = pkg.get('package', {})
            package_name = package.get('name', '')
            try:
                files = await self._fetch_npm_by_name(package_name)
                results.extend(files)
            except Exception as exc:
                logger.debug("npm paket hatası: %s - %s", package_name, exc)
        
        return results
    
    async def _fetch_pypi(self, url: str) -> list[FetchedCode]:
        """PyPI paketinden kod çek."""
        package_name = url.rstrip('/').split('/')[-1]
        return await self._fetch_pypi_by_name(package_name)
    
    async def _fetch_pypi_by_name(self, package_name: str) -> list[FetchedCode]:
        """PyPI paket adıyla kod çek."""
        logger.info("PyPI paketi çekiliyor: %s", package_name)
        
        # PyPI JSON API
        api_url = f"https://pypi.org/pypi/{package_name}/json"
        response = await self._client.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        # GitHub URL'ini bul
        info = data.get('info', {})
        github_url = None
        for url_key in ('project_urls', 'home_page', 'download_url'):
            url_value = info.get(url_key)
            if url_value and 'github.com' in str(url_value):
                github_url = url_value
                break
        
        if github_url:
            return await self._fetch_github(github_url)
        
        # Source distribution indir
        # TODO: sdist indir ve extract et
        return []
    
    async def _search_pypi(self, query: str, max_results: int) -> list[FetchedCode]:
        """PyPI'de paket ara."""
        search_url = (
            f"https://pypi.org/search/"
            f"?q={query}&o=&c=Programming+Language+%3A%3A+Python"
        )
        
        response = await self._client.get(search_url)
        response.raise_for_status()
        
        # HTML parse et ve paket adlarını çıkar
        # TODO: beautifulsoup4 ile parse
        return []
    
    async def _fetch_webpage(self, url: str) -> list[FetchedCode]:
        """Web sayfasından kod örnekleri çek."""
        response = await self._client.get(url)
        response.raise_for_status()
        html = response.text
        
        # Kod bloklarını çıkar (regex ile)
        code_blocks = re.findall(
            r'<pre><code[^>]*class="[^"]*(?:language-)?(\w+)[^"]*"[^>]*>'
            r'(.*?)</code></pre>',
            html,
            re.DOTALL,
        )
        
        files: list[FetchedCode] = []
        for i, (lang, code) in enumerate(code_blocks):
            content = self._unescape_html(code).strip()
            if len(content) < 10:
                continue
            
            file_hash = hashlib.md5(content.encode()).hexdigest()
            files.append(FetchedCode(
                source_url=url,
                file_path=f"web_example_{i}.{lang}",
                content=content,
                language=lang or 'text',
                hash=file_hash,
                metadata={'type': 'web', 'url': url},
            ))
        
        logger.info("%d kod bloğu çekildi: %s", len(files), url)
        return files
    
    async def close(self) -> None:
        """Temizlik."""
        await self._client.aclose()
        # Temp dizini temizle
        import shutil
        if self._temp_dir.exists():
            shutil.rmtree(self._temp_dir)
    
    def _detect_language(self, extension: str) -> str:
        """Dosya uzantısından dil tespiti."""
        mapping = {
            '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
            '.ts': 'typescript', '.tsx': 'typescript', '.rs': 'rust',
            '.go': 'go', '.java': 'java', '.c': 'c', '.cpp': 'cpp',
            '.rb': 'ruby', '.php': 'php', '.swift': 'swift', '.kt': 'kotlin',
            '.scala': 'scala', '.sh': 'bash', '.bash': 'bash',
            '.yml': 'yaml', '.yaml': 'yaml', '.json': 'json',
            '.toml': 'toml', '.css': 'css', '.scss': 'scss', '.html': 'html',
        }
        return mapping.get(extension, 'text')
    
    @staticmethod
    def _unescape_html(text: str) -> str:
        """HTML escape karakterlerini çöz."""
        import html
        return html.unescape(text)
```

### Security Risk Analysis

| Risk | Seviye | Önlem |
|------|--------|-------|
| **Malicious code injection** | Yüksek | Kod çalıştırma, sadece indeksleme. Sandbox environment |
| **API rate limiting** | Orta | GitHub API token, rate limiter, exponential backoff |
| **Large file download** | Orta | 100MB limit, streaming download |
| **Copyright violation** | Yüksek | License check (MIT, Apache, GPL), user warning |
| **Dependency confusion** | Düşük | Package name validation, official registry only |
| **SSRF** | Orta | URL whitelist, internal IP block |

---

## 6. Multi-Model Orchestration

### Model Routing Algorithm

```
Sorgu / İstek
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│                 Intent Classifier                         │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Skor = Σ(ağırlıklı özellikler)                          │
│                                                           │
│  Özellikler:                                              │
│  ├── Dosya boyutu: >500 satır → Deep                     │
│  ├── Sorgu uzunluğu: >200 char → Smart                   │
│  ├── Kod oranı: >%80 kod → Fast (FIM)                    │
│  ├── Doğal dil oranı: >%50 → Smart                       │
│  ├── FIM pattern: imleç var → Fast                       │
│  ├── Komut: "refactor", "test" → Deep                    │
│  └── Karmaşıklık: nested loops → Deep                    │
│                                                           │
│  Threshold:                                               │
│  ├── Skor < 30 → Fast (FIM: 1-3B)                        │
│  ├── Skor 30-70 → Smart (Chat: 7B)                       │
│  └── Skor > 70 → Deep (Refactor: 13-16B)                 │
│                                                           │
└──────────────────────────────────────────────────────────┘
    │
    ▼
Model Selection
    │
    ├── Fast: MLXRuntime (1.3B Q4) → ~45 token/s
    │        Bellek: ~2.5 GB, Her zaman sıcak
    │
    ├── Smart: MLXRuntime (7B Q4) → ~15 token/s
    │        Bellek: ~7 GB, İsteğe bağlı yükle
    │
    └── Deep: OllamaClient (13B Q4) → ~8 token/s
             Bellek: ~12 GB, LRU cache
```

### Router Implementation

```python
# apps/backend/yontai/models/router.py
"""Intent-aware model router."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ModelTier(Enum):
    FAST = "fast"       # 1-3B: FIM, autocomplete
    SMART = "smart"     # 7B: chat, explain
    DEEP = "deep"       # 13-16B: refactor, architecture


class Intent(Enum):
    COMPLETION = "completion"   # FIM
    CHAT = "chat"               # Sohbet
    EXPLAIN = "explain"         # Kod açıklama
    TEST = "test"               # Test yazma
    REFACTOR = "refactor"       # Refactoring
    REVIEW = "review"           # Kod inceleme
    DEBUG = "debug"             # Hata ayıklama
    GENERATE = "generate"       # Kod üretme


@dataclass
class RoutingDecision:
    """Routing kararı."""
    tier: ModelTier
    intent: Intent
    confidence: float
    reason: str


class ModelRouter:
    """Prompt karmaşıklığına göre model routing.
    
    Özellikler:
    - Intent classification
    - Prompt complexity scoring
    - Bellek durumu kontrolü
    - Model availability check
    """
    
    def __init__(self):
        # Complexity patterns
        self._complex_patterns = [
            (r'(refactor|redesign|restructure|migrate)', 30),
            (r'(architecture|design pattern|best practice)', 25),
            (r'(optimize|performance|memory leak)', 20),
            (r'(security|vulnerability|exploit)', 25),
            (r'(test|unit test|integration test)', 15),
            (r'(explain|describe|what does)', 10),
        ]
        
        # Intent patterns
        self._intent_patterns = {
            Intent.COMPLETION: [
                r'^\s*(def |class |function |import |const |let |var )',
                r'^\s*(if |for |while |switch |try )',
            ],
            Intent.EXPLAIN: [
                r'(explain|açıkla|ne işe yarar|nasıl çalışır)',
                r'(what does|how does|why is)',
            ],
            Intent.TEST: [
                r'(test|birim test|unittest|pytest|vitest)',
                r'(test case|assert|expect|should)',
            ],
            Intent.REFACTOR: [
                r'(refactor|düzenle|iyileştir|modernize)',
                r'(clean up|simplify|extract)',
            ],
            Intent.REVIEW: [
                r'(review|incele|feedback|code review)',
                r'(hatal?|bug|issue|problem)',
            ],
        }
    
    def route(
        self,
        prompt: str,
        file_context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Sorguyu analiz et ve uygun model katmanını seç."""
        
        # 1. Intent classification
        intent = self._classify_intent(prompt)
        
        # 2. Complexity scoring
        complexity = self._calculate_complexity(prompt, file_context)
        
        # 3. Tier selection
        if intent == Intent.COMPLETION:
            tier = ModelTier.FAST
            reason = "FIM completion"
        elif complexity > 70:
            tier = ModelTier.DEEP
            reason = f"High complexity ({complexity})"
        elif complexity > 30 or intent in (Intent.REFACTOR, Intent.REVIEW):
            tier = ModelTier.SMART
            reason = f"Medium complexity ({complexity})"
        else:
            tier = ModelTier.FAST
            reason = f"Low complexity ({complexity})"
        
        return RoutingDecision(
            tier=tier,
            intent=intent,
            confidence=min(complexity / 100, 0.95),
            reason=reason,
        )
    
    def _classify_intent(self, prompt: str) -> Intent:
        """Sorgunun niyetini sınıflandır."""
        prompt_lower = prompt.lower()
        
        # Önce FIM kontrolü (imleç context'i var mı?)
        if len(prompt) < 500 and re.search(r'^[\s]*(def |class |import |from |const |function )', prompt_lower):
            return Intent.COMPLETION
        
        # Intent pattern'leri
        for intent, patterns in self._intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, prompt_lower):
                    return intent
        
        # Default: chat
        return Intent.CHAT
    
    def _calculate_complexity(
        self,
        prompt: str,
        file_context: dict[str, Any] | None = None,
    ) -> int:
        """Prompt karmaşıklığını hesapla (0-100)."""
        score = 0
        
        # 1. Uzunluk bazlı
        if len(prompt) > 1000:
            score += 20
        elif len(prompt) > 500:
            score += 10
        
        # 2. Pattern bazlı
        for pattern, points in self._complex_patterns:
            if re.search(pattern, prompt.lower()):
                score += points
        
        # 3. Dosya context'i (opsiyonel)
        if file_context:
            file_size = file_context.get('size', 0)
            if file_size > 5000:
                score += 20
            elif file_size > 2000:
                score += 10
            
            # Çoklu dosya mı?
            if file_context.get('file_count', 1) > 3:
                score += 15
        
        # 4. Kod yoğunluğu
        code_lines = len(re.findall(r'[{}();]', prompt))
        if code_lines > 20:
            score += 10
        elif code_lines > 10:
            score += 5
        
        return min(score, 100)
```

---

## 7. User Model Training System (AI Lab)

### Training Pipeline Architecture

```
Kullanıcı → "React bileşenleri için model eğit"
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│              AI Lab Training Pipeline                     │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  1. Dataset Builder                                       │
│     ├── {insert} Kaynak seçimi (repo / internet / local)  │
│     ├── {insert} Kod çekme ve temizleme                   │
│     ├── {insert} Chunking (fonksiyon/sınıf bazında)      │
│     ├── {insert} Instruction generation (LLM ile)        │
│     ├── {insert} FIM sample generation                   │
│     ├── {insert} Dataset format (JSONL)                  │
│     └── {insert} Dataset validation & dedup              │
│                                                           │
│  2. Model Selection                                       │
│     ├── Base model: DeepSeek-Coder-1.3B (hızlı)          │
│     ├── Base model: DeepSeek-Coder-6.7B (kaliteli)       │
│     └── Quantization: Q4 (16GB için zorunlu)            │
│                                                           │
│  3. LoRA Configuration                                    │
│     ├── rank=16 (düşük bellek)                           │
│     ├── alpha=32                                          │
│     ├── target_modules: q_proj, v_proj (sadece)         │
│     ├── batch_size=1 (16GB için)                         │
│     ├── gradient_accumulation=4                           │
│     └── mixed_precision: bf16                            │
│                                                           │
│  4. Training (MLX)                                        │
│     ├── LoRA adaptörünü eğit (ana model frozen)          │
│     ├── ~500-2000 adım (1-2 saat)                        │
│     ├── Bellek: ~8-10 GB (6.7B Q4 + LoRA)               │
│     └── Checkpoint: her 100 adım                         │
│                                                           │
│  5. Export & Deploy                                       │
│     ├── LoRA weights: ~10 MB                             │
│     ├── Merge opsiyonel                                   │
│     ├── MLX formatında kaydet                             │
│     └── Hemen kullanıma hazır                            │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### MLX Fine-Tune Script

```python
# apps/backend/yontai/training/mlx_lora_trainer.py
"""MLX-based LoRA fine-tuning script for Apple Silicon.

M1 Pro 16 GB için optimize edilmiş LoRA eğitimi.
Ana model 4-bit quantize, LoRA adaptörü fp16.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# MLX
try:
    import mlx.core as mx
    import mlx.nn as nn
    from mlx_lm import load, generate
    from mlx_lm.utils import get_model_path, save_weights
    
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False


@dataclass
class LoRAConfig:
    """LoRA hyperparameters for 16GB RAM."""
    rank: int = 16
    alpha: float = 32.0
    dropout: float = 0.05
    target_modules: list[str] = None
    learning_rate: float = 2e-4
    batch_size: int = 1
    gradient_accumulation_steps: int = 4
    max_steps: int = 1000
    warmup_steps: int = 100
    save_steps: int = 200
    logging_steps: int = 10
    max_seq_length: int = 2048
    use_bf16: bool = True
    
    def __post_init__(self):
        if self.target_modules is None:
            self.target_modules = ["q_proj", "v_proj"]


@dataclass
class TrainingMetrics:
    """Eğitim metrikleri."""
    loss: float = 0.0
    accuracy: float = 0.0
    tokens_per_second: float = 0.0
    current_step: int = 0
    total_steps: int = 0
    elapsed_seconds: float = 0.0
    estimated_completion: str = ""


class MLXLoRATrainer:
    """MLX ile LoRA fine-tuning.
    
    M1 Pro 16 GB için tasarlanmıştır:
    - Model: 4-bit quantize (Q4)
    - LoRA: sadece q_proj, v_proj (düşük bellek)
    - Batch size: 1 + gradient accumulation
    - Mixed precision: bf16
    """
    
    def __init__(
        self,
        model_path: str,
        lora_config: LoRAConfig | None = None,
    ):
        if not MLX_AVAILABLE:
            raise RuntimeError("MLX kurulu değil.")
        
        self.model_path = model_path
        self.lora_config = lora_config or LoRAConfig()
        self._model = None
        self._tokenizer = None
        self._lora_layers: list[nn.Module] = []
        self._optimizer = None
        
    def load_model(self) -> None:
        """Modeli yükle ve LoRA katmanlarını ekle."""
        logger.info("Model yükleniyor: %s", self.model_path)
        
        # 4-bit quantize model yükle
        self._model, self._tokenizer = load(
            self.model_path,
            quantization="q4",  # 4-bit quantization
        )
        
        # LoRA katmanlarını ekle
        self._add_lora_layers()
        
        logger.info("Model yüklendi. LoRA parametreleri: %d", 
                   sum(p.size for p in self._lora_layers))
    
    def _add_lora_layers(self) -> None:
        """Hedef modüllere LoRA adaptörleri ekle."""
        for name, module in self._model.named_modules():
            if any(target in name for target in self.lora_config.target_modules):
                if isinstance(module, nn.Linear):
                    lora = nn.LoRALinear(
                        input_dims=module.input_dims,
                        output_dims=module.output_dims,
                        r=self.lora_config.rank,
                        scale=self.lora_config.alpha / self.lora_config.rank,
                    )
                    self._lora_layers.append(lora)
                    # Orijinal modülü dondur
                    module.freeze()
                    logger.debug("LoRA eklendi: %s (r=%d)", name, self.lora_config.rank)
    
    def train(
        self,
        dataset_path: str,
        output_dir: str,
        progress_callback=None,
    ) -> Path:
        """Eğitimi başlat.
        
        Args:
            dataset_path: JSONL dataset yolu
            output_dir: Çıktı dizini
            progress_callback: İlerleme callback'i (step, metrics) -> None
            
        Returns:
            LoRA ağırlıklarının kaydedildiği dizin
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Dataset'i yükle
        with open(dataset_path) as f:
            dataset = [json.loads(line) for line in f if line.strip()]
        
        logger.info("Eğitim başlıyor: %d örnek, %d adım", 
                   len(dataset), self.lora_config.max_steps)
        
        # Optimizer
        self._optimizer = nn.optimizers.AdamW(
            learning_rate=self.lora_config.learning_rate,
        )
        
        # Training loop
        global_step = 0
        total_loss = 0.0
        start_time = time.time()
        
        for epoch in range(10):  # max 10 epoch
            if global_step >= self.lora_config.max_steps:
                break
            
            for i, example in enumerate(dataset):
                if global_step >= self.lora_config.max_steps:
                    break
                
                # Forward pass
                loss = self._train_step(example)
                total_loss += loss
                
                # Gradient accumulation
                if (i + 1) % self.lora_config.gradient_accumulation_steps == 0:
                    self._optimizer.step()
                    self._optimizer.zero_grad()
                    global_step += 1
                    
                    # Logging
                    if global_step % self.lora_config.logging_steps == 0:
                        avg_loss = total_loss / self.lora_config.logging_steps
                        elapsed = time.time() - start_time
                        tps = global_step * self.lora_config.batch_size / elapsed if elapsed > 0 else 0
                        
                        metrics = TrainingMetrics(
                            loss=avg_loss,
                            current_step=global_step,
                            total_steps=self.lora_config.max_steps,
                            elapsed_seconds=round(elapsed, 2),
                            tokens_per_second=round(tps, 2),
                        )
                        
                        logger.info(
                            "Step %d/%d - loss: %.4f - %.2f steps/sec",
                            global_step, self.lora_config.max_steps,
                            avg_loss, tps,
                        )
                        
                        if progress_callback:
                            progress_callback(global_step, metrics)
                        
                        total_loss = 0.0
                    
                    # Save checkpoint
                    if global_step % self.lora_config.save_steps == 0:
                        checkpoint_path = output_path / f"checkpoint-{global_step}"
                        self._save_lora_weights(checkpoint_path)
                        logger.info("Checkpoint kaydedildi: %s", checkpoint_path)
        
        # Final save
        final_path = output_path / "lora_weights"
        self._save_lora_weights(final_path)
        logger.info("Eğitim tamamlandı: %s", final_path)
        
        return final_path
    
    def _train_step(self, example: dict[str, Any]) -> mx.array:
        """Tek bir eğitim adımı."""
        # Tokenization
        if 'instruction' in example:
            text = f"{example['instruction']}\n{example.get('input', '')}\n{example.get('output', '')}"
        elif 'prefix' in example and 'suffix' in example:
            # FIM formatı
            text = f"<|fim_begin|>{example['prefix']}<|fim_hole|>{example['suffix']}<|fim_end|>{example.get('middle', '')}"
        else:
            text = example.get('text', '')
        
        tokens = self._tokenizer.encode(
            text,
            max_length=self.lora_config.max_seq_length,
            truncation=True,
        )
        
        # Loss hesapla
        logits = self._model(mx.array([tokens]))
        loss = nn.losses.cross_entropy(logits, mx.array([tokens]))
        
        # Backward
        loss.backward()
        
        return loss
    
    def _save_lora_weights(self, path: Path) -> None:
        """Sadece LoRA ağırlıklarını kaydet (model değil)."""
        path.mkdir(parents=True, exist_ok=True)
        
        weights = {}
        for i, layer in enumerate(self._lora_layers):
            weights[f"lora_{i}_weight"] = layer.weight
            if hasattr(layer, 'bias') and layer.bias is not None:
                weights[f"lora_{i}_bias"] = layer.bias
        
        save_weights(str(path), weights)
        
        # Config
        config = {
            "lora_rank": self.lora_config.rank,
            "lora_alpha": self.lora_config.alpha,
            "target_modules": self.lora_config.target_modules,
            "base_model": self.model_path,
        }
        with open(path / "lora_config.json", "w") as f:
            json.dump(config, f, indent=2)
    
    def generate_with_lora(
        self,
        prompt: str,
        lora_path: str,
        max_tokens: int = 512,
    ) -> str:
        """LoRA adaptörüyle birlikte metin üret."""
        # LoRA ağırlıklarını yükle
        self._load_lora_weights(lora_path)
        
        # Generate
        result = generate(self._model, self._tokenizer, prompt=prompt, max_tokens=max_tokens)
        return str(result)
    
    def _load_lora_weights(self, path: str) -> None:
        """LoRA ağırlıklarını yükle."""
        import glob
        weight_files = sorted(glob.glob(f"{path}/*.safetensors"))
        if weight_files:
            from mlx_lm.utils import load_weights
            weights = load_weights(weight_files)
            for i, layer in enumerate(self._lora_layers):
                key = f"lora_{i}_weight"
                if key in weights:
                    layer.weight = weights[key]
```

### Dataset Builder

```python
# apps/backend/yontai/training/dataset_builder.py
"""Dataset builder from internet code."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DatasetBuilder:
    """İnternetten çekilen kodlardan training dataset'i oluşturur.
    
    Desteklenen formatlar:
    - instruction: {instruction, input, output}
    - FIM: {prefix, suffix, middle}
    - chat: {messages: [{role, content}]}
    """
    
    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
    
    def build_instruction_dataset(
        self,
        code_files: list[dict[str, Any]],
        output_path: str,
    ) -> Path:
        """Kod dosyalarından instruction dataset'i oluştur.
        
        Her fonksiyon/sınıf için:
        - instruction: "Write a function that..."
        - input: (opsiyonel)
        - output: Kod
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        samples: list[dict[str, str]] = []
        
        for file in code_files[:self.max_samples]:
            content = file.get('content', '')
            path = file.get('file_path', '')
            language = file.get('language', 'text')
            
            # Fonksiyonları çıkar
            functions = self._extract_functions(content, language)
            for func_name, func_code in functions:
                # Instruction oluştur
                instruction = self._generate_instruction(func_name, language)
                
                samples.append({
                    'instruction': instruction,
                    'input': f"Dil: {language}\nDosya: {path}",
                    'output': func_code,
                })
        
        # JSONL olarak kaydet
        with open(output, 'w') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        logger.info("Dataset oluşturuldu: %d sample -> %s", len(samples), output)
        return output
    
    def build_fim_dataset(
        self,
        code_files: list[dict[str, Any]],
        output_path: str,
    ) -> Path:
        """Kod dosyalarından FIM (Fill-in-the-Middle) dataset'i oluştur.
        
        Her fonksiyon için:
        - prefix: Fonksiyon başlangıcı
        - suffix: Fonksiyon sonu
        - middle: Ortadaki kod (modelin tahmin etmesi gereken)
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        samples: list[dict[str, str]] = []
        
        for file in code_files[:self.max_samples]:
            content = file.get('content', '')
            language = file.get('language', 'text')
            
            # Fonksiyonları çıkar
            functions = self._extract_functions(content, language)
            for _, func_code in functions:
                lines = func_code.split('\n')
                if len(lines) < 6:
                    continue
                
                # Ortadaki satırları gizle
                split_point = len(lines) // 2
                prefix = '\n'.join(lines[:split_point])
                middle = '\n'.join(lines[split_point:split_point + 3])
                suffix = '\n'.join(lines[split_point + 3:])
                
                if len(middle) < 10:
                    continue
                
                samples.append({
                    'prefix': prefix,
                    'suffix': suffix,
                    'middle': middle,
                    'language': language,
                })
        
        # JSONL olarak kaydet
        with open(output, 'w') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        logger.info("FIM dataset oluşturuldu: %d sample -> %s", len(samples), output)
        return output
    
    def build_chat_dataset(
        self,
        code_files: list[dict[str, Any]],
        output_path: str,
    ) -> Path:
        """Kod dosyalarından chat dataset'i oluştur."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        samples: list[dict[str, Any]] = []
        
        for file in code_files[:self.max_samples]:
            content = file.get('content', '')
            language = file.get('language', 'text')
            
            # Her fonksiyon için bir sohbet örneği
            functions = self._extract_functions(content, language)
            for func_name, func_code in functions[:3]:  # Dosya başına max 3
                samples.append({
                    'messages': [
                        {
                            'role': 'user',
                            'content': f"Write a {language} function called {func_name}"
                        },
                        {
                            'role': 'assistant',
                            'content': f"Here's the {func_name} function:\n\n```{language}\n{func_code}\n```"
                        }
                    ]
                })
        
        # JSONL olarak kaydet
        with open(output, 'w') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        logger.info("Chat dataset oluşturuldu: %d sample -> %s", len(samples), output)
        return output
    
    def _extract_functions(
        self,
        content: str,
        language: str,
    ) -> list[tuple[str, str]]:
        """Koddan fonksiyonları çıkar."""
        import re
        
        functions: list[tuple[str, str]] = []
        
        if language == 'python':
            pattern = r'^(async\s+)?def\s+(\w+)\s*\([^)]*\)\s*(->\s*\w+)?:'
        elif language in ('javascript', 'typescript'):
            pattern = r'(?:async\s+)?function\s+(\w+)\s*\(|(\w+)\s*=\s*(?:async\s+)?function\s*\('
        else:
            pattern = r'(?:fn|func|function)\s+(\w+)\s*\('
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            match = re.search(pattern, line)
            if not match:
                continue
            
            func_name = match.group(1) or match.group(2) or ''
            if func_name in ('if', 'for', 'while', 'with'):
                continue
            
            # Fonksiyonun bittiği satırı bul
            # Basit: girintinin sıfırlandığı yer
            if language == 'python':
                base_indent = len(line) - len(line.lstrip())
                end = i + 1
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() and len(lines[j]) - len(lines[j].lstrip()) <= base_indent:
                        end = j
                        break
                    end = j + 1
                func_code = '\n'.join(lines[i:end])
            else:
                # Süslü parantez tabanlı
                brace_count = 0
                end = i + 1
                for j in range(i, len(lines)):
                    brace_count += lines[j].count('{') - lines[j].count('}')
                    if brace_count <= 0 and j > i:
                        end = j + 1
                        break
                    end = j + 1
                func_code = '\n'.join(lines[i:end])
            
            if func_code.strip():
                functions.append((func_name, func_code))
        
        return functions
    
    def _generate_instruction(self, func_name: str, language: str) -> str:
        """Fonksiyon adından instruction oluştur."""
        # Snake case'i çöz
        name = func_name.replace('_', ' ').replace('-', ' ')
        
        templates = [
            f"Write a {language} function called {func_name}",
            f"Implement the {func_name} function in {language}",
            f"Create a {language} function named {func_name}",
            f"How to write {func_name} in {language}?",
        ]
        
        return random.choice(templates)
```

---

## 8. VS Code UX Geliştirmeleri

### Command Palette Actions

```typescript
// VS Code command mapping
const COMMANDS = {
    // Code Actions
    'yontai.explainCode': {
        title: 'YontAI: Kodu Açıkla',
        icon: '$(book)',
        keybinding: 'ctrl+shift+e',
    },
    'yontai.generateTests': {
        title: 'YontAI: Test Yaz',
        icon: '$(beaker)',
        keybinding: 'ctrl+shift+t',
    },
    'yontai.refactorCode': {
        title: 'YontAI: Kodu Refactor Et',
        icon: '$(wand)',
        keybinding: 'ctrl+shift+r',
    },
    'yontai.addTypeHints': {
        title: 'YontAI: Tip İpuçları Ekle',
        icon: '$(symbol-misc)',
    },
    'yontai.reviewCode': {
        title: 'YontAI: Kod İncelemesi',
        icon: '$(search)',
        keybinding: 'ctrl+shift+i',
    },
    'yontai.findBugs': {
        title: 'YontAI: Hata Ara',
        icon: '$(bug)',
        keybinding: 'ctrl+shift+b',
    },
    'yontai.optimizeImports': {
        title: 'YontAI: Importları Optimize Et',
        icon: '$(package)',
    },
    'yontai.addDocstrings': {
        title: 'YontAI: Dökümantasyon Ekle',
        icon: '$(note)',
    },
    'yontai.convertLanguage': {
        title: 'YontAI: Dil Çevir',
        icon: '$(arrow-swap)',
    },
    
    // AI Lab
    'yontai.chat': {
        title: 'YontAI: Sohbet',
        icon: '$(comment-discussion)',
        keybinding: 'cmd+shift+space',
    },
    'yontai.trainModel': {
        title: 'YontAI: Model Eğit',
        icon: '$(rocket)',
    },
    'yontai.updateKnowledge': {
        title: 'YontAI: Bilgi Güncelle',
        icon: '$(cloud-download)',
    },
    'yontai.indexProject': {
        title: 'YontAI: Projeyi İndeksle',
        icon: '$(database)',
    },
};
```

### Chat Panel (Webview)

```typescript
// chat/panel.ts
import * as vscode from 'vscode';

export class YontAIChatPanel {
    public static readonly viewType = 'yontai.chat';
    private _panel: vscode.WebviewPanel | undefined;

    constructor(
        private context: vscode.ExtensionContext,
        private api: YontAIAPI,
        private contextEngine: YontAIContextEngine
    ) {}

    show() {
        if (this._panel) {
            this._panel.reveal(vscode.ViewColumn.Beside);
            return;
        }

        this._panel = vscode.window.createWebviewPanel(
            YontAIChatPanel.viewType,
            'YontAI Sohbet',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            }
        );

        this._panel.webview.html = this.getHtml();
        this._panel.onDidDispose(() => { this._panel = undefined; });
    }

    private getHtml(): string {
        return `<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
               background: var(--vscode-editor-background); 
               color: var(--vscode-editor-foreground); 
               height: 100vh; display: flex; flex-direction: column; }
        #messages { flex: 1; overflow-y: auto; padding: 16px; }
        .message { margin-bottom: 16px; padding: 12px; border-radius: 8px; }
        .user { background: var(--vscode-input-background); }
        .assistant { background: var(--vscode-textBlockQuote-background); }
        .message pre { background: #1e1e1e; padding: 12px; border-radius: 4px; 
                      overflow-x: auto; margin-top: 8px; }
        #input-area { display: flex; padding: 12px; gap: 8px; 
                     border-top: 1px solid var(--vscode-panel-border); }
        #input { flex: 1; padding: 8px 12px; border: 1px solid var(--vscode-input-border);
                border-radius: 4px; background: var(--vscode-input-background); 
                color: var(--vscode-input-foreground); font-size: 14px; }
        #send { padding: 8px 16px; background: var(--vscode-button-background); 
               color: var(--vscode-button-foreground); border: none; border-radius: 4px; 
               cursor: pointer; font-size: 14px; }
        #send:hover { background: var(--vscode-button-hoverBackground); }
        .context-info { font-size: 11px; color: var(--vscode-descriptionForeground); 
                       margin-top: 4px; }
    </style>
</head>
<body>
    <div id="messages"></div>
    <div id="input-area">
        <input type="text" id="input" placeholder="Kod hakkında soru sor..." autofocus />
        <button id="send">Gönder</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        const messages = document.getElementById('messages');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('send');

        function addMessage(role, content) {
            const div = document.createElement('div');
            div.className = 'message ' + role;
            div.textContent = content;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        sendBtn.onclick = () => {
            const text = input.value.trim();
            if (!text) return;
            addMessage('user', text);
            input.value = '';
            vscode.postMessage({ type: 'chat', text });
        };

        input.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                sendBtn.click();
            }
        };

        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.type === 'response') {
                addMessage('assistant', msg.text);
            } else if (msg.type === 'context') {
                const info = document.createElement('div');
                info.className = 'context-info';
                info.textContent = '📎 Bağlam: ' + msg.files.join(', ');
                messages.appendChild(info);
            }
        });
    </script>
</body>
</html>`;
    }

    dispose() {
        this._panel?.dispose();
    }
}
```

---

## 9. Prompt Engineering Mimarisi

### Prompt Injection Strategy

```
Kullanıcı Sorusu
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│              Prompt Assembly Pipeline                     │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  1. System Message (project-aware)                       │
│     ├── Framework detection (React, Node, Python)        │
│     ├── Coding style preferences                         │
│     ├── Language preference (Türkçe/English)             │
│     └── Project-specific rules                           │
│                                                           │
│  2. Context Injection                                    │
│     ├── Open file: imports + function signatures         │
│     ├── RAG: top 5 relevant snippets                    │
│     ├── AST: class/function definitions                 │
│     └── History: last 3 interactions                    │
│                                                           │
│  3. RAG Context Formatting                               │
│     └── Dosya:satır sembol:tip formatında                │
│                                                           │
│  4. User Query                                           │
│                                                           │
│  5. Response Constraints                                 │
│     ├── Max tokens                                       │
│     ├── Stop strings                                     │
│     └── Format (markdown, code block)                   │
│                                                           │
└──────────────────────────────────────────────────────────┘
    │
    ▼
<|system|>
[Project-aware system message]
Project: React 18 + TypeScript
Style: Functional components, hooks
Language: Turkish explanations
</|system|>
<|user|>
// Relevant context from RAG:
// src/components/Button.tsx:12 (function: ButtonProps)
// src/hooks/useAuth.ts:45 (function: useAuth)

[User query with injected context]
</|user|>
<|assistant|>
```

### Dynamic System Message Builder

```python
# apps/backend/yontai/integrations/dynamic_prompt.py
"""Dynamic prompt builder with context injection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yontai.integrations.prompt_templates import (
    DEFAULT_SYSTEM_MESSAGE,
    DEEPSEEK_SYSTEM_MESSAGE,
    build_system_message,
)
from yontai.rag.context_engine import ContextEngine


class DynamicPromptBuilder:
    """Proje bağlamına göre dinamik prompt oluşturur.
    
    Özellikler:
    - Framework detection
    - Coding style memory
    - RAG context injection
    - Dil seçimi (Türkçe/English)
    """
    
    def __init__(self, context_engine: ContextEngine):
        self.context_engine = context_engine
        self._framework_cache: dict[str, str] = {}
        
    async def build_chat_prompt(
        self,
        query: str,
        current_file: str | None = None,
        language: str = "tr",
        model_family: str = "deepseek",
    ) -> str:
        """Sohbet prompt'u oluştur."""
        
        # 1. Framework detection
        framework = await self._detect_framework(current_file)
        
        # 2. Coding style
        style = await self._detect_coding_style(current_file)
        
        # 3. System message
        sys_message = build_system_message(
            project_context=framework,
            language=language.upper(),
            code_style=style,
        ) if language == "tr" else DEEPSEEK_SYSTEM_MESSAGE
        
        # 4. RAG context
        rag_context = self.context_engine.build_prompt_context(
            query=query,
            current_file=current_file,
            max_tokens=2048,
        )
        
        # 5. Build final prompt
        parts = [f"<|system|>\n{sys_message}\n"]
        
        if rag_context:
            parts.append(f"<|user|>\n{rag_context}\n\n{query}\n")
        else:
            parts.append(f"<|user|>\n{query}\n")
        
        parts.append("<|assistant|>\n")
        
        return "".join(parts)
    
    async def build_fim_prompt(
        self,
        prefix: str,
        suffix: str,
        current_file: str | None = None,
    ) -> str:
        """FIM prompt'u oluştur."""
        # FIM için sistem mesajı kullanılmaz
        return f"<|fim_begin|>{prefix}<|fim_hole|>{suffix}<|fim_end|>"
    
    async def build_code_action_prompt(
        self,
        action: str,
        code: str,
        language: str = "python",
        current_file: str | None = None,
    ) -> str:
        """Kod eylemi prompt'u oluştur."""
        from yontai.integrations.prompt_templates import CodeActionTemplates
        
        # RAG context
        rag_context = self.context_engine.build_prompt_context(
            query=code,
            current_file=current_file,
            max_tokens=1024,
        )
        
        # Action template
        action_templates = {
            "explain": CodeActionTemplates.explain_code,
            "test": CodeActionTemplates.generate_tests,
            "refactor": CodeActionTemplates.refactor_code,
            "typehints": CodeActionTemplates.add_type_hints,
            "review": CodeActionTemplates.review_code,
            "bugs": CodeActionTemplates.find_bugs,
            "imports": CodeActionTemplates.optimize_imports,
            "docstrings": CodeActionTemplates.add_docstrings,
        }
        
        template_fn = action_templates.get(action, CodeActionTemplates.explain_code)
        action_prompt = template_fn(code, language)
        
        # Build
        parts = [f"<|system|>\n{DEFAULT_SYSTEM_MESSAGE}\n"]
        if rag_context:
            parts.append(f"<|user|>\n{rag_context}\n\n{action_prompt}\n")
        else:
            parts.append(f"<|user|>\n{action_prompt}\n")
        parts.append("<|assistant|>\n")
        
        return "".join(parts)
    
    async def _detect_framework(self, file_path: str | None) -> str | None:
        """Dosyadan framework tespit et."""
        if not file_path:
            return None
        
        # Cache'te varsa döndür
        if file_path in self._framework_cache:
            return self._framework_cache[file_path]
        
        # package.json veya pyproject.toml ara
        path = Path(file_path)
        project_root = path.parent
        
        # package.json
        pkg_json = project_root / "package.json"
        if pkg_json.exists():
            import json
            try:
                with open(pkg_json) as f:
                    pkg = json.load(f)
                deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
                
                if 'react' in deps:
                    framework = f"React {deps.get('react', 'latest')}"
                elif 'next' in deps:
                    framework = f"Next.js {deps.get('next', 'latest')}"
                elif 'vue' in deps:
                    framework = f"Vue {deps.get('vue', 'latest')}"
                elif 'express' in deps:
                    framework = f"Express {deps.get('express', 'latest')}"
                else:
                    framework = "Node.js"
                
                self._framework_cache[file_path] = framework
                return framework
            except Exception:
                pass
        
        # pyproject.toml
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            return "Python"
        
        # Cargo.toml
        cargo = project_root / "Cargo.toml"
        if cargo.exists():
            return "Rust"
        
        return None
    
    async def _detect_coding_style(self, file_path: str | None) -> str | None:
        """Kod stili tespit et."""
        if not file_path:
            return None
        
        path = Path(file_path)
        
        # ESLint config
        for config_name in ['.eslintrc', '.eslintrc.js', '.eslintrc.json', '.eslintrc.yaml']:
            config = path.parent / config_name
            if config.exists():
                return "ESLint kuralları uygulanıyor"
        
        # Ruff config (Python)
        if (path.parent / 'pyproject.toml').exists():
            return "Ruff + mypy strict mode"
        
        # Prettier
        if (path.parent / '.prettierrc').exists() or (path.parent / '.prettierrc.js').exists():
            return "Prettier formatı"
        
        return None
```

---

## 10. Geliştirme Fazları ve Timeline

### Faz 1: MVP (2-3 hafta) 🎯

| Görev | Süre | Detay |
|-------|------|-------|
| VS Code extension iskeleti | 3 gün | package.json, activation, commands |
| FIM completion provider | 4 gün | InlineCompletionItemProvider, debounce |
| Basit RAG (açık dosya) | 2 gün | Prefix/suffix extraction |
| Model router (fast/smart) | 3 gün | Intent classification, tier selection |
| Chat panel (webview) | 2 gün | Webview HTML, messaging |

### Faz 2: Context Engine (3-5 hafta) 🔍

| Görev | Süre | Detay |
|-------|------|-------|
| tree-sitter AST indexing | 5 gün | Python, JS, TS, Rust parser |
| ChromaDB vector search | 3 gün | Embedding, similarity search |
| Project memory graph | 4 gün | Dependency-aware retrieval |
| Sliding window context | 2 gün | Token budget management |
| Workspace watcher | 2 gün | File change detection |

### Faz 3: Multi-Model + MLX (4-6 hafta) 🚀

| Görev | Süre | Detay |
|-------|------|-------|
| MLX runtime optimization | 5 gün | Memory management, KV cache |
| llama.cpp fallback | 3 gün | Server mode integration |
| Speculative decoding | 5 gün | Draft model + target model |
| Model switching UI | 3 gün | Status bar, model selector |
| Benchmark dashboard | 3 gün | Performance metrics |

### Faz 4: AI Coding Lab (6-10 hafta) 🧪

| Görev | Süre | Detay |
|-------|------|-------|
| Web fetcher module | 5 gün | GitHub, npm, PyPI crawler |
| Dataset builder | 5 gün | Instruction, FIM, chat format |
| LoRA training pipeline | 7 gün | MLX LoRA trainer |
| RAG-first fallback | 3 gün | 16GB memory-safe training |
| Training UI | 5 gün | Webview training dashboard |
| Model export/deploy | 3 gün | LoRA weights, merge, deploy |

### Toplam: ~15-24 hafta

---

## Kritik Kısıtlar ve Riskler

### Apple Silicon M1 Pro 16GB Kısıtları

| Kısıt | Çözüm |
|-------|-------|
| Max 1 büyük model (7B Q4) | LRU cache + cold swap |
| LoRA training: 8-10 GB | Batch size=1, grad accumulation |
| KV cache: 2-3 GB | Cache compression, sliding window |
| Training süresi: 1-2 saat | 500-2000 adım, erken durdurma |

### Güvenlik Riskleri

| Risk | Önlem |
|------|-------|
| Code injection (web fetch) | HTTP client, no eval |
| API rate limiting | Token bucket, backoff |
| Disk space | 100MB limit, temp cleanup |
| Memory leak | LRU eviction, gc.collect() |

### Başarı Kriterleri

| Metrik | Hedef |
|--------|-------|
| FIM latency | <150ms |
| RAG search | <50ms |
| Model switch | <2s |
| Training (500 step) | <45 dk |
| Context window | 4096 token |
| Code action response | <5s |

---

## Özet: "AI Coding Lab" Vizyonu

```
┌──────────────────────────────────────────────────────────────┐
│                 YontAI AI Coding Lab                          │
│                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐ │
│  │   VS Code IDE   │  │   Model Store   │  │  AI Lab       │ │
│  │                 │  │                 │  │               │ │
│  │ • FIM autocompl.│  │ • MLX models    │  │ • Web fetch   │ │
│  │ • Chat panel    │  │ • Ollama models │  │ • Dataset     │ │
│  │ • Code actions  │  │ • LoRA adapters │  │ • Train       │ │
│  │ • RAG context   │  │ • Model compare │  │ • Deploy      │ │
│  └────────┬────────┘  └────────┬────────┘  └───────┬───────┘ │
│           │                    │                     │        │
│           └────────────────────┼─────────────────────┘        │
│                                │                              │
│                    ┌───────────▼───────────┐                  │
│                    │   Backend Engine      │                  │
│                    │   (Python FastAPI)    │                  │
│                    │   MLX · Ollama · RAG  │                  │
│                    └───────────────────────┘                  │
│                                                               │
│              ⚡ Yerel · Açık Kaynak · Apple Silicon           │
└──────────────────────────────────────────────────────────────┘
```

Bu mimari ile YontAI sadece bir kod asistanı değil, kullanıcının kendi coding AI modelini oluşturduğu, eğittiği ve geliştirdiği **yerel AI mühendislik laboratuvarı** haline gelir.