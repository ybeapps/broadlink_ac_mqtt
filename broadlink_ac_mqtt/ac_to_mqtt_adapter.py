#!/usr/bin/python
import json
import logging
import os
import sys
import time
import traceback

import paho.mqtt.client as mqtt
import yaml

import broadlink_ac_mqtt.ac_communication.broadlink.discovery
import broadlink_ac_mqtt.ac_communication.broadlink.version
from broadlink_ac_mqtt.ac_communication.broadlink import device_factory
from broadlink_ac_mqtt.ac_communication.broadlink.ac_db_disconnected import ac_db_disconnected

sys.path.insert(1, os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ac_communication', 'broadlink'))

logger = logging.getLogger(__name__)


class AcToMqtt:
    previous_status = {}
    last_update = {}

    def __init__(self, config):
        self.device_objects = None
        self.config = config
        self._mqtt: mqtt.Client = None

    def test(self, config):

        for device in config['devices']:
            device_bla = device_factory.create_device(dev_type=0xFFFFFFF,
                                                      host=(device['ip'], device['port']),
                                                      mac=bytearray.fromhex(device['mac']),
                                                      name=device['name'])
            status = device_bla.set_temperature(32)

    # print status

    def discover(self):

        # Go discovery
        discovered_devices = broadlink_ac_mqtt.ac_communication.broadlink.discovery.discover(timeout=5,
                                                                                             bind_to_ip=self.config[
                                                                                                 'bind_to_ip'])
        devices = {}

        if discovered_devices == None:
            error_msg = "No Devices Found, make sure you on the same network segment"
            logger.debug(error_msg)

            # print "nothing found"
            sys.exit()

        # Make sure correct device id
        for device in discovered_devices:
            if device.devtype == 0x4E2a:
                devices[device.status['macaddress']] = device

        return devices

    def make_device_objects(self, device_list=None):
        device_objects = {}

        if device_list == [] or device_list == None:
            error_msg = " Cannot make device objects, empty list given"
            logger.error(error_msg)
            sys.exit()

        for device in device_list:
            new_device = self.device_config_to_device_object(device)
            device_objects[device['mac']] = new_device

        return device_objects

    def device_config_to_device_object(self, device_config):
        try:
            new_device = device_factory.create_device(dev_type=0x4E2a,
                                                      host=(device_config['ip'], device_config['port']),
                                                      mac=bytearray.fromhex(device_config['mac']),
                                                      name=device_config['name'],
                                                      update_interval=self.config['update_interval'])
        except Exception as e:
            logger.error(f"Failed to create device object from config: {device_config}")
            new_device = None

        if not new_device:
            new_device = device_factory.create_device(dev_type=0xFFFFFFFF,
                                                      host=(device_config['ip'], device_config['port']),
                                                      mac=bytearray.fromhex(device_config['mac']),
                                                      name=device_config['name'],
                                                      update_interval=self.config['update_interval'])

        new_device.original_config = device_config

        return new_device

    def disconnect_mqtt(self):
        try:
            self._mqtt.disconnect()
        except:
            ""

    def publish_devices_status(self, config, devices, reconnect_if_needed: bool):
        self.device_objects = devices
        self.config = config

        # If there are no devices so throw error
        if devices == [] or devices == None:
            print("No devices defined")
            logger.error("No Devices defined, either enable discovery or add them to config")
            return
        else:
            logger.debug(f"Following devices configured {repr(devices)}")

        # we are alive # Update PID file
        try:

            for key in devices:

                device = devices[key]
                # Just check status on every update interval
                if key in self.last_update:
                    logger.debug(f"Checking {key} for timeout")
                    if (self.last_update[key] + self.config["update_interval"]) > time.time():
                        logger.debug(
                            f"Timeout {self.config['update_interval']} not done, so lets wait a bit : "
                            f"{self.last_update[key] + self.config['update_interval']} : {time.time()}")
                        time.sleep(0.5)
                        continue
                    else:
                        ""
                # print "timeout done"

                if reconnect_if_needed:
                    if isinstance(device, ac_db_disconnected):
                        logger.info(f"Device {key} is disconnected, trying to reconnect")
                        device = self.device_config_to_device_object(device.original_config)
                        devices[key] = device

                # Get the status, the global update interval is used as well to reduce requests to aircons as they slow

                status = None
                try:
                    status = device.get_ac_status()
                except Exception as e:
                    logger.warning(f"Device {key} - failed to retrieve status. considering as disconnected")
                    device = self.device_config_to_device_object(device.original_config)
                    devices[key] = device
                    status = None

                # print status
                if status:
                    # Update last time checked
                    self.last_update[key] = time.time()
                    self.publish_mqtt_info(status)

                else:
                    logger.debug("No status")

        except Exception as e:
            logger.critical(e)
            logger.debug(traceback.format_exc())
        # Something went wrong.....

        return 1

    def dump_homeassistant_config_from_devices(self, devices):

        if devices == {}:
            print("No devices defined")
            sys.exit()

        devices_array = self.make_devices_array_from_devices(devices)
        if devices_array == {}:
            print("something went wrong, no devices found")
            sys.exit()

        print("**************** Start copy below ****************")
        a = []
        for key in devices_array:
            # Echo
            device = devices_array[key]
            device['platform'] = 'mqtt'
            a.append(device)
        print(yaml.dump({'climate': a}))
        print("**************** Stop copy above ****************")

    def make_devices_array_from_devices(self, devices):

        devices_array = {}

        for device in devices.values():
            # topic = self.config["mqtt_auto_discovery_topic"]+"/climate/"+device.status["macaddress"]+"/config"
            name = ""
            if not device.name:
                name = device.status["macaddress"]
            else:
                name = device.name.encode('ascii', 'ignore')

            device_array = {
                "name": str(name.decode("utf-8"))
                , "power_command_topic": self.config["mqtt_topic_prefix"] + device.status["macaddress"] + "/power/set"
                , "mode_command_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/mode_homeassistant/set"
                , "temperature_command_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/temp/set"
                , "fan_mode_command_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/fanspeed_homeassistant/set"
                , "swing_mode_command_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/fixation_v/set"
                , "action_topic": self.config["mqtt_topic_prefix"] + device.status["macaddress"] + "/homeassistant/set"
                # Read values
                , "current_temperature_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/ambient_temp/value"
                , "mode_state_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/mode_homeassistant/value"
                , "temperature_state_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/temp/value"
                , "fan_mode_state_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/fanspeed_homeassistant/value"
                , "swing_mode_state_topic": self.config["mqtt_topic_prefix"] + device.status[
                    "macaddress"] + "/fixation_v/value"
                , "fan_modes": ["Auto", "Low", "Medium", "High", "Turbo", "Mute"]
                , "modes": ["off", "cool", "heat", "fan_only", "dry"]
                , "swing_modes": ["TOP", "MIDDLE1", "MIDDLE2", "MIDDLE3", "BOTTOM", "SWING", "AUTO"]
                , "max_temp": 32.0
                , "min_temp": 16.0
                , "precision": 0.5
                , "temp_step": 0.5  # @Anonym-tsk
                , "unique_id": device.status["macaddress"]
                , "device": {"ids": device.status["macaddress"], "name": str(name.decode("utf-8")), "model": 'Aircon',
                             "mf": "Broadlink", "sw": broadlink_ac_mqtt.ac_communication.broadlink.version.version}
                , "pl_avail": "online"
                , "pl_not_avail": "offline"
                , "availability_topic": self.config["mqtt_topic_prefix"] + "LWT"
            }

            devices_array[device.status["macaddress"]] = device_array

        return devices_array

    def publish_mqtt_auto_discovery(self, devices):
        if devices == [] or devices == None:
            print("No devices defined")
            logger.error("No Devices defined, either enable discovery or add them to config")
            sys.exit()

        # Make an array
        devices_array = self.make_devices_array_from_devices(devices)
        if devices_array == {}:
            print("something went wrong, no devices found")
            sys.exit()

        # If retain is set for MQTT, then retain it
        if (self.config["mqtt_auto_discovery_topic_retain"]):
            retain = self.config["mqtt_auto_discovery_topic_retain"]

        else:
            retain = False

        logger.debug("HA config Retain set to: " + str(retain))

        # Loop da loop all devices and publish discovery settings
        for key in devices_array:
            device = devices_array[key]
            topic = self.config["mqtt_auto_discovery_topic"] + "/climate/" + key + "/config"
            # Publish
            self._publish(topic, json.dumps(device), retain=retain)

    def publish_mqtt_info(self, status, force_update=False):
        # If auto discovery is used, then always update
        if not force_update:
            force_update = True if "mqtt_auto_discovery_topic" in self.config and self.config[
                "mqtt_auto_discovery_topic"] else False

        logger.debug("Force update is: " + str(force_update))

        # Publish all values in status
        for key in status:
            # Make sure it's a string
            value = status[key]

            # check if device already in previous_status
            if not force_update and status['macaddress'] in self.previous_status:
                # Check if key in state
                if key in self.previous_status[status['macaddress']]:
                    # If the values are same, skip it to make mqtt less chatty #17

                    if self.previous_status[status['macaddress']][key] == value:
                        # print ("value same key:%s, value:%s vs : %s" %  (key,value,self.previous_status[status['macaddress']][key]))
                        continue
                    else:
                        ""
            # print ("value NOT Same key:%s, value:%s vs : %s" %  (key,value,self.previous_status[status['macaddress']][key]))

            pubResult = self._publish(self.config["mqtt_topic_prefix"] + status['macaddress'] + '/' + key + '/value',
                                      value)

            if pubResult != None:
                logger.warning(f'Publishing Result: "{mqtt.error_string(pubResult)}"')
                if pubResult == mqtt.MQTT_ERR_NO_CONN:
                    self.connect_mqtt()

                break

        # Set previous to current
        self.previous_status[status['macaddress']] = status

        return

    # self._publish(binascii.hexlify(status['macaddress'])+'/'+ 'temp/value',status['temp']);

    def _publish(self, topic, value, retain=False, qos=0):
        payload = value
        logger.debug(f'publishing on topic "{topic}", data "{payload}"')
        pubResult = self._mqtt.publish(topic, payload=payload, qos=qos, retain=retain)

        # If there is an error, then debug log and return not None
        if pubResult[0] != 0:
            logger.debug(f'Publishing Result: "{mqtt.error_string(pubResult[0])}"')
            return pubResult[0]

    def connect_mqtt(self):
        # Setup client
        self._mqtt = mqtt.Client(client_id=self.config["mqtt_client_id"], clean_session=True, userdata=None)

        # Set last will and testament
        self._mqtt.will_set(self.config["mqtt_topic_prefix"] + "LWT", "offline", True)

        # Auth
        if self.config["mqtt_user"] and self.config["mqtt_password"]:
            self._mqtt.username_pw_set(self.config["mqtt_user"], self.config["mqtt_password"])

        # Setup callbacks
        self._mqtt.on_connect = self._on_mqtt_connect
        self._mqtt.on_message = self._on_mqtt_message
        self._mqtt.on_log = self._on_mqtt_log
        self._mqtt.on_subscribed = self._mqtt_on_subscribe

        # Connect
        logger.debug(
            f"Connecting to MQTT: {self.config['mqtt_host']} with client ID = {self.config['mqtt_client_id']}")
        self._mqtt.connect(self.config["mqtt_host"], port=self.config["mqtt_port"], keepalive=60, bind_address="")

        # Start
        self._mqtt.loop_start()  # creates new thread and runs Mqtt.loop_forever() in it.

    def _on_mqtt_log(self, client, userdata, level, buf):

        if level == mqtt.MQTT_LOG_ERR:
            logger.debug(f"Mqtt log: {buf}")

    def _mqtt_on_subscribe(self, client, userdata, mid, granted_qos):
        logger.debug("Mqtt Subscribed")

    def _on_mqtt_message(self, client, userdata, msg):

        try:
            logger.debug(
                f'Mqtt Message Received! Userdata: {userdata}, Message {msg.topic + " " + str(msg.payload)}')
            # Function is second last .. decode to str #43
            function = str(msg.topic.split('/')[-2])
            address = msg.topic.split('/')[-3]
            # Make sure its proper STR .. python3  #43 .. very
            address = address.encode('ascii', 'ignore').decode("utf-8")
            # 43 decode to force to str
            value = str(msg.payload.decode("ascii"))
            logger.debug(f'Mqtt decoded --> Function: {function}, Address: {address}, value: {value}')

        except Exception as e:
            logger.critical(e)
            return

        # Process received
        # Probably need to exit here as well if command not send, but should exit on status update
        # above .. grr, hate stupid python
        if function == "temp":
            try:
                if self.device_objects.get(address):
                    status = self.device_objects[address].set_temperature(float(value))

                    if status:
                        self.publish_mqtt_info(status)
                else:
                    logger.debug(f"Device not on list of devices {address}, type: {type(address)}")
                    return
            except Exception as e:
                logger.critical(e)
                return

        elif function == "power":
            if value.lower() == "on":
                status = self.device_objects[address].switch_on()
                if status:
                    self.publish_mqtt_info(status)
            elif value.lower() == "off":
                status = self.device_objects[address].switch_off()
                if status:
                    self.publish_mqtt_info(status)
            else:
                logger.debug("Switch has invalid value, values is on/off received %s", value)
                return

        elif function == "mode":

            status = self.device_objects[address].set_mode(value)
            if status:
                self.publish_mqtt_info(status)

            else:
                logger.debug("Mode has invalid value %s", value)
                return

        elif function == "fanspeed":
            if value.lower() == "turbo":
                status = self.device_objects[address].set_turbo("ON")

            # status = self.device_objects[address].set_mute("OFF")
            elif value.lower() == "mute":
                status = self.device_objects[address].set_mute("ON")

            else:
                # status = self.device_objects[address].set_mute("ON")
                # status = self.device_objects[address].set_turbo("OFF")
                status = self.device_objects[address].set_fanspeed(value)

            if status:
                self.publish_mqtt_info(status)

            else:
                logger.debug("Fanspeed has invalid value %s", value)
                return

        elif function == "fanspeed_homeassistant":
            if value.lower() == "turbo":
                status = self.device_objects[address].set_turbo("ON")

            # status = self.device_objects[address].set_mute("OFF")
            elif value.lower() == "mute":
                status = self.device_objects[address].set_mute("ON")

            else:
                # status = self.device_objects[address].set_mute("ON")
                # status = self.device_objects[address].set_turbo("OFF")
                status = self.device_objects[address].set_fanspeed(value)

            if status:
                self.publish_mqtt_info(status)

            else:
                logger.debug("Fanspeed_homeassistant has invalid value %s", value)
                return

        elif function == "mode_homekit":

            status = self.device_objects[address].set_homekit_mode(value)
            if status:
                self.publish_mqtt_info(status)

            else:
                logger.debug("Mode_homekit has invalid value %s", value)
                return
        elif function == "mode_homeassistant":

            status = self.device_objects[address].set_homeassistant_mode(value)
            if status:
                self.publish_mqtt_info(status)

            else:
                logger.debug("Mode_homeassistant has invalid value %s", value)
                return
        elif function == "state":

            if value == "refresh":
                logger.debug("Refreshing states")
                status = self.device_objects[address].get_ac_status()
            else:
                logger.debug(f"Command not valid: {value}")
                return

            if status:
                self.publish_mqtt_info(status, force_update=True)
            else:
                logger.debug("Unable to refresh")
                return
            return
        elif function == "fixation_v":
            try:
                if self.device_objects.get(address):
                    status = self.device_objects[address].set_fixation_v(value)

                    if status:
                        self.publish_mqtt_info(status)
                else:
                    logger.debug(f"Device not on list of devices {address}, type: {type(address)}")
                    return
            except Exception as e:
                logger.critical(e)
                return
        elif function == "fixation_h":
            try:
                if self.device_objects.get(address):
                    status = self.device_objects[address].set_fixation_h(value)
                    if status:
                        self.publish_mqtt_info(status)
                else:
                    logger.debug(f"Device not on list of devices {address}, type: {type(address)}")
                    return
            except Exception as e:
                logger.critical(e)
                return
        elif function == "display":
            try:
                if self.device_objects.get(address):
                    status = self.device_objects[address].set_display(value)
                    if status:
                        self.publish_mqtt_info(status)
                else:
                    logger.debug(f"Device not on list of devices {address}, type: {type(address)}")
                    return
            except Exception as e:
                logger.critical(e)
                return
        elif function == "mildew":
            try:
                if self.device_objects.get(address):
                    status = self.device_objects[address].set_mildew(value)
                    if status:
                        self.publish_mqtt_info(status)
                else:
                    logger.debug(f"Device not on list of devices {address}, type: {type(address)}")
                    return
            except Exception as e:
                logger.critical(e)
                return
        elif function == "clean":
            try:
                if self.device_objects.get(address):
                    status = self.device_objects[address].set_clean(value)
                    if status:
                        self.publish_mqtt_info(status)
                else:
                    logger.debug(f"Device not on list of devices {address}, type: {type(address)}")
                    return
            except Exception as e:
                logger.critical(e)
                return
        elif function == "health":
            try:
                if self.device_objects.get(address):
                    status = self.device_objects[address].set_health(value)
                    if status:
                        self.publish_mqtt_info(status)
                else:
                    logger.debug(f"Device not on list of devices {address}, type: {type(address)}")
                    return
            except Exception as e:
                logger.critical(e)
                return
        elif function == "sleep":
            try:
                if self.device_objects.get(address):
                    status = self.device_objects[address].set_sleep(value)
                    if status:
                        self.publish_mqtt_info(status)
                else:
                    logger.debug(f"Device not on list of devices {address}, type: {type(address)}")
                    return
            except Exception as e:
                logger.critical(e)
                return
        else:
            logger.debug("No function match")
            return

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """
        RC definition:
        0: Connection successful
        1: Connection refused - incorrect protocol version
        2: Connection refused - invalid client identifier
        3: Connection refused - server unavailable
        4: Connection refused - bad username or password
        5: Connection refused - not authorised
        6-255: Currently unused.
        """

        logger.debug(f'Mqtt connected! client={client}, userdata={userdata}, flags={flags}, rc={rc}')
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        sub_topic = self.config["mqtt_topic_prefix"] + "+/+/set"
        client.subscribe(sub_topic)
        logger.debug(f'Listing on {sub_topic} for messages')

        # LWT
        self._publish(self.config["mqtt_topic_prefix"] + 'LWT', 'online', retain=True)
