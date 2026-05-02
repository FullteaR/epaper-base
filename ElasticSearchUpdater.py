"""
ElasticSearchUpdater: ES クラスタのメトリクスを e-paper ディスプレイに表示する。
prometheus-community/elasticsearch_exporter のメトリクスを使用。
--es.indices フラグが必要。

画面構成:
  画面1 — クラスタ概要 (status / nodes / shards / 総docs・store / QPS)
  画面2 — インデックス別 health・docs・store・Δ10m (前半, 2列)
  画面3 — インデックス別 health・docs・store・Δ10m (後半, 2列)
"""

from PIL import Image, ImageDraw
from PrometheusBase import (
    PrometheusBase,
    COLOR_BG, COLOR_FG, COLOR_SUB, COLOR_OK, COLOR_WARN, COLOR_CRIT,
    COLOR_NEUTRAL, COLOR_BORDER,
    FONT_REG, FONT_BOLD, _load_font,
)


# インデックス一覧の行レイアウト
ROW_H        = 20
ROW_START_Y  = 48
ROWS_PER_COL = (456 - ROW_START_Y) // ROW_H  # 20行/列
ROWS_PER_SCR = ROWS_PER_COL * 2               # 40行/画面
COL_W        = 400

# 列内 x 座標 (列先頭からの相対)
NAME_X   = 20    # インデックス名
DOCS_X   = 185   # ドキュメント数
STORE_X  = 248   # ストレージ
DELTA_X  = 318   # Δ10m
NAME_MAX = 22    # (NAME_X + NAME_MAX*7 ≈ DOCS_X)


