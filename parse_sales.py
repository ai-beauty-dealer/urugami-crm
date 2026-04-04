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
    """
    納品日から『計上月』を判定する
    - 20日締めサロン: ピーブランズヘア大野城, ピーブランズヘア春日, Pブランズ姪浜, 出張理美容
        -> 21日以降なら翌月扱い
    - 他のサロン: 全て末締め
        -> 当月扱い
    """
    SALONS_20th = ["ピーブランズヘア大野城", "ピーブランズヘア春日", "Pブランズ姪浜", "出張理美容"]

    try:
        dt = datetime.strptime(date_str, "%Y/%m/%d")
        year = dt.year
        month = dt.month
        
        # 20日締めサロンの場合のみ、21日以降を翌月に送る
        if salon_name in SALONS_20th:
            if dt.day >= 21:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
        
        return f"{year}-{month:02d}"
    except:
        # パースできない場合はそのままYYYY-MMを返す試行
        if len(date_str) >= 7: return date_str[:7].replace("/", "-")
        return "unknown"

# ===== パス設定 =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../.."))  # 2nd-Brain/
SALES_TXT_GLOB = os.path.join(BASE_DIR, "99_Sbox/annual_analysis_2025/*.txt")
SALES_2026_01 = os.path.join(BASE_DIR, "99_Sbox/売上データ/2026年1月度売上.txt")
SALES_2026_02_CSV = os.path.join(BASE_DIR, "99_Sbox/売上データ/2026年2月度売上.csv")
SALES_2026_03_CSV = os.path.join(BASE_DIR, "99_Sbox/売上データ/2026年3月度売上.csv")
CUSTOMERS_JSON = os.path.join(BASE_DIR, "00_システム/devtools/route_report_tool/backend/customers.json")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "salon_products.json")

# ===== customers.json 読み込み =====
with open(CUSTOMERS_JSON, "r", encoding="utf-8") as f:
    customers_map = json.load(f)

all_salons = []
for day, salons in customers_map.items():
    for salon in salons:
        all_salons.append({"name": salon, "day": day})

def normalize(text: str) -> str:
    if not text: return ""
    result = ""
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E: result += chr(code - 0xFEE0)
        elif ch == "　": result += " "
        else: result += ch
    result = unicodedata.normalize("NFKC", result)
    result = re.sub(r"[''ʼ\u2018\u2019\u02BC]", "'", result)
    result = re.sub(r"\s+", " ", result).strip().upper()
    return result

MANUAL_MAPPING = {
    "FATE": "フェイト", "Ｆａｔｅ": "フェイト", "Fate": "フェイト",
    "リンクコネクト株式会社": "スコップ", "リンクコネクト": "スコップ",
    "STANDARD": "スタンダード", "Ｓｔａｎｄａｒｄ": "スタンダード", "スタンダード": "スタンダード",
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
    "Oneness+": "ワンネス", "Oneness": "ワンネス", "ひとみ美容室": "ひとみ美容室",
    "plant": "プラント", "Plant": "プラント",
    "出張理美容協会": "出張理美容", "出張理美容": "出張理美容",
    "Hairdesign ａｔｔｒｉｃｏ": "アトリコ", "Hairdesign attrico": "アトリコ", "attrico": "アトリコ",
    "７Ｖｅｌｖｅｔ": "セブンベルベット", "7Velvet": "セブンベルベット",
    "ｃｏｓｙ      Ｖｅｌｖｅｔ": "コージーベルベット", "ｃｏｓｙ    Ｖｅｌｖｅｔ": "コージーベルベット",
    "cosy Velvet": "コージーベルベット", "Cosy velvet": "コージーベルベット",
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
    "シーサイド": "シーサイド", "KUKUI": "ククイ", "epice": "エピス", "Epice": "エピス",
    "epis": "エピス", "ATOMIK": "アトミック", "Ａｔｏｍｉｋ": "アトミック",
    "Hair make Ｌｉｌｙ": "リリー", "Hair make Lily": "リリー", "Lilly": "リリー",
    "ホロホロｈａｉｒ": "ホロホロヘアー", "ホロホロhair": "ホロホロヘアー", "ホロホロヘアー": "ホロホロヘアー",
    "Ｓａｌｏｎ     ＣＯＣＯ": "サロンココ", "Salon COCO": "サロンココ",
    "Ａｍｂｅｒ．": "アンバー", "Amber.": "アンバー", "luxe hair design": "リュクス", "Luxe": "リュクス",
    "Ｃｌａｒｋｅ'hair studio": "クラーク", "Clarke'hair studio": "クラーク", "Clarke": "クラーク",
    "ミツアミ堂": "ミツアミ堂", "ＬＡＣＯ    ｈａｉｒ": "ラコヘアー", "LACO hair": "ラコヘアー",
    "Ｖｅｌｖｅｔ ｈａｉｒ 千早": "ベルベット千早", "Velvet hair 千早": "ベルベット千早", "Velvet 千早": "ベルベット千早",
    "(株)田菱 ＰＲＡＹＥＲ": "プレアー", "田菱 PRAYER": "プレアー",
    "ＳＴＲＡＷＢＥＲＲＹ": "ストロベリー", "STRAWBERRY": "ストロベリー",
    "SiERRA LAXZE": "シエララグゼ", "sierra laxze": "シエララグゼ", "シエララグゼ": "シエララグゼ",
    "Roble": "ロブレ", "ロブレ": "ロブレ",
    "STYLEE produce by Hair Bloom": "スタイリー", "THREE...HAKATA bleach": "スリー ブリーチ",
    "Private salon Bellreage": "ベルリアージュ", "Private salon  Bellreage": "ベルリアージュ",
    "X Riche hair": "リッシュヘアー", "ricore'": "リコラ", "Ｒｉｃｏｒｅ'": "リコラ",
    "AtomiK稲榮": "アトミック", "AtomiK稲栄": "アトミック",
    "永田      竜一": "永田 竜一", "永田    竜一": "永田 竜一", "永田　竜一": "永田 竜一",
}

