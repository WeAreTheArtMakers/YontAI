/**
 * YontAI Language Manager
 * 
 * Clean, extensible multi-language system for the YontAI website.
 * 
 * API:
 *   setLanguage('tr')       - Switch language and update DOM
 *   getText('hero.title')   - Get translated text by key path
 *   getCurrentLanguage()    - Returns 'tr' or 'en'
 * 
 * HTML Usage:
 *   <h1 data-i18n="hero.title"></h1>
 *   <p data-i18n="hero.subtitle" data-i18n-params='{"name":"YontAI"}'></p>
 * 
 * Adding a new language:
 *   1. Add a new key to LANGUAGES object (e.g., 'de')
 *   2. Copy all section keys from 'en' and translate values
 *   3. Done - no other code changes needed
 */

const LANGUAGES = {
  tr: {
    nav: {
      home: 'Ana Sayfa',
      features: 'Özellikler',
      architecture: 'Mimari',
      performance: 'Performans',
      about: 'Hakkında',
      contact: 'İletişim',
      getStarted: 'Başla',
      viewOnGitHub: 'GitHub\'da Gör',
    },
    hero: {
      badge: '🚀 Apple Silicon için Optimize Edildi',
      title: 'Kendi Yapay Zeka Kod Asistanını Oluştur',
      subtitle: 'YontAI ile kendi coding AI modelini eğit, internetten güncel kod topla, proje bağlamını anla ve akıllı kod tamamlama ile üretkenliğini katla.',
      ctaPrimary: 'Başlamak için',
      ctaSecondary: 'GitHub\'da Keşfet',
      typingPrefix: 'Sen yazarken, YontAI ',
      typingTexts: ['kodunu tamamlar', 'hatalarını bulur', 'testlerini yazar', 'refactor eder', 'dökümantasyon ekler'],
      stats: {
        commnits: 'Commits',
        files: 'Dosya',
        linesOfCode: 'Satır Kod',
      },
    },
    features: {
      title: 'Güçlü Özellikler',
      subtitle: 'YontAI, yerel AI kod asistanınızı bir üst seviyeye taşımak için tasarlandı.',
      mlx: {
        title: 'MLX Apple Silicon Desteği',
        desc: 'M1/M2/M3/M4 çiplerinde %40\'a varan hız artışı. 4-bit kuantize modellerle 16 GB RAM\'de 7B model çalıştırın.',
      },
      multiModel: {
        title: 'Çoklu Model Orkestrasyonu',
        desc: 'Akıllı routing: 1-3B hızlı model FIM için, 7-16B akıllı model sohbet için. Otomatik geçiş, sıfır gecikme.',
      },
      fim: {
        title: 'FIM Kod Tamamlama',
        desc: 'DeepSeek-Coder formatında Fill-in-the-Middle. İmleç öncesi/sonrasını analiz eder. <150ms yanıt süresi.',
      },
      rag: {
        title: 'RAG Bağlam Motoru',
        desc: 'tree-sitter ile 17 dilde AST parsing. ChromaDB vektör arama. Proje bağımlılık grafı ile akıllı context.',
      },
      knowledge: {
        title: 'İnternetten Kod Toplama',
        desc: 'GitHub API, npm, PyPI entegrasyonu. Tek tıkla güncel kod çek, temizle, embedding yap, RAG\'e ekle.',
      },
      training: {
        title: 'AI Lab Model Eğitimi',
        desc: 'MLX ile LoRA/QLoRA fine-tuning. Dataset builder ile instruction/FIM/chat formatında eğitim verisi oluşturun.',
      },
    },
    architecture: {
      title: 'Sistem Mimarisi',
      subtitle: 'YontAI, modüler ve genişletilebilir bir mimari üzerine inşa edilmiştir.',
      layers: {
        ui: 'Kullanıcı Arayüzü',
        api: 'API Katmanı',
        runtime: 'Model Runtime',
        rag: 'RAG Motoru',
        training: 'Eğitim Pipeline',
      },
    },
    performance: {
      title: 'Performans (M1 Pro 16 GB)',
      subtitle: 'Apple Silicon üzerinde gerçek dünya benchmark sonuçları.',
      model: 'Model',
      quantization: 'Quantization',
      tokensPerSec: 'Token/s',
      ramUsage: 'RAM Kullanımı',
      rows: {
        deepseek13: { model: 'DeepSeek-Coder 1.3B', quant: 'Q4', tokens: '45-55', ram: '~2.5 GB' },
        deepseek67: { model: 'DeepSeek-Coder 6.7B', quant: 'Q4', tokens: '15-22', ram: '~8 GB' },
        codeqwen: { model: 'CodeQwen-7B', quant: 'Q4', tokens: '12-18', ram: '~7 GB' },
        starcode: { model: 'StarCoder2-3B', quant: 'Q4', tokens: '30-40', ram: '~4 GB' },
        fim: { model: 'FIM (1.3B)', quant: 'Q4', tokens: '<200ms', ram: '~2.5 GB' },
      },
    },
    about: {
      title: 'YontAI Nedir?',
      subtitle: 'YontAI, sadece bir kod asistanı değil — kendi coding AI modelini oluşturduğun, eğittiğin ve geliştirdiğin yerel bir AI mühendislik laboratuvarıdır.',
      mission: 'Misyonumuz, her geliştiricinin kendi ihtiyaçlarına özel AI modelleri oluşturabilmesini sağlamak. Tamamen yerel, tamamen gizli, tamamen senin kontrolünde.',
      cta: 'Başlamak için',
      stat1: 'Açık Kaynak',
      stat2: 'Gizlilik Odaklı',
      stat3: 'Apple Silicon',
    },
    footer: {
      copyright: '© {year} YontAI. Tüm hakları saklıdır.',
      description: 'Kendi yapay zeka kod asistanını oluştur. Açık kaynak, gizlilik odaklı, Apple Silicon için optimize.',
      quickLinks: 'Hızlı Linkler',
      resources: 'Kaynaklar',
      documentation: 'Dokümantasyon',
      apiReference: 'API Referansı',
      architecture: 'Mimari',
      chnagelog: 'Değişiklikler',
      madeWith: '❤️ ile yapıldı',
    },
    common: {
      loading: 'Yükleniyor...',
      error: 'Hata oluştu',
      retry: 'Tekrar dene',
      learnMore: 'Daha Fazla',
      getStarted: 'Başla',
      starOnGitHub: 'Yıldızla',
    },
  },

  en: {
    nav: {
      home: 'Home',
      features: 'Features',
      architecture: 'Architecture',
      performance: 'Performance',
      about: 'About',
      contact: 'Contact',
      getStarted: 'Get Started',
      viewOnGitHub: 'View on GitHub',
    },
    hero: {
      badge: '🚀 Optimized for Apple Silicon',
      title: 'Build Your Own AI Coding Assistant',
      subtitle: 'Train your own coding AI model, gather code from the internet, understand project context, and supercharge your productivity with intelligent code completion — all running locally on your machine.',
      ctaPrimary: 'Get Started',
      ctaSecondary: 'Explore on GitHub',
      typingPrefix: 'While you code, YontAI ',
      typingTexts: ['completes your code', 'finds your bugs', 'writes your tests', 'refactors your code', 'adds documentation'],
      stats: {
        commnits: 'Commits',
        files: 'Files',
        linesOfCode: 'Lines of Code',
      },
    },
    features: {
      title: 'Powerful Features',
      subtitle: 'YontAI is designed to take your local AI coding assistant to the next level.',
      mlx: {
        title: 'MLX Apple Silicon Support',
        desc: 'Up to 40% speed improvement on M1/M2/M3/M4 chips. Run 7B models on 16GB RAM with 4-bit quantization.',
      },
      multiModel: {
        title: 'Multi-Model Orchestration',
        desc: 'Smart routing: 1-3B fast model for FIM, 7-16B smart model for chat. Automatic switching, zero latency.',
      },
      fim: {
        title: 'FIM Code Completion',
        desc: 'Fill-in-the-Middle with DeepSeek-Coder format. Analyzes prefix/suffix context. <150ms response time.',
      },
      rag: {
        title: 'RAG Context Engine',
        desc: 'AST parsing in 17 languages with tree-sitter. ChromaDB vector search. Smart context with dependency graph.',
      },
      knowledge: {
        title: 'Web Knowledge Ingestion',
        desc: 'GitHub API, npm, PyPI integration. One-click code fetching, cleaning, embedding, and RAG indexing.',
      },
      training: {
        title: 'AI Lab Model Training',
        desc: 'LoRA/QLoRA fine-tuning with MLX. Dataset builder for instruction, FIM, and chat format training data.',
      },
    },
    architecture: {
      title: 'System Architecture',
      subtitle: 'YontAI is built on a modular, extensible architecture.',
      layers: {
        ui: 'User Interface',
        api: 'API Layer',
        runtime: 'Model Runtime',
        rag: 'RAG Engine',
        training: 'Training Pipeline',
      },
    },
    performance: {
      title: 'Performance (M1 Pro 16 GB)',
      subtitle: 'Real-world benchmark results on Apple Silicon.',
      model: 'Model',
      quantization: 'Quantization',
      tokensPerSec: 'Token/s',
      ramUsage: 'RAM Usage',
      rows: {
        deepseek13: { model: 'DeepSeek-Coder 1.3B', quant: 'Q4', tokens: '45-55', ram: '~2.5 GB' },
        deepseek67: { model: 'DeepSeek-Coder 6.7B', quant: 'Q4', tokens: '15-22', ram: '~8 GB' },
        codeqwen: { model: 'CodeQwen-7B', quant: 'Q4', tokens: '12-18', ram: '~7 GB' },
        starcode: { model: 'StarCoder2-3B', quant: 'Q4', tokens: '30-40', ram: '~4 GB' },
        fim: { model: 'FIM (1.3B)', quant: 'Q4', tokens: '<200ms', ram: '~2.5 GB' },
      },
    },
    about: {
      title: 'What is YontAI?',
      subtitle: 'YontAI is not just a coding assistant — it\'s a local AI engineering lab where you create, train, and evolve your own coding AI models.',
      mission: 'Our mission is to empower every developer to create AI models tailored to their specific needs. Fully local, fully private, fully under your control.',
      cta: 'Get Started',
      stat1: 'Open Source',
      stat2: 'Privacy First',
      stat3: 'Apple Silicon',
    },
    footer: {
      copyright: '© {year} YontAI. All rights reserved.',
      description: 'Build your own AI coding assistant. Open source, privacy-first, optimized for Apple Silicon.',
      quickLinks: 'Quick Links',
      resources: 'Resources',
      documentation: 'Documentation',
      apiReference: 'API Reference',
      architecture: 'Architecture',
      chnagelog: 'Changelog',
      madeWith: 'Made with ❤️',
    },
    common: {
      loading: 'Loading...',
      error: 'An error occurred',
      retry: 'Retry',
      learnMore: 'Learn More',
      getStarted: 'Get Started',
      starOnGitHub: 'Star on GitHub',
    },
  },
};

