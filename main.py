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
    
    # Use the new headless mode which is more robust
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Randomize window size slightly to avoid standard bot fingerprints
    chrome_options.add_argument("--window-size=1366,768")
    
    # --- STEALTH FLAGS ---
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Use a highly standard, recent User Agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )
    return driver

def renew_pass():
    if not LIBRARY_CARD or not LIBRARY_PIN or not NYT_EMAIL:
        logging.error("Missing credentials! Check GitHub Secrets.")
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

        # --- PHASE 2: NYT AUTH HANDLING ---
        logging.info("Waiting for NYT page load (5s)...")
        time.sleep(5) 
        
        # Check if we are on the landing page that asks for login
        body_text = driver.find_element(By.TAG_NAME, "body").text

        if "Already have an account? Log in" in body_text or "Log in" in body_text:
            logging.info("NYT Login required. Finding login link...")

            # STRATEGY CHANGE: Get the URL and navigate directly
            # This is safer than .click() which might hang on a redirect
            login_url = None
            try:
                # Find the link element
                login_link_elem = driver.find_element(By.XPATH, "//a[contains(text(), 'Log in')] | //button[contains(text(), 'Log in')]")
                login_url = login_link_elem.get_attribute("href")
            except:
                logging.warning("Could not find Log In link element, checking if we are already redirected.")

            if login_url:
                logging.info(f"Navigating directly to Auth URL: {login_url[:50]}...")
                driver.get(login_url)
            else:
                logging.info("No href found or already on page. Continuing.")

            # --- EMAIL FIELD (WITH RETRY) ---
            logging.info("Looking for NYT Email field...")
            
            email_field_found = False
            for attempt in range(2): # Try twice
                try:
                    # Look for email by ID or Name
                    email_input = wait.until(lambda d: d.find_element(By.ID, "email") or d.find_element(By.NAME, "email"))
                    email_input.clear()
                    email_input.send_keys(NYT_EMAIL)
                    logging.info("Entered Email.")
                    email_field_found = True
                    break # Success, exit loop
                except:
                    if attempt == 0:
                        logging.warning("Email field not found. Refreshing page to bypass blank screen...")
                        driver.refresh()
                        time.sleep(5) # Wait for reload
                    else:
                        logging.error("Refresh failed. Email field still missing.")

            if not email_field_found:
                # --- DEBUGGING CRITICAL FAILURE ---
                logging.error("!!! FAILED TO FIND EMAIL FIELD !!!")
                logging.error(f"Current URL: {driver.current_url}")
                logging.error("Dumping HTML Source (first 2000 chars) to analyze block:")
                print("="*30)
                # print page_source to see hidden HTML or error messages
                print(driver.page_source[:2000]) 
                print("="*30)
                raise Exception("Email field missing - Automation detected or page failed to load.")

            # Click Continue (if exists)
            try:
                continue_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
                continue_btn.click()
                time.sleep(2)
            except:
                pass 

            # Enter Password
            pass_input = wait.until(EC.element_to_be_clickable((By.ID, "password")))
            pass_input.clear()
            pass_input.send_keys(NYT_PASSWORD)

            # Submit
            submit_btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Log In')]")
            submit_btn.click()
            time.sleep(5)

        # --- PHASE 3: REDEMPTION ---
        logging.info("Checking for 'Redeem' button...")
        try:
            # Re-fetch body text after login
            body_text = driver.find_element(By.TAG_NAME, "body").text
            
            if "Redeem" in body_text:
                driver.find_element(By.XPATH, "//button[contains(text(), 'Redeem')]").click()
                logging.info("SUCCESS: Clicked 'Redeem'.")
            elif "You have a pass" in body_text or "Basic Digital Access" in body_text:
                logging.info("SUCCESS: Pass is already active.")
            else:
                logging.info("Status unclear. Page text snippet:")
                print(body_text[:300])
        except Exception as e:
            logging.warning(f"Error checking redemption status: {e}")

    except Exception as e:
        logging.error(f"Script Failed: {e}")
        raise e

    finally:
        driver.quit()
        logging.info("Browser closed.")

if __name__ == "__main__":
    renew_pass()