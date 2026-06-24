"""Intent-aware model router with complexity scoring.

Analyses incoming prompts to classify intent, calculate complexity,
and route to the appropriate model tier (Fast/Smart/Deep).

Architecture (from ARCHITECTURE.md §6):
    Intent Classifier → Complexity Scoring → Tier Selection
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ModelTier(str, Enum):
    """Model tiers corresponding to capacity and latency budgets."""

    FAST = "fast"  # 1-3B: FIM, autocomplete (<150ms target)
    SMART = "smart"  # 7B: chat, explain, code review
    DEEP = "deep"  # 13-16B: refactor, architecture, complex reasoning


class Intent(str, Enum):
    """Supported intent categories for routing decisions."""

    COMPLETION = "completion"  # Fill-in-the-Middle
    CHAT = "chat"  # General conversation
    EXPLAIN = "explain"  # Code explanation
    TEST = "test"  # Test generation
    REFACTOR = "refactor"  # Code refactoring
    REVIEW = "review"  # Code review
    DEBUG = "debug"  # Debugging / bug finding
    GENERATE = "generate"  # Code generation from description


@dataclass
class RoutingDecision:
    """The result of a routing evaluation."""

    tier: ModelTier
    intent: Intent
    confidence: float  # 0.0 - 1.0
    complexity_score: int  # 0-100
    reason: str  # Human-readable explanation


@dataclass
class IntentPattern:
    """A pattern associated with a specific intent."""

    pattern: str
    weight: float = 1.0


@dataclass
class ComplexityRule:
    """A rule that contributes to the complexity score."""

    pattern: str
    points: int
    description: str = ""


class ModelRouter:
    """Intent-aware model router with prompt complexity scoring.

    Features:
    - Classifies prompt into 7 supported intents
    - Scores complexity on a 0-100 scale
    - Selects the appropriate ModelTier based on intent + complexity
    - Provides confidence and reasoning for each decision

    Complexity factors:
    - Prompt length and structure
    - Presence of complex keywords (refactor, architecture, security)
    - Code density (braces, semicolons, operators)
    - File context size (if provided)
    - Multi-file awareness

    Intent detection priority:
    1. FIM patterns (code prefix with function/class/import start)
    2. Explicit intent keywords (explain, test, refactor, etc.)
    3. Code vs natural language ratio
    4. Default to CHAT
    """

    # Complexity-increasing keywords and their point values
    _COMPLEX_PATTERNS: list[ComplexityRule] = [
        ComplexityRule(r"(refactor|redesign|restructure|migrate)", 30, "Structural change"),
        ComplexityRule(r"(architecture|design pattern|best practice)", 25, "Design discussion"),
        ComplexityRule(r"(optimize|performance|memory leak|bottleneck)", 20, "Performance"),
        ComplexityRule(r"(security|vulnerability|exploit|authentication)", 25, "Security"),
        ComplexityRule(r"(test|unit test|integration test|e2e|assert)", 15, "Testing"),
        ComplexityRule(r"(explain|describe|what does|how does|why)", 10, "Explanation"),
        ComplexityRule(r"(async|concurrent|parallel|thread|await)", 20, "Concurrency"),
        ComplexityRule(r"(database|sql|orm|query|migration)", 15, "Data layer"),
        ComplexityRule(r"(deploy|ci/cd|docker|kubernetes|pipeline)", 20, "DevOps"),
    ]

    # Intent-specific regex patterns
    _INTENT_PATTERNS: dict[Intent, list[IntentPattern]] = {
        Intent.COMPLETION: [
            IntentPattern(r"^\s*(def |class |function |import |from |const |let |var )"),
            IntentPattern(r"^\s*(if |for |while |switch |try |pub fn|impl )"),
            IntentPattern(r"^\s*(export |interface |type |enum |struct |trait )"),
        ],
        Intent.EXPLAIN: [
            IntentPattern(r"(explain|acikla|ne ise yarar|nasil calisir)"),
            IntentPattern(r"(what does|how does|why is|describe this)"),
            IntentPattern(r"(bu kod ne yapiyor|aciklar misin)"),
        ],
        Intent.TEST: [
            IntentPattern(r"(test|birim test|unittest|pytest|vitest)"),
            IntentPattern(r"(test case|assert|expect|should|describe|it\(|test\()"),
            IntentPattern(r"(test yaz|test olustur|generate test)"),
        ],
        Intent.REFACTOR: [
            IntentPattern(r"(refactor|duzenle|iyilestir|modernize)"),
            IntentPattern(r"(clean up|simplify|extract|reorganize)"),
            IntentPattern(r"(kodu duzenle|yeniden yapilandir)"),
        ],
        Intent.REVIEW: [
            IntentPattern(r"(review|incele|feedback|code review)"),
            IntentPattern(r"(hatali?|bug|issue|problem|vulnerability)"),
            IntentPattern(r"(kodu incele|gozden gecir)"),
        ],
        Intent.DEBUG: [
            IntentPattern(r"(debug|hata ayikla|hatali? bul)"),
            IntentPattern(r"(crash|exception|stack trace|error log)"),
            IntentPattern(r"(neden calismiyor|not working|broken)"),
        ],
        Intent.GENERATE: [
            IntentPattern(r"(generate|olustur|yaz|write|create)"),
            IntentPattern(r"(bana .+ yaz|bir .+ olustur)"),
            IntentPattern(r"(implement|uygula|kodla)"),
        ],
        Intent.CHAT: [
            IntentPattern(r".*"),  # Catch-all with low weight
        ],
    }

    def __init__(self) -> None:
        self._stats: dict[str, int] = {
            "total_routes": 0,
            "fast_routes": 0,
            "smart_routes": 0,
            "deep_routes": 0,
        }

    def route(
        self,
        prompt: str,
        file_context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Analyse the prompt and return a routing decision.

        Args:
            prompt: The user's input prompt or code context.
            file_context: Optional metadata about the current file
                (size, language, path, file_count).

        Returns:
            A RoutingDecision with tier, intent, confidence, and reason.
        """
        self._stats["total_routes"] += 1

        # 1. Classify intent
        intent = self._classify_intent(prompt)

        # 2. Calculate complexity score
        complexity = self._calculate_complexity(prompt, file_context)

        # 3. Select tier based on intent + complexity
        tier, reason = self._select_tier(intent, complexity, file_context)

        # 4. Compute confidence (normalised complexity / 100, capped at 0.95)
        confidence = min(complexity / 100, 0.95)

        # Update stats
        if tier == ModelTier.FAST:
            self._stats["fast_routes"] += 1
        elif tier == ModelTier.SMART:
            self._stats["smart_routes"] += 1
        else:
            self._stats["deep_routes"] += 1

        return RoutingDecision(
            tier=tier,
            intent=intent,
            confidence=round(confidence, 3),
            complexity_score=complexity,
            reason=reason,
        )

    def _classify_intent(self, prompt: str) -> Intent:
        """Determine the user's intent from the prompt text."""
        prompt_lower = prompt.lower().strip()

        # Fast-path: short code-like prompts → COMPLETION
        if len(prompt) < 1000:
            for pattern in self._INTENT_PATTERNS[Intent.COMPLETION]:
                if re.search(pattern.pattern, prompt_lower):
                    return Intent.COMPLETION

        # Score each intent by matching patterns
        best_intent = Intent.CHAT
        best_score = 0.0

        for intent, patterns in self._INTENT_PATTERNS.items():
            if intent == Intent.COMPLETION:
                continue
            if intent == Intent.CHAT:
                continue

            score = 0.0
            for ip in patterns:
                matches = re.findall(ip.pattern, prompt_lower)
                score += len(matches) * ip.weight

            if score > best_score:
                best_score = score
                best_intent = intent

        if best_score < 0.5:
            code_ratio = self._estimate_code_ratio(prompt_lower)
            if code_ratio > 0.6:
                return Intent.COMPLETION
            return Intent.CHAT

        return best_intent

    def _calculate_complexity(
        self,
        prompt: str,
        file_context: dict[str, Any] | None = None,
    ) -> int:
        """Calculate prompt complexity on a 0-100 scale."""
        score = 0
        prompt_lower = prompt.lower()

        # 1. Length-based scoring (0-20)
        length = len(prompt)
        if length > 2000:
            score += 20
        elif length > 1000:
            score += 15
        elif length > 500:
            score += 10
        elif length > 200:
            score += 5

        # 2. Complexity keyword matching (0-40, cumulative)
        keyword_score = 0
        for rule in self._COMPLEX_PATTERNS:
            matches = re.findall(rule.pattern, prompt_lower)
            if matches:
                keyword_score += rule.points * min(len(matches), 3)

        score += min(keyword_score, 40)

        # 3. Code density (0-15)
        code_ratio = self._estimate_code_ratio(prompt_lower)
        if code_ratio > 0.8:
            score += 15
        elif code_ratio > 0.6:
            score += 10
        elif code_ratio > 0.4:
            score += 5

        # 4. File context (0-25)
        if file_context:
            file_size = file_context.get("size", 0)
            if file_size > 5000:
                score += 15
            elif file_size > 2000:
                score += 10
            elif file_size > 500:
                score += 5

            file_count = file_context.get("file_count", 1)
            if file_count > 5:
                score += 10
            elif file_count > 3:
                score += 5

            language = file_context.get("language", "")
            if language in ("rust", "c++", "cpp", "haskell"):
                score += 5

        return min(score, 100)

    def _select_tier(
        self,
        intent: Intent,
        complexity: int,
        file_context: dict[str, Any] | None = None,
    ) -> tuple[ModelTier, str]:
        """Select the appropriate model tier based on intent + complexity."""
        if intent == Intent.COMPLETION:
            return ModelTier.FAST, f"FIM completion (intent={intent.value})"

        if complexity > 70:
            return (
                ModelTier.DEEP,
                f"High complexity ({complexity}): requires deep model",
            )

        if complexity > 30 or intent in (Intent.REFACTOR, Intent.REVIEW):
            return (
                ModelTier.SMART,
                f"Medium complexity ({complexity}, intent={intent.value})",
            )

        return ModelTier.FAST, f"Low complexity ({complexity}, intent={intent.value})"

    def _estimate_code_ratio(self, text: str) -> float:
        """Estimate the ratio of code-like content in the text."""
        if not text.strip():
            return 0.0

        code_chars = len(re.findall(r"[{}();=+\-*/%<>&|!~^\[\].,:#@]", text))
        code_keywords = len(
            re.findall(
                r"\b(def|class|import|return|if|else|for|while|try|except|"
                r"const|let|var|function|export|interface|type|pub|fn|impl)\b",
                text,
            )
        )

        total_code_signals = code_chars + (code_keywords * 3)
        max_signals = len(text) * 0.3

        return min(total_code_signals / max_signals, 1.0)

    def get_stats(self) -> dict[str, int]:
        """Return routing statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset all routing statistics to zero."""
        for key in self._stats:
            self._stats[key] = 0
