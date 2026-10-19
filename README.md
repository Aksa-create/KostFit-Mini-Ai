# KostFit — Functional Prototype

Aplikasi rekomendasi menu harian anak kost dengan Production Rule-Based Knowledge Representation.

## Stack
- Python + Flask
- SQLite
- HTML, CSS, Bootstrap 5, Jinja
- Inference engine berbasis aturan IF–THEN

## Menjalankan (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```
Buka `http://127.0.0.1:5000`.

## Akun admin demo
- Email: `admin@kostfit.local`
- Password: `AdminKostFit123!`
## Akun user abi
- Email: 'abi@gmail.com'
- Password: 'Abi12345'

Akun admin dibuat otomatis pada database baru. Ganti password dan SECRET_KEY sebelum deployment. Akun demo ini hanya untuk pengembangan lokal.

## Fitur
- Register, login, logout; password hashing
- Profil: usia, aktivitas, budget, pola makan, alergi, preferensi, fasilitas memasak, tujuan
- Rekomendasi menu dengan gambar, harga estimasi, bahan, alasan, nilai gizi simulasi
- Production rules untuk menyaring telur, ikan, kacang, susu, vegetarian, dan menu tanpa bahan hewani
- Simpan menu favorit, halaman favorit, riwayat rekomendasi
- Admin terproteksi role untuk melihat akun dan CRUD knowledge base makanan
- Logo SVG, desain responsif, fallback gambar bila gambar eksternal gagal

## Catatan gambar
Gambar menu memakai URL foto eksternal Unsplash. Browser memerlukan koneksi internet untuk memuat foto. Jika gambar gagal, aplikasi menampilkan placeholder lokal. Ilustrasi hero dan logo berada di `static/images`.

## KR
- Knowledge Base: tabel `meals` beserta fakta kategori, harga, bahan, protein, alergen dan nilai gizi.
- Inference Engine: fungsi `infer_menu()` pada `app.py`.
- Production Rule-Based: filter alergi dan preferensi lebih dulu, lalu memilih menu per kategori sesuai batas budget.
- Explainability: aturan yang aktif ditampilkan di dashboard.

## Batasan
Data harga dan gizi hanya untuk simulasi akademik. Nilai gizi perlu diverifikasi. Prototype bukan pengganti ahli gizi/tenaga kesehatan. Form alergi pada versi ini menangani daftar alergen terbatas. Fasilitas memasak dan tujuan disimpan tetapi belum menjadi filter penalaran; dapat ditambahkan sebagai pengembangan berikutnya. Untuk deployment publik, tambahkan CSRF protection, rate limiting, pengaturan cookie/session yang aman, dan ubah SECRET_KEY serta kredensial demo.


## Revisi algoritma rekomendasi (Algorithm Reviewed 8.5 target)

- Hard constraints untuk alergi, pola makan, preferensi tidak menyukai ikan/seafood, dan budget diterapkan sebelum pemeringkatan.
- Pemilihan kombinasi menu lintas kategori menggunakan pencarian kombinasi terbatas, memaksimalkan kategori terisi lalu skor relevansi dan efisiensi biaya.
- Tujuan `hemat`, `praktis`, dan `seimbang` menggunakan sinyal pemeringkatan yang berbeda.
- Preferensi tanpa memasak menyaring menu ke indikasi siap santap yang dapat dikenali dari data yang tersedia.
- Hasil menjelaskan kategori yang tidak terisi dan batasan model.
- Database tidak dimigrasikan atau diubah oleh revisi ini.

Batasan: kualitas deteksi alergi dan diet bergantung pada kelengkapan data bahan. Skor gizi adalah heuristik, bukan rekomendasi medis; profil saat ini tidak memiliki tinggi/berat badan sehingga target kalori personal belum dihitung. Jalankan pengujian browser/integrasi sebelum deployment.


## Output jadwal makan harian

Dashboard kini menampilkan semua menu aktif yang lolos aturan alergi/pola makan dan preferensi yang menjadi hard constraint, dikelompokkan ke Sarapan, Makan siang, Makan malam, dan Camilan. Menu yang dipilih dalam kombinasi harian dan sesuai budget diberi label **PRIORITAS**; opsi lain yang masih memenuhi filter diberi label **ALTERNATIF · TIDAK PRIORITAS**. Total biaya dan progress budget dihitung dari menu prioritas saja. Data database tidak diubah.
