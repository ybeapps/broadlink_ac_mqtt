#!/usr/bin/python
# -*- coding: utf8 -*-

import logging
import struct


class ac_db_disconnected:
    type = "ac_db_disconnected"

    def __init__(self, debug=False, dev_type=None):
        self._dev_type = dev_type
        self.original_config = None
        logging.basicConfig(level=(logging.DEBUG if debug else logging.INFO))
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Debugging Enabled")

    def get_ac_status(self, force_update=False):
        return None

    def set_default_values(self):
        pass

    def set_temperature(self, temperature):
        pass

    def switch_off(self):
        pass

    def switch_on(self):
        pass

    def set_mode(self, mode_text):
        pass

    def set_fanspeed(self, mode_text):
        pass

    def set_mute(self, value):
        pass

    def set_turbo(self, value):
        pass

    def set_fixation_v(self, fixation_text):
        pass

    def set_fixation_h(self, fixation_text):
        pass

    def set_display(self, value):
        pass

    def set_mildew(self, value):
        pass

    def set_clean(self, value):
        pass

    def set_health(self, value):
        pass

    def set_sleep(self, value):
        pass

    def set_homekit_mode(self, status):
        pass

    def set_homeassistant_mode(self, status):
        pass

    def get_ac_info(self):
        pass

    def get_ac_states(self, force_update=False):
        pass

    def make_nice_status(self, status):
        pass

    def get_key(self, list, search_value):
        pass

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
        pass
