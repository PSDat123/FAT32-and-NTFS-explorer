from FAT32 import FAT32
from NTFS import NTFS
from Shell import Shell
import os

if __name__ == "__main__":
  print("FIT HCMUS - CSC10007 - Operating System - FAT32 & NTFS project")
  print("----------------------------")
  print("* 21127243 - Phung Sieu Dat")
  print("* 21127296 - Dang Ha Huy")
  print("* 21127300 - Nguyen Cat Huy")
  print("----------------------------")
  volumes = [chr(x) + ":" for x in range(65, 91) if os.path.exists(chr(x) + ":")]
  print("Available volumes:")
  for i in range(len(volumes)):
    print(f"{i + 1}/", volumes[i])
  try:
    choice = int(input("Which volume to use: "))
  except Exception as e:
    print(f"[ERROR] {e}")
    exit()

  if choice <= 0 and choice > len(volumes):
    print("[ERROR] Invalid choice!")
    exit()
  print()
  
  volume_name = volumes[choice - 1]
  if FAT32.check_fat32(volume_name):
    vol = FAT32(volume_name)
  elif NTFS.check_ntfs(volume_name):
    vol = NTFS(volume_name)
  else:
    print("[ERROR] Unsupported volume type")
    exit()

  print(vol)
  shell = Shell(vol)
  shell.cmdloop()
