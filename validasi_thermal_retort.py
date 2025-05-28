import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import datetime
import os

# PDF class
class PDF(FPDF):
    def header(self):
        self.set_font('DejaVu', '', 12)
        self.cell(0, 10, 'Laporan Validasi Thermal Proses Retort', ln=True, align='C')

    def chapter_body(self, text):
        self.multi_cell(0, 10, text)

    def add_metadata(self, nama_produk, tanggal_proses, nama_operator, nama_alat, f0_total, passed):
        self.set_font('DejaVu', '', 12)
        self.ln(10)
        self.chapter_body(f"Nama Produk: {nama_produk}")
        self.chapter_body(f"Tanggal Proses: {tanggal_proses}")
        self.chapter_body(f"Operator: {nama_operator}")
        self.chapter_body(f"Alat Retort: {nama_alat}")
        self.chapter_body(f"Nilai F₀ Total: {f0_total:.2f}")
        status = "✅ Lolos" if passed else "❌ Tidak Lolos"
        self.chapter_body(f"Validasi Suhu ≥121.1°C selama 3 menit: {status}")

# Streamlit app
st.set_page_config(page_title="Tools mengetahui F0")

st.title("Aplikasi Validasi Thermal Retort")

nama_produk = st.text_input("Nama Produk")
tanggal_proses = st.date_input("Tanggal Proses", value=datetime.date.today())
nama_operator = st.text_input("Nama Operator")
nama_alat = st.text_input("Nama Alat Retort")

uploaded_file = st.file_uploader("Upload Data Suhu (CSV dengan kolom waktu & suhu)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("Data Awal:", df.head())

    suhu = df['suhu'].to_numpy()
    waktu = np.arange(len(suhu)) * 60  # dalam detik
    f0 = np.sum(10 ** ((suhu - 121.1) / 10)) * 1 / 60  # F0 total

    st.metric("Nilai F₀", f"{f0:.2f}")
    
    suhu_valid = np.all(suhu >= 121.1)
    durasi_valid = np.sum(suhu >= 121.1)
    passed = durasi_valid >= 3

    st.success("✅ Validasi Suhu Berhasil") if passed else st.error("❌ Validasi Gagal")

    if st.button("Download Laporan PDF"):
        pdf = PDF()
        pdf.add_page()
        pdf.add_font('DejaVu', '', 'fonts/DejaVuSans.ttf', uni=True)
        pdf.set_font('DejaVu', '', 12)
        pdf.add_metadata(nama_produk, tanggal_proses.strftime("%Y-%m-%d"), nama_operator, nama_alat, f0, passed)
        
        filename = f"laporan_validasi_{nama_produk.replace(' ', '_')}.pdf"
        pdf.output(filename)

        with open(filename, "rb") as f:
            st.download_button("⬇️ Unduh Laporan PDF", f, file_name=filename, mime="application/pdf")
