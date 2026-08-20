"""AI tool data: cache categories plus a read-only model inspector.

Models are NEVER automatic cleanup targets. They are reported separately with
path, size, application, last modified, and a likely model/cache classification.
"""

import os
from dataclasses import dataclass
from datetime import datetime

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.files import walk_safe
from crapcleaner.utils.platform import (
    get_appdata,
    get_local_appdata,
    get_user_profile,
    is_windows,
)

MODEL_EXTENSIONS = (
    ".gguf",
    ".safetensors",
    ".bin",
    ".onnx",
    ".pth",
    ".pt",
    ".ckpt",
    ".ggml",
    ".tflite",
    ".h5",
    ".pb",
)

INSPECT_MIN_SIZE = 50 * 1024 * 1024


@dataclass
class AiDataItem:
    path: str
    size: int
    application: str
    last_modified: datetime | None
    classification: str


def _ai_roots() -> list[tuple[str, str]]:
    """Known local model stores, one entry per application that actually exists.

    ComfyUI and text-generation-webui are cloned anywhere, so only conventional
    locations are probed; a filesystem-wide hunt was rejected as too invasive.
    """
    user = get_user_profile()
    local = get_local_appdata()
    roots = {
        "Ollama": os.path.join(user, ".ollama"),
        "LM Studio": os.path.join(user, ".lmstudio"),
        "Hugging Face": os.path.join(local, "huggingface"),
        "Torch Hub": os.path.join(local, "torch"),
        "Jan.ai": os.path.join(user, "jan"),
        "ComfyUI": os.path.join(user, "ComfyUI"),
        "text-generation-webui": os.path.join(user, "text-generation-webui"),
    }
    if is_windows():
        roots["Ollama (local)"] = os.path.join(local, "Ollama")
        roots["LM Studio (local)"] = os.path.join(local, "LM Studio")
        roots["Jan.ai (roaming)"] = os.path.join(get_appdata(), "Jan", "data")
    else:
        roots["Jan.ai (config)"] = os.path.join(user, ".config", "Jan", "data")
        roots["ComfyUI (documents)"] = os.path.join(user, "Documents", "ComfyUI")
    return [(app, path) for app, path in roots.items() if os.path.isdir(path)]


def _classify(path: str, _app: str, size: int) -> str:
    lowered = path.lower()
    if any(lowered.endswith(ext) for ext in MODEL_EXTENSIONS):
        return "model"
    name_parts = os.path.normpath(lowered).split(os.sep)
    if any(part in ("models", "blobs", "snapshots", "hub", "weights") for part in name_parts):
        return "model"
    if "cache" in name_parts or "temp" in name_parts:
        return "cache"
    if size >= 1024 * 1024 * 1024:
        return "model"
    return "cache"


def get_ai_data(min_size: int = INSPECT_MIN_SIZE) -> list[AiDataItem]:
    items: list[AiDataItem] = []
    for app, root in _ai_roots():
        for dirpath, dirnames, filenames in walk_safe(root):
            for name in filenames:
                full = os.path.join(dirpath, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                if st.st_size < min_size:
                    continue
                try:
                    mtime = datetime.fromtimestamp(st.st_mtime)
                except (OSError, ValueError, OverflowError):
                    mtime = None
                items.append(
                    AiDataItem(
                        path=full,
                        size=st.st_size,
                        application=app,
                        last_modified=mtime,
                        classification=_classify(full, app, st.st_size),
                    )
                )
    items.sort(key=lambda item: item.size, reverse=True)
    return items


def find_ai_model_dirs() -> list[str]:
    found: list[str] = []
    for _app, root in _ai_roots():
        for sub in ("models", "hub", "blobs", "checkpoints", os.path.join("models", "checkpoints")):
            p = os.path.join(root, sub)
            if os.path.isdir(p):
                found.append(p)
        if "ollama" in root.lower() and os.path.isdir(root):
            found.append(root)
    return sorted(set(found))


def get_categories() -> list[CleanupCategory]:
    user = get_user_profile()
    local = get_local_appdata()

    categories: list[CleanupCategory] = []

    lm_cache = os.path.join(user, ".lmstudio", "cache")
    hf_refs = os.path.join(local, "huggingface", "hub", ".cache")

    cache_targets: list[CacheTarget] = []
    if os.path.isdir(lm_cache):
        cache_targets.append(CacheTarget(path=lm_cache))
    if os.path.isdir(hf_refs):
        cache_targets.append(CacheTarget(path=hf_refs))

    if cache_targets:
        categories.append(
            CleanupCategory(
                id="ai_app_cache",
                name="AI application caches",
                group="AI",
                description="Small cache folders from AI tools (LM Studio cache, Hugging Face metadata). Model weights are NEVER included.",
                safety_level=SafetyLevel.REVIEW,
                what_it_contains="LM Studio's cache folder and the Hugging Face hub metadata cache - catalogue listings, model cards, and download bookkeeping.",
                why_it_grows="Browsing or searching for models stores a record of each one, and downloads leave their bookkeeping behind.",
                why_safe_to_delete="The model weight directories are deliberately outside this category, so nothing you have downloaded is removed; only metadata about models is. The tools re-fetch that metadata from the network when you next browse, so an offline machine will show an empty catalogue until it can reach the hub again.",
                regeneration_behavior="Rebuilt the next time you open the model browser or download something.",
                targets=cache_targets,
            )
        )

    categories.append(
        CleanupCategory(
            id="ai_models",
            name="AI models (read-only report)",
            group="AI",
            description="Model weight data for Ollama, LM Studio, Hugging Face, Jan.ai, ComfyUI, and text-generation-webui. NEVER deleted automatically. Use the AI Data tab to inspect individual files.",
            safety_level=SafetyLevel.DANGEROUS,
            what_it_contains="Model weight files - .gguf, .safetensors, checkpoints and blobs - stored by Ollama, LM Studio, Hugging Face, Jan.ai, ComfyUI, and text-generation-webui.",
            why_it_grows="Each model is a separate download of several gigabytes, and every tool keeps every model and quantisation you have ever pulled.",
            why_safe_to_delete="Nothing here is deleted by a cleanup: this category is never selected for you and is listed so you can see where the space went. Deleting a model is not free - it comes back only as a multi-gigabyte download, sometimes behind an account login or an access agreement, so review individual files in the AI Data tab and remove them yourself.",
            regeneration_behavior="Nothing changes unless you delete a model yourself; a tool that needs a model you removed downloads it again on next use.",
            auto_selected=False,
            finder=find_ai_model_dirs,
            finder_args=(),
        )
    )

    return categories
