"""
KafkaUpdater: Kafka クラスタのメトリクスを e-paper ディスプレイに表示する。
danielqsj/kafka-exporter が Prometheus に公開するメトリクスを使用。

画面構成:
  画面1 — クラスタ概要 (ブローカー数 / トピック / パーティション / URP)
  画面2 — CG × トピック別ラグ詳細・2列 (1/2)
            CG ヘッダー行: ラグ + Δ10m + 1時間スパークライン
            トピック行   : ラグ + Δ10m
  画面3 — CG × トピック別ラグ詳細・2列 (2/2)
"""

from PIL import Image, ImageDraw
from PrometheusBase import (
    PrometheusBase,
    COLOR_BG, COLOR_FG, COLOR_SUB, COLOR_OK, COLOR_WARN, COLOR_CRIT,
    COLOR_NEUTRAL, COLOR_BORDER,
    FONT_REG, FONT_BOLD, _load_font,
)


LAG_WARN = 1_000
LAG_CRIT = 10_000

# 行の高さ
CG_H    = 36   # CG ヘッダー: テキスト行 + スパークライン
TOPIC_H = 20   # トピック行
SEP_H   = 6    # グループ間空白
ROW_HEIGHT = {"cg": CG_H, "topic": TOPIC_H, "sep": SEP_H}

# 画面レイアウト
ROW_START_Y = 48
COL_W       = 400
MAX_COL_H   = 456 - ROW_START_Y  # 408px

# 列内 x 座標 (列先頭からの相対)
LAG_X   = 242  # ラグ値
DELTA_X = 297  # Δ値
NAME_MAX = 30  # 名前の最大文字数


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


def _fmt_delta(delta: float | None) -> tuple[str, tuple]:
    """(表示文字列, 色) を返す"""
    if delta is None:
        return "—", COLOR_SUB
    if delta > 0:
        return f"+{_fmt_lag(delta)}", COLOR_CRIT
    if delta < 0:
        return f"−{_fmt_lag(-delta)}", COLOR_OK
    return "—", COLOR_SUB


