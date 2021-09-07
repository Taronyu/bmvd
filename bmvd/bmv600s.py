try:
    import serial
    _HAS_SERIAL = True
except ModuleNotFoundError:
    _HAS_SERIAL = False

import argparse
from contextlib import contextmanager
from enum import IntFlag


class AlarmReason(IntFlag):
    low_voltage = 1
    high_voltage = 2
    low_state_of_charge = 4


def _str_to_bool(value: str) -> bool:
    if str == "On":
        return True
    else:
        return False


_FIELD_NAMES = dict()
_FIELD_NAMES["V"] = ("voltage", int, "Voltage (mV)")
_FIELD_NAMES["I"] = ("current", int, "Current (mA)")
_FIELD_NAMES["CE"] = ("consumed_energy", int, "Consumed energy (mAh)")
_FIELD_NAMES["SOC"] = ("state_of_charge", int, "State of charge (promille)")
_FIELD_NAMES["TTG"] = ("time_to_go", int, "Time to go (min)")
_FIELD_NAMES["Alarm"] = ("alarm", _str_to_bool, "Alarm active")
_FIELD_NAMES["Relay"] = ("relay", _str_to_bool, "Relay active")
_FIELD_NAMES["AR"] = ("alarm_reason", int, "Alarm reason")
_FIELD_NAMES["BMV"] = ("bmv_model", str, "BMV model")
_FIELD_NAMES["FW"] = ("fw_version", str, "BMV firmware version")
_FIELD_NAMES["H1"] = ("deepest_discharge", int, "Deepest discharge (mAh)")
_FIELD_NAMES["H2"] = ("last_discharge", int, "Last discharge (mAh)")
_FIELD_NAMES["H3"] = ("average_discharge", int, "Average discharge (mAh)")
_FIELD_NAMES["H4"] = ("num_charge_cycles", int, "Number of charge cycles")
_FIELD_NAMES["H5"] = ("num_full_discharges", int, "Number of full discharges")
_FIELD_NAMES["H6"] = ("total_consumed", int, "Total consumed energy (mAh)")
_FIELD_NAMES["H7"] = ("min_battery_voltage", int,
                      "Minimum battery voltage (mV)")
_FIELD_NAMES["H8"] = ("max_battery_voltage", int,
                      "Maximum battery voltage (mV)")
_FIELD_NAMES["H9"] = ("days_since_last_full_charge", int,
                      "Number of days since last full charge")
_FIELD_NAMES["H10"] = ("num_auto_syncs", int,
                       "Number of automatic synchronizations")
_FIELD_NAMES["H11"] = ("num_low_voltage_alarms", int,
                       "Number of low voltage alarms", int)
_FIELD_NAMES["H12"] = ("num_high_voltage_alarms", int,
                       "Number of high voltage alarms")


def _get_field_value(name: str, value: str) -> tuple:
    meta = _FIELD_NAMES.get(name)
    if meta:
        return (meta[0], meta[1](value))
    else:
        return (name, value)


def has_serial_support() -> bool:
    return _HAS_SERIAL


@contextmanager
def open_serial_port(device: str):
    """Opens the specified serial port for reading with the correct settings
    for the Victron BMV-600S battery monitor.

    Parameters:
            device: The serial port device path

    Returns:
            (sp, err): Serial port handle and error if opening the port failed
    """
    try:
        sp = serial.Serial(device, 19200, timeout=5, xonxoff=True)
    except serial.SerialException as e:
        yield None, e
    else:
        try:
            yield sp, None
        finally:
            sp.close()


class BlockReader:
    "Class to extract blocks from byte buffers."
    _CHECKSUM_LABEL = b"Checksum"

    def __init__(self):
        "Initializes a new class instance."
        self._buffer = bytearray()

    def read(self, data: bytes):
        """Reads the given byte buffer into the internal buffer and tries to
        extract blocks.

        Parameters:
            data: Bytes to process

        Returns:
            List of extracted blocks or None.
        """
        if not data:
            return None

        result = []
        self._buffer.extend(data)
        while True:
            block = self._extract_block()
            if block:
                result.append(block)
            else:
                self._check_discard_buffer()
                break

        return result

    def _extract_block(self) -> dict:
        pos = self._buffer.find(BlockReader._CHECKSUM_LABEL)
        if pos == -1:
            return None

        blocklen = pos + len(BlockReader._CHECKSUM_LABEL) + 2
        if len(self._buffer) < blocklen:
            return None

        blockbuf = self._buffer[:blocklen]
        del self._buffer[:blocklen]

        if sum(blockbuf) % 256 != 0:
            return None

        del blockbuf[pos:blocklen]

        block = dict()
        lines = blockbuf.splitlines()
        for line in lines:
            text = line.decode("ascii", "replace")
            if text:
                BlockReader._parse_line_ex(text, block)

        return block

    def _check_discard_buffer(self, maxsize=1024):
        if len(self._buffer) >= maxsize:
            del self._buffer[:maxsize]

    def _parse_line_ex(line: str, block: dict):
        values = line.split('\t')
        if len(values) == 2:
            (name, value) = _get_field_value(values[0], values[1])
            block[name] = value


def _print_block(block: dict):
    for k, v in block.items():
        print("{0}: {1}".format(k, v))


def _read_data_file(filePath: str, reader: BlockReader):
    with open(filePath, "rb") as fin:
        while True:
            data = fin.read(64)
            if data:
                blocks = reader.read(data)
                for b in blocks:
                    _print_block(b)
            else:
                break


def main():
    ap = argparse.ArgumentParser(
        prog="bmv600s", description="read BMV-600S data files")
    ap.add_argument("filename", type=str, help="path to the data file to read")
    args = ap.parse_args()

    reader = BlockReader()
    _read_data_file(args.filename, reader)


if __name__ == "__main__":
    main()