def find_matching_salon(customer_name: str, all_salons: list):
    if customer_name in MANUAL_MAPPING:
        target_name = MANUAL_MAPPING[customer_name]
        for salon in all_salons:
            if salon["name"] == target_name: return salon
        # マスタにない場合でも、マッピングがあるならその名前で「その他」扱いとして返す
        return {"name": target_name, "day": "その他"}
    
    norm_cust = normalize(customer_name)
    for raw_key, target_name in MANUAL_MAPPING.items():
        if normalize(raw_key) == norm_cust:
            for salon in all_salons:
                if salon["name"] == target_name: return salon
            return {"name": target_name, "day": "その他"}
    
    best_match = None
    best_score = 0
    for salon in all_salons:
        norm_salon = normalize(salon["name"])
        if norm_cust == norm_salon: return salon
        score = 0
        if norm_salon in norm_cust or norm_cust in norm_salon:
            if len(norm_salon) >= 3: score = len(norm_salon)
        if score == 0:
            cust_words = set(norm_cust.split())
            salon_words = set(norm_salon.split())
            common = cust_words & salon_words
            if common: score = len(" ".join(common))
        if score > best_score:
            best_score = score
            best_match = salon
    if best_score >= 3: return best_match
    return None

def parse_sales_csv(filepath: str) -> list[dict]:
    records = []
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, "r", encoding="cp932", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 22: continue
                # 0:得意先ｺｰﾄﾞ, 1:得 意 先 名, 5:納品日(YYYY/MM/DD), 17:商品ｺｰﾄﾞ, 18:商品名, 21:販売単価
                date_str = row[5].strip()
                customer_name = row[1].strip()
                product_code = row[17].strip()
                product_name = row[18].strip()
                qty = safe_int(row[20])
                unit_price = safe_int(row[21])
                total_sales = safe_int(row[23])
                # 26列目:在庫単価 (Stock Unit Price)
                unit_cost = safe_float(row[26])
                # ユーザー要求: 利益 = 売上 - (在庫単価 * 数量) で計算
                total_cost = int(unit_cost * qty)
                total_profit = total_sales - total_cost
                
                if not re.match(r'\d{4}/\d{2}/\d{2}', date_str): continue
                if customer_name in ("得 意 先 名", "得意先名", "売 上 一 覧 表"): continue
                if not product_code or not product_name: continue
                
                # サンプル品(単価0)も購入履歴として重要なので含める
                records.append({
                    "customer_name": customer_name, "delivery_date": date_str,
                    "product_code": product_code, "product_name": product_name,
                    "qty": qty, "unit_price": unit_price, "total_sales": total_sales,
                    "unit_cost": unit_cost, "total_profit": total_profit
                })
    except Exception as e: print(f"  Warning: Error parsing CSV {filepath}: {e}")
    return records

def parse_sales_file(filepath: str) -> list[dict]:
    records = []
    with open(filepath, "r", encoding="utf-8") as f: lines = f.readlines()
    current_customer = None
    current_delivery_date = None
    for line in lines:
        if "\x0c" in line: line = line.replace("\x0c", "")
        header_match = re.search(r'^\s{0,10}\d{5,10}\s+(.+?)\s{2,}[７7][６6][１1]\s+\S+\s+(\d{4}/\d{2}/\d{2})', line)
        if header_match:
            customer_raw = re.sub(r"\s+$", "", header_match.group(1).strip())
            code_match = re.match(r'^\s*(\d{5,10})', line)
            if code_match and code_match.group(1).startswith('99'):
                current_customer = None
                current_delivery_date = None
                continue
            current_customer = customer_raw
            current_delivery_date = header_match.group(2)
            continue
        # 売上行の解析 (コード, 名称, 数量, 単価, 金額, 在庫単価, 原価, 粗利)
        # ※**記号やスペースの変動に対応
        detail_match = re.search(r'売\s+上\s+(\d+)\s+(.+?)\s+(\d+)\s+([\d,]+(?:\s+\*\*)?)\s+([\d,]+)\s+([\d,.]+)\s+([\d,]+)\s+([\d,]+)', line)
        if detail_match and current_customer:
            product_code = detail_match.group(1).strip()
            product_name = re.sub(r"^\*\s*", "", detail_match.group(2).strip())
            product_name = re.sub(r"\s{2,}\d+$", "", product_name).strip()
            
            qty = safe_int(detail_match.group(3))
            unit_price = safe_int(detail_match.group(4))
            total_sales = safe_int(detail_match.group(5))
            unit_cost = safe_float(detail_match.group(6))  # 在庫単価
            # ユーザー要求: 利益 = 売上 - (在庫単価 * 数量) で計算
            total_cost = int(unit_cost * qty)
            total_profit = total_sales - total_cost
            
            if (unit_price == 0 and total_sales == 0) or product_code == "9999001": continue
            
            records.append({
                "customer_name": current_customer, "delivery_date": current_delivery_date,
                "product_code": product_code, "product_name": product_name, 
                "qty": qty, "unit_price": unit_price, "total_sales": total_sales,
                "unit_cost": unit_cost, "total_profit": total_profit
            })
            continue

        # 伝引（値引き）の解析
        discount_match = re.search(r'^\s+伝引\(.+?\)\s+(\d+)\s+[-\*]*\s+([-\d,]+)', line)
        if discount_match and current_customer:
            discount_val = safe_int(discount_match.group(2))
            records.append({
                "customer_name": current_customer, "delivery_date": current_delivery_date,
                "product_code": "DISCOUNT", "product_name": "伝引",
                "qty": 1, "unit_price": discount_val, "total_sales": discount_val,
                "unit_cost": 0, "total_profit": discount_val # 伝引はそのまま粗利（マイナス）
            })
    return records

def main():
    print("売上ファイルを解析中...")
    all_records = []
    txt_files = sorted(glob.glob(SALES_TXT_GLOB))
    for filepath in txt_files:
        records = parse_sales_file(filepath)
        all_records.extend(records)
        print(f"  {os.path.basename(filepath)}: {len(records)} 件")
    if os.path.exists(SALES_2026_01):
        records = parse_sales_file(SALES_2026_01)
        all_records.extend(records)
        print(f"  {os.path.basename(SALES_2026_01)}: {len(records)} 件")
    if os.path.exists(SALES_2026_02_CSV):
        records = parse_sales_csv(SALES_2026_02_CSV)
        all_records.extend(records)
        print(f"  {os.path.basename(SALES_2026_02_CSV)}: {len(records)} 件")
    if os.path.exists(SALES_2026_03_CSV):
        records = parse_sales_csv(SALES_2026_03_CSV)
        all_records.extend(records)
        print(f"  {os.path.basename(SALES_2026_03_CSV)}: {len(records)} 件")
    print(f"\n合計 {len(all_records)} 件の取引レコードを解析")
    
    # 1. 商品別集計用のデータ作成
    customer_products = defaultdict(dict)
    for rec in all_records:
        cname = rec["customer_name"]
        pcode = rec["product_code"]
        pname = rec["product_name"]
        price = rec["unit_price"]
        total_sales = rec.get("total_sales", price)
        unit_cost = rec.get("unit_cost", 0)
        date_str = rec["delivery_date"]
        
        # 最新の原価も保持
        if pcode not in customer_products[cname]:
            customer_products[cname][pcode] = {
                "product_code": pcode, "product_name": pname, 
                "unit_price": price, "unit_cost": unit_cost, "last_order_date": date_str
            }
        else:
            existing = customer_products[cname][pcode]
            try:
                if datetime.strptime(date_str, "%Y/%m/%d") > datetime.strptime(existing["last_order_date"], "%Y/%m/%d"):
                    existing["last_order_date"] = date_str
                    existing["unit_price"] = price
                    existing["unit_cost"] = unit_cost
            except: pass
    
    salon_data = {day: {} for day in customers_map.keys()}
    if "その他" not in salon_data: salon_data["その他"] = {}
    for cust_raw, products in customer_products.items():
        matched = find_matching_salon(cust_raw, all_salons)
        if matched:
            salon_name, day = matched["name"], matched["day"]
        else:
            salon_name, day = cust_raw, "その他"
            
        if salon_name not in salon_data[day]: salon_data[day][salon_name] = []
        existing_codes = {p["product_code"] for p in salon_data[day][salon_name]}
        for prod in products.values():
            if prod["product_code"] not in existing_codes: salon_data[day][salon_name].append(prod)
            else:
                for ep in salon_data[day][salon_name]:
                    if ep["product_code"] == prod["product_code"]:
                        try:
                            if datetime.strptime(prod["last_order_date"], "%Y/%m/%d") > datetime.strptime(ep["last_order_date"], "%Y/%m/%d"):
                                ep.update(prod)
                        except: pass
    
    for day in salon_data:
        for salon in salon_data[day]:
            salon_data[day][salon].sort(key=lambda x: x["last_order_date"], reverse=True)
    
    output = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "customers": customers_map, "salons": salon_data}
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f: json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ 商品詳細出力完了: {OUTPUT_JSON}")

    # 2. 月次推移集計用のデータ作成
    monthly_output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "salons": {}
    }
    
    unmatched_set = set() # 表示用
    for rec in all_records:
        cust_raw = rec["customer_name"]
        matched = find_matching_salon(cust_raw, all_salons)
        
        if matched:
            salon_name = matched["name"]
        else:
            # マッチしなかった場合、送り状の名前をそのまま使い「その他」の訪問曜日とする
            salon_name = cust_raw
            unmatched_set.add(cust_raw)
        
        month_key = get_report_month(rec["delivery_date"], salon_name)
        
        if salon_name not in monthly_output["salons"]:
            monthly_output["salons"][salon_name] = {}
        
        if month_key not in monthly_output["salons"][salon_name]:
            monthly_output["salons"][salon_name][month_key] = {
                "sales": 0, "cost": 0, "profit": 0, "details": []
            }
        
        m_data = monthly_output["salons"][salon_name][month_key]
        sales = rec.get("total_sales", 0)
        profit = rec.get("total_profit", 0)
        qty = rec.get("qty", 1)
        pname = rec["product_name"]
        
        found_detail = False
        for detail in m_data["details"]:
            if detail["name"] == pname:
                detail["qty"] += qty
                detail["sales"] += sales
                found_detail = True
                break
        
        if not found_detail:
            m_data["details"].append({"name": pname, "qty": qty, "sales": sales})
        
        # 実データに基づいた集計 (売上と利益を直接加算)
        m_data["sales"] += sales
        m_data["profit"] += profit
        m_data["cost"] = m_data["sales"] - m_data["profit"]

    # 異常値チェック (伝引を除く負の利益がないか)
    negative_profit_salons = []
    for sname, months in monthly_output["salons"].items():
        for mkey, data in months.items():
            if data["profit"] < 0 and data["sales"] > 0:
                negative_profit_salons.append(f"{sname} ({mkey}): 利益={data['profit']} (売上={data['sales']})")
    
    if negative_profit_salons:
        print("\n⚠️  注意: 売上があるのに利益がマイナスの月があります（原価設定の確認を推奨）:")
        for msg in negative_profit_salons[:10]:
            print(f"  - {msg}")

    MONTHLY_JSON = os.path.join(SCRIPT_DIR, "salon_monthly_sales.json")
    with open(MONTHLY_JSON, "w", encoding="utf-8") as f:
        json.dump(monthly_output, f, ensure_ascii=False, indent=2)
    print(f"✅ 月次集計出力完了: {MONTHLY_JSON}")

    # ===== デプロイ用同期 =====
    DEPLOY_DIR = os.path.join(SCRIPT_DIR, ".deploy")
    if os.path.exists(DEPLOY_DIR):
        import shutil
        shutil.copy2(os.path.join(SCRIPT_DIR, "index.html"), os.path.join(DEPLOY_DIR, "index.html"))
        shutil.copy2(OUTPUT_JSON, os.path.join(DEPLOY_DIR, "salon_products.json"))
        shutil.copy2(MONTHLY_JSON, os.path.join(DEPLOY_DIR, "salon_monthly_sales.json"))
        print(f"🚀 .deploy への同期完了 (HTML + JSON)")

    total_salons = sum(len(s) for s in salon_data.values())
    print(f"\n解析結果 summary:")
    print(f"  マッチしたサロン数: {total_salons}")
    if unmatched_set:
        print(f"  ⚠️  「その他」として自動計上した得意先名（{len(unmatched_set)}件）:")
        for name in sorted(list(unmatched_set)):
            print(f"    - {name}")

if __name__ == "__main__":
    main()
