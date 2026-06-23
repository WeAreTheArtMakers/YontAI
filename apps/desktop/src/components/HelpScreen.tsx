import { useState } from "react";
import { BookOpen, Cpu, Database, Zap, Target, RefreshCw, GraduationCap, Info } from "lucide-react";

interface GlossaryTerm {
  term: string;
  definition: string;
  example: string;
  whenToUse: string;
  category: string;
}

const glossary: GlossaryTerm[] = [
  // 2026 Yöntemleri
  {
    term: "GRPO (Group Relative Policy Optimization)",
    category: "2026 Yöntemleri",
    definition: "2026'nın en popüler RL yöntemi. Grup bazlı karşılaştırma ile policy optimization yapar. RLVR paradigmasının temel taşıdır.",
    example: "Örnek: Matematik problemleri için birden fazla çözüm üretir ve en iyisini seçer.",
    whenToUse: "Ne zaman kullanılır: Reasoning ve problem-solving yeteneklerini geliştirmek istediğinizde. Özellikle matematik, kod ve mantıksal akıl yürütme için ideal."
  },
  {
    term: "DAPO (Distributed Adaptive Policy Optimization)",
    category: "2026 Yöntemleri",
    definition: "GRPO'nun geliştirilmiş versiyonu. Dağıtık eğitim ve adaptive sampling ile daha hızlı ve verimli. DeepSeek-R1'de kullanıldı.",
    example: "Örnek: 32B model ile AIME 2024'te state-of-the-art sonuçlar (%50 daha az adımda).",
    whenToUse: "Ne zaman kullanılır: Büyük ölçekli RL eğitimi yaparken. GRPO'dan 4.2x daha az rollout maliyeti."
  },
  {
    term: "RLVR (RL with Verifiable Rewards)",
    category: "2026 Yöntemleri",
    definition: "Doğrulanabilir reward'lar ile RL. Matematik, kod gibi doğru/yanlış cevabı net olan görevler için. TÜLU 3'te kullanıldı.",
    example: "Örnek: Kod yazdırıp test case'lerle doğrulama. Doğru çözüm = +1 reward, yanlış = -1.",
    whenToUse: "Ne zaman kullanılır: Ground truth cevabı olan görevlerde. Kod, matematik, mantık problemleri."
  },
  {
    term: "SDPO (Self-Distillation Policy Optimization)",
    category: "2026 Yöntemleri",
    definition: "Kendi kendine distillation yaparak öğrenir. External teacher veya reward model gerektirmez. Token-level feedback kullanır.",
    example: "Örnek: Model kendi çıktılarını değerlendirip iyileştirir (self-play).",
    whenToUse: "Ne zaman kullanılır: Labeled data az olduğunda veya self-improvement istediğinizde."
  },
  
  // Verimli Yöntemler
  {
    term: "LoRA (Low-Rank Adaptation)",
    category: "Verimli Yöntemler",
    definition: "Büyük modelleri verimli fine-tune etmek için low-rank matrisler kullanır. Sadece küçük adapter'lar eğitilir, base model donuk kalır.",
    example: "Örnek: 7B model için sadece 10-50MB adapter. Base model 14GB, adapter 20MB.",
    whenToUse: "Ne zaman kullanılır: Sınırlı GPU belleği (8-16GB) olduğunda. Hızlı iterasyon istediğinizde. Çoklu task için farklı adapter'lar."
  },
  {
    term: "QLoRA (Quantized LoRA)",
    category: "Verimli Yöntemler",
    definition: "LoRA + 4-bit quantization. Model 4-bit'e quantize edilir, sadece LoRA parametreleri full precision'da tutulur.",
    example: "Örnek: 70B modeli 24GB GPU'da eğitebilirsiniz. Normal LoRA 140GB gerektirir.",
    whenToUse: "Ne zaman kullanılır: Çok büyük modeller (30B+) ve çok sınırlı GPU. Consumer GPU'larda (RTX 4090) büyük model eğitimi."
  },
  
  // Tercih Optimizasyonu
  {
    term: "DPO (Direct Preference Optimization)",
    category: "Tercih Optimizasyonu",
    definition: "Reward model olmadan preference learning. 2024'te RLHF'nin yerini aldı. Daha basit, daha hızlı, daha stabil.",
    example: "Örnek: 'Bu cevap daha iyi' şeklinde etiketlenmiş veri ile eğitim. Reward model eğitmeye gerek yok.",
    whenToUse: "Ne zaman kullanılır: Chat modeli hizalama. Paired preference data varsa. RLHF'den daha basit alternatif."
  },
  {
    term: "ORPO (Odds Ratio Preference Optimization)",
    category: "Tercih Optimizasyonu",
    definition: "SFT ve preference tuning'i tek aşamada birleştirir. Daha verimli, daha az kaynak. 2024'te popüler oldu.",
    example: "Örnek: İki aşama yerine tek aşama. SFT + DPO = ORPO.",
    whenToUse: "Ne zaman kullanılır: Hızlı prototipleme. Kaynak tasarrufu. İki aşamalı pipeline yerine tek aşama."
  },
  {
    term: "KTO (Kahneman-Tversky Optimization)",
    category: "Tercih Optimizasyonu",
    definition: "Unpaired feedback ile çalışır. 'Bu iyi' veya 'Bu kötü' yeterli, karşılaştırma gerekmez. Daha esnek veri formatı.",
    example: "Örnek: Sadece thumbs up/down feedback. Paired comparison gerekmez.",
    whenToUse: "Ne zaman kullanılır: Paired data toplamak zor olduğunda. Binary feedback varsa."
  },
  
  // Pekiştirmeli Öğrenme
  {
    term: "PPO (Proximal Policy Optimization)",
    category: "Pekiştirmeli Öğrenme",
    definition: "Klasik RLHF yöntemi. Reward model + actor-critic algoritması. Karmaşık ama güçlü ve kanıtlanmış.",
    example: "Örnek: ChatGPT'nin ilk versiyonlarında kullanıldı. Reward model eğitilir, sonra PPO ile policy optimize edilir.",
    whenToUse: "Ne zaman kullanılır: Karmaşık reward fonksiyonları. Production sistemler. Maksimum performans gerektiğinde."
  },
  {
    term: "RLHF (RL from Human Feedback)",
    category: "Pekiştirmeli Öğrenme",
    definition: "İnsan feedback'i ile reward model eğitimi, sonra RL ile policy optimization. 2023-2024'ün standart yöntemi.",
    example: "Örnek: İnsanlar cevapları sıralar, reward model öğrenir, model bu reward'a göre optimize edilir.",
    whenToUse: "Ne zaman kullanılır: İnsan değerlendirmesi kritik olduğunda. Subjektif kalite metrikleri."
  },
  {
    term: "RLAIF (RL from AI Feedback)",
    category: "Pekiştirmeli Öğrenme",
    definition: "İnsan yerine AI-generated feedback kullanır. Daha scalable, daha ucuz. Anthropic'in Constitutional AI yaklaşımı.",
    example: "Örnek: GPT-4 feedback verir, model bu feedback'e göre öğrenir. İnsan annotator gerekmez.",
    whenToUse: "Ne zaman kullanılır: Büyük ölçekli eğitim. İnsan feedback pahalı olduğunda. Scalability önemli olduğunda."
  },
  
  // Hiperparametreler
  {
    term: "Epochs (Dönem)",
    category: "Hiperparametreler",
    definition: "Modelin tüm eğitim veri setini kaç kez göreceği. 1 epoch = veri setinin tamamı bir kez.",
    example: "Örnek: 3 epoch = Model veri setini 3 kez görür. 1000 örnek x 3 epoch = 3000 training step.",
    whenToUse: "Önerilen: Küçük veri setleri (<1000 örnek) için 3-5 epoch. Büyük veri setleri (>10K) için 1-2 epoch. Overfitting'e dikkat!"
  },
  {
    term: "Batch Size (Grup Boyutu)",
    category: "Hiperparametreler",
    definition: "Her gradient update'te kaç örnek işlenir. Büyük batch = daha stabil ama daha fazla bellek. Küçük batch = daha az bellek ama daha noisy.",
    example: "Örnek: Batch size 4 = Her adımda 4 örnek işlenir, sonra gradient update. 1000 örnek / 4 = 250 step per epoch.",
    whenToUse: "Önerilen: GPU belleğinize göre. 8GB GPU = 1-4, 16GB = 4-8, 24GB = 8-16, 48GB+ = 16-32. Gradient accumulation ile büyük effective batch."
  },
  {
    term: "Learning Rate (Öğrenme Hızı)",
    category: "Hiperparametreler",
    definition: "Model ağırlıklarının ne kadar hızlı güncelleneceği. Çok büyük = instability, çok küçük = yavaş öğrenme.",
    example: "Örnek: 2e-4 = 0.0002. Her gradient update'te ağırlıklar bu oranda değişir.",
    whenToUse: "Önerilen: LoRA için 1e-4 - 5e-4 (0.0001-0.0005). QLoRA için 2e-4 - 1e-3. Full fine-tune için 1e-5 - 1e-4. DPO/ORPO için 5e-7 - 5e-6."
  },
  {
    term: "LoRA Rank",
    category: "Hiperparametreler",
    definition: "LoRA matrislerinin boyutu. Büyük rank = daha fazla kapasite ama daha fazla parametre. Küçük rank = daha az parametre ama sınırlı kapasite.",
    example: "Örnek: Rank 8 = 8x8 matris. Rank 16 = 16x16 matris. Rank 16 yaklaşık 2x daha fazla parametre.",
    whenToUse: "Önerilen: Basit tasklar için rank 8. Genel amaçlı için rank 16. Karmaşık tasklar için rank 32-64. Rank 128+ nadiren gerekir."
  },
  {
    term: "Max Sequence Length",
    category: "Hiperparametreler",
    definition: "Modelin işleyebileceği maksimum token sayısı. Uzun context = daha fazla bellek. Kısa context = daha az bellek.",
    example: "Örnek: 2048 token ≈ 1500 kelime. 4096 token ≈ 3000 kelime. 8192 token ≈ 6000 kelime.",
    whenToUse: "Önerilen: Chat için 2048-4096. Uzun dökümanlar için 8192-16384. Code için 4096-8192. Bellek sınırınıza göre ayarlayın."
  }
];

