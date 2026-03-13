from __future__ import annotations

import argparse
from collections import deque
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def parse_color(value: str) -> tuple[int, int, int] | None:
    normalized = value.strip().lower()
    if normalized in {"transparent", "none"}:
        return None
    if normalized == "black":
        return (0, 0, 0)
    if normalized == "white":
        return (255, 255, 255)

    if normalized.startswith("#") and len(normalized) == 7:
        return (
            int(normalized[1:3], 16),
            int(normalized[3:5], 16),
            int(normalized[5:7], 16),
        )
    raise ValueError("Background must be: black, white, transparent, or #RRGGBB.")


def flatten_background(rgba: Image.Image, background_color: tuple[int, int, int] | None) -> Image.Image:
    if background_color is None:
        return rgba

    flattened = Image.new("RGB", rgba.size, background_color)
    flattened.paste(rgba, mask=rgba.split()[3])
    return flattened


def remove_white_background_edge_connected(
    rgba: Image.Image,
    white_threshold: int,
    neutral_tolerance: int,
) -> Image.Image:
    arr = np.array(rgba.convert("RGBA"))
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    max_c = rgb.max(axis=2)
    min_c = rgb.min(axis=2)
    is_near_white = (
        (rgb[:, :, 0] >= white_threshold)
        & (rgb[:, :, 1] >= white_threshold)
        & (rgb[:, :, 2] >= white_threshold)
        & ((max_c - min_c) <= neutral_tolerance)
        & (alpha > 0)
    )

    h, w = is_near_white.shape
    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    def add_if_candidate(y: int, x: int) -> None:
        if not visited[y, x] and is_near_white[y, x]:
            visited[y, x] = True
            q.append((y, x))

    for x in range(w):
        add_if_candidate(0, x)
        add_if_candidate(h - 1, x)
    for y in range(h):
        add_if_candidate(y, 0)
        add_if_candidate(y, w - 1)

    while q:
        y, x = q.popleft()
        if y > 0:
            add_if_candidate(y - 1, x)
        if y + 1 < h:
            add_if_candidate(y + 1, x)
        if x > 0:
            add_if_candidate(y, x - 1)
        if x + 1 < w:
            add_if_candidate(y, x + 1)

    arr[:, :, 3][visited] = 0
    return Image.fromarray(arr)


def process_image_white_only(
    input_path: Path,
    output_path: Path,
    background_color: tuple[int, int, int] | None,
    white_threshold: int,
    neutral_tolerance: int,
) -> None:
    rgba = Image.open(input_path).convert("RGBA")
    cleaned = remove_white_background_edge_connected(
        rgba=rgba,
        white_threshold=white_threshold,
        neutral_tolerance=neutral_tolerance,
    )
    out = flatten_background(cleaned, background_color)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path, format="PNG")


def process_image_ai(
    input_path: Path,
    output_path: Path,
    model_name: str,
    alpha_matting: bool,
    alpha_foreground: int,
    alpha_background: int,
    alpha_erode: int,
    background_color: tuple[int, int, int] | None,
) -> None:
    from backgroundremover.bg import remove

    with input_path.open("rb") as f:
        input_bytes = f.read()

    output_bytes = remove(
        input_bytes,
        model_name=model_name,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=alpha_foreground,
        alpha_matting_background_threshold=alpha_background,
        alpha_matting_erode_structure_size=alpha_erode,
    )
    rgba = Image.open(BytesIO(output_bytes)).convert("RGBA")
    out = flatten_background(rgba, background_color)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-remove logo backgrounds. Default mode removes edge-connected white only.",
    )
    parser.add_argument(
        "--input-folder",
        default="acceptance-logos",
        help="Folder containing source logos.",
    )
    parser.add_argument(
        "--output-folder",
        default="acceptance-logos",
        help="Folder to write processed logos.",
    )
    parser.add_argument(
        "--mode",
        default="white-only",
        choices=["white-only", "ai"],
        help="white-only is safer for logos; ai uses backgroundremover segmentation.",
    )
    parser.add_argument(
        "--model",
        default="u2net",
        choices=["u2net", "u2netp", "u2net_human_seg"],
        help="AI model used for segmentation.",
    )
    parser.add_argument(
        "--background",
        default="black",
        help="black, white, transparent, or #RRGGBB",
    )
    parser.add_argument(
        "--alpha-matting",
        action="store_true",
        help="Enable alpha matting for cleaner edges.",
    )
    parser.add_argument("--af", type=int, default=240, help="Alpha foreground threshold.")
    parser.add_argument("--ab", type=int, default=10, help="Alpha background threshold.")
    parser.add_argument("--ae", type=int, default=8, help="Alpha erosion size (1-25).")
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=235,
        help="Pixels >= this RGB value are considered white candidates (0-255).",
    )
    parser.add_argument(
        "--neutral-tolerance",
        type=int,
        default=26,
        help="Max RGB channel spread for white candidates (prevents colored logos from being removed).",
    )
    args = parser.parse_args()

    source = Path(args.input_folder)
    target = Path(args.output_folder)
    bg_color = parse_color(args.background)

    if not source.exists():
      raise FileNotFoundError(f"Input folder does not exist: {source}")

    image_files = sorted(
        p for p in source.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )
    if not image_files:
        print("No supported images found.")
        return

    for image_path in image_files:
        out_path = target / f"{image_path.stem}.png"
        print(f"Processing {image_path.name} -> {out_path.name} [{args.mode}]")
        if args.mode == "white-only":
            process_image_white_only(
                input_path=image_path,
                output_path=out_path,
                background_color=bg_color,
                white_threshold=args.white_threshold,
                neutral_tolerance=args.neutral_tolerance,
            )
        else:
            process_image_ai(
                input_path=image_path,
                output_path=out_path,
                model_name=args.model,
                alpha_matting=args.alpha_matting,
                alpha_foreground=args.af,
                alpha_background=args.ab,
                alpha_erode=args.ae,
                background_color=bg_color,
            )

    print(f"Done. Processed {len(image_files)} file(s).")


if __name__ == "__main__":
    main()
