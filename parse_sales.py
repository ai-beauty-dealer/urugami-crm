#!/usr/bin/env python3
import re
import json
import os
import unicodedata
import glob
import csv
from collections import defaultdict
from datetime import datetime

def safe_int(value: str) -> int:
    """カンマやアスタリスクを含む文字列を安全に整数へ変換する"""
    if not value: return 0
    try:
        clean_val = value.replace(",", "").replace("*", "").strip()
        if not clean_val: return 0
        return int(float(clean_val))
    except:
        return 0

def safe_float(value: str) -> float:
    """在庫単価などの小数を安全に変換する"""
    if not value: return 0.0
    try:
        clean_val = value.replace(",", "").replace("*", "").strip()
        if not clean_val: return 0.0
        return float(clean_val)
    except:
        return 0.0

def get_report_month(date_str: str, salon_name: str) -> str:
    """納品日から『計上月』を判定する (原則20日締め)"""
    try:
        dt = datetime.strptime(date_str, "%Y/%m/%d")
        year, month = dt.year, dt.month
        # 原則20日締め: 21日以降は翌月扱い
        # 例: 2026/01/21 -> 2026-02
        if dt.day >= 21:
            month += 1
            if month > 12:
                month = 1
                year += 1
        return f"{year}-{month:02d}"
    except:
        if len(date_str) >= 7: return date_str[:7].replace("/", "-")
        return "unknown"

# ===== パス設定 =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../.."))
SALES_MASTER_CSV = os.path.join(BASE_DIR, "99_Sbox/売上データ/2024:06:21〜2026:02:20.csv")
SALES_TXT_GLOB = os.path.join(BASE_DIR, "99_Sbox/annual_analysis_2025/*.txt")
SALES_2026_01 = os.path.join(BASE_DIR, "99_Sbox/売上データ/2026年1月度売上.txt")
SALES_2026_02_CSV = os.path.join(BASE_DIR, "99_Sbox/売上データ/2026年2月度売上.csv")
SALES_2026_03_CSV = os.path.join(BASE_DIR, "99_Sbox/売上データ/2026年3月度売上.csv")
CUSTOMERS_JSON = os.path.join(BASE_DIR, "00_システム/devtools/route_report_tool/backend/customers.json")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "salon_products.json")
MONTHLY_JSON = os.path.join(SCRIPT_DIR, "salon_monthly_sales.json")

# Mapping data from customers.json
if os.path.exists(CUSTOMERS_JSON):
    with open(CUSTOMERS_JSON, "r", encoding="utf-8") as f:
        customers_map = json.load(f)
else:
    customers_map = {}
all_salons = [{"name": s, "day": d} for d, ss in customers_map.items() for s in ss]

def normalize(text: str) -> str:
    if not text: return ""
    result = "".join([chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else (" " if ch == "　" else ch) for ch in text])
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", result)).strip().upper()

