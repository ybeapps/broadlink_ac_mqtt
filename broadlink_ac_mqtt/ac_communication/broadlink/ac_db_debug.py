import socket
import struct
import time

from broadlink_ac_mqtt.ac_communication.broadlink.ac_db import ac_db
from broadlink_ac_mqtt.ac_communication.broadlink.device import device
from broadlink_ac_mqtt.ac_communication.broadlink.connect_timeout import ConnectTimeout


class ac_db_debug(device):
    import logging

    type = "ac_db"

    def __init__(self, host, mac, name=None, cloud=None, debug=False, update_interval=0, devtype=None, auth=False):
        device.__init__(self, host, mac, name=name, cloud=cloud, devtype=devtype, update_interval=update_interval)

        devtype = devtype
        self.status = {}
        self.logger = self.logging.getLogger(__name__)

        self.update_interval = update_interval

        ##Set default values
        # mac = mac[::-1]

        self.set_default_values()

        self.status['macaddress'] = ''.join(format(x, '02x') for x in mac)
        self.status['hostip'] = host
        self.status['name'] = name

        self.logging.basicConfig(level=(self.logging.DEBUG if debug else self.logging.INFO))
        self.logger.debug("Debugging Enabled")

        self.logger.debug("Authenticating")
        if self.auth() == False:
            print("Authentication Failed to AC")

        self.logger.debug("Setting test temperature")
        self.set_temperature(25)

        ##Get the current details
        self.logger.debug("Getting current details in init")

    # self.get_ac_states(force_update = True)

    def get_ac_states(self, force_update=False):
        GET_STATES = bytearray.fromhex(
            "0C00BB0006800000020011012B7E0000")  ##From app queryAuxinfo:bb0006800000020011012b7e

        ##Check if the status is up to date to reduce timeout issues. Can be overwritten by force_update
        self.logger.debug("Last update was: %s" % self.status['lastupdate'])
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
            self.status['fixation_h'] = response_payload[11] >> 5 & 0b00000111
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

    def set_default_values(self):

        self.status['temp'] = float(19)
        self.status['fixation_v'] = ac_db.STATIC.FIXATION.VERTICAL.AUTO
        self.status['power'] = ac_db.STATIC.ONOFF.ON
        self.status['mode'] = ac_db.STATIC.MODE.AUTO
        self.status['sleep'] = ac_db.STATIC.ONOFF.OFF
        self.status['display'] = ac_db.STATIC.ONOFF.ON
        self.status['health'] = ac_db.STATIC.ONOFF.OFF
        self.status['ifeel'] = ac_db.STATIC.ONOFF.OFF
        self.status['fixation_h'] = ac_db.STATIC.FIXATION.HORIZONTAL.LEFT_RIGHT_FIX
        self.status['fanspeed'] = ac_db.STATIC.FAN.AUTO
        self.status['turbo'] = ac_db.STATIC.ONOFF.OFF
        self.status['mute'] = ac_db.STATIC.ONOFF.OFF
        self.status['clean'] = ac_db.STATIC.ONOFF.OFF
        self.status['mildew'] = ac_db.STATIC.ONOFF.OFF
        self.status['macaddress'] = None
        self.status['hostip'] = None
        self.status['lastupdate'] = None
        self.status['ambient_temp'] = None
        self.status['devicename'] = None

    def set_temperature(self, temperature):
        self.logger.debug("Setting temprature to %s", temperature)
        # self.get_ac_states()
        self.status['temp'] = float(temperature)

        self.set_ac_status()

    # return self.make_nice_status(self.status)

    def set_ac_status(self):
        self.logger.debug("Start set_ac_status")
        # packet = bytearray(32)
        # 10111011 00000000 00000110 10000000 00000000 00000000 00001111 00000000 00000001 9 00000001 10 01000111 11 00101000  12 00100000 13 10100000 14 00000000 15 00100000  16 00000000 17 00000000 18 00100000 19 00000000 20 00010000 21 00000000 22 00000101 10010001 10010101
        # print "setting something"
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
        # print temperature

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

        # print ("Payload:"+ ''.join(format(x, '02x') for x in payload))

        # first byte is length, Then placeholder then payload +2 for CRC16
        request_payload = bytearray(32)
        request_payload[0] = len(payload) + 2  ##Length plus of payload plus crc
        request_payload[2:len(payload) + 2] = payload  ##Add the Payload

        # append CRC

        crc = self.checksum_func(payload)
        # print ("Checksum:"+format(crc,'02x'))
        request_payload[len(payload) + 1] = ((crc >> 8) & 0xFF)
        request_payload[len(payload) + 2] = crc & 0xFF

        # print ("Packet:"+ ''.join(format(x, '02x') for x in request_payload))

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

    def send_packet(self, command, payload):
        self.count = (self.count + 1) & 0xffff
        packet = bytearray(0x38)
        packet[0x00] = 0x5a
        packet[0x01] = 0xa5
        packet[0x02] = 0xaa
        packet[0x03] = 0x55
        packet[0x04] = 0x5a
        packet[0x05] = 0xa5
        packet[0x06] = 0xaa
        packet[0x07] = 0x55
        packet[0x24] = 0x2a  # ==> Type
        packet[0x25] = 0x4e  # ==> Type
        packet[0x26] = command
        packet[0x28] = self.count & 0xff
        packet[0x29] = self.count >> 8
        packet[0x2a] = self.mac[0]
        packet[0x2b] = self.mac[1]
        packet[0x2c] = self.mac[2]
        packet[0x2d] = self.mac[3]
        packet[0x2e] = self.mac[4]
        packet[0x2f] = self.mac[5]
        packet[0x30] = self.id[0]
        packet[0x31] = self.id[1]
        packet[0x32] = self.id[2]
        packet[0x33] = self.id[3]

        checksum = 0xbeaf
        for i in range(len(payload)):
            checksum += payload[i]
            checksum = checksum & 0xffff

        payload = self.encrypt(bytes(payload))

        packet[0x34] = checksum & 0xff
        packet[0x35] = checksum >> 8

        for i in range(len(payload)):
            packet.append(payload[i])

        checksum = 0xbeaf
        for i in range(len(packet)):
            checksum += packet[i]
            checksum = checksum & 0xffff
        packet[0x20] = checksum & 0xff
        packet[0x21] = checksum >> 8

        # print 'Sending Packet:\n'+''.join(format(x, '02x') for x in packet)+"\n"
        starttime = time.time()

        with self.lock:
            while True:
                try:
                    self.cs.sendto(packet, self.host)
                    self.cs.settimeout(1)
                    response = self.cs.recvfrom(1024)
                    # print response
                    break
                except socket.timeout as err:
                    if (time.time() - starttime) < self.timeout:
                        pass
                    # print "timedout"
                    print(err)
                    raise ConnectTimeout(200, self.host)
        return bytearray(response[0])

    def auth(self):
        payload = bytearray(0x50)
        payload[0x04] = 0x31
        payload[0x05] = 0x31
        payload[0x06] = 0x31
        payload[0x07] = 0x31
        payload[0x08] = 0x31
        payload[0x09] = 0x31
        payload[0x0a] = 0x31
        payload[0x0b] = 0x31
        payload[0x0c] = 0x31
        payload[0x0d] = 0x31
        payload[0x0e] = 0x31
        payload[0x0f] = 0x31
        payload[0x10] = 0x31
        payload[0x11] = 0x31
        payload[0x12] = 0x31
        payload[0x1e] = 0x01
        payload[0x2d] = 0x01
        payload[0x30] = ord('T')
        payload[0x31] = ord('e')
        payload[0x32] = ord('s')
        payload[0x33] = ord('t')
        payload[0x34] = ord(' ')
        payload[0x35] = ord(' ')
        payload[0x36] = ord('1')

        response = self.send_packet(0x65, payload)

        enc_payload = response[0x38:]

        payload = self.decrypt(bytes(enc_payload))

        if not payload:
            return False

        key = payload[0x04:0x14]
        if len(key) % 16 != 0:
            return False

        self.id = payload[0x00:0x04]
        self.key = key
        return True
