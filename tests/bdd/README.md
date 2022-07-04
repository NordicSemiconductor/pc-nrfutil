# bdd-tests

## dfu.feature

The following environment variables can be exported to run the dfu.feature tests:

* `PCA10056_0` and `PCA10056_1`: Serial number of Jlink devices.
    * `PCA10056_0`: Board used by `dfu usb-serial`, `dfu serial` and `dfu ble` tests.
    * `PCA10056_1`: Board used by `dfu ble` test.
* `PCA10059`: Serial number of usb interface.
    * Used by trigger interface test.
* `NRFUTIL`: Path to nrfutil.
	* Used to program the devices.

If no devices are exported the first devices found will be used.
If no nrfutil is exported the nrfutil installed will be used.
