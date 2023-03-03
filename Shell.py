import cmd
from typing import Union
from FAT32 import FAT32
from NTFS import NTFS
class Shell(cmd.Cmd):
  intro = "Welcome to Shelby the pseudo-shell! Type help or ? to list the commands.\n"
  prompt = ""
  def __init__(self, volume: Union[FAT32, NTFS]) -> None:
    super(Shell, self).__init__()
    self.vol = volume
    self.__update_prompt()

  def __update_prompt(self):
    Shell.prompt = f'┌──(Tommy@Shelby)-[{self.vol.get_cwd()}]\n└─$ '
  
  def do_cwd(self, arg):
    print(self.vol.get_cwd())
  
  def do_ls(self, arg):
    try:
      filelist = self.vol.get_dir(arg)
      print(f"{'Mode':<10}  {'Sector':>10}  {'LastWriteTime':<20}  {'Length':>15}  {'Name'}")
      print(f"{'────':<10}  {'──────':>10}  {'─────────────':<20}  {'──────':>15}  {'────'}")
      for file in filelist:
        flags = file['Flags']
        flagstr = list("-------")
        if flags & 0b1:
          flagstr[-1] = 'r'
        if flags & 0b10:
          flagstr[-2] = 'h'
        if flags & 0b100:
          flagstr[-3] = 's'
        if flags & 0b1000:
          flagstr[-4] = 'v'
        if flags & 0b10000:
          flagstr[-5] = 'd'
        if flags & 0b100000:
          flagstr[-6] = 'a'
        flagstr = "".join(flagstr)

        print(f"{flagstr:<10}  {file['Sector']:>10}  {str(file['Date Modified']):<20}  {file['Size'] if file['Size'] else '':>15}  {file['Name']}")
    except Exception as e:
      print(f"[ERROR] {e}")

  def do_cd(self, arg):
    try:
      self.vol.change_dir(arg)
      self.__update_prompt()
    except Exception as e:
      print(f"[ERROR] {e}")

  def do_tree(self, arg):
    def print_tree(entry, prefix="", last=False):
      print(prefix + ("└─" if last else "├─") + entry["Name"])
      # check if is archive
      if entry["Flags"] & 0b100000:
        return
      
      self.vol.change_dir(entry["Name"])
      entries = self.vol.get_dir()
      l = len(entries)
      for i in range(l):
        if entries[i]["Name"] in (".", ".."):
          continue
        prefix_char = "   " if last else "│  "
        print_tree(entries[i], prefix + prefix_char, i == l - 1)
      self.vol.change_dir("..")

    cwd = self.vol.get_cwd()
    try:
      if arg != "":
        self.vol.change_dir(arg)
        print(self.vol.get_cwd())
      else:
        print(cwd)
      entries = self.vol.get_dir()
      l = len(entries)
      for i in range(l):
        if entries[i]["Name"] in (".", ".."):
          continue
        print_tree(entries[i], "", i == l - 1)
    except Exception as e:
      print(f"[ERROR] {e}")
    finally:
      self.vol.change_dir(cwd)

  def do_cat(self, arg):
    if arg == "":
      print(f"[ERROR] No path provided")
      return
    try:
      print(self.vol.get_text_file(arg))
    except Exception as e:
      print(f"[ERROR] {e}")

  def do_echo(self, arg):
    print(arg) # lol

  def do_fsstat(self, arg):
    print(self.vol)
    
  def do_bye(self, arg):
    print('Thank you for using Shelby! See you next time...')
    self.close()
    return True
  
  def close(self):
    if self.vol:
      del self.vol
      self.vol = None