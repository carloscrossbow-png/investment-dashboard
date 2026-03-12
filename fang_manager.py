"""
================================================
FANG+ 管理モジュール
================================================
機能:
  1. Yahoo!ファイナンスから基準価額を自動取得
  2. fang_purchases.csv で購入履歴を管理
  3. 加重平均取得単価を自動計算

iFreeNEXT FANG+インデックス
  Yahoo!ファイナンスコード: 04311181
  ISIN: JP90C000K379
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

FANG_FUND_CODE = "04311181"  # iFreeNEXT FANG+インデックス

# CSV保存先（Google Sheets連携がない場合のローカルパス）
# Streamlit Cloud上ではGoogle Sheetsを使うこと
LOCAL_CSV_PATH = os.path.expanduser(
    "~/PyCharmMiscProject/株スクリーニング完成版/portfolio_data/fang_purchases.csv"
)

COLUMNS = ["購入日", "投資額", "取得単価", "口数", "メモ"]


# ================================================
# 1. Yahoo!ファイナンスから基準価額を取得
# ================================================

def get_fang_current_price(debug: bool = False) -> float:
    """
    Yahoo!ファイナンスから iFreeNEXT FANG+ の現在基準価額を取得。
    失敗時は 0.0 を返す。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }

    # 方法1: 投資信託ページ
    url1 = f"https://finance.yahoo.co.jp/quote/{FANG_FUND_CODE}"
    try:
        r1 = requests.get(url1, headers=headers, timeout=15)
        r1.raise_for_status()
        soup1 = BeautifulSoup(r1.text, "html.parser")

        # クラス名で価格要素を探す
        for cls in ["_3rXWJKZF", "PriceBoard__price__1V0k", "price"]:
            el = soup1.find(class_=cls)
            if el:
                text = el.get_text(strip=True).replace(",", "").replace("円", "")
                try:
                    val = float(text)
                    if 10000 <= val <= 500000:
                        if debug:
                            print(f"[DEBUG] クラス '{cls}' で取得: {val:,.0f}円")
                        return val
                except ValueError:
                    pass

        # フォールバック: テキスト全体から数値パターンで抽出
        text_all = soup1.get_text()
        matches = re.findall(r'(\d{2,3},\d{3})', text_all[:5000])
        for m in matches:
            val = float(m.replace(",", ""))
            if 10000 <= val <= 500000:
                if debug:
                    print(f"[DEBUG] テキスト抽出で取得: {val:,.0f}円")
                return val

    except requests.exceptions.RequestException as e:
        if debug:
            print(f"[DEBUG] 方法1エラー: {e}")

    # 方法2: 投資信託協会
    url2 = "https://toushin-lib.fwg.ne.jp/FdsWeb/FDST030000?isinCd=JP90C000K379"
    try:
        r2 = requests.get(url2, headers=headers, timeout=15)
        r2.raise_for_status()
        soup2 = BeautifulSoup(r2.text, "html.parser")
        text2 = soup2.get_text()
        candidates = re.findall(r'\b(\d{2,3},\d{3})\b', text2[:3000])
        for c in candidates:
            val = float(c.replace(",", ""))
            if 10000 <= val <= 500000:
                if debug:
                    print(f"[DEBUG] 投資信託協会で取得: {val:,.0f}円")
                return val
    except requests.exceptions.RequestException as e:
        if debug:
            print(f"[DEBUG] 方法2エラー: {e}")

    if debug:
        print("[DEBUG] 全ての方法で取得失敗")
    return 0.0


# ================================================
# 2. 購入履歴 CSV 管理
# ================================================

def _resolve_csv_path(csv_path: str = "") -> str:
    """CSVパスを決定（引数 > ローカルデフォルト）"""
    if csv_path:
        return csv_path
    return LOCAL_CSV_PATH


def load_fang_purchases(csv_path: str = "") -> pd.DataFrame:
    """購入履歴CSVを読み込む。存在しない場合は空のDataFrameを返す。"""
    path = _resolve_csv_path(csv_path)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
            # 列が不足している場合は補完
            for col in COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            return df[COLUMNS]
        except Exception:
            pass
    return pd.DataFrame(columns=COLUMNS)


