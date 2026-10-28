import os

from modules.crypto import DSAHandler, ElGamalHandler, RSAHandler
from modules.evaluation.document_test import DOCUMENT_FORMATS, TAMPER_MODES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")

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
    "subtitle": "Analisis pembangkitan seed berbasis AI untuk tanda tangan digital RSA, DSA, dan ElGamal.",
    "tab_sign": "Tanda Tangan",
    "tab_experiment": "Eksperimen Multi Dokumen",
    "tab_benchmark": "Benchmark AI",
    "tab_dashboard": "Dashboard",
    "tab_export": "Ekspor dan Riwayat",
    "sidebar_title": "Konfigurasi",
    "sidebar_ai": "Modul AI",
    "sidebar_ai_param": "Parameter AI",
    "sidebar_bit_length": "Panjang seed (bit)",
    "sidebar_tolerance": "Toleransi keacakan (sigma)",
    "sidebar_repro": "Mode reproduksi (PRNG ber-seed)",
    "sidebar_repro_help": "Hanya untuk riset. Seed hasil mode ini tidak aman untuk kunci sesungguhnya.",
    "sidebar_repro_seed": "Nilai seed reproduksi",
    "sidebar_crypto": "Modul Kriptografi",
    "sidebar_crypto_choice": "Algoritma untuk mode tunggal",
    "sidebar_key_sizes": "Ukuran kunci per algoritma",
    "sidebar_key_size": "Ukuran kunci %s (bit)",
    "elgamal_warning": "ElGamal memakai grup safe prime standar (RFC 3526). Seed AI menentukan private key, bukan parameter p dan g.",
    "sign_header": "Tanda Tangan dan Verifikasi",
    "sign_upload": "Unggah dokumen",
    "sign_text": "Atau tulis teks langsung",
    "sign_no_input": "Unggah dokumen atau isi teks untuk memulai.",
    "sign_hash": "SHA-256 dokumen",
    "sign_button": "Bangkitkan seed, buat kunci, dan tandatangani",
    "sign_spinner": "Membangkitkan seed dan menandatangani",
    "sign_done": "Tanda tangan dibuat dengan %s dan %s.",
    "sign_signature": "Signature (hex)",
    "verify_button": "Verifikasi dokumen saat ini",
    "verify_none": "Belum ada tanda tangan pada sesi ini.",
    "verify_ok": "Verifikasi berhasil: tanda tangan valid dan dokumen asli.",
    "verify_fail": "Verifikasi gagal: tanda tangan tidak valid atau dokumen telah diubah.",
    "tamper_button": "Uji otomatis dokumen yang diubah",
    "tamper_title": "Hasil uji dokumen diubah",
    "tamper_col_case": "Kasus",
    "tamper_col_valid": "Dinyatakan valid",
    "tamper_col_expected": "Seharusnya valid",
    "tamper_original": "dokumen asli",
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
    "experiment_saved": "Hasil disimpan di %s",
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
    "export_header": "Ekspor dan Riwayat",
    "export_none": "Belum ada data untuk diekspor.",
    "export_single": "Unduh laporan tanda tangan (JSON)",
    "export_sig": "Unduh signature (.sig)",
    "export_experiment": "Unduh laporan eksperimen (JSON)",
    "export_benchmark": "Unduh laporan benchmark (JSON)",
    "export_history": "Hasil tersimpan di folder results",
    "export_history_none": "Belum ada hasil tersimpan.",
    "export_sensitive": "Berkas hasil memuat seed dan kunci publik. Perlakukan folder results sebagai data sensitif.",
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