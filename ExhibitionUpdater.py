from ImageUpdater import ImageUpdater
import requests
import io
import re
import json
import os
import random
from datetime import date, datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

CACHE_PATH = "./cache/exhibitions.json"
CACHE_TTL_HOURS = 24

# カテゴリ → 背景色（薄めのトーン）
CATEGORY_COLORS = {
    "絵画・平面":       (255, 252, 245),
    "彫刻・立体":       (248, 252, 255),
    "写真":             (245, 250, 255),
    "映像・メディア":   (250, 245, 255),
    "イラスト":         (255, 248, 245),
    "ドローイング":     (255, 253, 245),
    "版画":             (252, 255, 248),
    "インスタレーション": (248, 255, 252),
    "デザイン":         (255, 245, 250),
    "工芸・陶芸":       (252, 248, 240),
    "ファッション":     (255, 245, 255),
    "建築":             (245, 245, 255),
}
DEFAULT_BG = (252, 251, 249)

CLOSED_JP = {
    "Monday": "月",
    "Tuesday": "火",
    "Wednesday": "水",
    "Thursday": "木",
    "Friday": "金",
    "Saturday": "土",
    "Sunday": "日",
    "Holidays": "祝",
}


class ExhibitionUpdater(ImageUpdater):

    def __init__(self):
        super().__init__()
        self.FONT_BOLD_PATH = "./fonts/NotoSansJP-Bold.ttf"
        self.FONT_REG_PATH = "./fonts/NotoSansJP-Regular.ttf"
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

    def fetch_events(self):
        """キャッシュが24時間以上古ければ再取得、それ以外はキャッシュを返す。"""
        JST = timezone(timedelta(hours=9))
        now = datetime.now(JST)

        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
            cached_at = datetime.fromisoformat(cache["cached_at"])
            if (now - cached_at).total_seconds() < CACHE_TTL_HOURS * 3600:
                print(f"ExhibitionUpdater: キャッシュを使用 ({cache['cached_at']})")
                return cache["events"]

        print("ExhibitionUpdater: Tokyo Art Beat から取得中...")
        html = requests.get(
            "https://www.tokyoartbeat.com/ja/events",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        ).text
        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not m:
            raise RuntimeError("__NEXT_DATA__ が見つかりません")

        raw = json.loads(m.group(1))
        fallback = raw["props"]["pageProps"]["fallback"]
        key = list(fallback.keys())[0]
        events = fallback[key]["data"]

        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"cached_at": now.isoformat(), "events": events}, f, ensure_ascii=False)

        print(f"ExhibitionUpdater: {len(events)} 件取得、キャッシュ保存完了")
        return events

    def _in_target_area(self, event):
        """東京・神奈川・千葉・埼玉の会場のみ True を返す。
        東京の会場は地区名（例: "清澄白河、両国"）、他県は県名（例: "神奈川県"）で入っている。"""
        area = (event.get("venue", {})
                     .get("fields", {})
                     .get("localArea", {})
                     .get("fields", {})
                     .get("name", ""))
        ALLOW_PREFECTURES = {"神奈川県", "千葉県", "埼玉県"}
        # 県・府・道で終わる → 明示的な都道府県名。対象外県は除外
        if area.endswith(("県", "府", "道")):
            return area in ALLOW_PREFECTURES
        # それ以外は東京の地区名とみなして含める
        return True

    def get_active_events(self, events):
        today = date.today().isoformat()
        active = [
            e for e in events
            if e.get("scheduleStartsOn", "") <= today <= e.get("scheduleEndsOn", "")
            and self._in_target_area(e)
        ]
        active.sort(key=lambda e: e.get("popularity", 0), reverse=True)
        return active

    def _bg_color(self, categories):
        for cat in categories:
            name = cat.get("fields", {}).get("name", "")
            if name in CATEGORY_COLORS:
                return CATEGORY_COLORS[name]
        return DEFAULT_BG

    def _closed_str(self, event):
        closed = event.get("closedDays", [])
        if not closed:
            return ""
        jp = [CLOSED_JP.get(d, d) for d in closed]
        return "休：" + "・".join(jp)

    def _badge(self, event):
        """NEW / まもなく終了 バッジ文字列を返す。両方該当する場合はまもなく終了優先。"""
        today = date.today()
        ends = event.get("scheduleEndsOn", "")
        starts = event.get("scheduleStartsOn", "")
        try:
            end_date = date.fromisoformat(ends)
            if (end_date - today).days <= 7:
                return ("まもなく終了", (200, 60, 60))
        except ValueError:
            pass
        try:
            start_date = date.fromisoformat(starts)
            if (today - start_date).days <= 7:
                return ("NEW", (46, 140, 80))
        except ValueError:
            pass
        return None

    def _fetch_poster(self, event, cell_w, cell_h):
        """ポスター画像を取得してセルサイズにリサイズして返す。失敗時は None。"""
        try:
            url = (event.get("imageposter", {})
                        .get("fields", {})
                        .get("file", {})
                        .get("url", ""))
            if not url:
                return None
            # Contentful Images API でJPEGに変換しリサイズ
            full_url = f"https:{url}?fm=jpg&w={cell_w}&h={cell_h}&fit=fill"
            resp = requests.get(full_url, timeout=10)
            resp.raise_for_status()
            poster = Image.open(io.BytesIO(resp.content)).convert("RGB")
            poster = poster.resize((cell_w, cell_h), Image.LANCZOS)
            return poster
        except Exception:
            return None

    def _fmt_date(self, d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%-m/%-d")
        except Exception:
            return d

    def _draw_wrapped(self, draw, text, font, x, y, max_width, fill, line_height, max_lines, stroke_width=0, stroke_fill=None):
        line = ""
        lines = []
        for ch in text:
            test = line + ch
            if draw.textlength(test, font=font) <= max_width:
                line = test
            else:
                lines.append(line)
                line = ch
                if len(lines) >= max_lines:
                    break
        if line and len(lines) < max_lines:
            lines.append(line)

        for line_text in lines:
            draw.text((x, y), line_text, font=font, fill=fill,
                      stroke_width=stroke_width, stroke_fill=stroke_fill)
            y += line_height
        return y

    def create_screen(self, four_events):
        """4件の展示会を2×2レイアウトで800×480の画像に描画する。"""
        img = Image.new("RGB", (800, 480), color=(240, 238, 235))
        draw = ImageDraw.Draw(img)

        f_venue  = ImageFont.truetype(self.FONT_BOLD_PATH, 17)
        f_title  = ImageFont.truetype(self.FONT_REG_PATH,  16)
        f_sub    = ImageFont.truetype(self.FONT_REG_PATH,  13)
        f_date   = ImageFont.truetype(self.FONT_BOLD_PATH, 17)
        f_badge  = ImageFont.truetype(self.FONT_BOLD_PATH, 13)

        CELL_W, CELL_H = 400, 240
        POSITIONS = [(0, 0), (400, 0), (0, 240), (400, 240)]
        DIVIDER   = (195, 190, 183)
        PAD       = 16

        for i, event in enumerate(four_events):
            cx, cy = POSITIONS[i]
            categories = event.get("categories", [])

            # ---- ポスター背景 or カテゴリ背景色 ----
            poster = self._fetch_poster(event, CELL_W, CELL_H)
            if poster:
                # ポスターを貼り、暗めのオーバーレイをかけて文字を読みやすくする
                img.paste(poster, (cx, cy))
                dark = Image.new("RGB", (CELL_W, CELL_H), (0, 0, 0))
                cell = img.crop((cx, cy, cx + CELL_W, cy + CELL_H))
                blended = Image.blend(cell, dark, alpha=0.52)
                img.paste(blended, (cx, cy))
                draw = ImageDraw.Draw(img)
                text_color   = (255, 255, 255)
                sub_color    = (220, 215, 210)
                date_color   = (255, 255, 255)
                closed_color = (220, 215, 210)
                stroke_w     = 2
                stroke_c     = (0, 0, 0)
            else:
                bg = self._bg_color(categories)
                draw.rectangle((cx, cy, cx + CELL_W - 1, cy + CELL_H - 1), fill=bg)
                text_color   = (35, 35, 35)
                sub_color    = (120, 110, 100)
                date_color   = (100, 90, 80)
                closed_color = (160, 140, 120)
                stroke_w     = 0
                stroke_c     = None

            venue_name  = event.get("venue", {}).get("fields", {}).get("fullName", "")
            event_name  = event.get("eventName", "")
            starts      = event.get("scheduleStartsOn", "")
            ends        = event.get("scheduleEndsOn", "")
            area        = (event.get("venue", {})
                               .get("fields", {})
                               .get("localArea", {})
                               .get("fields", {})
                               .get("name", ""))
            cat_names   = [c.get("fields", {}).get("name", "") for c in categories]
            cat_str     = " / ".join(cat_names[:2])
            closed_str  = self._closed_str(event)
            badge       = self._badge(event)
            date_str    = f"{self._fmt_date(starts)} – {self._fmt_date(ends)}"

            y = cy + PAD

            # ---- 会場名 ----
            draw.text((cx + PAD, y), venue_name, font=f_venue, fill=text_color,
                      stroke_width=stroke_w, stroke_fill=stroke_c)
            y += 24

            # ---- エリア | カテゴリ ----
            sub_parts = [p for p in [area, cat_str] if p]
            sub = "  |  ".join(sub_parts)
            draw.text((cx + PAD, y), sub, font=f_sub, fill=sub_color,
                      stroke_width=stroke_w, stroke_fill=stroke_c)
            y += 20

            # ---- バッジ ----
            if badge:
                badge_text, badge_color = badge
                bw = draw.textlength(badge_text, font=f_badge) + 10
                draw.rectangle((cx + PAD, y, cx + PAD + bw, y + 18),
                               fill=badge_color)
                draw.text((cx + PAD + 5, y + 2), badge_text,
                          font=f_badge, fill=(255, 255, 255))
                y += 24

            # ---- 展示タイトル ----
            max_lines = 3 if badge else 4
            y = self._draw_wrapped(draw, event_name, f_title,
                                   cx + PAD, y,
                                   max_width=CELL_W - PAD * 2,
                                   fill=text_color,
                                   line_height=22,
                                   max_lines=max_lines,
                                   stroke_width=stroke_w,
                                   stroke_fill=stroke_c)

            # ---- 下部：会期 & 休館日 ----
            bottom_y = cy + CELL_H - PAD - 20
            draw.text((cx + PAD, bottom_y), date_str,
                      font=f_date, fill=date_color,
                      stroke_width=stroke_w, stroke_fill=stroke_c)
            if closed_str:
                cl_w = draw.textlength(closed_str, font=f_sub)
                draw.text((cx + CELL_W - PAD - cl_w, bottom_y + 4), closed_str,
                          font=f_sub, fill=closed_color,
                          stroke_width=stroke_w, stroke_fill=stroke_c)

        # ---- 区切り線 ----
        draw.line([(400, 0), (400, 480)], fill=DIVIDER, width=1)
        draw.line([(0, 240), (800, 240)], fill=DIVIDER, width=1)

        return img

    def update(self):
        try:
            events  = self.fetch_events()
            active  = self.get_active_events(events)
            print(f"ExhibitionUpdater: 本日開催中 {len(active)} 件")

            if len(active) == 0:
                print("ExhibitionUpdater: 開催中の展示が見つかりません")
                return

            if len(active) < 12:
                active = active + random.choices(active, k=12 - len(active))

            selected = random.sample(active, 12)

            imgs = [
                self.create_screen(selected[0:4]),
                self.create_screen(selected[4:8]),
                self.create_screen(selected[8:12]),
            ]
            self.image_request(imgs)
        except Exception as e:
            print(f"ExhibitionUpdater Error: {e}")


if __name__ == "__main__":
    updater = ExhibitionUpdater()
    updater.update()
