"""
Smart Home Device Management System
OOP Lab Project - classes only (GUI can import this module).

OOP concepts used:
  Encapsulation : private/protected attributes, accessed via methods/properties
  Inheritance   : Light, Fan, AC, Heater, Geyser, DoorLock, Refrigerator extend Device
  Polymorphism  : turn_on(), turn_off() and get_status() behave per device type
  Abstraction   : Device is an abstract base class (abc)
"""

from abc import ABC, abstractmethod
from datetime import datetime
import json


# ----------------------------------------------------------------------
# Abstract base class
# ----------------------------------------------------------------------
class Device(ABC):
    """Abstract base class: common data and behaviour of every device."""

    def __init__(self, device_id, name, room):
        self.device_id = device_id
        self.name = name
        self.room = room
        self._is_on = False      # protected: change only via methods
        self._hub = None         # set when the device is added to a Hub

    # ---- read-only access to protected state
    @property
    def is_on(self):
        return self._is_on

    # ---- common behaviour (subclasses may override)
    def turn_on(self):
        self._is_on = True

    def turn_off(self):
        self._is_on = False

    def _notify(self, message):
        """Send an alert to the hub (if the device is connected to one)."""
        if self._hub is not None:
            self._hub.receive_notification(self, message)

    # ---- must be implemented by every subclass
    @abstractmethod
    def get_status(self):
        """Return a human-readable status string."""

    # ---- saving / loading support
    def _extra_state(self):
        """Subclass-specific state for JSON. Override in subclasses."""
        return {}

    def to_dict(self):
        data = {
            "type": type(self).__name__,
            "device_id": self.device_id,
            "name": self.name,
            "room": self.room,
            "is_on": self._is_on,
        }
        data.update(self._extra_state())
        return data

    def _restore_state(self, data):
        """Subclass-specific restore. Override in subclasses."""

    def __str__(self):
        return self.get_status()


# ----------------------------------------------------------------------
# Concrete devices
# ----------------------------------------------------------------------
class Light(Device):
    def __init__(self, device_id, name, room, brightness=100):
        super().__init__(device_id, name, room)
        self.__brightness = 100          # private
        self.set_brightness(brightness)

    def get_brightness(self):
        return self.__brightness

    def set_brightness(self, value):
        if not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError("Brightness must be an integer from 0 to 100")
        self.__brightness = value

    def get_status(self):
        state = "ON" if self._is_on else "OFF"
        return (f"[Light] {self.name} ({self.room}) - {state}, "
                f"brightness {self.__brightness}%")

    def _extra_state(self):
        return {"brightness": self.__brightness}

    def _restore_state(self, data):
        self.set_brightness(data.get("brightness", 100))


class Fan(Device):
    MIN_SPEED, MAX_SPEED = 1, 5

    def __init__(self, device_id, name, room, speed=1):
        super().__init__(device_id, name, room)
        self.__speed = self.MIN_SPEED
        self.set_speed(speed)

    def get_speed(self):
        return self.__speed

    def set_speed(self, value):
        if not isinstance(value, int) or not self.MIN_SPEED <= value <= self.MAX_SPEED:
            raise ValueError(f"Fan speed must be {self.MIN_SPEED}-{self.MAX_SPEED}")
        self.__speed = value

    def get_status(self):
        state = f"ON, speed {self.__speed}" if self._is_on else "OFF"
        return f"[Fan] {self.name} ({self.room}) - {state}"

    def _extra_state(self):
        return {"speed": self.__speed}

    def _restore_state(self, data):
        self.set_speed(data.get("speed", 1))


class AC(Device):
    MIN_TEMP, MAX_TEMP = 16, 30

    def __init__(self, device_id, name, room, temperature=24):
        super().__init__(device_id, name, room)
        self.__temperature = 24
        self.set_temperature(temperature)

    def get_temperature(self):
        return self.__temperature

    def set_temperature(self, value):
        if not self.MIN_TEMP <= value <= self.MAX_TEMP:
            raise ValueError(f"AC temperature must be {self.MIN_TEMP}-{self.MAX_TEMP} C")
        self.__temperature = value

    def get_status(self):
        state = f"ON, set to {self.__temperature} C" if self._is_on else "OFF"
        return f"[AC] {self.name} ({self.room}) - {state}"

    def _extra_state(self):
        return {"temperature": self.__temperature}

    def _restore_state(self, data):
        self.set_temperature(data.get("temperature", 24))


class Heater(Device):
    MIN_TEMP, MAX_TEMP = 15, 35

    def __init__(self, device_id, name, room, temperature=25):
        super().__init__(device_id, name, room)
        self.__temperature = 25
        self.set_temperature(temperature)

    def get_temperature(self):
        return self.__temperature

    def set_temperature(self, value):
        if not self.MIN_TEMP <= value <= self.MAX_TEMP:
            raise ValueError(f"Heater temperature must be {self.MIN_TEMP}-{self.MAX_TEMP} C")
        self.__temperature = value
        if self._is_on and value >= 33:
            self._notify(f"{self.name} is set to a high temperature ({value} C)")

    def get_status(self):
        state = f"ON, set to {self.__temperature} C" if self._is_on else "OFF"
        return f"[Heater] {self.name} ({self.room}) - {state}"

    def _extra_state(self):
        return {"temperature": self.__temperature}

    def _restore_state(self, data):
        self.set_temperature(data.get("temperature", 25))


