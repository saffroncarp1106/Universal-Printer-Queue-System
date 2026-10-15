"""
processor.py
Centauri Carbon Batch Print — GCode Processing
"""

import os
import re
import base64
from datetime import datetime


def find_m84_line(lines: list) -> int:
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "M84" or stripped == "M84 ;disable steppers":
            return i
    return None


def extract_filament_grams(content: str) -> float:
    match = re.search(r";\s*filament used \[g\]\s*=\s*([\d.]+)", content)
    return float(match.group(1)) if match else None


def extract_thumbnail_png(content: str) -> bytes:
    """Extract embedded base64 PNG thumbnail from gcode. Returns raw PNG bytes or None."""
    match = re.search(
        r'; thumbnail begin \d+x\d+ \d+\n(.*?); thumbnail end',
        content, re.DOTALL
    )
    if not match:
        return None
    raw = match.group(1)
    b64 = ''.join(line.lstrip('; ').strip() for line in raw.splitlines())
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def get_file_info(input_path: str) -> dict:
    if not os.path.isfile(input_path):
        return {"valid": False}
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {
        "valid":            True,
        "grams_per_print":  extract_filament_grams(content),
        "thumbnail_png":    extract_thumbnail_png(content),
        "filename":         os.path.basename(input_path),
        "size_kb":          os.path.getsize(input_path) / 1024,
    }


def generate_queue(jobs: list, output_path: str) -> dict:
    if not jobs:
        return {"success": False, "message": "Queue is empty."}

    total_grams = 0.0
    total_copies = sum(j["copies"] for j in jobs)
    blocks = []

    for job in jobs:
        path = job["path"]
        copies = job["copies"]
        if not os.path.isfile(path):
            return {"success": False, "message": f"File not found:\n{path}"}
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        grams = extract_filament_grams(raw)
        if grams:
            total_grams += grams * copies
        blocks.append((raw, copies, os.path.basename(path), grams))

    with open(output_path, "w", encoding="utf-8") as out:
        out.write("; ============================================================\n")
        out.write("; CENTAURI CARBON BATCH PRINT QUEUE\n")
        out.write(f"; Jobs:    {len(jobs)}\n")
        out.write(f"; Prints:  {total_copies} total\n")
        if total_grams:
            out.write(f"; Filament: {total_grams:.2f}g total\n")
        out.write(f"; Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write("; ============================================================\n\n")

        last_block_idx = len(blocks) - 1
        for bi, (raw, copies, fname, grams) in enumerate(blocks):
            lines = raw.splitlines(keepends=True)
            m84_idx = find_m84_line(lines)
            if m84_idx is not None:
                body_no_m84 = "".join(lines[:m84_idx] + lines[m84_idx + 1:])
            else:
                body_no_m84 = raw

            is_last_block = (bi == last_block_idx)
            for ci in range(1, copies + 1):
                is_absolute_last = is_last_block and (ci == copies)
                out.write(f"; ===== JOB {bi+1}/{len(blocks)}: {fname} "
                          f"(print {ci}/{copies}) =====\n")
                out.write(raw if is_absolute_last else body_no_m84)
                out.write("\n")

    size_kb = os.path.getsize(output_path) / 1024
    return {
        "success":       True,
        "output_path":   output_path,
        "output_size_kb": size_kb,
        "total_grams":   total_grams if total_grams else None,
        "total_copies":  total_copies,
        "job_count":     len(jobs),
    }


def suggest_queue_output_path(first_path: str) -> str:
    folder = os.path.dirname(first_path)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(folder, f"centauri_queue_{ts}.gcode")
