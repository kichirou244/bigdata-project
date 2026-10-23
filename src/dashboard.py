"""Dashboard YouTube Trending: Streamlit + DuckDB đọc Parquet phân vùng."""
from __future__ import annotations

import time
from pathlib import Path

import duckdb
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed" / "youtube_trending"

CATEGORY = {
    1: "Film & Animation", 2: "Autos & Vehicles", 10: "Music", 15: "Pets & Animals",
    17: "Sports", 19: "Travel & Events", 22: "People & Blogs", 23: "Comedy",
    24: "Entertainment", 25: "News & Politics", 26: "Howto & Style",
    27: "Education", 28: "Science & Technology", 29: "Nonprofits & Activism",
}

st.set_page_config(page_title="YouTube Trending Analytics", page_icon="📈", layout="wide")


def glob_parquet(sub: str) -> str:
    return (PROC / sub).as_posix() + "/**/*.parquet"


@st.cache_resource
def get_con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET threads TO 4")
    for sub in ("summary", "daily"):
        if (PROC / sub).exists():
            con.execute(f"SELECT COUNT(*) FROM read_parquet('{glob_parquet(sub)}')")
    return con


def run_query(con, sql: str, params=None):
    t0 = time.perf_counter()
    df = con.execute(sql, params).df()
    return df, (time.perf_counter() - t0) * 1000


def show(df, fig, ms: float) -> None:
    st.plotly_chart(fig, width="stretch")
    st.dataframe(df, width="stretch", hide_index=True)
    st.caption(f"⏱ Query {ms:.0f} ms (NFR3: <= 2000 ms)")


def main() -> None:
    st.title("📈 YouTube Trending Analytics")
    st.caption("Spark → Parquet phân vùng → DuckDB · trụ hạng · tốc độ tăng trưởng view")

    if not (PROC / "summary").exists():
        st.error("Chưa có dữ liệu processed. Chạy: `python src\\transform.py`")
        return

    con = get_con()
    regions_df, _ = run_query(
        con, f"SELECT DISTINCT region FROM read_parquet('{glob_parquet('summary')}') ORDER BY 1"
    )
    regions = regions_df["region"].tolist()

    with st.sidebar:
        st.header("Bộ lọc")
        selected = st.multiselect("Quốc gia (region)", regions, default=regions[:1])
        top_n = st.slider("Top N hiển thị", 5, 30, 10)

    if not selected:
        st.info("Chọn ít nhất một quốc gia ở thanh bên trái.")
        return

    where = f"region IN ({', '.join('?' for _ in selected)})"
    summary_glob = glob_parquet("summary")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["🏆 Số ngày trụ hạng", "🚀 Tốc độ tăng trưởng", "📺 Kênh & Danh mục", "📈 Xu hướng theo ngày"]
    )

    with tab1:
        st.subheader("Video trụ hạng lâu nhất")
        df, ms = run_query(
            con,
            f"""SELECT title, channel_title, region, retention_days,
                       snapshots AS so_snapshot, total_views, publish_hour
                FROM read_parquet('{summary_glob}')
                WHERE {where}
                ORDER BY retention_days DESC, total_views DESC
                LIMIT ?""",
            selected + [top_n],
        )
        if df.empty:
            st.warning("Không có dữ liệu.")
        else:
            fig = px.bar(
                df.sort_values("retention_days"),
                x="retention_days", y="title", color="region",
                labels={"retention_days": "Số ngày trụ hạng", "title": "Video"},
                height=420,
            )
            show(df, fig, ms)

    with tab2:
        st.subheader("Tốc độ tăng trưởng view theo giờ đăng")
        df, ms = run_query(
            con,
            f"""SELECT publish_hour, ROUND(AVG(avg_views_per_hour)) AS avg_views_per_hour,
                       ROUND(MAX(peak_views_per_hour)) AS peak_views_per_hour, COUNT(*) AS videos
                FROM read_parquet('{summary_glob}')
                WHERE {where} AND publish_hour IS NOT NULL
                GROUP BY publish_hour ORDER BY publish_hour""",
            selected,
        )
        if not df.empty:
            fig = px.line(
                df, x="publish_hour", y="avg_views_per_hour", markers=True,
                labels={"publish_hour": "Giờ đăng (UTC)", "avg_views_per_hour": "Views/giờ (TB)"},
                height=380,
            )
            show(df, fig, ms)

        st.subheader(f"Top {top_n} video bứt phá nhanh nhất (peak views/giờ)")
        df2, ms2 = run_query(
            con,
            f"""SELECT title, channel_title, region,
                       ROUND(peak_views_per_hour) AS peak_views_per_hour,
                       retention_days, total_views
                FROM read_parquet('{summary_glob}')
                WHERE {where} AND peak_views_per_hour IS NOT NULL
                ORDER BY peak_views_per_hour DESC LIMIT ?""",
            selected + [top_n],
        )
        if not df2.empty:
            fig2 = px.bar(
                df2.sort_values("peak_views_per_hour"),
                x="peak_views_per_hour", y="title", color="region",
                labels={"peak_views_per_hour": "Peak views/giờ", "title": "Video"},
                height=420,
            )
            show(df2, fig2, ms2)

    with tab3:
        st.subheader(f"Top {top_n} kênh theo tổng views")
        df, ms = run_query(
            con,
            f"""SELECT channel_title, region, SUM(total_views) AS total_views,
                       COUNT(*) AS videos, ROUND(AVG(retention_days), 1) AS avg_retention_days
                FROM read_parquet('{summary_glob}')
                WHERE {where}
                GROUP BY channel_title, region ORDER BY total_views DESC LIMIT ?""",
            selected + [top_n],
        )
        if not df.empty:
            fig = px.bar(
                df.sort_values("total_views"), x="total_views", y="channel_title",
                color="region", orientation="h",
                labels={"total_views": "Tổng views", "channel_title": "Kênh"},
                height=420,
            )
            show(df, fig, ms)

        st.subheader("Phân bố theo danh mục")
        df2, ms2 = run_query(
            con,
            f"""SELECT category_id, SUM(total_views) AS total_views, COUNT(*) AS videos
                FROM read_parquet('{summary_glob}')
                WHERE {where} GROUP BY category_id ORDER BY total_views DESC""",
            selected,
        )
        if df2.empty or df2["category_id"].isna().all():
            st.info("Nguồn không có `category_id` -> bỏ qua biểu đồ danh mục.")
        else:
            df2["category"] = df2["category_id"].map(CATEGORY).fillna(
                df2["category_id"].astype(str)
            )
            fig2 = px.pie(
                df2, names="category", values="total_views",
                labels={"category": "Danh mục", "total_views": "Tổng views"},
                height=420,
            )
            show(df2, fig2, ms2)

    with tab4:
        st.subheader("Số video lọt trending theo ngày")
        df, ms = run_query(
            con,
            f"""SELECT trending_dt, region, COUNT(*) AS videos, SUM(views) AS views_cumulative
                FROM read_parquet('{glob_parquet('daily')}')
                WHERE {where}
                GROUP BY trending_dt, region ORDER BY trending_dt""",
            selected,
        )
        if not df.empty:
            fig = px.line(
                df, x="trending_dt", y="videos", color="region",
                labels={"trending_dt": "Ngày trending", "videos": "Số video"},
                height=380,
            )
            show(df, fig, ms)


if __name__ == "__main__":
    main()
