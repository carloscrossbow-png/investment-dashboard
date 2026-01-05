"""
統合投資ダッシュボード
FANG+ + シクリカル株 + マクロ経済指標を一元管理
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import requests
from bs4 import BeautifulSoup
import re
import requests
from bs4 import BeautifulSoup
import re


# ========================================
# 詳細判定関数
# ========================================

def calculate_market_score(buffett, shiller, vix, yield_curve):
    """市場スコアを計算"""
    score = 0
    details = []

    # バフェット指数の評価
    if buffett < 100:
        score += 3
        buffett_eval = ("🎯 大チャンス", "+3点")
    elif buffett < 130:
        score += 2
        buffett_eval = ("✅ 割安", "+2点")
    elif buffett < 150:
        score += 1
        buffett_eval = ("😊 適正", "+1点")
    elif buffett < 180:
        score += 0
        buffett_eval = ("😐 やや割高", "0点")
    elif buffett < 200:
        score -= 1
        buffett_eval = ("⚠️ 割高", "-1点")
    elif buffett < 220:
        score -= 2
        buffett_eval = ("🚨 かなり割高", "-2点")
    else:
        score -= 3
        buffett_eval = ("🚨 歴史的割高", "-3点")

    details.append(("💰 バフェット指数", f"{buffett:.1f}%", buffett_eval[0], buffett_eval[1]))

    # シラーPERの評価
    if shiller < 10:
        score += 3
        shiller_eval = ("🎯 大チャンス", "+3点")
    elif shiller < 15:
        score += 2
        shiller_eval = ("✅ 割安", "+2点")
    elif shiller < 20:
        score += 1
        shiller_eval = ("😊 適正", "+1点")
    elif shiller < 25:
        score += 0
        shiller_eval = ("😐 やや割高", "0点")
    elif shiller < 30:
        score -= 1
        shiller_eval = ("⚠️ 割高", "-1点")
    elif shiller < 35:
        score -= 2
        shiller_eval = ("🚨 かなり割高", "-2点")
    else:
        score -= 3
        shiller_eval = ("🚨 歴史的割高", "-3点")

    details.append(("📊 シラーPER", f"{shiller:.1f}倍", shiller_eval[0], shiller_eval[1]))

    # VIX指数の評価
    if vix > 30:
        score += 3
        vix_eval = ("🎯 買いチャンス", "+3点")
    elif vix > 25:
        score += 1
        vix_eval = ("😰 不安", "+1点")
    elif vix > 20:
        score += 0
        vix_eval = ("😐 やや不安", "0点")
    elif vix > 15:
        score += 1
        vix_eval = ("😊 中立", "+1点")
    else:
        score += 2
        vix_eval = ("😌 楽観的", "+2点")

    details.append(("😱 VIX指数", f"{vix:.2f}", vix_eval[0], vix_eval[1]))

    # イールドカーブの評価
    if yield_curve < -1.0:
        score -= 2
        yield_eval = ("🚨 深刻な逆イールド", "-2点")
    elif yield_curve < -0.5:
        score -= 1
        yield_eval = ("⚠️ 逆イールド", "-1点")
    elif yield_curve < 0:
        score += 0
        yield_eval = ("😐 フラット", "0点")
    elif yield_curve < 1.0:
        score += 1
        yield_eval = ("✅ 正常", "+1点")
    else:
        score += 2
        yield_eval = ("✅ 理想的", "+2点")

    details.append(("🔴 イールドカーブ", f"{yield_curve:.2f}%", yield_eval[0], yield_eval[1]))

    return score, details


def get_detailed_us_market_judgment(buffett, shiller, vix, yield_curve, score):
    """詳細な市場判断（米国株）"""

    # 基本判定
    if score >= 8:
        level = '🎯 大チャンス'
        color = 'success'
    elif score >= 5:
        level = '✅ 買い推奨'
        color = 'success'
    elif score >= 2:
        level = '😊 やや買い'
        color = 'info'
    elif score >= -1:
        level = '😐 中立'
        color = 'info'
    elif score >= -4:
        level = '⚠️ やや警戒'
        color = 'warning'
    elif score >= -7:
        level = '🚨 警戒'
        color = 'error'
    else:
        level = '🚨 最大警戒'
        color = 'error'

    # 詳細分析
    buffett_high = buffett > 200
    shiller_high = shiller > 30
    both_high = buffett_high and shiller_high
    vix_panic = vix > 30
    vix_calm = vix < 15
    yield_inverted = yield_curve < 0

    # パターン判定
    if both_high and vix_calm:
        pattern = '🚨 天井圏での楽観'
        analysis = f'''
**現在の状況**
・バフェット指数：{buffett:.1f}%（歴史的割高）
・シラーPER：{shiller:.1f}倍（歴史的割高）
・VIX：{vix:.2f}（市場は楽観的）

**何を意味するか**
市場が歴史的割高にも関わらず、投資家は楽観的。これは典型的な「天井圏での楽観」パターン。

**過去の類似ケース**
・2000年ITバブル崩壊前
・2007年リーマンショック前
→ いずれも1-2年以内に大幅調整

**リスク分析**
🚨 調整リスク：非常に高い（-20～-40%）
⏱️ 調整時期：6ヶ月～2年以内の可能性
📊 期待リターン（今後10年）：3-5%/年程度
'''
        recommendation = f'''
**FANG+投資について**

❌ **新規投資：完全停止を推奨**
　理由：高値づかみリスクが極めて高い

⚠️ **既存10万円：保有継続**
　理由：5年保有なら回復の可能性大
　対策：-30%まで下落しても売らない覚悟を

📊 **追加投資：以下の条件まで待機**
　✅ 条件1：バフェット指数 200%以下
　✅ 条件2：シラーPER 30倍以下
　✅ 条件3：VIX 25超え（調整局面）

**推奨戦略**
1月：完全待機（現金温存）
2-3月：市場動向を注視
条件満たす：30%投資 → さらに下落：追加投資
'''

    elif both_high and vix_panic:
        pattern = '🎯 割高圏での調整'
        analysis = f'''
**現在の状況**
・バフェット指数：{buffett:.1f}%（割高）
・シラーPER：{shiller:.1f}倍（割高）
・VIX：{vix:.2f}（パニック状態）

**何を意味するか**
割高な市場で調整（パニック売り）が発生。短期的な押し目買いチャンスだが、長期的には割高。

**期待シナリオ**
📈 短期（3-6ヶ月）：+10～20%回復
⚠️ 中期（1-2年）：再度調整の可能性
📊 長期（5年）：プラスリターンの可能性高い
'''
        recommendation = f'''
**FANG+投資について**

⚠️ **新規投資：分割購入で参加**
　VIXパニックは買いシグナル（ただし全額は避ける）

📊 **推奨投資プラン**
VIX 30-35：予算の30%投資
VIX 35-40：さらに30%投資
VIX 40超え：残り40%投資
'''

    elif yield_inverted and buffett_high:
        pattern = '⚠️ 景気後退警告'
        analysis = f'''
**現在の状況**
・バフェット指数：{buffett:.1f}%（割高）
・イールドカーブ：{yield_curve:.2f}%（逆イールド）

**何を意味するか**
逆イールドは6-18ヶ月後の景気後退を示唆。

**リスク分析**
⚠️ 景気後退確率：6ヶ月以内 30%
⚠️ 景気後退確率：12ヶ月以内 60%
'''
        recommendation = f'''
**FANG+投資について**

⚠️ **新規投資：慎重に**
現金比率を高めに維持（50%以上）
VIX 25超えまで待機も選択肢
'''

    else:
        pattern = '📊 総合分析'
        analysis = f'''
**現在の状況**
・バフェット指数：{buffett:.1f}%
・シラーPER：{shiller:.1f}倍
・VIX：{vix:.2f}
・イールドカーブ：{yield_curve:.2f}%

**市場の位置づけ**
{'割安' if buffett < 150 else '適正' if buffett < 180 else '割高'}な水準で、
{'パニック' if vix > 30 else '不安' if vix > 20 else '安定'}している状態。
'''
        recommendation = f'''
スコア {score}点に基づき、慎重な投資判断を推奨。
'''

    return {
        'level': level,
        'color': color,
        'score': score,
        'pattern': pattern,
        'analysis': analysis,
        'recommendation': recommendation
    }


def get_detailed_cyclical_judgment(ticker_code, stock_name, current_data, macro_environment):
    """シクリカル株の詳細判定"""

    # 現在の指標
    per = current_data.get('per', 10.0)
    dividend_yield = current_data.get('dividend_yield', 0)
    equity_ratio = current_data.get('equity_ratio', 40.0)
    roe = current_data.get('roe', 10.0)
    price_position = current_data.get('price_position', 0)

    # マクロ環境
    yield_curve = macro_environment.get('yield_curve', 0)

    # スコアリング
    score = 0
    score_details = []

    # PER分析（最重要）
    if per < 5:
        score += 5
        per_eval = "🎯 超割安"
        per_detail = f"PER {per:.1f}倍は絶好の買い場。通常時の半値以下。"
    elif per < 7:
        score += 4
        per_eval = "✅ 割安"
        per_detail = f"PER {per:.1f}倍は底値圏。積極的に買い。"
    elif per < 10:
        score += 2
        per_eval = "😊 適正"
        per_detail = f"PER {per:.1f}倍は適正水準。"
    elif per < 12:
        score += 0
        per_eval = "😐 やや高め"
        per_detail = f"PER {per:.1f}倍はやや高め。様子見推奨。"
    elif per < 15:
        score -= 2
        per_eval = "⚠️ 高め"
        per_detail = f"PER {per:.1f}倍は売却を検討すべき水準。"
    else:
        score -= 4
        per_eval = "🚨 割高"
        per_detail = f"PER {per:.1f}倍は天井圏。即座に売却推奨。"

    score_details.append(("PER", f"{per:.1f}倍", per_eval, per_detail))

    # 配当利回り
    if dividend_yield > 4:
        score += 2
        div_eval = "✅ 高配当"
        div_detail = f"配当{dividend_yield:.1f}%は高水準。"
    elif dividend_yield > 2.5:
        score += 1
        div_eval = "😊 適正配当"
        div_detail = f"配当{dividend_yield:.1f}%は標準的。"
    else:
        score += 0
        div_eval = "😐 低配当"
        div_detail = f"配当{dividend_yield:.1f}%はやや物足りない。"

    score_details.append(("配当利回り", f"{dividend_yield:.1f}%", div_eval, div_detail))

    # 自己資本比率
    if equity_ratio > 50:
        score += 2
        equity_eval = "✅ 健全"
        equity_detail = f"自己資本比率{equity_ratio:.1f}%は非常に健全。"
    elif equity_ratio > 30:
        score += 1
        equity_eval = "😊 適正"
        equity_detail = f"自己資本比率{equity_ratio:.1f}%は標準的。"
    else:
        score -= 1
        equity_eval = "⚠️ やや不安"
        equity_detail = f"自己資本比率{equity_ratio:.1f}%はやや低め。"

    score_details.append(("自己資本比率", f"{equity_ratio:.1f}%", equity_eval, equity_detail))

    # ROE
    if roe > 15:
        score += 1
        roe_eval = "✅ 高収益"
        roe_detail = f"ROE {roe:.1f}%は優良企業レベル。"
    elif roe > 10:
        score += 1
        roe_eval = "😊 適正"
        roe_detail = f"ROE {roe:.1f}%は標準的。"
    else:
        score += 0
        roe_eval = "😐 低収益"
        roe_detail = f"ROE {roe:.1f}%はやや低め。"

    score_details.append(("ROE", f"{roe:.1f}%", roe_eval, roe_detail))

    # マクロ環境
    macro_note = ""
    if yield_curve < 0:
        score -= 1
        macro_note = f"⚠️ 逆イールド（{yield_curve:.2f}%）→ 景気後退リスク"
    else:
        macro_note = f"✅ 正常なイールドカーブ（{yield_curve:.2f}%）"

    # 総合判定
    if score >= 10:
        level = "🎯🎯🎯 絶好の買い場"
        action = "即座に購入推奨"
        color = "success"
    elif score >= 7:
        level = "🎯 強い買い推奨"
        action = "積極的に購入"
        color = "success"
    elif score >= 4:
        level = "✅ 買い推奨"
        action = "購入を検討"
        color = "success"
    elif score >= 0:
        level = "😐 中立"
        action = "様子見"
        color = "info"
    elif score >= -3:
        level = "⚠️ 売却検討"
        action = "利益確定を検討"
        color = "warning"
    else:
        level = "🚨 売却推奨"
        action = "即座に売却"
        color = "error"

    # 詳細分析レポート
    detailed_analysis = f'''
### 📊 指標スコアリング
**総合スコア：{score}点 / 15点**

'''

    for indicator, value, evaluation, detail in score_details:
        detailed_analysis += f"**{indicator}**: {value} → {evaluation}  \n{detail}\n\n"

    detailed_analysis += f"### 🌍 マクロ環境\n{macro_note}\n\n"
    detailed_analysis += f"### 🎯 判断：{level}\n\n"

    # PERベースの詳細判断
    if per < 5 and dividend_yield > 3 and equity_ratio > 40:
        detailed_analysis += f'''
**【最強の買いシグナル】**

✅ PER {per:.1f}倍 = 歴史的底値  
✅ 配当 {dividend_yield:.1f}% = 高配当で待てる  
✅ 自己資本比率 {equity_ratio:.1f}% = 財務健全

**投資プラン**
1. 今月：予算の60%を投資
2. さらに下落時：残り40%投資
3. 売却目標：PER 12倍で50%、PER 15倍で全売却

**期待リターン：+{(12 / per - 1) * 100:.0f}%**
'''

    elif per < 7:
        detailed_analysis += f'''
**【買い推奨】**

✅ PER {per:.1f}倍 = 底値圏  
{'✅' if dividend_yield > 2.5 else '😐'} 配当 {dividend_yield:.1f}%

**投資プラン**
1. 今月：予算の40%を投資
2. 追加下落時：30%追加
3. 売却目標：PER 12-15倍

**期待リターン：+{(12 / per - 1) * 100:.0f}%**
'''

    elif per >= 12:
        detailed_analysis += f'''
**【売却検討】**

⚠️ PER {per:.1f}倍 = 天井圏

**なぜ売却すべきか**
・シクリカル株のPER {per:.1f}倍は割高
・ここからの上昇余地は限定的

**売却プラン**
・PER 12-13倍：50%売却
・PER 13-15倍：75%売却
・PER 15倍超：全売却
'''

    return {
        'score': score,
        'level': level,
        'action': action,
        'color': color,
        'details': score_details,
        'analysis': detailed_analysis
    }


@st.cache_data(ttl=3600)
def get_cyclical_detailed_data():
    """シクリカル株の詳細データ取得"""

    # 既存の関数を使う
    cyclical_df = load_cyclical_portfolio()

    if cyclical_df.empty:
        return []

    detailed_stocks = []

    for idx, row in cyclical_df.iterrows():
        ticker = str(row['銘柄コード']) + '.T'
        stock_name = row['銘柄名']
        purchase_price = float(row['購入価格'])
        shares = float(row['購入株数'])
        purchase_date = row['購入日']

        try:
            # Yahoo Financeから追加データ取得
            stock = yf.Ticker(ticker)
            info = stock.info
            history = stock.history(period="1y")

            # 現在価格
            if len(history) > 0:
                current_price = history['Close'].iloc[-1]
            else:
                current_price = info.get('currentPrice', purchase_price)

            # PER
            per = info.get('trailingPE', None)
            if per is None or per == 0 or str(per) == 'nan':
                per = 10.0

            # 配当利回り
            dividend_yield = info.get('dividendYield', 0)
            if dividend_yield and dividend_yield < 1:
                dividend_yield = dividend_yield * 100
            elif not dividend_yield:
                dividend_yield = 0

            # 自己資本比率（簡易）
            equity_ratio = 40.0

            # ROE
            roe = info.get('returnOnEquity', 0)
            if roe and roe < 1:
                roe = roe * 100
            elif not roe:
                roe = 10.0

            # 52週高値との比較
            if len(history) > 0:
                high_52w = history['High'].max()
                price_position = ((current_price - high_52w) / high_52w * 100)
            else:
                price_position = 0

            # 損益計算
            cost = purchase_price * shares
            current_value = current_price * shares
            profit = current_value - cost
            profit_pct = (profit / cost * 100) if cost > 0 else 0

            detailed_stocks.append({
                'ticker_code': row['銘柄コード'],
                'stock_name': stock_name,
                'purchase_price': purchase_price,
                'current_price': current_price,
                'shares': shares,
                'purchase_date': purchase_date,
                'cost': cost,
                'current_value': current_value,
                'profit': profit,
                'profit_pct': profit_pct,
                'per': per,
                'dividend_yield': dividend_yield,
                'equity_ratio': equity_ratio,
                'roe': roe,
                'price_position': price_position
            })

        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            continue

    return detailed_stocks

# ページ設定
st.set_page_config(
    page_title="統合投資ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .big-metric { font-size: 2.5rem; font-weight: bold; }
    .positive { color: #00ff00; }
    .negative { color: #ff4444; }
    .warning { color: #ffaa00; }
    .neutral { color: #888888; }
    .section-header { 
        font-size: 1.5rem; 
        font-weight: bold; 
        margin-top: 2rem; 
        margin-bottom: 1rem;
        border-bottom: 2px solid #444;
        padding-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# データキャッシュ（1時間）
@st.cache_data(ttl=3600)
def get_bond_yields():
    """債券利回り取得"""
    try:
        tnx = yf.Ticker("^TNX")  # 10年債
        fvx = yf.Ticker("^FVX")  # 5年債

        tnx_data = tnx.history(period="5d")
        fvx_data = fvx.history(period="5d")

        if len(tnx_data) > 0 and len(fvx_data) > 0:
            ten_year = tnx_data['Close'].iloc[-1]
            five_year = fvx_data['Close'].iloc[-1]

            # 2年債を推定（10年債 - 0.8%程度）
            two_year = ten_year - 0.8

            return {
                'ten_year': ten_year,
                'two_year': two_year,
                'spread': ten_year - two_year
            }
    except:
        pass
    return {'ten_year': 0, 'two_year': 0, 'spread': 0}

@st.cache_data(ttl=3600)
def get_vix():
    """VIX指数取得"""
    try:
        vix = yf.Ticker("^VIX")
        vix_data = vix.history(period="5d")
        if len(vix_data) > 0:
            return {
                'current': vix_data['Close'].iloc[-1],
                'history': vix_data['Close'].tolist()
            }
    except:
        pass
    return {'current': 0, 'history': []}

@st.cache_data(ttl=3600)
def get_major_indices():
    """主要指数取得"""
    try:
        indices = {
            'S&P 500': '^GSPC',
            'NASDAQ': '^IXIC',
            'QQQ': 'QQQ'
        }

        results = {}
        for name, ticker in indices.items():
            stock = yf.Ticker(ticker)
            data = stock.history(period="5d")
            if len(data) > 0:
                current = data['Close'].iloc[-1]
                prev = data['Close'].iloc[-2] if len(data) > 1 else current
                change_pct = ((current - prev) / prev * 100) if prev > 0 else 0

                results[name] = {
                    'price': current,
                    'change_pct': change_pct
                }

        return results
    except:
        pass
    return {}

@st.cache_data(ttl=86400)  # 24時間キャッシュ
def get_shiller_pe_auto():
    """
    multpl.comからシラーPERを自動取得

    Returns:
        float: シラーPER（取得失敗時はNone）
    """
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        }

        url = "https://www.multpl.com/shiller-pe"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        current_value = soup.find('div', id='current')

        if current_value:
            shiller_text = current_value.get_text().strip()
            # 正規表現で数値を抽出
            match = re.search(r'\d+\.\d+', shiller_text)
            if match:
                return float(match.group())
        return None
    except:
        return None

@st.cache_data(ttl=3600)
def get_stock_price(ticker):
    """日本株の現在価格取得"""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="5d")
        if len(data) > 0:
            current = data['Close'].iloc[-1]
            prev = data['Close'].iloc[-2] if len(data) > 1 else current
            change_pct = ((current - prev) / prev * 100) if prev > 0 else 0

            return {
                'price': current,
                'change_pct': change_pct
            }
    except:
        pass
    return {'price': 0, 'change_pct': 0}

def calculate_danger_level(buffett, yield_spread, vix):
    """総合危険度計算"""
    danger = 0

    # イールドカーブ
    if yield_spread < -0.5:
        danger += 3
    elif yield_spread < 0:
        danger += 2

    # VIX
    if vix > 30:
        danger += 3
    elif vix > 25:
        danger += 2
    elif vix > 20:
        danger += 1

    # バフェット指数
    if buffett > 200:
        danger += 3
    elif buffett > 180:
        danger += 2
    elif buffett > 150:
        danger += 1

    return danger

def load_cyclical_portfolio():
    """シクリカル株ポートフォリオ読込（Google Sheets対応）"""

    # Google Sheets の CSV エクスポート URL（設定で変更可能）
    # サイドバーで設定した場合はそちらを優先
    google_sheets_url = st.session_state.get('google_sheets_url', '')

    # ローカルファイルパス
    local_csv_path = "/Users/carlos/PyCharmMiscProject/株スクリーニング完成版/portfolio_data/purchased_stocks.csv"

    df = pd.DataFrame()

    # 優先順位1: Google Sheets URL
    if google_sheets_url:
        try:
            df = pd.read_csv(google_sheets_url)
            st.sidebar.success("✅ Google Sheets から読込成功")
        except Exception as e:
            st.sidebar.error(f"❌ Google Sheets 読込失敗: {e}")

    # 優先順位2: ローカルファイル
    if df.empty and os.path.exists(local_csv_path):
        try:
            df = pd.read_csv(local_csv_path, encoding='utf-8-sig')
        except Exception as e:
            print(f"ローカルファイル読み込みエラー: {e}")

    # データ集約処理
    if not df.empty and '銘柄コード' in df.columns:
        # 同じ銘柄の複数購入記録を集約
        aggregated_rows = []

        for code in df['銘柄コード'].unique():
            stock_records = df[df['銘柄コード'] == code]

            # 合計株数計算
            total_shares = stock_records['購入株数'].sum()

            # 平均取得単価計算（加重平均）
            total_cost = (stock_records['購入株数'] * stock_records['購入単価']).sum()
            avg_price = total_cost / total_shares if total_shares > 0 else 0

            # 最も古い購入日を使用
            first_purchase = stock_records['購入日'].min()

            # 集約レコード作成
            aggregated_rows.append({
                '銘柄コード': code,
                '銘柄名': stock_records.iloc[0]['企業名'],
                '購入価格': avg_price,
                '購入株数': total_shares,
                '購入日': first_purchase
            })

        return pd.DataFrame(aggregated_rows)

    # デモデータ（ファイルが存在しない場合）
    return pd.DataFrame({
        '銘柄コード': [],
        '銘柄名': [],
        '購入価格': [],
        '購入株数': [],
        '購入日': []
    })

# メインページ
st.title("📊 統合投資ダッシュボード")
st.caption(f"最終更新: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")

    # Google Sheets 連携設定
    st.subheader("☁️ データソース")

    # Secretsからデフォルト URLを取得
    default_google_sheets_url = ""
    try:
        default_google_sheets_url = st.secrets.get("google_sheets", {}).get("csv_url", "")
    except:
        pass

    # Google Sheets URL入力
    google_sheets_url_input = st.text_input(
        "Google Sheets CSV URL（任意）",
        value=default_google_sheets_url,
        help="Google Sheets の CSV エクスポート URL を入力すると、外出先からも最新データを確認できます",
        placeholder="https://docs.google.com/spreadsheets/d/.../export?format=csv&gid=0"
    )

    # セッションステートに保存
    if google_sheets_url_input:
        st.session_state['google_sheets_url'] = google_sheets_url_input

    # データソース表示
    if google_sheets_url_input:
        st.info("📊 データソース: Google Sheets")
    else:
        st.info("💻 データソース: ローカルファイル")

    st.markdown("---")

    # Secretsからデフォルト値を取得
    default_buffett = 200.0
    default_shiller = 30.0
    try:
        default_buffett = float(st.secrets.get("settings", {}).get("buffett_indicator", 200.0))
        default_shiller = float(st.secrets.get("settings", {}).get("shiller_pe", 30.0))
    except:
        pass

    # バフェット指数
    buffett_indicator = st.number_input(
        "バフェット指数 (%) ※手動入力",
        min_value=50.0,
        max_value=300.0,
        value=default_buffett,
        step=1.0,
        help="https://currentmarketvaluation.com/ で確認"
    )

    # シラーPER（自動取得）
    st.markdown("### 📊 シラーPER")

    shiller_auto = get_shiller_pe_auto()

    if shiller_auto:
        st.success(f"✅ 自動取得成功: {shiller_auto:.2f}倍")
        shiller_pe = shiller_auto
        st.info(f"📊 現在値: {shiller_pe:.2f}倍")
    else:
        st.warning("⚠️ 自動取得失敗。手動入力してください")

        shiller_pe = st.number_input(
            "シラーPER (倍) ※手動入力",
            min_value=5.0,
            max_value=60.0,
            value=default_shiller,
            step=0.1,
            help="自動取得失敗時の手動入力"
        )

    st.markdown("---")

    # FANG+設定
    st.subheader("💎 FANG+設定")
    fang_investment = st.number_input(
        "投資額（円）",
        min_value=0,
        max_value=10000000,
        value=400000,
        step=10000
    )

    fang_purchase_price = st.number_input(
        "購入時の基準価額",
        min_value=0.0,
        value=0.0,
        step=100.0,
        help="購入後に入力してください"
    )

    # 現金
    st.subheader("💵 現金")
    cash_reserve = st.number_input(
        "待機資金（円）",
        min_value=0,
        max_value=10000000,
        value=100000,
        step=10000
    )

    st.markdown("---")
    st.caption("毎週日曜日にバフェット指数を更新")
    st.caption("シラーPERは自動更新（24時間キャッシュ）")

# データ取得
bonds = get_bond_yields()
vix_data = get_vix()
indices = get_major_indices()

# ========================================
# 1. マクロ経済指標
# ========================================
st.markdown('<div class="section-header">🌍 マクロ経済指標</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("### 🔴 債券利回り")
    st.metric("10年債利回り", f"{bonds['ten_year']:.2f}%")
    st.metric("2年債利回り（概算）", f"{bonds['two_year']:.2f}%")

    spread = bonds['spread']
    st.metric("イールドカーブ", f"{spread:.2f}%")

    if spread >= 0:
        st.success("✅ 正常範囲")
    else:
        st.error("⚠️ 逆イールド発生中")

with col2:
    st.markdown("### 😱 恐怖指数 (VIX)")
    vix_current = vix_data['current']
    st.metric("VIX指数", f"{vix_current:.2f}")

    if vix_current < 15:
        st.success("😊 楽観的")
        st.info("市場は安定。保有継続。")
    elif vix_current < 20:
        st.info("😐 中立")
        st.info("通常の変動範囲。")
    elif vix_current < 30:
        st.warning("😰 やや不安")
        st.warning("警戒が必要。")
    else:
        st.error("😱 パニック")
        st.error("🎯 買い増しチャンス！")

    # VIX推移グラフ
    if len(vix_data['history']) > 0:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=vix_data['history'],
            mode='lines+markers',
            line=dict(color='red', width=2),
            marker=dict(size=6)
        ))
        fig.update_layout(
            title="過去5日間のVIX推移",
            height=200,
            margin=dict(l=0, r=0, t=30, b=0),
            showlegend=False,
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

with col3:
    st.markdown("### 💰 バフェット指数")
    st.metric("バフェット指数 (%)", f"{buffett_indicator:.1f}%")

    if buffett_indicator > 200:
        st.error("🚨 歴史的割高")
        st.error("警戒！調整リスク大。")
    elif buffett_indicator > 180:
        st.warning("⚠️ 割高")
        st.warning("新規購入は慎重に。")
    elif buffett_indicator > 150:
        st.info("😐 やや割高")
    else:
        st.success("✅ 適正水準")

with col4:
    st.markdown("### 📊 シラーPER")
    st.metric("シラーPER (倍)", f"{shiller_pe:.1f}倍")

    if shiller_pe > 30:
        st.error("🚨 歴史的割高")
        st.error("期待リターン低め。")
    elif shiller_pe > 25:
        st.warning("⚠️ 割高")
        st.warning("慎重に投資。")
    elif shiller_pe > 20:
        st.info("😐 やや割高")
    elif shiller_pe > 15:
        st.success("✅ 適正水準")
    else:
        st.success("🎯 割安！")

# ========================================
# 2. 総合市場評価（米国株）
# ========================================
st.markdown('<div class="section-header">🎯 総合市場評価（米国株）</div>', unsafe_allow_html=True)

# スコア計算
market_score, score_details = calculate_market_score(
    buffett_indicator,
    shiller_pe,
    vix_data['current'],
    bonds['spread']
)

# 詳細判断取得
us_judgment = get_detailed_us_market_judgment(
    buffett_indicator,
    shiller_pe,
    vix_data['current'],
    bonds['spread'],
    market_score
)

# 2列レイアウト
col1, col2 = st.columns([1, 2])

with col1:
    # スコア表示
    st.metric("総合スコア", f"{market_score:+d} / 10")

    # 判定レベル表示
    if us_judgment['color'] == 'success':
        st.success(f"**{us_judgment['level']}**")
    elif us_judgment['color'] == 'info':
        st.info(f"**{us_judgment['level']}**")
    elif us_judgment['color'] == 'warning':
        st.warning(f"**{us_judgment['level']}**")
    else:
        st.error(f"**{us_judgment['level']}**")

with col2:
    # 各指標の詳細
    st.subheader("📊 各指標の評価")

    detail_data = []
    for indicator, value, evaluation, score_str in score_details:
        detail_data.append({
            '指標': indicator,
            '現在値': value,
            '評価': evaluation,
            'スコア': score_str
        })

    st.dataframe(
        pd.DataFrame(detail_data),
        use_container_width=True,
        hide_index=True
    )

# 詳細分析
with st.expander(f"🔍 詳細分析：{us_judgment['pattern']}", expanded=True):
    st.markdown(us_judgment['analysis'])
    st.markdown("---")
    st.markdown(us_judgment['recommendation'])

# ========================================
# 3. ポートフォリオ全体サマリー
# ========================================
st.markdown('<div class="section-header">💼 ポートフォリオ全体</div>', unsafe_allow_html=True)

# シクリカル株データ読込
cyclical_df = load_cyclical_portfolio()

# FANG+評価額計算
fang_current_value = fang_investment
fang_profit = 0
fang_profit_pct = 0

if fang_purchase_price > 0:
    # 実際にはQQQの価格を取得して計算
    qqq_data = get_stock_price('QQQ')
    if qqq_data['price'] > 0 and fang_purchase_price > 0:
        fang_current_value = fang_investment * (qqq_data['price'] / fang_purchase_price)
        fang_profit = fang_current_value - fang_investment
        fang_profit_pct = (fang_profit / fang_investment * 100)

# シクリカル株評価額計算
cyclical_total_cost = 0
cyclical_total_value = 0

if not cyclical_df.empty:
    for idx, row in cyclical_df.iterrows():
        ticker = str(row['銘柄コード']) + '.T'
        purchase_price = float(row['購入価格'])
        shares = float(row['購入株数'])
        cost = purchase_price * shares

        cyclical_total_cost += cost

        # 現在価格取得
        stock_data = get_stock_price(ticker)
        if stock_data['price'] > 0:
            current_value = stock_data['price'] * shares
            cyclical_total_value += current_value
        else:
            cyclical_total_value += cost

cyclical_profit = cyclical_total_value - cyclical_total_cost
cyclical_profit_pct = (cyclical_profit / cyclical_total_cost * 100) if cyclical_total_cost > 0 else 0

# 合計計算
total_investment = fang_investment + cyclical_total_cost + cash_reserve
total_value = fang_current_value + cyclical_total_value + cash_reserve
total_profit = total_value - total_investment
total_profit_pct = (total_profit / total_investment * 100) if total_investment > 0 else 0

# 表示
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "💰 合計資産",
        f"¥{total_value:,.0f}",
        f"{total_profit:+,.0f} ({total_profit_pct:+.2f}%)"
    )

with col2:
    profit_color = "positive" if fang_profit >= 0 else "negative"
    st.metric(
        "💎 FANG+",
        f"¥{fang_current_value:,.0f}",
        f"{fang_profit:+,.0f} ({fang_profit_pct:+.2f}%)"
    )

with col3:
    st.metric(
        "📊 シクリカル株",
        f"¥{cyclical_total_value:,.0f}",
        f"{cyclical_profit:+,.0f} ({cyclical_profit_pct:+.2f}%)"
    )

with col4:
    st.metric("💵 現金", f"¥{cash_reserve:,.0f}")

# 資産配分グラフ
fig = go.Figure(data=[go.Pie(
    labels=['FANG+', 'シクリカル株', '現金'],
    values=[fang_current_value, cyclical_total_value, cash_reserve],
    hole=0.4,
    marker=dict(colors=['#FF6B6B', '#4ECDC4', '#95E1D3'])
)])
fig.update_layout(
    title="資産配分",
    height=300,
    template="plotly_dark"
)
st.plotly_chart(fig, use_container_width=True)

# ========================================
# 4. シクリカル株詳細分析
# ========================================
st.markdown('<div class="section-header">📊 シクリカル株 詳細分析</div>', unsafe_allow_html=True)

# マクロ環境データ
macro_env = {
    'yield_curve': bonds['spread'],
    'buffett': buffett_indicator,
    'shiller': shiller_pe,
    'vix': vix_data['current']
}

# 詳細データ取得
detailed_stocks = get_cyclical_detailed_data()

if detailed_stocks:
    st.info(f"📊 保有銘柄：{len(detailed_stocks)}銘柄")

    # 各銘柄の詳細分析
    for stock_data in detailed_stocks:

        # 詳細判定実行
        judgment = get_detailed_cyclical_judgment(
            ticker_code=stock_data['ticker_code'],
            stock_name=stock_data['stock_name'],
            current_data={
                'per': stock_data['per'],
                'dividend_yield': stock_data['dividend_yield'],
                'equity_ratio': stock_data['equity_ratio'],
                'roe': stock_data['roe'],
                'price_position': stock_data['price_position']
            },
            macro_environment=macro_env
        )

        # 表示
        with st.expander(
                f"**{stock_data['ticker_code']} {stock_data['stock_name']}** - {judgment['level']} (スコア: {judgment['score']}点)",
                expanded=True
        ):
            # 基本情報
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "現在価格",
                    f"¥{stock_data['current_price']:,.0f}",
                    f"{stock_data['profit_pct']:+.1f}%"
                )

            with col2:
                st.metric("PER", f"{stock_data['per']:.1f}倍")

            with col3:
                st.metric("配当", f"{stock_data['dividend_yield']:.1f}%")

            with col4:
                st.metric("自己資本比率", f"{stock_data['equity_ratio']:.1f}%")

            # 詳細分析
            st.markdown(judgment['analysis'])

else:
    st.info("シクリカル株の保有データがありません。")

# ========================================
# 5. 主要指数
# ========================================
st.markdown('<div class="section-header">📈 主要指数</div>', unsafe_allow_html=True)

if indices:
    cols = st.columns(len(indices))
    for i, (name, data) in enumerate(indices.items()):
        with cols[i]:
            color = "positive" if data['change_pct'] >= 0 else "negative"
            st.metric(
                name,
                f"${data['price']:,.2f}" if name == 'QQQ' else f"{data['price']:,.2f}",
                f"{data['change_pct']:+.2f}%"
            )

# ========================================
# 6. 総合判定
# ========================================
st.markdown('<div class="section-header">🎯 総合判定</div>', unsafe_allow_html=True)

danger_level = calculate_danger_level(buffett_indicator, bonds['spread'], vix_data['current'])

col1, col2 = st.columns([1, 2])

with col1:
    st.metric("⚠️ 警戒レベル", f"{danger_level} / 9")

    if danger_level >= 7:
        st.error("🚨 最大警戒")
    elif danger_level >= 5:
        st.warning("⚠️ 高警戒")
    elif danger_level >= 3:
        st.info("😐 中警戒")
    else:
        st.success("✅ 低警戒")

with col2:
    st.subheader("💡 推奨アクション")

    if danger_level >= 7:
        st.error("🚨 即座に損切りを検討")
        st.write("- 全ポジションの見直し")
        st.write("- 現金比率を60%以上に")
    elif danger_level >= 5:
        st.warning("⚠️ 新規購入を一時停止")
        st.write("- 保有継続、追加購入は控える")
        st.write("- 現金を確保")
    elif danger_level >= 3:
        st.info("😐 慎重に行動")
        st.write("- 通常通り保有継続")
        st.write("- 追加購入は少額に")
    else:
        st.success("✅ 通常通り行動")
        st.write("- 保有継続")
        st.write("- 投資計画通りに実行")

    if vix_data['current'] > 30:
        st.success("🎯 VIX 30超え！買い増しチャンス")
        st.write(f"- 待機資金 ¥{cash_reserve:,.0f} の活用を検討")

# フッター
st.markdown("---")
st.caption("📌 このダッシュボードは投資判断の参考情報です。最終判断はご自身で行ってください。")