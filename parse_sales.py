#!/usr/bin/env python3
import re
import json
import os
import unicodedata
import glob
import csv
from datetime import datetime

def safe_int(value: str) -> int:
    if not value: return 0
    try:
        clean_val = str(value).replace(",", "").replace("*", "").replace(" ", "").strip()
        if not clean_val: return 0
        return int(float(clean_val))
    except:
        return 0

def safe_float(value: str) -> float:
    if not value: return 0.0
    try:
        clean_val = str(value).replace(",", "").replace("*", "").replace(" ", "").strip()
        if not clean_val: return 0.0
        return float(clean_val)
    except:
        return 0.0

def get_report_month(date_str: str) -> str:
    try:
        date_str = date_str.replace("-", "/")
        dt = datetime.strptime(date_str, "%Y/%m/%d")
        year, month = dt.year, dt.month
        if dt.day >= 21:
            month += 1
            if month > 12: month = 1; year += 1
        return f"{year}-{month:02d}"
    except:
        if len(date_str) >= 7: return date_str[:7].replace("/", "-")
        return "unknown"

# ===== パス設定 =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../.."))

SALES_MASTER_CSV = os.path.join(BASE_DIR, "99_Sbox/売上データ/2024:06:21〜2026:02:20.csv")
SALES_INDIVIDUAL_FILES = sorted(glob.glob(os.path.join(BASE_DIR, "99_Sbox/annual_analysis_2025/*.txt"))) + \
                         sorted(glob.glob(os.path.join(BASE_DIR, "99_Sbox/売上データ/202[4-6]*.csv"))) + \
                         sorted(glob.glob(os.path.join(BASE_DIR, "99_Sbox/売上データ/202[4-6]*_layout.txt")))

CUSTOMERS_JSON = os.path.join(BASE_DIR, "00_システム/devtools/route_report_tool/backend/customers.json")
MONTHLY_JSON = os.path.join(SCRIPT_DIR, "salon_monthly_sales.json")
PRODUCTS_JSON = os.path.join(SCRIPT_DIR, "salon_products.json")

if os.path.exists(CUSTOMERS_JSON):
    with open(CUSTOMERS_JSON, "r", encoding="utf-8") as f:
        customers_map = json.load(f)
else:
    customers_map = {}

# 全サロンのリスト化（属する曜日を記録するため）
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
    "ATOMIK": "アトミック", "Ａｔｏｍｉｋ": "アトミック", "AtomiK稲榮": "アトミック", "AtomiK稲栄": "アトミック",
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
    "Private salon Bellreage": "ベルリアージュ", "X Riche hair": "リッシュヘアー", "永田　竜一": "永田 竜一",
}

def get_canonical_name(customer_name: str) -> str:
    norm_cust = normalize(customer_name)
    if customer_name in MANUAL_MAPPING:
        return MANUAL_MAPPING[customer_name]
    for raw_key, target in MANUAL_MAPPING.items():
        if normalize(raw_key) == norm_cust:
            return target
    # 完全一致
    for s in all_salons:
        if normalize(s["name"]) == norm_cust:
            return s["name"]
    # 部分一致
    for raw_key, target in MANUAL_MAPPING.items():
        if norm_cust in normalize(raw_key) or normalize(raw_key) in norm_cust:
            return target
    for s in all_salons:
        s_norm = normalize(s["name"])
        if s_norm in norm_cust or norm_cust in s_norm:
            return s["name"]
    return re.sub(r"\s+", " ", customer_name).strip()

def get_salon_day(salon_name: str) -> str:
    for s in all_salons:
        if s["name"] == salon_name:
            return s["day"]
    return "Others"

