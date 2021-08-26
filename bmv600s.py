import argparse

def print_block(block):
	for line in block:
		print(line)
	print()

def load_data_file(filePath: str, parser, bufsize=1024):
	counter = 0
	with open(filePath, "rb") as fin:
		while True:
			data = fin.read(bufsize)
			if data:
				for b in parser.process(data):
					print_block(b)
			else:
				break

class StreamParser:
	_CHECKSUM_LABEL = b"Checksum"

	def __init__(self):
		self._buffer = bytearray()

	def process(self, data: bytes):
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
		# Find the checksum label
		pos = self._buffer.find(StreamParser._CHECKSUM_LABEL)
		if pos == -1:
			return None

		# Total block length
		# Checksum label length: len(label) + 1 tab + 1 byte
		blocklen = pos + len(StreamParser._CHECKSUM_LABEL) + 2
		if len(self._buffer) < blocklen:
			return None

		# Remove the block memory
		blockbuf = self._buffer[:blocklen]
		del self._buffer[:blocklen]

		# Validate the block (checksum)
		if sum(blockbuf) % 256 != 0:
			return None

		# Remove the checksum block
		del blockbuf[pos:blocklen]

		# Split the lines
		lines = blockbuf.splitlines()
		return [l.decode("ascii", "replace") for l in lines if l]

	def _check_discard_buffer(self, maxsize=1024):
		if len(self._buffer) >= maxsize:
			del self._buffer[:maxsize]

def main():
	ap = argparse.ArgumentParser(prog="bmv600s", description="Read Victron BMV-600s serial data")
	ap.add_argument("device", metavar="DEVICE", type=str,
					help="device name to use")
	ap.add_argument("-s", "--single", action="store_true",
					help="read only one data block and exit")
	ap.add_argument("-f", "--file", dest="open_file", action="store_true",
					help="read a data file and exit")
	args = ap.parse_args()

	sp = StreamParser()

	if args.open_file:
		load_data_file(args.device, sp)

if __name__ == "__main__":
	main()
