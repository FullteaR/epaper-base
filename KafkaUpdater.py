"""
KafkaUpdater: Kafka クラスタのメトリクスを e-paper ディスプレイに表示する。
danielqsj/kafka-exporter が Prometheus に公開するメトリクスを使用。

画面構成:
  画面1 — クラスタ概要 (ブローカー数 / トピック / パーティション / URP)
  画面2 — CG × トピック別ラグ詳細・2列表示 (1/2)
  画面3 — CG × トピック別ラグ詳細・2列表示 (2/2)
"""

from PIL import Image, ImageDraw
from PrometheusBase import (
    PrometheusBase,
    COLOR_BG, COLOR_FG, COLOR_SUB, COLOR_OK, COLOR_WARN, COLOR_CRIT, COLOR_BORDER,
    FONT_REG, FONT_BOLD, _load_font,
)


LAG_WARN = 1_000
LAG_CRIT = 10_000

ROW_H        = 20
ROW_START_Y  = 48                            # ヘッダー下
ROWS_PER_COL = (456 - ROW_START_Y) // ROW_H  # 20行/列
ROWS_PER_SCR = ROWS_PER_COL * 2              # 40行/画面

COL_W    = 400   # 列幅
LAG_X    = 340   # 列内のラグ表示 x (列先頭からの相対)
NAME_MAX = 40    # 名前の最大文字数


def _lag_color(lag: float):
    if lag == 0:
        return COLOR_OK
    if lag < LAG_WARN:
        return COLOR_WARN
    return COLOR_CRIT


def _fmt_lag(lag: float) -> str:
    if lag >= 1_000_000:
        return f"{lag/1_000_000:.1f}M"
    if lag >= 1_000:
        return f"{lag/1_000:.1f}k"
    return f"{lag:.0f}"


