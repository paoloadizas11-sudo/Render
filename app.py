import os, json, uuid, secrets, shutil, subprocess, sys
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
BOTS = BASE / "bots"
USERS_FILE = DATA / "users.json"
BOTDB_FILE = DATA / "bots.json"

DATA.mkdir(exist_ok=True)
BOTS.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

def load_json(path, default):
    if not path.exists():
        path.write_text(json.dumps(default, indent=2))
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

def current_user():
    return session.get("user")

def user_bots():
    bots = load_json(BOTDB_FILE, [])
    return [b for b in bots if b["owner"] == current_user()]

def get_bot(bot_id):
    bots = load_json(BOTDB_FILE, [])
    for b in bots:
        if b["id"] == bot_id and b["owner"] == current_user():
            return b, bots
    return None, bots

def proc_path(bot_id):
    return DATA / f"{bot_id}.pid"

def log_path(bot_id):
    return DATA / f"{bot_id}.log"

def is_running(bot_id):
    p = proc_path(bot_id)
    if not p.exists():
        return False
    try:
        pid = int(p.read_text())
        os.kill(pid, 0)
        return True
    except Exception:
        try: p.unlink()
        except Exception: pass
        return False

def start_bot(bot):
    if is_running(bot["id"]):
        return False, "Bot is already running."
    bot_dir = BOTS / bot["id"]
    script = bot_dir / bot["filename"]
    log = log_path(bot["id"])
    with open(log, "a", buffering=1) as out:
        out.write("\n--- STARTING BOT ---\n")
        # Bot token is supplied as an environment variable, not a command-line argument.
        env = os.environ.copy()
        env["TELEGRAM_BOT_TOKEN"] = bot.get("token", "")
        p = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(bot_dir),
            stdout=out,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True
        )
    proc_path(bot["id"]).write_text(str(p.pid))
    return True, "Bot started."

def stop_bot(bot):
    pth = proc_path(bot["id"])
    if not pth.exists():
        return False, "Bot is not running."
    try:
        pid = int(pth.read_text())
        os.kill(pid, 15)
    except Exception:
        pass
    try: pth.unlink()
    except Exception: pass
    return True, "Bot stopped."

@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        if len(username) < 3 or len(password) < 6:
            flash("Username must be 3+ characters and password 6+ characters.", "error")
        else:
            users = load_json(USERS_FILE, [])
            if any(u["username"] == username for u in users):
                flash("Username already exists.", "error")
            else:
                import hashlib
                users.append({"username": username, "password": hashlib.sha256(password.encode()).hexdigest()})
                save_json(USERS_FILE, users)
                session["user"] = username
                return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        import hashlib
        username = request.form.get("username","").strip().lower()
        password = hashlib.sha256(request.form.get("password","").encode()).hexdigest()
        users = load_json(USERS_FILE, [])
        if any(u["username"] == username and u["password"] == password for u in users):
            session["user"] = username
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if not current_user(): return redirect(url_for("login"))
    bots = user_bots()
    for b in bots: b["running"] = is_running(b["id"])
    return render_template("dashboard.html", bots=bots)

@app.route("/bot/create", methods=["GET","POST"])
def create_bot():
    if not current_user(): return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form.get("name","").strip()
        token = request.form.get("token","").strip()
        upload = request.files.get("file")
        if not name or not token or not upload or not upload.filename.endswith(".py"):
            flash("Enter a name, Telegram token, and upload a .py file.", "error")
            return render_template("create_bot.html")
        bot_id = uuid.uuid4().hex[:12]
        bot_dir = BOTS / bot_id
        bot_dir.mkdir()
        filename = Path(upload.filename).name
        upload.save(bot_dir / filename)
        bots = load_json(BOTDB_FILE, [])
        bots.append({
            "id": bot_id, "owner": current_user(), "name": name,
            "filename": filename, "token": token
        })
        save_json(BOTDB_FILE, bots)
        flash("Bot created. Review the code before starting it.", "success")
        return redirect(url_for("bot_page", bot_id=bot_id))
    return render_template("create_bot.html")

@app.route("/bot/<bot_id>")
def bot_page(bot_id):
    if not current_user(): return redirect(url_for("login"))
    bot, _ = get_bot(bot_id)
    if not bot: return "Not found", 404
    bot["running"] = is_running(bot_id)
    log = log_path(bot_id)
    text = log.read_text(errors="replace")[-12000:] if log.exists() else "No logs yet."
    return render_template("bot.html", bot=bot, logs=text)

@app.post("/bot/<bot_id>/start")
def bot_start(bot_id):
    bot, _ = get_bot(bot_id)
    if not bot: return jsonify(error="Not found"), 404
    ok, msg = start_bot(bot)
    return jsonify(ok=ok, message=msg)

@app.post("/bot/<bot_id>/stop")
def bot_stop(bot_id):
    bot, _ = get_bot(bot_id)
    if not bot: return jsonify(error="Not found"), 404
    ok, msg = stop_bot(bot)
    return jsonify(ok=ok, message=msg)

@app.post("/bot/<bot_id>/restart")
def bot_restart(bot_id):
    bot, _ = get_bot(bot_id)
    if not bot: return jsonify(error="Not found"), 404
    stop_bot(bot)
    ok, msg = start_bot(bot)
    return jsonify(ok=ok, message=msg)

@app.post("/bot/<bot_id>/delete")
def bot_delete(bot_id):
    bot, bots = get_bot(bot_id)
    if not bot: return jsonify(error="Not found"), 404
    stop_bot(bot)
    bots = [b for b in bots if b["id"] != bot_id]
    save_json(BOTDB_FILE, bots)
    shutil.rmtree(BOTS / bot_id, ignore_errors=True)
    try: log_path(bot_id).unlink()
    except Exception: pass
    return jsonify(ok=True)

@app.get("/bot/<bot_id>/status")
def bot_status(bot_id):
    bot, _ = get_bot(bot_id)
    if not bot: return jsonify(error="Not found"), 404
    return jsonify(running=is_running(bot_id))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
