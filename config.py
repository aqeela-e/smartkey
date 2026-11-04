import os

from modules.crypto import DSAHandler, ElGamalHandler, RSAHandler
from modules.evaluation.document_test import DOCUMENT_FORMATS, TAMPER_MODES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATABASE_PATH = os.path.join(DATA_DIR, "smartkey.db")
PACKAGES_DIR = os.path.join(DATA_DIR, "packages")

APP_TITLE = "SmartKey"
PAGE_LAYOUT = "wide"

AI_LABELS = {
    "GA": "Genetic Algorithm (GA)",
    "ANN": "Artificial Neural Network (ANN)",
    "ACO": "Ant Colony Optimization (ACO)",
}

AI_PARAM_SPECS = {
    "GA": [
        ("population_size", "Population Size", 10, 200, 50, 1),
        ("generations", "Generations", 10, 500, 100, 1),
        ("mutation_rate", "Mutation Rate", 0.0, 1.0, 0.2, 0.05),
        ("crossover_rate", "Crossover Rate", 0.0, 1.0, 0.7, 0.05),
    ],
    "ANN": [
        ("hidden_1", "Hidden Layer 1 Nodes", 10, 500, 10, 1),
        ("hidden_2", "Hidden Layer 2 Nodes (0 = tidak dipakai)", 0, 200, 0, 1),
        ("noise_std_dev", "Noise Standard Deviation", 0.1, 5.0, 1.0, 0.1),
    ],
    "ACO": [
        ("num_ants", "Number of Ants", 5, 100, 10, 1),
        ("iterations", "Iterations", 10, 200, 20, 1),
        ("evaporation_rate", "Evaporation Rate", 0.01, 1.0, 0.1, 0.01),
    ],
}

BIT_LENGTH_OPTIONS = (128, 256, 384, 512)
DEFAULT_BIT_LENGTH = 256
TOLERANCE_SPEC = (1.0, 4.0, 2.0, 0.1)
REPRODUCTION_SEED_DEFAULT = 2026

CRYPTO_ALGORITHMS = ("RSA", "DSA", "ElGamal")
CRYPTO_KEY_SIZES = {
    "RSA": RSAHandler.SUPPORTED_KEY_SIZES,
    "DSA": DSAHandler.SUPPORTED_KEY_SIZES,
    "ElGamal": ElGamalHandler.SUPPORTED_KEY_SIZES,
}
CRYPTO_DEFAULT_KEY_SIZE = {"RSA": 2048, "DSA": 2048, "ElGamal": 2048}

UPLOAD_TYPES = sorted({ext for exts in DOCUMENT_FORMATS.values() for ext in exts})
MAX_FILES_PER_FORMAT = 1500
EXPERIMENT_TRIALS_SPEC = (1, 30, 3, 1)
SYNTHETIC_PER_FORMAT_SPEC = (5, 1500, 50, 5)
DETECTOR_SAMPLES_SPEC = (50, 2000, 300, 50)
EXPERIMENT_SOURCES = ("Unggah berkas", "Folder lokal", "Dataset sintetis")
SIGN_SOURCES = ("Unggah berkas", "Teks langsung", "Folder lokal")
HISTORY_SECTIONS = ("Hasil", "Paket", "Verifikasi", "Kunci")
RESULT_KINDS = ("experiment", "benchmark", "detector")

BENCHMARK_BIT_LENGTH = 256
BENCHMARK_BUDGET = 200
BENCHMARK_TOLERANCE = 2.0
BENCHMARK_ANN_HIDDEN = (10,)
BENCHMARK_TRIALS_SPEC = (30, 1000, 100, 10)

PALETTE = {
    "primary": "#3d5a73",
    "accent": "#6f8fa8",
    "pass": "#4f8a6e",
    "fail": "#b5605a",
    "neutral": "#8c97a1",
    "surface": "#f5f6f8",
    "border": "#d5d9de",
    "text": "#2b3640",
    "series": ["#3d5a73", "#6f8fa8", "#9bb3c4", "#4f8a6e", "#b5605a"],
}

STYLE = {
    "font_weight": 300,
    "heading_weight": 400,
    "card_radius": "4px",
    "tab_radius": "4px",
    "border": "rgba(128, 128, 128, 0.30)",
    "tab_surface": "rgba(128, 128, 128, 0.10)",
    "tab_active": "rgba(128, 128, 128, 0.22)",
}