MANUAL_MAPPING = {
    "FATE": "フェイト", "Ｆａｔｅ": "フェイト", "Fate": "フェイト",
    "リンクコネクト株式会社": "スコップ", "リンクコネクト": "スコップ",
    "STANDARD": "スタンダード", "Ｓｔａｎｄａｒｄ": "スタンダード",
    "リッシュヘアー": "リッシュヘアー", "Riche hair": "リッシュヘアー",
    "Ｐ－ｂｒａｎｄｓ ｈａｉｒ Ｕｒｉｎｏ": "ピーブランズヘア大野城",
    "P-brandshair onojo komorebi": "ピーブランズヘア大野城",
    "P-brandshair onojo": "ピーブランズヘア大野城",
    "Ｐ－ｂｒａｎｄｓ春日": "ピーブランズヘア春日",
    "Ｈａｉｒ Ａｒｉ": "アリー", "Hair Ari": "アリー", "Ari": "アリー",
    "STYLEE": "スタイリー", "Ｓｔｙｌｅｅ": "スタイリー",
    "Bellreage": "ベルリアージュ", "Hair salon Ｃｒｅａ": "クレア",
    "Hair salon Crea": "クレア", "Crea": "クレア",
    "HAIR SALON ＲＨＹＴＨＭ": "リズム", "RHYTHM": "リズム",
    "Oneness+": "ワンネス", "Oneness": "ワンネス",
    "plant": "プラント", "Plant": "プラント",
    "出張理美容協会": "出張理美容", "出張理美容": "出張理美容",
    "Hairdesign ａｔｔｒｉｃｏ": "アトリコ", "Hairdesign attrico": "アトリコ", 
    "７Ｖｅｌｖｅｔ": "セブンベルベット", "7Velvet": "セブンベルベット",
    "ｃｏｓｙ      Ｖｅｌｖｅｔ": "コージーベルベット", "cosy Velvet": "コージーベルベット",
    "ａｖｅ": "アヴェ", "Ave": "アヴェ", "ave": "アヴェ",
    "株式会社 ＴＨＲＥＥ": "スリー1階", "ere hair salon": "エレ", "ere": "エレ",
    "ｄｒｏｐ ｂｙ ｄｒｏｐ": "ドロップバイドロップ", "drop by drop": "ドロップバイドロップ",
    "Ｖｅｌｖｅｔ ｈａｉｒ": "ベルベットヘア", "Velvet hair": "ベルベットヘア",
    "ｒｉｃｏｒｅ'": "リコラ", "ricore": "リコラ", "Ｒｉｃｏｒｅ": "リコラ",
    "LYTRIE": "ライトリー", "Ｌｙｔｒｉｅ": "ライトリー",
    "THREE": "スリー5階", "THREE HAKATA bleach": "スリー ブリーチ",
    "株式会社LiBro Life Works": "リブロ", "株式会社LiBro": "リブロ",
    "ＨＡＬＳ ｈａｉｒ ｐｌａｃｅ": "ハルズヘアー", "HALS hair place": "ハルズヘアー",
    "ｌｕｃｋ": "ラック", "luck": "ラック",
    "ＫＯＺＹ株式会社": "コージー", "KOZY株式会社": "コージー", "KOZY": "コージー",
    "Ｎａｔｔｙ": "ナッティー", "Natty": "ナッティー", "NATTY": "ナッティー",
    "P-brands meinohama Ricetta": "Pブランズ姪浜", "Ｐ－ｂｒａｎｄｓ ｍｅｉｎｏｈａｍａ": "Pブランズ姪浜",
    "Pbrandshair meinohama": "Pブランズ姪浜", "Hui hair design": "フイ",
    "Ｈｕｉ ｈａｉｒ ｄｅｓｉｇｎ": "フイ", "Hui": "フイ", "Lutella": "ルテラ",
    "ＴＯＲＳＯ": "トルソー", "TORSO": "トルソー", "nook hair shop": "ヌーク", "nook": "ヌーク",
    "Seaside Hair&Nail": "シーサイド", "SEASIDE HAIR": "シーサイド", "seaside": "シーサイド",
    "KUKUI": "ククイ", "epice": "エピス", "Epice": "エピス", "epis": "エピス",
    "ATOMIK": "アトミック", "Ａｔｏｍｉｋ": "アトミック",
    "Hair make Ｌｉｌｙ": "リリー", "Hair make Lily": "リリー", "Lilly": "リリー",
    "ホロホロｈａｉｒ": "ホロホロヘアー", "ホロホロhair": "ホロホロヘアー",
    "Ｓａｌｏｎ     ＣＯＣＯ": "サロンココ", "Salon COCO": "サロンココ",
    "Ａｍｂｅｒ．": "アンバー", "Amber.": "アンバー", "luxe hair design": "リュクス", "Luxe": "リュクス",
    "Ｃｌａｒｋｅ'hair studio": "クラーク", "Clarke'hair studio": "クラーク",
    "ミツアミ堂": "ミツアミ堂", "ＬＡＣＯ    ｈａｉｒ": "ラコヘアー", "LACO hair": "ラコヘアー",
    "Ｖｅｌｖｅｔ ｈａｉｒ 千早": "ベルベット千早", "Velvet hair 千早": "ベルベット千早",
    "(株)田菱 ＰＲＡＹＥＲ": "プレアー", "田菱 PRAYER": "プレアー",
    "ＳＴＲＡＷＢＥＲＲＹ": "ストロベリー", "STRAWBERRY": "ストロベリー",
    "SiERRA LAXZE": "シエララグゼ", "sierra laxze": "シエララグゼ",
    "Roble": "ロブレ", "ロブレ": "ロブレ",
    "STYLEE produce by Hair Bloom": "スタイリー", "THREE...HAKATA bleach": "スリー ブリーチ",
    "Private salon Bellreage": "ベルリアージュ", "X Riche hair": "リッシュヘアー", 
    "AtomiK稲榮": "アトミック", "AtomiK稲栄": "アトミック", "永田　竜一": "永田 竜一",
}

