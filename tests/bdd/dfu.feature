Feature: Perform DFU
  Scenario: USB serial DFU completes without error
    Given the user wants to perform dfu usb-serial
    And using package tests\resources\blinky_mbr_sdk160.zip
    And nrfjprog tests\resources\secure_bootloader_usb_mbr_pca10056_debug_sdk160.hex for usb-serial PCA10056_0
    Then perform dfu using nrfutil NRFUTIL

  Scenario: Serial DFU completes without error
    Given the user wants to perform dfu serial
    And using package tests\resources\blinky_mbr_sdk160.zip
    And nrfjprog tests\resources\secure_bootloader_uart_mbr_pca10056_debug_sdk160.hex for serial PCA10056_0
    Then perform dfu using nrfutil NRFUTIL

  Scenario: BLE DFU completes without error
    Given the user wants to perform dfu ble
    And using package tests\resources\hrs_application_s140_sdk160.zip
    And option --conn-ic-id NRF52
    And option --name DfuTarg
    And nrfjprog tests\resources\secure_bootloader_ble_s140_pca10056_debug_sdk160.hex for ble PCA10056_0
    And nrfjprog connectivity for serial PCA10056_1
    Then perform dfu using nrfutil NRFUTIL

  # DFU trigger tests runs twice in case the device was already in bootloader before starting.
  # The test will fail if the device is not in bootloader mode or is running an application without trigger interface.
  @unstable
  Scenario: Enter bootloader and perform DFU using trigger interface
    Given the user wants to perform dfu usb-serial
    And using package connectivity_usb
    And -snr PCA10059
    Then perform dfu using nrfutil NRFUTIL
    Then perform dfu using nrfutil NRFUTIL

  # TODO : This does currently not work as the PCA10056 through usb does not 
  # enter bootloader after getting flashed with connectivity software.
  #
  # -- NB! -- : The above test for PCA10059 is changed to PCA10056 for robustnes. 
  # DFU trigger tests runs twice in case the device was already in bootloader before starting.
  # The test will fail if the device is not in bootloader mode or is running an application without trigger interface.
  #Scenario: Enter bootloader and perform DFU using trigger interface
  #  Given the user wants to perform dfu usb-serial
  #  And using package connectivity_usb
  #  And nrfjprog tests\resources\open_bootloader_usb_mbr_pca10059_debug_sdk160.hex for usb-serial PCA10056_0
  #  Then perform dfu twice with port change
