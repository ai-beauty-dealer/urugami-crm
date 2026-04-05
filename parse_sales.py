#!/usr/bin/env python3
import re
import json
import os
import unicodedata
import glob
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

def normalize(text: str) -> str:
    if not text: return ""
    result = "".join([chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else (" " if ch == "　" else ch) for ch in text])
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", result)).strip().upper()

def get_report_month(date_str: str) -> str:
    """納品日から『計上月』を判定する (原則20日締め)"""
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
SALES_INDIVIDUAL_FILES = sorted(glob.glob(os.path.join(BASE_DIR, "99_Sbox/annual_analysis_2025/*.txt"))) + \
                         sorted(glob.glob(os.path.join(BASE_DIR, "99_Sbox/売上データ/202[4-6]*_layout.txt")))

CUSTOMERS_JSON = os.path.join(BASE_DIR, "00_システム/devtools/route_report_tool/backend/customers.json")
MONTHLY_JSON = os.path.join(SCRIPT_DIR, "salon_monthly_sales.json")

if os.path.exists(CUSTOMERS_JSON):
    with open(CUSTOMERS_JSON, "r", encoding="utf-8") as f:
        customers_map = json.load(f)
else:
    customers_map = {}
all_salons = [{"name": s, "day": d} for d, ss in customers_map.items() for s in ss]

def parse_layout_file(filepath: str) -> list[dict]:
    """layout.txt ファイルから「摘要（小計）」行を直接抽出する"""
    records = []
    try:
        with open(filepath, "r", encoding="utf-8") as f: lines = f.readlines()
        
        # ファイルから対象月を特定 (ファイル冒頭の期間指定 2025/12/21 ～ 2026/01/20 等)
        target_month = None
        for line in lines[:50]:
            m = re.search(r'【\s*(\d{4}/\d{2}/\d{2})\s*～\s*(\d{4}/\d{2}/\d{2})\s*】', line)
            if m:
                # 終了日の月をそのファイルの「計上月」とする
                target_month = get_report_month(m.group(2))
                break
        
        if not target_month:
            # ファイル名から推測
            m = re.search(r'(\d{4})年(\d+)月', os.path.basename(filepath))
            target_month = f"{m.group(1)}-{int(m.group(2)):02d}" if m else "unknown"

        cur_c = None
        for line in lines:
            line = line.replace("\x0c", "").replace("\n", "")
            # サロンヘッダー (コード と サロン名)
            h_match = re.search(r'^\s{0,10}(\d{5,10})\s+(.+?)\s{2,}[７7][６6][１1]', line)
            if h_match:
                cur_c = h_match.group(2).strip()
                continue
            
            # 摘要（小計）行: 摘要 [Code]:[Name] [Sales] [Cost] [Profit]
            # 例: 摘要     2982678:BS luxe hair design 55,611 46,390 9,221
            abst_match = re.search(r'摘要\s+([\d:]+)?(.+?)\s+([-\d,]+)\s+([-\d,]+)\s+([-\d,]+)', line)
            if abst_match and cur_c:
                s_val, c_val, p_val = safe_int(abst_match.group(3)), safe_int(abst_match.group(4)), safe_int(abst_match.group(5))
                records.append({
                    "salon_name": cur_c,
                    "month": target_month,
                    "sales": s_val,
                    "cost": c_val,
                    "profit": p_val
                })
                # 同じサロン内で複数の摘要行がある場合があるため、集計時に合算する
    except Exception as e: print(f"  Err {filepath}: {e}")
    return records

def run_parsing():
    print("売上統合フェーズ開始 (摘要集計モード)...")
    monthly = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "salons": {}}
    
    # 月ごとに1つの layout.txt を選ぶ
    month_to_file = {}
    for f in SALES_INDIVIDUAL_FILES:
        m = re.search(r'(\d{4})年(\d+)月', os.path.basename(f))
        if m:
            target = f"{m.group(1)}-{int(m.group(2)):02d}"
            if target not in month_to_file or "_layout.txt" in f:
                month_to_file[target] = f

    for month, f in month_to_file.items():
        print(f"  {month}度のソース: {os.path.basename(f)}")
        recs = parse_layout_file(f)
        for r in recs:
            c = r["salon_name"]
            matched = next((s for s in all_salons if normalize(s["name"]) == normalize(c)), None)
            sname = matched["name"] if matched else c
            
            if sname not in monthly["salons"]: monthly["salons"][sname] = {}
            if month not in monthly["salons"][sname]: monthly["salons"][sname][month] = {"sales": 0, "cost": 0, "profit": 0, "details": []}
            m = monthly["salons"][sname][month]
            m["sales"] += r["sales"]; m["profit"] += r["profit"]; m["cost"] += r["cost"]

    with open(MONTHLY_JSON, "w", encoding="utf-8") as f: json.dump(monthly, f, ensure_ascii=False, indent=2)
    
    # 1月度の検証
    total_jan = sum(sal.get("2026-01", {}).get("sales", 0) for sal in monthly["salons"].values())
    profit_jan = sum(sal.get("2026-01", {}).get("profit", 0) for sal in monthly["salons"].values())
    print(f"🎉 2026-01 総売上: {total_jan:,}円")
    print(f"🎉 2026-01 総利益: {profit_jan:,}円")
    return True

if __name__ == "__main__":
    run_parsing()
