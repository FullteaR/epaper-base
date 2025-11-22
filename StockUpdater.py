from ImageUpdater import ImageUpdater
import yfinance as yf
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

class StockUpdater(ImageUpdater):

    def __init__(self):
        super().__init__()
        
        self.FONT_BOLD_PATH = "./fonts/NotoSansJP-Bold.ttf"
        self.FONT_REG_PATH = "./fonts/NotoSansJP-Regular.ttf"
        
        # 設定: 銘柄、名称、単位、単位の位置(prefix/suffix)
        self.SCREENS_CONFIG = [
            # Screen 1: クリプト & コモディティ & GS
            [
                {"ticker": "BTC-USD", "name": "Bitcoin",       "unit": "$",  "pos": "prefix"},
                {"ticker": "GS",      "name": "Goldman Sachs", "unit": "$",  "pos": "prefix"}, # ETH -> GS
                {"ticker": "GC=F",    "name": "Gold (金)",      "unit": "$",  "pos": "prefix"},
                {"ticker": "CL=F",    "name": "Crude Oil",     "unit": "$",  "pos": "prefix"},
            ],
            # Screen 2: 米国 & 欧州
            [
                {"ticker": "^GSPC",   "name": "S&P 500",       "unit": "pt", "pos": "suffix"}, # 指数はpt表記が一般的
                {"ticker": "^IXIC",   "name": "NASDAQ",        "unit": "pt", "pos": "suffix"},
                {"ticker": "^DJI",    "name": "NYダウ",         "unit": "$",  "pos": "prefix"}, # ダウはドル表記も多い
                {"ticker": "^FTSE",   "name": "FTSE 100",      "unit": "pt", "pos": "suffix"},
            ],
            # Screen 3: 日本 & 為替
            [
                {"ticker": "^N225",   "name": "日経平均",       "unit": "円", "pos": "suffix"},
                {"ticker": "1306.T",  "name": "TOPIX (ETF)",   "unit": "円", "pos": "suffix"},
                {"ticker": "JPY=X",   "name": "USD/JPY",       "unit": "円", "pos": "suffix"},
                {"ticker": "EURJPY=X","name": "EUR/JPY",       "unit": "円", "pos": "suffix"},
            ]
        ]

    def fetch_data(self):
        print("Fetching market data...")
        all_tickers = []
        for screen in self.SCREENS_CONFIG:
            for item in screen:
                all_tickers.append(item["ticker"])
        
        # 1ヶ月分、日足
        data = yf.download(all_tickers, period="1mo", interval="1d", progress=False)['Close']
        return data

    def format_value(self, value, unit, pos):
        """数値を単位付きの文字列に変換するヘルパー"""
        # 小数点以下の桁数調整
        if value >= 1000:
            val_str = f"{value:,.0f}"
        else:
            val_str = f"{value:,.2f}"

        if pos == "prefix":
            return f"{unit}{val_str}"
        else:
            return f"{val_str}{unit}"

    def draw_detailed_chart(self, draw, rect, series, config):
        """詳細チャート描画 (単位対応版)"""
        x_base, y_base, box_w, box_h = rect
        name = config["name"]
        unit = config["unit"]
        pos  = config["pos"]
        
        series = series.dropna()
        if len(series) < 2:
            draw.text((x_base+10, y_base+10), f"{name}: No Data", fill=(0,0,0))
            return

        prices = series.tolist()
        dates = series.index
        
        curr_price = prices[-1]
        start_price = prices[0]
        diff = curr_price - start_price
        pct = (diff / start_price) * 100
        
        trend_color = (220, 60, 60) if diff >= 0 else (46, 160, 80)
        bg_tint = (255, 250, 250) if diff >= 0 else (250, 255, 250)
        
        # 背景
        draw.rectangle((x_base, y_base, x_base+box_w, y_base+box_h), fill=bg_tint, outline=(200,200,200))

        # レイアウト
        padding_top = 50
        padding_btm = 30
        padding_left = 10
        padding_right = 70 # 単位が入るので少し広めに

        gw = box_w - padding_left - padding_right
        gh = box_h - padding_top - padding_btm
        gx = x_base + padding_left
        gy = y_base + padding_top

        # スケール
        p_max = max(prices)
        p_min = min(prices)
        margin = (p_max - p_min) * 0.1
        if margin == 0: margin = 1
        p_max += margin
        p_min -= margin

        def map_y(val):
            return gy + gh - (val - p_min) / (p_max - p_min) * gh
        def map_x(i):
            return gx + i * (gw / (len(prices) - 1))

        f_axis = ImageFont.truetype(self.FONT_REG_PATH, 14)
        f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 22)
        f_val   = ImageFont.truetype(self.FONT_BOLD_PATH, 22)
        f_pct   = ImageFont.truetype(self.FONT_REG_PATH, 18)

        # ==== Y軸 (単位付き) ====
        steps = 3
        for i in range(steps):
            ratio = i / (steps - 1)
            val = p_min + (p_max - p_min) * ratio
            y = map_y(val)
            
            draw.line([(gx, y), (gx+gw, y)], fill=(220, 220, 220), width=1)
            
            # 軸ラベルにも単位をつける（スペース節約のためPrefixのみにするか、そのままつけるか）
            # ここではシンプルにそのままつけます
            axis_str = self.format_value(val, unit, pos)
            draw.text((gx + gw + 5, y - 8), axis_str, font=f_axis, fill=(150, 150, 150))

        # ==== X軸 (日付) ====
        date_indices = [0, len(dates)-1]
        for i in date_indices:
            x = map_x(i)
            draw.line([(x, gy), (x, gy+gh)], fill=(220, 220, 220), width=1)
            d_str = dates[i].strftime("%m/%d")
            text_pos_x = x if i == 0 else x - 35
            draw.text((text_pos_x, gy + gh + 5), d_str, font=f_axis, fill=(100, 100, 100))

        # ==== グラフ線 ====
        points = [(map_x(i), map_y(p)) for i, p in enumerate(prices)]
        draw.line(points, fill=trend_color, width=2)
        ex, ey = points[-1]
        draw.ellipse((ex-3, ey-3, ex+3, ey+3), fill=trend_color)

        # ==== タイトルと現在値 ====
        draw.text((x_base + 10, y_base + 10), name, font=f_title, fill=(50, 50, 50))
        
        # 現在値 (単位あり)
        current_str = self.format_value(curr_price, unit, pos)
        pct_str = f"{'+' if diff>0 else ''}{pct:.2f}%"
        
        draw.text((x_base + 10, y_base + 40), current_str, font=f_val, fill=(20, 20, 20))
        # パーセント表示の位置調整（現在値の後ろに）
        val_w = draw.textlength(current_str, font=f_val)
        draw.text((x_base + 10 + val_w + 10, y_base + 42), pct_str, font=f_pct, fill=trend_color)

    def create_screen(self, screen_config, data):
        img = Image.new("RGB", (800, 480), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        positions = [
            (0, 0, 400, 240),   (400, 0, 400, 240),
            (0, 240, 400, 240), (400, 240, 400, 240)
        ]
        
        for i, item in enumerate(screen_config):
            if i >= 4: break
            rect = positions[i]
            ticker = item["ticker"]
            
            if ticker in data:
                self.draw_detailed_chart(draw, rect, data[ticker], item)
            else:
                x,y,w,h = rect
                draw.rectangle((x,y,x+w,y+h), outline=(200,200,200))
                draw.text((x+20, y+100), "Data Error", fill=(0,0,0))

        # 区切り線
        draw.line([(400, 0), (400, 480)], fill=(180, 180, 180), width=2)
        draw.line([(0, 240), (800, 240)], fill=(180, 180, 180), width=2)
        
        return img

    def update(self):
        try:
            df = self.fetch_data()
            imgs = [self.create_screen(cfg, df) for cfg in self.SCREENS_CONFIG]
            self.image_request(imgs)
        except Exception as e:
            print(f"StockUpdater Error: {e}")

if __name__=="__main__":
    updater = StockUpdater()
    updater.update()