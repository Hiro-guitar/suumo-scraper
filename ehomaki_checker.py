# ehomaki_checker.py

import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from suumo_scrape import extract_conditions_from_url
from suumo_search_url import build_suumo_search_url

# ========== スプレッドシート設定 ==========
SPREADSHEET_ID = '195OS2gb97TUJS8srYlqLT5QXuXU0zUZxmbeuWtsGQRY'
SHEET_NAME = 'Sheet1'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# ========== Seleniumドライバー設定 ==========
def get_driver():
    options = Options()
    options.add_argument('--headless')  # ヘッドレスで実行
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    return webdriver.Chrome(options=options)

# ========== 空いてる次の列（右端）を取得 ==========
def get_next_available_col():
    header_row = sheet.row_values(1)
    return len(header_row) + 1

# ========== 検索結果からえほうまき物件を探す ==========
def check_ehomaki_listing(search_url, expected_data):
    driver = get_driver()
    driver.get(search_url)
    time.sleep(2)

    listings = driver.find_elements(By.CSS_SELECTOR, 'div.cassetteitem')

    for listing in listings:
        try:
            # 賃料（「8.9」万円のような数字）
            price_text = listing.find_element(By.CSS_SELECTOR, '.cassetteitem_price .value').text.strip().replace('万円', '')
            # 間取り
            floor_plan_text = listing.find_element(By.CSS_SELECTOR, '.cassetteitem_madori').text.strip()
            # 専有面積（例: "19.48m²" → "19.48"）
            area_text = listing.find_element(By.CSS_SELECTOR, '.cassetteitem_menseki').text.strip().replace('m²', '')
            # 最寄駅・徒歩分数を含むブロック
            station_text = listing.find_element(By.CSS_SELECTOR, '.cassetteitem_detail-text').text
            # 築年数などの情報
            age_text = listing.find_element(By.CSS_SELECTOR, '.cassetteitem_detail-col1').text

            # === 完全一致判定 ===
            match = (
                price_text == str(expected_data["price"]) and
                area_text == str(expected_data["area"]) and
                floor_plan_text == expected_data["floor_plan"] and
                any(s["station"] in station_text for s in expected_data["stations"]) and
                f"徒歩{expected_data['stations'][0]['distance']}分" in station_text and
                f"築{expected_data['age']}年" in age_text
            )

            # ここにprintを入れてデバッグ
            print("=== 比較中 ===")
            print("賃料:", price_text, "期待値:", expected_data["price"])
            print("面積:", area_text, "期待値:", expected_data["area"])
            print("間取り:", floor_plan_text, "期待値:", expected_data["floor_plan"])
            print("駅名含むテキスト:", station_text)
            print("期待駅名一覧:", [s["station"] for s in expected_data["stations"]])
            print("徒歩分数判定文字列:", f"徒歩{expected_data['stations'][0]['distance']}分")
            print("築年数テキスト:", age_text)
            print("判定結果:", match)
            print("-------------")

            if not match:
                continue

            # === 詳細ページにアクセスして社名を確認 ===
            detail_link = listing.find_element(By.CSS_SELECTOR, 'a.js-cassette_link_href').get_attribute('href')
            driver.get(detail_link)
            time.sleep(1.5)

            if "合同会社えほうまき" in driver.page_source:
                driver.quit()
                return True

            driver.back()
            time.sleep(1)
        except Exception as e:
            print(f"⚠️ 抽出エラー: {e}")
            continue

    driver.quit()
    return False

# 新しい列を1列増やして書き込む
def append_new_column_and_write(row, value):
    header = sheet.row_values(1)
    current_cols = len(header)
    next_col = current_cols + 1

    # 列数が足りなければ拡張
    sheet.resize(cols=next_col)

    # 書き込み
    sheet.update_cell(row, next_col, value)

# ========== メイン処理 ==========
def main():
    urls = sheet.col_values(3)[1:]  # C列のURL（2行目から）
    next_col = get_next_available_col()

    for idx, url in enumerate(urls, start=2):
        if not url.strip().startswith("http"):
            continue

        print(f"🔍 処理中: Row {idx} - {url}")
        data = extract_conditions_from_url(url)
        if not data:
            print("⚠️ 抽出失敗")
            append_new_column_and_write(idx, "エラー")
            continue

        search_url = build_suumo_search_url(
            station_info=data['stations'],
            price=data['price'],
            area_max=data['area'],
            age_max=data['age'],
            floor_plan=data['floor_plan']
        )

        if not search_url:
            print("⚠️ 検索URL生成失敗")
            append_new_column_and_write(idx, "URLエラー")
            continue

        is_listed = check_ehomaki_listing(search_url, data)
        result = "⭕️" if is_listed else ""
        append_new_column_and_write(idx, result)

        print(f"✅ 結果: {result or '見つからず'}")

if __name__ == "__main__":
    main()
