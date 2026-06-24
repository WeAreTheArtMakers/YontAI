"""
MLX LoRA Trainer — fine-tunes models on Apple Silicon using mlx-lm.
Adds LoRA adapters to q_proj / v_proj, uses gradient accumulation
to fit within 16 GB RAM, and reports progress via callbacks.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import mlx.core as mx
import mlx.nn as nn
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols / callbacks
# ---------------------------------------------------------------------------


class ProgressCallback(Protocol):
    """Called periodically during training with current metrics."""

    def __call__(
        self,
        epoch: int,
        step: int,
        total_steps: int,
        loss: float,
        learning_rate: float,
        **extra: Any,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class LoRAConfig:
    """Configuration for LoRA layers."""

    rank: int = 16
    alpha: float = 32.0
    dropout: float = 0.05
    target_modules: tuple[str, ...] = ("q_proj", "v_proj")
    bias: str = "none"


@dataclass
class TrainingConfig:
    """Hyper-parameters for the training loop."""

    batch_size: int = 4
    micro_batch_size: int = 1
    learning_rate: float = 2e-4
    max_steps: int = 1000
    warmup_steps: int = 100
    max_grad_norm: float = 1.0
    eval_steps: int = 100
    save_steps: int = 500
    log_steps: int = 10

    @property
    def gradient_accumulation_steps(self) -> int:
        """Derive accumulation steps to simulate larger batch on limited VRAM."""
        return max(1, self.batch_size // self.micro_batch_size)


@dataclass
class TrainingMetrics:
    """Aggregated training results."""

    final_loss: float = 0.0
    best_loss: float = float("inf")
    total_steps: int = 0
    total_time_s: float = 0.0
    avg_tokens_per_sec: float = 0.0
    loss_history: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# MLX LoRA Trainer
# ---------------------------------------------------------------------------


class MLXLoRATrainer:
    """
    Trains a model on Apple Silicon using LoRA adapters via mlx-lm.

    Features:
    - Loads any HuggingFace-compatible model via ``mlx_lm``
    - Adds LoRA layers to ``q_proj`` and ``v_proj`` (configurable)
    - Gradient accumulation to fit within ~16 GB unified memory
    - Saves compact LoRA weights (~10 MB)
    - Reports progress via user-supplied callbacks
    """

    def __init__(
        self,
        model_name: str,
        lora_config: LoRAConfig | None = None,
        training_config: TrainingConfig | None = None,
        adapter_path: str | Path = "adapters",
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.model_name = model_name
        self.lora_config = lora_config or LoRAConfig()
        self.training_config = training_config or TrainingConfig()
        self.adapter_path = Path(adapter_path)
        self.progress_callback = progress_callback

        # Will be populated during load
        self._model: nn.Module | None = None
        self._tokenizer: Any = None
        self._lora_layers: list[nn.Module] = []
        self._optimizer: nn.Optimizer | None = None

    # -- Public API --------------------------------------------------------

    def load_model(self) -> None:
        """
        Load the base model and tokenizer via ``mlx_lm``, then apply LoRA.
        """
        try:
            from mlx_lm import load as mlx_load
            from mlx_lm.utils import get_model_path
        except ImportError as exc:
            raise ImportError(
                "mlx_lm is required. Install with: pip install mlx-lm"
            ) from exc

        logger.info("Loading model '%s' ...", self.model_name)
        model_path = get_model_path(self.model_name)

        # mlx_lm.load returns (model, tokenizer)
        self._model, self._tokenizer = mlx_load(model_path)

        # Freeze base model parameters
        for p in self._model.parameters():
            p.requires_grad = False

        # Inject LoRA adapters
        self._add_lora_layers()
        logger.info(
            "LoRA adapters added (rank=%d, modules=%s)",
            self.lora_config.rank,
            self.lora_config.target_modules,
        )

        # Count trainable parameters
        trainable = sum(
            p.size for p in self._model.parameters() if p.requires_grad
        )
        total = sum(p.size for p in self._model.parameters())
        logger.info(
            "Trainable params: %d / %d (%.2f%%)",
            trainable,
            total,
            100.0 * trainable / max(total, 1),
        )

    def train(
        self,
        train_iterator: Any,
        val_iterator: Any | None = None,
    ) -> TrainingMetrics:
        """
        Run the training loop.

        Parameters
        ----------
        train_iterator:
            An iterable yielding batches of tokenized data. Each batch
            should be a dict with keys ``input_ids`` and ``labels``
            (both mx.array).
        val_iterator:
            Optional validation iterator (same format).

        Returns
        -------
        TrainingMetrics with loss history and timing.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        cfg = self.training_config
        acc_steps = cfg.gradient_accumulation_steps

        # Setup optimizer
        self._optimizer = nn.optimizers.AdamW(
            learning_rate=cfg.learning_rate,
        )

        # Collect trainable parameters
        trainable_params = [
            p for p in self._model.parameters() if p.requires_grad
        ]

        # Optimizer state
        state = [self._optimizer.init(p) for p in trainable_params]

        metrics = TrainingMetrics()
        total_tokens = 0
        start_time = time.time()

        step = 0
        best_loss = float("inf")
        loss_history: list[float] = []
        accumulated_grads: list[mx.array | None] = [None] * len(trainable_params)

        for batch in train_iterator:
            if step >= cfg.max_steps:
                break

            input_ids = batch["input_ids"]
            labels = batch.get("labels", input_ids)

            # Forward pass
            logits = self._model(input_ids)
            loss = nn.losses.cross_entropy(logits, labels, reduction="mean")

            # Scale loss for gradient accumulation
            loss = loss / acc_steps

            # Backward pass
            grads = mx.grad(lambda: loss, trainable_params)()
            for i, g in enumerate(grads):
                if accumulated_grads[i] is None:
                    accumulated_grads[i] = g
                else:
                    accumulated_grads[i] = accumulated_grads[i] + g

            # Gradient clipping and optimizer step when accumulation is complete
            if (step + 1) % acc_steps == 0:
                # Clip gradients
                clipped = [
                    mx.clip(g, -cfg.max_grad_norm, cfg.max_grad_norm)
                    if g is not None else g
                    for g in accumulated_grads
                ]

                # Update weights
                for i, p in enumerate(trainable_params):
                    if clipped[i] is not None:
                        self._optimizer.update(p, clipped[i], state[i])

                # Zero accumulated grads
                accumulated_grads = [None] * len(trainable_params)

            loss_val = float(loss.item() * acc_steps)
            loss_history.append(loss_val)
            best_loss = min(best_loss, loss_val)
            total_tokens += input_ids.size

            # Logging
            if step % cfg.log_steps == 0:
                lr = self._get_current_lr(step)
                logger.info(
                    "Step %6d / %d | loss %.4f | best %.4f | lr %.2e",
                    step,
                    cfg.max_steps,
                    loss_val,
                    best_loss,
                    lr,
                )
                if self.progress_callback:
                    self.progress_callback(
                        epoch=0,
                        step=step,
                        total_steps=cfg.max_steps,
                        loss=loss_val,
                        learning_rate=lr,
                        best_loss=best_loss,
                    )

            # Validation
            if val_iterator is not None and step % cfg.eval_steps == 0:
                val_loss = self._evaluate(val_iterator)
                logger.info("Validation loss after step %d: %.4f", step, val_loss)

            # Save checkpoint
            if step > 0 and step % cfg.save_steps == 0:
                self.save_adapter(step=step)

            step += 1

        elapsed = time.time() - start_time
        metrics.final_loss = loss_history[-1] if loss_history else 0.0
        metrics.best_loss = best_loss
        metrics.total_steps = step
        metrics.total_time_s = elapsed
        metrics.avg_tokens_per_sec = total_tokens / max(elapsed, 1e-6)
        metrics.loss_history = loss_history

        # Final save
        self.save_adapter(step=step)

        logger.info(
            "Training complete: %d steps in %.2f s (%.1f tok/s)",
            step,
            elapsed,
            metrics.avg_tokens_per_sec,
        )
        return metrics

    def save_adapter(self, step: int | None = None) -> Path:
        """Save LoRA adapter weights to disk (~10 MB)."""
        self.adapter_path.mkdir(parents=True, exist_ok=True)

        # Collect LoRA weights only
        lora_weights: dict[str, mx.array] = {}
        for layer in self._lora_layers:
            for name, param in layer.parameters().items():
                if param.requires_grad:
                    key = f"{layer.__class__.__name__}.{name}"
                    lora_weights[key] = param

        # Save as safetensors-compatible dict (convert to numpy for JSON-safe)
        weights_dict = {
            k: v.tolist() if hasattr(v, "tolist") else v
            for k, v in lora_weights.items()
        }

        # MLX native save (preferred)
        save_path = self.adapter_path / "adapters.safetensors"
        try:
            import mlx.core as mx_core
            weights_flat = {k: mx.array(v) if not isinstance(v, mx.array) else v
                           for k, v in lora_weights.items()}
            mx_core.save_safetensors(str(save_path), weights_flat)
        except Exception:
            # Fallback: JSON
            save_path = self.adapter_path / "adapters.json"
            with save_path.open("w") as f:
                json.dump(weights_dict, f)

        # Save config
        config = {
            "base_model": self.model_name,
            "lora_config": {
                "rank": self.lora_config.rank,
                "alpha": self.lora_config.alpha,
                "dropout": self.lora_config.dropout,
                "target_modules": list(self.lora_config.target_modules),
                "bias": self.lora_config.bias,
            },
            "training_config": {
                "batch_size": self.training_config.batch_size,
                "micro_batch_size": self.training_config.micro_batch_size,
                "learning_rate": self.training_config.learning_rate,
                "max_steps": self.training_config.max_steps,
            },
            "step": step,
        }
        config_path = self.adapter_path / "adapter_config.json"
        with config_path.open("w") as f:
            json.dump(config, f, indent=2)

        size_mb = sum(
            v.nbytes if hasattr(v, "nbytes") else 0
            for v in lora_weights.values()
        ) / (1024 * 1024)
        logger.info(
            "Adapter saved to %s (~%.1f MB)",
            self.adapter_path,
            size_mb,
        )
        return self.adapter_path

    # -- Internal helpers --------------------------------------------------

    def _add_lora_layers(self) -> None:
        """Find target linear layers and wrap them with LoRA."""
        assert self._model is not None

        target_names = set(self.lora_config.target_modules)

        def _find_and_replace(module: nn.Module, path: str = "") -> None:
            for key, child in list(module.children().items()):
                child_path = f"{path}.{key}" if path else key
                if any(child_path.endswith(t) for t in target_names) and isinstance(child, nn.Linear):
                    lora_layer = LoRALinear(
                        child,
                        rank=self.lora_config.rank,
                        alpha=self.lora_config.alpha,
                        dropout=self.lora_config.dropout,
                    )
                    setattr(module, key, lora_layer)
                    self._lora_layers.append(lora_layer)
                else:
                    _find_and_replace(child, child_path)

        _find_and_replace(self._model)

    def _evaluate(self, val_iterator: Any) -> float:
        """Run a single validation pass and return average loss."""
        assert self._model is not None
        losses: list[float] = []
        for batch in val_iterator:
            input_ids = batch["input_ids"]
            labels = batch.get("labels", input_ids)
            logits = self._model(input_ids)
            loss = nn.losses.cross_entropy(logits, labels, reduction="mean")
            losses.append(float(loss.item()))
            if len(losses) >= 10:  # limit eval batches for speed
                break
        return float(np.mean(losses)) if losses else 0.0

    def _get_current_lr(self, step: int) -> float:
        """Linear warmup then constant LR."""
        cfg = self.training_config
        if step < cfg.warmup_steps:
            return cfg.learning_rate * (step + 1) / cfg.warmup_steps
        return cfg.learning_rate