def add_fang_purchase(
    purchase_date: str,
    amount: float,
    unit_price: float,
    memo: str = "",
    csv_path: str = "",
) -> pd.DataFrame:
    """
    購入履歴を追加して保存する。
    purchase_date: "YYYY-MM-DD"
    amount:        投資額（円）
    unit_price:    取得単価（基準価額）
    memo:          備考（任意）
    """
    df = load_fang_purchases(csv_path)
    units = round(amount / unit_price, 6) if unit_price > 0 else 0.0
    new_row = pd.DataFrame([{
        "購入日":   purchase_date,
        "投資額":   int(amount),
        "取得単価": int(unit_price),
        "口数":     units,
        "メモ":     memo,
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    path = _resolve_csv_path(csv_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


# ================================================
# 3. サマリー計算
# ================================================

def calc_fang_summary(
    current_price: float = 0.0,
    csv_path: str = "",
) -> dict:
    """
    FANG+のポートフォリオサマリーを返す。

    Returns:
        {
          "total_investment": 合計投資額,
          "total_units":      合計口数,
          "avg_cost":         加重平均取得単価,
          "current_price":    現在基準価額,
          "current_value":    評価額,
          "profit":           評価損益,
          "profit_pct":       評価損益率（%）,
          "price_source":     "自動取得" or "手動入力" or "取得失敗",
          "purchases":        購入履歴DataFrame,
        }
    """
    df = load_fang_purchases(csv_path)

    result = {
        "total_investment": 0.0,
        "total_units":      0.0,
        "avg_cost":         0.0,
        "current_price":    0.0,
        "current_value":    0.0,
        "profit":           0.0,
        "profit_pct":       0.0,
        "price_source":     "取得失敗",
        "purchases":        df,
    }

    if df.empty:
        return result

    # 集計
    total_investment = float(df["投資額"].sum())
    total_units      = float(df["口数"].sum())
    avg_cost         = total_investment / total_units if total_units > 0 else 0.0

    result["total_investment"] = total_investment
    result["total_units"]      = total_units
    result["avg_cost"]         = avg_cost

    # 現在価格
    if current_price > 0:
        price        = current_price
        price_source = "手動入力"
    else:
        price        = get_fang_current_price()
        price_source = "自動取得" if price > 0 else "取得失敗"

    if price > 0:
        current_value = total_units * price
        profit        = current_value - total_investment
        profit_pct    = (profit / total_investment * 100) if total_investment > 0 else 0.0
    else:
        current_value = total_investment  # 取得失敗時は投資額で代替
        profit        = 0.0
        profit_pct    = 0.0

    result["current_price"]  = price
    result["current_value"]  = current_value
    result["profit"]         = profit
    result["profit_pct"]     = profit_pct
    result["price_source"]   = price_source

    return result


# ================================================
# 単体テスト（python fang_manager.py で実行）
# ================================================

if __name__ == "__main__":
    print("=" * 60)
    print("FANG+ 管理モジュール テスト")
    print("=" * 60)

    # 購入履歴を追加する場合はコメントを外して実行
    # add_fang_purchase("2026-01-07", 100000, 84919, "初回購入 NISA成長投資枠")

    print("\n📡 Yahoo!ファイナンスから基準価額を取得中...")
    price = get_fang_current_price(debug=True)
    if price > 0:
        print(f"  現在の基準価額: {price:,.0f}円")
    else:
        print("  ⚠️ 取得失敗（手動で入力してください）")

    print("\n📊 ポートフォリオサマリー計算中...")
    summary = calc_fang_summary()

    if summary["total_investment"] > 0:
        print(f"\n【FANG+ サマリー】")
        print(f"  合計投資額  : ¥{summary['total_investment']:>12,.0f}")
        print(f"  合計口数    : {summary['total_units']:>14.4f} 口")
        print(f"  加重平均単価: ¥{summary['avg_cost']:>12,.0f}")
        print(f"  現在基準価額: ¥{summary['current_price']:>12,.0f}  ({summary['price_source']})")
        print(f"  評価額      : ¥{summary['current_value']:>12,.0f}")
        print(f"  評価損益    : ¥{summary['profit']:>+12,.0f}  ({summary['profit_pct']:+.2f}%)")
        print(f"\n【購入履歴】")
        print(summary["purchases"].to_string(index=False))
    else:
        print("  購入履歴がありません。")
        print("  add_fang_purchase('2026-01-07', 100000, 84919) で追加してください。")

    print("\n" + "=" * 60)