def find_matching_salon(customer_name: str, all_salons: list):
    norm_cust = normalize(customer_name)
    if customer_name in MANUAL_MAPPING:
        target = MANUAL_MAPPING[customer_name]
        return next((s for s in all_salons if s["name"] == target), {"name": target, "day": "その他"})
    for raw_key, target in MANUAL_MAPPING.items():
        if normalize(raw_key) == norm_cust:
            return next((s for s in all_salons if s["name"] == target), {"name": target, "day": "その他"})
    best = next((s for s in all_salons if normalize(s["name"]) == norm_cust), None)
    return best

def parse_sales_csv(filepath: str) -> list[dict]:
    records = []
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, "r", encoding="cp932", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 30: continue # 粗利まで読み込むため30以上に
                date_str, cname, slip_no = row[5].strip(), row[1].strip(), row[6].strip()
                pcode, pname = row[17].strip(), row[18].strip()
                qty, price, sales, cost = safe_int(row[20]), safe_int(row[21]), safe_int(row[23]), safe_float(row[26])
                # ユーザー要求: 手動計算ではなく、28列目の粗利を正解として採用する
                profit = safe_int(row[28])
                
                if not re.match(r'\d{4}/\d{2}/\d{2}', date_str) or cname in ("得意先名", "売 上 一 覧 表"): continue
                records.append({
                    "customer_name": cname, "delivery_date": date_str, "slip_no": slip_no,
                    "product_code": pcode, "product_name": pname, "qty": qty, 
                    "unit_price": price, "total_sales": sales, "unit_cost": cost, "total_profit": profit
                })
    except Exception as e: print(f"  Warning: Error parsing CSV {filepath}: {e}")
    return records

def parse_sales_file(filepath: str) -> list[dict]:
    records = []
    try:
        with open(filepath, "r", encoding="utf-8") as f: lines = f.readlines()
        cur_c, cur_d, cur_s = None, None, None
        for line in lines:
            line = line.replace("\x0c", "")
            # 伝票ヘッダー
            h_match = re.search(r'^\s{0,10}\d{5,10}\s+(.+?)\s{2,}[７7][６6][１1]\s+\S+\s+(\d{4}/\d{2}/\d{2})\s+(\d+)\s', line)
            if h_match:
                cur_c, cur_d, cur_s = h_match.group(1).strip(), h_match.group(2), h_match.group(3)
                continue
            
            # 売上行 (数量, 単価, 売上, 在庫単価, 原価, 粗利)
            # 例: 売   上  ... 1   2,700   2,700   2,007.00   2,007   693
            d_match = re.search(r'売\s+上\s+(\d+)\s+(.+?)\s+(\d+)\s+([\d,]+(?:\s+\*\*)?)\s+([\d,]+)\s+([\d,.]+)\s+([\d,]+)\s+([-\d,]+)', line)
            if d_match and cur_c:
                qty, price, sales, cost_unit, cost_total, profit = \
                    safe_int(d_match.group(3)), safe_int(d_match.group(4)), safe_int(d_match.group(5)), \
                    safe_float(d_match.group(6)), safe_int(d_match.group(7)), safe_int(d_match.group(8))
                
                records.append({
                    "customer_name": cur_c, "delivery_date": cur_d, "slip_no": cur_s,
                    "product_code": d_match.group(1), "product_name": re.sub(r"^\*\s*", "", d_match.group(2)).strip(),
                    "qty": qty, "unit_price": price, "total_sales": sales, "unit_cost": cost_unit, "total_profit": profit
                })
                continue
                
            # 伝引 (値引き) 行
            # 例: 伝引(％) ... -975 ... -975
            disc_match = re.search(r'伝引\(.+?\)\s+(\d+)\s+[-\*]*\s+([-\d,]+)\s{2,}.+?\s+([-\d,]+)', line)
            if disc_match and cur_c:
                # 伝引の金額は3番目の数値（右端の粗利/合計）を採用
                disc_val = safe_int(disc_match.group(3))
                records.append({
                    "customer_name": cur_c, "delivery_date": cur_d, "slip_no": cur_s,
                    "product_code": "DISCOUNT", "product_name": "伝引",
                    "qty": 1, "unit_price": disc_val, "total_sales": disc_val, "unit_cost": 0, "total_profit": disc_val
                })
                
    except Exception as e: print(f"  Warning: Error parsing TXT {filepath}: {e}")
    return records

