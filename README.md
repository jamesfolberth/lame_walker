# lame_walker
Walk a directory of mp3 files, transcoding each with LAME into a cloned directory.

```
usage: lame_walker.py [-h] [--queue-size QUEUE_SIZE]
                      [--num-workers NUM_WORKERS] [--clean] [--dry-run]
                      [--verbose] [--lame-args LAME_ARGS]
                      indir outdir

Convert MP3 files from a directory tree to use average/variable bitrate and
copy the files to a cloned directory.

positional arguments:
  indir                 The directory of original MP3 files.
  outdir                The directory of output MP3 files.

optional arguments:
  -h, --help            show this help message and exit
  --queue-size QUEUE_SIZE
                        The maximum number of items on the queue.
  --num-workers NUM_WORKERS
                        The number of worker processes to run simultaneously.
  --clean               Clean up any "work" files that are left over from
                        failed processing.
  --dry-run             Do a dry run of the processing, printing files to be
                        converted
  --verbose             Be verbose in the processing
  --lame-args LAME_ARGS
                        The optional arguments pased to `lame`.
```
