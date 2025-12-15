"""
🎨 Colorful Logger for Bio-NER Pipeline
========================================
Rich, step-by-step logging with beautiful formatting
"""
from loguru import logger
import sys

# ─────────────────────────────────────────────────────────────
# Remove default handler and add custom colorful format
# ─────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    format=(
        "<bold><cyan>┃</cyan></bold> "
        "<green>{time:HH:mm:ss}</green> "
        "<level>{level: <8}</level> "
        "<white>{message}</white>"
    ),
    level="DEBUG",
    colorize=True,
)

# ─────────────────────────────────────────────────────────────
# Step Counter for Pipeline Progress
# ─────────────────────────────────────────────────────────────
_step_counter = 0


def reset_steps():
    """Reset the step counter."""
    global _step_counter
    _step_counter = 0


def step(message: str, icon: str = "🔵"):
    """Log a numbered step with icon."""
    global _step_counter
    _step_counter += 1
    logger.info(f"{icon} [{_step_counter}] {message}")


# ─────────────────────────────────────────────────────────────
# Phase Headers - Major Pipeline Sections
# ─────────────────────────────────────────────────────────────
def phase(title: str, subtitle: str = ""):
    """Display a major phase header."""
    width = 50
    logger.info("")
    logger.opt(colors=True).info(f"<bold><magenta>╔{'═' * width}╗</magenta></bold>")
    logger.opt(colors=True).info(f"<bold><magenta>║</magenta></bold>  <bold><white>🚀 {title.upper()}</white></bold>")
    if subtitle:
        logger.opt(colors=True).info(f"<bold><magenta>║</magenta></bold>     <dim>{subtitle}</dim>")
    logger.opt(colors=True).info(f"<bold><magenta>╚{'═' * width}╝</magenta></bold>")
    logger.info("")


def section(title: str):
    """Display a section divider."""
    logger.opt(colors=True).info(f"<cyan>──────────────────────────────────────────────────</cyan>")
    logger.opt(colors=True).info(f"<bold><cyan>  📌 {title}</cyan></bold>")
    logger.opt(colors=True).info(f"<cyan>──────────────────────────────────────────────────</cyan>")


# ─────────────────────────────────────────────────────────────
# Info Box - Summary Display
# ─────────────────────────────────────────────────────────────
def box(title: str, items: list[str]):
    """Display info in a styled box."""
    width = max(len(item) for item in items) + 6
    width = max(width, len(title) + 6)
    
    logger.opt(colors=True).info(f"<yellow>┌{'─' * width}┐</yellow>")
    logger.opt(colors=True).info(f"<yellow>│</yellow> <bold><white>📦 {title}</white></bold>{' ' * (width - len(title) - 4)}<yellow>│</yellow>")
    logger.opt(colors=True).info(f"<yellow>├{'─' * width}┤</yellow>")
    for item in items:
        logger.opt(colors=True).info(f"<yellow>│</yellow>   {item}{' ' * (width - len(item) - 3)}<yellow>│</yellow>")
    logger.opt(colors=True).info(f"<yellow>└{'─' * width}┘</yellow>")


# ─────────────────────────────────────────────────────────────
# Status Messages
# ─────────────────────────────────────────────────────────────
def success(message: str):
    """Log a success message."""
    logger.opt(colors=True).info(f"<bold><green>✅ {message}</green></bold>")


def warning(message: str):
    """Log a warning message."""
    logger.opt(colors=True).warning(f"<bold><yellow>⚠️  {message}</yellow></bold>")


def error(message: str):
    """Log an error message."""
    logger.opt(colors=True).error(f"<bold><red>❌ {message}</red></bold>")


def loading(message: str):
    """Log a loading/progress message."""
    logger.opt(colors=True).info(f"<bold><blue>⏳ {message}...</blue></bold>")


def done(message: str):
    """Log a completion message."""
    logger.opt(colors=True).info(f"<bold><green>🎉 {message}</green></bold>")


# ─────────────────────────────────────────────────────────────
# Data Display
# ─────────────────────────────────────────────────────────────
def stats(title: str, data: dict):
    """Display statistics in a formatted way."""
    logger.opt(colors=True).info(f"<bold><cyan>📊 {title}</cyan></bold>")
    for key, value in data.items():
        logger.opt(colors=True).info(f"   <dim>•</dim> {key}: <bold>{value}</bold>")


def result(entity: str, label: str, score: float):
    """Display a NER result."""
    color = "green" if score > 0.9 else "yellow" if score > 0.7 else "red"
    logger.opt(colors=True).info(
        f"   <bold><white>{entity}</white></bold> → "
        f"<bold><{color}>{label}</{color}></bold> "
        f"<dim>(score: {score:.3f})</dim>"
    )


# ─────────────────────────────────────────────────────────────
# Pipeline Banner
# ─────────────────────────────────────────────────────────────
def banner():
    """Display the pipeline startup banner."""
    logger.opt(colors=True).info("")
    logger.opt(colors=True).info("<bold><magenta>  ╭──────────────────────────────────────────────╮</magenta></bold>")
    logger.opt(colors=True).info("<bold><magenta>  │</magenta></bold>                                              <bold><magenta>│</magenta></bold>")
    logger.opt(colors=True).info("<bold><magenta>  │</magenta></bold>   <bold><cyan>🧬 BIO-ENTITY NER FINE-TUNING PIPELINE</cyan></bold>     <bold><magenta>│</magenta></bold>")
    logger.opt(colors=True).info("<bold><magenta>  │</magenta></bold>      <dim>Cancer NER with PubMedBERT</dim>              <bold><magenta>│</magenta></bold>")
    logger.opt(colors=True).info("<bold><magenta>  │</magenta></bold>                                              <bold><magenta>│</magenta></bold>")
    logger.opt(colors=True).info("<bold><magenta>  ╰──────────────────────────────────────────────╯</magenta></bold>")
    logger.opt(colors=True).info("")


# Re-export logger for direct use
__all__ = [
    "logger",
    "reset_steps",
    "step",
    "phase",
    "section", 
    "box",
    "success",
    "warning",
    "error",
    "loading",
    "done",
    "stats",
    "result",
    "banner",
]
