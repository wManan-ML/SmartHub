"""
Smart Home Hub - Streamlit front end
Run with:  streamlit run app.py

This file only draws the interface. All the real logic (devices, hub,
scheduling, notifications, saving) is in the classes of smart_home_devices.py
"""

import html
import os
import tempfile
from datetime import datetime

import streamlit as st

from smart_home_devices import (
    Hub, Light, Fan, AC, Heater, Geyser, DoorLock, Refrigerator, DEVICE_TYPES,
)

st.set_page_config(page_title="Smart Home Hub", page_icon="🏠", layout="wide")

# the hub is saved to this file after every change (the "backend")
STATE_FILE = "home_state.json"

# picture (emoji) and colour for every kind of device
THEME = {
    "Light": ("💡", "#E0A800"),
    "Fan": ("🌀", "#2A8BD1"),
    "AC": ("❄️", "#1596A8"),
    "Heater": ("🔥", "#E2542B"),
    "Geyser": ("🚿", "#C93A7B"),
    "DoorLock": ("🔒", "#6A4FC4"),
    "Refrigerator": ("🧊", "#2E9E55"),
}
DEFAULT_THEME = ("🔌", "#888888")


def theme_of(dev):
    return THEME.get(type(dev).__name__, DEFAULT_THEME)


# ----------------------------------------------------------------------
# The hub: created once on the server and shared by every visitor
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


def save_hub(hub):
    try:
        hub.save_to_json(STATE_FILE)
    except OSError:
        pass        # if the server does not let us write, the app still works


@st.cache_resource
def get_hub():
    # if a saved file exists, load the devices from it
    if os.path.exists(STATE_FILE):
        try:
            hub = Hub()
            hub.load_from_json(STATE_FILE)
            return hub
        except Exception:
            pass    # file is broken, so start again with the demo devices
    hub = make_demo_hub()
    save_hub(hub)
    return hub


hub = get_hub()

if "error" not in st.session_state:
    st.session_state.error = None   # last error message to show


def safe(func, *args):
    """Call a hub/device method; if validation fails, remember the message."""
    try:
        func(*args)
    except (ValueError, KeyError) as e:
        st.session_state.error = str(e)


# ----------------------------------------------------------------------
# Sidebar: add device, backup
# ----------------------------------------------------------------------
st.sidebar.title("🏠 " + hub.name)

st.sidebar.subheader("Add a device")
with st.sidebar.form("add_form", clear_on_submit=True):
    new_type = st.selectbox("Type", list(DEVICE_TYPES.keys()),
                            format_func=lambda t: f"{THEME.get(t, DEFAULT_THEME)[0]} {t}")
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

st.sidebar.subheader("Backup")
st.sidebar.caption("Changes are saved on the server automatically. "
                   "You can also keep your own copy.")


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
        except Exception as e:
            st.session_state.error = f"Could not load file: {e}"
        os.remove(path)


# ----------------------------------------------------------------------
# Device cards
# ----------------------------------------------------------------------
def build_css(devices):
    """One coloured square per device (darker when ON, faded when OFF)."""
    css = "@keyframes spin { to { transform: rotate(360deg); } } "
    css += ".spin { animation: spin 1.2s linear infinite; } "
    for n, dev in enumerate(devices):
        accent = theme_of(dev)[1]
        if dev.is_on:
            bg, border = "40", accent
        else:
            bg, border = "14", accent + "55"
        css += (f".st-key-card_{n} {{ background: {accent}{bg}; "
                f"border: 2px solid {border}; border-radius: 14px; "
                f"padding: 14px 16px; }} ")
    return "<style>" + css + "</style>"


