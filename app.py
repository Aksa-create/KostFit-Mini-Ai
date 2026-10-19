import os, json
import psycopg
from psycopg.rows import dict_row
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "local-only-change-this-secret-key"
class DatabaseConnection:
    """Small compatibility layer for the existing SQLite-style query calls."""
    def __init__(self):
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL belum diatur. Tambahkan connection string Neon di environment.")
        # Neon pooled URLs may use sslmode=require; ensure TLS for hosted PostgreSQL.
        if "sslmode=" not in database_url:
            separator = "&" if "?" in database_url else "?"
            database_url += separator + "sslmode=require"
        self.conn = psycopg.connect(database_url, row_factory=dict_row)

    @staticmethod
    def _sql(sql):
        sql = sql.replace("?", "%s")
        sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        if "INSERT INTO favorites" in sql and "ON CONFLICT" not in sql:
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT (user_id, meal_id) DO NOTHING"
        return sql

    def execute(self, sql, params=()):
        return self.conn.execute(self._sql(sql), params)

    def executemany(self, sql, params):
        return self.conn.cursor().executemany(self._sql(sql), params)

    def executescript(self, script):
        # Schema statements in this project contain no embedded semicolons.
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
        return False

def db_conn():
    return DatabaseConnection()

MEAL_SEED = [
    ("Nasi, telur dadar, dan buncis", "Sarapan", 8500, "nasi telur buncis", "Telur", 420, 16, 62, 12, 1, 0, 1,
     "Nasi, telur, buncis, bawang, sedikit minyak", "Karbohidrat, protein, dan sayuran dalam satu menu.",
     "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=85"),
    ("Nasi, tempe, dan sayur bening", "Makan siang", 9000, "nasi tempe sayur", "Tempe", 460, 18, 68, 13, 1, 0, 1,
     "Nasi, tempe, bayam, jagung, bawang", "Protein nabati dengan sayuran dan sumber karbohidrat.",
     "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=85"),
    ("Nasi ayam panggang dan capcay", "Makan siang", 12000, "nasi ayam sayur", "Ayam", 520, 30, 65, 14, 1, 0, 0,
     "Nasi, ayam, wortel, kol, sawi", "Protein hewani dan variasi sayuran.",
     "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=85"),
    ("Nasi ikan kembung dan sayur", "Makan siang", 11000, "nasi ikan sayur", "Ikan", 500, 27, 64, 13, 1, 1, 0,
     "Nasi, ikan kembung, sayuran, bumbu", "Ikan menjadi salah satu pilihan sumber protein.",
     "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=85"),
    ("Oat pisang dan susu", "Sarapan", 7500, "oat pisang susu", "Susu", 350, 12, 55, 9, 1, 0, 0,
     "Oat, pisang, susu", "Alternatif sarapan praktis; perhatikan alergi atau intoleransi susu.",
     "https://images.unsplash.com/photo-1517673132405-a56a62b18caf?auto=format&fit=crop&w=900&q=85"),
    ("Tahu, tempe, nasi, dan tumis sayur", "Makan malam", 10000, "tahu tempe nasi sayur", "Tahu dan tempe", 490, 22, 66, 14, 1, 0, 0,
     "Tahu, tempe, nasi, sawi, wortel", "Pilihan protein nabati dan sayuran.",
     "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=85"),
    ("Sup ayam, kentang, dan wortel", "Makan malam", 12000, "sup ayam", "Ayam", 390, 26, 42, 10, 1, 0, 0,
     "Ayam, kentang, wortel, seledri", "Menu berkuah dengan protein dan sayuran.",
     "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=85"),
    ("Pisang dan kacang panggang", "Camilan", 5000, "pisang kacang", "Kacang", 230, 6, 32, 10, 1, 0, 0,
     "Pisang, kacang panggang", "Camilan praktis; hindari bila alergi kacang.",
     "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?auto=format&fit=crop&w=900&q=85"),
    ("Yogurt plain dan buah", "Camilan", 6500, "yogurt buah", "Susu", 190, 8, 28, 5, 1, 0, 0,
     "Yogurt plain, buah potong", "Camilan dengan buah; perhatikan toleransi produk susu.",
     "https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=900&q=85"),
    ("Roti gandum isi ayam", "Sarapan", 9000, "roti ayam", "Ayam", 380, 23, 44, 10, 1, 0, 0,
     "Roti gandum, ayam suwir, selada, tomat", "Pilihan sarapan praktis dengan protein.",
     "https://images.unsplash.com/photo-1525351484163-7529414344d8?auto=format&fit=crop&w=900&q=85"),
    ("Gado-gado sederhana", "Makan siang", 10000, "gado gado sayuran", "Kacang", 430, 15, 48, 19, 1, 0, 0,
     "Sayuran rebus, tahu, kentang, saus kacang", "Sayuran dan protein nabati; saus kacang mengandung alergen kacang.",
     "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=85"),
    ("Nasi telur dan tumis sawi", "Makan malam", 8000, "nasi telur sawi", "Telur", 410, 15, 61, 11, 1, 0, 1,
     "Nasi, telur, sawi, bawang", "Pilihan sederhana dengan sumber protein dan sayuran.",
     "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=85"),
]

