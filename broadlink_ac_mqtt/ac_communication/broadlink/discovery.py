import socket
import time
from datetime import datetime

from broadlink_ac_mqtt.ac_communication.broadlink.device_factory import create_device


def discover(timeout=None, bind_to_ip=None):
    if bind_to_ip is None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))  # connecting to a UDP address doesn't send packets
        bind_to_ip = s.getsockname()[0]

    address = bind_to_ip.split('.')
    cs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    cs.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    cs.bind((bind_to_ip, 0))

    port = cs.getsockname()[1]
    starttime = time.time()

    devices = []

    timezone = int(time.timezone / -3600)
    packet = bytearray(0x30)

    year = datetime.now().year

    if timezone < 0:
        packet[0x08] = 0xff + timezone - 1
        packet[0x09] = 0xff
        packet[0x0a] = 0xff
        packet[0x0b] = 0xff
    else:
        packet[0x08] = timezone
        packet[0x09] = 0
        packet[0x0a] = 0
        packet[0x0b] = 0
    packet[0x0c] = year & 0xff
    packet[0x0d] = year >> 8
    packet[0x0e] = datetime.now().minute
    packet[0x0f] = datetime.now().hour
    subyear = str(year)[2:]
    packet[0x10] = int(subyear)
    packet[0x11] = datetime.now().isoweekday()
    packet[0x12] = datetime.now().day
    packet[0x13] = datetime.now().month
    packet[0x18] = int(address[0])
    packet[0x19] = int(address[1])
    packet[0x1a] = int(address[2])
    packet[0x1b] = int(address[3])
    packet[0x1c] = port & 0xff
    packet[0x1d] = port >> 8
    packet[0x26] = 6
    checksum = 0xbeaf

    for i in range(len(packet)):
        checksum += packet[i]
    checksum = checksum & 0xffff
    packet[0x20] = checksum & 0xff
    packet[0x21] = checksum >> 8

    cs.sendto(packet, ('255.255.255.255', 80))
    if timeout is None:
        response = cs.recvfrom(1024)
        responsepacket = bytearray(response[0])
        host = response[1]
        mac = responsepacket[0x3a:0x40]
        mac = mac[::-1]  ##Flip correct
        devtype = responsepacket[0x34] | responsepacket[0x35] << 8
        name = responsepacket[0x40:].split(b'\x00')[0].decode('utf-8')
        if not name:
            name = mac
        cloud = bool(responsepacket[-1])
        cs.close()
        return create_device(devtype, host, mac, name=name, cloud=cloud)
    else:
        while (time.time() - starttime) < timeout:
            cs.settimeout(timeout - (time.time() - starttime))
            try:
                response = cs.recvfrom(1024)
            except socket.timeout:
                return devices
            responsepacket = bytearray(response[0])

            # print ":".join("{:02x}".format(c) for c in responsepacket)
            # print ":".join("{:c}".format(c) for c in responsepacket)

            host = response[1]
            devtype = responsepacket[0x34] | responsepacket[0x35] << 8
            mac = responsepacket[0x3a:0x40]
            mac = mac[::-1]  ##flip Correct
            name = responsepacket[0x40:].split(b'\x00')[0].decode('utf-8')
            ##Make sure there is some name
            if not name:
                name = mac

            cloud = bool(responsepacket[-1])
            dev = create_device(devtype, host, mac, name=name, cloud=cloud)
            devices.append(dev)

    cs.close()
    return devices
