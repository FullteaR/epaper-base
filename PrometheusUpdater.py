"""
PrometheusUpdater: Prometheus メトリクスを e-paper ディスプレイに表示する。

画面構成:
  画面1 — Proxmox 4ノード (proxmox1〜4) の 2×2 ノードカード
  画面2 — Proxmox 以外からランダムに選んだ 4ノードの 2×2 ノードカード
  画面3 — 全ノードのヘルス一覧 (up/down + CPU + MEM + disk)

各ノードカード (400×240px):
  ホスト名 / CPU使用率バー / メモリ使用率バー / ロードアベレージ /
  ネットワーク速度 / CPU 1時間スパークライン
"""

import random
import requests
import time
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from ImageUpdater import ImageUpdater


PROMETHEUS_URL = "http://monitor.cloud.rikuta:9090"

PROXMOX_INSTANCES = [
    "proxmox1.cloud.rikuta:9100",
    "proxmox2.cloud.rikuta:9100",
    "proxmox3.cloud.rikuta:9100",
    "proxmox4.cloud.rikuta:9100",
]

FONT_REG  = "./fonts/NotoSansJP-Regular.ttf"
FONT_BOLD = "./fonts/NotoSansJP-Bold.ttf"

# e-paper 7色パレットに寄せた色
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


def _bar_color(pct: float):
    if pct < 60:
        return COLOR_OK
    if pct < 80:
        return COLOR_WARN
    return COLOR_CRIT


def _fmt_bytes(bps: float) -> str:
    if bps >= 1_000_000:
        return f"{bps/1_000_000:.1f}MB/s"
    if bps >= 1_000:
        return f"{bps/1_000:.0f}KB/s"
    return f"{bps:.0f}B/s"


def _short_host(instance: str) -> str:
    host = instance.split(":")[0]
    for suffix in [".cloud.rikuta", ".server.rikuta", ".raspi.rikuta", ".kafka.server.rikuta"]:
        host = host.replace(suffix, "")
    return host


