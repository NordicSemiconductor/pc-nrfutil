# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

try:
    import s130_nrf51_ble_driver as ble_driver
except Exception:
    print "Error. No ble_driver module found."


UNIT_0_625_MS = 625  # Unit used for scanning and advertising parameters
UNIT_1_25_MS = 1250  # Unit used for connection interval parameters
UNIT_10_MS = 10000  # Unit used for supervision timeout parameter


def msec_to_units(time_ms, resolution):
    """Convert milliseconds to BLE specific time units."""
    units = time_ms * 1000 / resolution
    return int(units)


def units_to_msec(units, resolution):
    """Convert BLE specific units to milliseconds."""
    time_ms = units * resolution / 1000
    return time_ms


def uint8_array_to_list(array_pointer, length):
    """Convert uint8_array to python list."""
    data_array = ble_driver.uint8_array.frompointer(array_pointer)
    data_list = _populate_list(data_array, length)
    return data_list


def uint16_array_to_list(array_pointer, length):
    """Convert uint16_array to python list."""
    data_array = ble_driver.uint16_array.frompointer(array_pointer)
    data_list = _populate_list(data_array, length)
    return data_list


def service_array_to_list(array_pointer, length):
    """Convert ble_gattc_service_array to python list."""
    data_array = ble_driver.ble_gattc_service_array.frompointer(array_pointer)
    data_list = _populate_list(data_array, length)
    return data_list


def include_array_to_list(array_pointer, length):
    """Convert ble_gattc_include_array to python list."""
    data_array = ble_driver.ble_gattc_include_array.frompointer(array_pointer)
    data_list = _populate_list(data_array, length)
    return data_list


def char_array_to_list(array_pointer, length):
    """Convert ble_gattc_char_array to python list."""
    data_array = ble_driver.ble_gattc_char_array.frompointer(array_pointer)
    data_list = _populate_list(data_array, length)
    return data_list


def desc_array_to_list(array_pointer, length):
    """Convert ble_gattc_desc_array to python list."""
    data_array = ble_driver.ble_gattc_desc_array.frompointer(array_pointer)
    data_list = _populate_list(data_array, length)
    return data_list


def handle_value_array_to_list(array_pointer, length):
    """Convert ble_gattc_handle_value_array to python list."""
    data_array = ble_driver.ble_gattc_handle_value_array.frompointer(array_pointer)
    data_list = _populate_list(data_array, length)
    return data_list


def _populate_list(data_array, length):
    data_list = []
    for i in range(0, length):
        data_list.append(data_array[i])
    return data_list


def list_to_uint8_array(data_list):
    """Convert python list to uint8_array."""

    data_array = _populate_array(data_list, ble_driver.uint8_array)
    return data_array


def list_to_uint16_array(data_list):
    """Convert python list to uint16_array."""

    data_array = _populate_array(data_list, ble_driver.uint16_array)
    return data_array


def list_to_service_array(data_list):
    """Convert python list to ble_gattc_service_array."""

    data_array = _populate_array(data_list, ble_driver.ble_gattc_service_array)
    return data_array


def list_to_include_array(data_list):
    """Convert python list to ble_gattc_include_array."""

    data_array = _populate_array(data_list, ble_driver.ble_gattc_include_array)
    return data_array


def list_to_char_array(data_list):
    """Convert python list to ble_gattc_char_array."""

    data_array = _populate_array(data_list, ble_driver.ble_gattc_char_array)
    return data_array


def list_to_desc_array(data_list):
    """Convert python list to ble_gattc_desc_array."""

    data_array = _populate_array(data_list, ble_driver.ble_gattc_desc_array)
    return data_array


def list_to_handle_value_array(data_list):
    """Convert python list to ble_gattc_handle_value_array."""

    data_array = _populate_array(data_list, ble_driver.ble_gattc_handle_value_array)
    return data_array


def _populate_array(data_list, array_type):
    length = len(data_list)
    data_array = array_type(length)
    for i in range(0, length):
        data_array[i] = data_list[i]
    return data_array
