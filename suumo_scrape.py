# suumo_scrape.py

from bs4 import BeautifulSoup
import requests
import re

headers = {"User-Agent": "Mozilla/5.0"}

def get_property_value(soup, title_name):
    for section in soup.select(".property_data"):
        title = section.select_one(".property_data-title")
        body = section.select_one(".property_data-body")
        if title and title_name in title.text:
            return body.text.strip()
    return "N/A"

def parse_station_info(station_info_raw):
    lines = station_info_raw.strip().split('\n')
    results = []

    for line in lines:
        match = re.match(r'(.+?)[/／](.+?)駅\s*歩(\d+)分', line)
        if match:
            line_name, station_name, distance = match.groups()
            results.append({
                'line': line_name.strip(),
                'station': station_name.strip(),
                'distance': int(distance)
            })
    return results

def extract_conditions_from_url(url):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ リクエスト失敗: {url} - {e}")
        return None

    soup = BeautifulSoup(response.content, "html.parser")

    title = soup.title.text.strip()

    station_info_tag = soup.select_one(".property_view_detail-body .property_view_detail-text")
    station_info_raw = station_info_tag.text.strip() if station_info_tag else "N/A"
    station_list = parse_station_info(station_info_raw)

    price_tag = soup.select_one(".property_view_main-emphasis")
    price_text = price_tag.text.strip() if price_tag else "N/A"
    if price_text != "N/A":
        match = re.search(r"[\d\.]+", price_text)
        price_number = float(match.group()) if match else None
    else:
        price_number = None

    floor_plan = get_property_value(soup, "間取り")

    area_text = get_property_value(soup, "専有面積")
    area_number = float(re.search(r"[\d\.]+", area_text).group()) if area_text != "N/A" else None

    age_text = get_property_value(soup, "築年数")
    age_match = re.search(r"(\d+)", age_text)
    age_number = int(age_match.group(1)) if age_match else None

    return {
        "title": title,
        "station_info_raw": station_info_raw,
        "stations": station_list,
        "price": price_number,
        "floor_plan": floor_plan,
        "area": area_number,
        "age": age_number
    }
