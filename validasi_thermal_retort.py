import io
import os
import sqlite3
import tempfile
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd
import streamlit as st
from fpdf import FPDF


DB_PATH = "retort_data.db"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS hasil_retort (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pelanggan TEXT,
            nama_umkm TEXT,
            nama_produk TEXT,
            nomor_kontak TEXT,
            jumlah_awal INTEGER,
            basket1 INTEGER,
            basket2 INTEGER,
            basket3 INTEGER,
            jumlah_akhir INTEGER,
            total_f0 REAL,
            tanggal TEXT,
            data_pantauan TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def calculate_f0(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    cleaned_df = df.copy()
    cleaned_df["Suhu (C)"] = pd.to_numeric(cleaned_df["Suhu (C)"], errors="coerce")
    cleaned_df = cleaned_df.dropna(subset=["Suhu (C)"]).reset_index(drop=True)

    z = 10
    t_ref = 121.1
    f0_values = []

    for suhu in cleaned_df["Suhu (C)"]:
        if suhu > 90:
            nilai_f0 = 10 ** ((suhu - t_ref) / z)
        else:
            nilai_f0 = 0
        f0_values.append(nilai_f0)

    cleaned_df["F0 per menit"] = f0_values
    cleaned_df["Akumulasi F0"] = cleaned_df["F0 per menit"].cumsum()
    total_f0 = round(float(cleaned_df["Akumulasi F0"].iloc[-1]), 2)
    return cleaned_df, total_f0


def evaluate_f0_validation(
    df: pd.DataFrame,
    target_temp: float = 121.1,
    target_duration: int = 3,
    tolerance_min_temp: float = 120.0,
    tolerance_max_temp: float = 121.1,
    tolerance_duration: int = 10,
) -> tuple[bool, str]:
    consecutive_target = 0
    consecutive_tolerance = 0

    for suhu in df["Suhu (C)"]:
        if suhu >= target_temp:
            consecutive_target += 1
            consecutive_tolerance = 0
            if consecutive_target >= target_duration:
                return (
                    True,
                    "LOLOS. Parameter proses panas memenuhi kriteria validasi, yaitu suhu sterilisasi mencapai minimal 121.1 C secara berturut-turut selama sekurang-kurangnya 3 menit.",
                )
        else:
            consecutive_target = 0

        if tolerance_min_temp <= suhu < tolerance_max_temp:
            consecutive_tolerance += 1
            if consecutive_tolerance >= tolerance_duration:
                return (
                    True,
                    "LOLOS. Parameter proses panas dinyatakan memenuhi kriteria validasi berdasarkan toleransi operasional, yaitu suhu berada pada rentang 120.0 C sampai kurang dari 121.1 C secara berturut-turut selama sekurang-kurangnya 10 menit, sehingga hasil dinyatakan sesuai untuk validasi F0.",
                )
        else:
            consecutive_tolerance = 0

    return (
        False,
        "TIDAK LOLOS. Parameter proses panas belum memenuhi kriteria validasi, karena suhu sterilisasi tidak mencapai minimal 121.1 C selama sekurang-kurangnya 3 menit dan juga tidak memenuhi rentang toleransi 120.0 C sampai kurang dari 121.1 C selama sekurang-kurangnya 10 menit.",
    )


def classify_validation_zone(
    suhu: float,
    target_temp: float = 121.1,
    tolerance_min_temp: float = 120.0,
) -> str:
    if suhu >= target_temp:
        return "target"
    if tolerance_min_temp <= suhu < target_temp:
        return "tolerance"
    return "other"


def build_chart_image(df: pd.DataFrame) -> io.BytesIO:
    chart_df = df.copy()
    chart_df["Menit"] = range(1, len(chart_df) + 1)
    chart_df["Zona Validasi"] = chart_df["Suhu (C)"].apply(classify_validation_zone)

    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axis_temp = plt.subplots(figsize=(11, 6))
    axis_f0 = axis_temp.twinx()

    figure.patch.set_facecolor("white")
    axis_temp.set_facecolor("#f8fafc")

    axis_temp.axhspan(120.0, 121.1, facecolor="#f59e0b", alpha=0.12)
    axis_temp.axhspan(121.1, max(chart_df["Suhu (C)"].max() + 2, 123), facecolor="#10b981", alpha=0.08)

    axis_temp.plot(
        chart_df["Menit"],
        chart_df["Suhu (C)"],
        color="#0f172a",
        linewidth=2.4,
        marker="o",
        markersize=5,
        label="Suhu Proses (C)",
        zorder=3,
    )
    axis_f0.plot(
        chart_df["Menit"],
        chart_df["Akumulasi F0"],
        color="#ea580c",
        linewidth=2.8,
        marker="s",
        markersize=4,
        label="Akumulasi F0",
        zorder=4,
    )

    target_points = chart_df[chart_df["Zona Validasi"] == "target"]
    tolerance_points = chart_df[chart_df["Zona Validasi"] == "tolerance"]

    if not target_points.empty:
        axis_temp.scatter(
            target_points["Menit"],
            target_points["Suhu (C)"],
            color="#059669",
            s=45,
            zorder=5,
            label="Zona target >= 121.1 C",
        )
    if not tolerance_points.empty:
        axis_temp.scatter(
            tolerance_points["Menit"],
            tolerance_points["Suhu (C)"],
            color="#d97706",
            s=45,
            zorder=5,
            label="Zona toleransi 120.0-<121.1 C",
        )

    axis_temp.axhline(121.1, color="#059669", linestyle="--", linewidth=1.5)
    axis_temp.axhline(120.0, color="#d97706", linestyle=":", linewidth=1.5)
    axis_temp.axhline(90.0, color="#dc2626", linestyle=":", linewidth=1.2)

    axis_temp.annotate(
        "Batas target 121.1 C",
        xy=(chart_df["Menit"].iloc[-1], 121.1),
        xytext=(-110, 10),
        textcoords="offset points",
        color="#047857",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#a7f3d0"),
    )
    axis_temp.annotate(
        "Batas toleransi 120.0 C",
        xy=(chart_df["Menit"].iloc[-1], 120.0),
        xytext=(-115, -22),
        textcoords="offset points",
        color="#b45309",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#fde68a"),
    )

    max_f0 = float(chart_df["Akumulasi F0"].max())
    axis_f0.scatter(
        chart_df["Menit"].iloc[-1],
        max_f0,
        color="#c2410c",
        s=70,
        zorder=6,
    )
    axis_f0.annotate(
        f"F0 akhir: {max_f0:.2f}",
        xy=(chart_df["Menit"].iloc[-1], max_f0),
        xytext=(-80, 18),
        textcoords="offset points",
        color="#9a3412",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#fdba74"),
    )

    axis_temp.set_title("Profil Suhu Sterilisasi dan Akumulasi F0", fontsize=14, fontweight="bold", pad=14)
    axis_temp.set_xlabel("Menit ke-", fontsize=11)
    axis_temp.set_ylabel("Suhu Proses (C)", fontsize=11, color="#0f172a")
    axis_f0.set_ylabel("Akumulasi F0", fontsize=11, color="#ea580c")

    axis_temp.set_xlim(1, len(chart_df))
    axis_temp.set_ylim(min(85, chart_df["Suhu (C)"].min() - 5), max(123, chart_df["Suhu (C)"].max() + 3))
    axis_f0.set_ylim(0, max(1, max_f0 * 1.2))

    axis_temp.tick_params(axis="y", colors="#0f172a")
    axis_f0.tick_params(axis="y", colors="#ea580c")
    axis_temp.grid(True, which="major", color="#cbd5e1", alpha=0.65)
    axis_f0.grid(False)

    legend_handles = [
        Line2D([0], [0], color="#0f172a", lw=2.4, marker="o", markersize=5, label="Suhu Proses (C)"),
        Line2D([0], [0], color="#ea580c", lw=2.8, marker="s", markersize=4, label="Akumulasi F0"),
        Line2D([0], [0], color="#059669", lw=1.5, linestyle="--", label="Ambang target 121.1 C"),
        Line2D([0], [0], color="#d97706", lw=1.5, linestyle=":", label="Ambang toleransi 120.0 C"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#059669", markersize=8, label="Titik target"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#d97706", markersize=8, label="Titik toleransi"),
    ]
    axis_temp.legend(
        handles=legend_handles,
        loc="upper left",
        frameon=True,
        framealpha=0.95,
        facecolor="white",
        edgecolor="#cbd5e1",
    )

    summary_text = (
        f"Total data: {len(chart_df)} menit\n"
        f"Suhu maksimum: {chart_df['Suhu (C)'].max():.1f} C\n"
        f"F0 akhir: {max_f0:.2f}"
    )
    axis_temp.text(
        0.985,
        0.03,
        summary_text,
        transform=axis_temp.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#cbd5e1"),
    )

    figure.tight_layout()

    image_buffer = io.BytesIO()
    figure.savefig(image_buffer, format="png", bbox_inches="tight")
    image_buffer.seek(0)
    plt.close(figure)
    return image_buffer


def generate_pdf(
    data_input: dict, df: pd.DataFrame, total_f0: float, validation_message: str
) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    tanggal = data_input.get("tanggal")
    if hasattr(tanggal, "strftime"):
        tanggal_str = tanggal.strftime("%Y-%m-%d")
    else:
        tanggal_str = "-"

    pdf.cell(0, 10, txt="Laporan Hasil Retort", ln=True, align="C")
    pdf.cell(0, 10, txt="Diproses oleh Rumah Retort Bersama", ln=True, align="C")
    pdf.ln(5)

    pdf.cell(0, 10, txt=f"Tanggal Proses: {tanggal_str}", ln=True)
    pdf.cell(0, 10, txt=f"Pelanggan: {data_input.get('pelanggan', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"UMKM: {data_input.get('nama_umkm', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"Produk: {data_input.get('nama_produk', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"Nomor Kontak: {data_input.get('nomor_kontak', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"Jumlah Awal: {data_input.get('jumlah_awal', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"Basket 1: {data_input.get('basket1', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"Basket 2: {data_input.get('basket2', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"Basket 3: {data_input.get('basket3', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"Jumlah Akhir: {data_input.get('jumlah_akhir', '-')}", ln=True)
    pdf.cell(0, 10, txt=f"Total F0: {total_f0}", ln=True)
    pdf.multi_cell(0, 10, txt=f"Status Validasi F0: {validation_message}")
    pdf.ln(5)

    chart_buffer = build_chart_image(df)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_chart:
        temp_chart.write(chart_buffer.getvalue())
        temp_chart_path = temp_chart.name

    try:
        pdf.image(temp_chart_path, x=10, w=180)
    finally:
        if os.path.exists(temp_chart_path):
            os.remove(temp_chart_path)

    return pdf.output(dest="S").encode("latin-1")


def save_result(data_input: dict, total_f0: float, raw_df: pd.DataFrame) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO hasil_retort (
            pelanggan,
            nama_umkm,
            nama_produk,
            nomor_kontak,
            jumlah_awal,
            basket1,
            basket2,
            basket3,
            jumlah_akhir,
            total_f0,
            tanggal,
            data_pantauan
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data_input["pelanggan"],
            data_input["nama_umkm"],
            data_input["nama_produk"],
            data_input["nomor_kontak"],
            data_input["jumlah_awal"],
            data_input["basket1"],
            data_input["basket2"],
            data_input["basket3"],
            data_input["jumlah_akhir"],
            total_f0,
            data_input["tanggal"].strftime("%Y-%m-%d"),
            raw_df.to_json(),
        ),
    )
    conn.commit()
    conn.close()


def main() -> None:
    init_db()

    st.set_page_config(layout="wide")
    st.title("Tools Proses Retort - F0 Calculator | by Rumah Retort Bersama")

    with st.form("input_form"):
        st.subheader("Data Proses Retort")
        col1, col2 = st.columns(2)

        with col1:
            pelanggan = st.text_input("Nama Pelanggan")
            nama_umkm = st.text_input("Nama UMKM")
            nama_produk = st.text_input("Nama Produk")
            nomor_kontak = st.text_input("Nomor Kontak")
            tanggal = st.date_input("Tanggal Proses", datetime.today())

        with col2:
            jumlah_awal = st.number_input("Jumlah Awal", min_value=0, step=1)
            basket1 = st.number_input("Isi Basket 1", min_value=0, step=1)
            basket2 = st.number_input("Isi Basket 2", min_value=0, step=1)
            basket3 = st.number_input("Isi Basket 3", min_value=0, step=1)
            jumlah_akhir = st.number_input("Jumlah Akhir", min_value=0, step=1)

        st.subheader("Data Pantauan per Menit")
        df_input = st.data_editor(
            pd.DataFrame(
                {
                    "Waktu": [],
                    "Suhu (C)": [],
                    "Tekanan (Bar)": [],
                    "Keterangan": [],
                }
            ),
            num_rows="dynamic",
            use_container_width=True,
        )

        submitted = st.form_submit_button("Hitung Nilai F0")

    if not submitted:
        return

    if df_input.empty:
        st.error("Masukkan data pantauan terlebih dahulu.")
        return

    if "Suhu (C)" not in df_input.columns:
        st.error("Kolom 'Suhu (C)' wajib tersedia.")
        return

    df_result, total_f0 = calculate_f0(df_input)
    if df_result.empty:
        st.error("Data suhu belum valid. Isi kolom 'Suhu (C)' dengan angka.")
        return

    is_valid, validation_message = evaluate_f0_validation(df_result)

    data_input = {
        "tanggal": tanggal,
        "pelanggan": pelanggan,
        "nama_umkm": nama_umkm,
        "nama_produk": nama_produk,
        "nomor_kontak": nomor_kontak,
        "jumlah_awal": int(jumlah_awal),
        "basket1": int(basket1),
        "basket2": int(basket2),
        "basket3": int(basket3),
        "jumlah_akhir": int(jumlah_akhir),
    }

    save_result(data_input, total_f0, df_input)

    st.success(f"Total nilai F0: {total_f0}")
    if is_valid:
        st.success(validation_message)
    else:
        st.error(validation_message)
    st.dataframe(df_result, use_container_width=True)
    st.image(
        build_chart_image(df_result),
        caption="Grafik profil suhu sterilisasi dan akumulasi F0",
        use_container_width=True,
    )

    pdf_data = generate_pdf(data_input, df_result, total_f0, validation_message)
    st.download_button(
        "Unduh Laporan PDF",
        pdf_data,
        file_name=f"laporan_retort_{tanggal}.pdf",
        mime="application/pdf",
    )


if __name__ == "__main__":
    main()
