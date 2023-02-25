import cmd
from FAT32 import FAT32

class Shell(cmd.Cmd):
  intro = "Welcome to Shelby the pseudo-shell! Type help or ? to list the commands.\n"
  cwd = []
  prompt = ""
  def __init__(self, volume: FAT32) -> None:
    super(Shell, self).__init__()
    self.vol = volume
    Shell.cwd.append(self.vol.name + ":\\")
    self.__updatePrompt()

  def __updatePrompt(self):
    Shell.prompt = f"┌──(Tommy@Shelby)-[{''.join(Shell.cwd)}]\n└─$ "

  def do_ls(self, arg):
    try:
      filelist = self.vol.getDir(arg)
      print(f"{'Flags':<11}{'Date Modified':<22}{'Size':<12}{'Name':<10}")
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

        print(f"{flagstr:<11}{str(file['Date Modified']):<22}{file['Size']:<12}{file['Name']:<10}")
    except Exception as e:
      print(f"[ERROR] {e}")

  def do_cd(self, arg):
    try:
      self.vol.changeDir(arg)
      dirs = arg.replace("/", "\\").strip("\\").split("\\")
      # print(dirs)
      
      for d in dirs:
        if d == "..":
          Shell.cwd.pop()
        elif d != ".":
          Shell.cwd.append(d + "\\")
        self.__updatePrompt()
    except Exception as e:
      print(f"[ERROR] {e}")

  def do_tree(self, arg):
    pass
  
  def do_cat(self, arg):
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