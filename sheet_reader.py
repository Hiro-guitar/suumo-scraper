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

# === 元シートのデータ取得 ===
def get_source_data():
    sheet = client.open_by_key(SPREADSHEET_ID_SOURCE).sheet1
    result = sheet.get(SOURCE_RANGE)
    return [(row[0], row[1], row[9]) for row in result if len(row) >= 10 and row[0] and row[9].startswith('http')]

# === ターゲットシートとデータ ===
target_sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
source_data = get_source_data()
existing_data = target_sheet.get_all_values()

# === ヘッダー + 履歴保持処理 ===
header = existing_data[0] if existing_data else []
existing_rows = existing_data[1:] if len(existing_data) > 1 else []
existing_map = {(row[0], row[1], row[2]): idx for idx, row in enumerate(existing_rows, start=2)}

# === 最新データとして上書き + 不要行は削除 ===
new_rows = []
row_mapping = {}  # 新しいrow番号 → 元データindex

for idx, row in enumerate(source_data, start=2):
    new_rows.append([row[0], row[1], row[2]])
    row_mapping[idx] = row

# 物件名・部屋番号・URLだけ更新（A〜C列）
target_sheet.resize(rows=1)  # ヘッダー以外リセット
target_sheet.update('A2', new_rows)

# 不足列あれば追加
all_values = target_sheet.get_all_values()
max_col = max(len(r) for r in all_values if any(c.strip() for c in r))
col_index = max_col + 1
if target_sheet.col_count < col_index:
    target_sheet.add_cols(col_index - target_sheet.col_count)

# タイムスタンプ記入
now = datetime.datetime.now(pytz.timezone("Asia/Tokyo"))
timestamp = now.strftime("%m-%d %H:%M")
target_sheet.update_cell(1, col_index, timestamp)

# === SUUMOチェック一括処理 ===
search_urls = []
statuses = []

for i, (title, room_no, url) in enumerate(source_data, start=2):
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
            detail_url = find_matching_property(search_url, result)

            if detail_url:
                if check_company_name(detail_url):
                    print("⭕️ えほうまきが掲載中！")
                    status = "⭕️"
                else:
                    print("❌ 他社掲載")
                    status = "❌"
            else:
                print("🔍 一致物件なし")
                status = ""
        else:
            print("⚠️ 検索URL作成失敗")
            search_url = ""
            status = "URL失敗"
    else:
        print("⚠️ 条件抽出失敗")
        search_url = ""
        status = "抽出失敗"

    search_urls.append([search_url])
    statuses.append([status])

# === 一括で書き込み ===
start_row = 2
end_row = start_row + len(search_urls) - 1

# 検索URLを D列に
target_sheet.update(f"D{start_row}:D{end_row}", search_urls)

# 結果（⭕️❌）を履歴列に
from gspread.utils import rowcol_to_a1
start_cell = rowcol_to_a1(start_row, col_index)
end_cell = rowcol_to_a1(end_row, col_index)
target_sheet.update(f"{start_cell}:{end_cell}", statuses)
