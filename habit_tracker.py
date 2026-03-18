import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import cloudinary
import cloudinary.uploader
import hashlib
import secrets
import json
from datetime import datetime, date, timedelta

# --- 1. KONFIGURACE CLOUDU (Google Sheets & Cloudinary) ---

def get_gspread_client():
    """Autorizace do Google Sheets pomocí Service Accountu ze Secrets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def load_from_gsheet(sheet_name):
    """Načte data z konkrétního listu v Google tabulce."""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["spreadsheet_id"]).worksheet(sheet_name)
        data = sheet.get_all_records()

        # Převod JSON stringů zpět na listy/dicty (pro členy a habity)
        for row in data:
            for key in row:
                val = str(row[key])
                if val.startswith('[') or val.startswith('{'):
                    try:
                        row[key] = json.loads(val)
                    except:
                        pass
        return data
    except Exception as e:
        st.error(f"Chyba při čtení z Google Sheets ({sheet_name}): {e}")
        return [] if sheet_name == "records" else {}

def save_to_gsheet(sheet_name, data_to_save):
    """Uloží data do Google tabulky (přepíše celý list)."""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["spreadsheet_id"]).worksheet(sheet_name)
        sheet.clear()

        if not data_to_save:
            return

        # Převod slovníku (users/groups) na seznam řádků
        if isinstance(data_to_save, dict):
            final_list = []
            for k, v in data_to_save.items():
                row = {"id_key": k}
                row.update(v)
                final_list.append(row)
            data_to_save = final_list

        headers = list(data_to_save[0].keys())
        rows = [headers]

        for item in data_to_save:
            row_values = []
            for h in headers:
                val = item.get(h, "")
                if isinstance(val, (list, dict)):
                    row_values.append(json.dumps(val))
                else:
                    row_values.append(str(val))
            rows.append(row_values)

        sheet.update(rows)
    except Exception as e:
        st.error(f"Chyba při zápisu do Google Sheets ({sheet_name}): {e}")

def upload_to_cloudinary(file):
    """Nahraje soubor na Cloudinary a vrátí URL."""
    cloudinary.config(
        cloud_name = st.secrets["cloudinary_name"],
        api_key = st.secrets["cloudinary_key"],
        api_secret = st.secrets["cloudinary_secret"],
        secure = True
    )
    res = cloudinary.uploader.upload(file)
    return res["secure_url"]

def hash_pw(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- 2. LOGIKA GENEROVÁNÍ ÚKOLŮ ---

def sync_daily_habits(user_id, group_id, users_db, groups_db, records_db):
    """Zkontroluje, zda má uživatel vygenerované záznamy pro všechny dny."""
    last_seen_str = users_db[user_id].get("last_seen", str(date.today() - timedelta(days=1)))
    last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d").date()
    today = date.today()

    all_group_habits = groups_db.get(group_id, {}).get("habits", [])
    my_habits = [h for h in all_group_habits if isinstance(h, dict) and h.get('owner') == user_id]

    check_dates = [last_seen + timedelta(days=i) for i in range(1, (today - last_seen).days + 1)]
    if today not in check_dates:
        check_dates.append(today)

    changed = False
    for d in check_dates:
        d_str = str(d)
        for h in my_habits:
            exists = any(r for r in records_db if r['user_id'] == user_id and r['habit'] == h['name'] and r['date'] == d_str)
            if not exists:
                records_db.append({
                    "id": secrets.token_hex(4),
                    "user_id": user_id,
                    "group_id": group_id,
                    "habit": h['name'],
                    "punishment": h['punishment'],
                    "date": d_str,
                    "status": "todo",
                    "comment": "",
                    "image_url": ""
                })
                changed = True

    users_db[user_id]["last_seen"] = str(today)
    if changed:
        save_to_gsheet("users", users_db)
        save_to_gsheet("records", records_db)

# --- 3. UI STRÁNKY ---

def login_page():
    st.title("🎯 Habit Tracker")
    t1, t2 = st.tabs(["🔐 Přihlášení", "📝 Registrace"])

    with t1:
        u = st.text_input("Uživatelské jméno")
        p = st.text_input("Heslo", type="password")
        if st.button("Vstoupit"):
            raw_users = load_from_gsheet("users")
            users = {row['id_key']: {k: v for k, v in row.items() if k != 'id_key'} for row in raw_users}
            if u in users and users[u]["password"] == hash_pw(p):
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Neplatné údaje.")

    with t2:
        nu = st.text_input("Zvolte jméno")
        np = st.text_input("Zvolte heslo", type="password")
        if st.button("Vytvořit účet"):
            raw_users = load_from_gsheet("users")
            users = {row['id_key']: {k: v for k, v in row.items() if k != 'id_key'} for row in raw_users}
            if nu in users:
                st.error("Jméno je obsazené.")
            else:
                users[nu] = {"password": hash_pw(np), "groups": [], "last_seen": str(date.today())}
                save_to_gsheet("users", users)
                st.success("Účet vytvořen!")

def main_app():
    user_id = st.session_state.user

    # Načtení dat
    raw_users = load_from_gsheet("users")
    users = {row['id_key']: {k: v for k, v in row.items() if k != 'id_key'} for row in raw_users}

    raw_groups = load_from_gsheet("groups")
    groups = {row['id_key']: {k: v for k, v in row.items() if k != 'id_key'} for row in raw_groups}

    records = load_from_gsheet("records")
    user_data = users[user_id]

    # --- SIDEBAR ---
    st.sidebar.title(f"👤 {user_id}")
    u_groups = user_data.get("groups", [])
    group_options = {g_id: groups[g_id]["name"] for g_id in u_groups if g_id in groups}

    sel_g_id = st.sidebar.selectbox("Vyberte skupinu:", list(group_options.keys()), format_func=lambda x: group_options[x]) if group_options else None

    if sel_g_id:
        cur_g = groups[sel_g_id]
        st.sidebar.markdown(f"### 🏠 {cur_g['name']} ({sel_g_id})")

        with st.sidebar.expander("👥 Členové"):
            for m in cur_g.get("members", []): st.text(f"• {m}")

        with st.sidebar.expander("➕ Přidat nový habit"):
            nh = st.text_input("Co chceš dělat?", key="nh")
            np = st.text_input("Trest při nesplnění", key="np")
            if st.button("Uložit habit"):
                cur_g.setdefault("habits", []).append({"name": nh, "punishment": np, "owner": user_id})
                save_to_gsheet("groups", groups)
                st.rerun()

    st.sidebar.divider()
    with st.sidebar.expander("🏢 Vytvořit skupinu"):
        ng = st.text_input("Název nové skupiny")
        if st.button("Založit"):
            nid = secrets.token_hex(3).upper()
            groups[nid] = {"name": ng, "members": [user_id], "habits": []}
            user_data.setdefault("groups", []).append(nid)
            save_to_gsheet("groups", groups)
            save_to_gsheet("users", users)
            st.rerun()

    with st.sidebar.expander("🔗 Připojit se ke skupině"):
        jc = st.text_input("Kód skupiny")
        if st.button("Vstoupit"):
            if jc in groups:
                if user_id not in groups[jc]["members"]:
                    groups[jc]["members"].append(user_id)
                if jc not in user_data["groups"]:
                    user_data["groups"].append(jc)
                save_to_gsheet("groups", groups)
                save_to_gsheet("users", users)
                st.rerun()

    if st.sidebar.button("🚪 Odhlásit se"):
        del st.session_state.user
        st.rerun()

    # --- HLAVNÍ FEED ---
    if not sel_g_id:
        st.info("👈 Vyberte skupinu v bočním panelu.")
        return

    sync_daily_habits(user_id, sel_g_id, users, groups, records)
    today_obj = date.today()

    st.title(f"Feed: {groups[sel_g_id]['name']}")

    # --- MOJE RESTY ---
    st.subheader("📝 Moje úkoly")
    my_tasks = [r for r in records if r['user_id'] == user_id and r['group_id'] == sel_g_id and r['status'] in ['todo', 'punished']]

    if not my_tasks:
        st.success("Všechno hotovo! Dobrá práce.")
    else:
        for r in sorted(my_tasks, key=lambda x: x['date']):
            # PŘÍPAD A: Byl ti udělen TREST
            if r['status'] == 'punished':
                header = f"⚠️ TREST: {r['punishment']} (Zamítnuto u: {r['habit']})"
                with st.expander(header, expanded=True):
                    st.error(f"Tvůj pokus o '{r['habit']}' byl zamítnut. Musíš splnit trest: **{r['punishment']}**")
                    img = st.file_uploader("Nahraj důkaz o splnění trestu", type=['png', 'jpg', 'jpeg'], key=f"p_{r['id']}")
                    c = st.text_input("Komentář k trestu", key=f"cp_{r['id']}")
                    if st.button("Odevzdat trest", key=f"bp_{r['id']}"):
                        if img: r['image_url'] = upload_to_cloudinary(img)
                        r['status'], r['comment'] = 'pending', f"OPRAVA (Trest): {c}"
                        save_to_gsheet("records", records); st.rerun()

            # PŘÍPAD B: Standardní HABIT (i když se zpožděním)
            else:
                task_date = datetime.strptime(r['date'], "%Y-%m-%d").date()
                days_diff = (today_obj - task_date).days
                delay_label = f" (Zpoždění {days_diff} dní)" if days_diff > 0 else " (Dnešní)"

                header = f"🎯 HABIT: {r['habit']} z {r['date']}{delay_label}"
                with st.expander(header):
                    st.info(f"Úkol k splnění: **{r['habit']}**")
                    img = st.file_uploader("Nahraj foto důkaz", type=['png', 'jpg', 'jpeg'], key=f"i_{r['id']}")
                    c = st.text_input("Komentář", key=f"c_{r['id']}")
                    if st.button("Odeslat ke schválení", key=f"b_{r['id']}"):
                        if img: r['image_url'] = upload_to_cloudinary(img)
                        r['status'], r['comment'] = 'pending', c
                        save_to_gsheet("records", records); st.rerun()

    st.divider()
    # --- KE SCHVÁLENÍ OSTATNÍM ---
    st.subheader("👀 Ke schválení parťákům")
    to_rev = [r for r in records if r['group_id'] == sel_g_id and r['status'] == 'pending' and r['user_id'] != user_id]

    if not to_rev:
        st.caption("Nikdo zatím nic neposlal.")
    else:
        for r in to_rev:
            st.warning(f"🔔 {r['user_id']} odevzdal: **{r['habit']}**")
            if r.get('image_url'):
                st.image(r['image_url'])
            st.write(f"💬 {r['comment']} (Úkol z: {r['date']})")

            c1, c2 = st.columns(2)
            if c1.button(f"✅ Schválit {r['user_id']}", key=f"ok_{r['id']}"):
                r['status'] = 'approved'
                save_to_gsheet("records", records)
                st.rerun()

            if c2.button(f"❌ Zamítnout (Udělit trest!)", key=f"ko_{r['id']}"):
                # Nastavíme status 'punished', což uživateli aktivuje červený box s trestem
                r['status'] = 'punished'
                save_to_gsheet("records", records)
                st.rerun()

if 'user' not in st.session_state:
    login_page()
else:
    main_app()
