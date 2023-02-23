from FAT32 import FAT32

class Shell:
  def __init__(self, volume: FAT32) -> None:
    self.vol = volume
  def interactive(self):
    print(self.vol)
    self.ls()
    # while(True):
    #   cmd = input(">")
    #   if cmd == "ls":
    #     self.vol.RDET.getList()
  def ls(self, dir=""):
    filelist = self.vol.getDir(dir)
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