class DoorLock(Device):
    """turn_on() locks the door, turn_off() unlocks it (polymorphism)."""

    def __init__(self, device_id, name, room):
        super().__init__(device_id, name, room)
        self._is_on = True            # a lock is "on" when locked
        self.__locked = True

    def is_locked(self):
        return self.__locked

    def lock(self):
        self.__locked = True
        self._is_on = True
        self._notify(f"{self.name} locked")

    def unlock(self):
        self.__locked = False
        self._is_on = False
        self._notify(f"{self.name} UNLOCKED")

    def turn_on(self):
        self.lock()

    def turn_off(self):
        self.unlock()

    def get_status(self):
        return (f"[DoorLock] {self.name} ({self.room}) - "
                f"{'LOCKED' if self.__locked else 'UNLOCKED'}")

    def _extra_state(self):
        return {"locked": self.__locked}

    def _restore_state(self, data):
        self.__locked = data.get("locked", True)
        self._is_on = self.__locked


class Refrigerator(Device):
    MIN_TEMP, MAX_TEMP = 1, 8
    ALERT_TEMP = 6

    def __init__(self, device_id, name, room, temperature=4):
        super().__init__(device_id, name, room)
        self._is_on = True            # fridge is normally always running
        self.__temperature = 4
        self.__door_open = False
        self.set_temperature(temperature)

    def get_temperature(self):
        return self.__temperature

    def set_temperature(self, value):
        if not self.MIN_TEMP <= value <= self.MAX_TEMP:
            raise ValueError(f"Fridge temperature must be {self.MIN_TEMP}-{self.MAX_TEMP} C")
        self.__temperature = value
        if value > self.ALERT_TEMP:
            self._notify(f"{self.name}: temperature is high ({value} C)")

    def is_door_open(self):
        return self.__door_open

    def open_door(self):
        self.__door_open = True
        self._notify(f"{self.name}: door is open")

    def close_door(self):
        self.__door_open = False

    def turn_off(self):
        # A fridge should not be switched off casually.
        self._notify(f"{self.name}: turning off a refrigerator is not allowed")

    def get_status(self):
        door = "OPEN" if self.__door_open else "closed"
        return (f"[Refrigerator] {self.name} ({self.room}) - "
                f"{self.__temperature} C, door {door}")

    def _extra_state(self):
        return {"temperature": self.__temperature, "door_open": self.__door_open}

    def _restore_state(self, data):
        self.set_temperature(data.get("temperature", 4))
        self.__door_open = data.get("door_open", False)


class Geyser(Device):
    MIN_TEMP, MAX_TEMP = 30, 75
    HOT_TEMP = 70

    def __init__(self, device_id, name, room, temperature=50):
        super().__init__(device_id, name, room)
        self.__temperature = 50
        self.set_temperature(temperature)

    def get_temperature(self):
        return self.__temperature

    def set_temperature(self, value):
        if not self.MIN_TEMP <= value <= self.MAX_TEMP:
            raise ValueError(f"Geyser temperature must be {self.MIN_TEMP}-{self.MAX_TEMP} C")
        self.__temperature = value
        if self._is_on and value >= self.HOT_TEMP:
            self._notify(f"{self.name} is set to a very high temperature ({value} C)")

    def turn_on(self):
        super().turn_on()
        self._notify(f"{self.name} is heating, remember to switch it off")

    def get_status(self):
        state = f"ON, heating to {self.__temperature} C" if self._is_on else "OFF"
        return f"[Geyser] {self.name} ({self.room}) - {state}"

    def _extra_state(self):
        return {"temperature": self.__temperature}

    def _restore_state(self, data):
        self.set_temperature(data.get("temperature", 50))


# ----------------------------------------------------------------------
# Hub: connects and controls all devices
# ----------------------------------------------------------------------
DEVICE_TYPES = {
    "Light": Light, "Fan": Fan, "AC": AC, "Heater": Heater,
    "Geyser": Geyser, "DoorLock": DoorLock, "Refrigerator": Refrigerator,
}


