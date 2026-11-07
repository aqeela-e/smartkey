# SmartKey

Aplikasi riset berbasis Streamlit untuk menganalisis pembangkitan seed berbasis AI (GA, ANN, ACO) pada tanda tangan digital RSA, DSA, dan ElGamal.

## Alur Sistem

1. Tab Sign: AI menghasilkan satu seed mentah, lalu seed diturunkan per algoritma dan ukuran kunci (HMAC-SHA256 dengan label domain). Satu dokumen menghasilkan satu file bertanda tangan dengan format aslinya (misalnya PNG tetap PNG), karena tanda tangan dan kunci publik disematkan di akhir file. Lebih dari satu dokumen otomatis dikemas menjadi satu ZIP yang hanya berisi file-file bertanda tangan (nama dan format asli), tanpa file tambahan. Semua hasil tersimpan di `data/packages`. Khusus PDF yang ditandatangani dengan RSA, tanda tangan memakai standar PDF (PKCS#7, sertifikat dibuat sendiri dari kunci hasil seed) sehingga terbaca di Nitro, Adobe, dan pembaca PDF lain. Sertifikatnya self-signed, jadi pembaca PDF menampilkan status penerbit belum tepercaya, tetapi perubahan sekecil apa pun pada isi PDF terdeteksi. Format lain dan algoritma DSA atau ElGamal memakai tanda tangan SmartKey yang tertanam di akhir file.
2. Tab Verifikasi: unggah file bertanda tangan atau ZIP hasil batch. Hasilnya Valid, Tidak valid (dokumen diubah, tanda tangan tidak cocok, atau paket rusak), atau Belum ditandatangani untuk berkas biasa. Kunci publik dicocokkan dengan registri kunci di database.
3. Tab Eksperimen Multi Dokumen: seed yang sama dipakai RSA, DSA, dan ElGamal per percobaan. Setiap dokumen ditandatangani, diverifikasi, diubah, lalu diverifikasi ulang. File bertanda tangan semua dokumen dapat diunduh sebagai satu ZIP.
4. Seed dievaluasi dengan entropi Shannon, uji entropi terkalibrasi, uji entropi selisih, dan NIST (Frequency, Block Frequency, Runs).
5. Semua data disimpan di database SQLite `data/smartkey.db` (kunci, batch, dokumen bertanda tangan, verifikasi, hasil eksperimen dan benchmark). Tab Riwayat memanggil kembali data dari database.

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
- `modules/signing`: paket tanda tangan, verifikasi, dan layanan sign banyak dokumen.
- `modules/db`: repository SQLite.
- `modules/experiment`: runner eksperimen multi dokumen.
- `ui`: komponen Streamlit.
- `tests`: pengujian otomatis.

## Catatan

- ElGamal memakai grup safe prime standar (RFC 3526, 2048 dan 4096 bit). Seed AI menentukan private key, sedangkan p dan g tetap. Ini membuat keygen ElGamal cepat.
- Mode reproduksi memakai PRNG ber-seed dan tidak aman untuk kunci sesungguhnya.
- Folder `data` memuat database dan paket yang berisi seed serta kunci publik. Perlakukan sebagai data sensitif.
- File DOCX bertanda tangan kemungkinan tidak terbuka di Microsoft Word karena data tanda tangan berada di akhir file. PNG, JPG, dan PDF diuji tetap terbuka.