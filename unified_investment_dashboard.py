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

# たーちゃん哲学2.0 - 売却目標価格自動推定
try:
    from auto_per_estimator import get_target_prices_auto, clear_cache, load_cache
    TARGET_PRICES_AVAILABLE = True
except ImportError:
    TARGET_PRICES_AVAILABLE = False

# FANG+ 管理モジュール
try:
    from fang_manager import get_fang_current_price, calc_fang_summary, add_fang_purchase, load_fang_purchases
    FANG_MODULE_OK = True
except ImportError:
    FANG_MODULE_OK = False

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

@st.cache_data(ttl=3600)
def get_stock_fundamentals(ticker):
    """PERとEPSを取得（たーちゃん哲学2.0用）"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        per = info.get('trailingPE') or info.get('forwardPE') or 0
        eps = info.get('trailingEps') or info.get('forwardEps') or 0
        # 文字列が混入している場合の対応
        try:
            per = float(per) if per else 0
            eps = float(eps) if eps else 0
        except (ValueError, TypeError):
            per, eps = 0, 0
        # EPSが取れない場合は現在価格/PERで逆算
        if (not eps or eps <= 0) and per > 0:
            price_data = get_stock_price(ticker)
            if price_data['price'] > 0:
                eps = round(price_data['price'] / per, 2)
        return {'per': per, 'eps': eps}
    except Exception:
        return {'per': 0, 'eps': 0}

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

    # Secretsからデフォルト URLを取得（設定されていない場合は空文字列）
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

    # バフェット指数
    buffett_indicator = st.number_input(
        "バフェット指数 (%) ※手動入力",
        min_value=50.0,
        max_value=300.0,
        value=200.0,
        step=1.0,
        help="https://currentmarketvaluation.com/ で確認"
    )

    # バフェット指数確認ボタン
    st.link_button(
        "📊 バフェット指数を確認",
        "https://currentmarketvaluation.com/",
        use_container_width=True,
        type="primary"
    )

    st.caption("💡 毎週日曜日に更新してください")

    st.markdown("---")

    # FANG+設定
    st.subheader("💎 FANG+インデックス")

    if FANG_MODULE_OK:
        # 基準価額の自動取得ボタン
        if st.button("📡 最新基準価額を取得", use_container_width=True,
                     help="Yahoo!ファイナンスからiFreeNEXT FANG+の基準価額を取得します"):
            with st.spinner("Yahoo!ファイナンスから取得中..."):
                _auto_price = get_fang_current_price()
            if _auto_price > 0:
                st.session_state["fang_price_auto"] = _auto_price
                st.success(f"✅ 取得成功: ¥{_auto_price:,.0f}")
            else:
                st.warning("⚠️ 自動取得失敗。手動で入力してください。")

        # 表示用: 取得済み価格を表示
        _auto_price_disp = st.session_state.get("fang_price_auto", 0.0)
        if _auto_price_disp > 0:
            st.caption(f"取得済み基準価額: ¥{_auto_price_disp:,.0f}")

        # 手動入力（自動取得失敗時のバックアップ）
        fang_manual_price = st.number_input(
            "現在の基準価額（手動・任意）",
            min_value=0.0,
            value=0.0,
            step=100.0,
            help="自動取得が失敗した場合に手動で入力してください"
        )

        # 積立購入を追加するフォーム
        with st.expander("➕ 積立購入を追加"):
            _col1, _col2 = st.columns(2)
            with _col1:
                _new_date   = st.date_input("購入日", value=None, key="fang_new_date")
                _new_amount = st.number_input("投資額（円）", min_value=0, step=10000, key="fang_new_amount")
            with _col2:
                _new_price  = st.number_input("取得単価（基準価額）", min_value=0.0, step=100.0, key="fang_new_price")
                _new_memo   = st.text_input("メモ（任意）", key="fang_new_memo")
            if st.button("💾 購入履歴を追加", use_container_width=True, key="fang_add_btn"):
                if _new_date and _new_amount > 0 and _new_price > 0:
                    add_fang_purchase(
                        str(_new_date), _new_amount, _new_price, _new_memo
                    )
                    st.success(f"追加しました: ¥{_new_amount:,.0f} @ ¥{_new_price:,.0f}")
                    st.rerun()
                else:
                    st.error("購入日・投資額・取得単価をすべて入力してください。")

        # 購入履歴の表示
        _hist_df = load_fang_purchases()
        if not _hist_df.empty:
            with st.expander("📋 購入履歴を確認"):
                st.dataframe(_hist_df, use_container_width=True, hide_index=True)

        # サマリー計算（ダッシュボード本体で使う変数を設定）
        _manual = fang_manual_price
        _auto   = st.session_state.get("fang_price_auto", 0.0)
        _use_price = _auto if _auto > 0 else _manual
        _fang_summary = calc_fang_summary(current_price=_use_price)

        # ダッシュボード計算用変数（後段で使用）
        fang_investment    = _fang_summary["total_investment"]
        fang_current_value = _fang_summary["current_value"]
        fang_profit        = _fang_summary["profit"]
        fang_profit_pct    = _fang_summary["profit_pct"]
        fang_purchase_price = _fang_summary["avg_cost"]  # 後段の互換性のため残す

    else:
        # fang_manager.py が見つからない場合は旧来の手動入力
        st.warning("⚠️ fang_manager.py が見つかりません。")
        fang_investment = st.number_input(
            "投資額（円）", min_value=0, max_value=10000000, value=100000, step=10000
        )
        fang_purchase_price = st.number_input(
            "購入時の基準価額", min_value=0.0, value=0.0, step=100.0,
            help="購入後に入力してください"
        )
        fang_current_value = fang_investment
        fang_profit        = 0.0
        fang_profit_pct    = 0.0

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

    # ---- シクリカル株 購入・売却記録 ----
    st.markdown("---")
    st.subheader("📊 シクリカル株 記録")

    try:
        from cyclical_purchase_manager import (
            add_cyclical_purchase, get_purchase_history, delete_last_purchase
        )
        PURCHASE_MODULE_OK = True
    except ImportError:
        PURCHASE_MODULE_OK = False

    if PURCHASE_MODULE_OK:
        with st.expander("➕ 購入記録を追加"):
            p_date   = st.date_input("購入日", key="p_date")
            p_code   = st.text_input("銘柄コード（4桁）", placeholder="例: 9127", key="p_code")
            p_name   = st.text_input("企業名", placeholder="例: Tamai Steamship", key="p_name")
            p_price  = st.number_input("購入単価（円）", min_value=0.0, step=1.0, key="p_price")
            p_shares = st.number_input("購入株数", min_value=0, step=1, key="p_shares")
            p_memo   = st.text_input("メモ（任意）", key="p_memo")
            if p_price > 0 and p_shares > 0:
                st.caption(f"💰 投資額: ¥{int(p_price * p_shares):,}")
            if st.button("💾 追加して保存", use_container_width=True, key="p_save"):
                if p_code and p_name and p_price > 0 and p_shares > 0:
                    ok = add_cyclical_purchase(
                        str(p_date), p_code, p_name, p_price, p_shares, p_memo
                    )
                    if ok:
                        st.success(f"✅ {p_name}（{p_code}）{p_shares}株 @ ¥{p_price:,.0f} を記録しました")
                        st.rerun()
                    else:
                        st.error("❌ 保存失敗。Secrets の gcp_service_account を確認してください。")
                else:
                    st.error("銘柄コード・企業名・単価・株数をすべて入力してください。")

        with st.expander("🗑️ 最後の記録を取り消す"):
            st.warning("直前に追加した購入記録を1件削除します。")
            if st.button("取り消す", use_container_width=True, key="p_delete"):
                ok = delete_last_purchase()
                if ok:
                    st.success("✅ 最後の記録を削除しました")
                    st.rerun()
                else:
                    st.error("削除失敗またはデータがありません")

        with st.expander("📋 購入履歴を確認"):
            hist = get_purchase_history()
            if hist.empty:
                st.info("購入履歴がありません")
            else:
                st.dataframe(hist, use_container_width=True, hide_index=True)
                st.caption(f"合計 {len(hist)} 件")
    else:
        st.warning("⚠️ cyclical_purchase_manager.py が見つかりません")

    # ---- 売却目標価格キャッシュ管理 ----
    if TARGET_PRICES_AVAILABLE:

        st.markdown("---")
        st.subheader("🎯 売却目標価格")
        cache = load_cache()
        if cache:
            oldest = min(
                (v["cached_at"] for v in cache.values() if "cached_at" in v),
                default=None,
            )
            days_old = (datetime.now() - oldest).days if oldest else "-"
            st.caption(f"キャッシュ: {len(cache)}銘柄 / 更新{days_old}日前")
        else:
            st.caption("キャッシュ: なし")
        if st.button("🔄 キャッシュを更新", use_container_width=True):
            clear_cache()
            st.success("削除しました。再読み込みで再計算されます。")
            st.rerun()
        st.caption("※ 7日間有効。銘柄追加後に更新推奨。")

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

# ========================================
# 2. ポートフォリオ全体サマリー
# ========================================
st.markdown('<div class="section-header">💼 ポートフォリオ全体</div>', unsafe_allow_html=True)

# シクリカル株データ読込
cyclical_df = load_cyclical_portfolio()

# FANG+評価額計算
# fang_manager統合済みの場合はサイドバーで既に計算されている
# 未統合（FANG_MODULE_OK=False）の場合のみここで旧来計算を行う
if not FANG_MODULE_OK:
    fang_current_value = fang_investment
    fang_profit = 0
    fang_profit_pct = 0
    if fang_purchase_price > 0:
        qqq_data = get_stock_price('QQQ')
        if qqq_data['price'] > 0:
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
# 3-2. 売却目標価格（たーちゃん哲学2.0）
# ========================================
st.markdown('<div class="section-header">🎯 売却目標価格</div>', unsafe_allow_html=True)

if not TARGET_PRICES_AVAILABLE:
    st.warning("⚠️ auto_per_estimator.py が見つかりません。リポジトリに追加してください。")
elif cyclical_df.empty:
    st.info("シクリカル株の保有データがありません。")
else:
    st.caption(
        "過去52週の株価データから銘柄ごとに現実的な売却目標価格を推定。"
        "各銘柄の特性に合わせた個別最適化目標を3段階で表示。"
    )

    # NTT除外オプション
    show_ntt = st.checkbox("NTT（長期配当ホールド）も含める", value=False, key="show_ntt")

    # 計算対象を決定
    target_df = cyclical_df.copy()
    if not show_ntt:
        target_df = target_df[target_df['銘柄コード'].astype(str) != '9432']

    if target_df.empty:
        st.info("表示対象の銘柄がありません（NTTを含める場合はチェックを入れてください）。")
    else:
        # ---- サマリーテーブル ----
        st.subheader("📊 全銘柄サマリー")

        summary_rows = []
        all_targets = {}   # ticker(コードのみ) → result

        progress = st.progress(0, text="目標価格を計算中...")

        for i, (_, row) in enumerate(target_df.iterrows()):
            ticker_code = str(int(row['銘柄コード']))
            ticker_full = ticker_code + '.T'
            name = row['銘柄名']
            purchase_price = float(row['購入価格'])

            progress.progress((i + 1) / len(target_df), text=f"計算中: {name}...")

            # 現在価格
            stock_data = get_stock_price(ticker_full)
            current_price = stock_data['price'] if stock_data['price'] > 0 else purchase_price

            # PER / EPS
            fundamentals = get_stock_fundamentals(ticker_full)
            per = fundamentals['per']
            eps = fundamentals['eps']

            if not per or per <= 0 or not eps or eps <= 0:
                summary_rows.append({
                    '銘柄': f"{name}（{ticker_code}）",
                    '現在価格': f"¥{current_price:,.0f}",
                    '現在PER': '-',
                    '🟡 保守的': '-',
                    '🟢 標準': '-',
                    '🚀 楽観的': '-',
                    '信頼度': '-',
                })
                continue

            try:
                result = get_target_prices_auto(ticker_code, current_price, per, eps, name)
                all_targets[ticker_code] = {
                    'result': result,
                    'current_price': current_price,
                    'per': per,
                    'name': name,
                }
                t = result['targets']
                pct_to_t1 = (t[0]['price'] - current_price) / current_price * 100

                alert = ''
                if pct_to_t1 <= 5:
                    alert = ' 🚨'
                elif pct_to_t1 <= 15:
                    alert = ' ⚠️'

                summary_rows.append({
                    '銘柄': f"{name}（{ticker_code}）",
                    '現在価格': f"¥{current_price:,.0f}",
                    '現在PER': f"{per:.1f}倍",
                    '🟡 保守的': f"¥{t[0]['price']:,.0f}  (+{t[0]['return_pct']}%){alert}",
                    '🟢 標準': f"¥{t[1]['price']:,.0f}  (+{t[1]['return_pct']}%)",
                    '🚀 楽観的': f"¥{t[2]['price']:,.0f}  (+{t[2]['return_pct']}%)",
                    '信頼度': f"{result['confidence']}%",
                })
            except Exception as e:
                summary_rows.append({
                    '銘柄': f"{name}（{ticker_code}）",
                    '現在価格': f"¥{current_price:,.0f}",
                    '現在PER': f"{per:.1f}倍",
                    '🟡 保守的': f"エラー: {e}",
                    '🟢 標準': '-',
                    '🚀 楽観的': '-',
                    '信頼度': '-',
                })

        progress.empty()

        if summary_rows:
            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                hide_index=True,
            )

        # 読み方説明
        with st.expander("📖 売却戦略の読み方"):
            st.markdown("""