def init_db():
    with db_conn() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            age INTEGER NOT NULL DEFAULT 20, activity TEXT NOT NULL DEFAULT 'sedang',
            budget INTEGER NOT NULL DEFAULT 25000, diet TEXT NOT NULL DEFAULT 'semua',
            dislikes TEXT NOT NULL DEFAULT '', allergies TEXT NOT NULL DEFAULT '',
            cooking TEXT NOT NULL DEFAULT 'kompor', goal TEXT NOT NULL DEFAULT 'seimbang'
        );
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            cost INTEGER NOT NULL, tags TEXT NOT NULL, protein TEXT NOT NULL, calories INTEGER NOT NULL DEFAULT 0,
            protein_g INTEGER NOT NULL DEFAULT 0, carbs_g INTEGER NOT NULL DEFAULT 0, fat_g INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1, contains_fish INTEGER NOT NULL DEFAULT 0,
            contains_egg INTEGER NOT NULL DEFAULT 0, ingredients TEXT NOT NULL, reason TEXT NOT NULL, image_url TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
            PRIMARY KEY(user_id, meal_id)
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            summary TEXT NOT NULL, total_cost INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        count = db.execute("SELECT COUNT(*) AS n FROM meals").fetchone()["n"]
        if count == 0:
            db.executemany("""INSERT INTO meals(name,category,cost,tags,protein,calories,protein_g,carbs_g,fat_g,active,
                contains_fish,contains_egg,ingredients,reason,image_url) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", MEAL_SEED)
        # Create admin only when credentials are configured in environment variables.
        admin_email = os.environ.get("ADMIN_EMAIL")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if admin_email and admin_password:
            admin = db.execute(
                "SELECT id FROM users WHERE email=?",
                (admin_email,)
            ).fetchone()

            if not admin:
                cur = db.execute(
                    """INSERT INTO users(name,email,password_hash,role)
                       VALUES(?,?,?,?) RETURNING id""",
                    (
                        "KostFit Admin",
                        admin_email,
                        generate_password_hash(admin_password),
                        "admin"
                    )
                )

                db.execute(
                    "INSERT INTO profiles(user_id) VALUES(?)",
                    (cur.fetchone()["id"],)
                    )

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Silakan login terlebih dahulu.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped

def get_profile(user_id):
    with db_conn() as db:
        return db.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()

def _contains_any(text, terms):
    """Match whole words/phrases after basic normalization."""
    import re
    normalized = re.sub(r"\s+", " ", (text or "").lower().replace("-", " ").replace("_", " "))
    return any(
        re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", normalized)
        for term in terms
    )


def infer_menu(profile, meals, preferred_menu=None):
    """
    Transparent production-rule recommender.
    Hard constraints (allergens, diet, dislikes, cooking constraints) are applied first.
    A small exhaustive search then selects the best affordable set across meal categories.
    """
    candidates = [dict(m) for m in meals if int(m["active"] or 0) == 1]
    rules = []
    allergies = {x.strip().lower() for x in (profile["allergies"] or "").split(",") if x.strip()}
    dislikes = {x.strip().lower() for x in (profile["dislikes"] or "").split(",") if x.strip()}

    def searchable(meal):
        return " ".join(str(meal.get(k, "") or "") for k in
                        ("name", "ingredients", "tags", "protein")).lower()

    # Alias sets are deliberately conservative. Real allergen safety still requires complete,
    # verified ingredient data; matching text alone cannot certify that a dish is safe.
    allergen_terms = {
        "telur": ("telur", "egg", "mayones", "mayonnaise", "albumin"),
        "kacang": ("kacang", "peanut", "groundnut", "almond", "mete", "cashew",
                   "saus kacang", "selai kacang"),
        "susu": ("susu", "milk", "yogurt", "yoghurt", "keju", "cheese",
                 "mentega", "butter", "krim", "cream", "whey", "kental manis"),
    }

    for allergen in sorted(allergies):
        terms = allergen_terms.get(allergen)
        if not terms:
            continue
        before = len(candidates)
        candidates = [m for m in candidates if not _contains_any(searchable(m), terms)]
        rules.append(f"Aturan alergi {allergen}: {before - len(candidates)} menu terdeteksi terkait dan dikecualikan.")

    if "ikan" in dislikes:
        fish_terms = ("ikan", "fish", "tuna", "salmon", "sarden", "kembung", "teri", "seafood", "udang", "cumi")
        before = len(candidates)
        candidates = [m for m in candidates if not _contains_any(searchable(m), fish_terms)
                      and int(m.get("contains_fish") or 0) != 1]
        rules.append(f"Preferensi tanpa ikan/seafood: {before - len(candidates)} menu dikecualikan.")

    diet = (profile["diet"] or "semua").lower()
    meat_terms = ("ayam", "daging", "sapi", "kambing", "ikan", "fish", "seafood",
                  "udang", "cumi", "bakso", "sosis", "kaldu ayam", "kaldu sapi",
                  "terasi", "anchovy", "teri")
    animal_terms = meat_terms + ("telur", "egg", "susu", "milk", "yogurt", "yoghurt",
                                 "keju", "cheese", "mentega", "butter", "madu", "honey")
    if diet == "vegetarian":
        before = len(candidates)
        candidates = [m for m in candidates if not _contains_any(searchable(m), meat_terms)]
        rules.append(f"Aturan vegetarian: {before - len(candidates)} menu dengan indikasi daging/ikan/kaldu hewani dikecualikan.")
    elif diet == "tanpa_hewani":
        before = len(candidates)
        candidates = [m for m in candidates if not _contains_any(searchable(m), animal_terms)
                      and int(m.get("contains_egg") or 0) != 1
                      and int(m.get("contains_fish") or 0) != 1]
        rules.append(f"Aturan tanpa bahan hewani: {before - len(candidates)} menu dikecualikan.")

    cooking = (profile["cooking"] or "kompor").lower()
    # Cooking method is treated as a preference score, not an unsafe ingredient-based hard filter.
    # The schema has no verified preparation-time/equipment field, so it would be misleading
    # to reject a dish based only on its name.
    if cooking == "tanpa_masak":
        ready_terms = ("roti", "yogurt", "yoghurt", "buah potong", "pisang", "siap santap", "siap makan")
        before = len(candidates)
        ready_candidates = [m for m in candidates if _contains_any(searchable(m), ready_terms)]
        # If the database has at least some identifiable no-cook options, do not recommend
        # dishes that appear to require cooking. If none are identifiable, return no result
        # rather than silently claiming a cooked dish is suitable.
        candidates = ready_candidates
        rules.append(f"Tanpa memasak: {before - len(candidates)} menu yang tidak teridentifikasi sebagai siap santap dikecualikan.")
    elif cooking == "rice_cooker":
        rules.append("Preferensi rice cooker dipakai sebagai sinyal praktis; data menu belum memiliki kolom alat memasak terverifikasi.")

    if not candidates:
        rules.append("Tidak ada menu yang lolos aturan wajib. Periksa profil dan kelengkapan bahan menu.")
        return [], 0, rules

    slots = ["Sarapan", "Makan siang", "Makan malam", "Camilan"]
    budget = max(0, int(profile["budget"] or 0))
    goal = (profile["goal"] or "seimbang").lower()

    def menu_score(m):
        cost = max(0, int(m.get("cost") or 0))
        kcal = max(0, int(m.get("calories") or 0))
        protein = max(0, int(m.get("protein_g") or 0))
        carbs = max(0, int(m.get("carbs_g") or 0))
        fat = max(0, int(m.get("fat_g") or 0))
        text = searchable(m)
        score = 0.0

        # An explicit requested menu receives a strong ranking boost, but it never bypasses
        # allergy/diet filters or the daily budget constraint.
        if preferred_menu and str(m.get("name", "")).strip().casefold() == str(preferred_menu).strip().casefold():
            score += 1000
        # All scores are heuristic ranking signals, not clinical nutrition assessment.
        if goal == "hemat":
            score += 45 / max(cost, 1) * 100
        elif goal == "praktis":
            quick_terms = ("roti", "oat", "pisang", "yogurt", "yoghurt", "buah potong", "siap santap")
            score += 18 if _contains_any(text, quick_terms) else 0
            if cooking == "tanpa_masak":
                score += 24 if _contains_any(text, quick_terms) else -8
            elif cooking == "rice_cooker":
                rice_terms = ("nasi", "telur", "oat", "pisang", "tempe", "tahu")
                score += 14 if _contains_any(text, rice_terms) else -4
            score += min(protein, 30) * 0.3
            score -= cost / 1000
        else:
            # Balanced goal rewards a mix of protein, carbohydrate and vegetables where recorded.
            score += min(protein, 35) * 1.2
            score += 5 if carbs > 0 else 0
            score += 4 if fat > 0 else 0
            score += 6 if _contains_any(text, ("sayur", "bayam", "wortel", "sawi", "buncis", "buah")) else 0
            score += 4 if kcal > 0 else -5
            score -= cost / 2500
        if cooking == "tanpa_masak" and _contains_any(text, ("roti", "oat", "pisang", "yogurt", "yoghurt", "buah potong", "siap santap")):
            score += 10
        elif cooking == "rice_cooker" and _contains_any(text, ("nasi", "telur", "oat", "pisang", "tempe", "tahu")):
            score += 6
        return score

    by_slot = {
        slot: sorted([m for m in candidates if m["category"] == slot and int(m.get("cost") or 0) > 0],
                     key=lambda m: (-menu_score(m), int(m.get("cost") or 0), str(m.get("name") or "").lower()))
        for slot in slots
    }
    # Preserve all eligible options for display; bound only the combination search.
    all_by_slot = {slot: list(options) for slot, options in by_slot.items()}
    for slot in slots:
        by_slot[slot] = by_slot[slot][:12]

    # Enumerate at most 13^4 combinations (including an empty slot), selecting by:
    # (1) more categories filled, (2) higher relevance score, (3) lower spend.
    import itertools
    choices = [[None] + by_slot[slot] for slot in slots]
    best, best_key = [], None
    for combination in itertools.product(*choices):
        picked = [m for m in combination if m is not None]
        total = sum(int(m["cost"]) for m in picked)
        if total > budget:
            continue
        preference_selected = int(bool(preferred_menu) and any(
            str(m.get("name", "")).strip().casefold() == str(preferred_menu).strip().casefold()
            for m in picked
        ))
        key = (preference_selected, len(picked), sum(menu_score(m) for m in picked), -total,
               tuple(str(m["name"]).lower() for m in picked))
        if best_key is None or key > best_key:
            best, best_key = picked, key

    total = sum(int(m["cost"]) for m in best)
    priority_ids = {m["id"] for m in best}
    if preferred_menu:
        if any(str(m.get("name", "")).strip().casefold() == str(preferred_menu).strip().casefold() for m in best):
            rules.append(f"Preferensi menu: {preferred_menu} diprioritaskan dan berhasil masuk rekomendasi.")
        else:
            rules.append(f"Preferensi menu: {preferred_menu} tidak dimasukkan karena tidak lolos aturan wajib atau tidak muat dalam budget.")
    chosen_slots = {m["category"] for m in best}
    missing = [slot for slot in slots if slot not in chosen_slots]
    if missing:
        rules.append("Budget/ketersediaan: kategori belum terisi: " + ", ".join(missing) + ".")
    else:
        rules.append("Budget: semua kategori terisi dan total harga berada dalam batas budget.")
    rules.append({
        "hemat": "Tujuan hemat: sistem mengutamakan menu terjangkau, lalu menilai protein sebagai sinyal tambahan.",
        "praktis": "Tujuan praktis: sistem mengutamakan indikasi persiapan sederhana dan kecocokan preferensi memasak.",
        "seimbang": "Tujuan seimbang: sistem memakai protein, keberadaan karbohidrat/lemak/sayuran, dan harga sebagai sinyal heuristik."
    }.get(goal, "Tujuan seimbang: sistem memakai skor heuristik untuk mengurutkan menu."))
    rules.append("Batasan model: usia dan aktivitas belum dapat menghasilkan target kalori personal karena profil tidak menyimpan berat badan/tinggi badan; skor gizi bukan penilaian medis.")
    rules.append("Keamanan alergi bergantung pada bahan dan label yang lengkap serta akurat di database.")

    # Return every eligible menu, not only the chosen combination. The chosen combination
    # is marked as priority; other eligible candidates remain visible as alternatives.
    all_ranked = []
    for slot in slots:
        options = sorted(all_by_slot[slot], key=lambda m: (
            0 if preferred_menu and str(m.get("name", "")).strip().casefold() == str(preferred_menu).strip().casefold() else 1,
            -menu_score(m), int(m.get("cost") or 0), str(m.get("name") or "").lower()
        ))
        for meal in options:
            meal["priority"] = meal["id"] in priority_ids
            meal["priority_reason"] = (
                "Diprioritaskan dalam rencana harian karena cocok dengan aturan dan budget."
                if meal["priority"] else
                "Alternatif yang memenuhi aturan dasar, tetapi tidak masuk kombinasi prioritas berdasarkan skor/budget."
            )
            all_ranked.append(meal)
    return all_ranked, total, rules

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(name) < 2 or "@" not in email or len(password) < 8:
            flash("Periksa nama, email, dan password (minimal 8 karakter).", "danger")
            return render_template("register.html")
        try:
            with db_conn() as db:
                with db.conn.transaction():
                    cur = db.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?) RETURNING id",
                        (name, email, generate_password_hash(password)))
                    db.execute("INSERT INTO profiles(user_id) VALUES(?)", (cur.fetchone()["id"],))
            flash("Akun berhasil dibuat. Silakan login.", "success")
            return redirect(url_for("login"))
        except psycopg.IntegrityError:
            flash("Email sudah terdaftar. Silakan login atau gunakan email lain.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db_conn() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("admin" if user["role"] == "admin" else "dashboard"))
        flash("Email atau password salah.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Kamu telah logout.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if session.get("role") == "admin":
        return redirect(url_for("admin"))
    if request.method == "POST":
        try:
            age = max(16, min(100, int(request.form.get("age", 20))))
            activity = request.form.get("activity", "sedang")
            if activity not in ["rendah", "sedang", "tinggi"]: activity = "sedang"
            budget = max(5000, min(500000, int(request.form.get("budget", 25000))))
            diet = request.form.get("diet", "semua")
            if diet not in ["semua", "vegetarian", "tanpa_hewani"]: diet = "semua"
            dislikes = ",".join(request.form.getlist("dislikes"))
            allergies = ",".join(request.form.getlist("allergies"))
            cooking = request.form.get("cooking", "kompor")
            if cooking not in ["kompor", "rice_cooker", "tanpa_masak"]: cooking = "kompor"
            goal = request.form.get("goal", "seimbang")
            if goal not in ["seimbang", "hemat", "praktis"]: goal = "seimbang"
            preferred_menu = request.form.get("preferred_menu", "").strip()
            # Only accept menu names that exist and are active; no schema migration required.
            with db_conn() as db:
                valid_preference = db.execute(
                    "SELECT name FROM meals WHERE active=1 AND name=?", (preferred_menu,)
                ).fetchone() if preferred_menu else None
            if preferred_menu and not valid_preference:
                preferred_menu = ""
            session["preferred_menu"] = preferred_menu
            with db_conn() as db:
                db.execute("""UPDATE profiles SET age=?,activity=?,budget=?,diet=?,dislikes=?,allergies=?,cooking=?,goal=?
                              WHERE user_id=?""",
                    (age, activity, budget, diet, dislikes, allergies, cooking, goal, session["user_id"]))
            flash("Profil berhasil disimpan dan rekomendasi dihitung ulang.", "success")
            return redirect(url_for("dashboard"))
        except ValueError:
            flash("Usia dan budget harus berupa angka.", "danger")
    profile = get_profile(session["user_id"])
    with db_conn() as db:
        all_meals = db.execute("SELECT * FROM meals WHERE active=1").fetchall()
        fav_ids = {r["meal_id"] for r in db.execute("SELECT meal_id FROM favorites WHERE user_id=?", (session["user_id"],))}
        history = db.execute("SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT 5", (session["user_id"],)).fetchall()
    preferred_menu = session.get("preferred_menu", "")
    meals, total, rules = infer_menu(profile, all_meals, preferred_menu=preferred_menu)
    return render_template("dashboard.html", profile=profile, meals=meals, total=total, rules=rules,
        favorites=fav_ids, history=history, allergies=profile["allergies"].split(","), dislikes=profile["dislikes"].split(","),
        preferred_menu=preferred_menu, available_menu_names=sorted({m["name"] for m in all_meals}))

@app.route("/favorite/<int:meal_id>", methods=["POST"])
@login_required
def favorite(meal_id):
    with db_conn() as db:
        exists = db.execute("SELECT 1 FROM meals WHERE id=? AND active=1", (meal_id,)).fetchone()
        if not exists: abort(404)
        fav = db.execute("SELECT 1 FROM favorites WHERE user_id=? AND meal_id=?", (session["user_id"], meal_id)).fetchone()
        if fav:
            db.execute("DELETE FROM favorites WHERE user_id=? AND meal_id=?", (session["user_id"], meal_id))
            flash("Menu dihapus dari favorit.", "info")
        else:
            db.execute("INSERT OR IGNORE INTO favorites(user_id,meal_id) VALUES(?,?)", (session["user_id"], meal_id))
            flash("Menu disimpan ke favorit.", "success")
    return redirect(url_for("dashboard"))

@app.route("/save-recommendation", methods=["POST"])
@login_required
def save_recommendation():
    profile = get_profile(session["user_id"])
    with db_conn() as db:
        all_meals = db.execute("SELECT * FROM meals WHERE active=1").fetchall()
        meals, total, _ = infer_menu(profile, all_meals, preferred_menu=session.get("preferred_menu", ""))
        priority_meals = [m for m in meals if m.get("priority")]
        summary = " | ".join(m["name"] for m in priority_meals) or "Tidak ada menu prioritas yang sesuai budget/pantangan"
        db.execute("INSERT INTO history(user_id,summary,total_cost) VALUES(?,?,?)", (session["user_id"], summary, total))
    flash("Rekomendasi tersimpan di riwayat.", "success")
    return redirect(url_for("dashboard"))

@app.route("/favorites")
@login_required
def favorites():
    with db_conn() as db:
        meals = db.execute("""SELECT m.* FROM meals m JOIN favorites f ON f.meal_id=m.id
                              WHERE f.user_id=? ORDER BY m.category,m.name""", (session["user_id"],)).fetchall()
    return render_template("favorites.html", meals=meals)

@app.route("/admin")
@admin_required
def admin():
    with db_conn() as db:
        users = db.execute("SELECT id,name,email,role,created_at FROM users ORDER BY id DESC").fetchall()
        meals = db.execute("SELECT * FROM meals ORDER BY category,name").fetchall()
        history_count = db.execute("SELECT COUNT(*) AS n FROM history").fetchone()["n"]
    return render_template("admin.html", users=users, meals=meals, history_count=history_count)

@app.route("/admin/meals/new", methods=["GET", "POST"])
@app.route("/admin/meals/<int:meal_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_meal(meal_id=None):
    with db_conn() as db:
        meal = db.execute("SELECT * FROM meals WHERE id=?", (meal_id,)).fetchone() if meal_id else None
        if meal_id and not meal: abort(404)
        if request.method == "POST":
            try:
                name = request.form["name"].strip()
                category = request.form["category"]
                cost = int(request.form["cost"])
                ingredients = request.form["ingredients"].strip()
                image_url = request.form["image_url"].strip()
                if not name or cost < 0 or category not in ["Sarapan", "Makan siang", "Makan malam", "Camilan"]:
                    raise ValueError
                values = (name, category, cost, request.form.get("tags","").strip(), request.form.get("protein","").strip(),
                    int(request.form.get("calories",0)), int(request.form.get("protein_g",0)), int(request.form.get("carbs_g",0)),
                    int(request.form.get("fat_g",0)), 1 if request.form.get("active") else 0,
                    1 if request.form.get("contains_fish") else 0, 1 if request.form.get("contains_egg") else 0,
                    ingredients, request.form.get("reason","").strip(), image_url)
                if meal_id:
                    db.execute("""UPDATE meals SET name=?,category=?,cost=?,tags=?,protein=?,calories=?,protein_g=?,carbs_g=?,
                        fat_g=?,active=?,contains_fish=?,contains_egg=?,ingredients=?,reason=?,image_url=? WHERE id=?""", values+(meal_id,))
                else:
                    db.execute("""INSERT INTO meals(name,category,cost,tags,protein,calories,protein_g,carbs_g,fat_g,active,
                        contains_fish,contains_egg,ingredients,reason,image_url) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values)
                flash("Data menu berhasil disimpan.", "success")
                return redirect(url_for("admin"))
            except (ValueError, KeyError):
                flash("Periksa kembali data menu. Harga dan nilai gizi harus berupa angka.", "danger")
    return render_template("meal_form.html", meal=meal)

@app.route("/admin/meals/<int:meal_id>/delete", methods=["POST"])
@admin_required
def delete_meal(meal_id):
    with db_conn() as db:
        db.execute("DELETE FROM meals WHERE id=?", (meal_id,))
    flash("Menu berhasil dihapus.", "success")
    return redirect(url_for("admin"))

@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="Halaman ini hanya dapat diakses oleh admin."), 403

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="Halaman yang kamu cari tidak ditemukan."), 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
