"""
Smart Home Hub - Streamlit front end
Run with:  streamlit run app.py

This file only draws the interface. All the real logic (devices, hub,
scheduling, notifications, saving) is in the classes of smart_home_devices.py
"""

import os
import tempfile
from datetime import datetime

import streamlit as st

from smart_home_devices import (
    Hub, Light, Fan, AC, Heater, Geyser, DoorLock, Refrigerator, DEVICE_TYPES,
)

st.set_page_config(page_title="Smart Home Hub", page_icon="🏠", layout="wide")


# ----------------------------------------------------------------------
# Setting up the hub (one Hub object is kept in session_state)
# ----------------------------------------------------------------------
def make_demo_hub():
    hub = Hub("My Home")
    hub.add_device(Light("L1", "Ceiling Light", "Living Room"))
    hub.add_device(Fan("F1", "Ceiling Fan", "Bedroom"))
    hub.add_device(AC("A1", "Split AC", "Bedroom"))
    hub.add_device(Heater("H1", "Room Heater", "Study"))
    hub.add_device(Geyser("G1", "Bathroom Geyser", "Bathroom"))
    hub.add_device(DoorLock("D1", "Front Door", "Entrance"))
    hub.add_device(Refrigerator("R1", "Fridge", "Kitchen"))
    return hub


if "hub" not in st.session_state:
    st.session_state.hub = make_demo_hub()
    st.session_state.ver = 0        # changes when devices are added/removed/loaded
    st.session_state.error = None   # last error message to show

hub = st.session_state.hub


def bump():
    """Changing the version gives the widgets fresh keys (avoids stale sliders)."""
    st.session_state.ver += 1


def safe(func, *args):
    """Call a hub/device method; if validation fails, remember the message."""
    try:
        func(*args)
    except (ValueError, KeyError) as e:
        st.session_state.error = str(e)


def apply_value(setter, key):
    """Used by sliders: read the slider value and pass it to the setter."""
    safe(setter, st.session_state[key])


def remove_device(device_id):
    safe(hub.remove_device, device_id)
    bump()


# ----------------------------------------------------------------------
# Sidebar: add device, save / load
# ----------------------------------------------------------------------
st.sidebar.title("🏠 " + hub.name)

st.sidebar.subheader("Add a device")
with st.sidebar.form("add_form", clear_on_submit=True):
    new_type = st.selectbox("Type", list(DEVICE_TYPES.keys()))
    new_id = st.text_input("Device ID (e.g. L2)")
    new_name = st.text_input("Name")
    new_room = st.text_input("Room")
    submitted = st.form_submit_button("Add")

if submitted:
    if not (new_id and new_name and new_room):
        st.session_state.error = "Please fill in ID, name and room"
    else:
        cls = DEVICE_TYPES[new_type]      # class picked from the dictionary
        safe(hub.add_device, cls(new_id.strip(), new_name.strip(), new_room.strip()))
        bump()

st.sidebar.subheader("Save / Load")


def hub_json_bytes():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    hub.save_to_json(path)
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


st.sidebar.download_button("Download state (JSON)", hub_json_bytes(),
                           file_name="home_state.json", mime="application/json")

uploaded = st.sidebar.file_uploader("Load a saved state", type="json")
if uploaded is not None:
    upload_id = f"{uploaded.name}-{uploaded.size}"
    if st.session_state.get("last_upload") != upload_id:
        st.session_state.last_upload = upload_id
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(uploaded.getvalue())
        try:
            hub.load_from_json(path)
            bump()
        except Exception as e:
            st.session_state.error = f"Could not load file: {e}"
        os.remove(path)


# ----------------------------------------------------------------------
# Device cards
# ----------------------------------------------------------------------
def device_controls(dev):
    """Show the right controls for each kind of device."""
    v = st.session_state.ver
    uid = f"{dev.device_id}_{v}"

    # on/off buttons (a DoorLock uses lock/unlock but the call is the same:
    # turn_on()/turn_off() -> polymorphism)
    on_label, off_label = ("Lock", "Unlock") if isinstance(dev, DoorLock) else ("ON", "OFF")
    c1, c2 = st.columns(2)
    c1.button(on_label, key=f"on_{uid}", on_click=safe, args=(dev.turn_on,))
    c2.button(off_label, key=f"off_{uid}", on_click=safe, args=(dev.turn_off,))

    if isinstance(dev, Light):
        key = f"bright_{uid}"
        st.slider("Brightness (%)", 0, 100, dev.get_brightness(), key=key,
                  on_change=apply_value, args=(dev.set_brightness, key))

    elif isinstance(dev, Fan):
        key = f"speed_{uid}"
        st.slider("Speed", dev.MIN_SPEED, dev.MAX_SPEED, dev.get_speed(), key=key,
                  on_change=apply_value, args=(dev.set_speed, key))

    elif isinstance(dev, (AC, Heater, Geyser, Refrigerator)):
        key = f"temp_{uid}"
        st.slider("Temperature (°C)", dev.MIN_TEMP, dev.MAX_TEMP,
                  dev.get_temperature(), key=key,
                  on_change=apply_value, args=(dev.set_temperature, key))

    if isinstance(dev, Refrigerator):
        d1, d2 = st.columns(2)
        d1.button("Open door", key=f"open_{uid}", on_click=safe, args=(dev.open_door,))
        d2.button("Close door", key=f"close_{uid}", on_click=safe, args=(dev.close_door,))


