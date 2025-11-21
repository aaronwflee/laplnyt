import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
LIBRARY_CARD = os.getenv("LIBRARY_CARD")
LIBRARY_PIN = os.getenv("LIBRARY_PIN")
NYT_COOKIE = os.getenv("NYT_COOKIE") # The new secret

TARGET_URL = "https://login.lapl.idm.oclc.org/login?url=https://ezmyaccount.nytimes.com/group-pass"

logging.basicConfig(level=logging.INFO)

def renew_pass():
    if not NYT_COOKIE:
        logging.error("Missing NYT_COOKIE! Please add it to GitHub Secrets.")
        return

    logging.info("Setting up Browser...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )
    wait = WebDriverWait(driver, 20)

    try:
        # --- PHASE 1: INJECT COOKIE ---
        # We must visit the domain before we can set a cookie for it.
        logging.info("Visiting NYT homepage to inject session cookie...")
        try:
            driver.get("https://www.nytimes.com")
        except:
            pass # Ignore timeouts, we just need the domain set
            
        # Inject the 'nyt-s' cookie which creates the logged-in session
        driver.add_cookie({
            'name': 'nyt-s',
            'value': NYT_COOKIE,
            'domain': '.nytimes.com',
            'path': '/'
        })
        logging.info("Session cookie injected.")

        # --- PHASE 2: LIBRARY LOGIN ---
        logging.info(f"Navigating to Library Login: {TARGET_URL}")
        driver.get(TARGET_URL)

        logging.info("Entering Library credentials...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@name, 'user') or contains(@name, 'code')]"))).send_keys(LIBRARY_CARD)
        driver.find_element(By.XPATH, "//input[contains(@name, 'pass') or contains(@name, 'pin')]").send_keys(LIBRARY_PIN)
        
        driver.find_element(By.XPATH, "//input[@type='submit'] | //button[contains(text(), 'Log In')]").click()
        logging.info("Submitted Library credentials.")

        # --- PHASE 3: REDEMPTION (SKIP LOGIN) ---
        logging.info("Waiting for redirect...")
        time.sleep(8) 
        
        # Since we injected the cookie, we should land directly on the "Redeem" page
        # or the "You already have a pass" page, bypassing the login form entirely.
        
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        if "Redeem" in body_text:
            try:
                driver.find_element(By.XPATH, "//button[contains(text(), 'Redeem')]").click()
                logging.info("SUCCESS: Clicked 'Redeem'.")
            except:
                logging.warning("Found Redeem text but couldn't click.")
        elif "You have a pass" in body_text or "Basic Digital Access" in body_text:
            logging.info("SUCCESS: Pass is already active.")
        elif "Log in" in body_text:
            logging.error("FAIL: The script was asked to login again.")
            logging.error("This means the NYT_COOKIE might be invalid or expired.")
        else:
            logging.info("Status unclear. Page snippet:")
            print(body_text[:300])

    except Exception as e:
        logging.error(f"Failed: {e}")
        # Debug dump
        try:
            print(driver.page_source[:1000])
        except:
            pass
        raise e

    finally:
        driver.quit()
        logging.info("Browser closed.")

if __name__ == "__main__":
    renew_pass()