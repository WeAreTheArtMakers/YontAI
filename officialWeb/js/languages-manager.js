/**
 * YontAI Language Manager
 * 
 * API: setLanguage('tr'), getText('key'), getCurrentLanguage()
 * HTML: <h1 data-i18n="hero.title"></h1>
 * 
 * Adding a language: Add key to LANGUAGES, copy all en keys, translate values.
 */

const LANGUAGES = {
  tr: {
    nav: { home: 'Ana Sayfa', features: 'Özellikler', architecture: 'Mimari', performance: 'Performans', about: 'Hakkında', contact: 'İletişim', getStarted: 'Başla', viewOnGitHub: "GitHub'da Gör" },
    hero: { badge: '🚀 Apple Silicon için Optimize Edildi', title: 'Kendi Yapay Zeka Kod Asistanını Oluştur', subtitle: 'YontAI ile kendi coding AI modelini eğit, internetten güncel kod topla, proje bağlamını anla ve akıllı kod tamamlama ile üretkenliğini katla.', ctaPrimary: 'Başlamak için', ctaSecondary: "GitHub'da Keşfet", typingPrefix: 'Sen yazarken, YontAI ', typingTexts: ['kodunu tamamlar', 'hatalarını bulur', 'testlerini yazar', 'refactor eder', 'dökümantasyon ekler'] },
    features: { title: 'Güçlü Özellikler', subtitle: 'YontAI, yerel AI kod asistanınızı bir üst seviyeye taşımak için tasarlandı.', mlx: { title: 'MLX Apple Silicon Desteği', desc: "M1/M2/M3/M4 çiplerinde %40'a varan hız artışı." }, multiModel: { title: 'Çoklu Model Orkestrasyonu', desc: 'Akıllı routing: 1-3B hızlı model FIM için, 7-16B akıllı model sohbet için.' }, fim: { title: 'FIM Kod Tamamlama', desc: 'DeepSeek-Coder formatında Fill-in-the-Middle. <150ms yanıt süresi.' }, rag: { title: 'RAG Bağlam Motoru', desc: '17 dilde AST parsing. ChromaDB vektör arama. Akıllı context.' }, knowledge: { title: 'İnternetten Kod Toplama', desc: 'GitHub API, npm, PyPI entegrasyonu.' }, training: { title: 'AI Lab Model Eğitimi', desc: 'MLX ile LoRA/QLoRA fine-tuning.' } },
    architecture: { title: 'Sistem Mimarisi', subtitle: 'Modüler ve genişletilebilir mimari.', layers: { ui: 'Kullanıcı Arayüzü', api: 'API Katmanı', runtime: 'Model Runtime', rag: 'RAG Motoru', training: 'Eğitim Pipeline' } },
    performance: { title: 'Performans (M1 Pro 16 GB)', subtitle: 'Apple Silicon benchmark sonuçları.', model: 'Model', quantization: 'Quantization', tokensPerSec: 'Token/s', ramUsage: 'RAM Kullanımı', rows: { deepseek13: { model: 'DeepSeek-Coder 1.3B', quant: 'Q4', tokens: '45-55', ram: '~2.5 GB' }, deepseek67: { model: 'DeepSeek-Coder 6.7B', quant: 'Q4', tokens: '15-22', ram: '~8 GB' }, codeqwen: { model: 'CodeQwen-7B', quant: 'Q4', tokens: '12-18', ram: '~7 GB' }, starcode: { model: 'StarCoder2-3B', quant: 'Q4', tokens: '30-40', ram: '~4 GB' }, fim: { model: 'FIM (1.3B)', quant: 'Q4', tokens: '<200ms', ram: '~2.5 GB' } } },
    about: { title: 'YontAI Nedir?', subtitle: 'Kendi AI modelini oluşturduğun yerel mühendislik laboratuvarı.', mission: 'Tamamen yerel, tamamen gizli, tamamen senin kontrolünde.', cta: 'Başla', stat1: 'Açık Kaynak', stat2: 'Gizlilik Odaklı', stat3: 'Apple Silicon' },
    footer: { copyright: '© 2025 YontAI. Tüm hakları saklıdır.', description: 'Kendi AI kod asistanını oluştur. Açık kaynak, gizlilik odaklı.', quickLinks: 'Hızlı Linkler', resources: 'Kaynaklar', documentation: 'Dokümantasyon', apiReference: 'API Referansı', architecture: 'Mimari', chnagelog: 'Değişiklikler', madeWith: '❤️ ile yapıldı' },
    common: { loading: 'Yükleniyor...', error: 'Hata oluştu', retry: 'Tekrar dene', learnMore: 'Daha Fazla', getStarted: 'Başla', starOnGitHub: 'Yıldızla' },
  },
  en: {
    nav: { home: 'Home', features: 'Features', architecture: 'Architecture', performance: 'Performance', about: 'About', contact: 'Contact', getStarted: 'Get Started', viewOnGitHub: 'View on GitHub' },
    hero: { badge: '🚀 Optimized for Apple Silicon', title: 'Build Your Own AI Coding Assistant', subtitle: 'Train your own coding AI model, gather code from the internet, understand project context, and supercharge your productivity with intelligent code completion.', ctaPrimary: 'Get Started', ctaSecondary: 'Explore on GitHub', typingPrefix: 'While you code, YontAI ', typingTexts: ['completes your code', 'finds your bugs', 'writes your tests', 'refactors your code', 'adds documentation'] },
    features: { title: 'Powerful Features', subtitle: 'Take your local AI coding assistant to the next level.', mlx: { title: 'MLX Apple Silicon Support', desc: 'Up to 40% speed improvement on M1/M2/M3/M4 chips.' }, multiModel: { title: 'Multi-Model Orchestration', desc: 'Smart routing: 1-3B fast model for FIM, 7-16B smart model for chat.' }, fim: { title: 'FIM Code Completion', desc: 'Fill-in-the-Middle with DeepSeek-Coder format. <150ms response time.' }, rag: { title: 'RAG Context Engine', desc: 'AST parsing in 17 languages. ChromaDB vector search. Smart context.' }, knowledge: { title: 'Web Knowledge Ingestion', desc: 'GitHub API, npm, PyPI integration.' }, training: { title: 'AI Lab Model Training', desc: 'LoRA/QLoRA fine-tuning with MLX.' } },
    architecture: { title: 'System Architecture', subtitle: 'Built on a modular, extensible architecture.', layers: { ui: 'User Interface', api: 'API Layer', runtime: 'Model Runtime', rag: 'RAG Engine', training: 'Training Pipeline' } },
    performance: { title: 'Performance (M1 Pro 16 GB)', subtitle: 'Real-world benchmark results on Apple Silicon.', model: 'Model', quantization: 'Quantization', tokensPerSec: 'Token/s', ramUsage: 'RAM Usage', rows: { deepseek13: { model: 'DeepSeek-Coder 1.3B', quant: 'Q4', tokens: '45-55', ram: '~2.5 GB' }, deepseek67: { model: 'DeepSeek-Coder 6.7B', quant: 'Q4', tokens: '15-22', ram: '~8 GB' }, codeqwen: { model: 'CodeQwen-7B', quant: 'Q4', tokens: '12-18', ram: '~7 GB' }, starcode: { model: 'StarCoder2-3B', quant: 'Q4', tokens: '30-40', ram: '~4 GB' }, fim: { model: 'FIM (1.3B)', quant: 'Q4', tokens: '<200ms', ram: '~2.5 GB' } } },
    about: { title: 'What is YontAI?', subtitle: "It's a local AI engineering lab where you create, train, and evolve your own coding AI models.", mission: 'Fully local, fully private, fully under your control.', cta: 'Get Started', stat1: 'Open Source', stat2: 'Privacy First', stat3: 'Apple Silicon' },
    footer: { copyright: '© 2025 YontAI. All rights reserved.', description: 'Build your own AI coding assistant. Open source, privacy-first.', quickLinks: 'Quick Links', resources: 'Resources', documentation: 'Documentation', apiReference: 'API Reference', architecture: 'Architecture', chnagelog: 'Changelog', madeWith: 'Made with ❤️' },
    common: { loading: 'Loading...', error: 'An error occurred', retry: 'Retry', learnMore: 'Learn More', getStarted: 'Get Started', starOnGitHub: 'Star on GitHub' },
  },
};

