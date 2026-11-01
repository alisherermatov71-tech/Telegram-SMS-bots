# -*- coding: utf-8 -*-
# Telegram SMM бот. Бір файл, тек стандартты кітапхана (Pydroid 3 / Python 3.8+)
import json, os, time, threading, traceback, html
import urllib.request, urllib.parse, urllib.error

# ===================== БАПТАУЛАР: тек осы жерді толтырыңыз =====================
TOKEN = "8925834126:AAH8F1eQ50IU4hw-idMI7-aXd3pLkDAt3Bs"   # @BotFather-ден алған токен
API_URL = "https://kzsmm.kz/api/v2"
API_KEY = "v9DIPjDQFYPCazZVNTwDtJPgmNHdwt4cn8yMtCKdzykywfWrXjaPyHVqfg3m"
ADMIN_ID = 6345089095                   # сіздің Telegram ID. Ботқа /id деп жазсаңыз көрсетеді
# ==============================================================================
# Үстеме, курс, Kaspi, қолдау сияқты қалғанының бәрін ботта ⚙️ Админ панельден өзгертесіз.

try:
    BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE = os.getcwd()
DB_FILE = os.path.join(BASE, "smm_data.json")

DEFAULTS = {"markup": 30.0, "markups": {}, "rate": 1.0, "kaspi": "", "support": "",
            "maintenance": False, "ref_percent": 5.0, "min_topup": 200, "top": 8, "welcome": ""}
db = {"users": {}, "settings": dict(DEFAULTS), "topups": {}, "banned": []}
lock = threading.RLock()
try:
    with open(DB_FILE, encoding="utf-8") as f:
        loaded = json.load(f)
    db.update(loaded)
    for k, v in DEFAULTS.items():
        db["settings"].setdefault(k, v)
except Exception:
    pass
S = db["settings"]
BOT = {"username": ""}
st = {}  # әр чаттың күйі


def save():
    with lock:
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False)
        except Exception:
            traceback.print_exc()


# ---------------- HTTP ----------------
def http(url, data=None, timeout=30):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def provider(**p):
    p["key"] = API_KEY
    return http(API_URL, p, 30)


def tg(method, **p):
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/%s" % (TOKEN, method),
        data=json.dumps(p).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"ok": False}
    except Exception:
        return {"ok": False}


# ---------------- Түймелер (түстері: success=жасыл, primary=көк, danger=қызыл) ----------------
G, P, R = "success", "primary", "danger"


def B(text, data, style=None):
    b = {"text": text, "callback_data": data}
    if style:
        b["style"] = style
    return b


def KB(*rows):
    return {"inline_keyboard": [list(r) for r in rows]}


def show(chat, mid, text, kb=None):
    p = dict(chat_id=chat, text=text, parse_mode="HTML", disable_web_page_preview=True)
    if kb:
        p["reply_markup"] = kb
    if mid:
        r = tg("editMessageText", message_id=mid, **p)
        if r.get("ok") or "not modified" in str(r.get("description", "")):
            return
    tg("sendMessage", **p)


esc = html.escape


def fmt(n):
    n = float(n)
    if n < 10:
        return "%.2f ₸" % n
    return "{:,}".format(int(round(n))).replace(",", " ") + " ₸"


# ---------------- Қолданушылар ----------------
def get_user(uid, frm=None):
    k = str(uid)
    with lock:
        if k not in db["users"]:
            db["users"][k] = {"balance": 0, "orders": [], "name": "", "joined": int(time.time()),
                              "spent": 0, "ref": None, "refs": 0, "refearn": 0}
        u = db["users"][k]
        if frm:
            u["name"] = ("@" + frm["username"]) if frm.get("username") else frm.get("first_name", "")
        return u


# ---------------- Қызметтер ----------------
PLATFORMS = {
    "Telegram": ("✈️", ["telegram", "телеграм"]),
    "Instagram": ("📸", ["instagram", "инстаграм", "insta"]),
    "YouTube": ("▶️", ["youtube", "ютуб"]),
    "TikTok": ("🎵", ["tiktok", "тикток", "tik tok"]),
}
TYPES = {
    "comments": ("💬 Пікір", ["comment", "комментар", "пікір"]),
    "views": ("👁️ Көрілім", ["view", "просмотр", "көрілім", "watch"]),
    "likes": ("❤️ Лайк", ["like", "лайк"]),
    "followers": ("👥 Жазылушы", ["follower", "подписчик", "subscriber", "жазылушы", "member", "участник"]),
}
TYPE_SHOW = ["followers", "likes", "views", "comments"]
GUAR = ["refill", "guarant", "non drop", "nondrop", "non-drop", "no drop", "кепіл", "гарант", "♻", "lifetime", "r30", "r60", "r90"]
FINAL = ("Completed", "Canceled", "Partial", "Refunded")
STATUS = {"Pending": "⏳ Күтуде", "In progress": "🔄 Орындалуда", "Processing": "🔄 Өңделуде",
          "Completed": "✅ Орындалды", "Partial": "⚠️ Жартылай", "Canceled": "❌ Бас тартылды", "Refunded": "↩️ Қайтарылды"}

