# lame_walker.py

Walk a directory of `.mp3`, `.wav`, or `.m4a` files, and transcode each file with LAME, putting the
new file into a cloned directory. For `.mp3` and `.wav` files, `lame` is used; for `.m4a` files,
`faad` is used. The tool will also copy images (`.jpg`, `.png`, `.pdf`) into the new directory tree.

## Motiviation
I like to listen to music when I ride my bike, run, etc., so I keep a fair amount of music on my
phone. I got a new mobile phone without an SD card slot :(, so I have precious little storage on the
new phone. On my old phone, I had about 30 GB of music on an SD card, but I didn't want to remove a
bunch of songs from my collection.

This tool ameliorates the (too widespread) problem of not having an SD card to expand the music
storage of your mobile phone. With `lame_walker.py`, you can transcode your music files to `.mp3`
files that use a lower average variable bitrate. When I'm running, biking, etc., I don't need super
high-fidelity audio (I listen to a lot of black metal on cheap earbuds!), so we can pretty safely
use a lower bitrate, which results in significantly smaller `.mp3` files. Thus, I can store more
songs per unit of storage on my phone.

The prototypical call to `lame` to transcode an input `.mp3` to a lower bitrate is something like
```bash
lame --abr 160 -b 96 input.mp3 output.mp3
```
We can also use one of their presets:

```bash
lame --preset medium input.mp3 output.mp3
```

Or use the variable bit rate quality parameterization:

```bash
lame -V 7 input.mp3 output.mp3
```

`lame_walker.py` is simply a wrapper around `lame` (and `faad`) to walk an input directory and call
the transcoder in multiple processes using Python's `multiprocessing`
module. Using the default `--lame-arg` (`-V 7`), I transcoded a 20 GB directory tree to about 15 GB.

Instead of using `lame_walker.py`, transcoding files in a directory could also be done with `find`
and `xargs`. The following one-liner will transcode the
`.mp3`s in a directory **in place** using 16 processes.
```bash
find inoutdir -type f -name "*.mp3" -print0 | xargs -0r -P16 -n1 -I % bash -c 'lame -V 7 --quiet "%" "%.tmp" && mv "%.tmp" "%"'
```

But `lame_walker.py` shows a nice progress bar.
(It used to show bitrate histograms for the multiple workers in a curses display. This was neat, but
only marginally useful so I've rewritten the code with simplicity in mind.)


## Prerequisites
* `lame` for (`.mp3`, `.wav`) -> `.mp3` transcoding.
* `faad` for `.m4a` -> `.wav` transcoding (we then transcode the `.wav` to `.mp3` with `lame`)
* We use Python 3.6+ and the associated standard library

On Arch Linux, you can install `lame` and `faad` with `pacman -S lame faad`.

## Usage
To use the tool, put the files you want to transcode in a directory, say `original`,
for this example.  Let's say `original` looks like this:

```
original
+-- artist_1
|   +-- album_1
|   |   +-- track_1.mp3
|   |   +-- track_2.mp3
|   |   +-- cover.jpg
|   +-- album_2
|   |   +-- track_1.m4a
|   |   +-- track_2.m4a
|   |   +-- album_sleeve.pdf
+-- artist_2
|   +-- album_1
|   |   +-- track_1.mp3
```

To walk `original` and transcode the music files and copy images, run

```bash
python3 /path/to/lame_walker.py original/ resampled/
```

The argparse help is
```
usage: lame_walker.py [-h] [--num-workers NUM_WORKERS] [--lame-args LAME_ARGS] indir outdir

Convert MP3 files from a directory tree to use average/variable bitrate and copy the transcoded files to a cloned directory tree.

positional arguments:
  indir                 The directory of original MP3 files.
  outdir                The directory of output MP3 files.

optional arguments:
  -h, --help            show this help message and exit
  --num-workers NUM_WORKERS
                        The number of worker processes to run simultaneously.
  --lame-args LAME_ARGS
                        The optional arguments pased to `lame`.
```
