"""
auto_per_estimator.py
過去52週データから現実的なPER天井を自動推定し、3段階の売却目標価格を計算する
たーちゃん哲学2.0 - 銘柄ごとの個別最適化売却目標
"""

import yfinance as yf
import pandas as pd
import pickle
import os
from datetime import datetime, timedelta


# キャッシュファイルパス
CACHE_FILE = "target_prices_cache.pkl"
CACHE_VALIDITY_DAYS = 7


def load_cache():
    """キャッシュを読み込む"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    """キャッシュを保存する"""
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(cache, f)
    except Exception as e:
        print(f"キャッシュ保存エラー: {e}")


def is_cache_valid(cache_entry):
    """キャッシュが有効期限内かチェック（7日間）"""
    if "cached_at" not in cache_entry:
        return False
    cached_at = cache_entry["cached_at"]
    return datetime.now() - cached_at < timedelta(days=CACHE_VALIDITY_DAYS)


def calculate_confidence(hist, volatility, historical_max_per, current_per):
    """推定の信頼度を計算（0-100%）"""
    score = 50  # ベーススコア

    # データポイント数（多いほど信頼度UP）
    data_points = len(hist)
    if data_points >= 200:
        score += 20
    elif data_points >= 100:
        score += 10
    elif data_points < 50:
        score -= 20

    # ボラティリティ（低いほど信頼度UP）
    if volatility < 0.015:
        score += 15
    elif volatility < 0.025:
        score += 5
    elif volatility > 0.04:
        score -= 15

    # 現在PERと歴史的最高PERの関係
    if current_per > 0 and historical_max_per > 0:
        ratio = historical_max_per / current_per
        if ratio > 2.0:
            score += 10  # 大きな上昇余地あり
        elif ratio < 1.2:
            score -= 10  # すでに高値圏

    return max(10, min(95, score))


def estimate_timeframes(current_per, conservative_per, standard_per, optimistic_per):
    """達成時期を推定"""
    def per_to_timeframe(current, target):
        ratio = target / current if current > 0 else 2.0
        if ratio <= 1.3:
            return "6ヶ月〜1年"
        elif ratio <= 1.8:
            return "1〜2年"
        elif ratio <= 2.5:
            return "2〜3年"
        else:
            return "3〜5年"

    return [
        per_to_timeframe(current_per, conservative_per),
        per_to_timeframe(current_per, standard_per),
        per_to_timeframe(current_per, optimistic_per),
    ]


def get_default_targets(current_per, eps, current_price=None):
    """データ取得失敗時のデフォルト目標"""
    conservative_per = min(current_per * 1.5, 7.0)
    standard_per = min(current_per * 2.0, 10.0)
    optimistic_per = min(current_per * 2.5, 12.0)

    result = {
        "ticker": "N/A",
        "current_per": current_per,
        "eps": eps,
        "target_per_conservative": round(conservative_per, 1),
        "target_per_standard": round(standard_per, 1),
        "target_per_optimistic": round(optimistic_per, 1),
        "sell_ratio_1": 0.40,
        "sell_ratio_2": 0.40,
        "sell_ratio_3": 0.20,
        "timeframe_conservative": "1〜2年",
        "timeframe_standard": "2〜3年",
        "timeframe_optimistic": "3〜5年",
        "reason": "データ取得不可のためデフォルト推定（PER×1.5/2.0/2.5倍）",
        "confidence": 30,
        "estimation_method": "デフォルト推定",
    }

    if current_price and eps and eps > 0:
        result["target_price_conservative"] = round(conservative_per * eps, 0)
        result["target_price_standard"] = round(standard_per * eps, 0)
        result["target_price_optimistic"] = round(optimistic_per * eps, 0)

    return result


def estimate_realistic_per_ceiling(ticker, current_per, eps, current_price):
    """
    過去52週データから現実的なPER天井を自動推定

    Args:
        ticker (str): 銘柄コード（例: '1848'）
        current_per (float): 現在のPER
        eps (float): 予想EPS
        current_price (float): 現在価格

    Returns:
        dict: 推定された目標価格情報
    """
    try:
        stock = yf.Ticker(f"{ticker}.T")
        hist = stock.history(period="1y")

        if hist.empty or eps == 0:
            return get_default_targets(current_per, eps, current_price)

        high_52w = hist["High"].max()
        low_52w = hist["Low"].min()
        historical_max_per = high_52w / eps
        volatility = hist["Close"].pct_change().std()

        # 現実的な天井PERを計算
        # 保守的: 過去最高PERの1.2倍（ほぼ確実に到達可能）
        conservative_per = min(historical_max_per * 1.2, 10.0)
        # 標準: 過去最高PERの1.5倍（景気回復時に到達可能）
        standard_per = min(historical_max_per * 1.5, 12.0)
        # 楽観的: 過去最高PERの2.0倍（景気ピーク時）
        optimistic_per = min(historical_max_per * 2.0, 15.0)

        # 現在値より低い場合は調整
        conservative_per = max(conservative_per, current_per * 1.5)
        standard_per = max(standard_per, current_per * 2.0)
        optimistic_per = max(optimistic_per, current_per * 2.5)

        confidence = calculate_confidence(hist, volatility, historical_max_per, current_per)
        timeframes = estimate_timeframes(current_per, conservative_per, standard_per, optimistic_per)

        return {
            "ticker": ticker,
            "current_per": current_per,
            "eps": eps,
            "target_per_conservative": round(conservative_per, 1),
            "target_per_standard": round(standard_per, 1),
            "target_per_optimistic": round(optimistic_per, 1),
            "target_price_conservative": round(conservative_per * eps, 0),
            "target_price_standard": round(standard_per * eps, 0),
            "target_price_optimistic": round(optimistic_per * eps, 0),
            "sell_ratio_1": 0.40,
            "sell_ratio_2": 0.40,
            "sell_ratio_3": 0.20,
            "timeframe_conservative": timeframes[0],
            "timeframe_standard": timeframes[1],
            "timeframe_optimistic": timeframes[2],
            "reason": f"過去52週最高PER {historical_max_per:.1f}倍を基準に自動推定",
            "confidence": confidence,
            "52w_high": round(high_52w, 0),
            "52w_low": round(low_52w, 0),
            "52w_high_per_estimate": round(historical_max_per, 1),
            "estimation_method": "自動推定（過去52週データ）",
        }

    except Exception as e:
        print(f"PER推定エラー ({ticker}): {e}")
        return get_default_targets(current_per, eps, current_price)


def get_target_prices_auto(ticker, current_price, current_per, eps, stock_name="", use_cache=True):
    """
    銘柄の3段階売却目標価格を返す（キャッシュ対応）

    Args:
        ticker (str): 銘柄コード
        current_price (float): 現在価格
        current_per (float): 現在PER
        eps (float): EPS
        stock_name (str): 銘柄名（表示用）
        use_cache (bool): キャッシュを使用するか

    Returns:
        dict: {
            'name': str,
            'current_per': float,
            'targets': [
                {'level': '保守的', 'per': float, 'price': float,
                 'return_pct': float, 'sell_ratio': int, 'timeframe': str},
                ...
            ],
            'reason': str,
            'confidence': int,
            'estimation_method': str,
        }
    """
    cache = load_cache() if use_cache else {}
    cache_key = f"{ticker}_{int(eps)}"

    # キャッシュ確認
    if cache_key in cache and is_cache_valid(cache.get(cache_key, {})):
        cached = cache[cache_key]
        estimated = cached.get("data", {})
    else:
        # 新規推定
        estimated = estimate_realistic_per_ceiling(ticker, current_per, eps, current_price)
        cache[cache_key] = {
            "data": estimated,
            "cached_at": datetime.now(),
        }
        save_cache(cache)

    # 結果を整形
    result = {
        "name": stock_name or ticker,
        "ticker": ticker,
        "current_per": current_per,
        "targets": [
            {
                "level": "保守的",
                "per": estimated["target_per_conservative"],
                "price": estimated.get("target_price_conservative", round(estimated["target_per_conservative"] * eps, 0)),
                "return_pct": round((estimated.get("target_price_conservative", estimated["target_per_conservative"] * eps) / current_price - 1) * 100, 1) if current_price else 0,
                "sell_ratio": int(estimated["sell_ratio_1"] * 100),
                "timeframe": estimated["timeframe_conservative"],
            },
            {
                "level": "標準",
                "per": estimated["target_per_standard"],
                "price": estimated.get("target_price_standard", round(estimated["target_per_standard"] * eps, 0)),
                "return_pct": round((estimated.get("target_price_standard", estimated["target_per_standard"] * eps) / current_price - 1) * 100, 1) if current_price else 0,
                "sell_ratio": int(estimated["sell_ratio_2"] * 100),
                "timeframe": estimated["timeframe_standard"],
            },
            {
                "level": "楽観的",
                "per": estimated["target_per_optimistic"],
                "price": estimated.get("target_price_optimistic", round(estimated["target_per_optimistic"] * eps, 0)),
                "return_pct": round((estimated.get("target_price_optimistic", estimated["target_per_optimistic"] * eps) / current_price - 1) * 100, 1) if current_price else 0,
                "sell_ratio": int(estimated["sell_ratio_3"] * 100),
                "timeframe": estimated["timeframe_optimistic"],
            },
        ],
        "reason": estimated["reason"],
        "confidence": estimated["confidence"],
        "estimation_method": estimated.get("estimation_method", "自動推定"),
    }

    if "52w_high" in estimated:
        result["52w_data"] = {
            "high": estimated["52w_high"],
            "low": estimated["52w_low"],
            "high_per": estimated["52w_high_per_estimate"],
        }

    return result


def clear_cache(ticker=None):
    """キャッシュをクリアする。ticker指定で個別削除、Noneで全削除"""
    if ticker is None:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print("キャッシュを全削除しました")
    else:
        cache = load_cache()
        keys_to_delete = [k for k in cache.keys() if k.startswith(f"{ticker}_")]
        for k in keys_to_delete:
            del cache[k]
        save_cache(cache)
        print(f"{ticker} のキャッシュを削除しました")


if __name__ == "__main__":
    # テスト実行
    test_cases = [
        ("1848", 650, 4.1, 158.5, "Fuji P.S Corporation"),
        ("9385", 836, 4.9, 170.6, "Shoei Corporation"),
        ("9127", 4465, 5.0, 893.0, "Tamai Steamship"),
        ("5445", 6410, 4.9, 1308.2, "Tokyo Tekko"),
        ("4611", 1494, 4.8, 311.3, "Dai Nippon Toryo"),
        ("7991", 1504, 3.7, 406.5, "Mamiya-OP"),
    ]

    for ticker, price, per, eps, name in test_cases:
        result = get_target_prices_auto(ticker, price, per, eps, name)
        print(f"\n{'='*55}")
        print(f"  {result['name']} ({ticker})")
        print(f"  現在PER: {per}倍 | 現在価格: ¥{price:,}")
        print(f"  推定方法: {result['estimation_method']} | 信頼度: {result['confidence']}%")
        print(f"  根拠: {result['reason']}")
        if "52w_data" in result:
            d = result["52w_data"]
            print(f"  52週高値: ¥{d['high']:,.0f} (PER {d['high_per']}倍)")
        print()
        for t in result["targets"]:
            arrow = "🟢" if t["return_pct"] >= 80 else "🟡" if t["return_pct"] >= 40 else "⚪"
            print(f"  {arrow} [{t['level']}・{t['timeframe']}]")
            print(f"     目標PER {t['per']}倍 → ¥{t['price']:,.0f}  (+{t['return_pct']}%)  売却{t['sell_ratio']}%")