const categories = [
  { id: "2026", label: "🚀 2026 Yöntemleri", icon: Zap },
  { id: "efficient", label: "⚡ Verimli Yöntemler", icon: Cpu },
  { id: "preference", label: "🎯 Tercih Optimizasyonu", icon: Target },
  { id: "rl", label: "🔄 Pekiştirmeli Öğrenme", icon: RefreshCw },
  { id: "hyperparams", label: "⚙️ Hiperparametreler", icon: Database },
];

export function HelpScreen() {
  const [selectedCategory, setSelectedCategory] = useState<string>("2026");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredTerms = glossary.filter(term => {
    const matchesCategory = selectedCategory === "all" || 
      (selectedCategory === "2026" && term.category === "2026 Yöntemleri") ||
      (selectedCategory === "efficient" && term.category === "Verimli Yöntemler") ||
      (selectedCategory === "preference" && term.category === "Tercih Optimizasyonu") ||
      (selectedCategory === "rl" && term.category === "Pekiştirmeli Öğrenme") ||
      (selectedCategory === "hyperparams" && term.category === "Hiperparametreler");
    
    const matchesSearch = searchQuery === "" || 
      term.term.toLowerCase().includes(searchQuery.toLowerCase()) ||
      term.definition.toLowerCase().includes(searchQuery.toLowerCase()) ||
      term.category.toLowerCase().includes(searchQuery.toLowerCase());
    
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-white/5 bg-background/50 backdrop-blur-xl px-8 py-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary/60 text-white shadow-lg shadow-primary/20">
            <BookOpen className="size-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Yardım & Rehber</h1>
            <p className="text-sm text-muted-foreground mt-1">
              YontAI kullanım kılavuzu ve terimler sözlüğü
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 border-r border-white/5 bg-background/30 p-4 overflow-y-auto">
          <div className="space-y-2">
            <button
              onClick={() => setSelectedCategory("all")}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedCategory === "all"
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-white/5"
              }`}
            >
              📚 Tüm Terimler
            </button>
            {categories.map(cat => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                  selectedCategory === cat.id
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-white/5"
                }`}
              >
                <cat.icon className="size-4" />
                {cat.label}
              </button>
            ))}
          </div>

          <div className="mt-6 pt-6 border-t border-white/5">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Hızlı Başlangıç
            </h3>
            <div className="space-y-2 text-sm">
              <button 
                onClick={() => setSelectedCategory("efficient")}
                className="block w-full text-left text-muted-foreground hover:text-primary transition-colors"
              >
                → Model Yükleme (LoRA/QLoRA)
              </button>
              <button 
                onClick={() => setSelectedCategory("2026")}
                className="block w-full text-left text-muted-foreground hover:text-primary transition-colors"
              >
                → İlk Chat (Vision Model)
              </button>
              <button 
                onClick={() => setSelectedCategory("hyperparams")}
                className="block w-full text-left text-muted-foreground hover:text-primary transition-colors"
              >
                → Veri Seti Oluşturma
              </button>
              <button 
                onClick={() => setSelectedCategory("2026")}
                className="block w-full text-left text-muted-foreground hover:text-primary transition-colors"
              >
                → Fine-Tuning Başlatma (GRPO)
              </button>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-8">
          {/* Search */}
          <div className="mb-6">
            <input
              type="text"
              placeholder="Terim ara..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full max-w-md bg-background/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          {/* Terms Grid */}
          <div className="space-y-6">
            {filteredTerms.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Info className="size-12 mx-auto mb-4 opacity-50" />
                <p>Aradığınız terim bulunamadı.</p>
              </div>
            ) : (
              filteredTerms.map((term, index) => (
                <div key={index} className="glass-panel p-6 rounded-2xl border border-white/5">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <h3 className="text-lg font-semibold text-primary">{term.term}</h3>
                    <span className="text-xs px-2 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
                      {term.category}
                    </span>
                  </div>
                  
                  <div className="space-y-3 text-sm">
                    <div>
                      <p className="text-muted-foreground leading-relaxed">{term.definition}</p>
                    </div>
                    
                    <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                      <p className="text-xs font-semibold text-primary mb-1">💡 Örnek</p>
                      <p className="text-muted-foreground">{term.example}</p>
                    </div>
                    
                    <div className="bg-primary/5 rounded-lg p-3 border border-primary/10">
                      <p className="text-xs font-semibold text-primary mb-1">🎯 Kullanım</p>
                      <p className="text-muted-foreground">{term.whenToUse}</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
