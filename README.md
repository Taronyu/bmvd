# bmvd

This project aims to provide a battery monitoring daemon.

Currently the Victron Energy BMV-600S is supported. The daemon will spawn two threads, one for reading the monitor data from the serial port, and the second to provide a JSON output of the current readings via a simple HTTP web server.

## Installation

Currently only a recent Python 3 environment and the `pyserial` module for serial communication is required.

Copy the project files over to a directory of your choice and install the required module.

## Running the daemon

You can show the built-in help by specifiyng the `-h` option: `python3 bmvd.py -h`

The only mandatory argument is the serial port device to use for reading the monitor data. It is specified as a positional argument: `python3 bmvd.py /dev/ttyAMA0`

Note that the user running the program must have the proper permissions to access the serial port.

The default status page is available under `http://localhost:7070/bmv600s`

Please refer to the built-in help for additional information of available options.

## License

This project is licensed under the GPLv3. See the [license file](License.txt) for details.