import os
import time
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
LIBRARY_CARD = os.getenv("LIBRARY_CARD")
LIBRARY_PIN = os.getenv("LIBRARY_PIN")
NYT_EMAIL = os.getenv("NYT_EMAIL")
NYT_PASSWORD = os.getenv("NYT_PASSWORD")

TARGET_URL = "https://login.lapl.idm.oclc.org/login?url=https://ezmyaccount.nytimes.com/group-pass"

logging.basicConfig(level=logging.INFO)

def get_undetected_driver():
    """
    Configures a patched Chrome driver that removes 'navigator.webdriver' flags
    and other obvious bot signatures.
    """
    logging.info("Initializing Undetected Chrome...")
    
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # We use a standard User Agent to blend in
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

    # headless=True in the constructor is the correct way to use UC in headless envs
    # version_main allows it to find the installed Chrome version on GitHub Actions automatically
    driver = uc.Chrome(
        options=options, 
        headless=True, 
        use_subprocess=False
    )
    
    return driver

def renew_pass():
    if not LIBRARY_CARD or not LIBRARY_PIN or not NYT_EMAIL:
        logging.error("Missing credentials! Check GitHub Secrets.")
        return

    driver = None
    try:
        driver = get_undetected_driver()
        wait = WebDriverWait(driver, 20)

        # --- PHASE 1: LIBRARY LOGIN ---
        logging.info(f"Navigating to Library Login: {TARGET_URL}")
        driver.get(TARGET_URL)

        logging.info("Entering Library credentials...")
        # Note: UC sometimes takes a moment to interact, so we wait explicitly
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@name, 'user') or contains(@name, 'code')]"))).send_keys(LIBRARY_CARD)
        driver.find_element(By.XPATH, "//input[contains(@name, 'pass') or contains(@name, 'pin')]").send_keys(LIBRARY_PIN)
        
        driver.find_element(By.XPATH, "//input[@type='submit'] | //button[contains(text(), 'Log In')]").click()
        logging.info("Submitted Library credentials.")

        # --- PHASE 2: NYT AUTH HANDLING ---
        logging.info("Waiting for NYT page load (5-8s)...")
        time.sleep(8) # Generous wait for redirects and anti-bot checks to pass
        
        # Check if we hit the Captcha wall immediately
        page_source = driver.page_source
        if "captcha-delivery" in page_source:
            logging.warning("Hit DataDome Captcha immediately. Attempting a refresh...")
            driver.refresh()
            time.sleep(5)

        body_text = driver.find_element(By.TAG_NAME, "body").text

        if "Already have an account? Log in" in body_text or "Log in" in body_text:
            logging.info("NYT Login required. Finding login link...")

            # 1. Navigate to Login Page
            login_url = None
            try:
                login_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Log in')] | //button[contains(text(), 'Log in')]")
                login_url = login_link.get_attribute("href")
            except:
                logging.info("Login link not found, assuming we might be on the form.")

            if login_url:
                driver.get(login_url)
                time.sleep(3)

            # 2. Handle Email
            logging.info("Entering Email...")
            email_field_found = False
            for _ in range(2):
                try:
                    email_input = wait.until(lambda d: d.find_element(By.ID, "email") or d.find_element(By.NAME, "email"))
                    email_input.clear()
                    email_input.send_keys(NYT_EMAIL)
                    email_field_found = True
                    break
                except:
                    logging.warning("Email field missing. Refreshing...")
                    driver.refresh()
                    time.sleep(5)
            
            if not email_field_found:
                logging.error("!!! BLOCK DETECTED !!!")
                logging.error("DataDome is likely blocking this IP.")
                print("HTML DUMP FOR DEBUG:")
                print(driver.page_source[:1000])
                raise Exception("Blocked by DataDome.")

            try:
                driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]").click()
                time.sleep(2)
            except:
                pass

            # 3. Handle Password
            logging.info("Entering Password...")
            pass_input = wait.until(EC.element_to_be_clickable((By.ID, "password")))
            pass_input.clear()
            pass_input.send_keys(NYT_PASSWORD)
            
            driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Log In')]").click()
            time.sleep(5)

        # --- PHASE 3: REDEMPTION ---
        logging.info("Checking for 'Redeem' button...")
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "Redeem" in body_text:
                driver.find_element(By.XPATH, "//button[contains(text(), 'Redeem')]").click()
                logging.info("SUCCESS: Clicked 'Redeem'.")
            elif "You have a pass" in body_text or "Basic Digital Access" in body_text:
                logging.info("SUCCESS: Pass is already active.")
            else:
                logging.info("Status unclear. Page snippet:")
                print(body_text[:300])
        except Exception as e:
            logging.warning(f"Error checking status: {e}")

    except Exception as e:
        logging.error(f"Failed: {e}")
        raise e

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        logging.info("Browser closed.")

if __name__ == "__main__":
    renew_pass()