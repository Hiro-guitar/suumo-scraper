import gspread
from google.oauth2.service_account import Credentials
from suumo_scrape import extract_conditions_from_url
from suumo_search_url import build_suumo_search_url
from suumo_checker import find_matching_property, check_company_name
import datetime
import pytz
import time
from gspread_formatting import CellFormat, color, format_cell_range

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

    existing_keys = {(row[0], row[1], row[2]) for row in existing_rows if len(row) >= 3}

    # 3. 不要行削除
    rows_to_delete = []
    for i, row in enumerate(existing_rows, start=2):
        key = tuple(row[:3])
        if key not in source_keys:
            rows_to_delete.append(i)

    for row_idx in reversed(rows_to_delete):
        print(f"🗑️ 行 {row_idx} を削除")
        target_sheet.delete_rows(row_idx)
        time.sleep(1)

    # 4. 新規物件追加
    all_values = target_sheet.get_all_values()
    existing_key_to_row = {
        (row[0], row[1], row[2]): idx
        for idx, row in enumerate(all_values[1:], start=2)
        if len(row) >= 3
    }
    max_row = len(all_values)

    for key in source_data:
        if key not in existing_key_to_row:
            max_row += 1
            print(f"➕ 新規追加: {key}")
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
                else:
                    target_sheet.update_cell(max_row, 4, "URL失敗")
            else:
                target_sheet.update_cell(max_row, 4, "抽出失敗")
            time.sleep(0.5)

    # 5. 結果列作成
    updated_data = target_sheet.get_all_values()
    max_col = max((len(row) for row in updated_data if any(cell.strip() for cell in row)), default=0)
    result_col_index = max_col + 1
    if result_col_index > target_sheet.col_count:
        target_sheet.add_cols(result_col_index - target_sheet.col_count)

    timestamp = datetime.datetime.now(pytz.timezone('Asia/Tokyo')).strftime("%m-%d %H:%M")
    target_sheet.update_cell(1, result_col_index, timestamp)

    # 6. 掲載チェック（D列が "http〜" or "抽出失敗" → 再抽出）
    for i, row in enumerate(updated_data[1:], start=2):
        if len(row) < 4:
            continue

        d_val = row[3].strip()
        should_retry = d_val in ["抽出失敗", "URL失敗", ""]

        if should_retry:
            print(f"🔁 再抽出: {row[2]}")
            result = extract_conditions_from_url(row[2])
            if result:
                search_url = build_suumo_search_url(
                    station_info=result['stations'],
                    price=result['price'],
                    area_max=result['area'],
                    age_max=result['age'],
                    floor_plan=result['floor_plan']
                )
                if search_url:
                    target_sheet.update_cell(i, 4, search_url)
                    d_val = search_url
                else:
                    target_sheet.update_cell(i, 4, "URL失敗")
                    continue
            else:
                target_sheet.update_cell(i, 4, "抽出失敗")
                continue
            time.sleep(0.5)

        if not d_val.startswith("http"):
            print("⚠️ 無効なURL、スキップ")
            continue

        print(f"🔍 掲載チェック: {d_val}")
        result = extract_conditions_from_url(row[2])
        if not result:
            print("⚠️ 抽出失敗（掲載URL）")
            target_sheet.update_cell(i, result_col_index, "抽出失敗")
            continue

        detail_url = find_matching_property(d_val, result)
        if detail_url:
            if check_company_name(detail_url):
                print("⭕️ 掲載あり")
                green = color(0.8, 1.0, 0.8)  # 薄い緑
                fmt = CellFormat(backgroundColor=green)
                col_letter = chr(ord('A') + result_col_index - 1)
                cell_range = f"{col_letter}{i}"
                format_cell_range(target_sheet, cell_range, fmt)
                # 文字は元々空欄なら更新不要
            else:
                print("❌ 他社掲載")
        else:
            print("🔍 一致なし")

        time.sleep(1)

if __name__ == "__main__":
    main()