def device_card(dev):
    with st.container(border=True):
        st.markdown(f"**{dev.name}**  \n{dev.room} · `{type(dev).__name__}`")
        st.write(dev.get_status())          # polymorphism: each class has its own text
        device_controls(dev)
        st.button("Remove", key=f"rm_{dev.device_id}_{st.session_state.ver}",
                  on_click=remove_device, args=(dev.device_id,))


# ----------------------------------------------------------------------
# Main page
# ----------------------------------------------------------------------
st.title("Smart Home Hub Controller")

if st.session_state.error:
    st.error(st.session_state.error)
    st.session_state.error = None

tab_dev, tab_sched, tab_notif, tab_oop = st.tabs(
    ["Devices", "Schedules", "Notifications", "OOP concepts"])

# ---- Devices tab ----
with tab_dev:
    top1, top2, top3 = st.columns([1, 1, 2])
    top1.button("Turn all ON", on_click=hub.turn_all_on)
    top2.button("Turn all OFF", on_click=hub.turn_all_off)
    rooms = ["All"] + sorted({d.room for d in hub.devices})
    room_filter = top3.selectbox("Room", rooms, label_visibility="collapsed")
    st.caption("Turn all OFF also unlocks the door, and the fridge refuses to switch off "
               "(it sends a notification instead).")

    shown = [d for d in hub.devices if room_filter in ("All", d.room)]
    if not shown:
        st.info("No devices to show.")
    for i in range(0, len(shown), 3):
        cols = st.columns(3)
        for col, dev in zip(cols, shown[i:i + 3]):
            with col:
                device_card(dev)

# ---- Schedules tab ----
with tab_sched:
    st.subheader("Add a schedule")
    devices = hub.devices
    if devices:
        s1, s2, s3 = st.columns(3)
        sched_dev = s1.selectbox("Device", devices,
                                 format_func=lambda d: f"{d.name} ({d.device_id})")
        sched_action = s2.selectbox("Action", ["on", "off"])
        sched_time = s3.time_input("Time", value=datetime.strptime("23:00", "%H:%M").time())
        if st.button("Add schedule"):
            safe(hub.schedule, sched_dev.device_id, sched_action,
                 sched_time.strftime("%H:%M"))
    else:
        st.info("Add a device first.")

    st.subheader("Current schedules")
    schedules = hub.get_schedules()
    if schedules:
        st.dataframe(schedules, hide_index=True)
    else:
        st.write("No schedules yet.")

    st.subheader("Run schedules")
    st.caption("A web app cannot run in the background, so schedules are checked when "
               "you press the button. You can pick the time to test with.")
    r1, r2 = st.columns([1, 3])
    test_time = r1.time_input("Check at", value=datetime.strptime("23:00", "%H:%M").time())
    if r2.button("Run due schedules"):
        when = datetime.now().replace(hour=test_time.hour, minute=test_time.minute)
        done = hub.run_due_schedules(when)
        if done:
            for line in done:
                st.success(line)
        else:
            st.write("Nothing was due at that time.")

# ---- Notifications tab ----
with tab_notif:
    notes = hub.get_notifications()
    st.button("Clear notifications", on_click=hub.clear_notifications)
    if notes:
        for stamp, text in reversed(notes):
            st.write(f"`{stamp}`  {text}")
    else:
        st.write("No notifications.")
    st.caption("Times are the server's time (cloud servers usually run on UTC).")

# ---- OOP tab ----
with tab_oop:
    st.subheader("Where each OOP concept is used")
    st.table({
        "Concept": ["Abstraction", "Inheritance", "Polymorphism", "Encapsulation"],
        "In the project": [
            "Device is an abstract class (ABC) with abstract get_status()",
            "Light, Fan, AC, Heater, Geyser, DoorLock, Refrigerator extend Device",
            "turn_on()/turn_off()/get_status() behave differently per class "
            "(lock, fridge refusing to turn off, etc.)",
            "Private attributes like __brightness, changed only through "
            "set_brightness() which validates the value",
        ],
    })

    st.subheader("Live polymorphism demo")
    st.caption("Same call, d.get_status(), on every object in the hub:")
    for d in hub.devices:
        st.write(f"`{type(d).__name__}` → {d.get_status()}")

    st.subheader("Encapsulation demo")
    lights = [d for d in hub.devices if isinstance(d, Light)]
    if lights:
        if st.button("Try to read light.__brightness directly"):
            try:
                st.write(lights[0].__brightness)
            except AttributeError as e:
                st.warning(f"AttributeError: {e}")
        st.write("Allowed way: `light.get_brightness()` →", lights[0].get_brightness())
    else:
        st.write("Add a Light to try this demo.")