cache = {"t": 0, "list": []}


def get_services():
    if cache["list"] and time.time() - cache["t"] < 300:
        return cache["list"]
    raw = provider(action="services")
    if not isinstance(raw, list):
        raise Exception(str(raw))
    out = []
    for s in raw:
        try:
            item = {"id": str(s["service"]), "name": s.get("name", ""), "category": s.get("category", ""),
                    "rate": float(s["rate"]), "min": int(s["min"]), "max": int(s["max"])}
        except Exception:
            continue
        if item["rate"] <= 0:
            continue
        h = (item["category"] + " " + item["name"]).lower()
        item["plat"] = next((p for p, (_, kw) in PLATFORMS.items() if any(k in h for k in kw)), None)
        item["type"] = next((t for t in ("comments", "views", "likes", "followers") if any(k in h for k in TYPES[t][1])), None)
        item["guar"] = any(k in h for k in GUAR)
        out.append(item)
    cache["t"], cache["list"] = time.time(), out
    return out


def markup_for(plat):
    return float(S["markups"].get(plat, S["markup"]))


def price_k(s):  # 1000 данаға, ₸
    return s["rate"] * (1 + markup_for(s["plat"]) / 100.0) * float(S["rate"])


# ---------------- Мәзір ----------------
def is_admin(uid):
    return bool(ADMIN_ID) and uid == ADMIN_ID


def menu_text(u, uid):
    t = "🚀 <b>SMM Панель</b>\n\n"
    if S["welcome"]:
        t += esc(S["welcome"]) + "\n\n"
    t += "💰 Баланс: <b>%s</b>\n🆔 ID: <code>%s</code>\n\nӘрекетті таңдаңыз 👇" % (fmt(u["balance"]), uid)
    return t


def main_kb(uid):
    # Ескі inline мәзір алынды. Мәзір енді тек төменгі пернетақтада.
    return None


BACK = KB([B("🏠 Мәзір", "menu", P)])
CANCEL = KB([B("❌ Бас тарту", "menu", R)])


def send_status(chat, mid, oid):
    try:
        r = provider(action="status", order=oid)
    except Exception:
        return show(chat, mid, "❌ Провайдермен байланыс қатесі", BACK)
    if r.get("error"):
        return show(chat, mid, "❌ " + esc(str(r["error"])), BACK)
    show(chat, mid, "📦 Тапсырыс <b>#%s</b>\nКүйі: %s\nҚалғаны: %s" % (
        esc(str(oid)), STATUS.get(r.get("status"), esc(str(r.get("status")))), esc(str(r.get("remains", "—")))), BACK)


def list_services(chat, mid, plat, typ, mode):
    try:
        svcs = get_services()
    except Exception:
        return show(chat, mid, "❌ Провайдермен байланыс қатесі. Кейінірек қайталаңыз.", BACK)
    items = [s for s in svcs if s["plat"] == plat and s["type"] == typ]
    if mode == "g":
        items = [s for s in items if s["guar"]]
    items.sort(key=lambda s: s["rate"])
    items = items[:int(S["top"])]
    mode_row = [B("💸 Арзан", "t:%s:%s:c" % (plat, typ), G if mode == "c" else P),
                B("💎 Кепілдікті", "t:%s:%s:g" % (plat, typ), G if mode == "g" else P)]
    back = [B("⬅️ Артқа", "p:" + plat, P)]
    if not items:
        return show(chat, mid, "Бұл бөлімде қызмет табылмады.", KB(mode_row, back))
    text = "%s <b>%s · %s</b>\n%s (1000 данаға):\n\n" % (
        PLATFORMS[plat][0], plat, TYPES[typ][0], "💸 Ең арзан" if mode == "c" else "💎 Кепілдікті (Refill)")
    for i, s in enumerate(items, 1):
        text += "<b>%d.</b> %s\n💵 %s · мин %s · макс %s\n\n" % (i, esc(s["name"][:80]), fmt(price_k(s)), s["min"], s["max"])
    nums = [B(str(i), "s:" + s["id"], G) for i, s in enumerate(items, 1)]
    show(chat, mid, text, KB(nums[:4], nums[4:8], mode_row, back))


# ---------------- Админ панель ----------------
SET_FIELDS = {
    "kaspi": ("💳 Төлем деректері (Kaspi)", str),
    "support": ("🆘 Қолдау username", str),
    "ref_percent": ("🎁 Реферал %", float),
    "min_topup": ("💵 Мин. толтыру ₸", float),
    "top": ("🔢 Тізімдегі қызмет саны", int),
    "welcome": ("👋 Сәлемдесу мәтіні", str),
}


