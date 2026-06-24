"""Prompt templates and FIM engine for YontAI.

DeepSeek-Coder FIM formatı, sohbet şablonu ve kod eylemleri için
optimize edilmiş prompt şablonları sağlar.

FIM Formatı:
    <|fim_begin|>{prefix}<|fim_hole|>{suffix}<|fim_end|>

Sohbet Formatı:
    <|system|>...<|user|>...<|assistant|>
"""

from __future__ import annotations

from dataclasses import dataclass

# Varsayılan sistem mesajı (Türkçe)
DEFAULT_SYSTEM_MESSAGE = (
    "Sen dünyanın en iyi yazılım geliştirme asistanısın. "
    "Cevapların doğru, temiz kod prensiplerine uygun ve her zaman "
    "Türkçe açıklamalı olsun. Kod üretirken açıklama satırları ekle, "
    "tip ipuçlarını kullan ve en iyi pratikleri takip et."
)

# DeepSeek-Coder özel sistem mesajı
DEEPSEEK_SYSTEM_MESSAGE = (
    "You are an AI programming assistant. Follow the user's requirements "
    "carefully & to the letter. First think step-by-step, explain your "
    "reasoning, then write the code. Always use Turkish for explanations."
)


@dataclass
class FIMTemplate:
    """Fill-in-the-Middle şablonu.

    DeepSeek-Coder FIM formatını kullanır.
    """

    prefix: str
    suffix: str
    add_system: bool = False
    system_message: str = ""

    def build(self) -> str:
        """FIM prompt'unu oluştur."""
        parts: list[str] = []
        if self.add_system and self.system_message:
            parts.append(f"<|system|>\n{self.system_message}\n")
        parts.append(f"<|fim_begin|>{self.prefix}<|fim_hole|>{self.suffix}<|fim_end|>")
        return "".join(parts)


@dataclass
class ChatTemplate:
    """Sohbet şablonu.

    DeepSeek-Coder sohbet formatını kullanır.
    """

    messages: list[dict[str, str]]
    system_message: str = DEFAULT_SYSTEM_MESSAGE
    model_family: str = "deepseek"

    def build(self) -> str:
        """Sohbet prompt'unu oluştur."""
        parts: list[str] = []

        # Sistem mesajı
        sys_msg = self.system_message
        if self.model_family in ("deepseek", "coder"):
            sys_msg = DEEPSEEK_SYSTEM_MESSAGE if not self.system_message else self.system_message

        parts.append(f"<|system|>\n{sys_msg}\n")

        # Mesajlar
        for msg in self.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"<|system|>\n{content}\n")
            elif role == "user":
                parts.append(f"<|user|>\n{content}\n")
            elif role == "assistant":
                parts.append(f"<|assistant|>\n{content}\n")

        parts.append("<|assistant|>\n")
        return "".join(parts)