class KafkaUpdater(PrometheusBase):

    # ── Prometheus クエリ ─────────────────────────────────────────────────────

    def _collect_kafka_metrics(self) -> dict:
        m = {}
        m["brokers"]           = self._query_scalar("kafka_brokers")
        m["topic_parts"]       = self._query("kafka_topic_partitions", key="topic")
        m["topic_urp"]         = self._query(
            "sum by (topic)(kafka_topic_partition_under_replicated_partition)", key="topic"
        )
        m["total_urp"]         = self._query_scalar(
            "sum(kafka_topic_partition_under_replicated_partition)"
        )
        m["cg_lag"]            = self._query(
            "sum by (consumergroup)(kafka_consumergroup_lag)", key="consumergroup"
        )
        m["cg_lag_delta"]      = self._query(
            "sum by (consumergroup)(kafka_consumergroup_lag)"
            " - sum by (consumergroup)(kafka_consumergroup_lag offset 10m)",
            key="consumergroup",
        )
        m["cg_lag_history"]    = self._query_range(
            "sum by (consumergroup)(kafka_consumergroup_lag)",
            duration_s=3600, step=120, key="consumergroup",
        )
        m["cg_topic_lag"]      = self._query_multi(
            "sum by (consumergroup, topic)(kafka_consumergroup_lag)",
            ["consumergroup", "topic"],
        )
        m["cg_topic_lag_delta"] = self._query_multi(
            "sum by (consumergroup, topic)(kafka_consumergroup_lag)"
            " - sum by (consumergroup, topic)(kafka_consumergroup_lag offset 10m)",
            ["consumergroup", "topic"],
        )
        return m

    # ── 列パッキング (高さベース、グループをまたがない) ───────────────────────

    def _build_columns(self, m: dict) -> list[list[tuple]]:
        groups = []
        for cg, total_lag in sorted(m["cg_lag"].items(), key=lambda x: x[0]):
            delta_cg = m["cg_lag_delta"].get(cg)
            hist_cg  = m["cg_lag_history"].get(cg, [])
            group = [("cg", cg, total_lag, delta_cg, hist_cg)]
            for topic, lag in sorted(
                [(t, l) for (g, t), l in m["cg_topic_lag"].items() if g == cg],
                key=lambda x: -x[1],
            ):
                delta_t = m["cg_topic_lag_delta"].get((cg, topic))
                group.append(("topic", topic, lag, delta_t, None))
            groups.append(group)

        columns: list[list[tuple]] = []
        current: list[tuple] = []
        cur_h = 0

        for group in groups:
            sep_h = SEP_H if current else 0
            grp_h = sum(ROW_HEIGHT[r[0]] for r in group)
            if cur_h + sep_h + grp_h > MAX_COL_H:
                columns.append(current)
                current = []
                cur_h   = 0
                sep_h   = 0
            if sep_h:
                current.append(("sep", "", 0, None, None))
                cur_h += sep_h
            current.extend(group)
            cur_h += grp_h

        if current:
            columns.append(current)
        return columns

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

    # ── 画面2・3: CG × トピック別ラグ詳細・2列 ──────────────────────────────

    def _draw_sparkline(self, draw, x, y, w, h, values):
        if not values or len(values) < 2:
            return
        lo, hi = min(values), max(values)
        if hi == lo:
            mid = y + h // 2
            draw.line([(x, mid), (x + w, mid)], fill=COLOR_NEUTRAL, width=1)
            return
        def pt(i, v):
            px = x + int(i * w / (len(values) - 1))
            py = y + h - int((v - lo) / (hi - lo) * h)
            return px, py
        prev = None
        for i, v in enumerate(values):
            cur = pt(i, v)
            if prev:
                draw.line([prev, cur], fill=COLOR_NEUTRAL, width=1)
            prev = cur

    def _screen_cg_lag_detail(self, left_col: list, right_col: list, page: str) -> Image.Image:
        canvas = Image.new("RGB", (800, 480), COLOR_BG)
        draw   = ImageDraw.Draw(canvas)

        f_title = _load_font(FONT_BOLD, 16)
        f_hdr   = _load_font(FONT_BOLD, 12)
        f_cg    = _load_font(FONT_BOLD, 11)
        f_body  = _load_font(FONT_REG,  11)
        f_val   = _load_font(FONT_BOLD, 11)

        draw.text((8, 6), f"CG Lag by Topic  ({page})", font=f_title, fill=COLOR_FG)
        draw.line([(0, 26), (800, 26)], fill=COLOR_BORDER, width=1)

        for col_idx in range(2):
            cx = col_idx * COL_W
            draw.text((cx + 8,       30), "Consumer Group / Topic", font=f_hdr, fill=COLOR_SUB)
            draw.text((cx + LAG_X,   30), "Lag",                    font=f_hdr, fill=COLOR_SUB)
            draw.text((cx + DELTA_X, 30), "Δ10m",                   font=f_hdr, fill=COLOR_SUB)

        draw.line([(0, 44), (800, 44)], fill=COLOR_BORDER, width=1)
        draw.line([(COL_W, 26), (COL_W, 479)], fill=COLOR_BORDER, width=1)

        for col_idx, col_data in enumerate([left_col, right_col]):
            cx = col_idx * COL_W
            y  = ROW_START_Y

            for kind, name, lag, delta, history in col_data:
                h     = ROW_HEIGHT[kind]
                color = _lag_color(lag)

                if kind == "sep":
                    y += h
                    continue

                if kind == "cg":
                    draw.rectangle((cx, y, cx + COL_W - 1, y + h - 1), fill=(245, 245, 250))
                    draw.ellipse((cx + 8, y + 4, cx + 16, y + 12), fill=color)
                    draw.text((cx + 20,    y + 2), name[:NAME_MAX], font=f_cg,  fill=COLOR_FG)
                    draw.text((cx + LAG_X, y + 2), _fmt_lag(lag),   font=f_val, fill=color)
                    delta_str, delta_color = _fmt_delta(delta)
                    draw.text((cx + DELTA_X, y + 2), delta_str, font=f_val, fill=delta_color)
                    # スパークライン (下半分)
                    spark_y = y + 18
                    spark_h = h - 22  # 14px
                    draw.rectangle((cx + 8, spark_y, cx + COL_W - 8, spark_y + spark_h),
                                   fill=(240, 244, 255))
                    if history:
                        self._draw_sparkline(draw, cx + 8, spark_y,
                                             COL_W - 16, spark_h, history)
                else:
                    draw.text((cx + 24,    y + 2), name[:NAME_MAX], font=f_body, fill=COLOR_SUB)
                    draw.text((cx + LAG_X, y + 2), _fmt_lag(lag),   font=f_body, fill=color)
                    delta_str, delta_color = _fmt_delta(delta)
                    draw.text((cx + DELTA_X, y + 2), delta_str, font=f_body, fill=delta_color)

                draw.line([(cx, y + h - 1), (cx + COL_W - 1, y + h - 1)],
                          fill=(230, 230, 230), width=1)
                y += h

        self._stamp(canvas, f"CG Lag Detail {page}")
        return canvas

    # ── エントリポイント ───────────────────────────────────────────────────────

    def update(self):
        print("[KafkaUpdater] メトリクス取得中...")
        m    = self._collect_kafka_metrics()
        cols = self._build_columns(m)

        def col(i): return cols[i] if i < len(cols) else []

        img1 = self._screen_cluster_health(m)
        img2 = self._screen_cg_lag_detail(col(0), col(1), "1/2")
        img3 = self._screen_cg_lag_detail(col(2), col(3), "2/2")

        self.image_request([img1, img2, img3])


if __name__ == "__main__":
    updater = KafkaUpdater()
    updater.update()
