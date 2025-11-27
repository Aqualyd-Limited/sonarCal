"""Re-writes Simrad raw files, datagram by datagram.

Use this script to test the sonarcal live feature, where it reads new
datagrams as they get added to a file.
"""
# /// script
# dependencies = [
#   "construct",
# ]
# ///

from time import sleep
from pathlib import Path
from construct import PaddedString, Timestamp, Bytes, Int32sl, Int64ul, this, Struct, StreamError

base_dir = Path(r'C:\Users\GavinMacaulay\OneDrive - Aqualyd Limited\Documents\Aqualyd\Projects'
                r'\2025-08 AZTI coding\example data')

raw_dir = base_dir/'CS90-raw'
out_dir = base_dir/'CS90-raw-replay'

out_dir.mkdir(parents=True, exist_ok=True)

raw_files = sorted(raw_dir.glob('*.raw'), key=lambda p: p.stem)

# Using Construct is nice, but we could do away with it for this simple case and
# have a script with no external dependencies.

dg_def =\
    Struct(
        'size' / Int32sl,
        'type' / PaddedString(4, 'ascii'),
        'timestamp' / Timestamp(Int64ul, 1e-7, 1600),
        'data' / Bytes(this.size-12),
        'size' / Int32sl
    )

# Delete all files in out_dir
for root, dirs, files in out_dir.walk(top_down=False):
    for name in files:
        (root / name).unlink()

for in_file in raw_files:
    out_file = out_dir / in_file.name
    with open(in_file, 'rb') as fin, open(out_file, 'wb') as fout:
        print(f'Rewriting {in_file.name}')
        try:
            while True:
                dg = dg_def.parse_stream(fin)
                dg_def.build_stream(dg, fout)

                # At end of ping force a flush to disk
                if dg['type'] == 'EOP0':
                    fout.flush()
                    print(f'  End of ping at {dg["timestamp"]}')
                    sleep(2.0)

        except StreamError:
            # end of file so pause a little to simulate the sonar taking a while to start
            # a new file
            sleep(0.5)
