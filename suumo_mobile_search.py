from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time

def scroll_and_adjust_slider(wait, xpath_selector, key, steps):
    slider = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_selector)))
    
    wait._driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", slider)
    time.sleep(0.5)


    slider.click()
    time.sleep(0.3)
    for _ in range(steps):
        slider.send_keys(key)
        time.sleep(0.05)

mobile_emulation = { "deviceName": "iPhone X" }
chrome_options = Options()
chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
# chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

service = Service("./chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)
wait = WebDriverWait(driver, 10)

driver.get("https://suumo.jp/chintai/tokyo/ensen/")
time.sleep(3)

try:
    # 路線選択
    line_elem = wait.until(EC.element_to_be_clickable(
        (By.XPATH, '//span[contains(text(),"東京メトロ丸ノ内線")]')
    ))
    line_elem.click()
    time.sleep(1)

    # 駅選択
    checkbox = wait.until(EC.element_to_be_clickable(
        (By.XPATH, '//span[contains(text(),"四谷三丁目")]/preceding-sibling::span/input[@type="checkbox"]')
    ))
    checkbox.click()
    time.sleep(1)

    # 検索条件追加
    filter_button = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, 'button.filter-button.js-filter-button')
    ))
    filter_button.click()
    time.sleep(2)

    # 賃料（上限）：24ステップ左（最大50 → 26万円）
    scroll_and_adjust_slider(wait,
        '//h2[text()="賃料"]/following-sibling::div//div[contains(@class,"rc-slider-handle-2")]',
        Keys.ARROW_LEFT, 24)

    # 間取り
    madori_types = ["1K", "1LDK"]
    for madori in madori_types:
        checkbox = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f'//span[text()="{madori}"]/preceding-sibling::input[@type="checkbox"]')
        ))
        checkbox.click()
        time.sleep(0.5)

    # 駅徒歩（上限）：2ステップ左（7分→5分）
    scroll_and_adjust_slider(wait,
        '//h2[text()="駅からの徒歩分数"]/following-sibling::div//div[@role="slider"]',
        Keys.ARROW_LEFT, 2)

    # 築年数：5ステップ左（10年→5年）
    scroll_and_adjust_slider(wait,
        '//h2[text()="築年数"]/following-sibling::div//div[@role="slider"]',
        Keys.ARROW_LEFT, 5)

    # 専有面積：下限を右へ（0→30㎡）
    scroll_and_adjust_slider(wait,
        '//h2[text()="専有面積"]/following-sibling::div//div[contains(@class,"rc-slider-handle-1")]',
        Keys.ARROW_RIGHT, 2)

    # 専有面積：上限を左へ（100㎡→75㎡）
    scroll_and_adjust_slider(wait,
        '//h2[text()="専有面積"]/following-sibling::div//div[contains(@class,"rc-slider-handle-2")]',
        Keys.ARROW_LEFT, 5)

    # 「選択した条件で検索」ボタン（JSで強制クリック）
    search_btn = wait.until(EC.presence_of_element_located(
        (By.XPATH, '//button[contains(text(), "選択した条件で検索")]')
    ))
    driver.execute_script("arguments[0].click();", search_btn)

    results = driver.find_elements(By.CLASS_NAME, "cassetteitem_content")
    if results:
        print("✅ 条件に一致する物件が見つかりました！")
    else:
        print("⚠️ 一致する物件が見つかりませんでした。")

except Exception as e:
    print(f"❌ エラー発生: {e}")

finally:
    driver.quit()
