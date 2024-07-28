#!/usr/bin/python
# -*- coding: utf8 -*-

import struct
import time

from broadlink_ac_mqtt.ac_communication.broadlink.device import device


class ac_db(device):
    import logging

    type = "ac_db"

    class STATIC:
        ##Static stuff
        class FIXATION:
            class VERTICAL:
                # STOP= 0b00000000
                TOP = 0b00000001
                MIDDLE1 = 0b00000010
                MIDDLE2 = 0b00000011
                MIDDLE3 = 0b00000100
                BOTTOM = 0b00000101
                SWING = 0b00000110
                AUTO = 0b00000111

            class HORIZONTAL:  ##Don't think this really works for all devices.
                LEFT_FIX = 2
                LEFT_FLAP = 1
                LEFT_RIGHT_FIX = 7
                LEFT_RIGHT_FLAP = 0
                RIGHT_FIX = 6
                RIGHT_FLAP = 5
                ON = 0
                OFF = 1

        class FAN:
            LOW = 0b00000011
            MEDIUM = 0b00000010
            HIGH = 0b00000001
            AUTO = 0b00000101
            NONE = 0b00000000

        class MODE:
            COOLING = 0b00000001
            DRY = 0b00000010
            HEATING = 0b00000100
            AUTO = 0b00000000
            FAN = 0b00000110

        class ONOFF:
            OFF = 0
            ON = 1

    def __init__(self, host, mac, name=None, cloud=None, debug=False, update_interval=0, devtype=None, bind_to_ip=None):

        device.__init__(self, host, mac, name=name, cloud=cloud, devtype=devtype, update_interval=update_interval,
                        bind_to_ip=bind_to_ip)

        devtype = devtype
        self.status = {}
        self.original_config = None
        self.logger = self.logging.getLogger(__name__)

        self.update_interval = update_interval

        ##Set default values
        # mac = mac[::-1]

        self.set_default_values()
        self.status['macaddress'] = ''.join(format(x, '02x') for x in mac)
        self.status['hostip'] = host
        self.status['name'] = name
        self.status['lastupdate'] = 0

        self.logging.basicConfig(level=(self.logging.DEBUG if debug else self.logging.INFO))
        self.logger.debug("Debugging Enabled")

        ##Populate array with latest data
        self.logger.debug("Authenticating")
        if self.auth() == False:
            self.logger.critical(f"Authentication Failed to AC: {name} ({host}). skipping")
            return None

        self.logger.info(f"Authenticated to AC: {name} ({host}).")
        self.logger.debug("Getting current details in init")

        ##Get the current details
        self.get_ac_status(force_update=True)

    def get_ac_status(self, force_update=False):
        # Check if the status is up-to-date to reduce timeout issues. Can be overwritten by force_update
        self.logger.debug(f"Last update was: {self.status['lastupdate']}")

        if (force_update == False and (self.status['lastupdate'] + self.update_interval) > time.time()):
            return self.make_nice_status(self.status)

        # Get AC info(also populates the current temp)
        self.logger.debug("Getting AC Info")
        self.get_ac_info()
        self.logger.debug("AC Info Retrieved")
        # Get the current status ... get_ac_states does make_nice_status in return.
        self.logger.debug("Getting AC States")
        status = self.get_ac_states(True)
        self.logger.debug("AC States retrieved")
        return status

    def set_default_values(self):

        self.status['temp'] = float(19)
        self.status['fixation_v'] = self.STATIC.FIXATION.VERTICAL.AUTO
        self.status['power'] = self.STATIC.ONOFF.ON
        self.status['mode'] = self.STATIC.MODE.AUTO
        self.status['sleep'] = self.STATIC.ONOFF.OFF
        self.status['display'] = self.STATIC.ONOFF.ON
        self.status['health'] = self.STATIC.ONOFF.OFF
        self.status['ifeel'] = self.STATIC.ONOFF.OFF
        self.status['fixation_h'] = self.STATIC.FIXATION.HORIZONTAL.LEFT_RIGHT_FIX
        self.status['fanspeed'] = self.STATIC.FAN.AUTO
        self.status['turbo'] = self.STATIC.ONOFF.OFF
        self.status['mute'] = self.STATIC.ONOFF.OFF
        self.status['clean'] = self.STATIC.ONOFF.OFF
        self.status['mildew'] = self.STATIC.ONOFF.OFF
        self.status['macaddress'] = None
        self.status['hostip'] = None
        self.status['lastupdate'] = None
        self.status['ambient_temp'] = None
        self.status['devicename'] = None

    def set_temperature(self, temperature):
        self.logger.debug("Setting temperature to %s", temperature)
        self.get_ac_states()
        self.status['temp'] = float(temperature)

        self.set_ac_status()
        return self.make_nice_status(self.status)

    def switch_off(self):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()
        self.status['power'] = self.STATIC.ONOFF.OFF
        self.set_ac_status()
        return self.make_nice_status(self.status)

    def switch_on(self):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()
        self.status['power'] = self.STATIC.ONOFF.ON
        self.set_ac_status()

        return self.make_nice_status(self.status)

    def set_mode(self, mode_text):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.MODE.__dict__.get(mode_text.upper())
        if mode != None:
            self.status['mode'] = mode
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found mode value %s", str(mode_text))
            return False

    def set_fanspeed(self, mode_text):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.FAN.__dict__.get(mode_text.upper())
        if mode != None:
            self.status['fanspeed'] = mode
            self.status['turbo'] = self.STATIC.ONOFF.OFF
            self.status['mute'] = self.STATIC.ONOFF.OFF
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found mode value %s", str(mode_text))
            return False

    def set_mute(self, value):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.ONOFF.__dict__.get(value)
        if mode != None:
            self.status['mute'] = mode
            self.status['turbo'] = self.STATIC.ONOFF.OFF
            self.status['fanspeed'] = self.STATIC.FAN.NONE
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found mute value %s", str(value))
            return False

    def set_turbo(self, value):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.ONOFF.__dict__.get(value)
        if mode != None:
            self.status['turbo'] = mode
            self.status['mute'] = self.STATIC.ONOFF.OFF
            self.status['fanspeed'] = self.STATIC.FAN.NONE
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found Turbo value %s", str(value))
            return False

    def set_fixation_v(self, fixation_text):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        fixation = self.STATIC.FIXATION.VERTICAL.__dict__.get(fixation_text.upper())
        if fixation != None:
            self.status['fixation_v'] = fixation
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found mode value %s", str(fixation_text))
            return False

    def set_fixation_h(self, fixation_text):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        fixation = self.STATIC.FIXATION.HORIZONTAL.__dict__.get(fixation_text.upper())
        if fixation != None:
            self.status['fixation_h'] = fixation
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found mode value %s", str(fixation_text))
            return False

    def set_display(self, value):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.ONOFF.__dict__.get(value)
        if mode != None:
            self.status['display'] = mode
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found display value %s", str(value))
            return False

    def set_mildew(self, value):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.ONOFF.__dict__.get(value)
        if mode != None:
            self.status['mildew'] = mode
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found display value %s", str(value))
            return False

    def set_clean(self, value):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.ONOFF.__dict__.get(value)
        if mode != None:
            self.status['clean'] = mode
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found display value %s", str(value))
            return False

    def set_health(self, value):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.ONOFF.__dict__.get(value)
        if mode != None:
            self.status['health'] = mode
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found display value %s", str(value))
            return False

    def set_sleep(self, value):
        ##Make sure latest info as cannot just update one things, have set all
        self.get_ac_states()

        mode = self.STATIC.ONOFF.__dict__.get(value)
        if mode != None:
            self.status['sleep'] = mode
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Not found display value %s", str(value))
            return False

    def set_homekit_mode(self, status):
        if type(status) is not str:
            self.logger.debug('Status variable is not string %s', type(status))
            return False

        if status.lower() == 'coolon':
            self.status['mode'] = self.STATIC.MODE.COOLING
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)
        elif status.lower() == 'heaton':
            self.status['mode'] = self.STATIC.MODE.HEATING
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)

        elif status.lower() == 'auto':
            self.status['mode'] = self.STATIC.MODE.AUTO
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)

        if status.lower() == 'dry':
            self.status['mode'] = self.STATIC.MODE.DRY
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)
        if status.lower() == 'fan_only':
            self.status['mode'] = self.STATIC.MODE.FAN
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)
        elif status.lower() == "off":
            self.status['power'] = self.STATIC.ONOFF.OFF
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug('Invalid status for homekit %s', status)
            return False

    def set_homeassistant_mode(self, status):
        if type(status) is not str:
            self.logger.debug('Status variable is not string %s', type(status))
            return False

        if status.lower() == 'cool':
            self.status['mode'] = self.STATIC.MODE.COOLING
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)
        elif status.lower() == 'heat':
            self.status['mode'] = self.STATIC.MODE.HEATING
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)

        elif status.lower() == 'auto':
            self.status['mode'] = self.STATIC.MODE.AUTO
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)

        if status.lower() == 'dry':
            self.status['mode'] = self.STATIC.MODE.DRY
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)
        if status.lower() == 'fan_only':
            self.status['mode'] = self.STATIC.MODE.FAN
            self.status['power'] = self.STATIC.ONOFF.ON
            self.set_ac_status()
            return self.make_nice_status(self.status)
        elif status.lower() == "off":
            self.status['power'] = self.STATIC.ONOFF.OFF
            self.set_ac_status()
            return self.make_nice_status(self.status)
        else:
            self.logger.debug('Invalid status for homekit %s', status)
            return False

    def get_ac_info(self):
        GET_AC_INFO = bytearray.fromhex("0C00BB0006800000020021011B7E0000")
        response = self.send_packet(0x6a, GET_AC_INFO)
        # print "Response:" + ''.join(format(x, '02x') for x in response)
        # print "Response:" + ' '.join(format(x, '08b') for x in response[9:])

        err = response[0x22] | (response[0x23] << 8)
        if err == 0:

            # response = bytearray.fromhex("5aa5aa555aa5aa55000000000000000000000000000000000000000000000000c6d000002a4e6a0055b9af41a70d43b401000000b9c00000aeaac104468cf91b485f38c67f7bf57f");
            # response = bytearray.fromhex("5aa5aa555aa5aa5547006f008d9904312c003e00000000003133a84d00400000d8d500002a4e6a0070a1b88c08b043a001000000b9c0000038821c66e3b38a5afe79dcb145e215d7")

            response_payload = self.decrypt(bytes(response[0x38:]))
            response_payload = bytearray(response_payload)

            self.logger.debug("Acinfo Raw Response: " + ' '.join(format(x, '08b') for x in response_payload))
            self.logger.debug("Acinfo Raw Hex: " + ' '.join(format(x, '02x') for x in response_payload))

            response_payload = response_payload[2:]  ##Drop leading stuff as dont need
            self.logger.debug("AcInfo: " + ' '.join(format(x, '08b') for x in response_payload[9:]))

            if len(response_payload) < 40:  ##Hack for some invalid packets. should get proper length at some point.  #54
                self.logger.debug("AcInfo: Invalid, seems to short?")
                return 0

            ##Its only the last 5 bits?
            ambient_temp = response_payload[15] & 0b00011111

            self.logger.debug("Ambient Temp Decimal: %s" % float(response_payload[31] & 0b00011111))  ## @Anonym-tsk

            if ambient_temp:
                self.status['ambient_temp'] = ambient_temp

            return self.make_nice_status(self.status)
        else:
            self.logger.debug("Invalid packet received Errorcode %s" % err)
            self.logger.debug("Failed Raw Response: " + ' '.join(format(x, '08b') for x in response))
            return 0

    ### Get AC Status
    ## GEt the current status of the aircon and parse into status array a one have to send full status each time for update, cannot just send one setting
    ##
    def get_ac_states(self, force_update=False):
        GET_STATES = bytearray.fromhex(
            "0C00BB0006800000020011012B7E0000")  ##From app queryAuxinfo:bb0006800000020011012b7e

        # Check if the status is up to date to reduce timeout issues. Can be overwritten by force_update
        self.logger.debug(f"Last update was: {self.status['lastupdate']}")
        if (force_update == False and (self.status['lastupdate'] + self.update_interval) > time.time()):
            return self.make_nice_status(self.status)

        response = self.send_packet(0x6a, GET_STATES)
        ##Check response, the checksums should be 0
        err = response[0x22] | (response[0x23] << 8)

        if err == 0:

            response_payload = bytes(self.decrypt(bytes(response[0x38:])))

            response_payload = bytearray(response_payload)
            packet_type = response_payload[4]
            if packet_type != 0x07:  ##Should be result packet, otherwise something weird
                return False

            packet_len = response_payload[0]
            if packet_len != 0x19:  ##should be 25, if not, then wrong packet
                return False

            self.logger.debug("Raw AC Status: " + ' '.join(format(x, '08b') for x in response_payload[9:]))

            response_payload = response_payload[2:]  ##Drop leading stuff as dont need

            self.logger.debug("Raw AC Status: " + ' '.join(format(x, '02x') for x in response_payload))
            # self.logger.debug ("" + ' '.join(format(x, '08b') for x in response_payload[9:] )  )

            # AuxInfo [tem=18, panMode=7, panType=1, nowTimeHour=5, setTem05=0, antoSenseYards=0, nowTimeMin=51, windSpeed=5, timerHour=0, voice=0, timerMin=0, mode=4, hasDew=0, hasSenseYards=0, hasSleep=0, isFollow=0, roomTem=0, roomHum=0, timeEnable=0, open=1, hasElectHeat=0, hasEco=0, hasClean=0, hasHealth=0, hasAir=0, weedSet=0, electronicLock=0, showDisplyBoard=1, mouldProof=0, controlMode=0, sleepMode=0]

            self.status['temp'] = 8 + (response_payload[10] >> 3) + (0.5 * float(response_payload[12] >> 7))
            self.status['power'] = response_payload[18] >> 5 & 0b00000001
            self.status['fixation_v'] = response_payload[10] & 0b00000111
            self.status['mode'] = response_payload[15] >> 5 & 0b00001111
            self.status['sleep'] = response_payload[15] >> 2 & 0b00000001
            self.status['display'] = response_payload[20] >> 4 & 0b00000001
            self.status['mildew'] = response_payload[20] >> 3 & 0b00000001
            self.status['health'] = response_payload[18] >> 1 & 0b00000001
            self.status['fixation_h'] = response_payload[10] & 0b00000111
            self.status['fanspeed'] = response_payload[13] >> 5 & 0b00000111
            self.status['ifeel'] = response_payload[15] >> 3 & 0b00000001
            self.status['mute'] = response_payload[14] >> 7 & 0b00000001
            self.status['turbo'] = response_payload[14] >> 6 & 0b00000001
            self.status['clean'] = response_payload[18] >> 2 & 0b00000001

            self.status['lastupdate'] = time.time()

            return self.make_nice_status(self.status)

        else:
            return 0

        return self.status

    def make_nice_status(self, status):
        status_nice = {}
        status_nice['temp'] = status['temp']
        status_nice['ambient_temp'] = status['ambient_temp']
        status_nice['power'] = self.get_key(self.STATIC.ONOFF.__dict__, status['power'])
        status_nice['fixation_v'] = self.get_key(self.STATIC.FIXATION.VERTICAL.__dict__, status['fixation_v'])
        status_nice['mode'] = self.get_key(self.STATIC.MODE.__dict__, status['mode'])
        status_nice['sleep'] = self.get_key(self.STATIC.ONOFF.__dict__, status['sleep'])
        status_nice['display'] = self.get_key(self.STATIC.ONOFF.__dict__, status['display'])
        status_nice['mildew'] = self.get_key(self.STATIC.ONOFF.__dict__, status['mildew'])
        status_nice['health'] = self.get_key(self.STATIC.ONOFF.__dict__, status['health'])
        status_nice['fixation_h'] = self.get_key(self.STATIC.FIXATION.HORIZONTAL.__dict__, status['fixation_h'])

        status_nice['ifeel'] = self.get_key(self.STATIC.ONOFF.__dict__, status['ifeel'])
        status_nice['mute'] = self.get_key(self.STATIC.ONOFF.__dict__, status['mute'])
        status_nice['turbo'] = self.get_key(self.STATIC.ONOFF.__dict__, status['turbo'])
        status_nice['clean'] = self.get_key(self.STATIC.ONOFF.__dict__, status['clean'])

        status_nice['macaddress'] = status['macaddress']
        status_nice['device_name'] = status['devicename']

        ##HomeKit topics
        if self.status['power'] == self.STATIC.ONOFF.OFF:
            status_nice['mode_homekit'] = "Off"
        elif status['power'] == self.STATIC.ONOFF.ON and status['mode'] == self.STATIC.MODE.AUTO:
            status_nice['mode_homekit'] = "Auto"
        elif status['power'] == self.STATIC.ONOFF.ON and status['mode'] == self.STATIC.MODE.HEATING:
            status_nice['mode_homekit'] = "HeatOn"
        elif status['power'] == self.STATIC.ONOFF.ON and status['mode'] == self.STATIC.MODE.COOLING:
            status_nice['mode_homekit'] = "CoolOn"
        else:
            status_nice['mode_homekit'] = "Error"

        ##Home Assist topic
        if self.status['power'] == self.STATIC.ONOFF.OFF:
            status_nice['mode_homeassistant'] = "off"
        elif status['power'] == self.STATIC.ONOFF.ON and status['mode'] == self.STATIC.MODE.AUTO:
            status_nice['mode_homeassistant'] = "auto"
        elif status['power'] == self.STATIC.ONOFF.ON and status['mode'] == self.STATIC.MODE.HEATING:
            status_nice['mode_homeassistant'] = "heat"
        elif status['power'] == self.STATIC.ONOFF.ON and status['mode'] == self.STATIC.MODE.COOLING:
            status_nice['mode_homeassistant'] = "cool"
        elif status['power'] == self.STATIC.ONOFF.ON and status['mode'] == self.STATIC.MODE.DRY:
            status_nice['mode_homeassistant'] = "dry"
        elif status['power'] == self.STATIC.ONOFF.ON and status['mode'] == self.STATIC.MODE.FAN:
            status_nice['mode_homeassistant'] = "fan_only"
        else:
            status_nice['mode_homeassistant'] = "Error"

        ##Make fanspeed logic
        status_nice['fanspeed'] = self.get_key(self.STATIC.FAN.__dict__, status['fanspeed'])
        status_nice['fanspeed_homeassistant'] = self.get_key(self.STATIC.FAN.__dict__, status['fanspeed']).title()

        if status_nice['mute'] == "ON":
            status_nice['fanspeed_homeassistant'] = "Mute"
            status_nice['fanspeed'] = "MUTE"
        elif status_nice['turbo'] == "ON":
            status_nice['fanspeed_homeassistant'] = "Turbo"
            status_nice['fanspeed'] = "TURBO"

        return status_nice

    def get_key(self, list, search_value):

        for key, value in list.items():
            if value == search_value:
                return key
        ##Not found so return value;
        return search_value

    ###  UDP checksum function
    def checksum_func(self, data):
        checksum = 0
        data_len = len(data)
        if (data_len % 2) == 1:
            data_len += 1
            data += struct.pack('!B', 0)

        for i in range(0, len(data), 2):
            w = (data[i] << 8) + (data[i + 1])
            checksum += w

        checksum = (checksum >> 16) + (checksum & 0xFFFF)
        checksum = ~checksum & 0xFFFF
        return checksum

    def set_ac_status(self):
        self.logger.debug("Start set_ac_status")
        # packet = bytearray(32)
        # 10111011 00000000 00000110 10000000 00000000 00000000 00001111 00000000 00000001 9 00000001 10 01000111 11 00101000  12 00100000 13 10100000 14 00000000 15 00100000  16 00000000 17 00000000 18 00100000 19 00000000 20 00010000 21 00000000 22 00000101 10010001 10010101

        if self.status['temp'] < 16:
            temperature = 16 - 8
            temperature_05 = 0

            ##Make sure to fix the global status as well
            self.status['temp'] = 16

        elif self.status['temp'] > 32:
            temperature = 32 - 8
            temperature_05 = 0
            ##Make sure to fix the global status as well
            self.status['temp'] = 32

        else:
            ##if 0.5 then make true	. Also  offset with 8
            if self.status['temp'].is_integer():
                temperature = int(self.status['temp'] - 8)
                temperature_05 = 0
            else:
                temperature_05 = 1
                temperature = int(self.status['temp'] - 8)

        payload = bytearray(23)
        payload[0] = 0xbb
        payload[1] = 0x00
        payload[2] = 0x06  # Send command, seems like 07 is response
        payload[3] = 0x80
        payload[4] = 0x00
        payload[5] = 0x00
        payload[6] = 0x0f  # Set status .. #02 -> get info?
        payload[7] = 0x00
        payload[8] = 0x01
        payload[9] = 0x01
        payload[10] = 0b00000000 | temperature << 3 | self.status['fixation_v']
        payload[11] = 0b00000000 | self.status['fixation_h'] << 5
        payload[
            12] = 0b00001111 | temperature_05 << 7  # bit 1:  0.5  #bit   if 0b?1 then nothing done....  last 6 is some sort of packet_id
        payload[13] = 0b00000000 | self.status['fanspeed'] << 5
        payload[14] = 0b00000000 | self.status['turbo'] << 6 | self.status['mute'] << 7
        payload[15] = 0b00000000 | self.status['mode'] << 5 | self.status['sleep'] << 2
        payload[16] = 0b00000000
        payload[17] = 0x00
        payload[18] = 0b00000000 | self.status['power'] << 5 | self.status['health'] << 1 | self.status['clean'] << 2
        payload[19] = 0x00
        payload[20] = 0b00000000 | self.status['display'] << 4 | self.status['mildew'] << 3
        payload[21] = 0b00000000
        payload[22] = 0b00000000

        self.logger.debug("Payload:" + ''.join(format(x, '02x') for x in payload))

        # first byte is length, Then placeholder then payload +2 for CRC16
        request_payload = bytearray(32)
        request_payload[0] = len(payload) + 2  ##Length plus of payload plus crc
        request_payload[2:len(payload) + 2] = payload  ##Add the Payload

        # append CRC
        crc = self.checksum_func(payload)
        self.logger.debug("Checksum:" + format(crc, '02x'))
        request_payload[len(payload) + 1] = ((crc >> 8) & 0xFF)
        request_payload[len(payload) + 2] = crc & 0xFF

        self.logger.debug("Packet:" + ''.join(format(x, '02x') for x in request_payload))

        response = self.send_packet(0x6a, request_payload)
        self.logger.debug("Resposnse:" + ''.join(format(x, '02x') for x in response))

        err = response[0x22] | (response[0x23] << 8)
        if err == 0:

            response_payload = self.decrypt(bytes(response[0x38:]))
            response_payload = bytearray(response_payload)

            packet_type = response_payload[4]
            if packet_type == 0x07:  ##Should be result packet, otherwise something weird
                return self.status
            else:
                return False

            self.logger.debug("Payload: Nice:" + ''.join(x.encode('hex') for x in response_payload))

        return "done"
