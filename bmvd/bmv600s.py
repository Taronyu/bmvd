try:
    import serial
    _HAS_SERIAL = True
except ModuleNotFoundError:
    _HAS_SERIAL = False

import argparse
from contextlib import contextmanager
from enum import IntFlag
from dataclasses import InitVar, dataclass, field
from typing import Type


class AlarmReason(IntFlag):
    low_voltage = 1
    high_voltage = 2
    low_state_of_charge = 4


@dataclass
class MonitorData:
    source_name: str
    display_name: str
    description: str


@dataclass
class IntMonitorData(MonitorData):
    value: int = field(init=False)
    raw_value: InitVar[str]

    def __post_init__(self, raw_value: str) -> None:
        self.value = int(raw_value) if raw_value else 0


@dataclass
class BoolMonitorData(MonitorData):
    value: bool = field(init=False)
    raw_value: InitVar[str]

    def __post_init__(self, raw_value: str) -> None:
        self.value = raw_value == "On"


@dataclass
class AlarmReasonMonitorData(MonitorData):
    value: str = field(init=False)
    raw_value: InitVar[int]

    def __post_init__(self, raw_value: str) -> None:
        if not str:
            self.value = "None"

        int_value = int(raw_value)
        alarms = []
        for alarm in AlarmReason:
            if int_value & alarm:
                alarms.append(str(alarm))

        self.value = "|".join(alarms) if alarms else "None"


@dataclass
class StringMonitorData(MonitorData):
    value: str


class FieldMetadata:
    def __init__(self, source_name: str, display_name: str,
                 data_type: Type[MonitorData],
                 description: str = None) -> None:
        self.source_name = source_name
        self.display_name = display_name
        self.description = description
        self.data_type = data_type

    def create_instance(self, raw_value: str) -> MonitorData:
        return self.data_type(self.source_name, self.display_name,
                              self.description, raw_value)


DATA_FIELDS = dict()
DATA_FIELDS["V"] = FieldMetadata(
    "V", "voltage", IntMonitorData, "Voltage (mV)")
DATA_FIELDS["I"] = FieldMetadata(
    "I", "current", IntMonitorData, "Current (mA)")
DATA_FIELDS["CE"] = FieldMetadata(
    "CE", "consumed_energy", IntMonitorData, "Consumed energy (mAh)")
DATA_FIELDS["SOC"] = FieldMetadata(
    "SOC", "state_of_charge", IntMonitorData, "State of charge (promille)")
DATA_FIELDS["TTG"] = FieldMetadata(
    "TTG", "time_to_go", IntMonitorData, "Time to go (min)")
DATA_FIELDS["Alarm"] = FieldMetadata(
    "Alarm", "alarm", BoolMonitorData, "Alarm active")
DATA_FIELDS["Relay"] = FieldMetadata(
    "Relay", "relay", BoolMonitorData, "Relay active")
DATA_FIELDS["AR"] = FieldMetadata(
    "AR", "alarm_reason", AlarmReasonMonitorData, "Alarm reason")
DATA_FIELDS["BMV"] = FieldMetadata(
    "BMV", "bmv_model", StringMonitorData, "BMV model")
DATA_FIELDS["FW"] = FieldMetadata(
    "FW", "fw_version", StringMonitorData, "BMV firmware version")
DATA_FIELDS["H1"] = FieldMetadata(
    "H1", "deepest_discharge", IntMonitorData, "Deepest discharge (mAh)")
DATA_FIELDS["H2"] = FieldMetadata(
    "H2", "last_discharge", IntMonitorData, "Last discharge (mAh)")
DATA_FIELDS["H3"] = FieldMetadata(
    "H3", "average_discharge", IntMonitorData, "Average discharge (mAh)")
DATA_FIELDS["H4"] = FieldMetadata(
    "H4", "num_charge_cycles", IntMonitorData, "Number of charge cycles")
DATA_FIELDS["H5"] = FieldMetadata(
    "H5", "num_full_discharges", IntMonitorData, "Number of full discharges")
DATA_FIELDS["H6"] = FieldMetadata(
    "H6", "total_consumed", IntMonitorData, "Total consumed energy (mAh)")
DATA_FIELDS["H7"] = FieldMetadata(
    "H7", "min_battery_voltage", IntMonitorData, "Minimum battery voltage (mV)")
DATA_FIELDS["H8"] = FieldMetadata(
    "H8", "max_battery_voltage", IntMonitorData, "Maximum battery voltage (mV)")
DATA_FIELDS["H9"] = FieldMetadata(
    "H9", "days_since_last_full_charge", IntMonitorData, "Number of days since last full charge")
DATA_FIELDS["H10"] = FieldMetadata(
    "H10", "num_auto_syncs", IntMonitorData, "Number of automatic synchronizations")
DATA_FIELDS["H11"] = FieldMetadata(
    "H11", "num_low_voltage_alarms", IntMonitorData, "Number of low voltage alarms")
DATA_FIELDS["H12"] = FieldMetadata(
    "H12", "num_high_voltage_alarms", IntMonitorData, "Number of high voltage alarms")


def _get_field(name: str, value: str) -> MonitorData:
    field = DATA_FIELDS.get(name)
    if field:
        return field.create_instance(value)
    else:
        return None


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
            field = _get_field(values[0], values[1])
            if field:
                block[field.source_name] = field


def _print_block(block: dict):
    for _, v in block.items():
        print("{0}: {1}".format(v.display_name, v.value))


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
