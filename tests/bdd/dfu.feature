Feature: Perform DFU
  Scenario: USB serial DFU completes without error
    Given the user wants to perform dfu usb-serial
    And using package examples\dfu\secure_dfu_test_images\uart\nrf52840\blinky_mbr.zip
    And nrfjprog examples\dfu\secure_bootloader\pca10056_usb_debug\hex\secure_bootloader_usb_mbr_pca10056_debug.hex for usb-serial PCA10056_0
    Then perform dfu

  Scenario: Serial DFU completes without error
    Given the user wants to perform dfu serial
    And using package examples\dfu\secure_dfu_test_images\uart\nrf52840\blinky_mbr.zip
    And nrfjprog examples\dfu\secure_bootloader\pca10056_uart_debug\hex\secure_bootloader_uart_mbr_pca10056_debug.hex for serial PCA10056_0
    Then perform dfu

  Scenario: BLE DFU completes without error
    Given the user wants to perform dfu ble
    And using package examples\dfu\secure_dfu_test_images\ble\nrf52840\hrs_application_s140.zip
    And option --conn-ic-id NRF52
    And option --name DfuTarg
    And nrfjprog examples\dfu\secure_bootloader\pca10056_ble_debug\hex\secure_bootloader_ble_s140_pca10056_debug.hex for ble PCA10056_0
    And nrfjprog connectivity for serial PCA10056_1
    Then perform dfu

  # DFU trigger tests runs twice in case the device was already in bootloader before starting.
  # The test will fail if the device is not in bootloader mode or is running an application without trigger interface.
  Scenario: Enter bootloader and perform DFU using trigger interface
    Given the user wants to perform dfu usb-serial
    And using package connectivity_usb
    And -snr PCA10059
    Then perform dfu
    Then perform dfu
