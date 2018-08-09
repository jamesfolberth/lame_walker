# lame_walker.py
Walk a directory of `.mp3`, `.wav`, or `.m4a` files, and transcode each file with LAME,
putting the new file into a cloned directory.  For `.mp3` and `.wav` files, we use
`lame`; for `.m4a` files, we use `faad`.  The tool will also copy images (`.jpg`, `.png`)
into the new directory tree.

## Motiviation
I like to listen to music when I ride my bike, run, etc., so I keep a fair amount
of music on my phone.  I got a new mobile phone without an SD card slot :(, so I
have precious little storage on the new phone.  On my old phone, I had about 30
GB of music on an SD card, but I didn't want to remove a bunch of songs from my
collection.

This tool ameliorates the (widespread) problem of not having an SD card to expand
the music storage of your mobile phone.  With `lame_walker.py`, you can transcode your
music files to `.mp3` files that use a lower average variable bitrate.  When I'm
running, biking, etc., I don't need super high-fidelity audio (I also listen on
cheap earbuds!), so we can pretty safely use a lower bitrate, which results in
significantly smaller `.mp3` files.  Thus, I can store more songs per unit of
storage on my phone.

The prototypical call to `lame` to transcode an input `.mp3` to a lower bitrate
is something like

```bash
lame --abr 160 -b 96 input.mp3 output.mp3
```
We can also use one of their presets:

```bash
lame --preset medium input.mp3 output.mp3
```

`lame_walker.py` is simply a wrapper around `lame` (and `faad`) to walk an input
directory and call the transcoder in multiple processes using Python's `multiprocessing`
module.  Using the default `--lame-arg` (`--preset medium`), I transcoded a 20 GB
directory tree to about 15 GB.


## Prerequisites
* `lame` for (`.mp3`, `.wav`) -> `.mp3` transcoding.
* `faad` for `.m4a` -> `.wav` transcoding (we then transcode the `.wav` to `.mp3` with `lame`)
* We use Python 3 and the associated standard library

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
|   |   +-- album_art.jpg
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

By default, this will use `curses` to display bitrate histograms coming from `lame`.
This is useful if you're trying to target an average bitrate, are tweaking parameters,
etc.  This display looks something like

```
Percent complete:  0.0%  (0 of 5)
----------------------------------
Worker 3542:
transcode:
        original/artist_1/track_1.mp3
  -->  resampled/artist_1/track_1.mp3
   547/6752   ( 8%)|    0:00/    0:07|    0:00/    0:07|   23.891x|    0:06
 32 [  0]
 40 [  0]
 48 [  0]
 56 [  0]
 64 [  0]
 80 [  0]
 96 [  0]
112 [  0]
128 [194] %%****************************************************************
160 [203] %%%%%****************************************************************
192 [ 49] %%***************
224 [ 67] %%%%*******************
256 [ 29] %*********
320 [  5] **
------02:42--------------------------------------------------------------------
   kbps        LR    MS  %     long switch short %
  165.9        5.9  94.1        76.3  13.0  10.7

Worker 3543:
transcode:
        original/artist_2/track_1.mp3
  -->  resampled/artist_2/track_1.mp3
  1010/2876   (35%)|    0:01/    0:02|    0:01/    0:02|   26.085x|    0:01
 32 [   0]
 40 [   0]
 48 [   0]
 56 [   0]
 64 [   0]
 80 [   0]
 96 [   0]
112 [  88] %%***********
128 [ 394] %%%%%%%%%************************************************
160 [ 475] %%%%%%%%%%%%%%%%****************************************************
192 [  29] %%%**
224 [   7] %*
256 [  15] %%%
320 [   2] %
--------------------------00:48------------------------------------------------
   kbps        LR    MS  %     long switch short %
  146.4       21.4  78.6        95.2   2.8   2.0
```


The argparse help is
```
usage: lame_walker.py [-h] [--queue-size QUEUE_SIZE]
                      [--num-workers NUM_WORKERS] [--clean] [--dry-run]
                      [--verbose] [--get-exts] [--lame-args LAME_ARGS]
                      [--disptime DISPTIME]
                      indir outdir
 
Convert MP3 files from a directory tree to use average/variable bitrate and
copy the transcoded files to a cloned directory tree.
 
positional arguments:
  indir                 The directory of original MP3 files.

  outdir                The directory of output MP3 files.
 
optional arguments:
  -h, --help            show this help message and exit
  --queue-size QUEUE_SIZE
                        The maximum number of items on the queue.
  --num-workers NUM_WORKERS
                        The number of worker processes to run simultaneously.
  --clean               Clean up any "work" files that are left over from
                        failed processing.
  --dry-run             Do a dry run of the processing, printing files to be
                        converted.
  --verbose             Don't use curses, but be verbose in the processing.
  --get-exts            Walk the input directory and print all unique file
                        extensions.
  --lame-args LAME_ARGS
                        The optional arguments pased to `lame`.
  --disptime DISPTIME   The time between screen updates, which also overrides
                        the `--disptime` argument passed in --lame-args for
                        `lame`.
```
