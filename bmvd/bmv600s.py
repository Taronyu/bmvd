try:
    import serial
    _HAS_SERIAL = True
except ModuleNotFoundError:
    _HAS_SERIAL = False

import argparse
import dataclasses
import threading

from contextlib import contextmanager
from enum import IntFlag
from dataclasses import dataclass
from serial.serialutil import SerialException


class AlarmReason(IntFlag):
    NONE = 0
    LOW_VOLTAGE = 1
    HIGH_VOLTAGE = 2
    LOW_STATE_OF_CHARGE = 4


@dataclass
class MonitorData:
    voltage: int = 0
    current: int = 0
    consumed_energy: int = 0
    state_of_charge: int = 0
    time_to_go: int = 0
    alarm: bool = False
    relay: bool = False
    alarm_reason: str = ""
    model_name: str = ""
    firmware_version: str = ""

    deepest_discharge: int = 0
    last_discharge: int = 0
    average_discharge: int = 0
    num_charge_cycles: int = 0
    num_full_discharges: int = 0
    total_consumed: int = 0
    min_battery_voltage: int = 0
    max_battery_voltage: int = 0
    days_since_last_full_charge: int = 0
    num_auto_syncs: int = 0
    num_low_voltage_alarms: int = 0
    num_high_voltage_alarms: int = 0

    def set_value(self, key: str, value: str) -> None:
        if key == "V":
            self.voltage = MonitorData.value_as_int(value)
        elif key == "I":
            self.current = MonitorData.value_as_int(value)
        elif key == "CE":
            self.consumed_energy = MonitorData.value_as_int(value)
        elif key == "SOC":
            self.state_of_charge = MonitorData.value_as_int(value)
        elif key == "TTG":
            self.time_to_go = MonitorData.value_as_int(value)
        elif key == "Alarm":
            self.alarm = MonitorData.value_as_bool(value)
        elif key == "Relay":
            self.relay = MonitorData.value_as_bool(value)
        elif key == "AR":
            self.alarm_reason = MonitorData.value_as_alarm_str(value)
        elif key == "BMV":
            self.model_name = value
        elif key == "FW":
            self.firmware_version = value
        elif key == "H1":
            self.deepest_discharge = MonitorData.value_as_int(value)
        elif key == "H2":
            self.last_discharge = MonitorData.value_as_int(value)
        elif key == "H3":
            self.average_discharge = MonitorData.value_as_int(value)
        elif key == "H4":
            self.num_charge_cycles = MonitorData.value_as_int(value)
        elif key == "H5":
            self.num_full_discharges = MonitorData.value_as_int(value)
        elif key == "H6":
            self.total_consumed = MonitorData.value_as_int(value)
        elif key == "H7":
            self.min_battery_voltage = MonitorData.value_as_int(value)
        elif key == "H8":
            self.max_battery_voltage = MonitorData.value_as_int(value)
        elif key == "H9":
            self.days_since_last_full_charge = MonitorData.value_as_int(value)
        elif key == "H10":
            self.num_auto_syncs = MonitorData.value_as_int(value)
        elif key == "H11":
            self.num_low_voltage_alarms = MonitorData.value_as_int(value)
        elif key == "H12":
            self.num_high_voltage_alarms = MonitorData.value_as_int(value)
        else:
            raise KeyError("Unsupported field key '{0}'".format(key))

    def from_dict(self, values: dict) -> None:
        # Current data
        self.voltage = MonitorData.value_as_int(values.get("V"))
        self.current = MonitorData.value_as_int(values.get("I"))
        self.consumed_energy = MonitorData.value_as_int(values.get("CE"))
        self.state_of_charge = MonitorData.value_as_int(values.get("SOC"))
        self.time_to_go = MonitorData.value_as_int(values.get("TTG"))
        self.alarm = MonitorData.value_as_bool(values.get("Alarm"))
        self.relay = MonitorData.value_as_bool(values.get("Relay"))
        self.alarm_reason = MonitorData.value_as_alarm_str(values.get("AR"))
        self.model_name = values.get("BMV")
        self.firmware_version = values.get("FW")
        # Historical data
        self.deepest_discharge = MonitorData.value_as_int(values.get("H1"))
        self.last_discharge = MonitorData.value_as_int(values.get("H2"))
        self.average_discharge = MonitorData.value_as_int(values.get("H3"))
        self.num_charge_cycles = MonitorData.value_as_int(values.get("H4"))
        self.num_full_discharges = MonitorData.value_as_int(values.get("H5"))
        self.total_consumed = MonitorData.value_as_int(values.get("H6"))
        self.min_battery_voltage = MonitorData.value_as_int(values.get("H7"))
        self.max_battery_voltage = MonitorData.value_as_int(values.get("H8"))
        self.days_since_last_full_charge = MonitorData.value_as_int(
            values.get("H9"))
        self.num_auto_syncs = MonitorData.value_as_int(values.get("H10"))
        self.num_low_voltage_alarms = MonitorData.value_as_int(
            values.get("H11"))
        self.num_high_voltage_alarms = MonitorData.value_as_int(
            values.get("H12"))

    @staticmethod
    def value_as_int(value: str) -> int:
        return int(value) if value else 0

    @staticmethod
    def value_as_bool(value: str) -> bool:
        return value == "On"

    @staticmethod
    def value_as_alarm_str(value: str) -> str:
        if value:
            value = int(value)
            alarms = [alarm.name for alarm in AlarmReason if value & alarm]
            if alarms:
                return "|".join(alarms)

        return AlarmReason.NONE.name


