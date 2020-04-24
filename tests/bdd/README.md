# bdd-tests

## dfu.feature

The following environment variables must be exported to run the dfu.feature tests:

* `PCA10056_0` and `PCA10056_1`: Serial number of Jlink devices
    * `PCA10056_0`: Board used by `dfu usb-serial`, `dfu serial` and `dfu ble` tests.
    * `PCA10056_1`: Board used by `dfu ble` test.
* `PCA10059`: Serial number of usb interface.
    * Used by trigger interface test.
