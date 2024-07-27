import random
import socket
import threading
import time

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from broadlink_ac_mqtt.ac_communication.broadlink.connect_timeout import ConnectTimeout


class device:
    __INIT_KEY = "097628343fe99e23765c1513accf8b02"
    __INIT_VECT = "562e17996d093d28ddb3ba695a2e6f58"

    def __init__(self, host, mac, timeout=10, name=None, cloud=None, devtype=None, update_interval=0, bind_to_ip=None):

        self.host = host
        self.mac = mac
        self.name = name
        self.cloud = cloud
        self.timeout = timeout
        self.devtype = devtype
        self.count = random.randrange(0xffff)
        ##AES
        self.key = bytearray(
            [0x09, 0x76, 0x28, 0x34, 0x3f, 0xe9, 0x9e, 0x23, 0x76, 0x5c, 0x15, 0x13, 0xac, 0xcf, 0x8b, 0x02])
        self.iv = bytearray(
            [0x56, 0x2e, 0x17, 0x99, 0x6d, 0x09, 0x3d, 0x28, 0xdd, 0xb3, 0xba, 0x69, 0x5a, 0x2e, 0x6f, 0x58])

        self.id = bytearray([0, 0, 0, 0])
        self.cs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.cs.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # self.cs.bind(('',0))
        self.type = "Unknown"
        self.lock = threading.Lock()
        self.update_interval = update_interval
        self.bind_to_ip = bind_to_ip
        self.aes = None
        self.update_aes(bytes.fromhex(self.__INIT_KEY))

    def update_aes(self, key: bytes) -> None:
        """Update AES."""
        self.aes = Cipher(
            algorithms.AES(bytes(key)), modes.CBC(self.iv), backend=default_backend()
        )

    def encrypt(self, payload: bytes) -> bytes:
        """Encrypt the payload."""
        encryptor = self.aes.encryptor()
        return encryptor.update(bytes(payload)) + encryptor.finalize()

    def decrypt(self, payload: bytes) -> bytes:
        """Decrypt the payload."""
        decryptor = self.aes.decryptor()
        return decryptor.update(bytes(payload)) + decryptor.finalize()

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

        self.update_aes(payload[0x04:0x14])

        return True

    def get_type(self):
        return self.type

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

                    break
                except socket.timeout:
                    if (time.time() - starttime) < self.timeout:
                        pass
                    raise ConnectTimeout(200, self.host)
        return bytearray(response[0])
