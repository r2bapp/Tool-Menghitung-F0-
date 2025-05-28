import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import os
from datetime import datetime

# === PDF Class ===
class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
        self.add_font("DejaVu", "B", "fonts/DejaVuSans-Bold.ttf", uni=True)
        self.add_page()
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("DejaVu", 'B', 16)
        self.cell(0, 10, "Laporan Validasi Thermal Retort", ln=True, align='C')

    def chapter_title(self, title):
        self.set_font("DejaVu", 'B', 14)
        self.cell(0, 10, title, ln=True, align='L')

    def chapter_body(self, text):
        self.set_font("DejaVu", '', 12)
        self.multi_cell(0, 10, text)

    def add_metadata(self, nama_produk, tanggal_proses, operator, alat, f0_total, passed):
        self.chapter_title("Informasi Umum")
        self.chapter_body(f"Nama Produk: {nama_produk}\nTanggal Proses: {tanggal_proses}\nOperator: {operator}\nAlat Retort: {alat}")
        self.chapter_title("Hasil Validasi")
        self.chapter_body(f"Nilai F₀ Total: {f0_total:.2f}\nValidasi Suhu ≥121.1°C selama 3 menit: {'✅ Lolos' if passed else '❌ Tidak Lolos'}")

# === F0 Calculation ===
def hitung_f0(data_suhu, dt=60):
    f0 = [0]
    t_ref = 121.1
    z = 10
    counter = 0
    valid_temp = []

    for temp in data_suhu:
        if temp >= t_ref:
            counter += 1
            valid_temp.append(1)
        else:
            valid_temp.append(0)
        delta = dt * 10 ** ((temp - t_ref) / z)
        f0.append(f0[-1] + delta)
    return f0[1:], valid_temp

# === Streamlit App ===
st.set_page_config(page_title="Tools Mengetahui F₀", layout="wide")
st.title("🔧 Tools Mengetahui F₀ Validasi Thermal Retort")

with st.expander("📄 Input Metadata"):
    nama_produk = st.text_input("Nama Produk", "Rendang Retort")
    tanggal_proses = st.date_input("Tanggal Proses", datetime.now()).strftime('%d-%m-%Y')
    nama_operator = st.text_input("Nama Operator", "Budi")
    nama_alat = st.text_input("Nama Alat Retort", "Retort A")

# === Upload File atau Input Manual ===
st.markdown("## 📥 Masukkan Data Suhu (°C per menit)")

input_method = st.radio("Pilih Metode Input:", ["Upload CSV", "Input Manual"])

if input_method == "Upload CSV":
    uploaded_file = st.file_uploader("Upload file CSV berisi data suhu per menit", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        suhu = df.iloc[:, 0].tolist()
        st.line_chart(suhu)
elif input_method == "Input Manual":
    suhu_input = st.text_area("Masukkan suhu tiap menit, pisahkan dengan koma", "121.5, 121.7, 122.1, 120.8, 122.5")
    try:
        suhu = [float(s.strip()) for s in suhu_input.split(",")]
        st.line_chart(suhu)
    except:
        st.error("Format input tidak valid. Pastikan angka dipisah dengan koma.")

# === Hitung dan Tampilkan ===
if st.button("✅ Hitung Nilai F₀"):
    if len(suhu) < 1:
        st.warning("Masukkan data suhu terlebih dahulu.")
    else:
        f0_values, valid_flags = hitung_f0(suhu)
        lolos = sum(valid_flags) >= 3
        st.success(f"Nilai F₀: {f0_values[-1]:.2f}")
        st.info(f"Lolos Validasi Suhu ≥121.1°C selama 3 menit: {'✅ Ya' if lolos else '❌ Tidak'}")

        # === Buat PDF ===
        pdf = PDF()
        pdf.add_metadata(nama_produk, tanggal_proses, nama_operator, nama_alat, f0_values[-1], lolos)
        output_path = "/tmp/hasil_validasi.pdf"
        pdf.output(output_path)

        with open(output_path, "rb") as f:
            st.download_button("📥 Unduh Laporan PDF", f, file_name="hasil_validasi.pdf", mime="application/pdf")
