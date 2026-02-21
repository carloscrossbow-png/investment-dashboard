"""
================================================
シクリカル株購入記録管理モジュール
================================================
機能: purchased_stocks.csv への購入記録追加

使い方（ダッシュボードから）:
  from cyclical_purchase_manager import add_cyclical_purchase
  
  add_cyclical_purchase(
      purchase_date="2025-11-05",
      ticker_code="9127",
      company_name="正栄汽船",
      purchase_price=2870,
      shares=100
  )
================================================
"""

import pandas as pd
import os
from datetime import datetime


CSV_PATH = "./portfolio_data/purchased_stocks.csv"


def add_cyclical_purchase(purchase_date, ticker_code, company_name, purchase_price, shares, memo=""):
    """
    シクリカル株の購入記録を追加
    
    Args:
        purchase_date: 購入日（YYYY-MM-DD形式）
        ticker_code: 銘柄コード（例: "9127"）
        company_name: 企業名（例: "正栄汽船"）
        purchase_price: 購入単価（円）
        shares: 購入株数
        memo: メモ（任意）
    """
    
    # フォルダ作成
    os.makedirs("./portfolio_data", exist_ok=True)
    
    # 投資金額計算
    investment = purchase_price * shares
    
    # 新規レコード
    new_record = {
        '購入日': purchase_date,
        '銘柄コード': ticker_code,
        '企業名': company_name,
        '購入単価': purchase_price,
        '購入株数': shares,
        '投資金額': investment,
        'メモ': memo
    }
    
    # CSV読み込み（存在しない場合は新規作成）
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
        # 新規レコードを追加
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    else:
        df = pd.DataFrame([new_record])
    
    # CSV保存
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    
    print(f"✅ 購入記録を追加しました: {ticker_code} {company_name} - {shares}株 @ ¥{purchase_price:,.0f}")


def get_purchase_history():
    """購入履歴を取得"""
    if os.path.exists(CSV_PATH):
        return pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    else:
        return pd.DataFrame(columns=['購入日', '銘柄コード', '企業名', '購入単価', '購入株数', '投資金額', 'メモ'])


def delete_last_purchase():
    """最後の購入記録を削除（誤入力訂正用）"""
    if not os.path.exists(CSV_PATH):
        print("⚠️ 購入履歴がありません")
        return
    
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    
    if len(df) == 0:
        print("⚠️ 購入履歴がありません")
        return
    
    # 最後の行を削除
    df = df.iloc[:-1]
    
    # 保存
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    print("✅ 最後の購入記録を削除しました")


# ==========================================
# テスト用（単体実行時）
# ==========================================

if __name__ == "__main__":
    print("=" * 80)
    print("cyclical_purchase_manager.py テスト")
    print("=" * 80)
    
    # テストデータ追加（コメントアウト）
    # add_cyclical_purchase(
    #     purchase_date="2025-11-05",
    #     ticker_code="9127",
    #     company_name="正栄汽船",
    #     purchase_price=2870,
    #     shares=100,
    #     memo="テスト購入"
    # )
    
    # 購入履歴表示
    history = get_purchase_history()
    print(f"\n購入履歴: {len(history)}件")
    if not history.empty:
        print(history.to_string())