class LanguageManager {
  constructor() {
    this._currentLang = 'en';
    this._listeners = [];
    this._initialized = false;
  }

  init() {
    if (this._initialized) return;
    
    // 1. Try localStorage first
    const saved = localStorage.getItem('yontai_language');
    if (saved && LANGUAGES[saved]) {
      this._currentLang = saved;
    } else {
      // 2. Auto-detect browser language
      const browserLang = (navigator.language || navigator.userLanguage || '').substring(0, 2);
      this._currentLang = LANGUAGES[browserLang] ? browserLang : 'en';
    }

    // 3. Apply translations to DOM
    this._translateDOM();

    // 4. Re-translate when DOM changes (for dynamic content)
    if (window.MutationObserver) {
      const observer = new MutationObserver(() => this._translateDOM());
      observer.observe(document.body, { childList: true, subtree: true });
    }

    this._initialized = true;
    this._emit('languageChanged', { language: this._currentLang });
  }

  getCurrentLanguage() {
    return this._currentLang;
  }

  getText(key, params = {}) {
    const keys = key.split('.');
    let value = LANGUAGES[this._currentLang];
    
    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k];
      } else {
        // Fallback to English
        value = LANGUAGES['en'];
        for (const ek of keys) {
          if (value && typeof value === 'object' && ek in value) {
            value = value[ek];
          } else {
            return key; // Key not found
          }
        }
        break;
      }
    }

    if (typeof value !== 'string') return key;

    // Interpolation: {variable}
    return value.replace(/\{(\w+)\}/g, (match, varName) => {
      return varName in params ? String(params[varName]) : match;
    });
  }

  setLanguage(lang) {
    if (!LANGUAGES[lang] || this._currentLang === lang) return;
    
    this._currentLang = lang;
    localStorage.setItem('yontai_language', lang);
    
    this._translateDOM();
    this._emit('languageChanged', { language: lang });
    
    // Update HTML lang attribute
    document.documentElement.lang = lang;
  }

  toggleLanguage() {
    const newLang = this._currentLang === 'tr' ? 'en' : 'tr';
    this.setLanguage(newLang);
  }

  on(event, callback) {
    if (event === 'languageChanged') {
      this._listeners.push(callback);
    }
  }

  off(event, callback) {
    if (event === 'languageChanged') {
      this._listeners = this._listeners.filter(cb => cb !== callback);
    }
  }

  _translateDOM() {
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (!key) return;

      // Check for interpolation params
      const paramsAttr = el.getAttribute('data-i18n-params');
      let params = {};
      if (paramsAttr) {
        try {
          params = JSON.parse(paramsAttr);
        } catch (e) {
          console.warn('Invalid data-i18n-params:', paramsAttr);
        }
      }

      const text = this.getText(key, params);
      if (text !== key) {
        // Handle different element types
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
          el.placeholder = text;
        } else if (el.tagName === 'META') {
          el.content = text;
        } else {
          el.textContent = text;
        }
      }
    });

    // Update language switcher button
    document.querySelectorAll('[data-i18n-switcher]').forEach(el => {
      const lang = this._currentLang;
      el.textContent = lang === 'tr' ? 'EN' : 'TR';
      el.setAttribute('aria-label', `Switch to ${lang === 'tr' ? 'English' : 'Turkish'}`);
    });
  }

  _emit(event, data) {
    this._listeners.forEach(cb => {
      try { cb(data); } catch (e) { console.warn('Language listener error:', e); }
    });
    // Also dispatch DOM event
    document.dispatchEvent(new CustomEvent(event, { detail: data }));
  }
}

// Global instance
const langManager = new LanguageManager();

// Auto-init on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => langManager.init());
} else {
  langManager.init();
}