class CodeActionTemplates:
    """Kod eylemleri için hazır prompt şablonları."""

    @staticmethod
    def explain_code(code: str, language: str = "python") -> str:
        """Kodu açıkla (Türkçe).

        Args:
            code: Açıklanacak kod
            language: Programlama dili

        Returns:
            Prompt metni
        """
        return (
            f"Aşağıdaki {language} kodunu satır satır açıkla:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Her fonksiyonun, sınıfın ve önemli değişkenin ne işe yaradığını "
            "Türkçe olarak açıkla. Karmaşık mantığı basitleştirerek anlat."
        )

    @staticmethod
    def generate_tests(code: str, language: str = "python") -> str:
        """Kod için test yaz.

        Args:
            code: Test edilecek kod
            language: Programlama dili

        Returns:
            Prompt metni
        """
        return (
            f"Aşağıdaki {language} kodu için kapsamlı birim testleri yaz:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Testler şunları kapsamalı:\n"
            "- Normal durumlar (happy path)\n"
            "- Kenar durumlar (edge cases)\n"
            "- Hata durumları (error cases)\n"
            "- Sınır değerleri (boundary values)\n\n"
            "Test framework'ü olarak pytest (Python) veya vitest (JS/TS) kullan. "
            "Testleri Türkçe açıklamalı yaz."
        )

    @staticmethod
    def refactor_code(
        code: str,
        language: str = "python",
        target: str = "performance",
    ) -> str:
        """Kodu refactor et.

        Args:
            code: Refactor edilecek kod
            language: Programlama dili
            target: Hedef (performance, readability, maintainability)

        Returns:
            Prompt metni
        """
        target_descriptions = {
            "performance": "performansı artırmak",
            "readability": "okunabilirliği artırmak",
            "maintainability": "bakımı kolaylaştırmak",
            "security": "güvenliği artırmak",
            "async": "asenkron hale getirmek",
        }

        description = target_descriptions.get(target, f"{target} iyileştirmesi yapmak")

        return (
            f"Aşağıdaki {language} kodunu {description} için refactor et:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Yaptığın değişiklikleri Türkçe açıkla. "
            "Her değişikliğin nedenini belirt. "
            "Eski ve yeni kod arasındaki farkı göster."
        )

    @staticmethod
    def add_type_hints(code: str, language: str = "python") -> str:
        """Tip ipuçları ekle.

        Args:
            code: Tip ipucu eklenecek kod
            language: Programlama dili

        Returns:
            Prompt metni
        """
        return (
            f"Aşağıdaki {language} koduna tip ipuçları (type hints) ekle:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Tüm fonksiyon parametrelerine ve dönüş değerlerine "
            "uygun tipleri ekle. Değişkenlere de mümkünse tip ekle. "
            "Python için typing modülünü kullan. "
            "Değişikliklerini Türkçe açıkla."
        )

    @staticmethod
    def review_code(code: str, language: str = "python") -> str:
        """Kod incelemesi yap.

        Args:
            code: İncelenecek kod
            language: Programlama dili

        Returns:
            Prompt metni
        """
        return (
            f"Aşağıdaki {language} kodunu incele ve feedback ver:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Şu konuları değerlendir:\n"
            "- Kod kalitesi ve okunabilirlik\n"
            "- Performans sorunları\n"
            "- Güvenlik açıkları\n"
            "- En iyi pratiklere uygunluk\n"
            "- Eksik hata yönetimi\n"
            "- Test edilebilirlik\n\n"
            "Her maddeyi Türkçe detaylı açıkla ve önerilerini belirt."
        )

    @staticmethod
    def find_bugs(code: str, language: str = "python") -> str:
        """Koddaki hataları bul.

        Args:
            code: İncelenecek kod
            language: Programlama dili

        Returns:
            Prompt metni
        """
        return (
            f"Aşağıdaki {language} kodundaki potansiyel hataları ve "
            f"mantık sorunlarını bul:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Şu tür hataları ara:\n"
            "- Null/None referans hataları\n"
            "- Index out of bounds\n"
            "- Race condition / thread safety\n"
            "- Kaynak sızıntıları (dosya, ağ bağlantısı)\n"
            "- Yanlış tip kullanımı\n"
            "- Mantık hataları\n\n"
            "Her hatayı Türkçe açıkla ve düzeltme önerisi sun."
        )

    @staticmethod
    def optimize_imports(code: str, language: str = "python") -> str:
        """Import'ları optimize et.

        Args:
            code: İncelenecek kod
            language: Programlama dili

        Returns:
            Prompt metni
        """
        return (
            f"Aşağıdaki {language} kodundaki import ifadelerini optimize et:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Şunları yap:\n"
            "- Kullanılmayan import'ları kaldır\n"
            "- Import'ları grupla (standart kütüphane, üçüncü parti, yerel)\n"
            "- Gereksiz wildcard import'ları (*) belirli import'larla değiştir\n"
            "- Döngüsel import'ları tespit et\n\n"
            "Değişiklikleri Türkçe açıkla."
        )

    @staticmethod
    def add_docstrings(code: str, language: str = "python") -> str:
        """Dökümantasyon stringleri ekle.

        Args:
            code: Dökümantasyon eklenecek kod
            language: Programlama dili

        Returns:
            Prompt metni
        """
        return (
            f"Aşağıdaki {language} koduna dökümantasyon (docstring) ekle:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Tüm fonksiyon, sınıf ve modüllere açıklama ekle:\n"
            "- Ne yaptığı (kısa özet)\n"
            "- Parametreler ve tipleri\n"
            "- Dönüş değeri ve tipi\n"
            "- Raise ettiği istisnalar\n"
            "- Kullanım örneği (örnek kod)\n\n"
            "Python için Google-style veya NumPy-style docstring formatı kullan. "
            "Dökümantasyonu Türkçe yaz."
        )

    @staticmethod
    def convert_language(code: str, from_lang: str, to_lang: str) -> str:
        """Kodu bir dilden diğerine çevir.

        Args:
            code: Kaynak kod
            from_lang: Kaynak dil
            to_lang: Hedef dil

        Returns:
            Prompt metni
        """
        return (
            f"Aşağıdaki {from_lang} kodunu {to_lang} diline çevir:\n\n"
            f"```{from_lang}\n{code}\n```\n\n"
            "Çevirirken şunlara dikkat et:\n"
            "- Hedef dilin en iyi pratiklerini kullan\n"
            "- Aynı mantığı ve yapıyı koru\n"
            "- Performans açısından uygun dönüşümler yap\n"
            "- Hedef dile özgü kütüphaneleri tercih et\n\n"
            "Değişiklikleri Türkçe açıkla."
        )


def get_template_for_model(model_family: str | None) -> str:
    """Model ailesine göre uygun template formatını döndür.

    Args:
        model_family: Model ailesi (deepseek, llama, mistral, qwen, gemma)

    Returns:
        Template format adı: "deepseek", "llama", "mistral", "default"
    """
    if not model_family:
        return "deepseek"

    family = model_family.lower()

    if family in ("deepseek", "coder"):
        return "deepseek"
    elif family in ("llama", "llama3", "codellama"):
        return "llama"
    elif family in ("mistral", "mixtral"):
        return "mistral"
    elif family in ("qwen", "qwen2", "codeqwen"):
        return "qwen"
    elif family in ("gemma", "gemma2"):
        return "gemma"
    else:
        return "default"


def build_system_message(
    project_context: str | None = None,
    language: str | None = None,
    framework: str | None = None,
    code_style: str | None = None,
) -> str:
    """Proje özelinde sistem mesajı oluştur.

    Args:
        project_context: Proje hakkında kısa açıklama
        language: Kullanılan programlama dili
        framework: Kullanılan framework
        code_style: Kod stili kuralları

    Returns:
        Sistem mesajı
    """
    parts = [DEFAULT_SYSTEM_MESSAGE]

    if language or framework:
        details = "Mevcut proje "
        if language:
            details += f"{language} "
        if framework:
            details += f"({framework}) "
        details += "ile yazılıyor."
        parts.append(details)

    if project_context:
        parts.append(f"\nProje: {project_context}")

    if code_style:
        parts.append(f"\nKod stili: {code_style}")

    return "\n".join(parts)