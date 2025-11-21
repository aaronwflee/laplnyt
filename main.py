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

TARGET_URL = "https://login.lapl.idm.oclc.org/login?url=https://ezmyaccount.nytimes.com/group-pass"

logging.basicConfig(level=logging.INFO)

def get_stealth_driver():
    """Configures Chrome to look like a real human browser."""
    chrome_options = Options()
    
    # "headless=new" is much harder to detect than the old "--headless"
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # --- STEALTH FLAGS (The Secret Sauce) ---
    # 1. Turn off the "AutomationControlled" feature which screams "I am a robot"
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 2. Exclude the "enable-automation" switch that Selenium usually adds
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    # 3. Turn off the automation extension
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # 4. Use a standard user agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )
    return driver

def renew_pass():
    if not LIBRARY_CARD or not LIBRARY_PIN or not NYT_EMAIL:
        logging.error("Missing credentials! Ensure LIBRARY_CARD, LIBRARY_PIN, and NYT_EMAIL are set in GitHub Secrets.")
        return

    logging.info("Setting up Stealth Browser...")
    driver = get_stealth_driver()
    wait = WebDriverWait(driver, 20)

    try:
        # --- PHASE 1: LIBRARY LOGIN ---
        logging.info(f"Navigating to Library Login: {TARGET_URL}")
        driver.get(TARGET_URL)

        # Wait for library inputs
        logging.info("Entering Library credentials...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@name, 'user') or contains(@name, 'code')]"))).send_keys(LIBRARY_CARD)
        driver.find_element(By.XPATH, "//input[contains(@name, 'pass') or contains(@name, 'pin')]").send_keys(LIBRARY_PIN)
        
        driver.find_element(By.XPATH, "//input[@type='submit'] | //button[contains(text(), 'Log In')]").click()
        logging.info("Submitted Library credentials.")

        # --- PHASE 2: NYT INTERACTION ---
        logging.info("Waiting for NYT page load (5s)...")
        time.sleep(5) 
        
        body_text = driver.find_element(By.TAG_NAME, "body").text

        # Check for 'Log in' text
        if "Already have an account? Log in" in body_text or "Log in" in body_text:
            logging.info("NYT Login required. Starting NYT auth sequence...")

            # 1. Click initial 'Log in' if needed
            if "enter-email" not in driver.page_source:
                try:
                    login_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Log in')] | //button[contains(text(), 'Log in')]")
                    login_link.click()
                    time.sleep(3)
                except:
                    logging.info("Already on login form or couldn't find link.")

            # 2. Find Email Field (With Debugging)
            logging.info("Looking for NYT Email field...")
            try:
                # We try to find the email field. If this times out, it's likely a bot block.
                email_input = wait.until(EC.presence_of_element_located((By.ID, "email")))
                email_input.clear()
                email_input.send_keys(NYT_EMAIL)
                logging.info("Entered Email.")
            except Exception as e:
                # --- DEBUGGING BLOCK ---
                logging.error("!!! COULD NOT FIND EMAIL FIELD !!!")
                logging.error("Dumping page text to see if we were blocked:")
                print("="*30)
                print(driver.find_element(By.TAG_NAME, "body").text[:1000]) # Print first 1000 chars
                print("="*30)
                raise e # Re-raise error to stop script

            # Click Continue (if exists)
            try:
                continue_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
                continue_btn.click()
                time.sleep(2)
            except:
                pass 

            # 3. Enter Password
            pass_input = wait.until(EC.element_to_be_clickable((By.ID, "password")))
            pass_input.clear()
            pass_input.send_keys(NYT_PASSWORD)

            # 4. Submit
            submit_btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Log In')]")
            submit_btn.click()
            time.sleep(5)

        # --- PHASE 3: REDEMPTION ---
        logging.info("Checking for 'Redeem' button...")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        if "Redeem" in body_text:
            try:
                driver.find_element(By.XPATH, "//button[contains(text(), 'Redeem')]").click()
                logging.info("SUCCESS: Clicked 'Redeem'.")
            except:
                logging.info("Redeem button found but couldn't click.")
        elif "You have a pass" in body_text or "Basic Digital Access" in body_text:
            logging.info("SUCCESS: Pass is already active.")
        else:
            logging.info("Status unclear. Page text snippet:")
            print(body_text[:300])

    except Exception as e:
        logging.error(f"Script Failed: {e}")
        raise e

    finally:
        driver.quit()
        logging.info("Browser closed.")

if __name__ == "__main__":
    renew_pass()