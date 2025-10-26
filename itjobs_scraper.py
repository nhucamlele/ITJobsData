import time
import json
import os
import subprocess
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================================
# 🌐 URL cấu hình
# =========================================
BASE_URL = "https://www.itjobs.com.vn"
START_URL = "https://www.itjobs.com.vn/en"

# =========================================
# ⚙️ Tham số cào
# =========================================
MAX_JOBS = 100
PAGE_LOAD_DELAY = 3
SHOWMORE_WAIT = 3
DETAIL_PAGE_INITIAL_WAIT = 2
DETAIL_PAGE_EXTRA_WAIT = 2
RETRY_DETAIL = 2

# ⚠️ Lưu file JSON TRONG repo (để git push được)
SAVE_PATH = os.path.join(os.path.dirname(__file__), "itjobs_data.json")

# =========================================
# 🚀 Khởi tạo driver
# =========================================
def init_uc_driver(headless=False):
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)
    driver.set_window_size(1280, 900)
    return driver

# =========================================
# 🔎 Helper: an toàn lấy text
# =========================================
def safe_get_text(driver, by, selector, timeout=5):
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return el.text.strip()
    except:
        return ""

# =========================================
# 📜 Cào danh sách URL job
# =========================================
def get_job_urls(driver, url, old_urls, max_jobs=MAX_JOBS):
    driver.get(url)
    time.sleep(PAGE_LOAD_DELAY)

    total_urls = []
    last_count = 0
    same_count_retries = 0

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        try:
            show_more_btn = WebDriverWait(driver, SHOWMORE_WAIT).until(
                EC.element_to_be_clickable((By.ID, "btnShowMoreJob"))
            )
            driver.execute_script("arguments[0].click();", show_more_btn)
            time.sleep(3)
        except:
            print("⚠️ Hết nút 'SHOW MORE' hoặc lỗi click → dừng.")
            break

        jobs = driver.find_elements(By.CSS_SELECTOR, "a.jp_job_post_link")
        for j in jobs:
            href = j.get_attribute("href")
            if href and href not in total_urls:
                full_url = href if href.startswith("http") else BASE_URL + href
                # ⚡ Dừng sớm nếu gặp job cũ đầu tiên
                if full_url in old_urls:
                    print("⛔ Gặp job cũ, dừng quét danh sách.")
                    return total_urls
                total_urls.append(full_url)

        print(f"🔹 Đã lấy {len(total_urls)} job...")

        if len(total_urls) == last_count:
            same_count_retries += 1
            if same_count_retries >= 3:
                print("ℹ️ Không thấy tăng thêm job mới → dừng.")
                break
        else:
            same_count_retries = 0

        if len(total_urls) >= max_jobs:
            print("✅ Đã đạt giới hạn max_jobs.")
            break
        last_count = len(total_urls)

    return total_urls

# =========================================
# 🧾 Cào chi tiết job
# =========================================
def scrape_job_details(driver, job_url):
    driver.get(job_url)
    time.sleep(DETAIL_PAGE_INITIAL_WAIT)

    data = {"Url": job_url}
    try:
        container = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.jp_job_post_detail_cont"))
        )

        data["Job name"] = safe_get_text(container, By.TAG_NAME, "h3")
        data["Company Name"] = safe_get_text(container, By.TAG_NAME, "p")
        data["Address"] = safe_get_text(driver, By.CSS_SELECTOR, "span.color-black.font-size-20")
        data["Company type"] = "At office"
        data["Time"] = safe_get_text(driver, By.CSS_SELECTOR, "div.color-orange.text-nowrap.padding-top-10")

        skills = driver.find_elements(By.CSS_SELECTOR, "div.jp_skills_slider_wrapper ul.tech-skills-detail-page li")
        data["Skills"] = ", ".join([s.text.strip() for s in skills]) if skills else ""

        data["Salary"] = safe_get_text(driver, By.CSS_SELECTOR, "i.fa.fa-usd.j-usd.icon-style + span")

        data["Company size"], data["Company industry"] = "", ""
        try:
            items = driver.find_elements(By.CSS_SELECTOR, "ul li.company-info")
            for li in items:
                icon = li.find_element(By.TAG_NAME, "i").get_attribute("class")
                span_text = li.find_element(By.TAG_NAME, "span").text.strip()
                if "fa-building" in icon:
                    data["Company size"] = span_text
                elif "fa-list-alt" in icon:
                    data["Company industry"] = span_text
        except:
            pass

        data["Working days"] = "Monday - Friday"

    except Exception as e:
        print(f"⚠️ Lỗi khi cào {job_url}: {e}")

    return data

# =========================================
# 💾 Lưu / Gộp file JSON
# =========================================
def save_or_update_json(new_data, file_path=SAVE_PATH):
    """Gộp dữ liệu mới vào file JSON hiện có."""
    if os.path.exists(file_path):
        try:
            with open(file_path, encoding="utf-8") as f:
                old_data = json.load(f)
                if not isinstance(old_data, list):
                    old_data = []
        except Exception as e:
            print("⚠️ Không đọc được file cũ, sẽ tạo mới:", e)
            old_data = []
    else:
        old_data = []

    old_urls = {item.get("Url") for item in old_data if isinstance(item, dict) and item.get("Url")}
    fresh_data = [job for job in new_data if job.get("Url") not in old_urls]

    if not fresh_data:
        print("✅ Không có job mới để thêm.")
        return old_data

    print(f"🆕 Phát hiện {len(fresh_data)} job mới → thêm lên đầu file cũ...")
    updated = fresh_data + old_data

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    print(f"💾 Đã cập nhật {file_path}: tổng {len(updated)} job.")
    return updated

# =========================================
# 🧠 MAIN
# =========================================
def main():
    driver = init_uc_driver(headless=False)
    try:
        # Tải danh sách job cũ
        old_urls = set()
        if os.path.exists(SAVE_PATH):
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                try:
                    old_data = json.load(f)
                    old_urls = {item.get("Url") for item in old_data if item.get("Url")}
                    print(f"📂 Đã tải {len(old_urls)} job cũ.")
                except:
                    print("⚠️ File cũ lỗi định dạng, bỏ qua.")
        else:
            print("🆕 Không có file cũ, sẽ cào toàn bộ.")

        print("🔹 Đang lấy danh sách job mới...")
        job_urls = get_job_urls(driver, START_URL, old_urls, max_jobs=MAX_JOBS)
        print(f"📊 Tổng cộng {len(job_urls)} job URL mới.")

        new_jobs = []
        for idx, job_url in enumerate(job_urls):
            print(f"➡️ [{idx+1}/{len(job_urls)}] {job_url}")
            job_data = scrape_job_details(driver, job_url)
            new_jobs.append(job_data)

        if new_jobs:
            save_or_update_json(new_jobs)

        print("✅ Hoàn tất cào dữ liệu ITJobs!")

    finally:
        driver.quit()

    # =========================================
    # 🚀 GỬI LÊN GITHUB
    # =========================================
    repo_path = os.path.dirname(os.path.abspath(__file__))
    print("\n🚀 Đang cập nhật GitHub...")
    subprocess.run(["git", "add", "."], cwd=repo_path)
    subprocess.run(["git", "commit", "-m", "auto update ITJobs data and scraper"], cwd=repo_path)
    subprocess.run(["git", "push", "origin", "main"], cwd=repo_path)
    print("✅ Hoàn tất cập nhật GitHub.")

if __name__ == "__main__":
    main()
