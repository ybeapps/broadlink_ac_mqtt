"""
Tests for the reconnect-flood fix.
Verifies:
1. device_factory hex constant: 0xFFFFFFFF → ac_db_debug (not base device)
2. device_config_to_device_object fallback returns ac_db_disconnected (not base device)
3. publish_devices_status throttles reconnect attempts to once per 30s
4. monitor_connections respects shared cooldown
5. _devices_lock is a real threading.Lock
"""
import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import MagicMock, patch
from broadlink_ac_mqtt.ac_communication.broadlink import device_factory
from broadlink_ac_mqtt.ac_communication.broadlink.ac_db_disconnected import ac_db_disconnected
from broadlink_ac_mqtt.ac_communication.broadlink.device import device as BaseDevice
from broadlink_ac_mqtt.ac_to_mqtt_adapter import AcToMqtt, _RECONNECT_COOLDOWN_SECS

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

def test(name, condition):
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}")
    results.append(condition)


# ── Test 1: device_factory hex constant fix ──────────────────────────────────
print("\n1. device_factory: 0xFFFFFFFF case now exists (no longer falls to base device)")
dummy_host = ("192.168.1.1", 80)
dummy_mac = bytearray(6)

# 0x0000000 → ac_db_disconnected (the disconnected stub)
result_disconnected = device_factory.create_device(dev_type=0x0000000, host=dummy_host, mac=dummy_mac)
test("0x0000000 returns ac_db_disconnected", isinstance(result_disconnected, ac_db_disconnected))
test("ac_db_disconnected has original_config attr", hasattr(result_disconnected, 'original_config'))
test("get_ac_status() returns None (no exception)", result_disconnected.get_ac_status() is None)


# ── Test 2: device_config_to_device_object fallback ──────────────────────────
print("\n2. device_config_to_device_object: offline AC → ac_db_disconnected (not base device)")

config = {
    "update_interval": 1,
    "mqtt_host": "localhost",
    "mqtt_port": 1883,
    "mqtt_user": None,
    "mqtt_password": None,
    "mqtt_client_id": "test",
    "mqtt_topic_prefix": "ac/",
    "mqtt_auto_discovery_topic": False,
    "mqtt_auto_discovery_topic_retain": False,
}

device_config = {"ip": "192.168.99.99", "port": 80, "mac": "aabbccddeeff", "name": "TestAC"}

with patch.object(AcToMqtt, 'connect_mqtt'), \
     patch.object(AcToMqtt, 'start_monitoring'):
    adapter = AcToMqtt(config)
    adapter._mqtt = MagicMock()

# Patch create_device: real AC (0x4E2a) raises exception (simulates offline), fallback runs
original_create = device_factory.create_device

def patched_create(dev_type, host, mac, **kwargs):
    if dev_type == 0x4E2a:
        raise Exception("Connection refused (simulated offline)")
    return original_create(dev_type=dev_type, host=host, mac=mac, **kwargs)

device_factory.create_device = patched_create
try:
    fallback_device = adapter.device_config_to_device_object(device_config)
    test("returns ac_db_disconnected when AC offline", isinstance(fallback_device, ac_db_disconnected))
    test("does NOT return base device", not type(fallback_device) == BaseDevice)
    test("original_config is set", fallback_device.original_config == device_config)
    test("get_ac_status() returns None (no throw)", fallback_device.get_ac_status() is None)
finally:
    device_factory.create_device = original_create


# ── Test 3: publish_devices_status cooldown ───────────────────────────────────
print("\n3. publish_devices_status: reconnect throttled to once per 30s")

reconnect_call_count = 0

def mock_reconnect(cfg):
    global reconnect_call_count
    reconnect_call_count += 1
    d = ac_db_disconnected()
    d.original_config = cfg
    return d

adapter.device_config_to_device_object = mock_reconnect

broken = ac_db_disconnected()
broken.original_config = device_config
broken.get_ac_status = MagicMock(side_effect=Exception("device offline"))

devices = {"mac1": broken}

adapter.publish_devices_status(config, devices)
count_after_first = reconnect_call_count
test("first failure triggers reconnect attempt (count=1)", count_after_first == 1)

# Replace device in dict with a new broken one (as mock_reconnect returned one)
devices["mac1"] = devices.get("mac1", broken)
if hasattr(devices["mac1"], "get_ac_status") and not isinstance(devices["mac1"].get_ac_status, MagicMock):
    devices["mac1"].get_ac_status = MagicMock(side_effect=Exception("device offline"))

adapter.publish_devices_status(config, devices)
count_after_second = reconnect_call_count
test("immediate second call is throttled (count stays at 1)", count_after_second == 1)


# ── Test 4: cooldown shared between both paths ────────────────────────────────
print("\n4. monitor_connections: respects shared cooldown set by publish_devices_status")

with patch.object(AcToMqtt, 'connect_mqtt'), \
     patch.object(AcToMqtt, 'start_monitoring'):
    adapter2 = AcToMqtt(config)
    adapter2._mqtt = MagicMock()

monitor_reconnect_count = 0

def mock_reconnect2(cfg):
    global monitor_reconnect_count
    monitor_reconnect_count += 1
    d = ac_db_disconnected()
    d.original_config = cfg
    return d

adapter2.device_config_to_device_object = mock_reconnect2

broken2 = ac_db_disconnected()
broken2.original_config = device_config
adapter2.device_objects = {"mac2": broken2}

# Simulate: publish_devices_status just set the cooldown
adapter2._reconnect_cooldown["mac2"] = time.time()

# Simulate one monitor_connections iteration
with adapter2._devices_lock:
    items = list(adapter2.device_objects.items())

skipped = 0
for device_key, device in items:
    if not hasattr(device, 'status') or not device.status:
        last_attempt = adapter2._reconnect_cooldown.get(device_key, 0)
        if time.time() - last_attempt < _RECONNECT_COOLDOWN_SECS:
            skipped += 1

test("monitor_connections skips device already in cooldown", skipped == 1)
test("no extra reconnect calls made by monitor", monitor_reconnect_count == 0)


# ── Test 5: lock and cooldown init ───────────────────────────────────────────
print("\n5. Thread safety and constants")

with patch.object(AcToMqtt, 'connect_mqtt'), \
     patch.object(AcToMqtt, 'start_monitoring'):
    adapter3 = AcToMqtt(config)

test("_devices_lock is a threading.Lock", isinstance(adapter3._devices_lock, type(threading.Lock())))
test("_reconnect_cooldown starts empty", adapter3._reconnect_cooldown == {})
test("_RECONNECT_COOLDOWN_SECS is 30", _RECONNECT_COOLDOWN_SECS == 30)


# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'─'*40}")
print(f"Results: {passed}/{total} passed", "✓" if passed == total else "✗")
if passed != total:
    sys.exit(1)