class Hub:
    def __init__(self, name="Home Hub"):
        self.name = name
        self.__devices = {}        # device_id -> Device
        self.__notifications = []  # list of (timestamp, text)
        self.__schedules = []      # list of dicts

    # ---- device management ------------------------------------------
    @property
    def devices(self):
        return list(self.__devices.values())

    def add_device(self, device):
        if device.device_id in self.__devices:
            raise ValueError(f"Device id '{device.device_id}' already exists")
        device._hub = self
        self.__devices[device.device_id] = device

    def remove_device(self, device_id):
        device = self.get_device(device_id)
        device._hub = None
        del self.__devices[device_id]
        self.__schedules = [s for s in self.__schedules if s["device_id"] != device_id]

    def get_device(self, device_id):
        if device_id not in self.__devices:
            raise KeyError(f"No device with id '{device_id}'")
        return self.__devices[device_id]

    def update_device(self, device_id, name=None, room=None):
        device = self.get_device(device_id)
        if name:
            device.name = name
        if room:
            device.room = room

    # ---- user commands ----------------------------------------------
    def turn_all_on(self):
        for d in self.__devices.values():
            d.turn_on()           # polymorphism

    def turn_all_off(self):
        for d in self.__devices.values():
            d.turn_off()          # polymorphism

    def status_report(self):
        return [d.get_status() for d in self.__devices.values()]

    # ---- notifications ----------------------------------------------
    def receive_notification(self, device, message):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.__notifications.append((stamp, f"{device.name}: {message}"
                                     if device.name not in message else message))

    def get_notifications(self):
        return list(self.__notifications)

    def clear_notifications(self):
        self.__notifications.clear()

    # ---- scheduling -------------------------------------------------
    def schedule(self, device_id, action, time_str):
        """action: 'on' or 'off'; time_str: 'HH:MM' (24-hour)."""
        self.get_device(device_id)
        if action not in ("on", "off"):
            raise ValueError("Action must be 'on' or 'off'")
        datetime.strptime(time_str, "%H:%M")      # validates the format
        self.__schedules.append({"device_id": device_id, "action": action,
                                 "time": time_str, "last_run": None})

    def get_schedules(self):
        return [dict(s) for s in self.__schedules]

    def run_due_schedules(self, now=None):
        """Run schedules whose time matches 'now' (once per day each)."""
        now = now or datetime.now()
        current, today = now.strftime("%H:%M"), now.strftime("%Y-%m-%d")
        executed = []
        for s in self.__schedules:
            if s["time"] == current and s["last_run"] != today:
                device = self.__devices.get(s["device_id"])
                if device is not None:
                    device.turn_on() if s["action"] == "on" else device.turn_off()
                    executed.append(f"{device.name} -> {s['action']} at {s['time']}")
                s["last_run"] = today
        return executed

    # ---- saving / loading -------------------------------------------
    def save_to_json(self, filename):
        data = {
            "name": self.name,
            "devices": [d.to_dict() for d in self.__devices.values()],
            "schedules": self.__schedules,
        }
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_json(self, filename):
        with open(filename) as f:
            data = json.load(f)
        self.name = data.get("name", self.name)
        self.__devices.clear()
        for d in data.get("devices", []):
            cls = DEVICE_TYPES[d["type"]]
            device = cls(d["device_id"], d["name"], d["room"])
            device._restore_state(d)
            device._is_on = d.get("is_on", device._is_on)
            self.add_device(device)
        self.__schedules = data.get("schedules", [])


# ----------------------------------------------------------------------
# Terminal demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    hub = Hub("My Home")
    hub.add_device(Light("L1", "Ceiling Light", "Living Room"))
    hub.add_device(Fan("F1", "Ceiling Fan", "Bedroom"))
    hub.add_device(AC("A1", "Split AC", "Bedroom"))
    hub.add_device(Heater("H1", "Room Heater", "Study"))
    hub.add_device(DoorLock("D1", "Front Door", "Entrance"))
    hub.add_device(Refrigerator("R1", "Fridge", "Kitchen"))

    print("--- Initial status ---")
    for line in hub.status_report():
        print(line)

    print("\n--- User commands ---")
    hub.get_device("L1").turn_on()
    hub.get_device("L1").set_brightness(60)
    hub.get_device("A1").turn_on()
    hub.get_device("A1").set_temperature(22)
    hub.get_device("D1").unlock()
    hub.get_device("R1").open_door()
    hub.get_device("H1").turn_on()
    hub.get_device("H1").set_temperature(34)

    print("\n--- Turn everything on ---\n")
    hub.turn_all_on()
    for line in hub.status_report():
        print(line)

    print("\n--- Validation ---")
    try:
        hub.get_device("L1").set_brightness(150)
    except ValueError as e:
        print("Error:", e)

    print("\n--- Scheduling ---")
    hub.schedule("F1", "off", "23:00")
    run_time = datetime.now().replace(hour=23, minute=0)
    print("Executed:", hub.run_due_schedules(run_time))

    print("\n--- Notifications ---")
    for stamp, text in hub.get_notifications():
        print(stamp, "|", text)

    print("\n--- Save / load JSON ---")
    hub.save_to_json("home_state.json")
    hub2 = Hub()
    hub2.load_from_json("home_state.json")
    print(f"Loaded {len(hub2.devices)} devices from home_state.json")