| 段階 | タイミング | 売却比率 | 考え方 |
|------|-----------|---------|--------|
| 🟡 保守的 | 最初の利確 | **40%** | 過去52週高値レベル。ほぼ確実に到達可能。ここで4割を確定。 |
| 🟢 標準 | メインの利確 | **40%** | 景気回復時の現実的な天井。ここで大部分を確定。 |
| 🚀 楽観的 | 残りの利確 | **20%** | 景気ピーク時のベストケース。残り2割で最大リターンを狙う。 |

⚠️ 保守的目標に近づいたら Code 5 のシグナルも確認すること。
            """)

        st.markdown("---")

        # ---- 銘柄別詳細 ----
        if all_targets:
            st.subheader("🔍 銘柄別詳細")

            tab_names = [v['name'] for v in all_targets.values()]
            tabs = st.tabs(tab_names)

            for tab, (ticker_code, data) in zip(tabs, all_targets.items()):
                with tab:
                    result = data['result']
                    current_price = data['current_price']
                    per = data['per']

                    # メタ情報
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        conf = result['confidence']
                        badge = "🟢" if conf >= 70 else "🟡" if conf >= 50 else "🔴"
                        st.metric("信頼度", f"{badge} {conf}%")
                    with c2:
                        st.metric("推定方法", result['estimation_method'])
                    with c3:
                        if '52w_data' in result:
                            d = result['52w_data']
                            st.metric(
                                "52週高値",
                                f"¥{d['high']:,.0f}",
                                f"PER {d['high_per']}倍",
                            )

                    st.caption(f"根拠: {result['reason']}")
                    st.markdown("")

                    # 3段階の目標カード
                    cols = st.columns(3)
                    icons = ['🟡', '🟢', '🚀']

                    for col, target, icon in zip(cols, result['targets'], icons):
                        with col:
                            pct_to_target = (target['price'] - current_price) / current_price * 100
                            if pct_to_target <= 5:
                                status = "🚨 目標到達圏"
                            elif pct_to_target <= 20:
                                status = "⚠️ 目標接近中"
                            else:
                                status = f"残り +{pct_to_target:.0f}%"

                            st.metric(
                                label=f"{icon} {target['level']}（{target['timeframe']}）",
                                value=f"¥{target['price']:,.0f}",
                                delta=f"+{target['return_pct']}%",
                            )
                            st.caption(
                                f"目標PER: **{target['per']}倍** ／ 売却: {target['sell_ratio']}%  \n{status}"
                            )

                    # 売却ガイド
                    st.markdown("")
                    t = result['targets']
                    st.info(
                        f"**{result['name']} 売却ガイド**\n\n"
                        f"① 🟡 ¥{t[0]['price']:,.0f} 到達 → **{t[0]['sell_ratio']}%売却**（{t[0]['timeframe']}）\n\n"
                        f"② 🟢 ¥{t[1]['price']:,.0f} 到達 → **{t[1]['sell_ratio']}%売却**（{t[1]['timeframe']}）\n\n"
                        f"③ 🚀 ¥{t[2]['price']:,.0f} 到達 → **{t[2]['sell_ratio']}%売却・全売却**（{t[2]['timeframe']}）\n\n"
                        "⚠️ Code 5 でシグナル強度 6点以上 → 目標未達でも売却を検討"
                    )

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
