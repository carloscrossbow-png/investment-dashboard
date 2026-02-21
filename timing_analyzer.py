"""
================================================
購入タイミング分析モジュール（Code 6）
================================================
機能: RSI・移動平均・トレンド分析による購入タイミング判定

使い方:
  from timing_analyzer import analyze_purchase_timing
  
  result = analyze_purchase_timing(ticker_code="9127")
  
  print(result['timing_score'])  # 0-10
  print(result['recommendation'])  # "買い推奨" など
================================================
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def calculate_rsi(prices, period=14):
    """
    RSI（相対力指数）を計算
    
    Args:
        prices: 株価の Series
        period: 計算期間（デフォルト14日）
    
    Returns:
        float: RSI値（0-100）
    """
    if len(prices) < period + 1:
        return None
    
    # 前日比の変化を計算
    delta = prices.diff()
    
    # 上昇・下降を分離
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 平均を計算
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # RSを計算
    rs = avg_gain / avg_loss
    
    # RSIを計算
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1]


def analyze_purchase_timing(ticker_code, current_per=None):
    """
    購入タイミングを総合的に分析
    
    Args:
        ticker_code: 銘柄コード（例: "9127"）
        current_per: 現在のPER（任意、提供されればスコアに反映）
    
    Returns:
        dict: {
            'timing_score': 0-10,
            'recommendation': '買い推奨' | '様子見' | '買い控え',
            'rsi': RSI値,
            'rsi_signal': 'RSIシグナル',
            'ma_signal': '移動平均シグナル',
            'trend': 'トレンド',
            'details': [...],
            'action': '推奨アクション'
        }
    """
    
    ticker = f"{ticker_code}.T"
    
    try:
        # 過去6ヶ月のデータ取得
        stock = yf.Ticker(ticker)
        history = stock.history(period="6mo")
        
        if len(history) < 30:
            return {
                'timing_score': 0,
                'recommendation': 'データ不足',
                'action': 'データが不足しています',
                'details': []
            }
        
        # 現在価格
        current_price = history['Close'].iloc[-1]
        
        # RSI計算
        rsi = calculate_rsi(history['Close'], period=14)
        
        # 移動平均計算
        ma_5 = history['Close'].rolling(window=5).mean().iloc[-1]
        ma_25 = history['Close'].rolling(window=25).mean().iloc[-1]
        ma_75 = history['Close'].rolling(window=75).mean().iloc[-1] if len(history) >= 75 else None
        
        # スコアリング
        score = 0
        details = []
        
        # ==========================================
        # 1. RSI分析（最重要）
        # ==========================================
        if rsi:
            if rsi < 30:
                score += 4
                rsi_signal = "🎯 売られすぎ（絶好の買い場）"
                rsi_detail = f"RSI {rsi:.1f}は30未満で売られすぎ。反発の可能性大。"
            elif rsi < 40:
                score += 3
                rsi_signal = "✅ やや売られすぎ（買い推奨）"
                rsi_detail = f"RSI {rsi:.1f}は40未満でやや売られすぎ。"
            elif rsi < 50:
                score += 2
                rsi_signal = "😊 中立（やや買い）"
                rsi_detail = f"RSI {rsi:.1f}は中立圏。"
            elif rsi < 60:
                score += 1
                rsi_signal = "😐 中立"
                rsi_detail = f"RSI {rsi:.1f}は中立圏。"
            elif rsi < 70:
                score += 0
                rsi_signal = "⚠️ やや買われすぎ"
                rsi_detail = f"RSI {rsi:.1f}はやや買われすぎ。調整の可能性。"
            else:
                score -= 2
                rsi_signal = "🚨 買われすぎ（買い控え）"
                rsi_detail = f"RSI {rsi:.1f}は70超えで買われすぎ。調整待ち推奨。"
            
            details.append(('RSI', f"{rsi:.1f}", rsi_signal, rsi_detail))
        else:
            rsi_signal = "N/A"
            rsi_detail = "RSIデータなし"
        
        # ==========================================
        # 2. 移動平均分析
        # ==========================================
        if current_price < ma_25:
            score += 2
            ma_signal = "✅ 25日線を下回る（押し目買いチャンス）"
            ma_detail = f"現在価格¥{current_price:.0f}が25日線¥{ma_25:.0f}を下回る。"
        elif current_price < ma_5:
            score += 1
            ma_signal = "😊 5日線を下回る"
            ma_detail = f"現在価格¥{current_price:.0f}が5日線¥{ma_5:.0f}を下回る。"
        elif current_price > ma_25 * 1.1:
            score -= 1
            ma_signal = "⚠️ 25日線を大きく上回る"
            ma_detail = f"現在価格¥{current_price:.0f}が25日線¥{ma_25:.0f}を10%以上上回る。調整の可能性。"
        else:
            score += 0
            ma_signal = "😐 移動平均線付近"
            ma_detail = f"現在価格¥{current_price:.0f}は移動平均線付近。"
        
        details.append(('移動平均', f"¥{current_price:.0f}", ma_signal, ma_detail))
        
        # ==========================================
        # 3. トレンド分析
        # ==========================================
        if ma_75:
            if ma_5 > ma_25 > ma_75:
                score += 1
                trend = "📈 上昇トレンド"
                trend_detail = "短期・中期・長期すべて上昇トレンド。"
            elif ma_5 < ma_25 < ma_75:
                score += 2
                trend = "📉 下降トレンド（買い場）"
                trend_detail = "下降トレンド中。底値圏での買いチャンス。"
            else:
                score += 0
                trend = "😐 レンジ相場"
                trend_detail = "明確なトレンドなし。"
            
            details.append(('トレンド', trend, '', trend_detail))
        else:
            trend = "N/A"
        
        # ==========================================
        # 4. PER分析（提供された場合）
        # ==========================================
        if current_per:
            if current_per < 5:
                score += 3
                per_signal = "🎯 超割安PER"
                per_detail = f"PER {current_per:.1f}倍は歴史的割安。"
            elif current_per < 7:
                score += 2
                per_signal = "✅ 割安PER"
                per_detail = f"PER {current_per:.1f}倍は割安。"
            elif current_per < 10:
                score += 1
                per_signal = "😊 適正PER"
                per_detail = f"PER {current_per:.1f}倍は適正水準。"
            else:
                score += 0
                per_signal = "😐 やや高PER"
                per_detail = f"PER {current_per:.1f}倍はやや高め。"
            
            details.append(('PER', f"{current_per:.1f}倍", per_signal, per_detail))
        
        # ==========================================
        # 総合判定
        # ==========================================
        if score >= 8:
            recommendation = "🎯 強い買い推奨"
            action = "今月の投資予算の60%を投入推奨"
        elif score >= 6:
            recommendation = "✅ 買い推奨"
            action = "今月の投資予算の40%を投入推奨"
        elif score >= 4:
            recommendation = "😊 やや買い"
            action = "少額から様子見で投資"
        elif score >= 2:
            recommendation = "😐 中立"
            action = "様子見推奨"
        else:
            recommendation = "⚠️ 買い控え"
            action = "調整待ち推奨"
        
        return {
            'timing_score': min(score, 10),  # 最大10点
            'recommendation': recommendation,
            'rsi': rsi,
            'rsi_signal': rsi_signal,
            'ma_signal': ma_signal,
            'trend': trend,
            'details': details,
            'action': action,
            'current_price': current_price,
            'ma_5': ma_5,
            'ma_25': ma_25,
            'ma_75': ma_75
        }
    
    except Exception as e:
        print(f"エラー: {ticker_code} - {str(e)}")
        return {
            'timing_score': 0,
            'recommendation': 'エラー',
            'action': f'データ取得エラー: {str(e)}',
            'details': []
        }


# ==========================================
# テスト用（単体実行時）
# ==========================================

if __name__ == "__main__":
    print("=" * 80)
    print("timing_analyzer.py テスト")
    print("=" * 80)
    
    # テストデータ
    result = analyze_purchase_timing(
        ticker_code="9127",
        current_per=4.5
    )
    
    print(f"\n購入タイミングスコア: {result['timing_score']}/10")
    print(f"総合判定: {result['recommendation']}")
    print(f"推奨アクション: {result['action']}")
    
    if result.get('rsi'):
        print(f"\nRSI: {result['rsi']:.1f} - {result['rsi_signal']}")
    print(f"移動平均: {result['ma_signal']}")
    print(f"トレンド: {result['trend']}")
    
    if len(result['details']) > 0:
        print("\n詳細分析:")
        for indicator, value, signal, detail in result['details']:
            print(f"  [{indicator}] {value}")
            print(f"    → {detail}")
