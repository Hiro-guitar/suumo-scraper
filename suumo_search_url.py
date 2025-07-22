#suumo_search_url.py

from station_codes import get_codes
import math

def round_price_range(price):
    """
    指定ルールに従い、下限・上限の価格（万円）を算出する
    """
    steps = (
        [x * 0.5 for x in range(6, 41)] +  # 3.0〜20.0
        list(range(21, 31)) +              # 21〜30
        [35, 40, 50, 100]
    )
    
    # 探す位置
    lower = max([s for s in steps if s <= price])
    upper_candidates = [s for s in steps if s > price]
    upper = upper_candidates[0] if upper_candidates else None
    
    return lower, upper

def round_area_range(area):
    steps = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100]

    lowers = [s for s in steps if s <= area]
    uppers = [s for s in steps if s >= area]

    lower = max(lowers) if lowers else None
    upper = min(uppers) if uppers else None

    return lower, upper

def round_age_range(age):
    """
    築年数を指定の刻みに丸める。
    新築（0）、1, 3, 5, 7, 10, 15, 20, 25, 30
    ageがNoneならNoneを返す。
    """
    if age is None:
        return None

    steps = [0, 1, 3, 5, 7, 10, 15, 20, 25, 30]

    for step in steps:
        if age <= step:
            return step
    # もし30より大きければNoneを返す（上限）
    return None

def get_floor_plan_code(floor_plan):
    """
    間取り名からSUUMO間取りコードへ変換
    例:
    1R, ワンルーム -> 01
    1K -> 02
    1DK -> 03
    1LDK -> 04
    2K -> 05
    ...
    """
    mapping = {
       'ワンルーム': '01',
        '1R': '01',
        '1K': '02',
        '1DK': '03',
        '1LDK': '04',
        '2K': '05',
        '2DK': '06',
        '2LDK': '07',
        '3K': '08',
        '3DK': '09',
        '3LDK': '10',
        '4K': '11',
        '4DK': '12',
        '4LDK': '13',
        '5K以上': '14',
        # 必要に応じて追加してください
    }
    return mapping.get(floor_plan)

def round_walk_time(walk_minutes):
    """
    徒歩分数を以下の刻みに丸める:
    1, 3, 5, 7, 10, 15, 20
    それより大きい（20超）は指定なしとする（Noneを返す）
    """
    steps = [1, 3, 5, 7, 10, 15, 20]
    for step in steps:
        if walk_minutes <= step:
            return step
    return None  # 20分超は指定なし

def format_price(val):
    """
    .0がついていれば整数に変換して文字列で返す
    例: 9.0 → '9', 9.5 → '9.5'
    """
    return str(int(val)) if val == int(val) else str(val)

def build_suumo_search_url(station_info, price=None, area_max=None, age_max=None, floor_plan=None):
    print(f"📥 引数: price={price}, area_max={area_max}, age_max={age_max}, floor_plan={floor_plan}")
    """
    station_info: [{'line': '', 'station': '', 'distance': int}, ...]
    price: float 参考価格（万円）→ そこから下限・上限を計算
    area_max: float 最大面積（㎡）
    age_max: int 最大築年数（年）
    floor_plan: str 間取り例 '1K'（今は未対応）
    """
    if not station_info:
        return None

    # 1つ目の駅を使う
    first_station = station_info[0]
    line_name = first_station['line']
    station_name = first_station['station']
    line_code, station_code = get_codes(line_name, station_name)
    if not line_code or not station_code:
        print(f"⚠️ 駅コード取得失敗: {line_name} / {station_name}")
        return None

    # 駅コード下5桁を使用
    station_code_short = station_code[-5:]
    base_url = f"https://suumo.jp/chintai/tokyo/ek_{station_code_short}/"

    params = []

    if price:
        chinryomin, chinryomax = round_price_range(price)
        if chinryomin is not None:
            params.append(f"chinryomin={format_price(chinryomin)}")
        if chinryomax is not None:
            params.append(f"chinryomax={format_price(chinryomax)}")

    if area_max is not None:
        area_min, area_max_val = round_area_range(area_max)
        if area_min is not None:
            params.append(f"fr_senyumenmin={area_min}")
        if area_max_val is not None:
            params.append(f"fr_senyumenmax={area_max_val}")

   # 築年数
    if age_max is not None:
        cn_value = round_age_range(age_max)
        if cn_value is not None:  # ← 修正ポイント
            params.append(f"cn={cn_value}")

    # 間取りコードをURLパラメータに追加
    if floor_plan:
        code = get_floor_plan_code(floor_plan)
        if code:
            # cinm[] は配列パラメータなので、URLエンコードで %5B%5D を付ける
            params.append(f"cinm%5B%5D={code}")
    
    # 駅から徒歩分数の条件追加
    walk_minutes = first_station.get('distance')
    et = round_walk_time(walk_minutes)
    if et is not None:
        params.append(f"et={et}")

    if params:
        return base_url + "?" + "&".join(params)
    else:
        return base_url

# テスト用
if __name__ == "__main__":
    test_station_info = [{'line': '山手線', 'station': '東京', 'distance': 10}]
    url = build_suumo_search_url(
        test_station_info,
        price=9.9,
        area_max=27.49,
        age_max=10
    )
    print(url)
