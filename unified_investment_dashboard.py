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

    # Google Sheets URL入力
    google_sheets_url_input = st.text_input(
        "Google Sheets CSV URL（任意）",
        value="",
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

    # シラーPER
    shiller_pe = st.number_input(
        "シラーPER (倍) ※手動入力",
        min_value=5.0,
        max_value=60.0,
        value=default_shiller,
        step=0.1,
        help="https://currentmarketvaluation.com/ で確認（Shiller PE Ratio）"
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

# データ取得
bonds = get_bond_yields()
vix_data = get_vix()
indices = get_major_indices()

# ========================================
# 1. マクロ経済指標
# ========================================
st.markdown('<div class="section-header">🌍 マクロ経済指標</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

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
        st.plotly_chart(fig, width="stretch")

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

# 4列目を追加（シラーPER）
st.markdown('<div class="section-header">🌍 マクロ経済指標</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

# col1とcol2は既存のまま（債券利回り、VIX）

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
# 2. ポートフォリオ全体サマリー
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
st.plotly_chart(fig, width="stretch")

# ========================================
# 3. シクリカル株詳細
# ========================================
st.markdown('<div class="section-header">📊 シクリカル株 詳細</div>', unsafe_allow_html=True)

if not cyclical_df.empty:
    # 詳細テーブル作成
    detail_rows = []

    for idx, row in cyclical_df.iterrows():
        ticker = str(row['銘柄コード']) + '.T'
        stock_name = row['銘柄名']
        purchase_price = float(row['購入価格'])
        shares = float(row['購入株数'])
        purchase_date = row['購入日']

        cost = purchase_price * shares

        # 現在価格取得
        stock_data = get_stock_price(ticker)
        current_price = stock_data['price'] if stock_data['price'] > 0 else purchase_price
        current_value = current_price * shares
        profit = current_value - cost
        profit_pct = (profit / cost * 100) if cost > 0 else 0

        detail_rows.append({
            '銘柄コード': row['銘柄コード'],
            '銘柄名': stock_name,
            '購入価格': f"¥{purchase_price:,.0f}",
            '現在価格': f"¥{current_price:,.0f}",
            '株数': int(shares),
            '取得額': f"¥{cost:,.0f}",
            '評価額': f"¥{current_value:,.0f}",
            '損益': f"¥{profit:+,.0f}",
            '損益率': f"{profit_pct:+.2f}%",
            '購入日': purchase_date
        })

    detail_df = pd.DataFrame(detail_rows)

    # カラーコーディング（損益率列のみ）
    def highlight_profit(s):
        """損益率列に色を付ける"""
        if s.name == '損益率':
            return ['background-color: #1a4d2e' if '+' in str(v)
                   else 'background-color: #4d1a1a' if '-' in str(v)
                   else '' for v in s]
        return ['' for _ in s]

    st.dataframe(
        detail_df.style.apply(highlight_profit),
        width="stretch",
        height=400
    )

    # 簡易売却シグナル
    st.subheader("🚨 売却シグナル")

    signals = []
    for idx, row in cyclical_df.iterrows():
        ticker = str(row['銘柄コード']) + '.T'
        stock_name = row['銘柄名']
        purchase_price = float(row['購入価格'])
        shares = float(row['購入株数'])
        cost = purchase_price * shares

        stock_data = get_stock_price(ticker)
        current_price = stock_data['price'] if stock_data['price'] > 0 else purchase_price
        current_value = current_price * shares
        profit_pct = ((current_value - cost) / cost * 100) if cost > 0 else 0

        # シグナル判定
        signal_level = 0
        signal_reasons = []

        # 損益率チェック
        if profit_pct <= -30:
            signal_level += 3
            signal_reasons.append("⚠️ 損切りライン（-30%以下）")
        elif profit_pct >= 30:
            signal_level += 2
            signal_reasons.append("💰 利益確定ライン（+30%以上）")

        # 変動率チェック
        if abs(stock_data['change_pct']) > 5:
            signal_level += 1
            signal_reasons.append(f"📈 大幅変動（{stock_data['change_pct']:+.2f}%）")

        if signal_level > 0:
            signals.append({
                '銘柄': f"{row['銘柄コード']} {stock_name}",
                'シグナル強度': signal_level,
                '理由': ' / '.join(signal_reasons),
                '損益率': f"{profit_pct:+.2f}%"
            })

    if signals:
        signal_df = pd.DataFrame(signals)
        signal_df = signal_df.sort_values('シグナル強度', ascending=False)

        st.dataframe(
            signal_df,
            width="stretch",
            hide_index=True
        )
    else:
        st.success("✅ 現在、売却シグナルはありません。保有継続。")

else:
    st.info("シクリカル株の保有データがありません。")

# ========================================
# 4. 主要指数
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
# 5. 総合判定
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
