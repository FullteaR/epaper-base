from WebsiteUpdater import WebsiteUpdater
import requests
import math
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class WeatherUpdater(WebsiteUpdater):


    def __init__(self):
        self.JST = timezone(timedelta(hours=9))
        self.LOCATION = "東京"
        self.LAT = 35.6812
        self.LON = 139.7671
        self.FONT_REG_PATH = "./fonts/NotoSansJP-Regular.ttf"
        self.FONT_BOLD_PATH = "./fonts/NotoSansJP-Bold.ttf"

        # ====== 天気コード -> 簡易アイコン/テキスト ======
        self.WMO_MAP = {
            0:  ("快晴", "./images/weather/weather_icon/clear.png"),
            1:  ("晴れ", "./images/weather/weather_icon/mostly_clear.png"),
            2:  ("薄曇", "./images/weather/weather_icon/partly_cloudy.png"),
            3:  ("曇り", "./images/weather/weather_icon/cloudy.png"),

            45: ("霧", "./images/weather/weather_icon/fog.png"),
            48: ("氷霧", "./images/weather/weather_icon/fog.png"),

            51: ("霧雨(弱)", "./images/weather/weather_icon/drizzle_light.png"),
            53: ("霧雨(中)", "./images/weather/weather_icon/drizzle.png"),
            55: ("霧雨(強)", "./images/weather/weather_icon/drizzle_heavy.png"),

            56: ("着氷性霧雨(弱)", "./images/weather/weather_icon/freezing_drizzle_light.png"),
            57: ("着氷性霧雨(強)", "./images/weather/weather_icon/freezing_drizzle.png"),

            61: ("雨(弱)", "./images/weather/weather_icon/rain.png"),
            63: ("雨(中)", "./images/weather/weather_icon/rain.png"),
            65: ("雨(強)", "./images/weather/weather_icon/rain.png"),

            66: ("着氷性雨(弱)", "./images/weather/weather_icon/freezing_rain_light.png"),
            67: ("着氷性雨(強)", "./images/weather/weather_icon/freezing_rain.png"),

            71: ("雪(弱)", "./images/weather/weather_icon/snow.png"),
            73: ("雪(中)", "./images/weather/weather_icon/snow.png"),
            75: ("雪(強)", "./images/weather/weather_icon/snow.png"),

            77: ("雪粒", "./images/weather/weather_icon/snow.png"),

            80: ("にわか雨(弱)", "./images/weather/weather_icon/showers_light.png"),
            81: ("にわか雨(中)", "./images/weather/weather_icon/showers.png"),
            82: ("にわか雨(強)", "./images/weather/weather_icon/showers_heavy.png"),

            85: ("にわか雪(弱)", "./images/weather/weather_icon/snow_showers_light.png"),
            86: ("にわか雪(強)", "./images/weather/weather_icon/snow_showers_heavy.png"),

            95: ("雷雨", "./images/weather/weather_icon/thunderstorm.png"),
            96: ("雷雨(雹)", "./images/weather/weather_icon/thunderstorm.png"),
            99: ("激しい雷雨(雹)", "./images/weather/weather_icon/thunderstorm_heavy_hail.png"),
        }

        urls = [
            "http://project92.com/amesh/" # amesh
        ]
        super().__init__(urls)
    
    def wmo_to_str(self, code: int):
        return self.WMO_MAP.get(code, ("不明", "./images/weather/weather_icon/sunny.png"))

    

    def fetch_weather(self, lat, lon):
        BASE_URL = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.LAT}&longitude={self.LON}&timezone=Asia%2FTokyo"
            "&current_weather=true"
            "&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation_probability,precipitation,weathercode,"
            "wind_speed_10m,pressure_msl"
            "&daily=weathercode,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,sunrise,sunset"
        )
        url = BASE_URL.format(lat=lat, lon=lon)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    
    def make_today(self, payload):
        now = datetime.now(self.JST)
        current = payload["current_weather"]
        hourly = payload["hourly"]
        times = [datetime.fromisoformat(t).replace(tzinfo=self.JST) for t in hourly["time"]]

        temps = hourly["temperature_2m"]
        hums  = hourly["relative_humidity_2m"]
        press = hourly["pressure_msl"]
        is_day = current.get("is_day", 1)

        # ==== 背景 ====
        bg_color = (185, 217, 255) if is_day else (48, 64, 96)
        img = Image.new("RGB", (800, 480), color=bg_color)
        draw = ImageDraw.Draw(img)

        # ==== フォント ====
        f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 36)
        f_temp  = ImageFont.truetype(self.FONT_BOLD_PATH, 90)
        f_med   = ImageFont.truetype(self.FONT_REG_PATH, 26)
        f_sml   = ImageFont.truetype(self.FONT_REG_PATH, 20)

        # ==== データ抽出 ====
        desc, icon_path = self.wmo_to_str(current["weathercode"])
        temp = current["temperature"]
        wind = current["windspeed"]
        idx = min(range(len(times)), key=lambda i: abs((times[i]-now).total_seconds()))
        rh = hums[idx]
        pr = press[idx]
        sr = payload["daily"]["sunrise"][0].split("T")[1][:5]
        ss = payload["daily"]["sunset"][0].split("T")[1][:5]
        tmax = payload["daily"]["temperature_2m_max"][0]
        tmin = payload["daily"]["temperature_2m_min"][0]
        pop = payload["daily"]["precipitation_probability_max"][0]

        text_color = (25,25,25) if is_day else (230,230,230)
        sub_color  = (80,80,80) if is_day else (190,190,190)

        # ==== 天気アイコン ====
        icon_img = Image.open(icon_path).convert("RGBA").resize((140, 140))
        img.paste(icon_img, (60, 130), icon_img)

        # ==== タイトル ====
        draw.text((40, 25), f"{self.LOCATION} の天気", font=f_title, fill=text_color)
        draw.text((40, 70), now.strftime("%Y-%m-%d (%a) %H:%M"), font=f_sml, fill=sub_color)

        # ==== 気温と説明 ====
        draw.text((230, 130), f"{int(temp)}°C", font=f_temp, fill=text_color)
        draw.text((240, 230), desc, font=f_med, fill=sub_color)

        # ==== サブ情報 ====
        draw.text((60, 290), f"風速 {wind:.1f} m/s", font=f_sml, fill=sub_color)
        draw.text((260, 290), f"湿度 {int(rh)}%", font=f_sml, fill=sub_color)
        draw.text((440, 290), f"気圧 {int(pr)} hPa", font=f_sml, fill=sub_color)

        # ==== 右上：最高/最低/降水確率/月齢 ====
        box_x, box_y = 550, 30
        draw.text((box_x+15, box_y+10), f"最高 {int(tmax)}°C", font=f_med, fill=sub_color)
        draw.text((box_x+15, box_y+50), f"最低 {int(tmin)}°C", font=f_med, fill=sub_color)
        draw.text((box_x+15, box_y+85), f"降水確率 {int(pop)}%", font=f_med, fill=sub_color)

        # ==== グラフ ====
        gx, gy, gw, gh = 80, 330, 660, 100
        subtemps = temps[idx:idx+12]
        hours = [t.strftime("%H") for t in times[idx:idx+12]]
        draw.rectangle((gx, gy, gx+gw, gy+gh), fill=(255,255,255,220), outline=(180,180,180))

        tmin2, tmax2 = min(subtemps), max(subtemps)
        if tmax2 - tmin2 < 3:
            c = (tmax2 + tmin2)/2
            tmax2, tmin2 = c+1.5, c-1.5

        def map_t(i, val):
            return (gx + i*(gw/(len(subtemps)-1)), gy+gh - (val-tmin2)/(tmax2-tmin2+0.1)*gh)

        # ==== Y軸 ====
        step_count = 4
        for step in range(step_count):
            yv = tmin2 + (tmax2 - tmin2) * (1 - step / (step_count - 1))
            y = gy + gh * (step / (step_count - 1))
            draw.line([(gx-5, y), (gx, y)], fill=(180,180,180), width=2)
            draw.text((gx-55, y-10), f"{round(yv):>2}°C", font=f_sml, fill=sub_color)

        # ==== 折れ線 ====
        last = None
        for i, val in enumerate(subtemps):
            pt = map_t(i, val)
            if last:
                draw.line([last, pt], fill=(230,80,80), width=3)
            draw.ellipse((pt[0]-3, pt[1]-3, pt[0]+3, pt[1]+3), fill=(230,80,80))
            last = pt

        for i, h in enumerate(hours):
            x = gx + i*(gw/(len(hours)-1))
            draw.text((x-10, gy+gh+5), h, font=f_sml, fill=sub_color)

        # ==== 日の出・日の入り ====
        try:
            sunrise_img = Image.open("./images/weather/sunrise.png").convert("RGBA").resize((36,36))
            sunset_img  = Image.open("./images/weather/sunset.png").convert("RGBA").resize((36,36))
            img.paste(sunrise_img, (580, 440), sunrise_img)
            img.paste(sunset_img,  (700, 440), sunset_img)
        except FileNotFoundError:
            draw.text((580, 450), "🌅", font=f_sml, fill=sub_color)
            draw.text((700, 450), "🌇", font=f_sml, fill=sub_color)
        draw.text((620, 450), sr, font=f_sml, fill=sub_color)
        draw.text((740, 450), ss, font=f_sml, fill=sub_color)

        return img
    
    def make_week(self, payload):
        daily = payload["daily"]
        days = daily["time"]
        weathercodes = daily["weathercode"]
        tmaxs = daily["temperature_2m_max"]
        tmins = daily["temperature_2m_min"]
        pops = daily["precipitation_probability_max"]

        is_day = payload["current_weather"].get("is_day", 1)
        bg_color = (185, 217, 255) if is_day else (48, 64, 96)

        img = Image.new("RGB", (800, 480), color=bg_color)
        draw = ImageDraw.Draw(img)

        f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 36)
        f_day   = ImageFont.truetype(self.FONT_BOLD_PATH, 26)
        f_data  = ImageFont.truetype(self.FONT_REG_PATH, 22)
        f_sml   = ImageFont.truetype(self.FONT_REG_PATH, 18)

        text_color = (25,25,25) if is_day else (230,230,230)
        sub_color  = (80,80,80) if is_day else (180,180,180)

        # ==== タイトル ====
        draw.text((40, 25), f"{self.LOCATION} の週間天気", font=f_title, fill=text_color)

        # ==== 日本語曜日マップ ====
        jp_days = ["月", "火", "水", "木", "金", "土", "日"]

        # ==== 配置設定 ====
        start_x, start_y = 25, 100
        usable_w = 750
        cell_w = usable_w / 7
        max_days = min(7, len(days))

        # ==== 上段：各日の概要 ====
        for i in range(max_days):
            x_center = start_x + i * cell_w + cell_w / 2
            y = start_y

            date = datetime.fromisoformat(days[i])
            day_label = jp_days[date.weekday()]+"曜日"  # 日本語曜日

            desc, icon_path = self.wmo_to_str(weathercodes[i])
            icon_img = Image.open(icon_path).convert("RGBA").resize((55, 55))
            img.paste(icon_img, (int(x_center - 27), int(y)), icon_img)

            # 曜日
            w_day = draw.textlength(day_label, font=f_day)
            draw.text((x_center - w_day / 2, y + 65), day_label, font=f_day, fill=text_color)

            # 気温
            temp_text = f"{int(tmaxs[i])}/{int(tmins[i])}°C"
            w_temp = draw.textlength(temp_text, font=f_data)
            draw.text((x_center - w_temp / 2, y + 95), temp_text, font=f_data, fill=text_color)

            # 降水確率
            pop_text = f"降水 {int(pops[i])}%"
            w_pop = draw.textlength(pop_text, font=f_sml)
            draw.text((x_center - w_pop / 2, y + 120), pop_text, font=f_sml, fill=sub_color)

        # ==== 下段：週間気温推移グラフ ====
        gx, gy, gw, gh = 80, 280, 660, 160
        draw.rectangle((gx, gy, gx+gw, gy+gh), fill=(255,255,255), outline=(180,180,180))

        # スケール設定
        tmax_all = max(tmaxs[:max_days])
        tmin_all = min(tmins[:max_days])
        pad = 2
        tmax_all += pad
        tmin_all -= pad

        def map_temp(val):
            return gy + gh - (val - tmin_all) / (tmax_all - tmin_all) * gh

        # 折れ線（最高・最低）
        for arr, color in [(tmaxs, (230,80,80)), (tmins, (80,120,230))]:
            last = None
            for i, v in enumerate(arr[:max_days]):
                x = gx + i * (gw / (max_days - 1))
                y = map_temp(v)
                if last:
                    draw.line([last, (x, y)], fill=color, width=3)
                draw.ellipse((x-3, y-3, x+3, y+3), fill=color)
                last = (x, y)

        # Y軸（温度ラベル）
        for step in range(5):
            val = tmin_all + (tmax_all - tmin_all) * (1 - step / 4)
            y = map_temp(val)
            draw.line([(gx-5, y), (gx, y)], fill=sub_color)
            draw.text((gx-45, y-10), f"{int(val)}°C", font=f_sml, fill=sub_color)

        # X軸（日）
        for i in range(max_days):
            x = gx + i * (gw / (max_days - 1))
            draw.text((x-8, gy+gh+5), jp_days[datetime.fromisoformat(days[i]).weekday()], font=f_sml, fill=sub_color)

        return img

    def parse_amesh(self, img):
        return img.crop((0,50,int(800*0.95),480*0.95+50))

    def update(self):
        imgs = self.screen_shot(self.website_urls)

        data = self.fetch_weather(self.LAT, self.LON)
        img_today = self.make_today(data)
        img_week = self.make_week(data)
        img_amesh = self.parse_amesh(imgs[0])
        self.image_request([img_amesh, img_week, img_today])


if __name__=="__main__":
    updater = WeatherUpdater()

    updater.update()