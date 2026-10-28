# SmartKey

Aplikasi riset berbasis Streamlit untuk menganalisis pembangkitan seed berbasis AI (GA, ANN, ACO) pada tanda tangan digital RSA, DSA, dan ElGamal.

## Alur Sistem

1. AI menghasilkan satu seed mentah per percobaan. Objek yang dioptimasi adalah seed, dengan kriteria penalti keacakan (monobit, autokorelasi, block frequency).
2. Dari satu seed mentah itu diturunkan seed terpisah untuk tiap algoritma dan ukuran kunci memakai HMAC-SHA256 dengan label domain, lalu diperluas menjadi aliran byte deterministik untuk pembangkit kunci.
3. Dokumen (PDF, DOCX, TXT, PNG, JPG) hanya dipakai sebagai bahan uji: di-hash dengan SHA-256, ditandatangani, diverifikasi, diubah, lalu diverifikasi ulang.
4. Seed dievaluasi dengan entropi Shannon, uji entropi terkalibrasi, uji entropi selisih, dan NIST (Frequency, Block Frequency, Runs).
5. Hasil disimpan ke folder `results` sebagai JSON lengkap dengan seed, parameter, kunci publik, dan waktu.

## Confusion Matrix

- Verifikasi dokumen: dokumen asli (aktual valid) dan dokumen diubah (aktual tidak valid) terhadap hasil verifikasi.
- Uji keacakan: seed `os.urandom` (aktual acak) dan seed cacat (aktual tidak acak) terhadap hasil lolos atau gagal seluruh baterai uji.

## Menjalankan

Windows (PowerShell atau CMD):

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

macOS atau Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Aplikasi terbuka di http://localhost:8501. Untuk menjalankan test: `pytest tests/ -v`.

`gmpy2` bersifat opsional dan mempercepat ElGamal sekitar 10 kali. Jika gagal terpasang, aplikasi tetap berjalan dengan perhitungan bawaan Python.

## Struktur

- `config.py`: seluruh konstanta, opsi, teks antarmuka, dan palet warna.
- `modules/ai`: GA, ANN, ACO, dan sumber entropi.
- `modules/crypto`: derivasi seed, pembangkit kunci, tanda tangan, dan verifikasi.
- `modules/evaluation`: entropi, NIST, benchmark, confusion matrix, uji dokumen, kurva konvergensi.
- `modules/experiment`: runner eksperimen multi dokumen dan penyimpanan hasil.
- `ui`: komponen Streamlit.
- `tests`: pengujian otomatis.

## Catatan

- ElGamal memakai grup safe prime standar (RFC 3526, 2048 dan 4096 bit). Seed AI menentukan private key, sedangkan p dan g tetap. Ini membuat keygen ElGamal cepat.
- Mode reproduksi memakai PRNG ber-seed dan tidak aman untuk kunci sesungguhnya.
- Folder `results` memuat seed dan kunci publik. Perlakukan sebagai data sensitif.