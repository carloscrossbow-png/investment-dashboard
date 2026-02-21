"""
================================================
売却シグナル判定モジュール
================================================
機能: Code 5の判定ロジックを関数化
用途: ダッシュボード・Code 5の両方から利用可能

使い方（ダッシュボードから）:
  from signal_evaluator import evaluate_stock_signal
  
  result = evaluate_stock_signal(
      ticker_code="9127",
      purchase_price=2870,
      purchase_date="2025-11-05",
      shares=100,
      industry="海運業",
      purchase_per=3.5,
      purchase_roe=18.5,
      purchase_equity=70.2
  )
  
  print(result['signal_strength'])  # 0-10
  print(result['overall'])          # "問題なし" など
  print(result['action'])           # 推奨アクション
================================================
"""

import yfinance as yf
import pandas as pd
from datetime import datetime


# ==========================================
# ユーティリティ関数
# ==========================================

def safe_float(value, default=None):
    """安全な数値変換"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if pd.isna(value) or value == float('inf') or value == float('-inf'):
            return default
        return float(value)
    if isinstance(value, str):
        if value.strip() in ['', 'N/A', '-', 'None', 'nan']:
            return default
        try:
            converted = float(value)
            if pd.isna(converted) or converted == float('inf') or converted == float('-inf'):
                return default
            return converted
        except (ValueError, TypeError):
            return default
    return default


def check_cyclical_industry(industry):
    """シクリカル業種判定"""
    if pd.isna(industry):
        return False
    
    cyclical_keywords = [
        '海運業', '鉄鋼', '非鉄金属', '石油・石炭製品',
        '化学', '機械', '電気機器', '輸送用機器',
        '建設業', '金属製品', 'ゴム製品', 'ガラス・土石製品',
        '鉱業', '陸運業', '空運業', 'パルプ・紙'
    ]
    return any(keyword in str(industry) for keyword in cyclical_keywords)


# ==========================================
# 財務データ取得
# ==========================================

def get_stock_data(ticker_code):
    """株価・財務データを取得"""
    ticker = f"{ticker_code}.T"
    stock = yf.Ticker(ticker)
    
    try:
        info = stock.info
        balance_sheet = stock.balance_sheet
        income_stmt = stock.income_stmt
        
        data = {
            '現在株価': safe_float(info.get('currentPrice')),
            '52週高値': safe_float(info.get('fiftyTwoWeekHigh')),
            '52週安値': safe_float(info.get('fiftyTwoWeekLow')),
            '現在PER': safe_float(info.get('trailingPE')),
            '現在PBR': safe_float(info.get('priceToBook')),
            '現在ROE': safe_float(info.get('returnOnEquity')) * 100 if safe_float(
                info.get('returnOnEquity')) is not None else None,
            '現在配当利回り': safe_float(info.get('dividendYield')),
            '時価総額': safe_float(info.get('marketCap')),
        }
        
        # 自己資本比率
        if not balance_sheet.empty and len(balance_sheet.columns) > 0:
            latest_bs = balance_sheet.iloc[:, 0]
            total_assets = safe_float(latest_bs.get('Total Assets'))
            total_equity = safe_float(latest_bs.get('Stockholders Equity'))
            
            if total_assets and total_equity and total_assets > 0:
                data['現在自己資本比率'] = (total_equity / total_assets) * 100
            else:
                data['現在自己資本比率'] = None
        else:
            data['現在自己資本比率'] = None
        
        # 営業利益率・成長率
        if not income_stmt.empty and len(income_stmt.columns) > 1:
            latest_income = income_stmt.iloc[:, 0]
            prev_income = income_stmt.iloc[:, 1]
            
            revenue = safe_float(latest_income.get('Total Revenue'))
            operating_income = safe_float(latest_income.get('Operating Income'))
            prev_revenue = safe_float(prev_income.get('Total Revenue'))
            prev_operating_income = safe_float(prev_income.get('Operating Income'))
            
            if revenue and operating_income and revenue > 0:
                data['営業利益率'] = (operating_income / revenue) * 100
            else:
                data['営業利益率'] = None
            
            if revenue and prev_revenue and prev_revenue > 0:
                data['売上成長率'] = ((revenue - prev_revenue) / prev_revenue) * 100
            else:
                data['売上成長率'] = None
            
            if operating_income and prev_operating_income and prev_operating_income > 0:
                data['営業利益成長率'] = ((operating_income - prev_operating_income) / prev_operating_income) * 100
            else:
                data['営業利益成長率'] = None
        else:
            data['営業利益率'] = None
            data['売上成長率'] = None
            data['営業利益成長率'] = None
        
        return data
        
    except Exception as e:
        print(f"エラー: {ticker_code} - {str(e)}")
        return None


# ==========================================
# 売却シグナル判定（メイン関数）
# ==========================================

def evaluate_stock_signal(
    ticker_code,
    purchase_price,
    purchase_date,
    shares,
    industry,
    purchase_per=None,
    purchase_roe=None,
    purchase_equity=None
):
    """
    売却シグナルを総合判定
    
    Args:
        ticker_code: 銘柄コード（例: "9127"）
        purchase_price: 購入単価（円）
        purchase_date: 購入日（YYYY-MM-DD）
        shares: 購入株数
        industry: 業種名
        purchase_per: 購入時PER（任意）
        purchase_roe: 購入時ROE（任意）
        purchase_equity: 購入時自己資本比率（任意）
    
    Returns:
        dict: {
            'signal_strength': 0-10,
            'overall': '問題なし' | '軽微な懸念' | '要注意' | '売却検討' | '強い売却推奨',
            'action': '推奨アクションメッセージ',
            'signals': [...],  # 検出されたシグナル一覧
            'profit_rate': 評価損益率（%）,
            'current_price': 現在株価,
            'current_per': 現在PER,
            'current_roe': 現在ROE,
            'current_equity': 現在自己資本比率
        }
    """
    
    # 現在データを取得
    stock_data = get_stock_data(ticker_code)
    if not stock_data:
        return {
            'signal_strength': 0,
            'overall': 'データ取得失敗',
            'action': 'データが取得できませんでした',
            'signals': [],
            'profit_rate': 0,
            'current_price': None,
            'current_per': None,
            'current_roe': None,
            'current_equity': None
        }
    
    current_price = stock_data['現在株価']
    current_per = stock_data['現在PER']
    current_roe = stock_data['現在ROE']
    current_equity = stock_data['現在自己資本比率']
    
    # 評価損益計算
    if purchase_price and current_price and shares:
        investment = shares * purchase_price
        current_value = shares * current_price
        profit = current_value - investment
        profit_rate = (profit / investment * 100) if investment > 0 else 0
    else:
        profit_rate = 0
    
    signals = []
    signal_strength = 0
    
    # ==========================================
    # 1. PER分析（シクリカル株）
    # ==========================================
    if check_cyclical_industry(industry):
        if current_per:
            if current_per > 15:
                signals.append({
                    'category': 'PER評価',
                    'level': '高',
                    'message': f'PER {current_per:.1f}倍（天井圏）',
                    'detail': 'シクリカル株としては売却推奨水準です'
                })
                signal_strength += 3
            elif current_per > 12:
                signals.append({
                    'category': 'PER評価',
                    'level': '中',
                    'message': f'PER {current_per:.1f}倍（天井接近）',
                    'detail': '15倍到達前の売却を検討してください'
                })
                signal_strength += 2
    
    # ==========================================
    # 2. 評価損益分析
    # ==========================================
    if profit_rate < -20:
        signals.append({
            'category': '評価損益',
            'level': '高',
            'message': f'評価損益 {profit_rate:.1f}%',
            'detail': '大幅な含み損。損切りを検討してください'
        })
        signal_strength += 3
    elif profit_rate > 50:
        signals.append({
            'category': '評価損益',
            'level': '中',
            'message': f'評価損益 {profit_rate:.1f}%',
            'detail': '大幅な含み益。利益確定を検討してください'
        })
        signal_strength += 2
    
    # ==========================================
    # 3. 52週高値分析
    # ==========================================
    high_52w = stock_data.get('52週高値')
    low_52w = stock_data.get('52週安値')
    
    if current_price and high_52w and low_52w:
        range_52w = high_52w - low_52w
        if range_52w > 0:
            position = ((current_price - low_52w) / range_52w) * 100
            if position > 90:
                signals.append({
                    'category': '株価位置',
                    'level': '中',
                    'message': f'52週レンジの{position:.1f}%地点',
                    'detail': '高値圏にあります。調整局面に注意'
                })
                signal_strength += 2
    
    # ==========================================
    # 4. ROE悪化分析
    # ==========================================
    if current_roe and purchase_roe:
        roe_change = current_roe - purchase_roe
        if roe_change < -5:
            signals.append({
                'category': 'ROE',
                'level': '高',
                'message': f'ROE {roe_change:+.1f}%ポイント悪化',
                'detail': '収益性が大幅に低下しています'
            })
            signal_strength += 3
    
    # ==========================================
    # 5. 自己資本比率悪化分析
    # ==========================================
    if current_equity and purchase_equity:
        equity_change = current_equity - purchase_equity
        if equity_change < -10:
            signals.append({
                'category': '財務健全性',
                'level': '高',
                'message': f'自己資本比率 {equity_change:+.1f}%ポイント悪化',
                'detail': '財務状況が悪化しています'
            })
            signal_strength += 3
    
    # ==========================================
    # 6. 売上・利益成長率分析
    # ==========================================
    revenue_growth = stock_data.get('売上成長率')
    profit_growth = stock_data.get('営業利益成長率')
    
    if revenue_growth and revenue_growth < -10:
        signals.append({
            'category': '業績',
            'level': '中',
            'message': f'売上成長率 {revenue_growth:+.1f}%',
            'detail': '売上が減少しています'
        })
        signal_strength += 2
    
    if profit_growth and profit_growth < -20:
        signals.append({
            'category': '業績',
            'level': '高',
            'message': f'営業利益成長率 {profit_growth:+.1f}%',
            'detail': '営業利益が大幅に減少しています'
        })
        signal_strength += 3
    
    # ==========================================
    # 総合判定
    # ==========================================
    if signal_strength >= 8:
        overall = "強い売却推奨"
        action = "即座に売却を検討してください"
    elif signal_strength >= 6:
        overall = "売却検討"
        action = "詳細を確認し、1週間以内に売却判断してください"
    elif signal_strength >= 4:
        overall = "要注意"
        action = "注意深く監視し、悪化すれば売却を検討してください"
    elif signal_strength >= 2:
        overall = "軽微な懸念"
        action = "定期的に確認してください"
    else:
        overall = "問題なし"
        action = "保有継続で問題ありません"
    
    return {
        'signal_strength': signal_strength,
        'overall': overall,
        'action': action,
        'signals': signals,
        'profit_rate': profit_rate,
        'current_price': current_price,
        'current_per': current_per,
        'current_roe': current_roe,
        'current_equity': current_equity,
        'stock_data': stock_data  # 全データも返す
    }


# ==========================================
# テスト用（単体実行時）
# ==========================================

if __name__ == "__main__":
    print("=" * 80)
    print("signal_evaluator.py テスト")
    print("=" * 80)
    
    # テストデータ
    result = evaluate_stock_signal(
        ticker_code="9127",
        purchase_price=2870,
        purchase_date="2025-11-05",
        shares=100,
        industry="海運業",
        purchase_per=3.6,
        purchase_roe=20.6,
        purchase_equity=73.2
    )
    
    print(f"\nシグナル強度: {result['signal_strength']}/10")
    print(f"総合判定: {result['overall']}")
    print(f"推奨アクション: {result['action']}")
    print(f"評価損益率: {result['profit_rate']:+.2f}%")
    print(f"現在株価: ¥{result['current_price']:,.0f}")
    print(f"現在PER: {result['current_per']:.1f}倍" if result['current_per'] else "現在PER: データなし")
    
    if len(result['signals']) > 0:
        print("\n検出されたシグナル:")
        for sig in result['signals']:
            print(f"  [{sig['category']}] {sig['message']}")
            print(f"    → {sig['detail']}")
    else:
        print("\n✅ 問題は検出されませんでした")