def admin_kb():
    return KB(
        [B("📊 Статистика", "a:stats", P), B("🏦 Провайдер балансы", "a:prov", P)],
        [B("💹 Үстеме", "a:mk", G), B("💱 Курс", "a:rate", G)],
        [B("💰 Баланс беру", "a:add", G), B("👥 Клиенттер", "a:users", P)],
        [B("📢 Хабарлама тарату", "a:cast", P), B("🚫 Бан / ашу", "a:ban", R)],
        [B("⚙️ Баптаулар", "a:set", P)],
        [B("🏠 Мәзір", "menu", P)])


def admin_text():
    return "⚙️ <b>Админ панель</b>\n\nҮстеме (жалпы): <b>%s%%</b>\nКурс: <b>%s</b>\nТехжұмыс: %s" % (
        S["markup"], S["rate"], "🔧 қосулы" if S["maintenance"] else "өшірулі")


def markup_menu():
    t = "💹 <b>Үстеме</b>\n\nЖалпы: <b>%s%%</b>\n" % S["markup"]
    for p, (e, _) in PLATFORMS.items():
        v = S["markups"].get(p)
        t += "%s %s: %s\n" % (e, p, ("<b>%s%%</b>" % v) if v is not None else "жалпы")
    rows = [[B("🌐 Жалпы үстеме", "a:mks:g", G)]]
    pl = [B("%s %s" % (e, p), "a:mks:" + p, P) for p, (e, _) in PLATFORMS.items()]
    rows += [pl[:2], pl[2:], [B("⬅️ Артқа", "adm", P)]]
    return t, KB(*rows)


def set_markup(target, val):
    with lock:
        if target == "g":
            S["markup"] = float(val)
        elif val is None:
            S["markups"].pop(target, None)
        else:
            S["markups"][target] = float(val)
        save()


def on_admin_cb(chat, mid, uid, parts):
    a = parts[1]
    if a == "stats":
        with lock:
            us = list(db["users"].values())
        orders = [o for x in us for o in x["orders"]]
        day = time.time() - 86400
        rev = sum(o["sum"] for o in orders)
        profit = sum(o["sum"] - o.get("cost", 0) for o in orders)
        today = [o for o in orders if o["date"] > day]
        bal = sum(x["balance"] for x in us)
        return show(chat, mid, "📊 <b>Статистика</b>\n\n👥 Клиент: %d\n📦 Тапсырыс: %d (бүгін %d)\n💵 Айналым: %s\n📈 Пайда: <b>%s</b>\n💰 Клиенттер балансы: %s" % (
            len(us), len(orders), len(today), fmt(rev), fmt(profit), fmt(bal)), KB([B("⬅️ Артқа", "adm", P)]))
    if a == "prov":
        try:
            r = provider(action="balance")
            txt = "🏦 Провайдер балансы: <b>%s %s</b>" % (esc(str(r.get("balance", r))), esc(str(r.get("currency", ""))))
        except Exception:
            txt = "❌ Байланыс қатесі"
        return show(chat, mid, txt, KB([B("⬅️ Артқа", "adm", P)]))
    if a == "mk":
        t, k = markup_menu()
        return show(chat, mid, t, k)
    if a == "mks":
        tgt = parts[2]
        name = "Жалпы" if tgt == "g" else tgt
        cur = S["markup"] if tgt == "g" else S["markups"].get(tgt, "жалпы")
        vals = [10, 20, 30, 40, 50, 70, 100]
        btns = [B("%d%%" % v, "a:mkv:%s:%d" % (tgt, v), G) for v in vals]
        rows = [btns[:4], btns[4:], [B("✏️ Басқа сан", "a:mkc:" + tgt, P)]]
        if tgt != "g":
            rows.append([B("↩️ Жалпыға қайту", "a:mkv:%s:reset" % tgt, R)])
        rows.append([B("⬅️ Артқа", "a:mk", P)])
        return show(chat, mid, "💹 <b>%s</b> үстемесі\nҚазір: <b>%s</b>\n\nЖаңа мәнді таңдаңыз:" % (name, cur), KB(*rows))
    if a == "mkv":
        tgt, v = parts[2], parts[3]
        set_markup(tgt, None if v == "reset" else float(v))
        t, k = markup_menu()
        return show(chat, mid, "✅ Сақталды\n\n" + t, k)
    if a == "mkc":
        st[chat] = {"step": "setmk", "t": parts[2]}
        return show(chat, mid, "✏️ Үстемені санмен жазыңыз (мысалы 35):", CANCEL)
    if a == "rate":
        st[chat] = {"step": "setrate"}
        return show(chat, mid, "💱 Қазір: <b>%s</b>\n\nПровайдер бағасы теңгемен болса <b>1</b>, долларменен болса курсты жазыңыз (мысалы 500):" % S["rate"], CANCEL)
    if a == "add":
        st[chat] = {"step": "addbal"}
        return show(chat, mid, "💰 Жазыңыз: <code>USER_ID СОМА</code>\nМысалы: <code>123456789 5000</code>\n(азайту үшін минус: -1000)", CANCEL)
    if a == "cast":
        st[chat] = {"step": "cast"}
        return show(chat, mid, "📢 Барлық клиентке жіберілетін мәтінді жазыңыз:", CANCEL)
    if a == "ban":
        st[chat] = {"step": "ban"}
        return show(chat, mid, "🚫 Бан салу/алу үшін USER_ID жазыңыз:", CANCEL)
    if a == "users":
        with lock:
            top = sorted(db["users"].items(), key=lambda kv: kv[1]["spent"], reverse=True)[:10]
        t = "👥 <b>Үздік клиенттер</b>\n\n"
        for i, (k, x) in enumerate(top, 1):
            t += "%d. %s <code>%s</code> · %s · баланс %s\n" % (i, esc(x["name"] or "-"), k, fmt(x["spent"]), fmt(x["balance"]))
        return show(chat, mid, t, KB([B("⬅️ Артқа", "adm", P)]))
    if a == "set":
        t = "⚙️ <b>Баптаулар</b>\n\n"
        rows = []
        for k, (label, _) in SET_FIELDS.items():
            v = S[k]
            t += "%s: <b>%s</b>\n" % (label, esc(str(v)) if str(v) else "—")
            rows.append([B("✏️ " + label, "a:sv:" + k, P)])
        rows.append([B("🔧 Техжұмыс: " + ("ӨШІРУ" if S["maintenance"] else "ҚОСУ"), "a:tm", R if not S["maintenance"] else G)])
        rows.append([B("⬅️ Артқа", "adm", P)])
        return show(chat, mid, t, KB(*rows))
    if a == "sv":
        k = parts[2]
        st[chat] = {"step": "setval", "k": k}
        return show(chat, mid, "✏️ <b>%s</b>\nЖаңа мәнді жазыңыз (тазалау үшін «-»):" % SET_FIELDS[k][0], CANCEL)
    if a == "tm":
        S["maintenance"] = not S["maintenance"]
        save()
        return show(chat, mid, admin_text(), admin_kb())