def card_header(dev):
    """Picture + name + room. The picture goes grey when the device is off."""
    emoji = theme_of(dev)[0]
    if isinstance(dev, DoorLock) and not dev.is_locked():
        emoji = "🔓"
    style, cls = "font-size:40px; line-height:1;", ""
    if not dev.is_on:
        style += " filter: grayscale(1); opacity: 0.5;"
    elif isinstance(dev, Fan):
        cls = "spin"                 # fan icon rotates while it is on
    name, room = html.escape(dev.name), html.escape(dev.room)
    st.markdown(
        f"<div style='display:flex; align-items:center; gap:12px;'>"
        f"<div class='{cls}' style='{style}'>{emoji}</div>"
        f"<div><b>{name}</b><br>"
        f"<span style='opacity:0.7'>{room} · {type(dev).__name__}</span></div></div>",
        unsafe_allow_html=True)


def setting_slider(label, low, high, current, setter, key):
    """A slider for one setting. If the person moves it, apply it to the device."""
    # the current value is part of the key, so the slider always shows
    # what the device really has
    value = st.slider(label, low, high, current, key=f"{key}_{current}")
    if value != current:
        safe(setter, value)
        st.rerun()


def device_controls(dev):
    """Show the right controls for each kind of device."""
    uid = dev.device_id

    # on/off buttons (a DoorLock uses lock/unlock but the call is the same:
    # turn_on()/turn_off() -> polymorphism)
    on_label, off_label = ("Lock", "Unlock") if isinstance(dev, DoorLock) else ("ON", "OFF")
    c1, c2 = st.columns(2)
    if c1.button(on_label, key=f"on_{uid}"):
        safe(dev.turn_on)
        st.rerun()
    if c2.button(off_label, key=f"off_{uid}"):
        safe(dev.turn_off)
        st.rerun()

    # settings (speed, temperature...) are only shown while the device is ON
    if dev.is_on:
        if isinstance(dev, Light):
            setting_slider("Brightness (%)", 0, 100, dev.get_brightness(),
                           dev.set_brightness, f"bright_{uid}")
        elif isinstance(dev, Fan):
            setting_slider("Speed", dev.MIN_SPEED, dev.MAX_SPEED, dev.get_speed(),
                           dev.set_speed, f"speed_{uid}")
        elif isinstance(dev, (AC, Heater, Geyser, Refrigerator)):
            setting_slider("Temperature (°C)", dev.MIN_TEMP, dev.MAX_TEMP,
                           dev.get_temperature(), dev.set_temperature, f"temp_{uid}")

    if isinstance(dev, Refrigerator):
        d1, d2 = st.columns(2)
        if d1.button("Open door", key=f"open_{uid}"):
            safe(dev.open_door)
            st.rerun()
        if d2.button("Close door", key=f"close_{uid}"):
            safe(dev.close_door)
            st.rerun()


def device_card(dev, n):
    with st.container(key=f"card_{n}"):
        card_header(dev)
        st.caption(dev.get_status())        # polymorphism: each class has its own text
        device_controls(dev)
        if st.button("Remove", key=f"rm_{dev.device_id}"):
            safe(hub.remove_device, dev.device_id)
            st.rerun()


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
    if top1.button("Turn all ON"):
        hub.turn_all_on()
        st.rerun()
    if top2.button("Turn all OFF"):
        hub.turn_all_off()
        st.rerun()
    rooms = ["All"] + sorted({d.room for d in hub.devices})
    room_filter = top3.selectbox("Room", rooms, label_visibility="collapsed")
    st.caption("Turn all OFF also unlocks the door, and the fridge refuses to switch off "
               "(it sends a notification instead).")

    shown = [d for d in hub.devices if room_filter in ("All", d.room)]
    st.markdown(build_css(shown), unsafe_allow_html=True)
    if not shown:
        st.info("No devices to show.")
    for i in range(0, len(shown), 3):
        cols = st.columns(3)
        for j, dev in enumerate(shown[i:i + 3]):
            with cols[j]:
                device_card(dev, i + j)

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
            st.rerun()
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
    if st.button("Clear notifications"):
        hub.clear_notifications()
        st.rerun()
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
            "(lock, fridge refusing to turn off, etc.). Saving also works this way: "
            "each class overrides _extra_state() to save its own data",
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


# save everything to the file at the end of every run
save_hub(hub)