# ---------------------------------------------------------------------------
# LoRA Linear layer
# ---------------------------------------------------------------------------


class LoRALinear(nn.Module):
    """
    A LoRA wrapper around a frozen ``nn.Linear`` layer.

    During training only the ``lora_a`` and ``lora_b`` matrices are updated.
    The forward pass computes::

        output = base(x) + alpha / rank * (x @ lora_a @ lora_b)
    """

    def __init__(
        self,
        base_layer: nn.Linear,
        rank: int = 16,
        alpha: float = 32.0,
        dropout: float = 0.05,
    ) -> None:
        super().__init__()
        self.base = base_layer
        self.rank = rank
        self.scaling = alpha / rank

        input_dim = base_layer.weight.shape[1]
        output_dim = base_layer.weight.shape[0]

        # LoRA matrices
        self.lora_a = nn.Linear(input_dim, rank, bias=False)
        self.lora_b = nn.Linear(rank, output_dim, bias=False)

        # Initialize LoRA A with normal(0, 0.02), LoRA B with zeros
        nn.init.normal(self.lora_a.weight, mean=0.0, std=0.02)
        nn.init.constant(self.lora_b.weight, 0.0)

        self.dropout = nn.Dropout(dropout)

        # Freeze base
        self.base.requires_grad = False

    def __call__(self, x: mx.array) -> mx.array:
        base_out = self.base(x)
        lora_out = self.lora_b(self.dropout(self.lora_a(x)))
        return base_out + self.scaling * lora_out
