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

def get_report_month(date_str: str) -> str:
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
MONTHLY_JSON = os.path.join(SCRIPT_DIR, "salon_monthly_sales.json")

if os.path.exists(CUSTOMERS_JSON):
    with open(CUSTOMERS_JSON, "r", encoding="utf-8") as f:
        customers_map = json.load(f)
else:
    customers_map = {}
all_salons = [{"name": s, "day": d} for d, ss in customers_map.items() for s in ss]

def parse_sales_csv(filepath: str) -> list[dict]:
    """CSVから明細を抽出する (摘要がない形式用)"""
    records = []
    try:
        with open(filepath, "r", encoding="cp932", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 30: continue
                date_str, cname = row[5].strip(), row[1].strip()
                if not re.match(r'\d{4}/\d{2}/\d{2}', date_str) or cname in ("得意先名", "売 上 一 覧 表"): continue
                records.append({
                    "salon_name": cname,
                    "month": get_report_month(date_str),
                    "sales": safe_int(row[23]),
                    "cost": safe_int(row[27]),
                    "profit": safe_int(row[28])
                })
    except Exception as e: print(f"  Err CSV {filepath}: {e}")
    return records

def parse_layout_file(filepath: str) -> list[dict]:
    """layout.txt ファイルから「摘要（小計）」行を直接抽出する"""
    records = []
    try:
        with open(filepath, "r", encoding="utf-8") as f: lines = f.readlines()
        cur_c = None
        for line in lines:
            line = line.replace("\x0c", "").replace("\n", "")
            h_match = re.search(r'^\s{0,10}(\d{5,10})\s+(.+?)\s{2,}[７7][６6][１1]', line)
            if h_match: cur_c = h_match.group(2).strip(); continue
            abst_match = re.search(r'摘要\s+([\d:]+)?(.+?)\s+([-\d,]+)\s+([-\d,]+)\s+([-\d,]+)', line)
            if abst_match and cur_c:
                date_m = re.search(r'作成日\s+(\d+)/(\d+)/(\d+)', line) # 日付取得が難しい場合はファイルの想定月を使用
                records.append({
                    "salon_name": cur_c,
                    "sales": safe_int(abst_match.group(3)),
                    "cost": safe_int(abst_match.group(4)),
                    "profit": safe_int(abst_match.group(5)),
                    "is_summary": True
                })
    except Exception as e: print(f"  Err TXT {filepath}: {e}")
    return records

def run_parsing():
    print("売上統合フェーズ開始 (ハイブリッドモード)...")
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
        recs = []
        if "_layout.txt" in f:
            recs = parse_layout_file(f)
            # layout.txt の場合は records 内に月情報を埋める
            for r in recs: r["month"] = month
        else:
            recs = parse_sales_csv(f)
        
        for r in recs:
            sname_raw = r["salon_name"]
            matched = next((s for s in all_salons if normalize(s["name"]) == normalize(sname_raw)), None)
            sname = matched["name"] if matched else sname_raw
            m_key = r["month"]
            if sname not in monthly["salons"]: monthly["salons"][sname] = {}
            if m_key not in monthly["salons"][sname]: monthly["salons"][sname][m_key] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
            item = monthly["salons"][sname][m_key]
            item["sales"] += r["sales"]; item["profit"] += r["profit"]; item["cost"] += r["cost"]
        processed_months.add(month)

    # マスターCSVから未処理月 (2024年など) を復元
    if os.path.exists(SALES_MASTER_CSV):
        print(f"  マスターCSVから未処理月を補完中...")
        master_recs = parse_sales_csv(SALES_MASTER_CSV)
        added_count = 0
        for r in master_recs:
            if r["month"] not in processed_months:
                sname_raw = r["salon_name"]
                matched = next((s for s in all_salons if normalize(s["name"]) == normalize(sname_raw)), None)
                sname = matched["name"] if matched else sname_raw
                m_key = r["month"]
                if sname not in monthly["salons"]: monthly["salons"][sname] = {}
                if m_key not in monthly["salons"][sname]: monthly["salons"][sname][m_key] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
                item = monthly["salons"][sname][m_key]
                item["sales"] += r["sales"]; item["profit"] += r["profit"]; item["cost"] += r["cost"]
                added_count += 1
        print(f"  マスターから {added_count} 件の明細を補完しました")

    with open(MONTHLY_JSON, "w", encoding="utf-8") as f: json.dump(monthly, f, ensure_ascii=False, indent=2)
    # 簡易検証
    total_jan = sum(sal.get("2026-01", {}).get("sales", 0) for sal in monthly["salons"].values())
    total_dec24 = sum(sal.get("2024-12", {}).get("sales", 0) for sal in monthly["salons"].values())
    print(f"🎉 検証 2026-01 総売上: {total_jan:,}円")
    print(f"🎉 検証 2024-12 総売上: {total_dec24:,}円")
    return True

if __name__ == "__main__":
    run_parsing()
