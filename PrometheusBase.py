import time
from datetime import datetime, timezone, timedelta
import requests
from PIL import Image, ImageDraw, ImageFont
from ImageUpdater import ImageUpdater


PROMETHEUS_URL = "http://monitor.cloud.rikuta:9090"

FONT_REG  = "./fonts/NotoSansJP-Regular.ttf"
FONT_BOLD = "./fonts/NotoSansJP-Bold.ttf"

COLOR_BG      = (255, 255, 255)
COLOR_FG      = (20,  20,  20)
COLOR_SUB     = (90,  90,  90)
COLOR_OK      = (30,  140, 30)
COLOR_WARN    = (210, 120, 0)
COLOR_CRIT    = (200, 30,  30)
COLOR_NEUTRAL = (60,  60,  180)
COLOR_BORDER  = (180, 180, 180)


def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


class PrometheusBase(ImageUpdater):

    def __init__(self, prom_url: str = PROMETHEUS_URL):
        super().__init__()
        self.prom = prom_url.rstrip("/")
        self._session = requests.Session()

    def _query(self, promql: str, key: str = "instance") -> dict[str, float]:
        """instant query → {key_label_value: value}"""
        try:
            r = self._session.get(
                f"{self.prom}/api/v1/query",
                params={"query": promql},
                timeout=15,
            )
            r.raise_for_status()
            out = {}
            for item in r.json()["data"]["result"]:
                out[item["metric"].get(key, "")] = float(item["value"][1])
            return out
        except Exception as e:
            print(f"[Prometheus] query failed: {promql[:60]}... → {e}")
            return {}

    def _query_scalar(self, promql: str) -> float | None:
        """instant query → single scalar value"""
        try:
            r = self._session.get(
                f"{self.prom}/api/v1/query",
                params={"query": promql},
                timeout=15,
            )
            r.raise_for_status()
            result = r.json()["data"]["result"]
            return float(result[0]["value"][1]) if result else None
        except Exception as e:
            print(f"[Prometheus] scalar query failed: {promql[:60]}... → {e}")
            return None

    def _query_multi(self, promql: str, keys: list[str]) -> dict[tuple, float]:
        """instant query → {(key_values, ...): value}"""
        try:
            r = self._session.get(
                f"{self.prom}/api/v1/query",
                params={"query": promql},
                timeout=15,
            )
            r.raise_for_status()
            out = {}
            for item in r.json()["data"]["result"]:
                k = tuple(item["metric"].get(key, "") for key in keys)
                out[k] = float(item["value"][1])
            return out
        except Exception as e:
            print(f"[Prometheus] multi-key query failed: {promql[:60]}... → {e}")
            return {}

    def _query_range(self, promql: str, duration_s: int = 3600, step: int = 300) -> dict[str, list[float]]:
        """range query → {instance: [values]}"""
        now = int(time.time())
        try:
            r = self._session.get(
                f"{self.prom}/api/v1/query_range",
                params={
                    "query": promql,
                    "start": now - duration_s,
                    "end":   now,
                    "step":  step,
                },
                timeout=20,
            )
            r.raise_for_status()
            out = {}
            for item in r.json()["data"]["result"]:
                inst = item["metric"].get("instance", "")
                out[inst] = [float(v[1]) for v in item["values"]]
            return out
        except Exception as e:
            print(f"[Prometheus] range query failed: {promql[:60]}... → {e}")
            return {}

    def _stamp(self, img: Image.Image, title: str = ""):
        draw = ImageDraw.Draw(img)
        jst  = timezone(timedelta(hours=9))
        text = datetime.now(jst).strftime("%Y-%m-%d %H:%M JST")
        f    = _load_font(FONT_REG, 12)
        if title:
            draw.text((6, 462), title, font=f, fill=COLOR_SUB)
        tw = draw.textlength(text, font=f)
        x  = int(800 - tw - 6)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + dx, 462 + dy), text, font=f, fill=(255, 255, 255))
        draw.text((x, 462), text, font=f, fill=COLOR_SUB)
