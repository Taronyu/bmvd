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


class DataField:
    "This class defines metadata for a BMV data field."

    def __init__(self, name: str, description: str):
        """Constructs a new class instance.

        Parameters:
            name: Parameter name
            description: Optional parameter description
        """
        self.name = name
        self.description = description


class IntDataField(DataField):
    "This class provides metadata for an integer field."

    def convert(self, value: str) -> int:
        if value:
            return int(value)
        else:
            return 0


class BoolDataField(DataField):
    "This class provides metadata for a boolean field."

    def convert(self, value: str) -> bool:
        return True if value == "On" else False


class StringDataField(DataField):
    "This class provides metadata for a string field."

    def convert(self, value: str) -> str:
        return value


class AlarmReasonDataField(DataField):
    "This class provides metadata for a alarm reason field."

    def convert(self, value: str) -> str:
        if not value:
            return "None"

        value = int(value)
        if value == 0:
            return "None"

        alarms = []
        for alarm in AlarmReason:
            if value & alarm:
                alarms.append(str(alarm))

        return "|".join(alarms)


DATA_FIELDS = dict()
DATA_FIELDS["V"] = IntDataField("voltage", "Voltage (mV)")
DATA_FIELDS["I"] = IntDataField("current", "Current (mA)")
DATA_FIELDS["CE"] = IntDataField("consumed_energy", "Consumed energy (mAh)")
DATA_FIELDS["SOC"] = IntDataField(
    "state_of_charge", "State of charge (promille)")
DATA_FIELDS["TTG"] = IntDataField("time_to_go", "Time to go (min)")
DATA_FIELDS["Alarm"] = BoolDataField("alarm", "Alarm active")
DATA_FIELDS["Relay"] = BoolDataField("relay", "Relay active")
DATA_FIELDS["AR"] = AlarmReasonDataField("alarm_reason", "Alarm reason")
DATA_FIELDS["BMV"] = StringDataField("bmv_model", "BMV model")
DATA_FIELDS["FW"] = StringDataField("fw_version", "BMV firmware version")
DATA_FIELDS["H1"] = IntDataField(
    "deepest_discharge", "Deepest discharge (mAh)")
DATA_FIELDS["H2"] = IntDataField("last_discharge", "Last discharge (mAh)")
DATA_FIELDS["H3"] = IntDataField(
    "average_discharge", "Average discharge (mAh)")
DATA_FIELDS["H4"] = IntDataField(
    "num_charge_cycles", "Number of charge cycles")
DATA_FIELDS["H5"] = IntDataField(
    "num_full_discharges", "Number of full discharges")
DATA_FIELDS["H6"] = IntDataField(
    "total_consumed", "Total consumed energy (mAh)")
DATA_FIELDS["H7"] = IntDataField("min_battery_voltage",
                                 "Minimum battery voltage (mV)")
DATA_FIELDS["H8"] = IntDataField("max_battery_voltage",
                                 "Maximum battery voltage (mV)")
DATA_FIELDS["H9"] = IntDataField("days_since_last_full_charge",
                                 "Number of days since last full charge")
DATA_FIELDS["H10"] = IntDataField("num_auto_syncs",
                                  "Number of automatic synchronizations")
DATA_FIELDS["H11"] = IntDataField("num_low_voltage_alarms",
                                  "Number of low voltage alarms")
DATA_FIELDS["H12"] = IntDataField("num_high_voltage_alarms",
                                  "Number of high voltage alarms")


def _get_field_value(name: str, value: str) -> tuple:
    field = DATA_FIELDS.get(name)
    if field:
        return (field.name, field.convert(value))
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
