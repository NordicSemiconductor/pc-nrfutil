# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import re
import os
import json
from abc import ABCMeta, abstractmethod


class TargetDatabase(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_targets(self):
        pass

    @abstractmethod
    def get_target(self, target_id):
        pass

    @abstractmethod
    def refresh(self):
        pass

    @staticmethod
    def find_target(targets, target_id):
        for target in targets:
            if target["id"] == target_id:
                return target

        return None


class EnvTargetDatabase(TargetDatabase):
    def __init__(self):
        self.targets = None

    def get_targets(self):
        if self.targets is None:
            self.targets = []

            for key, value in os.environ.iteritems():
                match = re.match("NORDICSEMI_TARGET_(?P<target>\d+)_(?P<key>[a-zA-Z_]+)", key)

                if match:
                    key_value = match.groupdict()
                    if "key" in key_value and "target" in key_value:
                        target_id = int(key_value["target"])

                        target = self.find_target(self.targets, target_id)

                        if target is None:
                            target = {"id": int(target_id)}
                            self.targets.append(target)

                        target[key_value["key"].lower()] = value

        return self.targets

    def refresh(self):
        self.targets = None

    def get_target(self, target_id):
        return self.find_target(self.get_targets(), target_id)


class FileTargetDatabase(TargetDatabase):
    def __init__(self, filename):
        self.filename = filename
        self.targets = None

    def get_targets(self):
        if not self.targets:
            self.targets = json.load(open(self.filename, "r"))["targets"]

        return self.targets

    def get_target(self, target_id):
        return self.find_target(self.get_targets(), target_id)

    def refresh(self):
        self.targets = None


class TargetRegistry(object):
    def __init__(self, target_db=EnvTargetDatabase()):
        self.target_db = target_db

    def find_one(self, target_id=None):
        if target_id:
            return self.target_db.get_target(target_id)
        else:
            return None

    def get_all(self):
        return self.target_db.get_targets()