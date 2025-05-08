from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os
import time
import re
import logging
import sys
from pathlib import Path
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime  # 🔹 Import for timestamp
from google.oauth2 import service_account
import pytz
import traceback
from selenium.webdriver.common.keys import Keys  

# === Setup Logging ===
# This sets up logging to the console (GitHub Actions will capture this)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger()

# === Setup: Linux-compatible download directory ===
download_dir = os.path.join(os.getcwd(), "download")
os.makedirs(download_dir, exist_ok=True)

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")  # 🔹 Run Chrome in headless mode
chrome_options.add_argument("--disable-gpu")  # Optional: disable GPU usage
chrome_options.add_argument("--window-size=1920,1080")  # Optional: set window size for full rendering
chrome_options.add_argument("--no-sandbox")  # Optional: for Linux environments
chrome_options.add_argument("--disable-dev-shm-usage")  # Optional: prevents crashes on some systems
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
})

pattern = "Pending Slider Count"

def is_file_downloaded():
    return any(Path(download_dir).glob(f"*{pattern}*.xlsx"))

while True:
    try:
        # === Start driver ===
        log.info("Attempting to start the browser...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        wait = WebDriverWait(driver, 20)

        # === Step 1: Log into Odoo ===
        log.info("Navigating to login page...")
        driver.get("https://taps.odoo.com")
        wait.until(EC.presence_of_element_located((By.NAME, "login"))).send_keys("supply.chain3@texzipperbd.com")
        driver.find_element(By.NAME, "password").send_keys("@Shanto@86")
        time.sleep(2)
        driver.find_element(By.XPATH, "//button[contains(text(), 'Log in')]").click()
        time.sleep(2)

        # === Step 2: Click user/company switch ===
        time.sleep(2)
        try:
            wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".modal-backdrop")))
        except:
            pass

        switcher_span = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
            "div.o_menu_systray div.o_switch_company_menu > button > span"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", switcher_span)
        switcher_span.click()
        time.sleep(2)

        # === Step 3: Click 'Zipper' company ===
        log.info("Click 'Zipper' company ===")
        target_div = wait.until(EC.element_to_be_clickable((By.XPATH,
            "//div[contains(@class, 'log_into')][span[contains(text(), 'Zipper')]]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", target_div)
        target_div.click()
        time.sleep(2)

        # step 4
        # === Trigger global search box by sending a keystroke ===
        log.info("=== Trigger global search box by sending a keystroke ===")
        
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys("PPC")  # or use Keys.A if needed
        time.sleep(2)  # Wait for search box to appear
        
        # Step 5
        # Click on MRP option
        log.info("=== Click on MRP option ===")
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div/main/div/div[2]/div/div[1]/a/div/span"))).click() 
        time.sleep(4)

        # Step 6
        # click on list of report
        
        log.info("=== click on list of report ===")
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div/main/div/div/div/div/div/div[1]/div/div[2]/div/select"))).click() 
        time.sleep(4)
        
        # Step 7
        # click on Invoice summary of report
        log.info("=== click on Productiion slider count report ===")
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div/main/div/div/div/div/div/div[1]/div/div[2]/div/select/option[6]"))).click() 
        time.sleep(5)
        
        # Step 8
        # download the report
        log.info("=== download the report ===")
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div/footer/footer/button[1]/span"))).click() 
        time.sleep(20)
       
        # === Step 9: Confirm file downloaded ===
        
        if is_file_downloaded():
            log.info("✅ File download complete!")
            files = list(Path(download_dir).glob(f"*{pattern}*.xlsx"))
            if len(files) > 1:
                files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                for file in files[1:]:
                    file.unlink()
            driver.quit()
            break  # Exit the loop after file download is complete
        else:
            log.warning("⚠️ File not downloaded. Retrying...")
            

    except Exception as e:
        driver.save_screenshot("error_screenshot.png")
        log.error(f"❌ Error Roccurred: {traceback.format_exc()}\nRetrying in 10 seconds...\n")
        try:
            driver.quit()
        except:
            pass
        time.sleep(10)
        

# === Step 11: Load latest file and paste to Google Sheet ===
try:
    log.info("Checking for downloaded files...")
    files = list(Path(download_dir).glob(f"*{pattern}*.xlsx"))
    if not files:
        raise Exception("No matching file found.")

    # Sort and get the latest file
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest_file = files[0]
    print(f"Latest file found: {latest_file.name}")

    # Load into DataFrame
    df_pending_slider = pd.read_excel(latest_file,sheet_name=0)
    print("File loaded into DataFrame.")
    
    # Setup Google Sheets API
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = service_account.Credentials.from_service_account_file('gcreds.json', scopes=scope)
    log.info("✅ Successfully loaded credentials.")

    # Use gspread to authorize and access Google Sheets
    client = gspread.authorize(creds)

    # Open the sheet and paste the data
    sheet = client.open_by_key("1acV7UrmC8ogC54byMrKRTaD9i1b1Cf9QZ-H1qHU5ZZc")
    worksheet = sheet.worksheet("Pending order details")

    # Clear old content (optional)
    worksheet.batch_clear(['A2:AC'])

    # Paste new data
    set_with_dataframe(worksheet, df_pending_slider,row=2, col=1)
    print("Data pasted to Google Sheet (Pending order details).")
    
    # === ✅ Add timestamp to Y2 ===
    local_tz = pytz.timezone('Asia/Dhaka')
    local_time = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
    worksheet.update("AQ2", [[f"{local_time}"]])
    print(f"Timestamp written to AQ2: {local_time}")
    
    # USD paste
    sheet1 = client.open_by_key("1fLRxl5IMZ4AM95fa7JKPn78GcDV3P-eFNZd23xUhyXo")
    worksheet1 = sheet1.worksheet("Pending order details")

    # Clear old content (optional)
    worksheet1.batch_clear(['A2:AC'])

    # Paste new data
    set_with_dataframe(worksheet1, df_pending_slider,row=2, col=1)
    print("Data pasted to Google Sheet (Pending order details).")

    # === ✅ Add timestamp to Y2 ===
    local_time1 = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
    worksheet1.update("C1", [[f"{local_time1}"]])
    print(f"Timestamp written to C1: {local_time1}")

except Exception as e:
    print(f"Error while pasting to Google Sheets: {e}")
