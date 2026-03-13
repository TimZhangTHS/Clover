from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image
from backgroundremover.bg import remove


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


def process_image(
    input_path: Path,
    output_path: Path,
    model_name: str,
    alpha_matting: bool,
    alpha_foreground: int,
    alpha_background: int,
    alpha_erode: int,
    background_color: tuple[int, int, int] | None,
) -> None:
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

    if background_color is None:
      output_path.parent.mkdir(parents=True, exist_ok=True)
      rgba.save(output_path, format="PNG")
      return

    flattened = Image.new("RGB", rgba.size, background_color)
    flattened.paste(rgba, mask=rgba.split()[3])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    flattened.save(output_path, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-remove logo backgrounds with AI (backgroundremover).",
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
      print(f"Processing {image_path.name} -> {out_path.name}")
      process_image(
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
