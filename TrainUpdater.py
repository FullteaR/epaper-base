from ImageUpdater import ImageUpdater
import requests
import os
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont


class TrainUpdater(ImageUpdater):

    def __init__(self):
        super().__init__()
        self.JST = timezone(timedelta(hours=9))
        
        self.FONT_REG_PATH = "./fonts/NotoSansJP-Regular.ttf"
        self.FONT_BOLD_PATH = "./fonts/NotoSansJP-Bold.ttf"
        
        self.API_BASE = "https://api.odpt.org/api/v4"
        self.API_KEY = os.environ.get("ODPT_API_KEY", "YOUR_API_KEY_HERE")
        
        self.STATION_CONFIG = {
            "screen1": {
                "title": "虎ノ門ヒルズ・新橋 時刻表",
                "stations": [
                    {
                        "name": "虎ノ門ヒルズ",
                        "operator": "TokyoMetro",
                        "line": "Hibiya",
                        "line_ja": "日比谷線",
                        "station_id": "odpt.Station:TokyoMetro.Hibiya.ToranomonHills"
                    },
                    {
                        "name": "新橋",
                        "operator": "TokyoMetro",
                        "line": "Ginza",
                        "line_ja": "銀座線",
                        "station_id": "odpt.Station:TokyoMetro.Ginza.Shimbashi"
                    },
                    {
                        "name": "新橋",
                        "operator": "Toei",
                        "line": "Asakusa",
                        "line_ja": "浅草線",
                        "station_id": "odpt.Station:Toei.Asakusa.Shimbashi"
                    },
                    {
                        "name": "新橋",
                        "operator": "Yurikamome",
                        "line": "Yurikamome",
                        "line_ja": "ゆりかもめ",
                        "station_id": "odpt.Station:Yurikamome.Yurikamome.Shimbashi"
                    },
                ]
            },
            "screen3": {
                "title": "御成門 時刻表",
                "stations": [
                    {
                        "name": "御成門",
                        "operator": "Toei",
                        "line": "Mita",
                        "line_ja": "三田線",
                        "station_id": "odpt.Station:Toei.Mita.Onarimon"
                    }
                ]
            }
        }
        
        self.LINE_COLORS = {
            "Hibiya": (180, 180, 180),
            "Ginza": (255, 140, 0),
            "Asakusa": (230, 80, 100),
            "Mita": (0, 100, 180),
            "Yamanote": (154, 205, 50),
            "Yokosuka": (0, 70, 140),
            "KeihinTohoku": (0, 180, 220),
            "Tokaido": (255, 120, 0),
            "Yurikamome": (0, 180, 180),
        }
        
        self.OPERATOR_NAMES = {
            "TokyoMetro": "メトロ",
            "Toei": "都営",
            "JR-East": "JR",
            "Yurikamome": "",
        }
        
        self.STATION_NAME_MAP = {
            "NakaMeguro": "中目黒",
            "Nakameguro": "中目黒",
            "KitaSenju": "北千住",
            "Kitasenju": "北千住",
            "Shibuya": "渋谷",
            "Asakusa": "浅草",
            "NishiMagome": "西馬込",
            "Nishimagome": "西馬込",
            "NaritaAirportTerminal1": "成田空港",
            "NaritaAirport": "成田空港",
            "Oshiage": "押上",
            "KeikyuKurihama": "京急久里浜",
            "Misakiguchi": "三崎口",
            "Haneda": "羽田空港",
            "HanedaAirportTerminal1and2": "羽田空港",
            "HanedaAirportTerminal3": "羽田空港",
            "Meguro": "目黒",
            "Hiyoshi": "日吉",
            "NishiTakashimadaira": "西高島平",
            "Nishitakashimadaira": "西高島平",
            "Toyosu": "豊洲",
            "Shimbashi": "新橋",
            "Shinbashi": "新橋",
            "ToranomonHills": "虎ノ門ヒルズ",
            "Onarimon": "御成門",
            "Shinjuku": "新宿",
            "Ikebukuro": "池袋",
            "Tokyo": "東京",
            "Ueno": "上野",
            "Akihabara": "秋葉原",
            "Shinagawa": "品川",
            "Yokohama": "横浜",
            "Omiya": "大宮",
            "Chiba": "千葉",
            "Ofuna": "大船",
            "Zushi": "逗子",
            "Kurihama": "久里浜",
            "Atami": "熱海",
            "Odawara": "小田原",
            "Kofu": "甲府",
            "Takao": "高尾",
            "Hachioji": "八王子",
            "Kawasaki": "川崎",
            "Tsurumi": "鶴見",
            "Totsuka": "戸塚",
            "Fujisawa": "藤沢",
            "Hiratsuka": "平塚",
            "Shinkiba": "新木場",
            "Ariake": "有明",
        }
        
        self.TRAIN_TYPE_MAP = {
            "Local": "各停",
            "Express": "急行",
            "Rapid": "快速",
            "LimitedExpress": "特急",
            "SemiExpress": "準急",
            "CommuterExpress": "通勤急行",
            "CommuterRapid": "通勤快速",
            "RapidExpress": "快速急行",
            "AccessExpress": "アクセス特急",
            "AirportRapid": "エアポート快特",
            "TokyoMetro.Local": "各停",
            "Toei.Local": "各停",
            "Toei.Express": "急行",
            "Toei.Rapid": "快速",
            "Toei.AirportRapid": "エアポート快特",
        }
        
        self.DIRECTION_MAP = {
            "Outbound": "下り",
            "Inbound": "上り",
            "TokyoMetro.Hibiya.NakaMeguro": "中目黒方面",
            "TokyoMetro.Hibiya.KitaSenju": "北千住方面",
            "TokyoMetro.Ginza.Shibuya": "渋谷方面",
            "TokyoMetro.Ginza.Asakusa": "浅草方面",
            "Toei.Asakusa.NishiMagome": "西馬込方面",
            "Toei.Asakusa.Oshiage": "押上方面",
            "Toei.Mita.Meguro": "目黒方面",
            "Toei.Mita.NishiTakashimadaira": "西高島平方面",
            "Yurikamome.Yurikamome.Shimbashi": "新橋方面",
            "Yurikamome.Yurikamome.Toyosu": "豊洲方面",
        }
        
        self.RAILWAY_NAME_MAP = {
            "TokyoMetro.Ginza": "銀座線",
            "TokyoMetro.Marunouchi": "丸ノ内線",
            "TokyoMetro.MarunouchiBranch": "丸ノ内線支線",
            "TokyoMetro.Hibiya": "日比谷線",
            "TokyoMetro.Tozai": "東西線",
            "TokyoMetro.Chiyoda": "千代田線",
            "TokyoMetro.Yurakucho": "有楽町線",
            "TokyoMetro.Hanzomon": "半蔵門線",
            "TokyoMetro.Namboku": "南北線",
            "TokyoMetro.Fukutoshin": "副都心線",
            "Toei.Asakusa": "浅草線",
            "Toei.Mita": "三田線",
            "Toei.Shinjuku": "新宿線",
            "Toei.Oedo": "大江戸線",
            "Toei.Arakawa": "荒川線",
            "Toei.NipporiToneri": "日暮里舎人ライナー",
            "JR-East.Yamanote": "山手線",
            "JR-East.KeihinTohoku": "京浜東北線",
            "JR-East.Tokaido": "東海道線",
            "JR-East.Yokosuka": "横須賀線",
            "JR-East.ChuoRapid": "中央線快速",
            "JR-East.ChuoSobuLocal": "中央総武線各停",
            "JR-East.SobuRapid": "総武線快速",
            "JR-East.Takasaki": "高崎線",
            "JR-East.Utsunomiya": "宇都宮線",
            "JR-East.SaikyoKawagoe": "埼京川越線",
            "JR-East.ShonanShinjuku": "湘南新宿ライン",
            "JR-East.UenoTokyo": "上野東京ライン",
            "JR-East.Keiyo": "京葉線",
            "JR-East.Musashino": "武蔵野線",
            "JR-East.Nambu": "南武線",
            "Yurikamome.Yurikamome": "ゆりかもめ",
            "Keikyu.Main": "京急本線",
            "Keikyu.Airport": "京急空港線",
            "Keikyu.Daishi": "京急大師線",
            "Keikyu.Zushi": "京急逗子線",
            "Keikyu.Kurihama": "京急久里浜線",
            "Tokyu.Toyoko": "東急東横線",
            "Tokyu.Meguro": "東急目黒線",
            "Tokyu.DenEnToshi": "東急田園都市線",
            "Tokyu.Oimachi": "東急大井町線",
            "Tokyu.Ikegami": "東急池上線",
            "Tokyu.TokyuTamagawa": "東急多摩川線",
            "Odakyu.Odawara": "小田急小田原線",
            "Odakyu.Enoshima": "小田急江ノ島線",
            "Odakyu.Tama": "小田急多摩線",
            "Keio.Keio": "京王線",
            "Keio.New": "京王新線",
            "Keio.Inokashira": "京王井の頭線",
            "Keio.Sagamihara": "京王相模原線",
            "Keio.Takao": "京王高尾線",
            "Seibu.Ikebukuro": "西武池袋線",
            "Seibu.Shinjuku": "西武新宿線",
            "Seibu.Yurakucho": "西武有楽町線",
            "Seibu.Toshima": "西武豊島線",
            "Tobu.Skytree": "東武スカイツリーライン",
            "Tobu.Isesaki": "東武伊勢崎線",
            "Tobu.Nikko": "東武日光線",
            "Tobu.Tojo": "東武東上線",
            "Tobu.Urban": "東武アーバンパークライン",
        }
        
        self.OPERATOR_JA_MAP = {
            "TokyoMetro": "東京メトロ",
            "Toei": "都営",
            "JR-East": "JR東日本",
            "Yurikamome": "ゆりかもめ",
            "Keikyu": "京急",
            "Tokyu": "東急",
            "Odakyu": "小田急",
            "Keio": "京王",
            "Seibu": "西武",
            "Tobu": "東武",
        }

    def fetch_station_timetable(self, station_id, operator):
        url = f"{self.API_BASE}/odpt:StationTimetable"
        params = {
            "odpt:station": station_id,
            "acl:consumerKey": self.API_KEY
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching timetable for {station_id}: {e}")
            return []

    def fetch_train_information(self):
        operators = [
            "TokyoMetro", "Toei", "JR-East", "Yurikamome",
            "Keikyu", "Tokyu", "Odakyu", "Keio", "Seibu", "Tobu"
        ]
        all_info = []
        
        for operator in operators:
            url = f"{self.API_BASE}/odpt:TrainInformation"
            params = {
                "odpt:operator": f"odpt.Operator:{operator}",
                "acl:consumerKey": self.API_KEY
            }
            try:
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                all_info.extend(data)
            except Exception as e:
                print(f"Error fetching train info for {operator}: {e}")
        
        return all_info

    def translate_station_name(self, name):
        if not name:
            return "---"
        clean_name = name.split(".")[-1] if "." in name else name
        return self.STATION_NAME_MAP.get(clean_name, clean_name)

    def translate_train_type(self, train_type):
        if not train_type:
            return "各停"
        clean_type = train_type.split(":")[-1] if ":" in train_type else train_type
        return self.TRAIN_TYPE_MAP.get(clean_type, clean_type)

    def translate_direction(self, direction):
        if not direction:
            return ""
        clean_dir = direction.split(":")[-1] if ":" in direction else direction
        return self.DIRECTION_MAP.get(clean_dir, clean_dir)

    def translate_railway(self, railway):
        if not railway:
            return ""
        clean_railway = railway.split(":")[-1] if ":" in railway else railway
        return self.RAILWAY_NAME_MAP.get(clean_railway, clean_railway)

    def get_upcoming_trains_by_direction(self, timetable_data, num_trains=3):
        now = datetime.now(self.JST)
        current_time = now.strftime("%H:%M")
        weekday = now.weekday()
        
        if weekday < 5:
            calendar_type = "Weekday"
        elif weekday == 5:
            calendar_type = "Saturday"
        else:
            calendar_type = "Holiday"
        
        directions = {}
        
        for timetable in timetable_data:
            cal = timetable.get("odpt:calendar", "")
            if calendar_type not in cal and "SaturdayHoliday" not in cal:
                if calendar_type in ["Saturday", "Holiday"] and "SaturdayHoliday" in cal:
                    pass
                else:
                    continue
            
            direction_raw = timetable.get("odpt:railDirection", "")
            direction_key = direction_raw.split(":")[-1] if direction_raw else "Unknown"
            direction_ja = self.translate_direction(direction_raw)
            
            if direction_key not in directions:
                directions[direction_key] = {
                    "direction_ja": direction_ja,
                    "trains": []
                }
            
            train_objects = timetable.get("odpt:stationTimetableObject", [])
            
            for train in train_objects:
                dep_time = train.get("odpt:departureTime", "")
                if not dep_time:
                    continue
                
                if dep_time >= current_time:
                    train_type_raw = train.get("odpt:trainType", "")
                    train_type_ja = self.translate_train_type(train_type_raw)
                    
                    dest_stations = train.get("odpt:destinationStation", [])
                    if dest_stations and len(dest_stations) > 0:
                        dest_raw = dest_stations[0]
                    else:
                        dest_raw = ""
                    dest_ja = self.translate_station_name(dest_raw)
                    
                    directions[direction_key]["trains"].append({
                        "time": dep_time,
                        "destination": dest_ja,
                        "train_type": train_type_ja,
                    })
        
        for direction_key in directions:
            directions[direction_key]["trains"].sort(key=lambda x: x["time"])
            directions[direction_key]["trains"] = directions[direction_key]["trains"][:num_trains]
        
        return directions

    def make_timetable_screen(self, config, screen_width=800, screen_height=480):
        bg_color = (245, 245, 250)
        text_color = (30, 30, 30)
        sub_color = (100, 100, 100)
        
        img = Image.new("RGB", (screen_width, screen_height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 24)
            f_station = ImageFont.truetype(self.FONT_BOLD_PATH, 16)
            f_direction = ImageFont.truetype(self.FONT_BOLD_PATH, 14)
            f_time = ImageFont.truetype(self.FONT_BOLD_PATH, 14)
            f_dest = ImageFont.truetype(self.FONT_REG_PATH, 13)
            f_type = ImageFont.truetype(self.FONT_REG_PATH, 11)
        except:
            f_title = f_station = f_direction = f_time = f_dest = f_type = ImageFont.load_default()
        
        now = datetime.now(self.JST)
        draw.text((15, 10), config["title"], font=f_title, fill=text_color)
        draw.text((screen_width - 80, 12), now.strftime("%H:%M"), font=f_title, fill=text_color)
        
        y_start = 45
        stations = config["stations"]
        num_stations = len(stations)
        
        if num_stations == 1:
            col_width = screen_width - 20
            num_cols = 1
        else:
            num_cols = 2
            col_width = (screen_width - 30) // 2
        
        rows_per_col = (num_stations + num_cols - 1) // num_cols
        station_height = (screen_height - y_start - 10) // rows_per_col
        
        for idx, station in enumerate(stations):
            col = idx // rows_per_col
            row = idx % rows_per_col
            
            x_offset = 10 + col * (col_width + 10)
            y_offset = y_start + row * station_height
            
            line_color = self.LINE_COLORS.get(station["line"], (128, 128, 128))
            draw.rectangle((x_offset, y_offset, x_offset + 6, y_offset + station_height - 8), fill=line_color)
            
            operator_name = self.OPERATOR_NAMES.get(station["operator"], station["operator"])
            line_ja = station.get("line_ja", station["line"])
            if operator_name:
                station_label = f"{station['name']} ({operator_name}{line_ja})"
            else:
                station_label = f"{station['name']} ({line_ja})"
            draw.text((x_offset + 12, y_offset + 2), station_label, font=f_station, fill=text_color)
            
            timetable_data = self.fetch_station_timetable(station["station_id"], station["operator"])
            directions = self.get_upcoming_trains_by_direction(timetable_data, num_trains=3)
            
            if directions:
                dir_keys = list(directions.keys())
                num_dirs = len(dir_keys)
                dir_width = (col_width - 20) // max(num_dirs, 1)
                
                for d_idx, dir_key in enumerate(dir_keys[:2]):
                    dir_data = directions[dir_key]
                    dir_x = x_offset + 12 + d_idx * dir_width
                    dir_y = y_offset + 22
                    
                    dir_label = dir_data["direction_ja"] or dir_key
                    if len(dir_label) > 8:
                        dir_label = dir_label[:8]
                    draw.text((dir_x, dir_y), f"【{dir_label}】", font=f_direction, fill=(80, 80, 120))
                    
                    train_y = dir_y + 18
                    labels = ["先発", "次発", "次々発"]
                    
                    for t_idx, train in enumerate(dir_data["trains"][:3]):
                        if train_y + 16 > y_offset + station_height - 5:
                            break
                        
                        label = labels[t_idx] if t_idx < len(labels) else ""
                        time_text = train["time"]
                        dest_text = train["destination"]
                        type_text = train["train_type"]
                        
                        draw.text((dir_x, train_y), label, font=f_type, fill=(120, 120, 120))
                        draw.text((dir_x + 35, train_y), time_text, font=f_time, fill=text_color)
                        
                        dest_display = f"{dest_text}行"
                        if type_text and type_text != "各停":
                            dest_display = f"{type_text} {dest_display}"
                        
                        if len(dest_display) > 12:
                            dest_display = dest_display[:12]
                        draw.text((dir_x + 80, train_y), dest_display, font=f_dest, fill=sub_color)
                        
                        train_y += 18
                    
                    if not dir_data["trains"]:
                        draw.text((dir_x, dir_y + 18), "データなし", font=f_dest, fill=sub_color)
            else:
                draw.text((x_offset + 12, y_offset + 25), "時刻表データなし", font=f_dest, fill=sub_color)
            
            if row < rows_per_col - 1:
                draw.line((x_offset + 10, y_offset + station_height - 5, 
                          x_offset + col_width - 10, y_offset + station_height - 5), 
                         fill=(200, 200, 200), width=1)
        
        if num_cols == 2:
            mid_x = screen_width // 2
            draw.line((mid_x, y_start, mid_x, screen_height - 10), fill=(180, 180, 180), width=1)
        
        return img

    def make_delay_screen(self, screen_width=800, screen_height=480):
        bg_color = (245, 245, 250)
        text_color = (30, 30, 30)
        sub_color = (100, 100, 100)
        
        img = Image.new("RGB", (screen_width, screen_height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 24)
            f_line = ImageFont.truetype(self.FONT_BOLD_PATH, 16)
            f_status = ImageFont.truetype(self.FONT_REG_PATH, 14)
            f_small = ImageFont.truetype(self.FONT_REG_PATH, 12)
        except:
            f_title = f_line = f_status = f_small = ImageFont.load_default()
        
        now = datetime.now(self.JST)
        draw.text((15, 10), "首都圏 鉄道運行情報", font=f_title, fill=text_color)
        draw.text((screen_width - 80, 12), now.strftime("%H:%M"), font=f_title, fill=text_color)
        
        train_info = self.fetch_train_information()
        
        delays = []
        normal = []
        
        for info in train_info:
            railway_raw = info.get("odpt:railway", "")
            operator_raw = info.get("odpt:operator", "")
            status = info.get("odpt:trainInformationStatus", {})
            text = info.get("odpt:trainInformationText", {})
            
            if isinstance(status, dict):
                status_ja = status.get("ja", "")
            else:
                status_ja = str(status) if status else ""
            
            if isinstance(text, dict):
                text_ja = text.get("ja", "")
            else:
                text_ja = str(text) if text else ""
            
            railway_ja = self.translate_railway(railway_raw)
            operator_key = operator_raw.split(":")[-1] if operator_raw else ""
            operator_ja = self.OPERATOR_JA_MAP.get(operator_key, operator_key)
            
            entry = {
                "line": railway_ja,
                "operator": operator_ja,
                "status": status_ja,
                "text": text_ja
            }
            
            if status_ja and status_ja not in ["平常運転", "平常どおり運転しています", ""]:
                delays.append(entry)
            else:
                normal.append(entry)
        
        y_offset = 45
        
        if delays:
            draw.text((15, y_offset), "遅延・運転見合わせ", font=f_line, fill=(200, 50, 50))
            y_offset += 25
            
            for delay in delays[:6]:
                if y_offset > screen_height - 80:
                    break
                
                line_text = f"{delay['operator']} {delay['line']}"
                draw.text((25, y_offset), line_text, font=f_line, fill=text_color)
                y_offset += 20
                
                status_text = delay['status'] or delay['text']
                if len(status_text) > 45:
                    status_text = status_text[:45] + "..."
                draw.text((35, y_offset), status_text, font=f_status, fill=(180, 80, 80))
                y_offset += 22
            
            draw.line((15, y_offset, screen_width - 15, y_offset), fill=(200, 200, 200), width=1)
            y_offset += 10
        
        draw.text((15, y_offset), "平常運転", font=f_line, fill=(50, 150, 50))
        y_offset += 25
        
        normal_lines = [f"{n['line']}" for n in normal if n['line']]
        normal_text = "、".join(normal_lines)
        
        max_width = screen_width - 40
        lines = []
        current_line = ""
        
        for char in normal_text:
            test_line = current_line + char
            if draw.textlength(test_line, font=f_small) < max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        
        for line in lines[:8]:
            if y_offset > screen_height - 20:
                break
            draw.text((25, y_offset), line, font=f_small, fill=sub_color)
            y_offset += 18
        
        if not train_info:
            draw.text((25, 80), "運行情報を取得できませんでした", font=f_status, fill=sub_color)
            draw.text((25, 105), "APIキーを確認してください", font=f_small, fill=sub_color)
        
        return img

    def update(self):
        try:
            img_screen1 = self.make_timetable_screen(self.STATION_CONFIG["screen1"])
            img_screen2 = self.make_delay_screen()
            img_screen3 = self.make_timetable_screen(self.STATION_CONFIG["screen3"])
            
            self.image_request([img_screen1, img_screen2, img_screen3])
        except Exception as e:
            print(f"TrainUpdater Error: {e}")


if __name__ == "__main__":
    updater = TrainUpdater()
    updater.update()
