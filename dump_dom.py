import time
from datetime import datetime, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://www.goindigo.in/"

options = uc.ChromeOptions()
driver = uc.Chrome(options=options, version_main=151)

try:
    print("Loading page...")
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 10)
    
    date_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-widget-form-body__departure .booking-widget-field input")))
    driver.execute_script("arguments[0].click();", date_input)
    time.sleep(2)
    
    with open("calendar_dump.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
        
    print("Dumped calendar to calendar_dump.html")
except Exception as e:
    print(e)
finally:
    driver.quit()
