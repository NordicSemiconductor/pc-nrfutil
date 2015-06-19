# Notice:
#   It can be smart to use the function util.generate_options_table_for_cucumber() to generate entries in Examples for
#   the options. It will save you a lot of time :-)

Feature: Generate DFU package
    Scenario Outline: package generation
      Given the user wants to generate a DFU package with application <application>, bootloader <bootloader> and SoftDevice <softdevice> with name <package>
      And with option --application-version <app_ver>
      And with option --dev-revision <dev_rev>
      And with option --dev-type <dev_type>
      And with option --dfu-ver <dfu_ver>
      And with option --sd-req <sd_req>
      When user press enter
      Then the generated DFU package <package> contains correct data

      Examples:
        | application | bootloader                   | softdevice                   | app_ver | dev_rev | dev_type  | dfu_ver | sd_req                           | package         |
        | blinky.bin  | dfu_test_bootloader_b.hex    | dfu_test_softdevice_b.hex    | not_set | not_set | not_set   | not_set | not_set                          | 111_00000.zip   |
        | blinky.bin  | dfu_test_bootloader_b.hex    | not_set                      | not_set | not_set | not_set   | not_set | not_set                          | 110_00000.zip   |
        | blinky.bin  | not_set                      | dfu_test_softdevice_b.hex    | not_set | not_set | not_set   | not_set | not_set                          | 101_00000.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | not_set   | not_set | not_set                          | 100_00000.zip   |
        | not_set     | dfu_test_bootloader_b.hex    | dfu_test_softdevice_b.hex    | not_set | not_set | not_set   | not_set | not_set                          | 011_00000.zip   |
        | not_set     | dfu_test_bootloader_b.hex    | not_set                      | not_set | not_set | not_set   | not_set | not_set                          | 010_00000.zip   |
        | not_set     | not_set                      | dfu_test_softdevice_b.hex    | not_set | not_set | not_set   | not_set | not_set                          | 001_00000.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | not_set   | not_set | not_set                          | 100_00000.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xe94a  | not_set | not_set   | not_set | not_set                          | 100_00001.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | 0x90dd  | not_set   | not_set | not_set                          | 100_00010.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xf3e3  | 0xfaee  | not_set   | not_set | not_set                          | 100_00011.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | 0x2122    | not_set | not_set                          | 100_00100.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xdd23  | not_set | 0xab0a    | not_set | not_set                          | 100_00101.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | 0xdf0e  | 0x4954    | not_set | not_set                          | 100_00110.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0x5ccf  | 0xb5ba  | 0xc0da    | not_set | not_set                          | 100_00111.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | not_set   | 0.1     | not_set                          | 100_01000.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xc2db  | not_set | not_set   | 0.1     | not_set                          | 100_01001.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | 0x8f76  | not_set   | 0.1     | not_set                          | 100_01010.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0x93e4  | 0x23ee  | not_set   | 0.1     | not_set                          | 100_01011.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | 0x875d    | 0.1     | not_set                          | 100_01100.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xc7d4  | not_set | 0x8ba6    | 0.1     | not_set                          | 100_01101.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | 0xae75  | 0x3396    | 0.1     | not_set                          | 100_01110.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0x44d4  | 0xe052  | 0xb6eb    | 0.1     | not_set                          | 100_01111.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | not_set   | not_set | 0x0c38,0xdbf2,0x5db1             | 100_10000.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0x7de7  | not_set | not_set   | not_set | 0xf0c6,0x6659,0xa5b5             | 100_10001.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | 0x4406  | not_set   | not_set | 0x012b,0x8a44                    | 100_10010.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0x387e  | 0x782c  | not_set   | not_set | 0xdf48,0x38a6,0x8057,0x60ca      | 100_10011.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | 0xaebf    | not_set | 0xf6a5,0x0789,0x8206,0x1850      | 100_10100.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0x5d2e  | not_set | 0xde72    | not_set | 0x3882,0x8e03,0xfb86,0x9794      | 100_10101.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | 0xd9e8  | 0xd25f    | not_set | 0x8ea2                           | 100_10110.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0x9207  | 0x386c  | 0xff9a    | not_set | 0x627c                           | 100_10111.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | not_set   | 0.1     | 0x727d,0xfb0e,0xcd07,0x2464      | 100_11000.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xf0ec  | not_set | not_set   | 0.1     | 0xb700,0xa266,0xda24,0x4203      | 100_11001.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | 0x74ac  | not_set   | 0.1     | 0x8b8b,0xde2e,0xdacc,0x0638      | 100_11010.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xc012  | 0xf1f1  | not_set   | 0.1     | 0xb6d9                           | 100_11011.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | not_set | 0xb28f    | 0.1     | 0xe68c                           | 100_11100.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xed7   | not_set | 0x8d83    | 0.1     | 0xe0aa,0x39a7                    | 100_11101.zip   |
        | blinky.bin  | not_set                      | not_set                      | not_set | 0x85d6  | 0xa886    | 0.1     | 0x9521                           | 100_11110.zip   |
        | blinky.bin  | not_set                      | not_set                      | 0xb168  | 0x8f6f  | 0xf777    | 0.1     | 0x63ff,0x3e83,0xbb3b,0xa48e      | 100_11111.zip   |