class KafkaUpdater(PrometheusBase):

    # ── Prometheus クエリ ─────────────────────────────────────────────────────

    def _collect_kafka_metrics(self) -> dict:
        m = {}
        m["brokers"]      = self._query_scalar("kafka_brokers")
        m["topic_parts"]  = self._query("kafka_topic_partitions", key="topic")
        m["topic_urp"]    = self._query(
            "sum by (topic)(kafka_topic_partition_under_replicated_partition)",
            key="topic",
        )
        m["total_urp"]    = self._query_scalar(
            "sum(kafka_topic_partition_under_replicated_partition)"
        )
        m["cg_lag"]       = self._query(
            "sum by (consumergroup)(kafka_consumergroup_lag)",
            key="consumergroup",
        )
        m["cg_topic_lag"] = self._query_multi(
            "sum by (consumergroup, topic)(kafka_consumergroup_lag)",
            ["consumergroup", "topic"],
        )
        return m

    def _build_detail_rows(self, m: dict) -> list[tuple[str, str, float]]:
        rows = []
        for cg, total_lag in sorted(m["cg_lag"].items(), key=lambda x: -x[1]):
            rows.append(("cg", cg, total_lag))
            topic_lags = sorted(
                [(t, lag) for (g, t), lag in m["cg_topic_lag"].items() if g == cg],
                key=lambda x: -x[1],
            )
            for topic, lag in topic_lags:
                rows.append(("topic", topic, lag))
        return rows

    # ── 画面1: クラスタ概要 ───────────────────────────────────────────────────

    def _screen_cluster_health(self, m: dict) -> Image.Image:
        canvas = Image.new("RGB", (800, 480), COLOR_BG)
        draw   = ImageDraw.Draw(canvas)

        f_title = _load_font(FONT_BOLD, 16)
        f_hdr   = _load_font(FONT_BOLD, 12)
        f_stat  = _load_font(FONT_BOLD, 22)
        f_slbl  = _load_font(FONT_REG,  11)
        f_body  = _load_font(FONT_REG,  11)

        draw.text((8, 6), "Kafka Cluster", font=f_title, fill=COLOR_FG)
        draw.line([(0, 26), (800, 26)], fill=COLOR_BORDER, width=1)

        brokers     = int(m["brokers"] or 0)
        n_topics    = len(m["topic_parts"])
        total_parts = int(sum(m["topic_parts"].values()))
        total_urp   = int(m["total_urp"] or 0)
        n_cgs       = len(m["cg_lag"])

        stats = [
            ("Brokers",     f"{brokers}",    COLOR_OK if brokers > 0 else COLOR_CRIT),
            ("Topics",      str(n_topics),   COLOR_FG),
            ("Partitions",  str(total_parts), COLOR_FG),
            ("URP",         str(total_urp),  COLOR_OK if total_urp == 0 else COLOR_CRIT),
            ("Con. Groups", str(n_cgs),      COLOR_FG),
        ]
        stat_w = 155
        for i, (label, value, color) in enumerate(stats):
            sx = 8 + i * stat_w
            draw.text((sx, 34), label, font=f_slbl, fill=COLOR_SUB)
            draw.text((sx, 50), value, font=f_stat, fill=color)

        draw.line([(0, 80), (800, 80)], fill=COLOR_BORDER, width=1)

        draw.text((8,   84), "Topic",      font=f_hdr, fill=COLOR_SUB)
        draw.text((530, 84), "Partitions", font=f_hdr, fill=COLOR_SUB)
        draw.text((660, 84), "URP",        font=f_hdr, fill=COLOR_SUB)
        draw.line([(0, 98), (800, 98)], fill=COLOR_BORDER, width=1)

        row_h   = 20
        start_y = 102
        max_rows = (456 - start_y) // row_h

        topics_sorted = sorted(
            m["topic_parts"].items(),
            key=lambda x: (-m["topic_urp"].get(x[0], 0), x[0]),
        )
        for idx, (topic, parts) in enumerate(topics_sorted[:max_rows]):
            y   = start_y + idx * row_h
            urp = int(m["topic_urp"].get(topic, 0))
            draw.text((8,   y), topic[:65],      font=f_body, fill=COLOR_FG)
            draw.text((530, y), str(int(parts)), font=f_body, fill=COLOR_FG)
            draw.text((660, y), str(urp),        font=f_body,
                      fill=COLOR_CRIT if urp > 0 else COLOR_FG)
            draw.line([(0, y + row_h - 1), (800, y + row_h - 1)],
                      fill=(230, 230, 230), width=1)

        self._stamp(canvas, "Kafka Cluster")
        return canvas

    # ── 画面2・3: CG × トピック別ラグ詳細・2列表示 ───────────────────────────

    def _screen_cg_lag_detail(self, rows: list, offset: int, page: str) -> Image.Image:
        canvas = Image.new("RGB", (800, 480), COLOR_BG)
        draw   = ImageDraw.Draw(canvas)

        f_title = _load_font(FONT_BOLD, 16)
        f_hdr   = _load_font(FONT_BOLD, 12)
        f_cg    = _load_font(FONT_BOLD, 11)
        f_body  = _load_font(FONT_REG,  11)
        f_val   = _load_font(FONT_BOLD, 11)

        draw.text((8, 6), f"CG Lag by Topic  ({page})", font=f_title, fill=COLOR_FG)
        draw.line([(0, 26), (800, 26)], fill=COLOR_BORDER, width=1)

        # 列ヘッダー (左右共通)
        for col in range(2):
            cx = col * COL_W
            draw.text((cx + 8,       30), "Consumer Group / Topic", font=f_hdr, fill=COLOR_SUB)
            draw.text((cx + LAG_X,   30), "Lag",                    font=f_hdr, fill=COLOR_SUB)

        draw.line([(0, 44), (800, 44)], fill=COLOR_BORDER, width=1)
        draw.line([(COL_W, 26), (COL_W, 479)], fill=COLOR_BORDER, width=1)

        # 左列・右列それぞれ描画
        for col in range(2):
            cx      = col * COL_W
            col_off = offset + col * ROWS_PER_COL
            slice_  = rows[col_off: col_off + ROWS_PER_COL]

            for idx, (kind, name, lag) in enumerate(slice_):
                y     = ROW_START_Y + idx * ROW_H
                color = _lag_color(lag)

                if kind == "cg":
                    draw.rectangle((cx, y, cx + COL_W - 1, y + ROW_H - 1),
                                   fill=(245, 245, 250))
                    draw.ellipse((cx + 8, y + 4, cx + 16, y + 12), fill=color)
                    draw.text((cx + 20,    y + 2), name[:NAME_MAX], font=f_cg,  fill=COLOR_FG)
                    draw.text((cx + LAG_X, y + 2), _fmt_lag(lag),   font=f_val, fill=color)
                else:
                    draw.text((cx + 24,    y + 2), name[:NAME_MAX], font=f_body, fill=COLOR_SUB)
                    draw.text((cx + LAG_X, y + 2), _fmt_lag(lag),   font=f_body, fill=color)

                draw.line([(cx, y + ROW_H - 1), (cx + COL_W - 1, y + ROW_H - 1)],
                          fill=(230, 230, 230), width=1)

        self._stamp(canvas, f"CG Lag Detail {page}")
        return canvas

    # ── エントリポイント ───────────────────────────────────────────────────────

    def update(self):
        print("[KafkaUpdater] メトリクス取得中...")
        m    = self._collect_kafka_metrics()
        rows = self._build_detail_rows(m)

        img1 = self._screen_cluster_health(m)
        img2 = self._screen_cg_lag_detail(rows, offset=0,           page="1/2")
        img3 = self._screen_cg_lag_detail(rows, offset=ROWS_PER_SCR, page="2/2")

        self.image_request([img1, img2, img3])


if __name__ == "__main__":
    updater = KafkaUpdater()
    updater.update()
