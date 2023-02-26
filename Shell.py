import cmd
import re
from FAT32 import FAT32

class Shell(cmd.Cmd):
  intro = "Welcome to Shelby the pseudo-shell! Type help or ? to list the commands.\n"
  prompt = ""
  def __init__(self, volume: FAT32) -> None:
    super(Shell, self).__init__()
    self.vol = volume
    self.cwd = []
    self.__updatePrompt()

  def __updatePrompt(self):
    Shell.prompt = f'┌──(Tommy@Shelby)-[{self.vol.name + chr(92) + chr(92).join(self.cwd)}]\n└─$ '

  def do_ls(self, arg):
    try:
      filelist = self.vol.getDir(arg)
      print(f"{'Mode':<10}  {'LastWriteTime':>20}  {'Length':>15}  {'Name'}")
      print(f"{'────':<10}  {'─────────────':>20}  {'──────':>15}  {'────'}")
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

        print(f"{flagstr:<10}  {str(file['Date Modified']):>20}  {file['Size'] if file['Size'] else '':>15}  {file['Name']}")
    except Exception as e:
      print(f"[ERROR] {e}")

  def do_cd(self, arg):
    try:
      self.vol.changeDir(arg)
      dirs = re.sub(r"[/\\]+", r"\\", arg).split("\\")
      for d in dirs:
        if d == "..":
          self.cwd.pop()
        elif d != ".":
          self.cwd.append(d)
      self.__updatePrompt()
    except Exception as e:
      print(f"[ERROR] {e}")

  def do_tree(self, arg):
    print(self.vol.name + '\\' + '\\'.join(self.cwd))
    # pos = -1 -> First entry, pos = 1 -> Last entry
    def printTree(entry, prefix="", last=False):
      print(prefix + ("└─" if last else "├─") + entry["Name"])
      # check if is archive
      if entry["Flags"] & 0b100000:
        return
      
      self.vol.changeDir(entry["Name"])
      entries = self.vol.getDir()
      l = len(entries)
      for i in range(l):
        if entries[i]["Name"] in (".", ".."):
          continue
        prefixChar = "   " if last else "│  "
        printTree(entries[i], prefix + prefixChar, i == l - 1)
      self.vol.changeDir("..")

    try:
      entries = self.vol.getDir()
      l = len(entries)
      for i in range(l):
        if entries[i]["Name"] in (".", ".."):
          continue
        printTree(entries[i], "", i == l - 1)
    except Exception as e:
      print(f"[ERROR] {e}")
  
  def do_cat(self, arg):
    if arg == "":
      print(f"[ERROR] No path provided")
      return
    try:
      print(self.vol.getFileContent(arg).decode())
    except UnicodeDecodeError:
      print(f"[ERROR] Not a text file")
    except Exception as e:
      print(f"[ERROR] {e}")

  def do_bye(self, arg):
    print('Thank you for using Shelby')
    self.close()
    return True
  
  def close(self):
    if self.vol:
      del self.vol
      self.vol = None