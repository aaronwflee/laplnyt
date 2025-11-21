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
NYT_EMAIL = os.getenv("NYT_EMAIL")
NYT_PASSWORD = os.getenv("NYT_PASSWORD")

# The URL that starts the library auth process
TARGET_URL = "https://login.lapl.idm.oclc.org/login?url=https://ezmyaccount.nytimes.com/group-pass"

logging.basicConfig(level=logging.INFO)

def handle_cookie_banner(driver):
    """Attempts to close annoying cookie/privacy banners that block clicks."""
    try:
        logging.info("Checking for cookie banners...")
        # Common text for accept buttons
        cookie_xpaths = [
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Agree')]",
            "//button[contains(text(), 'Continue') and contains(@class, 'cookie')]",
            "//button[@data-testid='GDPR-accept']"
        ]
        for xpath in cookie_xpaths:
            try:
                btn = driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    btn.click()
                    logging.info("Clicked a cookie banner button.")
                    time.sleep(1)
                    break
            except:
                continue
    except:
        pass

def renew_pass():
    if not LIBRARY_CARD or not LIBRARY_PIN or not NYT_EMAIL:
        logging.error("Missing credentials! Ensure LIBRARY_CARD, LIBRARY_PIN, and NYT_EMAIL are set in GitHub Secrets.")
        return

    logging.info("Setting up Browser...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Using a standard Windows 10 User Agent to look less like a bot
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080") # Set a big window so elements aren't hidden
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )
    wait = WebDriverWait(driver, 20)

    try:
        # --- PHASE 1: LIBRARY LOGIN ---
        logging.info(f"Navigating to Library Login: {TARGET_URL}")
        driver.get(TARGET_URL)

        logging.info("Entering Library credentials...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@name, 'user') or contains(@name, 'code')]"))).send_keys(LIBRARY_CARD)
        driver.find_element(By.XPATH, "//input[contains(@name, 'pass') or contains(@name, 'pin')]").send_keys(LIBRARY_PIN)
        
        driver.find_element(By.XPATH, "//input[@type='submit'] | //button[contains(text(), 'Log In')]").click()
        logging.info("Submitted Library credentials.")

        # --- PHASE 2: NYT INTERACTION ---
        logging.info("Waiting for NYT page load...")
        time.sleep(5) 
        
        handle_cookie_banner(driver)
        
        body_text = driver.find_element(By.TAG_NAME, "body").text

        # Check if we need to log in to NYT
        if "Already have an account? Log in" in body_text or "Log in" in body_text:
            logging.info("NYT Login required. Starting NYT auth sequence...")
            
            # 1. Click the 'Log in' link/button if we aren't already on the login form
            if "enter-email" not in driver.page_source:
                try:
                    login_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Log in')] | //button[contains(text(), 'Log in')]")
                    login_link.click()
                    time.sleep(3)
                except:
                    logging.info("Could not click initial 'Log in', assuming we are already there or redirected.")

            # 2. Enter Email (with bot detection check)
            logging.info("Looking for NYT Email field...")
            try:
                # Try ID first, then Name
                email_input = wait.until(lambda d: d.find_element(By.ID, "email") or d.find_element(By.NAME, "email"))
                logging.info("Found Email field.")
                email_input.clear()
                email_input.send_keys(NYT_EMAIL)
            except Exception as e:
                # If we timeout here, it's likely a captcha or layout change
                logging.error("Could not find Email field. Checking page content...")
                page_dump = driver.find_element(By.TAG_NAME, "body").text
                if "captcha" in page_dump.lower() or "robot" in page_dump.lower():
                    logging.error("!!! CAPTCHA DETECTED !!! GitHub IP blocked.")
                else:
                    logging.error(f"Page text dump: {page_dump[:500]}")
                raise e
            
            # Click Continue (if exists)
            try:
                continue_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
                continue_btn.click()
                time.sleep(2)
            except:
                pass 

            # 3. Enter Password
            logging.info("Entering NYT Password...")
            pass_input = wait.until(EC.element_to_be_clickable((By.ID, "password")))
            pass_input.clear()
            pass_input.send_keys(NYT_PASSWORD)

            # 4. Click Final Login
            logging.info("Clicking final Login button...")
            submit_btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Log In')]")
            submit_btn.click()
            time.sleep(5)

        # --- PHASE 3: REDEMPTION ---
        logging.info("Checking for 'Redeem' button...")
        handle_cookie_banner(driver)
        
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        if "Redeem" in body_text:
            try:
                redeem_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Redeem')]")
                redeem_btn.click()
                logging.info("SUCCESS: Clicked 'Redeem'. Pass should be active.")
            except Exception as e:
                logging.warning(f"Redeem text found but button click failed: {e}")
        elif "You have a pass" in body_text or "Basic Digital Access" in body_text:
            logging.info("SUCCESS: Page indicates you already have an active pass.")
        else:
            logging.info("Unsure of status. Printing page text for review:")
            print(body_text[:500])

    except Exception as e:
        logging.error(f"Failed: {e}")
        logging.info(f"Crashed on URL: {driver.current_url}")
        raise e

    finally:
        driver.quit()
        logging.info("Browser closed.")

if __name__ == "__main__":
    renew_pass()