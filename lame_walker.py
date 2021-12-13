"""
A simple script to walk a directory tree and transcode (`lame`, `faad`) audio files into an output
tree.
"""
import argparse
import logging
import multiprocessing as mp
import os
import pathlib
import shutil
import subprocess

import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

LAME_EXE = 'lame'
LAME_EXT = ('.mp3', '.wav')
FAAD_EXE = 'faad'
FAAD_EXT = ('.m4a',)
TRANS_EXT = LAME_EXT + FAAD_EXT # transcodable extensions
IMAGE_EXT = ('.jpg', '.png', '.pdf')


logging.basicConfig(
    format="%(levelname)s:%(filename)s:%(lineno)d: %(message)s",
    level=logging.DEBUG,
)
log = logging.getLogger(__name__)


def worker_init():
    pass


def worker(work):
    ofn = work['ofn']
    if ofn.exists():
        work['returncode'] = 0  # kinda cheesy, but w/e
        return work

    ifn = work['ifn']
    if 'cmd' == work['action']:
        p = subprocess.run(work['args'], capture_output=True)

        work['returncode'] = p.returncode
        if 0 != p.returncode:
            work['stdout'] = p.stdout
            work['stderr'] = p.stderr

            msgf = "cmd failed (%d): %s"
            vals = [work['returncode'], ' '.join(work['args'])]
            for out in ('stdout','stderr'):
                if work[out]:
                    msgf = msgf + f'\n -> {out}: %s'
                    vals.append(work[out].decode())
            log.error(msgf, *vals)

    elif 'copy' == work['action']:
        shutil.copy2(ifn, ofn)
        work['returncode'] = 0  # similarly cheesy, as copy2 could raise

    else:
        raise RuntimeError(f"unknown action {work['action']}")

    return work


def main(args):
    # sanity check inputs
    indir = pathlib.Path(args.indir)
    if not indir.is_dir():
        raise ValueError(f"indir {args.indir} does not exist")

    outdir = pathlib.Path(args.outdir)
    if indir == outdir:
        raise ValueError(f"outdir cannot be the same as indir")

    outdir.mkdir(exist_ok=True)

    log.debug("Scanning input directory")
    # all directories (or links to dirs) in input
    all_dirs = []

    # all files to xcode/copy
    all_files = []

    for root, _, files in os.walk(indir, followlinks=True):
        root = pathlib.Path(root)

        if root != indir:
            dir = root.relative_to(indir)
            all_dirs.append(dir)

        for fn in files:
            fn = pathlib.Path(root/fn).relative_to(indir)
            all_files.append(fn)

    log.debug("Making output tree")
    for d in all_dirs:
        d = outdir/d
        d.mkdir(parents=True, exist_ok=True)

    # generate dicts describing the work to do
    def gen_work(all_files):
        for fn in all_files:
            work = {}
            ifn = indir / fn
            work['ifn'] = ifn

            ofn = outdir / fn
            if ifn.suffix in LAME_EXT:
                ofn = ofn.with_suffix('.mp3')
                work.update(
                    action='cmd',
                    ofn=ofn,
                    args=(LAME_EXE, '--quiet', *args.lame_args.split(), str(ifn), str(ofn)),
                )

            elif ifn.suffix in FAAD_EXT:
                ofn = ofn.with_suffix('.wav')
                work.update(
                    action='cmd',
                    ofn=ofn,
                    args=(FAAD_EXE, '--quiet', '-o', str(ofn), ifn),
                )

            else:
                work.update(ofn=ofn, action='copy')

            yield work

    log.debug("Transcoding")
    with mp.Pool(args.num_workers,
                 initializer=worker_init,
                 initargs=tuple()) as pool,\
         logging_redirect_tqdm():
        it = pool.imap_unordered(worker, gen_work(all_files), chunksize=1)
        it = tqdm.tqdm(it, total=len(all_files))
        for _ in it:
            pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Convert MP3 files from a directory tree to use average/"
                    "variable bitrate and copy the transcoded files to a cloned "
                    "directory tree.")

    parser.add_argument('indir', type=str,
                        help='The directory of original MP3 files.')
    parser.add_argument('outdir', type=str,
                        help='The directory of output MP3 files.')

    parser.add_argument('--num-workers', type=int, default=mp.cpu_count(),
                        help='The number of worker processes to run simultaneously.')

    #parser.add_argument('--lame-args', type=str, default='--abr 128 -b 64',
    #parser.add_argument('--lame-args', type=str, default='--preset medium',
    parser.add_argument('--lame-args', type=str, default='-V 7',
                        help='The optional arguments pased to `lame`.')

    args = parser.parse_args()
    main(args)
