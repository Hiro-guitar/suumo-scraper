# suumo_checker.py

import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
}

def extract_bukken_id(text):
    """
    bc_123456789 または SUUMO タイトルの末尾（100123456789）の数字を抽出
    """
    match = re.search(r'bc_(\d+)', text)
    if match:
        return match.group(1)

    match = re.search(r'（(\d{9,})）', text)  # 末尾の全角括弧内数字
    if match:
        return match.group(1)

    return None

def find_matching_property(search_url, original_data):
    """
    検索結果ページから data-bukken-cd を取得し、対象物件IDが含まれるか確認する
    """
    bukken_id = extract_bukken_id(original_data.get("title", ""))
    if not bukken_id:
        print("⚠️ 物件IDの抽出失敗")
        return None

    try:
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ 検索ページ取得失敗: {e}")
        return None

    soup = BeautifulSoup(response.content, "html.parser")
    bukken_elements = soup.select("li[data-bukken-cd]")

    bukken_ids = {el["data-bukken-cd"] for el in bukken_elements if el.has_attr("data-bukken-cd")}

    if bukken_id in bukken_ids:
        return f"https://suumo.jp/chintai/bc_{bukken_id}/"
    else:
        return None

def check_company_name(detail_url):
    """
    対象物件ページに『合同会社えほうまき』という文字があるか確認する
    """
    try:
        response = requests.get(detail_url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ 詳細ページ取得失敗: {e}")
        return False

    soup = BeautifulSoup(response.content, "html.parser")
    text = soup.get_text()
    return "合同会社えほうまき" in text

if __name__ == "__main__":
    # テスト用の検索URLと元データタイトル（物件IDを含む）
    search_url = "https://suumo.jp/chintai/tokyo/ek_03950/?chinryomin=9.5&chinryomax=10&fr_senyumenmin=20&fr_senyumenmax=25&cn=20&cinm%5B%5D=02&et=3"
    original_data = {
        "title": "【SUUMO】ＨＯＰＥ　ＣＩＴＹ　秋葉原（合同会社えほうまき提供）／東京都千代田区岩本町３／岩本町駅の賃貸・部屋探し情報（100446479749） | 賃貸マンション・賃貸アパート"
}

    print("🔍 一致物件を探しています…")
    matched_url = find_matching_property(search_url, original_data)

    if matched_url:
        print(f"✅ 一致物件あり: {matched_url}")

        if check_company_name(matched_url):
            print("⭕️ 掲載会社：合同会社えほうまき")
        else:
            print("❌ 掲載会社：別会社")
    else:
        print("🔎 一致物件なし")
