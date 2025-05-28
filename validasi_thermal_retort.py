import streamlit as st
from fpdf import FPDF
from io import BytesIO
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Inisialisasi objek PDF
pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# GANTI: gunakan font standar bawaan FPDF
pdf.set_font("Arial", size=12)

# Contoh teks (bisa diganti sesuai konteks Anda)
pdf.cell(200, 10, txt="Laporan Validasi Thermal Retort", ln=True, align="C")

# Tambahkan logika dan data lainnya sesuai aplikasi Anda

# Simpan ke memori
buffer = BytesIO()
pdf.output(buffer)
buffer.seek(0)

# Tampilkan di Streamlit
st.download_button(
    label="📄 Download Laporan PDF",
    data=buffer,
    file_name="validasi_thermal_retort.pdf",
    mime="application/pdf"
)

from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Validasi Thermal Retort", layout="wide")
st.title("🔥 Validasi Thermal Proses Sterilisasi - PT Rumah Retort Bersama")

st.markdown("""
Aplikasi ini menghitung nilai **F₀ (F-nol)** dari data suhu per menit selama proses sterilisasi.
Gunakan input manual atau upload file Excel berisi suhu tiap menit.
""")

# Metadata form
st.sidebar.header("📝 Form Metadata Proses")
nama_produk = st.sidebar.text_input("Nama Produk")
tanggal_proses = st.sidebar.date_input("Tanggal Proses")
nama_operator = st.sidebar.text_input("Nama Operator")
nama_alat = st.sidebar.text_input("Nama Alat Retort")

# Fungsi hitung F₀
def calculate_f0(temps, T_ref=121.1, z=10):
    f0_values = []
    for T in temps:
        if T < 90:
            f0_values.append(0)
        else:
            f0_values.append(10 ** ((T - T_ref) / z))
    return np.cumsum(f0_values)

# Fungsi ekstraksi suhu dari file Excel UMKM
def extract_suhu_from_umkm_excel(file):
    try:
        xls = pd.ExcelFile(file, engine="openpyxl")
        df_raw = xls.parse('Sheet1', header=None)

        # Cari baris tempat data suhu dimulai
        start_row = None
        for i, row in df_raw.iterrows():
            if row.astype(str).str.contains("DATA PANTAUAN", case=False, na=False).any():
                start_row = i + 1
                break

        if start_row is None:
            raise ValueError("Baris 'DATA PANTAUAN' tidak ditemukan.")

        df_data = df_raw.iloc[start_row:].reset_index(drop=True)

        suhu_col = None
        for col in df_data.columns:
            numeric_col = pd.to_numeric(df_data[col], errors='coerce')
            if (numeric_col > 90).sum() > 2:
                suhu_col = col
                break

        if suhu_col is None:
            raise ValueError("Kolom suhu tidak ditemukan.")

        suhu = pd.to_numeric(df_data[suhu_col], errors='coerce').dropna().tolist()
        return suhu

    except Exception as e:
        st.error(f"❌ Gagal ekstrak suhu dari file: {e}")
        return []

# Fungsi cek suhu minimal 121.1°C selama ≥3 menit
def check_minimum_holding_time(temps, min_temp=121.1, min_duration=3):
    holding_minutes = 0
    for t in temps:
        if t >= min_temp:
            holding_minutes += 1
            if holding_minutes >= min_duration:
                return True
        else:
            holding_minutes = 0
    return False

# PDF Generator
class PDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Laporan Validasi Thermal', ln=True, align='C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 10, title, ln=True)

    def chapter_body(self, text):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 10, text)

    def add_metadata(self, produk, tanggal, operator, alat, f0_total, passed):
        self.add_page()
        self.chapter_title("📋 Metadata Proses")
        self.chapter_body(f"Produk        : {produk}\nTanggal       : {tanggal}\nOperator      : {operator}\nAlat Retort   : {alat}")
        self.chapter_title("✅ Hasil Validasi")
        status = '✅ Lolos' if passed else '❌ Tidak Lolos'
        self.chapter_body(f"Nilai F₀ Total: {f0_total:.2f}\nValidasi suhu ≥121.1°C selama 3 menit: {status}")
        self.chapter_title("📅 Tanggal Cetak")
        self.chapter_body(datetime.now().strftime("%d-%m-%Y %H:%M:%S"))

# Pilihan metode input
input_method = st.radio("🔘 Pilih Metode Input", ["Manual", "Upload Excel"])
temps = []

if input_method == "Manual":
    st.subheader("📋 Input Manual Suhu per Menit")
    waktu = st.number_input("Jumlah menit", min_value=1, max_value=180, value=10)
    for i in range(waktu):
        temp = st.number_input(f"Menit ke-{i+1}: Suhu (°C)", value=25.0, step=0.1, key=f"temp_{i}")
        temps.append(temp)

elif input_method == "Upload Excel":
    st.subheader("📄 Upload File Excel")
    uploaded_file = st.file_uploader("Pilih file Excel (.xlsx)", type=["xlsx"])
    if uploaded_file:
        temps = extract_suhu_from_umkm_excel(uploaded_file)

# Proses F0
if temps:
    f0 = calculate_f0(temps)
    st.info(f"📊 Data suhu valid ditemukan: {len(temps)} menit")
    st.success(f"✅ Nilai F₀ Total: {f0[-1]:.2f}")

    valid = check_minimum_holding_time(temps)
    if valid:
        st.success("✅ Suhu ≥121.1°C tercapai minimal selama 3 menit")
    else:
        st.warning("⚠️ Suhu ≥121.1°C belum tercapai selama 3 menit")

    fig, ax = plt.subplots()
    ax.plot(range(1, len(temps)+1), temps, label="Suhu (°C)", marker='o')
    ax.axhline(90, color='red', linestyle='--', label="Ambang F₀ (90°C)")
    ax.axhline(121.1, color='green', linestyle='--', label="Target BPOM (121.1°C)")
    ax.set_xlabel("Menit")
    ax.set_ylabel("Suhu (°C)")

    ax2 = ax.twinx()
    ax2.plot(range(1, len(f0)+1), f0, color='orange', label="F₀ Akumulatif", linestyle='--')
    ax2.set_ylabel("F₀")

    ax.legend(loc="upper left")
    ax2.legend(loc="upper right")
    st.pyplot(fig)

    if st.button("📄 Ekspor ke PDF"):
        pdf = PDF()
        pdf.add_metadata(nama_produk, tanggal_proses, nama_operator, nama_alat, f0[-1], valid)
        pdf_bytes = pdf.output(dest='S').encode('latin1')
        st.download_button("💾 Unduh PDF", data=pdf_bytes, file_name="laporan_validasi.pdf", mime="application/pdf")

else:
    st.warning("⚠️ Masukkan data suhu terlebih dahulu.")
