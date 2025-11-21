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

def renew_pass():
    if not LIBRARY_CARD or not LIBRARY_PIN or not NYT_EMAIL:
        logging.error("Missing credentials! Ensure LIBRARY_CARD, LIBRARY_PIN, and NYT_EMAIL are set in GitHub Secrets.")
        return

    logging.info("Setting up Browser...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # IMPORTANT: Add a fake user-agent so NYT doesn't block the login as a 'bot'
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
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
        # Library Card Input
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@name, 'user') or contains(@name, 'code')]"))).send_keys(LIBRARY_CARD)
        # PIN Input
        driver.find_element(By.XPATH, "//input[contains(@name, 'pass') or contains(@name, 'pin')]").send_keys(LIBRARY_PIN)
        
        # Click Submit
        driver.find_element(By.XPATH, "//input[@type='submit'] | //button[contains(text(), 'Log In')]").click()
        logging.info("Submitted Library credentials.")

        # --- PHASE 2: NYT INTERACTION ---
        
        # Wait for the redirect to complete (Looking for NYT text)
        logging.info("Waiting for NYT page load...")
        time.sleep(5) 
        
        body_text = driver.find_element(By.TAG_NAME, "body").text

        # Check if we need to log in to NYT
        if "Already have an account? Log in" in body_text or "Log in" in body_text:
            logging.info("NYT Login required. Starting NYT auth sequence...")
            
            # 1. Click the 'Log in' link/button
            try:
                login_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Log in')] | //button[contains(text(), 'Log in')]")
                login_link.click()
            except:
                logging.info("Could not click initial 'Log in', trying to find email field directly...")

            # 2. Enter Email
            logging.info("Entering NYT Email...")
            email_input = wait.until(EC.element_to_be_clickable((By.ID, "email")))
            email_input.clear()
            email_input.send_keys(NYT_EMAIL)
            
            # NYT sometimes requires clicking "Continue" before password
            try:
                continue_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
                continue_btn.click()
                time.sleep(2) # Short wait for animation
            except:
                pass # If no continue button, password field might be there already

            # 3. Enter Password
            logging.info("Entering NYT Password...")
            pass_input = wait.until(EC.element_to_be_clickable((By.ID, "password")))
            pass_input.clear()
            pass_input.send_keys(NYT_PASSWORD)

            # 4. Click Final Login
            logging.info("Clicking final Login button...")
            submit_btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Log In')]")
            submit_btn.click()
            
            # Wait for login to process
            time.sleep(5)

        # --- PHASE 3: REDEMPTION ---
        logging.info("Checking for 'Redeem' button...")
        
        # Refresh page text after login attempt
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
            print(body_text[:500]) # Print first 500 chars to avoid log clutter

    except Exception as e:
        logging.error(f"Failed: {e}")
        # Print URL to see where we crashed
        logging.info(f"Crashed on URL: {driver.current_url}")
        raise e

    finally:
        driver.quit()
        logging.info("Browser closed.")

if __name__ == "__main__":
    renew_pass()