def has_serial_support() -> bool:
    return _HAS_SERIAL


@contextmanager
def open_serial_port(device: str):
    """Opens the specified serial port for reading with the correct settings
    for the Victron BMV-600S battery monitor.

    Parameters:
            device: The serial port device path

    Returns:
            sp: Serial port handle
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
        self._values = MonitorData()

    def reset(self):
        "Clears the current buffer."
        self._buffer.clear()
        self._values = MonitorData()

    @property
    def monitor_data(self) -> MonitorData:
        return self._values

    def read(self, data: bytes) -> int:
        """Reads the given byte buffer into the internal buffer and tries to
        extract blocks.

        Parameters:
            data: Bytes to process

        Returns:
            Number of extracted blocks.
        """
        counter = 0
        if not data:
            return counter

        self._buffer.extend(data)
        while True:
            if self._extract_block():
                counter += 1
            else:
                self._check_discard_buffer()
                break

        return counter

    def _extract_block(self) -> bool:
        pos = self._buffer.find(BlockReader._CHECKSUM_LABEL)
        if pos == -1:
            return False

        blocklen = pos + len(BlockReader._CHECKSUM_LABEL) + 2
        if len(self._buffer) < blocklen:
            return False

        blockbuf = self._buffer[:blocklen]
        del self._buffer[:blocklen]

        if sum(blockbuf) % 256 != 0:
            return False

        # Remove the checksum part
        del blockbuf[pos:blocklen]

        lines = blockbuf.splitlines()
        for line in lines:
            text = line.decode("ascii", "replace")
            self._parse_line_ex(text)

        return True

    def _check_discard_buffer(self, maxsize=1024) -> None:
        if len(self._buffer) >= maxsize:
            del self._buffer[:maxsize]

    def _parse_line_ex(self, line: str) -> None:
        if not line:
            return

        values = line.split('\t')
        if len(values) == 2:
            try:
                self._values.set_value(values[0], values[1])
            except KeyError as ex:
                print("Failed to set value: {0}", ex)


def _print_data(data: dict) -> None:
    for k, v in data.items():
        print("{0} = {1}".format(k, v))


def _read_data_file(filePath: str, reader: BlockReader):
    with open(filePath, "rb") as fin:
        while True:
            data = fin.read(64)
            if data:
                if reader.read(data) > 0:
                    _print_data(reader.monitor_data.__dict__)
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
        self._data = MonitorData()
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
        if self._reader.read(data) > 0:
            with self._lock:
                self._data = dataclasses.replace(self._reader.monitor_data)

    def copy_current_data(self) -> MonitorData:
        with self._lock:
            return dataclasses.replace(self._data)


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
