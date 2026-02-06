import streamlit as st
import json
import os
from datetime import date

HABITS = ["ScreenTime", "Stretch", "Workout"]
DATA_FILE = "data.json"
UPLOAD_DIR = "uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def calculate_punishment(record):
    puns = {"ScreenTime": "Skoč z okna", "Stretch": "Pull huzz", "Workout": "Vypij moře"}
    if record['habit'] in puns:
        pun = puns[record['habit']]
    else:
        pun = "Trest za trest"
    punishment = {
        "user": record["user"],
        "habit": f"{pun} - trest za {record['habit']}",
        "date": record["date"],
        "status": "not_done",
        "comment": "",
        "photo_path": None
    }
    return punishment

st.title("Habit Tracker")

current_user = st.sidebar.radio("Kdo jsi?", ["Kaidan", "Nick"])
partner_user = "Nick" if current_user == "Kaidan" else "Kaidan"

today_str = str(date.today())
all_records = load_data()

st.header(f"Dnešní úkoly ({today_str})")

for habit_name in HABITS:
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
            comment = st.text_input(f"Okomentuj (splnil, nebo proč nesplnil)", key=f"text_{habit_name}")

        if st.button(f"Odeslat {habit_name}", key=f"btn_{habit_name}"):
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
                save_data(all_records)
                st.success("Odesláno!")
                st.rerun()
            else:
                st.error("Musíte zadat komentář!")


st.divider()
st.header(f"Tresty pro {current_user}a")
for record in all_records:
    if record["user"] == current_user and record["status"] == "not_done":
        st.write(f"{record['habit']}")
        st.write(f"Datum: {record['date']}")

        col1, col2 = st.columns(2)

        with col1:
            uploaded_photo = st.file_uploader(f"Důkaz pro {record['habit']}", type=["jpg", "png"], key=f"p_photo_{record['habit']}")

        with col2:
            comment = st.text_input(f"Okomentuj", key=f"p_text_{record['habit']}")

        if st.button(f"Odeslat {record['habit']}", key=f"p_btn_{record['habit']}"):
            if comment:
                photo_path = None
                if uploaded_photo is not None:
                    file_extension = uploaded_photo.name.split(".")[-1]
                    file_name = f"PUNISH_{current_user}_{today_str}_{record['habit']}.{file_extension}"
                    photo_path = os.path.join(UPLOAD_DIR, file_name)
                    with open(photo_path, "wb") as f:
                        f.write(uploaded_photo.getbuffer())
                    record["status"] = "pending"
                    record["comment"] = comment
                    record["photo_path"] = photo_path
                    save_data(all_records)
                    st.success("Odesláno!")
                    st.rerun()
                else:
                    st.error("Musíte přidat fotku!")
            else:
                st.error("Musíte zadat komentář!")

st.divider()
st.header(f"Schvalování {partner_user}a")

for record in all_records:
    if record["user"] == partner_user and record["status"] == "pending":
        st.write(f"### Parťák splnil: **{record['habit']}**")
        st.write(f"Datum: {record['date']}")

        if record.get("photo_path"):
            st.image(record["photo_path"], caption=f"Důkaz od {partner_user}a", use_container_width=True)

        st.warning(f"Komentář: {record['comment']}")

        c1, c2 = st.columns(2)
        if c1.button("Schválit", key=f"ok_{record['habit']}_{record['date']}"):
            record["status"] = "approved"
            save_data(all_records)
            st.rerun()

        if c2.button("Zamítnout (TREST)", key=f"ko_{record['habit']}_{record['date']}"):
            record["status"] = "rejected"
            punishment = calculate_punishment(record)
            all_records.append(punishment)
            save_data(all_records)
            st.rerun()