class PrometheusUpdater(ImageUpdater):

    def __init__(self, prom_url: str = PROMETHEUS_URL):
        super().__init__()
        self.prom = prom_url.rstrip("/")
        self._session = requests.Session()

    # ── Prometheus クエリ ─────────────────────────────────────────────────────

    def _query(self, promql: str) -> dict[str, float]:
        """instant query → {instance: value}"""
        try:
            r = self._session.get(
                f"{self.prom}/api/v1/query",
                params={"query": promql},
                timeout=15,
            )
            r.raise_for_status()
            out = {}
            for item in r.json()["data"]["result"]:
                inst = item["metric"].get("instance", "")
                out[inst] = float(item["value"][1])
            return out
        except Exception as e:
            print(f"[Prometheus] query failed: {promql[:60]}... → {e}")
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

    def _collect_metrics(self) -> dict:
        """全メトリクスを一括取得して辞書で返す。"""
        m = {}
        m["up"]    = self._query("up")
        m["cpu"]   = self._query(
            "100 - avg by(instance)(rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100"
        )
        m["mem"]   = self._query(
            "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"
        )
        m["load1"] = self._query("node_load1")
        m["load5"] = self._query("node_load5")
        m["load15"]= self._query("node_load15")
        m["disk"]  = self._query(
            "(1 - node_filesystem_avail_bytes{mountpoint='/'} "
            "/ node_filesystem_size_bytes{mountpoint='/'}) * 100"
        )
        m["net_rx"]= self._query(
            "sum by(instance)(rate(node_network_receive_bytes_total{device!='lo'}[5m]))"
        )
        m["net_tx"]= self._query(
            "sum by(instance)(rate(node_network_transmit_bytes_total{device!='lo'}[5m]))"
        )
        m["temp"]  = self._query(
            "max by(instance)(node_hwmon_temp_celsius)"
        )
        m["mem_history"] = self._query_range(
            "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"
        )
        return m

    # ── ノードカード描画 (400×240) ────────────────────────────────────────────

    def _draw_bar(self, draw, x, y, w, h, pct, color):
        draw.rectangle((x, y, x + w, y + h), outline=COLOR_BORDER, width=1)
        fill_w = int(w * min(max(pct, 0), 100) / 100)
        if fill_w > 2:
            draw.rectangle((x + 1, y + 1, x + fill_w - 1, y + h - 1), fill=color)

    def _draw_sparkline(self, draw, x, y, w, h, values):
        if not values or len(values) < 2:
            return
        lo, hi = 0, max(max(values), 10)
        def pt(i, v):
            px = x + int(i * (w / (len(values) - 1)))
            py = y + h - int((v - lo) / (hi - lo) * h)
            return px, py
        prev = None
        for i, v in enumerate(values):
            cur = pt(i, v)
            if prev:
                draw.line([prev, cur], fill=COLOR_NEUTRAL, width=1)
            prev = cur

    def _node_card(self, instance: str, m: dict) -> Image.Image:
        img  = Image.new("RGB", (400, 240), COLOR_BG)
        draw = ImageDraw.Draw(img)

        f_host = _load_font(FONT_BOLD, 15)
        f_lbl  = _load_font(FONT_REG,  12)
        f_val  = _load_font(FONT_BOLD, 13)
        f_mini = _load_font(FONT_REG,  11)

        # 枠線
        draw.rectangle((0, 0, 399, 239), outline=COLOR_BORDER, width=1)

        up = m["up"].get(instance, 0)

        # ── ヘッダー ──
        host = _short_host(instance)
        status_color = COLOR_OK if up else COLOR_CRIT
        draw.ellipse((8, 8, 18, 18), fill=status_color)
        draw.text((24, 5), host, font=f_host, fill=COLOR_FG)

        temp = m["temp"].get(instance)
        if temp is not None:
            tc = COLOR_CRIT if temp >= 75 else (COLOR_WARN if temp >= 60 else COLOR_SUB)
            draw.text((310, 6), f"{temp:.0f}°C", font=f_val, fill=tc)

        draw.line([(8, 24), (392, 24)], fill=COLOR_BORDER, width=1)

        if not up:
            draw.text((160, 100), "DOWN", font=_load_font(FONT_BOLD, 36), fill=COLOR_CRIT)
            return img

        # ── CPU バー ──
        cpu = m["cpu"].get(instance, 0)
        y = 32
        draw.text((8, y), "CPU", font=f_lbl, fill=COLOR_SUB)
        self._draw_bar(draw, 50, y + 2, 290, 14, cpu, _bar_color(cpu))
        draw.text((348, y), f"{cpu:4.1f}%", font=f_val, fill=COLOR_FG)

        # ── MEM バー ──
        mem = m["mem"].get(instance, 0)
        y = 54
        draw.text((8, y), "MEM", font=f_lbl, fill=COLOR_SUB)
        self._draw_bar(draw, 50, y + 2, 290, 14, mem, _bar_color(mem))
        draw.text((348, y), f"{mem:4.1f}%", font=f_val, fill=COLOR_FG)

        # ── ディスク バー ──
        disk = m["disk"].get(instance, 0)
        y = 76
        draw.text((8, y), "Disk", font=f_lbl, fill=COLOR_SUB)
        self._draw_bar(draw, 50, y + 2, 290, 14, disk, _bar_color(disk))
        draw.text((348, y), f"{disk:4.1f}%", font=f_val, fill=COLOR_FG)

        # ── ロードアベレージ ──
        l1  = m["load1"].get(instance,  0)
        l5  = m["load5"].get(instance,  0)
        l15 = m["load15"].get(instance, 0)
        y = 98
        draw.text((8, y), "Load", font=f_lbl, fill=COLOR_SUB)
        draw.text((52, y), f"{l1:.2f}  {l5:.2f}  {l15:.2f}", font=f_val, fill=COLOR_FG)

        # ── ネットワーク ──
        rx = m["net_rx"].get(instance, 0)
        tx = m["net_tx"].get(instance, 0)
        y = 118
        draw.text((8, y), "Net", font=f_lbl, fill=COLOR_SUB)
        draw.text((42, y), f"↓{_fmt_bytes(rx)}  ↑{_fmt_bytes(tx)}", font=f_mini, fill=COLOR_FG)

        # ── CPU スパークライン (1h) ──
        history = m["mem_history"].get(instance, [])
        spark_y = 138
        draw.rectangle((8, spark_y, 391, 228), fill=(245, 248, 255))
        draw.text((8, spark_y + 1), "MEM 1h", font=f_mini, fill=COLOR_SUB)
        self._draw_sparkline(draw, 8, spark_y + 14, 384, 74, history)

        return img

    # ── 2×2 ノード画面 ────────────────────────────────────────────────────────

    def _screen_nodes(self, instances: list[str], m: dict, title: str) -> Image.Image:
        canvas = Image.new("RGB", (800, 480), COLOR_BG)
        positions = [(0, 0), (400, 0), (0, 240), (400, 240)]
        for i, inst in enumerate(instances[:4]):
            card = self._node_card(inst, m)
            canvas.paste(card, positions[i])
        self._stamp(canvas, title)
        return canvas

    # ── ヘルス一覧画面 ────────────────────────────────────────────────────────

    def _screen_health(self, m: dict) -> Image.Image:
        canvas = Image.new("RGB", (800, 480), COLOR_BG)
        draw   = ImageDraw.Draw(canvas)

        f_title = _load_font(FONT_BOLD, 16)
        f_host  = _load_font(FONT_BOLD, 12)
        f_val   = _load_font(FONT_REG,  11)
        f_hdr   = _load_font(FONT_REG,  11)

        draw.text((8, 6), "Infrastructure Health", font=f_title, fill=COLOR_FG)
        jst = timezone(timedelta(hours=9))
        draw.text((530, 8), datetime.now(jst).strftime("%Y-%m-%d %H:%M JST"),
                  font=f_val, fill=COLOR_SUB)
        draw.line([(0, 26), (800, 26)], fill=COLOR_BORDER, width=1)

        # ヘッダー行
        for col_x in (0, 400):
            x = col_x + 8
            draw.text((x + 16, 30), "Host",    font=f_hdr, fill=COLOR_SUB)
            draw.text((x + 130, 30), "CPU",    font=f_hdr, fill=COLOR_SUB)
            draw.text((x + 195, 30), "MEM",    font=f_hdr, fill=COLOR_SUB)
            draw.text((x + 255, 30), "Disk",   font=f_hdr, fill=COLOR_SUB)
            draw.text((x + 315, 30), "Load",   font=f_hdr, fill=COLOR_SUB)

        draw.line([(0, 44), (800, 44)], fill=COLOR_BORDER, width=1)

        # 全インスタンスを up/down でソートして表示
        all_inst = sorted(
            m["up"].keys(),
            key=lambda i: (0 if m["up"].get(i, 0) < 1 else 1, _short_host(i))
        )

        row_h  = 26
        start_y = 48
        max_rows = (480 - start_y) // row_h  # 片列最大行数

        for idx, inst in enumerate(all_inst):
            col = 0 if idx < max_rows else 1
            row = idx if idx < max_rows else idx - max_rows
            if col == 1 and row >= max_rows:
                break  # 溢れたら無視

            x = col * 400 + 8
            y = start_y + row * row_h

            up   = m["up"].get(inst, 0)
            cpu  = m["cpu"].get(inst)
            mem  = m["mem"].get(inst)
            disk = m["disk"].get(inst)
            l1   = m["load1"].get(inst)

            # ステータスドット
            dot_color = COLOR_OK if up >= 1 else COLOR_CRIT
            draw.ellipse((x, y + 5, x + 10, y + 15), fill=dot_color)

            # ホスト名
            host = _short_host(inst)[:16]
            draw.text((x + 14, y + 3), host, font=f_host,
                      fill=COLOR_FG if up else COLOR_CRIT)

            if not up:
                draw.text((x + 130, y + 3), "DOWN", font=f_val, fill=COLOR_CRIT)
                continue

            # CPU
            if cpu is not None:
                draw.text((x + 130, y + 3), f"{cpu:4.0f}%", font=f_val,
                          fill=_bar_color(cpu))
            # MEM
            if mem is not None:
                draw.text((x + 190, y + 3), f"{mem:4.0f}%", font=f_val,
                          fill=_bar_color(mem))
            # Disk
            if disk is not None:
                draw.text((x + 250, y + 3), f"{disk:4.0f}%", font=f_val,
                          fill=_bar_color(disk))
            # Load
            if l1 is not None:
                draw.text((x + 310, y + 3), f"{l1:.2f}", font=f_val,
                          fill=COLOR_FG)

            # 行区切り
            draw.line([(col * 400, y + row_h - 1), (col * 400 + 398, y + row_h - 1)],
                      fill=(230, 230, 230), width=1)

        # 列区切り
        draw.line([(400, 26), (400, 479)], fill=COLOR_BORDER, width=1)

        return canvas

    # ── タイムスタンプ ────────────────────────────────────────────────────────

    def _stamp(self, img: Image.Image, title: str = ""):
        draw = ImageDraw.Draw(img)
        jst  = timezone(timedelta(hours=9))
        text = datetime.now(jst).strftime("%Y-%m-%d %H:%M JST")
        f    = _load_font(FONT_REG, 12)
        if title:
            draw.text((6, 462), title, font=f, fill=COLOR_SUB)
        tw = draw.textlength(text, font=f)
        x  = int(800 - tw - 6)
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            draw.text((x+dx, 462+dy), text, font=f, fill=(255,255,255))
        draw.text((x, 462), text, font=f, fill=COLOR_SUB)

    # ── エントリポイント ───────────────────────────────────────────────────────

    def update(self):
        print("[PrometheusUpdater] メトリクス取得中...")
        m = self._collect_metrics()

        # 画面1: Proxmox 4ノード
        img1 = self._screen_nodes(PROXMOX_INSTANCES, m, "Proxmox Cluster")

        # 画面2: Proxmox 以外からランダム4ノード（up=1 を優先）
        non_proxmox = [
            i for i in m["up"].keys()
            if i not in PROXMOX_INSTANCES
        ]
        up_nodes   = [i for i in non_proxmox if m["up"].get(i, 0) >= 1]
        down_nodes = [i for i in non_proxmox if m["up"].get(i, 0) < 1]
        # up なノードを優先してランダムに4つ選ぶ
        random.shuffle(up_nodes)
        random.shuffle(down_nodes)
        selected = (up_nodes + down_nodes)[:4]
        img2 = self._screen_nodes(selected, m, "Random Nodes")

        # 画面3: 全体ヘルス
        img3 = self._screen_health(m)

        self.image_request([img1, img2, img3])


# ── 単体テスト ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    updater = PrometheusUpdater()
    updater.update()
