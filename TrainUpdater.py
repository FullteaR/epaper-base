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
                        "station_id": "odpt.Station:TokyoMetro.Hibiya.ToranomonHills"
                    },
                    {
                        "name": "新橋",
                        "operator": "TokyoMetro",
                        "line": "Ginza",
                        "station_id": "odpt.Station:TokyoMetro.Ginza.Shimbashi"
                    },
                    {
                        "name": "新橋",
                        "operator": "Toei",
                        "line": "Asakusa",
                        "station_id": "odpt.Station:Toei.Asakusa.Shimbashi"
                    },
                    {
                        "name": "新橋",
                        "operator": "JR-East",
                        "line": "Yamanote",
                        "station_id": "odpt.Station:JR-East.Yamanote.Shimbashi"
                    },
                    {
                        "name": "新橋",
                        "operator": "Yurikamome",
                        "line": "Yurikamome",
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
            "TokyoMetro": "東京メトロ",
            "Toei": "都営",
            "JR-East": "JR",
            "Yurikamome": "ゆりかもめ",
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
        operators = ["TokyoMetro", "Toei", "JR-East", "Yurikamome", "Keikyu", "Tokyu", "Odakyu", "Keio", "Seibu", "Tobu"]
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

    def get_upcoming_trains(self, timetable_data, num_trains=5):
        now = datetime.now(self.JST)
        current_time = now.strftime("%H:%M")
        weekday = now.weekday()
        
        if weekday < 5:
            calendar_type = "Weekday"
        elif weekday == 5:
            calendar_type = "Saturday"
        else:
            calendar_type = "Holiday"
        
        upcoming = []
        
        for timetable in timetable_data:
            cal = timetable.get("odpt:calendar", "")
            if calendar_type not in cal and "SaturdayHoliday" not in cal:
                if not (calendar_type in ["Saturday", "Holiday"] and "SaturdayHoliday" in cal):
                    continue
            
            direction = timetable.get("odpt:railDirection", "").split(":")[-1] if timetable.get("odpt:railDirection") else ""
            destination = timetable.get("odpt:destinationStation", [""])[0] if timetable.get("odpt:destinationStation") else ""
            if destination:
                destination = destination.split(".")[-1]
            
            train_objects = timetable.get("odpt:stationTimetableObject", [])
            
            for train in train_objects:
                dep_time = train.get("odpt:departureTime", "")
                if not dep_time:
                    continue
                
                if dep_time >= current_time:
                    train_type = train.get("odpt:trainType", "").split(":")[-1] if train.get("odpt:trainType") else "各停"
                    dest = train.get("odpt:destinationStation", [destination])[0] if train.get("odpt:destinationStation") else destination
                    if dest:
                        dest = dest.split(".")[-1]
                    
                    upcoming.append({
                        "time": dep_time,
                        "destination": dest,
                        "train_type": train_type,
                        "direction": direction
                    })
        
        upcoming.sort(key=lambda x: x["time"])
        return upcoming[:num_trains]

    def make_timetable_screen(self, config, screen_width=800, screen_height=480):
        bg_color = (245, 245, 250)
        text_color = (30, 30, 30)
        sub_color = (100, 100, 100)
        
        img = Image.new("RGB", (screen_width, screen_height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 28)
            f_station = ImageFont.truetype(self.FONT_BOLD_PATH, 20)
            f_time = ImageFont.truetype(self.FONT_BOLD_PATH, 18)
            f_dest = ImageFont.truetype(self.FONT_REG_PATH, 16)
            f_small = ImageFont.truetype(self.FONT_REG_PATH, 14)
        except:
            f_title = f_station = f_time = f_dest = f_small = ImageFont.load_default()
        
        now = datetime.now(self.JST)
        draw.text((20, 15), config["title"], font=f_title, fill=text_color)
        draw.text((screen_width - 150, 20), now.strftime("%H:%M"), font=f_title, fill=text_color)
        
        y_offset = 60
        stations = config["stations"]
        
        if len(stations) == 1:
            station_height = screen_height - y_offset - 20
        else:
            station_height = (screen_height - y_offset - 20) // min(len(stations), 4)
        
        for i, station in enumerate(stations[:4]):
            station_y = y_offset + i * station_height
            
            line_color = self.LINE_COLORS.get(station["line"], (128, 128, 128))
            draw.rectangle((15, station_y, 25, station_y + station_height - 10), fill=line_color)
            
            operator_name = self.OPERATOR_NAMES.get(station["operator"], station["operator"])
            station_label = f"{station['name']} ({operator_name} {station['line']}線)"
            draw.text((35, station_y + 5), station_label, font=f_station, fill=text_color)
            
            timetable_data = self.fetch_station_timetable(station["station_id"], station["operator"])
            upcoming = self.get_upcoming_trains(timetable_data, num_trains=4)
            
            if upcoming:
                train_y = station_y + 35
                for j, train in enumerate(upcoming):
                    if train_y + 25 > station_y + station_height - 10:
                        break
                    
                    time_text = train["time"]
                    dest_text = train["destination"] or "---"
                    type_text = train["train_type"] or ""
                    
                    draw.text((45, train_y), time_text, font=f_time, fill=text_color)
                    draw.text((110, train_y), dest_text, font=f_dest, fill=sub_color)
                    if type_text and type_text != "Local":
                        draw.text((250, train_y), type_text, font=f_small, fill=(180, 80, 80))
                    
                    train_y += 25
            else:
                draw.text((45, station_y + 35), "時刻表データなし", font=f_dest, fill=sub_color)
            
            if i < len(stations) - 1:
                draw.line((30, station_y + station_height - 5, screen_width - 30, station_y + station_height - 5), 
                         fill=(200, 200, 200), width=1)
        
        return img

    def make_delay_screen(self, screen_width=800, screen_height=480):
        bg_color = (245, 245, 250)
        text_color = (30, 30, 30)
        sub_color = (100, 100, 100)
        
        img = Image.new("RGB", (screen_width, screen_height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            f_title = ImageFont.truetype(self.FONT_BOLD_PATH, 28)
            f_line = ImageFont.truetype(self.FONT_BOLD_PATH, 18)
            f_status = ImageFont.truetype(self.FONT_REG_PATH, 16)
            f_small = ImageFont.truetype(self.FONT_REG_PATH, 14)
        except:
            f_title = f_line = f_status = f_small = ImageFont.load_default()
        
        now = datetime.now(self.JST)
        draw.text((20, 15), "都内 鉄道運行情報", font=f_title, fill=text_color)
        draw.text((screen_width - 150, 20), now.strftime("%H:%M"), font=f_title, fill=text_color)
        
        train_info = self.fetch_train_information()
        
        delays = []
        normal = []
        
        for info in train_info:
            railway = info.get("odpt:railway", "").split(":")[-1] if info.get("odpt:railway") else ""
            operator = info.get("odpt:operator", "").split(":")[-1] if info.get("odpt:operator") else ""
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
            
            line_name = railway.replace(".", " ")
            
            entry = {
                "line": line_name,
                "operator": operator,
                "status": status_ja,
                "text": text_ja
            }
            
            if status_ja and status_ja not in ["平常運転", "平常どおり運転しています", ""]:
                delays.append(entry)
            else:
                normal.append(entry)
        
        y_offset = 60
        
        if delays:
            draw.text((20, y_offset), "遅延・運転見合わせ", font=f_line, fill=(200, 50, 50))
            y_offset += 30
            
            for delay in delays[:8]:
                if y_offset > screen_height - 60:
                    break
                
                line_text = f"{delay['operator']} {delay['line']}"
                draw.text((30, y_offset), line_text, font=f_line, fill=text_color)
                y_offset += 22
                
                status_text = delay['status'] or delay['text']
                if len(status_text) > 50:
                    status_text = status_text[:50] + "..."
                draw.text((40, y_offset), status_text, font=f_status, fill=(180, 80, 80))
                y_offset += 28
            
            draw.line((20, y_offset, screen_width - 20, y_offset), fill=(200, 200, 200), width=1)
            y_offset += 15
        
        draw.text((20, y_offset), "平常運転", font=f_line, fill=(50, 150, 50))
        y_offset += 30
        
        normal_lines = [f"{n['operator']} {n['line']}" for n in normal[:20]]
        normal_text = "、".join(normal_lines)
        
        max_width = screen_width - 60
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
        
        for line in lines[:6]:
            if y_offset > screen_height - 30:
                break
            draw.text((30, y_offset), line, font=f_small, fill=sub_color)
            y_offset += 20
        
        if not train_info:
            draw.text((30, 100), "運行情報を取得できませんでした", font=f_status, fill=sub_color)
            draw.text((30, 130), "APIキーを確認してください", font=f_small, fill=sub_color)
        
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
