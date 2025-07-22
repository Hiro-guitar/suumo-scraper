import gspread
from google.oauth2.service_account import Credentials
from suumo_scrape import extract_conditions_from_url
from suumo_search_url import build_suumo_search_url
from suumo_checker import find_matching_property, check_company_name
import datetime
import pytz 

# ==== スプレッドシート設定 ====
SPREADSHEET_ID_SOURCE = '1oZKxfoZbFWzTfZvSU_ZVHtnWLDmJDYNd6MSfNqlB074'
SPREADSHEET_ID = '195OS2gb97TUJS8srYlqLT5QXuXU0zUZxmbeuWtsGQRY'
SHEET_NAME = 'Sheet1'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)

# ==== 元スプレッドシートからデータ取得 ====
def get_source_data():
    source_sheet = client.open_by_key(SPREADSHEET_ID_SOURCE).worksheet('シート1')
    values = source_sheet.get_all_values()

    data = []
    for row in values[1:]:
        if len(row) >= 10 and row[0] and row[9].startswith('http'):
            data.append((row[0], row[1], row[9]))  # (物件名, 部屋番号, URL)
    return data

# ==== 出力先のシート取得 ====
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# ==== 元データをシートに貼り付け ====
property_data = get_source_data()
start_row = 2
for i, (title, room_no, url) in enumerate(property_data, start=start_row):
    sheet.update_cell(i, 1, title)
    sheet.update_cell(i, 2, room_no)
    sheet.update_cell(i, 3, url)

# ==== そのC列を対象に検索・結果判定 ====
urls = sheet.col_values(3)

all_values = sheet.get_all_values()
max_col = max((len(row) for row in all_values if any(cell.strip() for cell in row)), default=0)
col_index = max_col + 1  # 次の空き列

if sheet.col_count < col_index:
    sheet.add_cols(col_index - sheet.col_count)

tokyo = pytz.timezone('Asia/Tokyo')
now = datetime.datetime.now(tokyo)
timestamp = now.strftime("%m-%d %H:%M")
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
            print(f"🔎 検索URL: {search_url}")
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
