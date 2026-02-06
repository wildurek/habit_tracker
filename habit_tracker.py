import streamlit as st
import json
import os
from datetime import date

DATA_FILE = "data.json"
HABITS_FILE = "habits.json"
UPLOAD_DIR = "uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_data(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

habits_config = load_data(HABITS_FILE, {})
all_records = load_data(DATA_FILE, [])

def calculate_punishment(record):
    config = habits_config.get(record['habit'], ("Neznámý trest", ""))
    pun_text = config[0]
    return {
        "user": record["user"],
        "habit": f"{pun_text}",
        "date": record["date"],
        "status": "not_done",
        "comment": "",
        "photo_path": None
    }

st.title("Habit Tracker")

current_user = st.sidebar.radio("And who the fuck are you?", ["Kaidan", "Nick"])
partner_user = "Nick" if current_user == "Kaidan" else "Kaidan"

st.sidebar.divider()
st.sidebar.header("Nastavení habitů")
new_habit = st.sidebar.text_input("Nový habit (název asi ne?)")
new_punishment = st.sidebar.text_input("Punishment??")

if st.sidebar.button("Ship it"):
    if new_habit and new_punishment:
        habits_config[new_habit] = (new_punishment, current_user)
        save_data(HABITS_FILE, habits_config)
        st.rerun()

if habits_config:
    habit_to_del = st.sidebar.selectbox("Odebrat habit", list(habits_config.keys()))
    if st.sidebar.button("Get out"):
        del habits_config[habit_to_del]
        save_data(HABITS_FILE, habits_config)
        st.rerun()

today_str = str(date.today())
st.header(f"Dnešní úkoly ({today_str})")

if not habits_config:
    st.warning("Lazy ass nigga")

for habit_name, tup in habits_config.items():
    _, habit_for = tup
    if habit_for == current_user:
        st.subheader(f"Habit: {habit_name}")

        is_already_submitted = False
        for record in all_records:
            if record["user"] == current_user and record["habit"] == habit_name and record["date"] == today_str:
                is_already_submitted = True
                st.info(f"Pro dnešek hotovo. Stav: {record['status']}")
                break

        if not is_already_submitted:
            col1, col2 = st.columns(2)
            with col1:
                uploaded_photo = st.file_uploader(f"Důkaz pro {habit_name}", type=["jpg", "png"], key=f"photo_{habit_name}")
            with col2:
                comment = st.text_input(f"Okomentuj", key=f"text_{habit_name}")

            if st.button(f"Ship {habit_name}", key=f"btn_{habit_name}"):
                if comment:
                    photo_path = None
                    if uploaded_photo is not None:
                        file_extension = uploaded_photo.name.split(".")[-1]
                        file_name = f"{current_user}_{today_str}_{habit_name}.{file_extension}"
                        photo_path = os.path.join(UPLOAD_DIR, file_name)
                        with open(photo_path, "wb") as f:
                            f.write(uploaded_photo.getbuffer())

                    new_record = {
                        "user": current_user,
                        "habit": habit_name,
                        "date": today_str,
                        "status": "pending",
                        "comment": comment,
                        "photo_path": photo_path
                    }
                    all_records.append(new_record)
                    save_data(DATA_FILE, all_records)
                    st.success("Odesláno!")
                    st.rerun()
                else:
                    st.error("Musíš zadat komentář!")

st.divider()
st.header(f"Tresty pro {current_user}a")
for record in all_records:
    if record["user"] == current_user and record["status"] == "not_done":
        st.warning(f"{record['habit']}")
        col1, col2 = st.columns(2)
        with col1:
            uploaded_photo = st.file_uploader(f"Důkaz trestu", type=["jpg", "png"], key=f"p_photo_{record['habit']}_{record['date']}")
        with col2:
            comment = st.text_input(f"Okomentuj splnění", key=f"p_text_{record['habit']}_{record['date']}")

        if st.button(f"Ship it", key=f"p_btn_{record['habit']}_{record['date']}"):
            if comment and uploaded_photo:
                file_extension = uploaded_photo.name.split(".")[-1]
                file_name = f"PUNISH_{current_user}_{record['date']}_{record['habit'][:10]}.{file_extension}"
                photo_path = os.path.join(UPLOAD_DIR, file_name)
                with open(photo_path, "wb") as f:
                    f.write(uploaded_photo.getbuffer())

                record["status"] = "pending"
                record["comment"] = comment
                record["photo_path"] = photo_path
                save_data(DATA_FILE, all_records)
                st.rerun()
            else:
                st.error("Musíš nahrát fotku i komentář!")

st.divider()
st.header(f"Schvalování {partner_user}a")
for record in all_records:
    if record["user"] == partner_user and record["status"] == "pending":
        st.write(f"### Parťák splnil: **{record['habit']}**")
        if record.get("photo_path"):
            st.image(record["photo_path"], use_container_width=True)
        st.info(f"Komentář: {record['comment']}")

        c1, c2 = st.columns(2)
        if c1.button("Schválit", key=f"ok_{record['user']}_{record['habit']}_{record['date']}"):
            record["status"] = "approved"
            save_data(DATA_FILE, all_records)
            st.rerun()

        if c2.button("Zamítnout", key=f"ko_{record['user']}_{record['habit']}_{record['date']}"):
            record["status"] = "rejected"
            punishment = calculate_punishment(record)
            all_records.append(punishment)
            save_data(DATA_FILE, all_records)
            st.rerun()