def _fmt_docs(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return f"{n:.0f}"


def _fmt_bytes(b: float) -> str:
    if b >= 1 << 40:
        return f"{b/(1<<40):.1f}TB"
    if b >= 1 << 30:
        return f"{b/(1<<30):.2f}GB"
    if b >= 1 << 20:
        return f"{b/(1<<20):.1f}MB"
    return f"{b/(1<<10):.0f}KB"


def _fmt_delta(delta: float | None) -> tuple[str, tuple]:
    """(表示文字列, 色) — 増加=青(中立), 減少=橙, ゼロ=灰"""
    if delta is None or delta == 0:
        return "—", COLOR_SUB
    if delta > 0:
        return f"+{_fmt_docs(delta)}", COLOR_NEUTRAL
    return f"−{_fmt_docs(-delta)}", COLOR_WARN


def _status_color(status_map: dict) -> tuple[str, tuple]:
    if status_map.get("red", 0) >= 1:
        return "RED",    COLOR_CRIT
    if status_map.get("yellow", 0) >= 1:
        return "YELLOW", COLOR_WARN
    return "GREEN", COLOR_OK


def _idx_dot_color(idx_health: dict, index: str) -> tuple:
    if idx_health.get((index, "red"), 0) >= 1:
        return COLOR_CRIT
    if idx_health.get((index, "yellow"), 0) >= 1:
        return COLOR_WARN
    if idx_health.get((index, "green"), 0) >= 1:
        return COLOR_OK
    return COLOR_SUB


class ElasticSearchUpdater(PrometheusBase):

    # ── Prometheus クエリ ─────────────────────────────────────────────────────

    def _collect_es_metrics(self) -> dict:
        m = {}
        m["cluster_status"]  = self._query(
            "elasticsearch_cluster_health_status", key="color"
        )
        m["nodes"]           = self._query_scalar(
            "elasticsearch_cluster_health_number_of_nodes"
        )
        m["data_nodes"]      = self._query_scalar(
            "elasticsearch_cluster_health_number_of_data_nodes"
        )
        m["shards"]          = self._query_scalar(
            "elasticsearch_cluster_health_active_shards"
        )
        m["primary_shards"]  = self._query_scalar(
            "elasticsearch_cluster_health_active_primary_shards"
        )
        m["unassigned"]      = self._query_scalar(
            "elasticsearch_cluster_health_unassigned_shards"
        )
        m["relocating"]      = self._query_scalar(
            "elasticsearch_cluster_health_relocating_shards"
        )
        m["pending_tasks"]   = self._query_scalar(
            "elasticsearch_cluster_health_number_of_pending_tasks"
        )
        m["total_docs"]      = self._query_scalar(
            "sum(elasticsearch_indices_docs_primary)"
        )
        m["store_bytes"]     = self._query_scalar(
            "sum(elasticsearch_indices_store_size_bytes_total)"
        )
        m["search_qps"]      = self._query(
            "rate(elasticsearch_indices_search_query_total[5m])", key="name"
        )
        m["index_qps"]       = self._query(
            "rate(elasticsearch_indices_indexing_index_total[5m])", key="name"
        )
        # インデックス別
        m["idx_docs"]  = self._query(
            "sum by (index) (elasticsearch_indices_docs_primary)", key="index"
        )
        m["idx_delta"] = self._query(
            "sum by (index) (elasticsearch_indices_docs_primary)"
            " - sum by (index) (elasticsearch_indices_docs_primary offset 10m)",
            key="index",
        )
        m["idx_store"]  = self._query(
            "sum by (index) (elasticsearch_indices_store_size_bytes_total)", key="index"
        )
        m["idx_health"] = self._query_multi(
            "elasticsearch_index_health_status", ["index", "color"]
        )
        return m

    # ── 画面1: クラスタ概要 ───────────────────────────────────────────────────

    def _screen_cluster(self, m: dict) -> Image.Image:
        canvas = Image.new("RGB", (800, 480), COLOR_BG)
        draw   = ImageDraw.Draw(canvas)

        f_title  = _load_font(FONT_BOLD, 16)
        f_status = _load_font(FONT_BOLD, 28)
        f_hdr    = _load_font(FONT_BOLD, 12)
        f_lbl    = _load_font(FONT_REG,  11)
        f_val    = _load_font(FONT_BOLD, 13)
        f_sub    = _load_font(FONT_REG,  11)

        draw.text((8, 6), "Elasticsearch", font=f_title, fill=COLOR_FG)
        draw.line([(0, 26), (800, 26)], fill=COLOR_BORDER, width=1)

        # ── ステータス ──
        status_str, status_color = _status_color(m["cluster_status"])
        draw.ellipse((12, 36, 28, 52), fill=status_color)
        draw.text((36, 34), status_str, font=f_status, fill=status_color)

        # ── ノード / シャード統計 ──
        stats = [
            ("Nodes",      m["nodes"],          COLOR_FG),
            ("Data",       m["data_nodes"],      COLOR_FG),
            ("Shards",     m["shards"],          COLOR_FG),
            ("Primary",    m["primary_shards"],  COLOR_FG),
            ("Unassigned", m["unassigned"],      COLOR_OK if (m["unassigned"] or 0) == 0 else COLOR_CRIT),
            ("Relocating", m["relocating"],      COLOR_FG),
            ("Pending",    m["pending_tasks"],   COLOR_OK if (m["pending_tasks"] or 0) == 0 else COLOR_WARN),
        ]
        stat_w = 110
        for i, (label, value, color) in enumerate(stats):
            sx = 8 + i * stat_w
            draw.text((sx, 62), label, font=f_sub, fill=COLOR_SUB)
            draw.text((sx, 76), str(int(value or 0)), font=f_val, fill=color)

        draw.line([(0, 96), (800, 96)], fill=COLOR_BORDER, width=1)

        # ── 総ドキュメント数・ストレージ ──
        draw.text((8,   102), "Total Docs", font=f_lbl, fill=COLOR_SUB)
        draw.text((120, 102), _fmt_docs(m["total_docs"] or 0), font=f_val, fill=COLOR_FG)
        draw.text((260, 102), "Store", font=f_lbl, fill=COLOR_SUB)
        draw.text((310, 102), _fmt_bytes(m["store_bytes"] or 0), font=f_val, fill=COLOR_FG)

        draw.line([(0, 120), (800, 120)], fill=COLOR_BORDER, width=1)

        # ── ノード別 QPS ──
        draw.text((8,   126), "Node", font=f_hdr, fill=COLOR_SUB)
        draw.text((200, 126), "Search QPS", font=f_hdr, fill=COLOR_SUB)
        draw.text((400, 126), "Index QPS",  font=f_hdr, fill=COLOR_SUB)
        draw.line([(0, 140), (800, 140)], fill=COLOR_BORDER, width=1)

        all_nodes = sorted(set(m["search_qps"]) | set(m["index_qps"]))
        for idx, node in enumerate(all_nodes):
            y  = 144 + idx * 24
            sq = m["search_qps"].get(node)
            iq = m["index_qps"].get(node)
            draw.text((8,   y), node[:20],                  font=f_val, fill=COLOR_FG)
            draw.text((200, y), f"{sq:.1f}" if sq else "—", font=f_val, fill=COLOR_NEUTRAL)
            draw.text((400, y), f"{iq:.1f}" if iq else "—", font=f_val, fill=COLOR_NEUTRAL)
            draw.line([(0, y + 22), (800, y + 22)], fill=(230, 230, 230), width=1)

        self._stamp(canvas, "Elasticsearch")
        return canvas

    # ── 画面2・3: インデックス別詳細 (2列) ──────────────────────────────────

    def _screen_indices(self, rows: list[tuple], offset: int, page: str) -> Image.Image:
        canvas = Image.new("RGB", (800, 480), COLOR_BG)
        draw   = ImageDraw.Draw(canvas)

        f_title = _load_font(FONT_BOLD, 16)
        f_hdr   = _load_font(FONT_BOLD, 12)
        f_body  = _load_font(FONT_REG,  11)
        f_val   = _load_font(FONT_BOLD, 11)

        draw.text((8, 6), f"Elasticsearch Indices  ({page})", font=f_title, fill=COLOR_FG)
        draw.line([(0, 26), (800, 26)], fill=COLOR_BORDER, width=1)

        for col_idx in range(2):
            cx = col_idx * COL_W
            draw.text((cx + NAME_X,  30), "Index", font=f_hdr, fill=COLOR_SUB)
            draw.text((cx + DOCS_X,  30), "Docs",  font=f_hdr, fill=COLOR_SUB)
            draw.text((cx + STORE_X, 30), "Store", font=f_hdr, fill=COLOR_SUB)
            draw.text((cx + DELTA_X, 30), "Δ10m",  font=f_hdr, fill=COLOR_SUB)

        draw.line([(0, 44), (800, 44)], fill=COLOR_BORDER, width=1)
        draw.line([(COL_W, 26), (COL_W, 479)], fill=COLOR_BORDER, width=1)

        for col_idx in range(2):
            cx      = col_idx * COL_W
            col_off = offset + col_idx * ROWS_PER_COL
            for row_idx, (name, hcolor, docs, store, delta) in enumerate(
                rows[col_off: col_off + ROWS_PER_COL]
            ):
                y = ROW_START_Y + row_idx * ROW_H

                draw.ellipse((cx + 8, y + 6, cx + 16, y + 14), fill=hcolor)
                draw.text((cx + NAME_X,  y + 2), name[:NAME_MAX],  font=f_body, fill=COLOR_FG)
                draw.text((cx + DOCS_X,  y + 2), _fmt_docs(docs),  font=f_val,  fill=COLOR_FG)
                draw.text((cx + STORE_X, y + 2), _fmt_bytes(store), font=f_val,  fill=COLOR_FG)
                delta_str, delta_color = _fmt_delta(delta)
                draw.text((cx + DELTA_X, y + 2), delta_str,        font=f_body, fill=delta_color)
                draw.line([(cx, y + ROW_H - 1), (cx + COL_W - 1, y + ROW_H - 1)],
                          fill=(230, 230, 230), width=1)

        self._stamp(canvas, f"ES Indices {page}")
        return canvas

    # ── エントリポイント ───────────────────────────────────────────────────────

    def update(self):
        print("[ElasticSearchUpdater] メトリクス取得中...")
        m = self._collect_es_metrics()

        # 内部インデックス (.*) を除外し、名前昇順でソート
        rows: list[tuple[str, tuple, float, float, float | None]] = []
        for idx in sorted(k for k in m["idx_docs"] if not k.startswith(".")):
            docs  = max(m["idx_docs"].get(idx, 0), 0)
            store = m["idx_store"].get(idx, 0)
            delta = m["idx_delta"].get(idx)
            hcolor = _idx_dot_color(m["idx_health"], idx)
            rows.append((idx, hcolor, docs, store, delta))

        img1 = self._screen_cluster(m)
        img2 = self._screen_indices(rows, offset=0,            page="1/2")
        img3 = self._screen_indices(rows, offset=ROWS_PER_SCR, page="2/2")

        self.image_request([img1, img2, img3])


if __name__ == "__main__":
    updater = ElasticSearchUpdater()
    updater.update()
