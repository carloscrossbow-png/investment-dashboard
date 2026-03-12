"""
================================================
シクリカル株購入・売却記録管理モジュール（gspread版）
================================================
機能:
  - Google Sheetsへの購入記録追加（永続保存）
  - 売却記録追加
  - 購入履歴取得

Streamlit Secretsに以下が必要:
  [gcp_service_account]
  type = "service_account"
  project_id = "..."
  private_key_id = "..."
  private_key = "..."
  client_email = "..."
  client_id = "..."
  ...
================================================
"""

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_ID = "1-ioGOVA9KUKYqOTuDo9s8jP1O_XTiOJLQNgnf3D08n8"
PURCHASE_SHEET_NAME = "purchased_stocks"


def get_gspread_client():
    """Streamlit Secretsからgspreadクライアントを取得。失敗時はNone。"""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES,
        )
        return gspread.authorize(creds)
    except Exception:
        return None


def get_purchase_history() -> pd.DataFrame:
    """購入履歴をGoogle Sheetsから取得"""
    client = get_gspread_client()
    if client is None:
        return pd.DataFrame(
            columns=["購入日", "銘柄コード", "企業名", "購入単価", "購入株数", "投資金額", "メモ"]
        )
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(PURCHASE_SHEET_NAME)
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame(
            columns=["購入日", "銘柄コード", "企業名", "購入単価", "購入株数", "投資金額", "メモ"]
        )
    except Exception:
        return pd.DataFrame(
            columns=["購入日", "銘柄コード", "企業名", "購入単価", "購入株数", "投資金額", "メモ"]
        )


def add_cyclical_purchase(
    purchase_date: str,
    ticker_code: str,
    company_name: str,
    purchase_price: float,
    shares: int,
    memo: str = "",
) -> bool:
    """購入記録をGoogle Sheetsに追加。成功時True。"""
    client = get_gspread_client()
    if client is None:
        return False
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        try:
            ws = sh.worksheet(PURCHASE_SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=PURCHASE_SHEET_NAME, rows=1000, cols=8)
            ws.append_row(["購入日", "銘柄コード", "企業名", "購入単価", "購入株数", "投資金額", "メモ"])
        investment = int(purchase_price * shares)
        ws.append_row([
            purchase_date,
            str(ticker_code),
            company_name,
            int(purchase_price),
            int(shares),
            investment,
            memo,
        ])
        return True
    except Exception as e:
        st.error(f"Google Sheets書き込みエラー: {e}")
        return False


def delete_last_purchase() -> bool:
    """最後の購入記録を削除（誤入力訂正用）。成功時True。"""
    client = get_gspread_client()
    if client is None:
        return False
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(PURCHASE_SHEET_NAME)
        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            return False
        ws.delete_rows(len(all_values))
        return True
    except Exception:
        return False
