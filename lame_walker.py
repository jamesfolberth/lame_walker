"""
A simple script to walk a directory, call the system `lame` util on each MP3,
and copy the converted file to a clone directory.  It looks like `lame` uses
a single thread, so we'll use `multiprocessing` to run transcoding in parallel.
"""

import os, shutil, string
import subprocess
import multiprocessing as mp
import multiprocessing.queues # to subclass mp.Queue()
import queue
import curses
import argparse

# for debug/dev only
import time
from pprint import pprint
  
# For cross-platform colors in terminal
# https://pypi.python.org/pypi/colorama
# maybe use (built-in?) `curses`?

class _StateQueue(mp.queues.Queue):
  """
  A `put` to this queue will clear it and put a single item.
  A `get` to this queue will get a single item.
  """
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    self._state_lock = mp.Lock() # use our own lock so we don't goof up the
                                 # base queue's sync objects

  def put(self, *args, **kwargs):
    with self._state_lock:
      while not self.empty():
        #print('clearing queue')
        try:
          super().get(False)
        except:
          pass
      super().put(*args, **kwargs)
  
  def get(self, *args, **kwargs):
    with self._state_lock:
      return super().get(*args, **kwargs)

def StateQueue(maxsize=0):
  return _StateQueue(maxsize, ctx=mp.get_context())


class ConverterProducer(mp.Process):
  def __init__(self, args, files_q, info_qs=[]):
    super().__init__()
    
    self.args = args

    self.indir = args.indir
    self.outdir = args.outdir
    self.aindir = os.path.abspath(self.indir)
    self.aoutdir = os.path.abspath(self.outdir)

    self.files_q = files_q
    self.files_q_timeout = 0.05 # seconds

    self.info_qs = info_qs

    self.worker_states = {}

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

    self.do_curses = not (self.args.verbose or self.args.dry_run)

  def filenames(self):
    for dirpath, dirnames, filenames in os.walk(self.indir):
      if filenames: # only care if files exist in dir; don't care about dirnames
        relpath = os.path.relpath(dirpath, self.indir)
                
        # absolute paths
        #infilenames = list(map(lambda fn: os.path.join(self.aindir, relpath, fn), filenames))
        #outfilenames = list(map(lambda fn: os.path.join(self.aoutdir, relpath, fn), filenames))
        
        # relative paths
        infilenames = list(map(lambda fn: os.path.join(self.indir, relpath, fn), filenames))
        outfilenames = list(map(lambda fn: os.path.join(self.outdir, relpath, fn), filenames))
        
        yield {'newpath': os.path.join(self.aoutdir, relpath),
            'infilenames': infilenames, 'outfilenames': outfilenames}
    
    for _ in range(self.args.num_workers):
      yield None # sentinel

  def update_worker_states(self):
    # Try to get info from the workers' info queues
    for info_q in self.info_qs:
      info_item = None
      try:
        info_item = info_q.get(False)
        self.worker_states[info_item['pid']] = info_item['msg']
      except queue.Empty:
        pass
  
  def print_states(self):
    if not (self.args.verbose or self.args.dry_run):
      msgs = []
      for worker, state in self.worker_states.items():
        op = state.get('op', '')
        if op == 'mkdir':
          text = 'mkdir:\n  -->   {}'.format(state['newpath'])

        elif op == 'rm':
          text = 'removing failed file:\n  -->  {}'.format(state['file'])

        elif op == 'copy':
          max_len = max(len(state['infile']), len(state['outfile'])) # to right align
          text = 'copy:\n      {1:>{0}}\n  -->  {2:>{0}}'.format(
              max_len, state['infile'], state['outfile'])
        
        #TODO JMF 2017/04/29: get info from transcoder's pipe
        elif op == 'transcode':
          max_len = max(len(state['infile']), len(state['outfile'])) # to right align
          text = 'transcode:\n      {1:>{0}}\n  -->  {2:>{0}}'.format(
              max_len, state['infile'], state['outfile'])
        else:
          text = ''
        msgs.append((worker, text))
      
      msgs.sort(key=lambda t: t[0]) # sort by PID
      
      text = ''
      import time; text = 'time: '+str(time.time())+'\n'
      for msg in msgs:
        text += 'Worker {0:4d}:\n{1}\n\n'.format(*msg)
        
      # display with curses
      self.win.erase()
      try:
          self.win.addstr(text)
      except curses.error:
          pass
      self.win.refresh()


  def run(self):
    # curses stuff adapted from
    # https://github.com/python/cpython/blob/2.7/Demo/curses/repeat.py
    if self.do_curses:
      self.win = curses.initscr()

    try:
      # main loop
      for filenames in self.filenames():
        put_succeeded = False
        while not put_succeeded:
          # Try to put an item on the file queue, but don't block too long
          try: 
            self.files_q.put(filenames, True, self.files_q_timeout)
            put_succeeded = True
          except queue.Full as e: # we didn't put anything on the queue
            put_succeeded = False
          
          if self.do_curses:
            self.update_worker_states()
            self.print_states() 
      
      #TODO JMF 2017/04/29: keep printing info until all info_q are closed/see sentinel
      #     will need to make the workers send a sentinel back
    finally:
      if self.do_curses:
        curses.endwin()

