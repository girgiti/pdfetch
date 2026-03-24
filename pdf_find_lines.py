#!/usr/bin/env python3
# Improved pdf_find_lines.py (deduped output)
# Usage:
#   python3 pdf_find_lines.py <pdf_path> "<kw1>" "<kw2>" ...

import sys
import os
import re
import subprocess
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
import pdfplumber
import pytesseract

OCR_LANG = "ben+eng"
TESSERACT_PSM = ["3", "6", "11"]
TESSERACT_OEM = "3"

def check_tesseract_lang():
    try:
        r = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, check=True)
        langs = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        return langs
    except Exception:
        return []

def normalize_line(line):
    """Normalize line for deduplication."""
    return re.sub(r"\s+", " ", line.strip())

def preprocess_variants(pil_img):
    imgs = []
    img = pil_img.convert("L")
    base_w = max(1200, img.width)
    ratio = base_w / img.width
    img = img.resize((base_w, int(img.height * ratio)), Image.LANCZOS)
    imgs.append(img)

    enh = ImageEnhance.Contrast(img).enhance(1.8)
    enh = ImageEnhance.Sharpness(enh).enhance(1.2)
    imgs.append(enh)

    mf = ImageOps.autocontrast(img).filter(ImageFilter.MedianFilter(3))
    imgs.append(mf)

    for thresh in (150, 140, 120):
        bin_img = img.point(lambda p: 255 if p > thresh else 0)
        imgs.append(bin_img)

    inv = ImageOps.invert(img)
    imgs.append(inv)
    imgs.append(ImageOps.autocontrast(inv))
    return imgs

def ocr_try(img):
    lines_out = []
    seen = set()
    for psm in TESSERACT_PSM:
        cfg = f"--oem {TESSERACT_OEM} --psm {psm}"
        try:
            txt = pytesseract.image_to_string(img, lang=OCR_LANG, config=cfg)
        except Exception:
            txt = ""
        if not txt:
            continue
        for ln in txt.splitlines():
            s = normalize_line(ln)
            if s and s not in seen:
                seen.add(s)
                lines_out.append(s)
    return lines_out

def full_page_ocr(pil_img):
    parts = []
    variants = preprocess_variants(pil_img)
    seen = set()
    for var in variants:
        lines = ocr_try(var)
        for ln in lines:
            norm = normalize_line(ln)
            if norm not in seen:
                seen.add(norm)
                parts.append(norm)
    if not parts:
        try:
            raw = pytesseract.image_to_string(pil_img, lang=OCR_LANG)
            for ln in raw.splitlines():
                s = normalize_line(ln)
                if s and s not in seen:
                    parts.append(s)
        except Exception:
            pass
    return parts

def search_pdf(pdf_path, keywords):
    if not os.path.exists(pdf_path):
        print("❌ File not found:", pdf_path)
        sys.exit(1)

    langs = check_tesseract_lang()
    print("Tesseract languages available:", langs if langs else "(couldn't check)")
    if not any("ben" in l for l in langs):
        print("⚠️ Warning: 'ben' not found in Tesseract languages. Bengali OCR may fail.")

    print(f"\n🔎 Scanning PDF: {pdf_path}")
    found = []
    seen_matches = set()

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for idx, page in enumerate(pdf.pages, start=1):
            print(f"  Scanning page {idx}/{total} ...", end="\r")
            pil_img = page.to_image(resolution=300).original
            lines = full_page_ocr(pil_img)

            for line in lines:
                low_line = line.lower()
                for kw in keywords:
                    if kw.lower() in low_line:
                        norm_line = normalize_line(line)
                        dedup_key = (idx, kw.lower(), norm_line)
                        if dedup_key not in seen_matches:
                            seen_matches.add(dedup_key)
                            found.append((idx, kw, norm_line))
    print()

    if found:
        print("\n=== MATCHES (deduped) ===")
        grouped = {}
        for page_num, kw, line in found:
            grouped.setdefault(page_num, []).append((kw, line))
        for page_num in sorted(grouped.keys()):
            print(f"\n📄 Page {page_num}")
            for kw, line in grouped[page_num]:
                print(f"  [{kw}] → {line}")
    else:
        print("\n❌ No matches found.")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 pdf_find_lines.py <pdf_path> <keyword1> [keyword2 ...]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    keywords = sys.argv[2:]
    search_pdf(pdf_path, keywords)

if __name__ == "__main__":
    main()