class LanguageManager {
  constructor() {
    this._currentLang = 'en';
    this._initialized = false;
  }

  init() {
    if (this._initialized) return;
    const saved = localStorage.getItem('yontai_language');
    if (saved && LANGUAGES[saved]) { this._currentLang = saved; }
    else {
      const browserLang = (navigator.language || '').substring(0, 2);
      this._currentLang = LANGUAGES[browserLang] ? browserLang : 'en';
    }
    this._translateDOM();
    document.documentElement.lang = this._currentLang;
    this._initialized = true;
  }

  getCurrentLanguage() { return this._currentLang; }

  getText(key) {
    const keys = key.split('.');
    let val = LANGUAGES[this._currentLang];
    for (const k of keys) { if (val && typeof val === 'object' && k in val) { val = val[k]; } else { val = LANGUAGES['en']; for (const ek of keys) { if (val && typeof val === 'object' && ek in val) val = val[ek]; else return key; } break; } }
    return typeof val === 'string' ? val : key;
  }

  setLanguage(lang) {
    if (!LANGUAGES[lang] || this._currentLang === lang) return;
    this._currentLang = lang;
    localStorage.setItem('yontai_language', lang);
    document.documentElement.lang = lang;
    this._translateDOM();
    document.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
  }

  toggleLanguage() { this.setLanguage(this._currentLang === 'tr' ? 'en' : 'tr'); }

  _translateDOM() {
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (!key) return;
      const text = this.getText(key);
      if (text !== key) {
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.placeholder = text;
        else if (el.tagName === 'META') el.content = text;
        else el.textContent = text;
      }
    });
    document.querySelectorAll('[data-i18n-switcher]').forEach(el => {
      el.textContent = this._currentLang === 'tr' ? 'EN' : 'TR';
    });
  }
}

// Global instance - auto init on DOMContentLoaded
const langManager = new LanguageManager();
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => langManager.init());
} else {
  langManager.init();
}