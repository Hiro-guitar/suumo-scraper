import gspread
from google.oauth2.service_account import Credentials
from suumo_scrape import extract_conditions_from_url
from suumo_search_url import build_suumo_search_url
from suumo_checker import find_matching_property, check_company_name
import datetime
import pytz

# === 設定 ===
SPREADSHEET_ID_SOURCE = '1oZKxfoZbFWzTfZvSU_ZVHtnWLDmJDYNd6MSfNqlB074'
SOURCE_RANGE = 'A:J'

SPREADSHEET_ID = '195OS2gb97TUJS8srYlqLT5QXuXU0zUZxmbeuWtsGQRY'
SHEET_NAME = 'Sheet1'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)

# === 元シートのデータ取得関数 ===
def get_source_data():
    sheet = client.open_by_key(SPREADSHEET_ID_SOURCE).sheet1
    result = sheet.get(SOURCE_RANGE)
    return [(row[0], row[1], row[9]) for row in result if len(row) >= 10 and row[0] and row[9].startswith('http')]

# === 対象シート読み込み ===
target_sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# === データ取得・転記（履歴保持モード） ===
existing_values = target_sheet.get_all_values()
existing_map = {}  # {(物件名, 部屋番号): 行番号}
rows_to_keep = set()

for idx, row in enumerate(existing_values[1:], start=2):  # ヘッダー除外
    if len(row) >= 2:
        key = (row[0], row[1])
        existing_map[key] = idx

property_data = get_source_data()

for (title, room_no, url) in property_data:
    key = (title, room_no)
    if key in existing_map:
        row_idx = existing_map[key]
        target_sheet.update_cell(row_idx, 3, url)  # C列 = URL
        rows_to_keep.add(row_idx)
    else:
        target_sheet.append_row([title, room_no, url])
        new_row = len(target_sheet.get_all_values())
        rows_to_keep.add(new_row)

# === 古い行を削除（元シートに存在しない物件） ===
rows_all = set(existing_map.values())
rows_to_delete = sorted(rows_all - rows_to_keep, reverse=True)

for row_idx in rows_to_delete:
    target_sheet.delete_rows(row_idx)

# === 結果列の追加準備 ===
all_values = target_sheet.get_all_values()
max_col = max((len(row) for row in all_values if any(cell.strip() for cell in row)), default=0)
col_index = max_col + 1

if target_sheet.col_count < col_index:
    target_sheet.add_cols(col_index - target_sheet.col_count)

# === 日時ラベル記入（日本時間） ===
tokyo = pytz.timezone('Asia/Tokyo')
now = datetime.datetime.now(tokyo)
timestamp = now.strftime("%m-%d %H:%M")
target_sheet.update_cell(1, col_index, timestamp)

# === チェック処理本体 ===
for i, (_, _, url) in enumerate(property_data, start=2):
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
            target_sheet.update_cell(i, 4, search_url)  # D列

            detail_url = find_matching_property(search_url, result)

            if detail_url:
                if check_company_name(detail_url):
                    print("⭕️ えほうまきが掲載中！")
                    target_sheet.update_cell(i, col_index, "⭕️")
                else:
                    print("❌ 他社掲載")
                    target_sheet.update_cell(i, col_index, "❌")
            else:
                print("🔍 一致物件なし")
                target_sheet.update_cell(i, col_index, "")
        else:
            print("⚠️ 検索URL作成失敗")
            target_sheet.update_cell(i, col_index, "URL失敗")
    else:
        print("⚠️ 条件抽出失敗")
        target_sheet.update_cell(i, col_index, "抽出失敗")
