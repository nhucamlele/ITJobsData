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
MAX_JOBS = 50
PAGE_LOAD_DELAY = 3
SHOWMORE_WAIT = 3
DETAIL_PAGE_INITIAL_WAIT = 2
DETAIL_PAGE_EXTRA_WAIT = 2
RETRY_DETAIL = 2
SAVE_PATH = "data/itjobs_data.json"
SAVE_EVERY = 100

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
def get_job_urls(driver, url, max_jobs=MAX_JOBS):
    driver.get(url)
    time.sleep(PAGE_LOAD_DELAY)

    total_urls = set()
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
            if href:
                total_urls.add(href if href.startswith("http") else BASE_URL + href)

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

    return list(total_urls)

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
# 💾 Lưu dữ liệu (thêm vào đầu file cũ)
# =========================================
def save_to_json(new_jobs):
    os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
    old_jobs = []
    if os.path.exists(SAVE_PATH):
        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                old_jobs = json.load(f)
        except:
            pass
    # thêm job mới vào đầu
    all_jobs = new_jobs + old_jobs
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=2)
    print(f"💾 Đã lưu {len(new_jobs)} job mới (tổng {len(all_jobs)} job) → {SAVE_PATH}")

# =========================================
# 🔁 Tự động commit & push lên GitHub
# =========================================
def git_push():
    try:
        subprocess.run("git add data/*.json", shell=True)
        subprocess.run('git commit -m "Auto update ITJobs data"', shell=True)
        subprocess.run("git push origin main", shell=True)
        print("🚀 Đã đẩy dữ liệu mới lên GitHub.")
    except Exception as e:
        print(f"⚠️ Lỗi khi push Git: {e}")

# =========================================
# 🧠 MAIN
# =========================================
def main():
    driver = init_uc_driver(headless=False)
    try:
        print("🔹 Đang lấy danh sách job...")
        job_urls = get_job_urls(driver, START_URL, max_jobs=MAX_JOBS)
        print(f"📊 Tổng cộng: {len(job_urls)} job URL")

        new_jobs = []
        for idx, job_url in enumerate(job_urls):
            print(f"➡️ [{idx+1}/{len(job_urls)}] {job_url}")
            job_data = scrape_job_details(driver, job_url)
            new_jobs.append(job_data)
            if (idx + 1) % SAVE_EVERY == 0:
                save_to_json(new_jobs)
                new_jobs = []

        if new_jobs:
            save_to_json(new_jobs)
            git_push()

        print("✅ Hoàn tất cào dữ liệu ITJobs!")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
