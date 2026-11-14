"""Optional pretrained semantic segmentation on georeferenced RGB imagery.

Torch and Transformers are imported only when inference is explicitly requested.
No model is selected or downloaded by the core engine.
"""

import json
import re
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window


def segment_rgb(
    source,
    output,
    *,
    model,
    tree_class,
    revision=None,
    threshold=0.5,
    tile_size=512,
    overlap=64,
    device="cpu",
):
    """Write binary predictions (0/1; 255 unknown) on the unchanged input grid.

    Uses halo tiles: each core pixel is written once, with neighboring context
    included during inference. Compatible with Transformers semantic-segmentation
    checkpoints exposing logits; callers choose a model and its tree class.
    Requires georeferenced uint8 RGB in bands 1–3. Does not acquire imagery.
    """
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise FileExistsError("Choose a new output path distinct from the source")
    if not 0 <= threshold <= 1 or tile_size <= 0 or overlap < 0 or overlap * 2 >= tile_size:
        raise ValueError("Invalid threshold, tile_size or overlap")
    if tree_class < 0 or device not in {"cpu", "cuda", "mps"}:
        raise ValueError("Invalid tree class or device")
    local = Path(model).is_dir()
    if not local and (not revision or not re.fullmatch(r"[0-9a-fA-F]{40}", revision)):
        raise ValueError("Remote models require a pinned 40-character commit SHA via --revision")
    with rasterio.open(source) as src:
        if src.crs is None or src.count < 3 or any(t != "uint8" for t in src.dtypes[:3]):
            raise ValueError("Provide georeferenced uint8 RGB imagery, bands 1–3")
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
    except ImportError as exc:
        raise ImportError(
            "Install inference dependencies: pip install 'pathe-resistance[geoai]'"
        ) from exc
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable; use --device cpu")
    if device == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS is unavailable; use --device cpu")
    options = {"trust_remote_code": False}
    if not local:
        options["revision"] = revision
    processor = AutoImageProcessor.from_pretrained(model, **options)
    network = (
        AutoModelForSemanticSegmentation.from_pretrained(
            model,
            use_safetensors=True,
            **options,
        )
        .to(device)
        .eval()
    )
    if tree_class >= network.config.num_labels:
        raise ValueError("tree_class is outside this model's class labels")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + ".partial.tif")
    if temporary.exists():
        raise FileExistsError(f"An incomplete output already exists: {temporary}")
    core_size = tile_size - 2 * overlap
    tiles = 0
    try:
        with rasterio.open(source) as src:
            profile = dict(
                driver="GTiff",
                width=src.width,
                height=src.height,
                count=1,
                dtype="uint8",
                crs=src.crs,
                transform=src.transform,
                nodata=255,
                compress="deflate",
                tiled=True,
                BIGTIFF="IF_SAFER",
            )
            with rasterio.open(temporary, "w", **profile) as dst:
                for y in range(0, src.height, core_size):
                    for x in range(0, src.width, core_size):
                        height, width = (
                            min(core_size, src.height - y),
                            min(core_size, src.width - x),
                        )
                        top, left = max(0, y - overlap), max(0, x - overlap)
                        bottom = min(src.height, y + height + overlap)
                        right = min(src.width, x + width + overlap)
                        window = Window(left, top, right - left, bottom - top)
                        valid = (src.read_masks([1, 2, 3], window=window) > 0).all(axis=0)
                        result = np.full(valid.shape, 255, dtype="uint8")
                        if valid.any():
                            rgb = np.moveaxis(src.read([1, 2, 3], window=window), 0, -1)
                            inputs = processor(images=rgb, return_tensors="pt", do_resize=False).to(
                                device
                            )
                            with torch.inference_mode():
                                logits = network(**inputs).logits
                                logits = torch.nn.functional.interpolate(
                                    logits,
                                    size=rgb.shape[:2],
                                    mode="bilinear",
                                    align_corners=False,
                                )
                                probability = logits.softmax(dim=1)[0, tree_class].cpu().numpy()
                            if not np.isfinite(probability).all():
                                raise ValueError("Model produced nonfinite probabilities")
                            result[valid] = (probability[valid] >= threshold).astype("uint8")
                        core = result[y - top : y - top + height, x - left : x - left + width]
                        dst.write(core, 1, window=Window(x, y, width, height))
                        tiles += 1
                dst.update_tags(
                    model=str(model),
                    revision=revision or "local checkpoint",
                    classes="0 not detected; 1 predicted tree; 255 unknown",
                    interpretation="Tree prediction; not measured shade or canopy ground truth",
                )
            resolution, crs = list(src.res), str(src.crs)
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    metadata = {
        "source": str(source),
        "output": str(output),
        "model": str(model),
        "revision": revision,
        "resolved_commit": getattr(network.config, "_commit_hash", None),
        "class_labels": network.config.id2label,
        "tree_class": tree_class,
        "threshold": threshold,
        "tile_size": tile_size,
        "halo_pixels": overlap,
        "tiles": tiles,
        "device": device,
        "resolution": resolution,
        "crs": crs,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "torch": version("torch"),
        "transformers": version("transformers"),
        "limits": "No local accuracy assessment. Check imagery resolution, vintage and model/data licenses.",
    }
    output.with_suffix(".provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata
