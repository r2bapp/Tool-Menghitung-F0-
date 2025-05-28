import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import os
from datetime import datetime

st.set_page_config(page_title="Tools mengetahui F0", layout="centered")

# PDF Report Class
class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_page()
        self.set_font("DejaVu", '', 14)

    def header(self):
        self.set_font("DejaVu", 'B', 16)
        self.cell(0, 10, 'Laporan Validasi Thermal Retort', ln=True, align='C')
        self.ln(10)

    def chapter_body(self, text):
        self.set_font("DejaVu", '', 12)
        self.multi_cell(0, 10, text)
        self.ln()

    def add_metadata(self, produk, tanggal, operator, alat, f0_total, passed):
        self.set_font("DejaVu", '', 12)
        self.chapter_body(f"Produk: {produk}\nTanggal: {tanggal}\nOperator: {operator}\nAlat: {alat}")
        self.chapter_body(f"Nilai F₀ Total: {f0_total:.2f}\nValidasi Suhu ≥121.1°C selama 3 menit: {'✅ Lolos' if passed else '❌ Tidak Lolos'}")

    def add_chart(self, suhu):
        plt.figure(figsize=(6, 3))
        plt.plot(suhu, label="Suhu (°C)")
        plt.axhline(y=121.1, color='r', linestyle='--', label='121.1°C')
        plt.xlabel("Menit ke-")
        plt.ylabel("Suhu (°C)")
        plt.legend()
        plt.tight_layout()
        chart_path = "chart.png"
        plt.savefig(chart_path)
        plt.close()
        self.image(chart_path, x=10, w=180)
        os.remove(chart_path)

    def save_pdf(self, filename):
        self.output(filename)

# Tambah font Unicode
pdf_font_path = "fonts/DejaVuSans.ttf"
if not os.path.exists(pdf_font_path):
    st.error("Font DejaVuSans.ttf tidak ditemukan di folder 'fonts'. Pastikan sudah mengunggahnya.")
else:
    pdf = PDF()
    pdf.add_font('DejaVu', '', pdf_font_path, uni=True)

st.title("🔥 Validasi Thermal Retort (F₀)")

# Metadata
nama_produk = st.text_input("Nama Produk")
tanggal_proses = st.date_input("Tanggal Proses", datetime.today())
nama_operator = st.text_input("Nama Operator")
nama_alat = st.text_input("Nama Alat Retort")

# Metode input suhu
input_mode = st.radio("Pilih Metode Input Suhu:", ("Manual", "Upload CSV"))

if input_mode == "Manual":
    menit = st.number_input("Jumlah Menit Proses", min_value=1, max_value=300, value=10)
    suhu_list = st.data_editor(
        pd.DataFrame({"Menit ke-": list(range(1, menit+1)), "Suhu (°C)": [121.1]*menit}),
        use_container_width=True,
        key="manual_input"
    )
    suhu = suhu_list["Suhu (°C)"].tolist()
else:
    uploaded_file = st.file_uploader("Unggah File CSV (Kolom: suhu)", type="csv")
    suhu = []
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        if "suhu" in df.columns:
            suhu = df["suhu"].tolist()
        else:
            st.error("File harus memiliki kolom bernama 'suhu'.")

# Fungsi perhitungan F0
def calculate_f0(suhu, ref_temp=121.1, z=10):
    dt = 60  # interval 1 menit = 60 detik
    f0 = [10 ** ((temp - ref_temp) / z) * dt / 60 for temp in suhu]
    return np.cumsum(f0)

# Tombol proses
if st.button("🔍 Hitung dan Validasi"):
    if not suhu:
        st.warning("Masukkan data suhu terlebih dahulu.")
    else:
        f0 = calculate_f0(suhu)
        valid = False
        durasi_valid = 0
        for temp in suhu:
            if temp >= 121.1:
                durasi_valid += 1
            else:
                durasi_valid = 0
            if durasi_valid >= 3:
                valid = True
                break

        st.success(f"Nilai F₀ Total: {f0[-1]:.2f}")
        st.info(f"✅ Validasi suhu ≥121.1°C selama 3 menit: {'LOLOS' if valid else 'TIDAK LOLOS'}")

        # Plot suhu
        fig, ax = plt.subplots()
        ax.plot(suhu, label="Suhu (°C)")
        ax.axhline(121.1, color='r', linestyle='--', label='121.1°C')
        ax.set_xlabel("Menit ke-")
        ax.set_ylabel("Suhu")
        ax.legend()
        st.pyplot(fig)

        # PDF
        report = PDF()
        report.add_font('DejaVu', '', pdf_font_path, uni=True)
        report.add_metadata(nama_produk, tanggal_proses, nama_operator, nama_alat, f0[-1], valid)
        report.add_chart(suhu)
        filename = f"Laporan_Validasi_{nama_produk.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        report.save_pdf(filename)

        with open(filename, "rb") as f:
            st.download_button("⬇️ Unduh Laporan PDF", f, file_name=filename)
        os.remove(filename)
