import requests
from bs4 import BeautifulSoup
import re


def get_shiller_pe():
    """multpl.comからシラーPERを自動取得"""
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

        # シラーPERの値を抽出
        current_value = soup.find('div', id='current')

        if current_value:
            shiller_text = current_value.get_text().strip()

            # 正規表現で数値を抽出（例: 40.30）
            match = re.search(r'\d+\.\d+', shiller_text)

            if match:
                shiller_pe = float(match.group())
                print(f"✅ シラーPER取得成功: {shiller_pe}倍")
                return shiller_pe
            else:
                print(f"❌ 数値が見つかりません: {shiller_text}")
                return None
        else:
            print("❌ シラーPERの要素が見つかりません")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ ネットワークエラー: {e}")
        return None
    except ValueError as e:
        print(f"❌ 数値変換エラー: {e}")
        return None
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        return None


if __name__ == "__main__":
    print("シラーPER取得テスト開始...")
    print("-" * 50)

    shiller = get_shiller_pe()

    if shiller:
        print("-" * 50)
        print(f"📊 現在のシラーPER: {shiller}倍")
        print("-" * 50)

        if shiller > 35:
            print("🚨 評価: 歴史的割高")
        elif shiller > 30:
            print("⚠️ 評価: かなり割高")
        elif shiller > 25:
            print("😐 評価: 割高")
        elif shiller > 20:
            print("😊 評価: やや割高")
        elif shiller > 15:
            print("✅ 評価: 適正")
        else:
            print("🎯 評価: 割安")
    else:
        print("❌ 取得失敗")
        print("デフォルト値 30.0 を使用します")