TEXTS = {
    "title": "SmartKey",
    "tab_sign": "Sign",
    "tab_verify": "Verifikasi",
    "tab_history": "Riwayat",
    "sidebar_crypto_choice": "Algoritma untuk Sign",
    "sign_header": "Sign Dokumen",
    "sign_intro": "Satu seed AI dipakai untuk membuat kunci, lalu setiap dokumen ditandatangani dan dikemas menjadi file bertanda tangan. Banyak dokumen langsung diunduh sebagai satu ZIP.",
    "sign_source": "Sumber dokumen",
    "sign_upload": "Unggah satu atau banyak dokumen",
    "sign_text": "Tulis teks yang akan ditandatangani",
    "sign_folder": "Path folder dokumen",
    "sign_limit": "Maksimum dokumen per format",
    "sign_no_input": "Belum ada dokumen. Unggah berkas, tulis teks, atau isi path folder.",
    "sign_button": "Sign dokumen",
    "sign_running": "Membangkitkan seed dan menandatangani",
    "sign_done": "%d dokumen ditandatangani dengan %s %d bit.",
    "sign_download_single": "Unduh dokumen bertanda tangan",
    "sign_download_batch": "Unduh semua dokumen bertanda tangan (satu ZIP)",
    "sign_saved": "Tersimpan otomatis di %s",
    "sign_key_info": "Kunci publik terdaftar di database dengan ID %d. Batch ID %d.",
    "sign_records": "Dokumen yang ditandatangani",
    "sign_next": "Untuk memeriksa keaslian, unggah berkas ini di tab Verifikasi.",
    "sign_col_name": "Berkas",
    "sign_col_format": "Format",
    "sign_col_size": "Ukuran (byte)",
    "sign_col_sha": "SHA-256",
    "sign_col_signature": "Signature (awal)",
    "verify_header": "Verifikasi Dokumen",
    "verify_intro": "Unggah dokumen bertanda tangan (.signed.zip) atau ZIP hasil batch. Berkas biasa yang belum ditandatangani akan dinyatakan belum bertanda tangan.",
    "verify_upload": "Unggah berkas untuk diverifikasi",
    "verify_button": "Verifikasi",
    "verify_none": "Belum ada berkas yang diunggah.",
    "verify_valid": "Valid",
    "verify_invalid": "Tidak valid",
    "verify_unsigned": "Belum ditandatangani",
    "verify_col_name": "Berkas",
    "verify_col_status": "Status",
    "verify_col_reason": "Alasan",
    "verify_col_algo": "Algoritma",
    "verify_col_key": "Kunci terdaftar",
    "verify_yes": "Ya",
    "verify_no": "Tidak",
    "verify_warn_unregistered": "Sebagian kunci publik tidak terdaftar di database ini. Keaslian pembuat kunci belum terjamin.",
    "verify_tamper_button": "Uji otomatis dokumen diubah",
    "verify_tamper_title": "Confusion Matrix Verifikasi Paket",
    "verify_tamper_note": "Dokumen asli dari paket yang valid diharapkan valid, lalu diubah (balik bit, tambah byte, potong byte) dan diharapkan tidak valid.",
    "history_section": "Bagian riwayat",
    "history_header": "Riwayat dari Database",
    "history_counts": "Isi database",
    "history_pick": "Pilih hasil tersimpan",
    "history_show": "Tampilkan",
    "history_json": "Unduh JSON",
    "history_none": "Belum ada data tersimpan.",
    "history_pick_batch": "Pilih batch tanda tangan",
    "history_download_pkg": "Unduh paket batch",
    "history_missing": "Berkas paket tidak ditemukan di disk.",
    "history_docs": "Dokumen dalam batch",
    "history_sensitive": "Database memuat seed dan kunci publik. Perlakukan folder data sebagai data sensitif.",
    "experiment_saved": "Hasil tersimpan di database dengan ID %d",
    "experiment_loaded_db": "Menampilkan hasil terakhir dari database",
    "experiment_make_packages": "Buat paket tanda tangan untuk semua dokumen (percobaan pertama)",
    "experiment_packages_ready": "%d paket tanda tangan siap diunduh dalam satu ZIP",
    "experiment_download_packages": "Unduh semua paket tanda tangan (ZIP)",
    "subtitle": "Analisis pembangkitan seed berbasis AI untuk tanda tangan digital RSA, DSA, dan ElGamal.",
    "tab_experiment": "Eksperimen Multi Dokumen",
    "tab_benchmark": "Benchmark AI",
    "tab_dashboard": "Dashboard",
    "sidebar_title": "Konfigurasi",
    "sidebar_ai": "Modul AI",
    "sidebar_ai_param": "Parameter AI",
    "sidebar_bit_length": "Panjang seed (bit)",
    "sidebar_tolerance": "Toleransi keacakan (sigma)",
    "sidebar_repro": "Mode reproduksi (PRNG ber-seed)",
    "sidebar_repro_help": "Hanya untuk riset. Seed hasil mode ini tidak aman untuk kunci sesungguhnya.",
    "sidebar_repro_seed": "Nilai seed reproduksi",
    "sidebar_crypto": "Modul Kriptografi",
    "sidebar_key_sizes": "Ukuran kunci per algoritma",
    "sidebar_key_size": "Ukuran kunci %s (bit)",
    "elgamal_warning": "ElGamal memakai grup safe prime standar (RFC 3526). Seed AI menentukan private key, bukan parameter p dan g.",
    "experiment_header": "Eksperimen Multi Dokumen",
    "experiment_intro": "Satu seed AI per percobaan dipakai bersama oleh RSA, DSA, dan ElGamal melalui turunan seed per algoritma. Setiap dokumen ditandatangani, diverifikasi, lalu diubah dan diverifikasi ulang.",
    "experiment_source": "Sumber dokumen",
    "experiment_upload": "Unggah banyak dokumen",
    "experiment_folder": "Path folder dokumen",
    "experiment_limit": "Maksimum dokumen per format",
    "experiment_synthetic": "Dokumen sintetis per format",
    "experiment_trials": "Jumlah percobaan (seed)",
    "experiment_modes": "Jenis perubahan dokumen",
    "experiment_run": "Jalankan eksperimen",
    "experiment_none": "Belum ada dokumen yang dimuat.",
    "experiment_running": "Menjalankan eksperimen",
    "experiment_docs": "Dokumen diuji",
    "experiment_confusion": "Confusion Matrix Verifikasi Dokumen",
    "experiment_timing": "Waktu per Algoritma",
    "experiment_format": "Ringkasan per Format",
    "experiment_seed": "Kualitas Seed pada Percobaan",
    "experiment_curve": "Konvergensi Penalti Percobaan Pertama",
    "detector_header": "Confusion Matrix Uji Keacakan",
    "detector_intro": "Seed acak sejati (os.urandom) sebagai kelas positif dan seed cacat (counter, bias, periodik, simbol terbatas) sebagai kelas negatif. Prediksi adalah lolos atau gagal seluruh baterai uji.",
    "detector_samples": "Jumlah seed per kelas",
    "detector_run": "Hitung confusion matrix uji keacakan",
    "detector_defect": "Deteksi per jenis cacat",
    "benchmark_header": "Benchmark Algoritma AI",
    "benchmark_intro": "GA, ANN, dan ACO dibandingkan dengan dua baseline tanpa AI pada budget evaluasi yang sama.",
    "benchmark_trials": "Jumlah percobaan per algoritma (N)",
    "benchmark_run": "Jalankan benchmark",
    "benchmark_progress": "Menjalankan benchmark",
    "benchmark_none": "Belum ada hasil benchmark.",
    "benchmark_rates": "Tingkat Lolos dengan Interval Kepercayaan 95%",
    "benchmark_summary": "Ringkasan per algoritma",
    "benchmark_indep": "Perbandingan pasangan pada uji independen",
    "benchmark_all": "Perbandingan pada semua tes (syarat gugur, bukan bukti keunggulan)",
    "dashboard_header": "Dashboard Analisis Seed",
    "dashboard_none": "Belum ada seed yang dibangkitkan. Gunakan tab Tanda Tangan.",
    "metric_time": "Waktu generate AI",
    "metric_entropy": "Entropi Shannon",
    "metric_entropy_help": "Entropi frekuensi byte. Batas teoritis untuk n byte adalah log2(min(256, n)).",
    "metric_normalized": "Entropi ternormalisasi",
    "metric_nist": "NIST pass rate",
    "metric_keygen": "Waktu keygen",
    "metric_sign": "Waktu sign",
    "metric_verify": "Waktu verify",
    "dashboard_nist": "Detail Uji Statistik",
    "dashboard_ring": "Tes Lulus",
    "dashboard_radar": "p-value per Uji",
    "dashboard_curve": "Konvergensi Penalti",
    "dashboard_note": "Ini uji lulus atau gagal, bukan peringkat kualitas. Seed acak sejati lolos semua tes sekitar 95% dari waktu.",
    "dashboard_insecure": "Sumber acak: %s. Seed ini tidak aman untuk kunci sesungguhnya.",
    "dashboard_source": "Sumber acak seed: %s",
    "test_pass": "Lulus",
    "test_fail": "Gagal",
    "label_valid": "Valid",
    "label_invalid": "Tidak valid",
    "label_actual": "Aktual",
    "label_predicted": "Prediksi",
    "label_random": "Acak",
    "label_defective": "Cacat",
    "label_passed": "Lolos",
    "label_failed": "Gagal",
    "axis_penalty": "Penalti",
    "axis_step": "Langkah",
    "axis_ms": "Milidetik",
    "axis_rate": "Tingkat lolos",
}

NIST_COLUMNS = ("Uji", "p-value", "Status")

STATUS_LABELS = {
    "valid": TEXTS["verify_valid"],
    "invalid": TEXTS["verify_invalid"],
    "unsigned": TEXTS["verify_unsigned"],
}

REASON_LABELS = {
    "ok": "Tanda tangan sesuai dan dokumen asli",
    "unsigned": "Berkas tidak berisi tanda tangan SmartKey",
    "bad_package": "Paket rusak atau tidak lengkap",
    "document_modified": "Dokumen telah diubah setelah ditandatangani",
    "signature_invalid": "Tanda tangan tidak cocok dengan dokumen",
    "manifest_mismatch": "Data manifest tidak cocok dengan dokumen",
}