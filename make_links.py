# prep lame_walker input directory by making symlinks to ~/Music
import argparse
import os
import pathlib


def main(args):
    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(exist_ok=True)

    root = pathlib.Path('~/Music').expanduser()

    # read in file with directories
    with open(args.dirsfn, 'r') as f:
        dirs = []
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            dirs.append(pathlib.Path(line))

    # if needed, make any higher-level directories (== dirs other than the symlink)
    hlds = set()
    for d in dirs:
        if d.parent == root:
            continue

        hld = d.relative_to(root).parent
        hlds.add(hld)

    for hld in hlds:
        d = outdir/hld
        d.mkdir(exist_ok=True)

    # make links
    for d in dirs:
        l = outdir/d.relative_to(root)
        if l.exists():
            continue
        os.symlink(d, l)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('outdir', type=str)
    parser.add_argument('dirsfn', type=str)
    args = parser.parse_args()
    main(args)