def run_parsing():
    print("売上ファイルを解析中...")
    raw = []
    if os.path.exists(SALES_MASTER_CSV): raw.extend(parse_sales_csv(SALES_MASTER_CSV))
    for f in sorted(glob.glob(SALES_TXT_GLOB)):
        if os.path.basename(f) != os.path.basename(SALES_MASTER_CSV): raw.extend(parse_sales_file(f))
    for f in [SALES_2026_01, SALES_2026_02_CSV, SALES_2026_03_CSV]:
        if os.path.exists(f): raw.extend(parse_sales_csv(f) if f.endswith(".csv") else parse_sales_file(f))
    
    seen, unique = set(), []
    for r in raw:
        key = (r["delivery_date"], r["customer_name"], r["slip_no"], r["product_code"], r["qty"], r["total_sales"])
        if key not in seen: seen.add(key); unique.append(r)
    
    # Aggregation
    prod_map = defaultdict(dict)
    monthly = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "salons": {}}
    for r in unique:
        c, p, d = r["customer_name"], r["product_code"], r["delivery_date"]
        matched = find_matching_salon(c, all_salons)
        sname = matched["name"] if matched else c
        month = get_report_month(d, sname)
        
        # Product Map (伝引以外を商品マスタへ追加)
        if p != "DISCOUNT":
            if p not in prod_map[sname]: prod_map[sname][p] = {"product_code": p, "product_name": r["product_name"], "unit_price": r["unit_price"], "unit_cost": r["unit_cost"], "last_order_date": d}
            elif datetime.strptime(d, "%Y/%m/%d") > datetime.strptime(prod_map[sname][p]["last_order_date"], "%Y/%m/%d"):
                prod_map[sname][p].update({"last_order_date": d, "unit_price": r["unit_price"], "unit_cost": r["unit_cost"]})
        
        # Monthly Map
        if sname not in monthly["salons"]: monthly["salons"][sname] = {}
        if month not in monthly["salons"][sname]: monthly["salons"][sname][month] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
        m = monthly["salons"][sname][month]
        m["sales"] += r["total_sales"]; m["profit"] += r["total_profit"]; m["cost"] = m["sales"] - m["profit"]
        
        # Details へ追加 (伝引は月ごとに1つにまとめる)
        pname = r["product_name"]
        det = next((i for i in m["details"] if i["name"] == pname), None)
        if det: det["qty"] += r["qty"]; det["sales"] += r["total_sales"]
        else: m["details"].append({"name": pname, "qty": r["qty"], "sales": r["total_sales"]})

    # Final logic (サロン別商品リスト)
    salon_final = {d: {} for d in customers_map.keys()}
    if "その他" not in salon_final: salon_final["その他"] = {}
    for sname, prods in prod_map.items():
        matched = find_matching_salon(sname, all_salons)
        day = matched["day"] if matched else "その他"
        if sname not in salon_final[day]: salon_final[day][sname] = []
        salon_final[day][sname].extend(prods.values())
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f: json.dump({"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "customers": customers_map, "salons": salon_final}, f, ensure_ascii=False, indent=2)
    with open(MONTHLY_JSON, "w", encoding="utf-8") as f: json.dump(monthly, f, ensure_ascii=False, indent=2)
    print(f"✅ 完成: records={len(unique)}")
    return True

if __name__ == "__main__":
    run_parsing()