def parse_sales_csv(filepath: str) -> list[dict]:
    records = []
    try:
        with open(filepath, "r", encoding="cp932", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 30: continue
                date_str, cname = row[5].strip(), row[1].strip()
                if not re.match(r'\d{4}/\d{2}/\d{2}', date_str) or cname in ("得意先名", "売 上 一 覧 表"): continue
                
                # Retrieve individual fields
                pcode, pname = row[17].strip(), row[18].strip()
                qty, price, sales, cost_unit = safe_int(row[20]), safe_int(row[21]), safe_int(row[23]), safe_float(row[26])
                cost = safe_int(row[27])
                profit = safe_int(row[28])

                records.append({
                    "salon_name": get_canonical_name(cname),
                    "month": get_report_month(date_str),
                    "delivery_date": date_str,
                    "product_code": pcode,
                    "product_name": pname,
                    "qty": qty,
                    "unit_price": price,
                    "unit_cost": cost_unit,
                    "sales": sales,
                    "cost": cost,
                    "profit": profit
                })
    except Exception as e: print(f"  Err CSV {filepath}: {e}")
    return records

def parse_layout_file(filepath: str) -> list[dict]:
    records = []
    try:
        with open(filepath, "r", encoding="utf-8") as f: lines = f.readlines()
        cur_c = None
        cur_products = []
        for line in lines:
            line = line.replace("\x0c", "").replace("\n", "")
            # ヘッダー：サロン名の抽出
            h_match = re.search(r'^\s{0,10}(\d{5,10})\s+(.+?)\s{2,}[７7][６6][１1]', line)
            if h_match: 
                cur_c = h_match.group(2).strip()
                cur_products = []
                continue
            
            # 商品行の抽出（取引区分 数量 ... 売上）
            p_match = re.search(r'^\s{2,}(?:売上|ｻﾝﾌﾟﾙ)\s+\d+\s+(.+?)\s{2,}(\d+)\s+', line)
            if p_match:
                cur_products.append({
                    "name": p_match.group(1).strip(),
                    "qty": safe_int(p_match.group(2))
                })

            # 摘要行（合計金額）
            abst_match = re.search(r'摘要\s+(?:[\d:]+)?(.*?)\s{5,}([-\d,]+)\s+([-\d,]+)\s+([-\d,]+)', line)
            if abst_match and cur_c:
                records.append({
                    "salon_name": get_canonical_name(cur_c),
                    "sales": safe_int(abst_match.group(2)),
                    "cost": safe_int(abst_match.group(3)),
                    "profit": safe_int(abst_match.group(4)),
                    "temp_details": cur_products # 摘要直前の商品を紐付け
                })
                cur_products = []
    except Exception as e: print(f"  Err TXT {filepath}: {e}")
    return records

def run_parsing():
    print("売上統合フェーズ開始 (名寄せ・商品抽出対応モード)...")
    monthly = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "salons": {}}
    prod_map = {} # {sname: {pcode or pname: product_dict}}

    month_to_file = {}
    for f in SALES_INDIVIDUAL_FILES:
        if os.path.basename(f) == os.path.basename(SALES_MASTER_CSV) or ".pdf" in f: continue
        m = re.search(r'(\d{4})年(\d+)月', os.path.basename(f))
        if m:
            target = f"{m.group(1)}-{int(m.group(2)):02d}"
            if target not in month_to_file or "_layout.txt" in f:
                month_to_file[target] = f

    processed_months = set()
    for month, f in month_to_file.items():
        print(f"  {month}度のソース: {os.path.basename(f)}")
        recs = parse_layout_file(f) if f.endswith(".txt") else parse_sales_csv(f)
        for r in recs:
            sname = r["salon_name"]
            m_key = month if f.endswith(".txt") else r["month"]
            
            # --- Initialize structures ---
            if sname not in monthly["salons"]: monthly["salons"][sname] = {}
            if m_key not in monthly["salons"][sname]: 
                monthly["salons"][sname][m_key] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
            if sname not in prod_map: prod_map[sname] = {}
            
            # --- Monthly Financials ---
            item = monthly["salons"][sname][m_key]
            item["sales"] += r["sales"]; item["profit"] += r["profit"]; item["cost"] += r["cost"]
            
            # --- Products (Layout vs CSV) ---
            if f.endswith(".txt") and "temp_details" in r:
                for p in r["temp_details"]:
                    pname = p["name"]
                    # Add to monthly details
                    existing = next((d for d in item["details"] if d["name"] == pname), None)
                    if existing: existing["qty"] += p["qty"]
                    else: item["details"].append({"name": pname, "qty": p["qty"], "sales": 0})
                    
                    # Add to prod_map stub if not seen
                    if pname not in prod_map[sname] and pname != "伝引":
                        prod_map[sname][pname] = {
                            "product_code": "", "product_name": pname, 
                            "unit_price": 0, "unit_cost": 0, "last_order_date": f"{m_key}-01".replace("-", "/")
                        }
            elif not f.endswith(".txt") and "product_name" in r:
                pname = r["product_name"]
                if pname:
                    # Add to monthly details
                    existing = next((d for d in item["details"] if d["name"] == pname), None)
                    if existing: 
                        existing["qty"] += r["qty"]
                        existing["sales"] += r["sales"]
                    else: 
                        item["details"].append({"name": pname, "qty": r["qty"], "sales": r["sales"]})
                    
                    # Add to prod_map full data
                    pcode = r.get("product_code", pname)
                    if pname != "伝引" and pcode != "DISCOUNT":
                        d_str = r.get("delivery_date", f"{m_key}-01".replace("-", "/"))
                        if pcode not in prod_map[sname]:
                            prod_map[sname][pcode] = {
                                "product_code": pcode, "product_name": pname,
                                "unit_price": r.get("unit_price", 0),
                                "unit_cost": r.get("unit_cost", 0),
                                "last_order_date": d_str
                            }
                        else:
                            try:
                                old_d = prod_map[sname][pcode]["last_order_date"].replace("-", "/")
                                curr_d = d_str.replace("-", "/")
                                if datetime.strptime(curr_d, "%Y/%m/%d") > datetime.strptime(old_d, "%Y/%m/%d"):
                                    prod_map[sname][pcode].update({
                                        "last_order_date": curr_d, 
                                        "unit_price": r.get("unit_price", 0), 
                                        "unit_cost": r.get("unit_cost", 0)
                                    })
                            except:
                                pass
        if recs: processed_months.add(month)

    if os.path.exists(SALES_MASTER_CSV):
        print(f"  マスターCSVから未処理月を補完中...")
        master_recs = parse_sales_csv(SALES_MASTER_CSV)
        for r in master_recs:
            if r["month"] not in processed_months:
                sname = r["salon_name"]
                m_key = r["month"]
                
                # --- Initialize structures ---
                if sname not in monthly["salons"]: monthly["salons"][sname] = {}
                if m_key not in monthly["salons"][sname]: 
                    monthly["salons"][sname][m_key] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
                if sname not in prod_map: prod_map[sname] = {}
                
                item = monthly["salons"][sname][m_key]
                item["sales"] += r["sales"]; item["profit"] += r["profit"]; item["cost"] += r["cost"]
                
                pname = r["product_name"]
                if pname:
                    existing = next((d for d in item["details"] if d["name"] == pname), None)
                    if existing: 
                        existing["qty"] += r["qty"]
                        existing["sales"] += r["sales"]
                    else: 
                        item["details"].append({"name": pname, "qty": r["qty"], "sales": r["sales"]})
                    
                    pcode = r.get("product_code", pname)
                    if pname != "伝引" and pcode != "DISCOUNT":
                        d_str = r.get("delivery_date", f"{m_key}-01".replace("-", "/"))
                        if pcode not in prod_map[sname]:
                            prod_map[sname][pcode] = {
                                "product_code": pcode, "product_name": pname,
                                "unit_price": r.get("unit_price", 0),
                                "unit_cost": r.get("unit_cost", 0),
                                "last_order_date": d_str
                            }
                        else:
                            try:
                                old_d = prod_map[sname][pcode]["last_order_date"].replace("-", "/")
                                curr_d = d_str.replace("-", "/")
                                if datetime.strptime(curr_d, "%Y/%m/%d") > datetime.strptime(old_d, "%Y/%m/%d"):
                                    prod_map[sname][pcode].update({
                                        "last_order_date": curr_d, 
                                        "unit_price": r.get("unit_price", 0), 
                                        "unit_cost": r.get("unit_cost", 0)
                                    })
                            except:
                                pass

    # Prepare products JSON matching old format: {"Tuesday": {"salonName": [products...]}}
    salon_final = {d: {} for d in customers_map.keys()}
    if "Others" not in salon_final: salon_final["Others"] = {}
    
    for sname, prods in prod_map.items():
        day = get_salon_day(sname)
        if day == "その他": day = "Others"
        if day not in salon_final: day = "Others"
        
        if sname not in salon_final[day]:
            salon_final[day][sname] = []
        salon_final[day][sname].extend(prods.values())

    with open(PRODUCTS_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customers": customers_map,
            "salons": salon_final
        }, f, ensure_ascii=False, indent=2)

    with open(MONTHLY_JSON, "w", encoding="utf-8") as f: 
        json.dump(monthly, f, ensure_ascii=False, indent=2)
        
    print("🎉 名寄せ・商品抽出完了。")
    return True

if __name__ == "__main__":
    run_parsing()
