"""
A simple script to walk a directory, call the system `lame` util on each MP3,
and copy the converted file to a clone directory.  It looks like `lame` uses
a single thread, so we'll use `multiprocessing` to run transcoding in parallel.
"""

import os, shutil, string
import subprocess
import multiprocessing as mp
import argparse

# for debug/dev only
import time
from pprint import pprint
  
# For cross-platform colors in terminal
# https://pypi.python.org/pypi/colorama

class ConverterProducer(mp.Process):
  def __init__(self, args, q):
    super().__init__()
    
    self.args = args

    self.indir = args.indir
    self.outdir = args.outdir
    self.aindir = os.path.abspath(self.indir)
    self.aoutdir = os.path.abspath(self.outdir)

    self.q = q

    self.checkArgs()

  def checkArgs(self):
    
    if not os.path.isdir(self.aindir):
      raise ValueError('The input directory does not exist.')

    if not os.path.isdir(self.aoutdir):
      os.makedirs(self.aoutdir)

    if os.path.samefile(self.aindir, self.aoutdir):
      #TODO JMF 2017/04/23: allow overwriting indir's files, or name `outdir`?
      raise ValueError('The input and output directory cannot be the '
          'same (for now).')

  def filenames(self):
    for dirpath, dirnames, filenames in os.walk(self.indir):
      if filenames: # only care if files exist in dir; don't care about dirnames
        relpath = os.path.relpath(dirpath, self.indir)
        
        infilenames = list(map(lambda fn: os.path.join(self.aindir, relpath, fn), filenames))
        outfilenames = list(map(lambda fn: os.path.join(self.aoutdir, relpath, fn), filenames))
        
        yield {'newpath': os.path.join(self.aoutdir, relpath),
            'infilenames': infilenames, 'outfilenames': outfilenames}
    
    for _ in range(self.args.num_workers):
      yield None # sentinel
  
  def run(self):
    for filenames in self.filenames():
      self.q.put(filenames)


class ConverterConsumer(mp.Process):
  def __init__(self, args, q):
    super().__init__()
    
    self.args = args
    self.q = q
    
    # extension to use when we're still working on the output file
    self.extension = '.wrk'
  
  def run(self):
    image_ext = frozenset(['jpg', 'png'])

    while True:
      try:

        item = self.q.get(block=True)
        if item is None: # sentinel
          return 

        if 'newpath' in item and 'infilenames' in item and 'outfilenames' in item:
          newpath = item['newpath']
          infilenames = item['infilenames']
          outfilenames = item['outfilenames']
          
          # make output dir if necessary
          if not os.path.isdir(newpath):
            msg = 'mkdir:\n  -->   {}'.format(newpath)
            if self.args.dry_run: print(msg)
            else:
              if not self.args.clean:
                if self.args.verbose: print(msg)
                os.makedirs(newpath)
          
          # loop over files
          for inf, outf in zip(infilenames, outfilenames):
            # skip if outfile already exists
            if os.path.isfile(outf): continue
            
            # we failed processing this one earlier; try again
            if os.path.isfile(outf+self.extension):
              msg = 'removing failed file:\n  -->  {}'.format(outf+self.extension)
              if self.args.clean or self.args.verbose or self.args.dry_run: 
                print(msg)
              if self.args.clean or not self.args.dry_run:
                os.unlink(outf+self.extension)
            
            # do work: transcode mp3; copy jpg and png
            max_len = max(len(inf), len(outf)) # to right align
            base_msg = ':\n       {1:>{0}}\n  -->  {2:>{0}}'.format(max_len, inf, outf)
            if self.args.clean: continue
            else:
              outf_wrk = outf+self.extension
              ext = os.path.splitext(outf)[1]
              
              if ext.lower()[1:] == 'mp3':
                #TODO JMF 2017/04/23: this is pretty sloppy; clean it up
                if self.args.verbose or self.args.dry_run: print('transcode'+base_msg)
                if self.args.dry_run: continue
                
                #TODO JMF 2017/04/23: lame stuff
                #TODO JMF 2017/04/23: what's the best function to use here?
                #subprocess.call(['lame', '--quiet', '--abr', '160', '-b', '96', inf, outf_wrk])
                lame_args = ['lame']
                lame_args.extend(self.args.lame_args.split())
                lame_args.extend((inf, outf_wrk))
                subprocess.call(lame_args)
                
              elif ext.lower()[1:] in image_ext:
                if self.args.verbose or self.args.dry_run: print('copy'+base_msg)
                if self.args.dry_run: continue
 
                shutil.copy2(inf, outf_wrk)
              
              else:
                continue # unrecognized file, so do nothing
              
              # if the hard part (transcode/copy) was a success, remove .wrk extension
              os.rename(outf_wrk, outf)
      
      except Exception as e:
        print(e)


#TODO JMF 2017/04/23: <Ctrl-C> grabber, so we can print warning to user then die?


def main(args):
  # initialize
  q = mp.Queue(args.queue_size)

  producer = ConverterProducer(args, q)
    
  if args.dry_run: args.num_workers = 1 # want predictable output

  consumers = []
  for _ in range(args.num_workers):
    consumers.append(ConverterConsumer(args, q))
  
  # start up processes
  producer.start()
  for consumer in consumers:
    consumer.start()
  
  # wait to finish
  for consumer in consumers:
    consumer.join()


if __name__ == '__main__':
  parser = argparse.ArgumentParser(
      description='Convert MP3 files from a directory tree to use average/'
          'variable bitrate and copy the files to a cloned directory.')

  # indir/outdir
  parser.add_argument('indir', type=str,
                    help='The directory of original MP3 files.')
  parser.add_argument('outdir', type=str,
                    help='The directory of output MP3 files.')
  
  # multiprocessing args
  parser.add_argument('--queue-size', type=int, default=2*mp.cpu_count(),
      help='The maximum number of items on the queue.')
  #parser.add_argument('--num-workers', type=int, default=mp.cpu_count(),
  parser.add_argument('--num-workers', type=int, default=2,
      help='The number of worker processes to run simultaneously.')
  
  # util args
  parser.add_argument('--clean', action='store_true',
      help='Clean up any "work" files that are left over from failed processing.')
  parser.add_argument('--dry-run', action='store_true',
      help='Do a dry run of the processing, printing files to be converted')
  parser.add_argument('--verbose', action='store_true',
      help='Be verbose in the processing')


  #TODO JMF 2017/04/23: lame parameters here, with sane defaults
  parser.add_argument('--lame-args', type=str, default='--quiet --abr 160 -b 96',
      help='The optional arguments pased to `lame`.')

  args = parser.parse_args()

  main(args)

# vim: set sw=2 sts=2 ts=4:
