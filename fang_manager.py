"""
================================================
FANG+ 管理モジュール v2
================================================
変更点:
  - Yahoo!ファイナンスのスクレイピングを強化
  - 複数の取得方法を試みる
  - FutureWarning を修正
================================================
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
from datetime import datetime

# ================================================
# 設定
# ================================================

FANG_FUND_CODE = "04311181"
FANG_CSV_PATH = "./portfolio_data/fang_purchases.csv"
COLUMNS = ["購入日", "投資額", "取得単価", "口数", "メモ"]


# ================================================
# 1. Yahoo!ファイナンスから基準価額を自動取得
# ================================================

def get_fang_current_price(debug: bool = False) -> float:
    """
    Yahoo!ファイナンスから FANG+ の現在基準価額を取得する。
    クラス名 'PriceBoard__price__1V0k' を主要セレクターとして使用。
    失敗時は 0.0 を返す。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
        "Referer": "https://finance.yahoo.co.jp/",
    }

    url = f"https://finance.yahoo.co.jp/quote/{FANG_FUND_CODE}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        if debug:
            print(f"[DEBUG] Status: {r.status_code}")

        # ----------------------------------------
        # 方法1（最優先）: 確認済みクラス名で直接取得
        # デバッグで特定: class='PriceBoard__price__1V0k'
        # ----------------------------------------
        tag = soup.find("span", class_="PriceBoard__price__1V0k")
        if tag:
            val_str = tag.get_text(strip=True).replace(",", "")
            val = float(val_str)
            if debug:
                print(f"[DEBUG] 方法1（PriceBoard__price__1V0k）: {val:,.0f}円")
            return val

        # ----------------------------------------
        # 方法2: クラス名が変わった場合のフォールバック
        # 'PriceBoard__price' を含む span を探す
        # ----------------------------------------
        for span in soup.find_all("span"):
            classes = span.get("class", [])
            if any("PriceBoard__price" in c for c in classes):
                val_str = span.get_text(strip=True).replace(",", "")
                if val_str.replace(".", "").isdigit():
                    val = float(val_str)
                    if 10000 <= val <= 500000:
                        if debug:
                            print(f"[DEBUG] 方法2（PriceBoard__price 部分一致）: {val:,.0f}円")
                        return val

        # ----------------------------------------
        # 方法3: StyledNumber__value クラスから取得
        # デバッグで確認: [17] class=['StyledNumber__value__3rXW'] text='73,603'
        # ----------------------------------------
        for span in soup.find_all("span"):
            classes = span.get("class", [])
            if any("StyledNumber__value" in c for c in classes):
                val_str = span.get_text(strip=True).replace(",", "")
                if val_str.replace(".", "").isdigit():
                    val = float(val_str)
                    if 10000 <= val <= 500000:
                        if debug:
                            print(f"[DEBUG] 方法3（StyledNumber__value）: {val:,.0f}円")
                        return val

        # ----------------------------------------
        # 方法4: テキスト全体から正規表現（最終手段）
        # ----------------------------------------
        text = soup.get_text()
        if debug:
            print(f"[DEBUG] テキスト先頭300文字:\n{text[:300]}")
        candidates = re.findall(r'\b(\d{2,3},\d{3})\b', text[:3000])
        if debug:
            print(f"[DEBUG] 価格候補: {candidates[:10]}")
        for c in candidates:
            val = float(c.replace(",", ""))
            if 10000 <= val <= 500000:
                if debug:
                    print(f"[DEBUG] 方法4（正規表現）: {val:,.0f}円")
                return val

    except requests.exceptions.RequestException as e:
        if debug:
            print(f"[DEBUG] 接続エラー: {e}")
    except Exception as e:
        if debug:
            print(f"[DEBUG] 解析エラー: {e}")

    if debug:
        print("[DEBUG] 全ての方法で取得失敗")
    return 0.0


# ================================================
# 2. 購入履歴 CSV の読み書き
# ================================================

def load_fang_purchases() -> pd.DataFrame:
    """fang_purchases.csv を読み込む"""
    os.makedirs(os.path.dirname(FANG_CSV_PATH), exist_ok=True)

    if not os.path.exists(FANG_CSV_PATH):
        return pd.DataFrame(columns=COLUMNS)

    df = pd.read_csv(FANG_CSV_PATH, encoding="utf-8-sig")
    df["購入日"] = pd.to_datetime(df["購入日"]).dt.strftime("%Y-%m-%d")
    df["投資額"] = pd.to_numeric(df["投資額"], errors="coerce").fillna(0)
    df["取得単価"] = pd.to_numeric(df["取得単価"], errors="coerce").fillna(0)
    df["口数"] = pd.to_numeric(df["口数"], errors="coerce").fillna(0)
    return df


def add_fang_purchase(
    purchase_date: str,
    investment_amount: float,
    purchase_price: float,
    memo: str = ""
) -> pd.DataFrame:
    """購入履歴に 1 件追加して CSV を保存する"""
    if purchase_price <= 0:
        raise ValueError("取得単価は 0 より大きい値を入力してください。")
    if investment_amount <= 0:
        raise ValueError("投資額は 0 より大きい値を入力してください。")

    units = investment_amount / purchase_price

    df = load_fang_purchases()

    new_row = pd.DataFrame([{
        "購入日": purchase_date,
        "投資額": float(investment_amount),
        "取得単価": float(purchase_price),
        "口数": round(units, 6),
        "メモ": memo
    }])

    # FutureWarning 対策: 空 DataFrame との concat を回避
    if df.empty:
        df = new_row.copy()
    else:
        df = pd.concat([df, new_row], ignore_index=True)

    df.to_csv(FANG_CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"✅ 購入履歴を追加: {purchase_date}  ¥{investment_amount:,.0f}  @{purchase_price:,.0f}円  {units:.4f}口")
    return df


def delete_last_purchase() -> pd.DataFrame:
    """最後の購入履歴を削除する（誤入力の訂正用）"""
    df = load_fang_purchases()
    if df.empty:
        print("⚠️ 購入履歴がありません。")
        return df
    removed = df.iloc[-1]
    df = df.iloc[:-1]
    df.to_csv(FANG_CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"🗑️ 削除: {removed['購入日']}  ¥{removed['投資額']:,.0f}  @{removed['取得単価']:,.0f}円")
    return df


# ================================================
# 3. サマリー計算
# ================================================

def calc_fang_summary(current_price: float = 0.0) -> dict:
    """加重平均取得単価・評価損益などを計算する"""
    df = load_fang_purchases()

    if df.empty:
        return {
            "total_investment": 0, "total_units": 0, "avg_cost": 0,
            "current_price": current_price, "current_value": 0,
            "profit": 0, "profit_pct": 0, "purchases": df,
            "price_source": "unavailable"
        }

    total_investment = df["投資額"].sum()
    total_units = df["口数"].sum()
    avg_cost = total_investment / total_units if total_units > 0 else 0

    price_source = "manual"
    if current_price <= 0:
        current_price = get_fang_current_price()
        price_source = "yahoo" if current_price > 0 else "unavailable"

    if current_price > 0 and avg_cost > 0:
        current_value = total_investment * (current_price / avg_cost)
        profit = current_value - total_investment
        profit_pct = profit / total_investment * 100
    else:
        current_value = total_investment
        profit = 0
        profit_pct = 0

    return {
        "total_investment": total_investment, "total_units": total_units,
        "avg_cost": avg_cost, "current_price": current_price,
        "current_value": current_value, "profit": profit,
        "profit_pct": profit_pct, "purchases": df, "price_source": price_source
    }


# ================================================
# 4. 単体テスト
# ================================================

if __name__ == "__main__":
    print("=" * 60)
    print("FANG+ 管理モジュール v2 テスト")
    print("=" * 60)

    # --- 現在価格をデバッグモードで取得 ---
    print("\n📡 Yahoo!ファイナンスから基準価額を取得中（デバッグあり）...")
    price = get_fang_current_price(debug=True)
    if price > 0:
        print(f"\n✅ 現在の基準価額: {price:,.0f}円")
    else:
        print("\n⚠️ 自動取得失敗。スクリーンショットの値（73,603円）で手動テスト:")
        price = 73603  # 手動フォールバック

    # --- サマリー ---
    print("\n📊 サマリー計算...")
    summary = calc_fang_summary(current_price=price)

    if summary["total_investment"] > 0:
        print(f"\n【FANG+ サマリー】")
        print(f"  合計投資額    : ¥{summary['total_investment']:>12,.0f}")
        print(f"  合計口数      : {summary['total_units']:>14.4f} 口")
        print(f"  加重平均単価  : ¥{summary['avg_cost']:>12,.0f}")
        print(f"  現在基準価額  : ¥{summary['current_price']:>12,.0f}  （{summary['price_source']}）")
        print(f"  評価額        : ¥{summary['current_value']:>12,.0f}")
        print(f"  評価損益      : ¥{summary['profit']:>+12,.0f}  （{summary['profit_pct']:+.2f}%）")
        print(f"\n【購入履歴】")
        print(summary["purchases"].to_string(index=False))
    else:
        print("  購入履歴なし。")
