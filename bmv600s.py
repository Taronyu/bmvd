import argparse

def load_data_file(filePath: str, parser):
	with open(filePath, "rb") as fin:
		while True:
			line = fin.readline()
			if line:
				parser.append_line(line)
			else:
				break

class BlockParser:
	_CHECKSUM_LABEL = b"Checksum"

	def __init__(self):
		self._lines = []
		self._block_count = 0

	def append_line(self, line: bytes):
		if not line:
			return

		line = line.strip()
		if not line:
			return

		self._lines.append(line)

		if line.startswith(BlockParser._CHECKSUM_LABEL):
			self._extract_block()

	def _extract_block(self):
		if self._is_checksum_ok():
			self._lines.pop() # remove checksum block
			for line in self._lines:
				text = line.decode("ascii", "replace")
				print(text.upper())
			print()

			self._block_count += 1

		self._lines.clear()

	def _is_checksum_ok(self) -> bool:
		_sum = 0
		for line in self._lines:
			# include stripped \r\n in the calculation
			_sum = _sum + 0x0d + 0x0a + sum(line)

		return _sum % 256 == 0

def main():
	ap = argparse.ArgumentParser(prog="bmv600s", description="Read Victron BMV-600s serial data")
	ap.add_argument("device", metavar="DEVICE", type=str,
					help="device name to use")
	ap.add_argument("-s", "--single", action="store_true",
					help="read only one data block and exit")
	ap.add_argument("-f", "--file", dest="open_file", action="store_true",
					help="read a data file and exit")
	args = ap.parse_args()

	bp = BlockParser()

	if args.open_file:
		load_data_file(args.device, bp)

if __name__ == "__main__":
	main()
