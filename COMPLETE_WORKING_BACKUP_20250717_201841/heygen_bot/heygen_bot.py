import time
import traceback
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

def log(msg, level="INFO"):
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "heygen_bot_error.log"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {msg}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry, end="")

def download_video_and_docs(email, password, download_dir=None):
    try:
        log("Starting HeyGen bot...")
        download_dir = download_dir or str(Path(__file__).parent / "downloads")
        os.makedirs(download_dir, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            # Go to HeyGen login page
            page.goto("https://app.heygen.com/login")
            log("Navigated to login page.")

            # Fill login form
            page.fill('input[type="email"]', email)
            page.fill('input[type="password"]', password)
            page.click('button[type="submit"]')
            log("Submitted login form.")
            page.wait_for_timeout(4000)

            # Go to video library
            page.goto("https://app.heygen.com/library")
            log("Navigated to video library.")
            page.wait_for_timeout(3000)

            # Find video from 19th May or latest
            video_found = False
            videos = page.query_selector_all('div[class*="video-card"]')
            for vid in videos:
                date_elem = vid.query_selector('div[class*="date"]')
                if date_elem:
                    date_text = date_elem.inner_text().strip()
                    if "19" in date_text and "5" in date_text:
                        vid.click()
                        video_found = True
                        log(f"Found video with date: {date_text}")
                        break
            if not video_found and videos:
                videos[0].click()
                log("Defaulted to latest video.")
            page.wait_for_timeout(2000)

            # Download video (simulate clicking download button)
            download_btn = page.query_selector('button:has-text("Download")')
            if download_btn:
                with page.expect_download() as download_info:
                    download_btn.click()
                download = download_info.value
                download.save_as(os.path.join(download_dir, download.suggested_filename))
                log(f"Downloaded video to {download_dir}")
            else:
                log("Download button not found for video.", "ERROR")

            # Download documentation (search for links/files)
            docs_downloaded = 0
            doc_links = page.query_selector_all('a[href$=".pdf"], a[href$=".docx"], a[href$=".txt"]')
            for link in doc_links:
                with page.expect_download() as download_info:
                    link.click()
                download = download_info.value
                download.save_as(os.path.join(download_dir, download.suggested_filename))
                docs_downloaded += 1
                log(f"Downloaded documentation: {download.suggested_filename}")
            log(f"Downloaded {docs_downloaded} documentation files.")

            browser.close()
            log("Bot completed successfully.")
    except Exception as e:
        tb = traceback.format_exc()
        log(f"Exception occurred: {e}\n{tb}", "ERROR")

if __name__ == "__main__":
    import getpass
    print("HeyGen Bot - Automated Video & Documentation Downloader")
    email = input("Enter your HeyGen email: ")
    password = getpass.getpass("Enter your HeyGen password: ")
    download_video_and_docs(email, password)
