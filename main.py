from FAT32 import FAT32
from NTFS import NTFS
from Shell import Shell
import os

if __name__ == "__main__":
  drives = [chr(x) + ":" for x in range(65, 91) if os.path.exists(chr(x) + ":")]
  print("Available volumes:")
  for i in range(len(drives)):
    print(f"{i + 1}/", drives[i])
  try:
    choice = int(input("Which volume to use: "))
  except Exception as e:
    print(f"[ERROR] {e}")
    exit()

  if choice <= 0 and choice > len(drives):
    print("[ERROR] Invalid choice!")
    exit()
  
  print()
  vol = FAT32(drives[choice - 1])
  print(vol)
  shell = Shell(vol)
  shell.cmdloop()
