"""
Debug script v3: Try multiple strategies to select a date
1. React event dispatch
2. Direct URL navigation
"""
import time
import json
from datetime import datetime, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

BASE_URL = "https://www.goindigo.in/"
ORIGIN = "DEL"
DESTINATION = "BOM"
ADVANCE_DAYS = 7

travel_date = (datetime.now() + timedelta(days=ADVANCE_DAYS)).strftime("%Y-%m-%d")
display_date = (datetime.now() + timedelta(days=ADVANCE_DAYS)).strftime("%d %b %Y")
print(f"Target: {travel_date} ({display_date})")

options = uc.ChromeOptions()
driver = uc.Chrome(options=options, version_main=151)

try:
    # ===== STRATEGY A: Direct URL to search results =====
    print("\n=== STRATEGY A: Try direct URL navigation ===")
    # Common IndiGo URL patterns for flight search
    direct_url = f"https://www.goindigo.in/book/flight-select.html?linkNav=search-widget-background-image&origin={ORIGIN}&destination={DESTINATION}&adult=1&children=0&infant=0&promoCode=&type=O&dateOfDep={travel_date}"
    print(f"Trying URL: {direct_url}")
    driver.get(direct_url)
    time.sleep(5)
    
    # Check if we got search results
    cards = driver.find_elements(By.CSS_SELECTOR, "div.srp__search-result-list__item[data-journey-key]")
    print(f"Found {len(cards)} flight cards")
    
    if cards:
        # Check what date is shown on the page
        page_text = driver.find_element(By.TAG_NAME, "body").text
        # Look for date indicators
        for line in page_text.split("\n"):
            if "sep" in line.lower() or "sept" in line.lower() or "07" in line:
                if len(line.strip()) < 80:
                    print(f"  Date-related text: '{line.strip()}'")
        
        print("\nSTRATEGY A: SUCCESS - Got flight results via direct URL!")
        print(f"Final URL: {driver.current_url}")
    else:
        print("STRATEGY A: No cards found, checking page...")
        print(f"Final URL: {driver.current_url}")
        # Maybe the URL format is different - dump what we see
        title = driver.title
        print(f"Page title: {title}")

    # ===== STRATEGY B: Try alternate URL format =====
    if not cards:
        print("\n=== STRATEGY B: Try alternate URL format ===")
        # Try DD/MM/YYYY format
        date_ddmmyyyy = (datetime.now() + timedelta(days=ADVANCE_DAYS)).strftime("%d/%m/%Y")
        direct_url2 = f"https://www.goindigo.in/book/flight-select.html?origin={ORIGIN}&destination={DESTINATION}&adult=1&children=0&infant=0&type=O&dateOfDep={date_ddmmyyyy}"
        print(f"Trying: {direct_url2}")
        driver.get(direct_url2)
        time.sleep(5)
        cards = driver.find_elements(By.CSS_SELECTOR, "div.srp__search-result-list__item[data-journey-key]")
        print(f"Found {len(cards)} flight cards")

    # ===== STRATEGY C: Dispatch React-compatible events =====
    if not cards:
        print("\n=== STRATEGY C: React event dispatch ===")
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, 20)

        # Origin
        origin_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-widget-form-body__from .booking-widget-field input")))
        driver.execute_script("arguments[0].click();", origin_input)
        time.sleep(1)
        ActionChains(driver).send_keys(ORIGIN).perform()
        time.sleep(1.5)
        opt = wait.until(EC.presence_of_element_located((By.XPATH, f"//*[text()='{ORIGIN}']")))
        driver.execute_script("arguments[0].click();", opt)
        time.sleep(1)

        # Destination
        dest_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-widget-form-body__to .booking-widget-field input")))
        driver.execute_script("arguments[0].click();", dest_input)
        time.sleep(1)
        ActionChains(driver).send_keys(DESTINATION).perform()
        time.sleep(1.5)
        opt = wait.until(EC.presence_of_element_located((By.XPATH, f"//*[text()='{DESTINATION}']")))
        driver.execute_script("arguments[0].click();", opt)
        time.sleep(1)

        # Open calendar
        date_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-widget-form-body__departure .booking-widget-field input")))
        driver.execute_script("arguments[0].click();", date_input)
        time.sleep(2)

        # Find target
        target_date_selector = f"div[data-date='{travel_date}']"
        target_el = None
        for attempt in range(6):
            elements = driver.find_elements(By.CSS_SELECTOR, target_date_selector)
            if elements:
                target_el = elements[0]
                break
            else:
                next_btn = driver.find_element(By.CSS_SELECTOR, "button.rdrNextButton")
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(0.5)

        if target_el:
            # Dispatch full event sequence that React listens to
            driver.execute_script("""
                var el = arguments[0];
                var evts = ['mousedown', 'mouseup', 'click'];
                evts.forEach(function(evtName) {
                    var evt = new MouseEvent(evtName, {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    el.dispatchEvent(evt);
                });
            """, target_el)
            time.sleep(1)
            
            # Also try dispatching on the span
            span = target_el.find_element(By.TAG_NAME, "span")
            driver.execute_script("""
                var el = arguments[0];
                var evts = ['mousedown', 'mouseup', 'click'];
                evts.forEach(function(evtName) {
                    var evt = new MouseEvent(evtName, {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    el.dispatchEvent(evt);
                });
            """, span)
            time.sleep(1)
            
            # Check aria-selected
            target_check = driver.find_elements(By.CSS_SELECTOR, target_date_selector)
            if target_check:
                print(f"  After dispatch: aria-selected='{target_check[0].get_attribute('aria-selected')}'")
            
            selected = driver.find_elements(By.CSS_SELECTOR, "div.custom-calendar-day[aria-selected='true']")
            for s in selected:
                print(f"  Currently selected: data-date='{s.get_attribute('data-date')}'")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
