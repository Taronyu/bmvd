try:
	import serial
	_HAS_SERIAL = True
except ModuleNotFoundError:
	_HAS_SERIAL = False

import argparse
from contextlib import contextmanager

def has_serial_support() -> bool:
	return _HAS_SERIAL

@contextmanager
def open_serial_port(device: str):
	"""Opens the specified serial port for reading with the correct settings for the Victron BMV-600S battery monitor.

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
	_CHECKSUM_LABEL = b"Checksum"

	def __init__(self):
		self._buffer = bytearray()

	def read(self, data: bytes):
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

	def _extract_block(self):
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
				BlockReader._parse_line(text, block)

		return block

	def _check_discard_buffer(self, maxsize=1024):
		if len(self._buffer) >= maxsize:
			del self._buffer[:maxsize]

	def _parse_line(line: str, block: dict):
		values = line.split('\t')
		if len(values) == 2:
			block[values[0]] = values[1]

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
	ap = argparse.ArgumentParser(prog="bmv600s", description="read bmv600s data files")
	ap.add_argument("filename", type=str, help="path to the data file to read")
	args = ap.parse_args()

	reader = BlockReader()
	_read_data_file(args.filename, reader)

if __name__ == "__main__":
	main()
