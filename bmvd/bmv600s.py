try:
    import serial
    _HAS_SERIAL = True
except ModuleNotFoundError:
    _HAS_SERIAL = False

import argparse
import threading
from contextlib import contextmanager
from enum import IntFlag
from typing import Any, Callable
from collections import deque

from serial.serialutil import SerialException


class AlarmReason(IntFlag):
    low_voltage = 1
    high_voltage = 2
    low_state_of_charge = 4


def _as_int(value: str) -> int:
    return int(value) if value else 0


def _as_bool(value: str) -> bool:
    return value == "On"


def _as_alarm_str(value: str) -> str:
    if value:
        value = int(value)
        alarms = [str(alarm) for alarm in AlarmReason if value & alarm]
        if alarms:
            return "|".join(alarms)

    return ""


class FieldMetadata:
    def __init__(self, name: str, converter: Callable[[str], Any]) -> None:
        self.name = name
        self._converter = converter

    def get_value(self, value: str):
        if self._converter:
            return self._converter(value)
        else:
            return value


DATA_FIELDS = dict()
DATA_FIELDS["V"] = FieldMetadata("voltage", _as_int)
DATA_FIELDS["I"] = FieldMetadata("current", _as_int)
DATA_FIELDS["CE"] = FieldMetadata("consumed_energy", _as_int)
DATA_FIELDS["SOC"] = FieldMetadata("state_of_charge", _as_int)
DATA_FIELDS["TTG"] = FieldMetadata("time_to_go", _as_int)
DATA_FIELDS["Alarm"] = FieldMetadata("alarm", _as_bool)
DATA_FIELDS["Relay"] = FieldMetadata("relay", _as_bool)
DATA_FIELDS["AR"] = FieldMetadata("alarm_reason", _as_alarm_str)
DATA_FIELDS["BMV"] = FieldMetadata("bmv_model", None)
DATA_FIELDS["FW"] = FieldMetadata("fw_version", None)
DATA_FIELDS["H1"] = FieldMetadata("deepest_discharge", _as_int)
DATA_FIELDS["H2"] = FieldMetadata("last_discharge", _as_int)
DATA_FIELDS["H3"] = FieldMetadata("average_discharge", _as_int)
DATA_FIELDS["H4"] = FieldMetadata("num_charge_cycles", _as_int)
DATA_FIELDS["H5"] = FieldMetadata("num_full_discharges", _as_int)
DATA_FIELDS["H6"] = FieldMetadata("total_consumed", _as_int)
DATA_FIELDS["H7"] = FieldMetadata("min_battery_voltage", _as_int)
DATA_FIELDS["H8"] = FieldMetadata("max_battery_voltage", _as_int)
DATA_FIELDS["H9"] = FieldMetadata("days_since_last_full_charge", _as_int)
DATA_FIELDS["H10"] = FieldMetadata("num_auto_syncs", _as_int)
DATA_FIELDS["H11"] = FieldMetadata("num_low_voltage_alarms", _as_int)
DATA_FIELDS["H12"] = FieldMetadata("num_high_voltage_alarms", _as_int)


def _get_field(name: str, value: str) -> tuple:
    field = DATA_FIELDS.get(name)
    if field:
        name = field.name
        value = field.get_value(value)

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
    sp = serial.Serial(device, 19200, timeout=5, xonxoff=True)
    try:
        yield sp
    finally:
        sp.close()


class BlockReader:
    "Class to extract blocks from byte buffers."
    _CHECKSUM_LABEL = b"Checksum"

    def __init__(self):
        "Initializes a new class instance."
        self._buffer = bytearray()

    def reset(self):
        "Clears the current buffer."
        self._buffer.clear()

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
            (name, value) = _get_field(values[0], values[1])
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


class SerialReaderThread(threading.Thread):
    def __init__(self, device: str):
        super().__init__()
        self.name = "SerialReaderThread"
        self.daemon = False
        self.stop_event = threading.Event()
        self._device = device
        self._lock = threading.Lock
        self._blocks = deque(maxlen=4)
        self._reader = BlockReader()

    def stop(self):
        print("Stopping the serial port reader")
        self.stop_event.set()

    def run(self):
        print("Starting the serial port reader")
        self._reader.reset()

        try:
            with open_serial_port(self._device) as sp:
                while True:
                    if self.stop_event.is_set():
                        break

                    data = sp.read(64)
                    if data:
                        self._process_data(data)
        except SerialException as ex:
            print("Failed to read serial data: {0}".format(ex))

    def _process_data(self, data) -> None:
        blocks = self._reader.read(data)
        if not blocks:
            return

        with self._lock:
            self._blocks.append(blocks)

    def take_blocks(self) -> list:
        with self._lock:
            blocks = list(self._blocks)
            self._blocks.clear()
            return blocks


def main():
    ap = argparse.ArgumentParser(
        prog="bmv600s", description="read BMV-600S data files")
    ap.add_argument("-f", "--file", dest="use_file", action="store_true",
                    help="open a file instead of a serial port")
    ap.add_argument("filename", type=str, help="path to the data file to read")
    args = ap.parse_args()

    if args.use_file:
        reader = BlockReader()
        _read_data_file(args.filename, reader)
    else:
        thread = SerialReaderThread(args.filename)
        thread.start()


if __name__ == "__main__":
    main()
