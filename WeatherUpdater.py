from WebsiteUpdater import WebsiteUpdater
import requests
import os
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

class WeatherUpdater(WebsiteUpdater):

    def __init__(self):
        self.JST = timezone(timedelta(hours=9))
        self.LOCATION = "東京"
        self.LAT = 35.6812
        self.LON = 139.7671
        
        # フォント設定
        self.FONT_REG_PATH = "./fonts/NotoSansJP-Regular.ttf"
        self.FONT_BOLD_PATH = "./fonts/NotoSansJP-Bold.ttf"

        # 画像フォルダ
        self.ICON_DIR = "./images/weather/"
        if not os.path.exists(self.ICON_DIR):
            os.makedirs(self.ICON_DIR)

        # ====== WMOコード -> ファイル名ベース ======
        # ここで指定した名前 + "-day.png" または "-night.png" を読みに行きます
        self.WMO_MAP = {
            0:  ("快晴", "clear"),
            1:  ("晴れ", "mostly-clear"),
            2:  ("薄曇", "partly-cloudy"),
            3:  ("曇り", "cloudy"),
            45: ("霧", "fog"),
            48: ("氷霧", "fog"),
            51: ("霧雨", "rain"),
            53: ("霧雨", "rain"),
            55: ("霧雨", "rain"),
            61: ("雨", "rain"),
            63: ("雨", "rain"),
            65: ("大雨", "rain"),
            71: ("雪", "snow"),
            73: ("雪", "snow"),
            75: ("大雪", "snow"),
            77: ("雪粒", "snow"),
            80: ("にわか雨", "rain"),
            81: ("にわか雨", "rain"),
            82: ("雷雨", "thunder"),
            85: ("にわか雪", "snow"),
            86: ("にわか雪", "snow"),
            95: ("雷雨", "thunder"),
            96: ("雷雨", "thunder"),
            99: ("雷雨", "thunder"),
        }

        urls = ["http://project92.com/amesh/"]
        super().__init__(urls)

    def get_weather_icon(self, code, is_day):
        """
        フォルダから画像を読み込む。
        ファイルがない場合は、レイアウト崩れ防止用にダミーの図形を生成して返す。
        """
        desc, base_name = self.WMO_MAP.get(code, ("不明", "cloudy"))
        
        # 昼夜サフィックス
        suffix = "-day" if is_day else "-night"
        filename = f"{base_name}{suffix}.png"
        filepath = os.path.join(self.ICON_DIR, filename)

        if os.path.exists(filepath):
            try:
                return desc, Image.open(filepath).convert("RGBA")
            except Exception as e:
                print(f"Error loading {filename}: {e}")
        else:
            print(f"Icon not found: {filename} (Using placeholder)")

        # ==== 画像がない場合のダミー生成 (単純な円) ====
        # ユーザーが画像を作るまでのプレースホルダー
        img = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 天気に応じて色を変える程度の簡易ロジック
        if "clear" in base_name or "partly" in base_name:
            color = (255, 165, 0) # オレンジ (晴れ)
        elif "rain" in base_name:
            color = (65, 105, 225) # 青 (雨)
        elif "cloud" in base_name:
            color = (169, 169, 169) # グレー (曇り)
        elif "snow" in base_name:
            color = (200, 240, 255) # 水色 (雪)
        else:
            color = (128, 128, 128)

        # 丸を描く
        draw.ellipse((20, 20, 140, 140), fill=color)
        
        # 文字でファイル名を描いておく（何を作ればいいかわかるように）
        try:
            f = ImageFont.truetype(self.FONT_REG_PATH, 14)
            draw.text((30, 70), filename, font=f, fill=(255,255,255))
        except:
            pass

        return desc, img

    def fetch_weather(self):
        BASE_URL = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.LAT}&longitude={self.LON}&timezone=Asia%2FTokyo"
            "&current_weather=true"
            "&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation_probability,weathercode,wind_speed_10m,pressure_msl,uv_index,winddirection_10m"
            "&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset,uv_index_max"
        )
        resp = requests.get(BASE_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()
    
    def make_today(self, payload):
        now = datetime.now(self.JST)
        current = payload["current_weather"]
        hourly = payload["hourly"]
        daily = payload["daily"]
        
        times = [datetime.fromisoformat(t).replace(tzinfo=self.JST) for t in hourly["time"]]
        idx = min(range(len(times)), key=lambda i: abs((times[i]-now).total_seconds()))
        is_day = current["is_day"]
        
        # アイコン取得
        desc, icon_img = self.get_weather_icon(current["weathercode"], is_day)
        
        temp = current["temperature"]
        wind_spd = current["windspeed"]
        rh = hourly["relative_humidity_2m"][idx]
        pr = hourly["pressure_msl"][idx]
        app_temp = hourly["apparent_temperature"][idx]
        uv_now = hourly["uv_index"][idx]
        uv_max = daily["uv_index_max"][0]
        sr = daily["sunrise"][0].split("T")[1][:5]
        ss = daily["sunset"][0].split("T")[1][:5]
        tmax = daily["temperature_2m_max"][0]
        tmin = daily["temperature_2m_min"][0]
        pop = daily["precipitation_probability_max"][0]

        bg_color = (220, 240, 255) if is_day else (40, 50, 80)
        text_color = (30,30,30) if is_day else (240,240,240)
        sub_color  = (80,80,80) if is_day else (180,180,180)

        img = Image.new("RGB", (800, 480), color=bg_color)
        draw = ImageDraw.Draw(img)

        # フォント読み込み
        try:
            f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 36)
            f_temp  = ImageFont.truetype(self.FONT_BOLD_PATH, 90)
            f_med   = ImageFont.truetype(self.FONT_REG_PATH, 26)
            f_sml   = ImageFont.truetype(self.FONT_REG_PATH, 22)
            f_mini  = ImageFont.truetype(self.FONT_REG_PATH, 16)
        except:
            f_title = f_temp = f_med = f_sml = f_mini = ImageFont.load_default()

        # 描画
        draw.text((40, 25), f"{self.LOCATION} の天気", font=f_title, fill=text_color)
        draw.text((40, 70), now.strftime("%Y-%m-%d (%a) %H:%M"), font=f_sml, fill=sub_color)

        # アイコン貼り付け
        icon_sz = 160
        icon_img = icon_img.resize((icon_sz, icon_sz), Image.Resampling.LANCZOS)
        img.paste(icon_img, (50, 110), icon_img)

        draw.text((230, 130), f"{int(temp)}°C", font=f_temp, fill=text_color)
        draw.text((240, 230), desc, font=f_med, fill=sub_color)

        start_y, col1_x, col2_x, line_h = 280, 60, 300, 35
        draw.text((col1_x, start_y),           f"体感: {int(app_temp)}°C", font=f_sml, fill=text_color)
        draw.text((col1_x, start_y + line_h),  f"湿度: {int(rh)}%",       font=f_sml, fill=sub_color)
        draw.text((col1_x, start_y + line_h*2),f"気圧: {int(pr)} hPa",    font=f_sml, fill=sub_color)
        draw.text((col2_x, start_y),           f"風速: {wind_spd:.1f} m/s", font=f_sml, fill=sub_color)
        draw.text((col2_x, start_y + line_h),  f"UV: {uv_now:.1f} (Max {uv_max:.1f})", font=f_sml, fill=sub_color)

        box_x, box_y = 560, 30
        draw.text((box_x+15, box_y+10), f"最高 {int(tmax)}°C", font=f_med, fill=text_color)
        draw.text((box_x+15, box_y+45), f"最低 {int(tmin)}°C", font=f_med, fill=sub_color)
        draw.text((box_x+15, box_y+80), f"降水 {int(pop)}%",   font=f_med, fill=text_color)

        gx, gy, gw, gh = 60, 380, 480, 80
        draw.rectangle((gx, gy, gx+gw, gy+gh), fill=(255,255,255,100), outline=(200,200,200))
        subtemps = hourly["temperature_2m"][idx:idx+12]
        tmin2, tmax2 = min(subtemps), max(subtemps)
        if tmax2 - tmin2 < 3: c = (tmax2 + tmin2)/2; tmax2, tmin2 = c+2, c-2
        def map_t(i, val): return (gx + i*(gw/(len(subtemps)-1)), gy+gh - (val-tmin2)/(tmax2-tmin2)*gh)

        last = None
        for i, val in enumerate(subtemps):
            pt = map_t(i, val)
            if last: draw.line([last, pt], fill=(230,80,80), width=3)
            draw.ellipse((pt[0]-3, pt[1]-3, pt[0]+3, pt[1]+3), fill=(230,80,80))
            last = pt
            
        hours = [t.strftime("%H") for t in times[idx:idx+12]]
        for i, h in enumerate(hours):
            if i % 2 == 0:
                x = gx + i*(gw/(len(hours)-1))
                draw.text((x-8, gy+gh+5), h, font=f_mini, fill=sub_color)

        draw.text((580, 400), "日出", font=f_sml, fill=sub_color)
        draw.text((640, 400), sr,    font=f_med, fill=text_color)
        draw.text((580, 440), "日入", font=f_sml, fill=sub_color)
        draw.text((640, 440), ss,    font=f_med, fill=text_color)

        return img
    
    def make_week(self, payload):
        daily = payload["daily"]
        days = daily["time"]
        weathercodes = daily["weathercode"]
        tmaxs = daily["temperature_2m_max"]
        tmins = daily["temperature_2m_min"]
        pops = daily["precipitation_probability_max"]
        is_day = payload["current_weather"].get("is_day", 1)

        bg_color = (220, 240, 255) if is_day else (40, 50, 80)
        img = Image.new("RGB", (800, 480), color=bg_color)
        draw = ImageDraw.Draw(img)

        try:
            f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 36)
            f_day   = ImageFont.truetype(self.FONT_BOLD_PATH, 24)
            f_data  = ImageFont.truetype(self.FONT_REG_PATH, 22)
            f_sml   = ImageFont.truetype(self.FONT_REG_PATH, 18)
        except:
            f_title = f_day = f_data = f_sml = ImageFont.load_default()

        text_color = (30,30,30) if is_day else (240,240,240)
        sub_color  = (80,80,80) if is_day else (180,180,180)

        draw.text((40, 25), f"{self.LOCATION} の週間天気", font=f_title, fill=text_color)

        jp_days = ["月", "火", "水", "木", "金", "土", "日"]
        start_x, start_y, usable_w = 25, 90, 750
        cell_w = usable_w / 7
        max_days = min(7, len(days))

        for i in range(max_days):
            x_center = start_x + i * cell_w + cell_w / 2
            y = start_y
            date = datetime.fromisoformat(days[i])
            
            draw.text((x_center - 25, y), date.strftime("%m/%d"), font=f_sml, fill=sub_color)
            draw.text((x_center - 10, y + 20), jp_days[date.weekday()], font=f_day, fill=text_color)

            # アイコン (週間は常に昼で取得)
            _, icon_img = self.get_weather_icon(weathercodes[i], is_day=1)
            icon_img = icon_img.resize((60, 60), Image.Resampling.LANCZOS)
            img.paste(icon_img, (int(x_center - 30), int(y + 55)), icon_img)

            temp_text = f"{int(tmaxs[i])}/{int(tmins[i])}"
            w_temp = draw.textlength(temp_text, font=f_data)
            draw.text((x_center - w_temp / 2, y + 125), temp_text, font=f_data, fill=text_color)
            pop_text = f"{int(pops[i])}%"
            w_pop = draw.textlength(pop_text, font=f_sml)
            draw.text((x_center - w_pop / 2, y + 155), pop_text, font=f_sml, fill=(80,120,230))

        gx, gy, gw, gh = 60, 300, 680, 150
        draw.rectangle((gx, gy, gx+gw, gy+gh), fill=(255,255,255,100), outline=(200,200,200))
        tmax_all, tmin_all = max(tmaxs[:max_days]) + 2, min(tmins[:max_days]) - 2
        def map_temp(val): return gy + gh - (val - tmin_all) / (tmax_all - tmin_all) * gh

        for arr, color in [(tmaxs, (230,80,80)), (tmins, (80,120,230))]:
            last = None
            for i, v in enumerate(arr[:max_days]):
                x = gx + i * (gw / (max_days - 1))
                y = map_temp(v)
                if last: draw.line([last, (x, y)], fill=color, width=3)
                draw.ellipse((x-4, y-4, x+4, y+4), fill=color)
                last = (x, y)
        return img

    def parse_amesh(self, img):
        return img.crop((0, 60, 760, 460)).resize((800,480))

    def update(self):
        try:
            imgs = self.screen_shot(self.website_urls)
            img_amesh = self.parse_amesh(imgs[0])
            data = self.fetch_weather()
            img_today = self.make_today(data)
            img_week = self.make_week(data)
            self.image_request([img_amesh, img_week, img_today])
        except Exception as e:
            print(f"WeatherUpdate Error: {e}")

if __name__=="__main__":
    updater = WeatherUpdater()
    updater.update()