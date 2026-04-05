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

def normalize_name(text: str) -> str:
    """サロン名の表記ゆれ（全角・半角・連続スペース・記号）を排除する"""
    if not text: return ""
    # 全角を半角に、NFKCで正規化（＆や・なども標準化される）
    result = unicodedata.normalize("NFKC", text)
    # 記号の除去（任意：名寄せの精度を上げるため、特定の記号を消去または置換）
    result = result.replace("・", "").replace(" ", "").replace("　", "")
    return result.strip().upper()

def get_report_month(date_str: str) -> str:
    try:
        # yyyy/mm/dd or yyyy-mm-dd
        date_str = date_str.replace("-", "/")
        dt = datetime.strptime(date_str, "%Y/%m/%d")
        year, month = dt.year, dt.month
        # 21日以降は翌月扱い（業界慣習）
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

# マスターの名寄せリストを作成
if os.path.exists(CUSTOMERS_JSON):
    with open(CUSTOMERS_JSON, "r", encoding="utf-8") as f:
        customers_map = json.load(f)
else:
    customers_map = {}
# 名前 -> 正規化名 のマッピング
name_to_canonical = {}
for ss in customers_map.values():
    if not ss: continue
    canonical = ss[0] # 最初の名前を代表名とする
    for s in ss:
        name_to_canonical[normalize_name(s)] = canonical

def get_canonical_name(raw_name: str) -> str:
    norm = normalize_name(raw_name)
    return name_to_canonical.get(norm, re.sub(r"\s+", " ", raw_name).strip())

def parse_sales_csv(filepath: str) -> list[dict]:
    records = []
    try:
        with open(filepath, "r", encoding="cp932", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 30: continue
                date_str, cname = row[5].strip(), row[1].strip()
                if not re.match(r'\d{4}/\d{2}/\d{2}', date_str) or cname in ("得意先名", "売 上 一 覧 表"): continue
                
                records.append({
                    "salon_name": get_canonical_name(cname),
                    "month": get_report_month(date_str),
                    "product_name": row[18].strip(),
                    "qty": safe_int(row[20]),
                    "sales": safe_int(row[23]),
                    "cost": safe_int(row[27]),
                    "profit": safe_int(row[28])
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
    print("売上統合フェーズ開始 (名寄せ強化モード)...")
    monthly = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "salons": {}}
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
            sname = r["salon_name"]; m_key = month if f.endswith(".txt") else r["month"]
            if sname not in monthly["salons"]: monthly["salons"][sname] = {}
            if m_key not in monthly["salons"][sname]: 
                monthly["salons"][sname][m_key] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
            
            item = monthly["salons"][sname][m_key]
            item["sales"] += r["sales"]; item["profit"] += r["profit"]; item["cost"] += r["cost"]
            
            if f.endswith(".txt") and "temp_details" in r:
                for p in r["temp_details"]:
                    # シンプルに加算（Layoutの場合は金額情報が各商品行にないので、数量ベース）
                    existing = next((d for d in item["details"] if d["name"] == p["name"]), None)
                    if existing: existing["qty"] += p["qty"]
                    else: item["details"].append({"name": p["name"], "qty": p["qty"], "sales": 0})
            elif not f.endswith(".txt") and "product_name" in r:
                p_name = r["product_name"]
                if p_name:
                    existing = next((d for d in item["details"] if d["name"] == p_name), None)
                    if existing: 
                        existing["qty"] += r["qty"]
                        existing["sales"] += r["sales"]
                    else: 
                        item["details"].append({"name": p_name, "qty": r["qty"], "sales": r["sales"]})
        if recs: processed_months.add(month)

    if os.path.exists(SALES_MASTER_CSV):
        print(f"  マスターCSVから未処理月を補完中...")
        master_recs = parse_sales_csv(SALES_MASTER_CSV)
        for r in master_recs:
            if r["month"] not in processed_months:
                sname = r["salon_name"]; m_key = r["month"]
                if sname not in monthly["salons"]: monthly["salons"][sname] = {}
                if m_key not in monthly["salons"][sname]: monthly["salons"][sname][m_key] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
                item = monthly["salons"][sname][m_key]
                item["sales"] += r["sales"]; item["profit"] += r["profit"]; item["cost"] += r["cost"]

    with open(MONTHLY_JSON, "w", encoding="utf-8") as f: json.dump(monthly, f, ensure_ascii=False, indent=2)
    print("🎉 名寄せ完了。")
    return True

if __name__ == "__main__":
    run_parsing()