class ConverterConsumer(mp.Process):
  def __init__(self, args, files_q, info_q=None):
    super().__init__()
    
    self.args = args
    self.files_q = files_q
    self.info_q = info_q
    
    # extension to use when we're still working on the output file
    self.extension = '.wrk'
  
  def run(self):
    image_ext = frozenset(['jpg', 'png'])

    while True:
      try:

        item = self.files_q.get(block=True)
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
                self.info_q.put({'pid': self.pid, 
                                 'msg': {'op': 'mkdir',
                                         'newpath': newpath
                                         }
                                 })
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
                self.info_q.put({'pid': self.pid,
                                 'msg': {'op': 'rm',
                                         'file': outf+self.extension
                                         }
                                 })
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
                self.info_q.put({'pid': self.pid,
                                 'msg': {'op': 'transcode',
                                         'infile': inf,
                                         'outfile': outf
                                         }
                                 })

                #TODO JMF 2017/04/25: if bitrate is less than target average bitrate, then 
                #                     don't transcode.
                
                #TODO JMF 2017/04/23: lame stuff
                #TODO JMF 2017/04/23: what's the best function to use here?
                #subprocess.call(['lame', '--quiet', '--abr', '160', '-b', '96', inf, outf_wrk])
                lame_args = ['lame']
                lame_args.extend(self.args.lame_args.split())
                lame_args.extend((inf, outf_wrk))
                subprocess.call(lame_args)
                
                #TODO JMF 2017/04/25: put file percentages on a Q to the producer to print?
                #proc = subprocess.Popen(lame_args, stdout=subprocess.PIPE)
                #for line in iter(proc.stdout.readline):
                #  print(line)
                
              elif ext.lower()[1:] in image_ext:
                if self.args.verbose or self.args.dry_run: print('copy'+base_msg)
                if self.args.dry_run: continue
                self.info_q.put({'pid': self.pid,
                                 'msg': {'op': 'copy',
                                         'infile': inf,
                                         'outfile': outf
                                         }
                                 })

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
  files_q = mp.Queue(args.queue_size)

  if args.dry_run: args.num_workers = 1 # want predictable output

  consumers = []
  info_qs = [] 
  for _ in range(args.num_workers):
    info_q = StateQueue(args.queue_size)
    info_qs.append(info_q)
    consumers.append(ConverterConsumer(args, files_q, info_q=info_q))
  
  producer = ConverterProducer(args, files_q, info_qs=info_qs)
  
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
  #parser.add_argument('--lame-args', type=str, default='--abr 160 -b 96',
      help='The optional arguments pased to `lame`.')

  args = parser.parse_args()

  main(args)

# vim: set sw=2 sts=2 ts=4:
