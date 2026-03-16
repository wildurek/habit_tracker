import streamlit as st
import json
import os
import hashlib
import secrets
from datetime import datetime, date, timedelta
from PIL import Image

# --- KONFIGURACE SOUBORŮ ---
DB_USERS = "users.json"
DB_GROUPS = "groups.json"
DB_RECORDS = "records.json"
UPLOAD_DIR = "uploads"

# Ujistíme se, že složka pro fotky existuje
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- POMOCNÉ FUNKCE PRO DATABÁZI (S POJISTKOU PROTI PÁDU) ---
def load_db(file, default_type=dict):
    if not os.path.exists(file):
        return default_type()
    try:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, default_type):
                return default_type()
            return data
    except (json.JSONDecodeError, IOError):
        return default_type()

def save_db(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def hash_pw(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- LOGIKA SYNCHRONIZACE HABITŮ ---
def sync_daily_habits(user_id, group_id):
    users = load_db(DB_USERS, dict)
    groups = load_db(DB_GROUPS, dict)
    records = load_db(DB_RECORDS, list)

    # Zjistíme, kdy byl uživatel naposledy aktivní
    last_seen_str = users[user_id].get("last_seen", str(date.today() - timedelta(days=1)))
    last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d").date()
    today = date.today()

    # Najdeme habity, které patří tomuto uživateli v této skupině
    all_group_habits = groups.get(group_id, {}).get("habits", [])
    my_habits = [h for h in all_group_habits if isinstance(h, dict) and h.get('owner') == user_id]

    # Vytvoříme seznam dní, které je potřeba zkontrolovat (včetně dneška)
    check_dates = [last_seen + timedelta(days=i) for i in range(1, (today - last_seen).days + 1)]
    if today not in check_dates:
        check_dates.append(today)

    changed = False
    for d in check_dates:
        d_str = str(d)
        for h in my_habits:
            # Pokud záznam pro daný den a habit neexistuje, vytvoříme ho
            exists = any(r for r in records if r['user_id'] == user_id and r['habit'] == h['name'] and r['date'] == d_str)
            if not exists:
                records.append({
                    "id": secrets.token_hex(4),
                    "user_id": user_id,
                    "group_id": group_id,
                    "habit": h['name'],
                    "punishment": h['punishment'], # Tady uchováváme název trestu
                    "date": d_str,
                    "status": "todo",
                    "comment": "",
                    "image_path": None
                })
                changed = True

    # Aktualizujeme datum poslední aktivity
    users[user_id]["last_seen"] = str(today)

    if changed:
        save_db(DB_USERS, users)
        save_db(DB_RECORDS, records)

# --- UI STRÁNKY (LOGIN A REGISTRACE) ---
def login_page():
    st.title("🎯 Habit Tracker")
    tab1, tab2 = st.tabs(["🔐 Přihlášení", "📝 Registrace"])

    with tab1:
        u = st.text_input("Uživatelské jméno")
        p = st.text_input("Heslo", type="password")
        if st.button("Vstoupit do aplikace"):
            users = load_db(DB_USERS, dict)
            if u in users and users[u]["pw"] == hash_pw(p):
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Neplatné přihlašovací údaje.")

    with tab2:
        new_u = st.text_input("Zvolte si jméno")
        new_p = st.text_input("Zvolte si heslo", type="password")
        if st.button("Vytvořit účet"):
            users = load_db(DB_USERS, dict)
            if not new_u or not new_p:
                st.warning("Vyplňte všechna pole.")
            elif new_u in users:
                st.error("Toto jméno je již obsazené.")
            else:
                users[new_u] = {"pw": hash_pw(new_p), "groups": [], "last_seen": str(date.today())}
                save_db(DB_USERS, users)
                st.success("Účet vytvořen! Nyní se můžete přihlásit.")

# --- HLAVNÍ APLIKACE ---
def main_app():
    user_id = st.session_state.user
    users = load_db(DB_USERS, dict)
    groups = load_db(DB_GROUPS, dict)
    user_data = users[user_id]

    # --- SIDEBAR KONFIGURACE ---
    st.sidebar.title(f"👤 {user_id}")

    # Výběr aktivní skupiny
    u_groups = user_data.get("groups", [])
    group_options = {g_id: groups[g_id]["name"] for g_id in u_groups if g_id in groups}

    sel_g_id = None
    if group_options:
        sel_g_id = st.sidebar.selectbox("Vyberte skupinu:", options=list(group_options.keys()), format_func=lambda x: group_options[x])

    if sel_g_id:
        cur_g = groups[sel_g_id]
        st.sidebar.markdown(f"### 🏠 {cur_g['name']} ({sel_g_id})")


        # Rozbalovací členové
        with st.sidebar.expander("👥 Členové skupiny"):
            for m in cur_g.get("members", []):
                st.text(f"• {m}")

        # Rozbalovací habity
        with st.sidebar.expander("📋 Moje habity"):
            my_h_list = [h for h in cur_g.get("habits", []) if isinstance(h, dict) and h.get("owner") == user_id]
            if not my_h_list:
                st.caption("Zatím nemáte žádné habity.")
            for h in my_h_list:
                st.markdown(f"**Habit:** {h['name']}")
                st.markdown(f"*Trest:* {h['punishment']}")
                st.divider()

        st.sidebar.divider()

        # Přidat nový habit (Rozbalovací)
        with st.sidebar.expander("➕ Přidat nový habit"):
            nh_name = st.text_input("Co chceš dělat?", key="nh_n")
            nh_punish = st.text_input("Trest při nesplnění", key="nh_p")
            if st.button("Uložit habit"):
                if nh_name and nh_punish:
                    cur_g.setdefault("habits", []).append({
                        "name": nh_name,
                        "punishment": nh_punish,
                        "owner": user_id
                    })
                    save_db(DB_GROUPS, groups)
                    st.rerun()
                else:
                    st.error("Musíš vyplnit název i trest.")

        # Opuštění skupiny
        if st.sidebar.button("🚪 Opustit tuto skupinu"):
            if user_id in cur_g["members"]:
                cur_g["members"].remove(user_id)
            if sel_g_id in user_data["groups"]:
                user_data["groups"].remove(sel_g_id)
            save_db(DB_GROUPS, groups)
            save_db(DB_USERS, users)
            st.rerun()

    st.sidebar.divider()

    # Vytvořit skupinu (Samostatně)
    with st.sidebar.expander("🏢 Vytvořit novou skupinu"):
        new_g_name = st.text_input("Název nové skupiny", key="ngn")
        if st.button("Založit skupinu"):
            if new_g_name:
                new_id = secrets.token_hex(3).upper()
                groups[new_id] = {"name": new_g_name, "members": [user_id], "habits": []}
                user_data.setdefault("groups", []).append(new_id)
                save_db(DB_GROUPS, groups)
                save_db(DB_USERS, users)
                st.rerun()

    # Připojit se ke skupině (Samostatně)
    with st.sidebar.expander("🔗 Připojit se ke skupině"):
        join_code = st.text_input("Vlož kód skupiny", key="jc")
        if st.button("Vstoupit"):
            if join_code in groups:
                if user_id not in groups[join_code]["members"]:
                    groups[join_code]["members"].append(user_id)
                if join_code not in user_data.get("groups", []):
                    user_data.setdefault("groups", []).append(join_code)
                save_db(DB_GROUPS, groups)
                save_db(DB_USERS, users)
                st.rerun()
            else:
                st.error("Skupina s tímto kódem neexistuje.")

    if st.sidebar.button("🚪 Odhlásit se"):
        del st.session_state.user
        st.rerun()

    # --- HLAVNÍ OBSAH (FEED) ---
    if not sel_g_id:
        st.info("👈 Vyberte skupinu v bočním panelu nebo si vytvořte novou.")
        return

    # Synchronizace úkolů pro vybranou skupinu
    sync_daily_habits(user_id, sel_g_id)
    records = load_db(DB_RECORDS, list)

    st.title(f"Feed: {groups[sel_g_id]['name']}")

    # 1. MOJE RESTY
    st.subheader("📝 Moje dnešní resty")
    my_todo = [r for r in records if r['user_id'] == user_id and r['status'] == 'todo' and r['group_id'] == sel_g_id]

    if not my_todo:
        st.success("Všechno máš pro dnešek hotové! Dobrá práce.")
    else:
        for r in sorted(my_todo, key=lambda x: x['date']):
            # Změna názvosloví: Habit vs Trest
            with st.expander(f"HABIT: {r['habit']} ({r['date']})"):
                st.error(f"⚠️ Trest za nesplnění: {r['punishment']}")
                img_file = st.file_uploader("Nahraj foto důkaz", type=['png', 'jpg', 'jpeg'], key=f"img_{r['id']}")
                comm = st.text_input("Komentář k odevzdání", key=f"c_{r['id']}")
                if st.button("Odeslat ke schválení", key=f"b_{r['id']}"):
                    if img_file:
                        p_name = f"{r['id']}_{img_file.name}"
                        path = os.path.join(UPLOAD_DIR, p_name)
                        with open(path, "wb") as f:
                            f.write(img_file.getbuffer())
                        r['image_path'] = path
                    r['status'] = 'pending'
                    r['comment'] = comm
                    save_db(DB_RECORDS, records)
                    st.rerun()

    st.divider()

    # 2. KE SCHVÁLENÍ OSTATNÍM
    st.subheader("👀 Ke schválení parťákům")
    to_rev = [r for r in records if r['group_id'] == sel_g_id and r['status'] == 'pending' and r['user_id'] != user_id]

    if not to_rev:
        st.caption("Nikdo zatím nic neposlal ke schválení.")
    else:
        for r in to_rev:
            st.warning(f"🔔 {r['user_id']} odevzdal habit: **{r['habit']}**")
            # Jasné zobrazení trestu pro motivaci schvalujícího
            st.info(f"💡 Trest při nesplnění by byl: **{r['punishment']}**")

            if r.get('image_path') and os.path.exists(r['image_path']):
                st.image(r['image_path'], caption=f"Důkaz uživatele {r['user_id']}")

            st.write(f"💬 Komentář: {r['comment']}")
            st.caption(f"Datum splnění: {r['date']}")

            c1, c2 = st.columns(2)
            if c1.button(f"✅ Schválit {r['user_id']}", key=f"ok_{r['id']}"):
                r['status'] = 'approved'
                save_db(DB_RECORDS, records)
                st.rerun()
            if c2.button(f"❌ Zamítnout (Musí splnit trest!)", key=f"ko_{r['id']}"):
                r['status'] = 'todo'
                save_db(DB_RECORDS, records)
                st.rerun()

# --- SPUŠTĚNÍ ---
if 'user' not in st.session_state:
    login_page()
else:
    main_app()
