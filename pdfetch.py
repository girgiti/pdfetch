import requests
from bs4 import BeautifulSoup
import os
import shutil
from urllib.parse import urljoin
import pdfplumber
import pytesseract
from PIL import Image

# ------------------------
# Custom Exception
# ------------------------
class NoMorePages(Exception):
    pass

# ------------------------
# Settings
# ------------------------
BASE_URL_TEMPLATE = "https://uttardinajpur.gov.in/past-notices/recruitment/page/{page}?date_from=2019-01-01&date_to=2025-09-03"
PDF_DIR = "uttar_dinajpur_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

KEYWORDS = ["Sangita Das", "Sangita Dey (Das)"]

# ------------------------
# Helpers
# ------------------------
def cleanup():
    print("🧹 Cleaning up downloaded files...")
    shutil.rmtree(PDF_DIR, ignore_errors=True)
    if os.path.exists("matches.txt"):
        os.remove("matches.txt")
    print("✅ Cleanup complete.")

def get_pdf_links(page_url, base_url):
    resp = requests.get(page_url)
    if resp.status_code != 200:
        raise NoMorePages()

    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            links.append(urljoin(base_url, href))

    if not links:
        raise NoMorePages()

    return links

def extract_text_from_pdf(filename):
    text = ""
    with pdfplumber.open(filename) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted
            else:
                # OCR fallback if page has no text
                img = page.to_image(resolution=300).original
                text += pytesseract.image_to_string(img)
    return text

# ------------------------
# Main
# ------------------------
def main():
    seen = set()
    matches = []
    page = 1

    try:
        while True:
            page_url = BASE_URL_TEMPLATE.format(page=page)
            print(f"🌐 Crawling page {page} -> {page_url}")
            pdf_links = get_pdf_links(page_url, page_url)

            for link in pdf_links:
                if link in seen:
                    continue
                seen.add(link)

                filename = os.path.join(PDF_DIR, os.path.basename(link))
                print(f"⬇️  Downloading {link} -> {filename}")

                try:
                    resp = requests.get(link, stream=True, timeout=60)
                    resp.raise_for_status()
                    with open(filename, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)

                    text = extract_text_from_pdf(filename)

                    for kw in KEYWORDS:
                        if kw.lower() in text.lower():
                            print(f"✅ Found '{kw}' in {link}")
                            matches.append((kw, link))

                except Exception as e:
                    print(f"❌ Failed to process {link}: {e}")

            page += 1

    except NoMorePages:
        print("📄 No more pages to crawl.")

    # Final report
    if matches:
        print("\n=== MATCHES FOUND ===")
        for kw, link in matches:
            print(f"Keyword: '{kw}' -> {link}")

        with open("matches.txt", "w") as report:
            for kw, link in matches:
                report.write(f"{kw} -> {link}\n")
        print("\n📄 Matches saved in matches.txt")
    else:
        print("\nNo matches found.")
        cleanup()

if __name__ == "__main__":
    main()

