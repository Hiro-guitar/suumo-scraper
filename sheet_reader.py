import gspread
from google.oauth2.service_account import Credentials
from suumo_scrape import extract_conditions_from_url
from suumo_search_url import build_suumo_search_url
from suumo_checker import find_matching_property, check_company_name
import datetime
import pytz
import time

# === 設定 ===
SPREADSHEET_ID_SOURCE = '1oZKxfoZbFWzTfZvSU_ZVHtnWLDmJDYNd6MSfNqlB074'
SOURCE_RANGE = 'A:J'  # 元シートから取得する範囲

SPREADSHEET_ID = '195OS2gb97TUJS8srYlqLT5QXuXU0zUZxmbeuWtsGQRY'
SHEET_NAME = 'Sheet1'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)

# === 元シートのデータ取得関数 ===
def get_source_data():
    sheet = client.open_by_key(SPREADSHEET_ID_SOURCE).sheet1
    result = sheet.get(SOURCE_RANGE)
    # 物件名, 部屋番号, 掲載ページURL（URLは10列目＝index9）
    return [(row[0], row[1], row[9]) for row in result if len(row) >= 10 and row[0] and row[9].startswith('http')]

# === メイン処理 ===
def main():
    target_sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    # 1. 元シートから最新データ取得
    source_data = get_source_data()
    source_keys = set(source_data)

    # 2. 既存データ取得
    existing_data = target_sheet.get_all_values()
    existing_rows = existing_data[1:] if len(existing_data) >= 2 else []

    existing_keys = set()
    for row in existing_rows:
        if len(row) >= 3:
            existing_keys.add((row[0], row[1], row[2]))

    # 3. 不要行の削除
    rows_to_delete = []
    for i, row in enumerate(existing_rows, start=2):
        key = tuple(row[:3])
        if key not in source_keys:
            rows_to_delete.append(i)

    for row_idx in reversed(rows_to_delete):
        print(f"🗑️ 行 {row_idx} を削除")
        target_sheet.delete_rows(row_idx)
        time.sleep(1)

    # 4. 新規追加（既存にないものだけ追加、D列まで処理）
    all_values = target_sheet.get_all_values()
    existing_key_to_row = {
        (row[0], row[1], row[2]): idx
        for idx, row in enumerate(all_values[1:], start=2)
        if len(row) >= 3
    }
    max_row = len(all_values)

    for key in source_data:
        if key not in existing_key_to_row:
            print(f"➕ 追加: {key}")
            max_row += 1
            target_sheet.update(f"A{max_row}:C{max_row}", [list(key)])
            url = key[2]
            result = extract_conditions_from_url(url)

            if result:
                search_url = build_suumo_search_url(
                    station_info=result['stations'],
                    price=result['price'],
                    area_max=result['area'],
                    age_max=result['age'],
                    floor_plan=result['floor_plan']
                )
                if search_url:
                    target_sheet.update_cell(max_row, 4, search_url)
                    time.sleep(0.3)
                else:
                    target_sheet.update_cell(max_row, 4, "URL失敗")
            else:
                target_sheet.update_cell(max_row, 4, "抽出失敗")

            time.sleep(0.5)

    # 5. 結果列の準備（右端に追加）
    updated_data = target_sheet.get_all_values()
    max_col = max((len(row) for row in updated_data if any(cell.strip() for cell in row)), default=0)
    result_col_index = max_col + 1
    if result_col_index > target_sheet.col_count:
        target_sheet.add_cols(result_col_index - target_sheet.col_count)

    timestamp = datetime.datetime.now(pytz.timezone('Asia/Tokyo')).strftime("%m-%d %H:%M")
    target_sheet.update_cell(1, result_col_index, timestamp)

    # 6. ⭕️掲載確認（D列URL → 結果列）
    for i, row in enumerate(updated_data[1:], start=2):
        if len(row) < 4:
            continue
        search_url = row[3].strip()
        if not search_url.startswith("http"):
            continue

        print(f"🔍 検索: {search_url}")
        result = extract_conditions_from_url(row[2])  # 掲載ページURL
        if not result:
            print("⚠️ 抽出失敗")
            target_sheet.update_cell(i, result_col_index, "抽出失敗")
            continue

        detail_url = find_matching_property(search_url, result)
        if detail_url:
            if check_company_name(detail_url):
                print("⭕️ えほうまき掲載中")
                target_sheet.update_cell(i, result_col_index, "⭕️")
            else:
                print("❌ 他社掲載（記入スキップ）")
        else:
            print("🔍 一致なし（記入スキップ）")

        time.sleep(1)

if __name__ == "__main__":
    main()
