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

# === 既存行の中で、元データにない物件は削除 ===
def clean_target_sheet(target_sheet, valid_entries, start_row=2):
    existing_values = target_sheet.get_all_values()
    rows_to_delete = []

    for i, row in enumerate(existing_values[start_row - 1:], start=start_row):
        if len(row) < 2:
            continue
        title = row[0].strip()
        room_no = row[1].strip()
        if (title, room_no) not in valid_entries:
            rows_to_delete.append(i)

    # 後ろから削除しないと行番号がずれるので reverse
    for row_index in reversed(rows_to_delete):
        print(f"🗑️ 削除対象: 行 {row_index}")
        target_sheet.delete_rows(row_index)

# === データ取得・転記 ===
target_sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
property_data = get_source_data()
# 重複防止のために一度掃除してから貼る
valid_pairs = [(title.strip(), room.strip()) for (title, room, _) in property_data]
clean_target_sheet(target_sheet, valid_pairs)

start_row = 2

# 一括書き込み（物件名, 部屋番号, URL → A列〜C列）
values_to_write = [[title, room_no, url] for (title, room_no, url) in property_data]
end_row = start_row + len(values_to_write) - 1
target_sheet.update(f"A{start_row}:C{end_row}", values_to_write)

# === 動的に結果列を追加 ===
all_values = target_sheet.get_all_values()
max_col = max((len(row) for row in all_values if any(cell.strip() for cell in row)), default=0)
col_index = max_col + 1

if target_sheet.col_count < col_index:
    target_sheet.add_cols(col_index - target_sheet.col_count)

# === 日時ラベルを記入 ===
tokyo = pytz.timezone('Asia/Tokyo')
now = datetime.datetime.now(tokyo)
timestamp = now.strftime("%m-%d %H:%M")
target_sheet.update_cell(1, col_index, timestamp)

# === 各物件のSUUMOチェック処理 ===
for i, (_, _, url) in enumerate(property_data, start=start_row):
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
