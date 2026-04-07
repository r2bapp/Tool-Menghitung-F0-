import io
import os
import sqlite3
import tempfile
from datetime import datetime

import matplotlib.pyplot as plt
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


def build_chart_image(df: pd.DataFrame) -> io.BytesIO:
    figure, axis = plt.subplots(figsize=(8, 4))
    axis.plot(df["Waktu"], df["Akumulasi F0"], marker="o")
    axis.set_title("Grafik Akumulasi F0")
    axis.set_xlabel("Waktu")
    axis.set_ylabel("F0")
    axis.grid(True)
    figure.autofmt_xdate()

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

    st.success(f"Total nilai F0: {tota
