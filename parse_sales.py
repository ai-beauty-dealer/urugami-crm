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
    if not value: return 0
    try:
        clean_val = value.replace(",", "").replace("*", "").replace(" ", "").strip()
        if not clean_val: return 0
        return int(float(clean_val))
    except:
        return 0

def safe_float(value: str) -> float:
    if not value: return 0.0
    try:
        clean_val = value.replace(",", "").replace("*", "").replace(" ", "").strip()
        if not clean_val: return 0.0
        return float(clean_val)
    except:
        return 0.0

def normalize(text: str) -> str:
    if not text: return ""
    result = "".join([chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else (" " if ch == "　" else ch) for ch in text])
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", result)).strip().upper()

def get_report_month(date_str: str, salon_name: str) -> str:
    """納品日から『計上月』を判定する (原則20日締め: 21日から翌月)"""
    try:
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
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "salon_products.json")
MONTHLY_JSON = os.path.join(SCRIPT_DIR, "salon_monthly_sales.json")

if os.path.exists(CUSTOMERS_JSON):
    with open(CUSTOMERS_JSON, "r", encoding="utf-8") as f:
        customers_map = json.load(f)
else:
    customers_map = {}
all_salons = [{"name": s, "day": d} for d, ss in customers_map.items() for s in ss]

def parse_sales_csv(filepath: str) -> list[dict]:
    records = []
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, "r", encoding="cp932", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 30: continue
                date_str, cname, slip_no = row[5].strip(), row[1].strip(), row[6].strip()
                if not re.match(r'\d{4}/\d{2}/\d{2}', date_str) or cname in ("得意先名", "売 上 一 覧 表"): continue
                records.append({
                    "customer_name": cname, "delivery_date": date_str, "slip_no": slip_no,
                    "product_code": row[17].strip(), "product_name": row[18].strip(),
                    "qty": safe_int(row[20]), "unit_price": safe_int(row[21]), 
                    "total_sales": safe_int(row[23]), "unit_cost": safe_float(row[26]), "total_profit": safe_int(row[28])
                })
    except Exception as e: print(f"  Err CSV {filepath}: {e}")
    return records

def parse_sales_file(filepath: str) -> list[dict]:
    records = []
    try:
        with open(filepath, "r", encoding="utf-8") as f: lines = f.readlines()
        cur_c, cur_d, cur_s = None, None, None
        for line in lines:
            line = line.replace("\x0c", "").replace("\n", "")
            # Header
            h_match = re.search(r'^\s{0,10}(\d{5,10})\s+(.+?)\s{2,}[７7][６6][１1]', line)
            d_match_header = re.search(r'(\d{4}/\d{2}/\d{2})\s+(\d+)\s', line)
            if h_match and d_match_header:
                cur_c, cur_d, cur_s = h_match.group(2).strip(), d_match_header.group(1), d_match_header.group(2)
                continue
            
            # Sale
            sale_match = re.search(r'売\s+上\s+(\d+)\s+(.+?)\s+(\d+)\s+([\d,]+(?:\s+\*\*)?)\s+([-\d,]+)\s+([\d,.]+)\s+([-\d,]+)\s+([-\d,]+)', line)
            if sale_match and cur_c:
                records.append({
                    "customer_name": cur_c, "delivery_date": cur_d, "slip_no": cur_s,
                    "product_code": sale_match.group(1), "product_name": re.sub(r"^\*\s*", "", sale_match.group(2)).strip(),
                    "qty": safe_int(sale_match.group(3)), "unit_price": safe_int(sale_match.group(4)), 
                    "total_sales": safe_int(sale_match.group(5)), "unit_cost": safe_float(sale_match.group(6)), "total_profit": safe_int(sale_match.group(8))
                })
                continue
                
            # Discount (Improved)
            disc_match = re.search(r'伝引\((.+?)\)\s+([-\d,%]*)\s+[-\*]*\s+([-\d,]+)\s+([-\d,]+)', line)
            if disc_match and cur_c:
                # 伝引の数値は行末の Profit/Total を採用 (group 4)
                disc_val = safe_int(disc_match.group(4))
                records.append({
                    "customer_name": cur_c, "delivery_date": cur_d, "slip_no": cur_s,
                    "product_code": "DISCOUNT", "product_name": "伝引", # 名称を統一
                    "qty": 1, "unit_price": disc_val, "total_sales": disc_val, "unit_cost": 0, "total_profit": disc_val
                })
    except Exception as e: print(f"  Err TXT {filepath}: {e}")
    return records

def run_parsing():
    print("売上統合フェーズ開始...")
    month_to_file = {}
    # モジュールごとに「最も詳細な最新の個別ファイル」を優先して1つ選ぶ
    for f in SALES_INDIVIDUAL_FILES:
        if os.path.basename(f) == os.path.basename(SALES_MASTER_CSV) or ".pdf" in f: continue
        # ファイル名からターゲット月を推測
        m = re.search(r'(\d{4})年(\d+)月', os.path.basename(f))
        if m:
            target = f"{m.group(1)}-{int(m.group(2)):02d}"
            # layout.txt を最優先、次に csv, 最後に TXT
            if target not in month_to_file or "_layout.txt" in f:
                month_to_file[target] = f
    
    raw = []
    processed_months = set()
    for month, f in month_to_file.items():
        print(f"  {month}度のソース: {os.path.basename(f)}")
        recs = parse_sales_csv(f) if f.endswith(".csv") else parse_sales_file(f)
        raw.extend(recs)
        processed_months.add(month)
        
    if os.path.exists(SALES_MASTER_CSV):
        print(f"  マスターCSVから未処理月を補完中...")
        master_recs = parse_sales_csv(SALES_MASTER_CSV)
        added_count = 0
        for r in master_recs:
            m = get_report_month(r["delivery_date"], r["customer_name"])
            if m not in processed_months:
                raw.append(r)
                added_count += 1
        print(f"  マスターから {added_count} 件追加")
    
    seen, unique = set(), []
    for r in raw:
        # 重複排除キーに「正規化された顧客名」を使用
        key = (r["delivery_date"], normalize(r["customer_name"]), r["slip_no"], r["product_code"], r["qty"], r["total_sales"])
        if key not in seen: seen.add(key); unique.append(r)
    
    # 集計ロジック (略)
    monthly = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "salons": {}}
    for r in unique:
        c, p, d = r["customer_name"], r["product_code"], r["delivery_date"]
        # 表示用の名寄せ
        matched = next((s for s in all_salons if normalize(s["name"]) == normalize(c)), None)
        sname = matched["name"] if matched else c
        month = get_report_month(d, sname)
        
        if sname not in monthly["salons"]: monthly["salons"][sname] = {}
        if month not in monthly["salons"][sname]: monthly["salons"][sname][month] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
        m = monthly["salons"][sname][month]
        m["sales"] += r["total_sales"]; m["profit"] += r["total_profit"]; m["cost"] = m["sales"] - m["profit"]
        
        pname = r["product_name"]
        det = next((i for i in m["details"] if normalize(i["name"]) == normalize(pname)), None)
        if det: det["qty"] += r["qty"]; det["sales"] += r["total_sales"]
        else: m["details"].append({"name": pname, "qty": r["qty"], "sales": r["total_sales"]})

    with open(MONTHLY_JSON, "w", encoding="utf-8") as f: json.dump(monthly, f, ensure_ascii=False, indent=2)
    # 簡易検証
    total_jan = sum(sal.get("2026-01", {}).get("sales", 0) for sal in monthly["salons"].values())
    print(f"🎉 2026-01 総売上: {total_jan:,}円")
    return True

if __name__ == "__main__":
    run_parsing()
