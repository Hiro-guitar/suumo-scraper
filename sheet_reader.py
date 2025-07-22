import gspread
from google.oauth2.service_account import Credentials
from suumo_scrape import extract_conditions_from_url
from suumo_search_url import build_suumo_search_url
from suumo_checker import find_matching_property, check_company_name
import datetime
import pytz 

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = '195OS2gb97TUJS8srYlqLT5QXuXU0zUZxmbeuWtsGQRY'
SHEET_NAME = 'Sheet1'
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

urls = sheet.col_values(3)  # C列（URL）

all_values = sheet.get_all_values()
max_col = max((len(row) for row in all_values if any(cell.strip() for cell in row)), default=0)
col_index = max_col + 1  # 右端の次の列

# 列数が足りなければ追加
if sheet.col_count < col_index:
    sheet.add_cols(col_index - sheet.col_count)

tokyo = pytz.timezone('Asia/Tokyo')
now = datetime.datetime.now()
timestamp = now.strftime("%m-%d %H:%M")  # ← 年なし、時:分あり
sheet.update_cell(1, col_index, timestamp)

for i, url in enumerate(urls, start=1):
    if not url.strip().startswith("http"):
        continue

    print(f"🔗 処理中: {url}")
    result = extract_conditions_from_url(url)

    if result:
        print(f"🏠 物件名: {result.get('title', 'N/A')}")

        search_url = build_suumo_search_url(
            station_info=result['stations'],
            price=result['price'],
            area_max=result['area'],
            age_max=result['age'],
            floor_plan=result['floor_plan']
        )

        if search_url:
            print(f"🔎 検索URL: {search_url}")  # ここで検索URLも表示

            # 🔽🔽 D列に検索URLを記入（列番号4）
            sheet.update_cell(i, 4, search_url)

            detail_url = find_matching_property(search_url, result)

            if detail_url:
                if check_company_name(detail_url):
                    print("⭕️ えほうまきが掲載中！")
                    sheet.update_cell(i, col_index, "⭕️")
                else:
                    print("❌ 他社掲載")
                    sheet.update_cell(i, col_index, "❌")
            else:
                print("🔍 一致物件なし")
                sheet.update_cell(i, col_index, "")
        else:
            print("⚠️ 検索URL作成失敗")
            sheet.update_cell(i, col_index, "URL失敗")
    else:
        print("⚠️ 条件抽出失敗")
        sheet.update_cell(i, col_index, "抽出失敗")
