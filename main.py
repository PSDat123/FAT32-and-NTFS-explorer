from FAT32 import FAT32
from NTFS import NTFS
from Shell import Shell

if __name__ == "__main__":
  vol = FAT32("D")
  shell = Shell(vol)
  shell.cmdloop()