# ---------------- Callback ----------------
def on_callback(q):
    chat, mid, uid = q["message"]["chat"]["id"], q["message"]["message_id"], q["from"]["id"]
    tg("answerCallbackQuery", callback_query_id=q["id"])
    u = get_user(uid, q["from"])
    parts = q["data"].split(":")
    a = parts[0]
    if str(uid) in db["banned"]:
        return
    if S["maintenance"] and not is_admin(uid):
        return show(chat, mid, "🔧 Техникалық жұмыс жүріп жатыр. Кейінірек қайтып келіңіз.")

    if a == "menu":
        st.pop(chat, None)
        return show(chat, mid, menu_text(u, uid), main_kb(uid))

    if a == "adm" and is_admin(uid):
        st.pop(chat, None)
        return show(chat, mid, admin_text(), admin_kb())
    if a == "a" and is_admin(uid):
        return on_admin_cb(chat, mid, uid, parts)

    if a == "tp" and is_admin(uid):  # төлем растау
        tid, act = parts[2], parts[1]
        with lock:
            t = db["topups"].get(tid)
            if not t or t["status"] != "pending":
                return tg("sendMessage", chat_id=chat, text="Бұл өтінім өңделіп қойған.")
            t["status"] = "ok" if act == "ok" else "no"
            tu = get_user(t["uid"])
            if act == "ok":
                tu["balance"] += t["amount"]
                if tu.get("ref") and str(tu["ref"]) in db["users"]:
                    bonus = t["amount"] * float(S["ref_percent"]) / 100.0
                    ru = db["users"][str(tu["ref"])]
                    ru["balance"] += bonus
                    ru["refearn"] += bonus
                    tg("sendMessage", chat_id=tu["ref"], text="🎁 Рефералыңыздың төлемінен бонус: +%s" % fmt(bonus))
            save()
        tg("editMessageReplyMarkup", chat_id=chat, message_id=mid, reply_markup={"inline_keyboard": []})
        if act == "ok":
            tg("sendMessage", chat_id=t["uid"], text="✅ Төлеміңіз расталды! +%s\n💰 Баланс: %s" % (fmt(t["amount"]), fmt(tu["balance"])))
            return tg("sendMessage", chat_id=chat, text="✅ Расталды: %s (%s)" % (fmt(t["amount"]), t["uid"]))
        tg("sendMessage", chat_id=t["uid"], text="❌ Төлеміңіз расталмады. Сұрақ болса қолдауға жазыңыз.")
        return tg("sendMessage", chat_id=chat, text="❌ Қабылданбады")

    if a == "order":
        rows = [B("%s %s" % (e, p), "p:" + p, P) for p, (e, _) in PLATFORMS.items()]
        return show(chat, mid, "📱 <b>Платформаны таңдаңыз:</b>", KB(rows[:2], rows[2:], [B("🏠 Мәзір", "menu", P)]))

    if a == "p":
        plat = parts[1]
        rows = [B(TYPES[t][0], "t:%s:%s:c" % (plat, t), G) for t in TYPE_SHOW]
        return show(chat, mid, "%s <b>%s</b>\nТипті таңдаңыз:" % (PLATFORMS[plat][0], plat), KB(rows[:2], rows[2:], [B("⬅️ Артқа", "order", P)]))

    if a == "t":
        return list_services(chat, mid, parts[1], parts[2], parts[3])

    if a == "s":
        try:
            s = next((x for x in get_services() if x["id"] == parts[1]), None)
        except Exception:
            s = None
        if not s:
            return show(chat, mid, "Қызмет табылмады.", BACK)
        st[chat] = {"step": "link", "svc": s}
        return show(chat, mid, "✅ <b>%s</b>\n\n🔗 Сілтемені (немесе @username) жіберіңіз:" % esc(s["name"]), CANCEL)

    if a == "ok":
        s = st.get(chat)
        if not s or s.get("step") != "confirm":
            return show(chat, mid, menu_text(u, uid), main_kb(uid))
        with lock:
            if u["balance"] < s["sum"]:
                return show(chat, mid, "❌ Баланс жеткіліксіз.\nКерек: %s\nБалансыңыз: %s" % (fmt(s["sum"]), fmt(u["balance"])),
                            KB([B("💳 Толтыру", "top", G)], [B("🏠 Мәзір", "menu", P)]))
            u["balance"] -= s["sum"]
            save()
        st.pop(chat, None)
        try:
            r = provider(action="add", service=s["svc"]["id"], link=s["link"], quantity=s["qty"])
        except Exception:
            r = {"error": "байланыс қатесі"}
        if not r.get("order"):
            with lock:
                u["balance"] += s["sum"]
                save()
            return show(chat, mid, "❌ Тапсырыс қабылданмады: %s\nАқшаңыз қайтарылды." % esc(str(r.get("error", "белгісіз қате"))), BACK)
        cost = s["svc"]["rate"] * s["qty"] / 1000.0 * float(S["rate"])
        with lock:
            u["spent"] += s["sum"]
            u["orders"].insert(0, {"id": r["order"], "name": s["svc"]["name"], "qty": s["qty"], "sum": s["sum"],
                                   "cost": cost, "date": int(time.time()), "status": "Pending", "done": False})
            u["orders"] = u["orders"][:40]
            save()
        if ADMIN_ID:
            tg("sendMessage", chat_id=ADMIN_ID, text="🛍 Жаңа тапсырыс #%s\n%s (%s)\n%s\n%s дана · %s · пайда ≈ %s" % (
                r["order"], u["name"], uid, s["svc"]["name"], s["qty"], fmt(s["sum"]), fmt(s["sum"] - cost)))
        return show(chat, mid, "✅ <b>Тапсырыс қабылданды!</b>\n\nНөмірі: <b>#%s</b>\nСомасы: %s\nБаланс: %s\n\nОрындалғанда хабарлаймын 🔔" % (
            r["order"], fmt(s["sum"]), fmt(u["balance"])), KB([B("🔍 Күйін тексеру", "st:%s" % r["order"], P)], [B("🏠 Мәзір", "menu", P)]))

    if a == "top":
        t = "💳 <b>Баланс толтыру</b>\n\nБалансыңыз: <b>%s</b>\nСомасын таңдаңыз:" % fmt(u["balance"])
        v = [1000, 2000, 5000, 10000]
        rows = [[B(fmt(x), "ta:%d" % x, G) for x in v[:2]], [B(fmt(x), "ta:%d" % x, G) for x in v[2:]],
                [B("✏️ Басқа сома", "topc", P)], [B("🏠 Мәзір", "menu", P)]]
        return show(chat, mid, t, KB(*rows))
    if a == "topc":
        st[chat] = {"step": "topamt"}
        return show(chat, mid, "✏️ Сомасын жазыңыз (мин. %s):" % fmt(S["min_topup"]), CANCEL)
    if a == "ta":
        return ask_receipt(chat, mid, int(parts[1]))

    if a == "my":
        if not u["orders"]:
            return show(chat, mid, "Әзірге тапсырыс жоқ.", BACK)
        rows = [[B("#%s · %s дана · %s" % (o["id"], o["qty"], fmt(o["sum"])), "st:%s" % o["id"], P)] for o in u["orders"][:8]]
        return show(chat, mid, "📦 <b>Соңғы тапсырыстар</b>\nКүйін көру үшін басыңыз:", KB(*rows, [B("🏠 Мәзір", "menu", P)]))
    if a == "st":
        return send_status(chat, mid, parts[1])
    if a == "chk":
        st[chat] = {"step": "status"}
        return show(chat, mid, "🔍 Тапсырыс нөмірін жіберіңіз:", CANCEL)

    if a == "prof":
        d = time.strftime("%d.%m.%Y", time.localtime(u["joined"]))
        return show(chat, mid, "👤 <b>Профиль</b>\n\n🆔 ID: <code>%s</code>\n📅 Тіркелген: %s\n📦 Тапсырыс: %d\n💸 Жұмсаған: %s\n💰 Баланс: <b>%s</b>" % (
            uid, d, len(u["orders"]), fmt(u["spent"]), fmt(u["balance"])), BACK)
    if a == "refl":
        link = "https://t.me/%s?start=ref_%s" % (BOT["username"], uid)
        return show(chat, mid, "🎁 <b>Рефералдық бағдарлама</b>\n\nДосыңыз сіздің сілтемеңізбен кіріп, баланс толтырса, сіз әр төлемнен <b>%s%%</b> бонус аласыз.\n\n🔗 Сілтемеңіз:\n<code>%s</code>\n\n👥 Шақырылған: %d\n💰 Тапқаныңыз: %s" % (
            S["ref_percent"], link, u["refs"], fmt(u["refearn"])), BACK)
    if a == "sup":
        sup = S["support"].replace("@", "")
        return show(chat, mid, ("🆘 Қолдау: @" + sup) if sup else "🆘 Қолдау қазір қолжетімсіз.", BACK)


def ask_receipt(chat, mid, amount):
    if amount < float(S["min_topup"]):
        return show(chat, mid, "❌ Ең аз сома: %s" % fmt(S["min_topup"]), KB([B("⬅️ Артқа", "top", P)]))
    if not S["kaspi"]:
        return show(chat, mid, "Төлем деректері әлі орнатылмаған. Қолдауға жазыңыз.", BACK)
    st[chat] = {"step": "receipt", "amount": amount}
    show(chat, mid, "💳 <b>Төлем</b>\n\nСома: <b>%s</b>\nАударым деректері:\n<code>%s</code>\n\nТөлегеннен кейін <b>чектің скриншотын</b> осы чатқа жіберіңіз 📸" % (
        fmt(amount), esc(S["kaspi"])), CANCEL)


# ---------------- Хабарламалар ----------------
def to_float(t):
    return float(t.replace(",", ".").replace("%", "").strip())


# Төменгі қалқымалы пернетақта (reply keyboard)
def RB(text, style):
    return {"text": text, "style": style}


def reply_kb(uid):
    rows = [
        [RB("🛍 Тапсырыс беру", G)],
        [RB("💳 Баланс толтыру", G), RB("📦 Тапсырыстарым", P)],
        [RB("🔍 Күйін тексеру", P), RB("👤 Профиль", P)],
        [RB("🎁 Рефералдық", P), RB("🆘 Қолдау", P)],
    ]
    if is_admin(uid):
        rows.append([RB("⚙️ Админ панель", R)])
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


KB_MAP = {"🛍 Тапсырыс беру": "order", "💳 Баланс толтыру": "top", "📦 Тапсырыстарым": "my",
          "🔍 Күйін тексеру": "chk", "👤 Профиль": "prof", "🎁 Рефералдық": "refl", "🆘 Қолдау": "sup",
          "⚙️ Админ панель": "adm"}


def on_message(m):
    if m["chat"]["type"] != "private":
        return
    chat, uid = m["chat"]["id"], m["from"]["id"]
    text = (m.get("text") or "").strip()
    new = str(uid) not in db["users"]
    u = get_user(uid, m["from"])

    if text == "/id":
        return tg("sendMessage", chat_id=chat, text="Сіздің ID: %s" % uid)
    if str(uid) in db["banned"]:
        return tg("sendMessage", chat_id=chat, text="🚫 Қолжетімсіз.")
    if S["maintenance"] and not is_admin(uid):
        return tg("sendMessage", chat_id=chat, text="🔧 Техникалық жұмыс жүріп жатыр. Кейінірек қайтып келіңіз.")

    if text.startswith("/start") or text == "/menu":
        st.pop(chat, None)
        parts = text.split()
        if new and len(parts) > 1 and parts[1].startswith("ref_"):
            rid = parts[1][4:]
            if rid.isdigit() and int(rid) != uid and rid in db["users"]:
                u["ref"] = int(rid)
                db["users"][rid]["refs"] += 1
        save()
        return show(chat, 0, menu_text(u, uid), reply_kb(uid))
    if text == "/admin" and is_admin(uid):
        return show(chat, 0, admin_text(), admin_kb())
    if text in KB_MAP:
        st.pop(chat, None)
        return on_callback({"message": {"chat": {"id": chat}, "message_id": 0},
                            "from": m["from"], "id": "0", "data": KB_MAP[text]})

    s = st.get(chat)
    if not s:
        return show(chat, 0, menu_text(u, uid), reply_kb(uid))
    step = s["step"]

    # --- клиент ағыны ---
    if step == "status":
        st.pop(chat, None)
        if not text.isdigit():
            return show(chat, 0, "Нөмір қате.", BACK)
        return send_status(chat, 0, text)
    if step == "link":
        ok = text.startswith("http") and " " not in text or (text.lstrip("@").replace(".", "").replace("_", "").isalnum() and len(text) > 2)
        if not ok:
            return show(chat, 0, "❌ Сілтеме қате. Қайта жіберіңіз:", CANCEL)
        s["link"], s["step"] = text, "qty"
        return show(chat, 0, "🔢 Санын жазыңыз (%s – %s):" % (s["svc"]["min"], s["svc"]["max"]), CANCEL)
    if step == "qty":
        if not text.isdigit() or not (s["svc"]["min"] <= int(text) <= s["svc"]["max"]):
            return show(chat, 0, "❌ Саны %s мен %s аралығында болуы керек:" % (s["svc"]["min"], s["svc"]["max"]), CANCEL)
        q = int(text)
        s["qty"], s["sum"], s["step"] = q, int(-(-price_k(s["svc"]) * q // 1000)), "confirm"
        return show(chat, 0, "📋 <b>Тапсырысты тексеріңіз</b>\n\n%s\n🔗 %s\n🔢 %d дана\n💵 Сомасы: <b>%s</b>\n💰 Балансыңыз: %s" % (
            esc(s["svc"]["name"]), esc(s["link"]), q, fmt(s["sum"]), fmt(u["balance"])),
            KB([B("✅ Растау", "ok", G), B("❌ Бас тарту", "menu", R)]))
    if step == "topamt":
        try:
            amt = int(to_float(text))
        except Exception:
            return show(chat, 0, "❌ Санмен жазыңыз:", CANCEL)
        return ask_receipt(chat, 0, amt)
    if step == "receipt":
        fid, kind = None, None
        if m.get("photo"):
            fid, kind = m["photo"][-1]["file_id"], "sendPhoto"
        elif m.get("document"):
            fid, kind = m["document"]["file_id"], "sendDocument"
        if not fid:
            return show(chat, 0, "📸 Чектің скриншотын (фото) жіберіңіз:", CANCEL)
        tid = str(int(time.time() * 1000))
        with lock:
            db["topups"][tid] = {"uid": uid, "amount": s["amount"], "status": "pending", "ts": int(time.time())}
            save()
        st.pop(chat, None)
        if ADMIN_ID:
            field = "photo" if kind == "sendPhoto" else "document"
            tg(kind, chat_id=ADMIN_ID, caption="💳 Төлем өтінімі\n%s (%s)\nСома: %s" % (u["name"], uid, fmt(s["amount"])),
               reply_markup=KB([B("✅ Растау", "tp:ok:" + tid, G), B("❌ Қабылдамау", "tp:no:" + tid, R)]), **{field: fid})
        return show(chat, 0, "✅ Чек жіберілді. Әкімші тексерген соң баланс толықтырылады.", BACK)

    # --- админ ағыны ---
    if not is_admin(uid):
        return
    back = KB([B("⚙️ Админ панель", "adm", P)])
    if step == "setmk":
        try:
            v = to_float(text)
            assert 0 <= v <= 1000
        except Exception:
            return show(chat, 0, "❌ Санмен жазыңыз (0–1000):", CANCEL)
        set_markup(s["t"], v)
        st.pop(chat, None)
        t, k = markup_menu()
        return show(chat, 0, "✅ Сақталды\n\n" + t, k)
    if step == "setrate":
        try:
            v = to_float(text)
            assert v > 0
        except Exception:
            return show(chat, 0, "❌ Санмен жазыңыз:", CANCEL)
        S["rate"] = v
        save()
        st.pop(chat, None)
        return show(chat, 0, "✅ Курс: <b>%s</b>" % v, back)
    if step == "setval":
        k = s["k"]
        typ = SET_FIELDS[k][1]
        try:
            v = "" if text == "-" else typ(to_float(text) if typ is not str else text)
        except Exception:
            return show(chat, 0, "❌ Мән қате:", CANCEL)
        S[k] = v
        save()
        st.pop(chat, None)
        return show(chat, 0, "✅ Сақталды", back)
    if step == "addbal":
        try:
            tid, amt = text.split()
            amt = to_float(amt)
            assert tid in db["users"]
        except Exception:
            return show(chat, 0, "❌ Формат: <code>USER_ID СОМА</code> (клиент ботқа кірген болуы керек)", CANCEL)
        with lock:
            db["users"][tid]["balance"] += amt
            save()
        st.pop(chat, None)
        tg("sendMessage", chat_id=int(tid), text="💰 Балансыңыз %s%s өзгерді. Қазір: %s" % ("+" if amt >= 0 else "", fmt(amt), fmt(db["users"][tid]["balance"])))
        return show(chat, 0, "✅ Дайын. %s балансы: %s" % (tid, fmt(db["users"][tid]["balance"])), back)
    if step == "ban":
        st.pop(chat, None)
        if text in db["banned"]:
            db["banned"].remove(text)
            msg = "✅ Бан алынды"
        else:
            db["banned"].append(text)
            msg = "🚫 Бан салынды"
        save()
        return show(chat, 0, msg + ": " + esc(text), back)
    if step == "cast":
        st.pop(chat, None)
        ids = list(db["users"].keys())

        def run():
            n = 0
            for i in ids:
                if tg("sendMessage", chat_id=int(i), text=text).get("ok"):
                    n += 1
                time.sleep(0.05)
            tg("sendMessage", chat_id=chat, text="📢 Жіберілді: %d / %d" % (n, len(ids)))
        threading.Thread(target=run, daemon=True).start()
        return show(chat, 0, "📢 Тарату басталды...", back)


# ---------------- Тапсырыс күйін бақылау ----------------
def finish_order(uid, o, r):
    o["done"] = True
    u = db["users"][uid]
    status = r["status"]
    msg = ""
    if status == "Completed":
        msg = "✅ Тапсырыс <b>#%s</b> орындалды!" % o["id"]
    elif status in ("Canceled", "Refunded"):
        u["balance"] += o["sum"]
        msg = "❌ Тапсырыс <b>#%s</b> бас тартылды. Ақша қайтарылды: +%s" % (o["id"], fmt(o["sum"]))
    elif status == "Partial":
        try:
            back = int(o["sum"] * int(r.get("remains", 0)) / max(o["qty"], 1))
        except Exception:
            back = 0
        u["balance"] += back
        msg = "⚠️ Тапсырыс <b>#%s</b> жартылай орындалды. Қайтарылды: +%s" % (o["id"], fmt(back))
    if msg:
        tg("sendMessage", chat_id=int(uid), text=msg, parse_mode="HTML")


def watcher():
    while True:
        time.sleep(120)
        try:
            pend = []
            with lock:
                for uid, u in db["users"].items():
                    for o in u["orders"]:
                        if o.get("done"):
                            continue
                        if time.time() - o["date"] > 14 * 86400:
                            o["done"] = True
                        else:
                            pend.append((uid, o))
            for i in range(0, len(pend), 50):
                chunk = pend[i:i + 50]
                res = provider(action="status", orders=",".join(str(o["id"]) for _, o in chunk))
                if not isinstance(res, dict):
                    continue
                for uid, o in chunk:
                    r = res.get(str(o["id"]))
                    if isinstance(r, dict) and r.get("status"):
                        o["status"] = r["status"]
                        if r["status"] in FINAL:
                            with lock:
                                finish_order(uid, o, r)
            save()
        except Exception:
            traceback.print_exc()


# ---------------- Іске қосу ----------------
def safe(fn, arg):
    try:
        fn(arg)
    except Exception:
        traceback.print_exc()


def main():
    if TOKEN.startswith("СІЗДІҢ"):
        print("Алдымен файлдың жоғарғы жағына TOKEN жазыңыз")
        return
    me = tg("getMe")
    if not me.get("ok"):
        print("Токен қате немесе интернет жоқ:", me)
        return
    BOT["username"] = me["result"]["username"]
    print("Бот іске қосылды: @%s" % BOT["username"])
    if not ADMIN_ID:
        print("ЕСКЕРТУ: ADMIN_ID жазылмаған. Ботқа /id деп жазып, ID-ді файлға қойыңыз.")
    threading.Thread(target=watcher, daemon=True).start()
    offset = 0
    while True:
        r = tg("getUpdates", offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
        if not r.get("ok"):
            time.sleep(3)
            continue
        for up in r["result"]:
            offset = up["update_id"] + 1
            if "callback_query" in up:
                threading.Thread(target=safe, args=(on_callback, up["callback_query"]), daemon=True).start()
            elif "message" in up:
                threading.Thread(target=safe, args=(on_message, up["message"]), daemon=True).start()


main()
