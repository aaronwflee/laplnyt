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
# We grab these from the cloud environment for security
LIBRARY_CARD = os.getenv("LIBRARY_CARD")
LIBRARY_PIN = os.getenv("LIBRARY_PIN")
TARGET_URL = "https://login.lapl.idm.oclc.org/login?url=https://ezmyaccount.nytimes.com/group-pass"

logging.basicConfig(level=logging.INFO)

def renew_pass():
    if not LIBRARY_CARD or not LIBRARY_PIN:
        logging.error("Credentials not found! Make sure Secrets are set in GitHub.")
        return

    logging.info("Setting up Headless Chrome in the Cloud...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # GitHub Actions runners come with Chrome installed
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )

    try:
        logging.info(f"Navigating to {TARGET_URL}")
        driver.get(TARGET_URL)

        wait = WebDriverWait(driver, 20)
        
        # LAPL/OCLC Login Page Logic
        logging.info("Looking for login inputs...")
        # Finding the user/barcode input
        card_input = wait.until(EC.presence_of_element_located((
            By.XPATH, "//input[contains(@name, 'user') or contains(@name, 'code') or contains(@id, 'barcode')]"
        )))
        # Finding the pin/password input
        pin_input = driver.find_element(By.XPATH, "//input[contains(@name, 'pass') or contains(@name, 'pin')]")
        
        logging.info("Entering secure credentials...")
        card_input.clear()
        card_input.send_keys(LIBRARY_CARD)
        
        pin_input.clear()
        pin_input.send_keys(LIBRARY_PIN)

        # Finding and clicking the submit button
        login_btn = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[contains(text(), 'Log In')]")
        login_btn.click()
        logging.info("Clicked login...")

        # --- DEBUGGING SECTION START ---
        # We wait 5 seconds to let the next page load (whether it's an error or success)
        logging.info("Waiting 5 seconds for page response...")
        time.sleep(5)
        
        # Grab the body text of whatever page we are on now
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        print("\n" + "="*30)
        print(" PAGE TEXT DUMP (DEBUGGING) ")
        print("="*30)
        print(body_text)
        print("="*30 + "\n")
        # --- DEBUGGING SECTION END ---

        # Wait for the redirect to NYT to verify success logic
        # We wait up to 10 seconds for the URL to change to something containing 'nytimes'
        wait.until(EC.url_contains("nytimes"))
        logging.info("Successfully redirected to NYT website.")
        
        # Optional: Click 'Redeem' if it exists on the landing page
        try:
            redeem_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Redeem')]")
            redeem_btn.click()
            logging.info("Clicked 'Redeem' button.")
        except:
            logging.info("No 'Redeem' button found - Pass might already be active or auto-redeemed.")

    except Exception as e:
        logging.error(f"Failed: {e}")
        # If we failed, print the final URL to see where we got stuck
        logging.info(f"Stuck on URL: {driver.current_url}")
        raise e

    finally:
        driver.quit()
        logging.info("Cloud browser closed.")

if __name__ == "__main__":
    renew_pass()