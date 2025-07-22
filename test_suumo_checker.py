from suumo_checker import find_matching_property, check_company_name

# 検索URL（スマホ版になるよう User-Agent 指定済み）
search_url = "https://suumo.jp/chintai/tokyo/ek_38430/?chinryomin=9.5&chinryomax=10&fr_senyumenmin=25&fr_senyumenmax=30&cn=10&cinm%5B%5D=02&et=15"

# もとの物件ページ（sheet_reader.py で抽出された情報を模倣）
original_data = {
    "title": "bc_100449536656"
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
