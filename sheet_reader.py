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
    source_keys = set(source_data)  # （物件名,部屋番号,URL）の集合

    # 2. 既存シートの全データ取得（ヘッダー含む）
    existing_data = target_sheet.get_all_values()
    if len(existing_data) < 2:
        existing_rows = []
    else:
        existing_rows = existing_data[1:]  # ヘッダーは除く

    # 3. 既存データのキーセット作成
    existing_keys = set()
    for row in existing_rows:
        if len(row) >= 3:
            existing_keys.add((row[0], row[1], row[2]))

    # 4. 既存にあってソースにない行は削除（下から順に）
    rows_to_delete = []
    for i, row in enumerate(existing_rows, start=2):
        key = tuple(row[:3])
        if key not in source_keys:
            rows_to_delete.append(i)

    for row_idx in reversed(rows_to_delete):
        print(f"🗑️ 行 {row_idx} を削除")
        target_sheet.delete_rows(row_idx)
        time.sleep(1)  # Google Sheets API制限対策で軽く待機

    # 5. ソースの物件を行単位で辞書化（key=(物件名,部屋番号,URL)）
    source_dict = {key: key for key in source_data}

    # 6. 既存データをkey→行番号マップ化（更新用）
    existing_key_to_row = {}
    for i, row in enumerate(target_sheet.get_all_values()[1:], start=2):
        if len(row) >= 3:
            existing_key_to_row[(row[0], row[1], row[2])] = i

    # 7. ソースにある物件を、既存の行番号に書き込むか、新規行追加か判定
    max_row = len(target_sheet.get_all_values())
    for key in source_data:
        if key in existing_key_to_row:
            # 既存行に更新
            row_num = existing_key_to_row[key]
            target_sheet.update(f"A{row_num}:C{row_num}", [list(key)])
            time.sleep(0.5)
        else:
            # 新規行追加（末尾）
            max_row += 1
            target_sheet.update(f"A{max_row}:C{max_row}", [list(key)])
            time.sleep(0.5)

    # 8. 列数、日時ラベルの準備
    all_values = target_sheet.get_all_values()
    max_col = max((len(row) for row in all_values if any(cell.strip() for cell in row)), default=0)
    result_col_index = max_col + 1
    if target_sheet.col_count < result_col_index:
        target_sheet.add_cols(result_col_index - target_sheet.col_count)

    tokyo = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(tokyo)
    timestamp = now.strftime("%m-%d %H:%M")
    target_sheet.update_cell(1, result_col_index, timestamp)

    # 9. 各物件のSUUMOチェック処理
    # 再度最新データ取得（A〜C列）
    updated_data = target_sheet.get_all_values()[1:]  # ヘッダー除く

    for i, row in enumerate(updated_data, start=2):
        if len(row) < 3:
            continue
        url = row[2].strip()
        if not url.startswith("http"):
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
                # D列（4列目）に検索URL更新
                target_sheet.update_cell(i, 4, search_url)
                time.sleep(0.3)

                detail_url = find_matching_property(search_url, result)

                if detail_url:
                    if check_company_name(detail_url):
                        print("⭕️ えほうまきが掲載中！")
                        target_sheet.update_cell(i, result_col_index, "⭕️")
                    else:
                        print("❌ 他社掲載")
                        target_sheet.update_cell(i, result_col_index, "❌")
                else:
                    print("🔍 一致物件なし")
                    target_sheet.update_cell(i, result_col_index, "")
            else:
                print("⚠️ 検索URL作成失敗")
                target_sheet.update_cell(i, result_col_index, "URL失敗")
        else:
            print("⚠️ 条件抽出失敗")
            target_sheet.update_cell(i, result_col_index, "抽出失敗")

        time.sleep(1)  # API制限対策ゆったり待機

if __name__ == "__main__":
    main()
