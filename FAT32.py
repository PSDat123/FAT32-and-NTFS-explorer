from enum import Flag, auto
from datetime import datetime
from itertools import chain

class Attribute(Flag):
    READ_ONLY = auto()
    HIDDEN = auto()
    SYSTEM = auto()
    VOLLABLE = auto()
    DIRECTORY = auto()
    ARCHIVE = auto()

class FAT:
  def __init__(self, data) -> None:
    self.rawData = data
    self.elements = []
    for i in range(0, len(self.rawData), 4):
      self.elements.append(int.from_bytes(self.rawData[i:i + 4], byteorder='little'))
    
class RDETentry:
  def __init__(self, data) -> None:
    self.rawData = data
    self.flag = data[0xB:0xC]
    self.isSubEntry = False
    self.isDeleted = False
    self.isEmpty = False
    self.isLabel = False
    self.attr = Attribute(0)
    self.size = 0
    self.dateCreated = 0
    self.lastAccessed = 0
    self.dateUpdated = 0
    if self.flag == b'\x0f':
      self.isSubEntry = True

    if not self.isSubEntry:
      self.name = self.rawData[:0x8]
      self.ext = self.rawData[0x8:0xB]
      if self.name[:1] == b'\xe5':
        self.isDeleted = True
      if self.name[:1] == b'\x00':
        self.isEmpty = True
        self.name = ""
        return
      
      self.attr = Attribute(int.from_bytes(self.flag, byteorder='little'))
      if Attribute.VOLLABLE in self.attr:
        self.name = self.name.decode()
        self.isLabel = True
        return

      self.timeCreatedRaw = int.from_bytes(self.rawData[0xD:0x10], byteorder='little')
      self.dateCreatedRaw = int.from_bytes(self.rawData[0x10:0x12], byteorder='little')
      self.lastAccessedRaw = int.from_bytes(self.rawData[0x12:0x14], byteorder='little')

      self.timeUpdatedRaw = int.from_bytes(self.rawData[0x16:0x18], byteorder='little')
      self.dateUpdatedRaw = int.from_bytes(self.rawData[0x18:0x1A], byteorder='little')

      h = (self.timeCreatedRaw & 0b111110000000000000000000) >> 19
      m = (self.timeCreatedRaw & 0b000001111110000000000000) >> 13
      s = (self.timeCreatedRaw & 0b000000000001111110000000) >> 7
      ms =(self.timeCreatedRaw & 0b000000000000000001111111)
      year = 1980 + ((self.dateCreatedRaw & 0b1111111000000000) >> 9)
      mon = (self.dateCreatedRaw & 0b0000000111100000) >> 5
      day = self.dateCreatedRaw & 0b0000000000011111

      self.dateCreated = datetime(year, mon, day, h, m, s, ms)

      year = 1980 + ((self.lastAccessedRaw & 0b1111111000000000) >> 9)
      mon = (self.lastAccessedRaw & 0b0000000111100000) >> 5
      day = self.lastAccessedRaw & 0b0000000000011111

      self.lastAccessed = datetime(year, mon, day)

      h = (self.timeUpdatedRaw & 0b1111100000000000) >> 11
      m = (self.timeUpdatedRaw & 0b0000011111100000) >> 5
      s = (self.timeUpdatedRaw & 0b0000000000011111) * 2
      year = 1980 + ((self.dateUpdatedRaw & 0b1111111000000000) >> 9)
      mon = (self.dateUpdatedRaw & 0b0000000111100000) >> 5
      day = self.dateUpdatedRaw & 0b0000000000011111

      self.dateUpdated = datetime(year, mon, day, h, m, s)

      self.startCluster = int.from_bytes(self.rawData[0x14:0x16][::-1] + self.rawData[0x1A:0x1C][::-1], byteorder='big') 
      self.size = int.from_bytes(self.rawData[0x1C:0x20], byteorder='little')

    else:
      self.index = self.rawData[0]
      # print(self.rawData)
      # print("Sub entry", self.index)
      self.name = b""
      for i in chain(range(0x1, 0xB), range(0xE, 0x1A), range(0x1C, 0x20)):
        self.name += int.to_bytes(self.rawData[i], 1, byteorder='little')
        if self.name.endswith(b"\xff\xff"):
          self.name = self.name[:-2]
          break
      self.name = self.name.decode('utf-16le')

class RDET:
  def __init__(self, data) -> None:
    self.rawData = data
    self.entries = []
    for i in range(0, len(data), 32):
      self.entries.append(RDETentry(self.rawData[i: i + 32]))
  
  def getFileListing(self):
    filename = ""
    filelist = []
    for i in range(len(self.entries)):
      if self.entries[i].isEmpty or self.entries[i].isDeleted or self.entries[i].isLabel: 
        filename = ""
        continue
      if self.entries[i].isSubEntry: 
        filename = self.entries[i].name + filename
      else:
        if not len(filename):
          filename = self.entries[i].name.strip().decode() + "." + self.entries[i].ext.decode()
        filelist.append((filename.strip("\x00"), self.entries[i]))
        filename = ""
    return filelist
  # def getList(self):
  #   filename = ""
  #   for i in range(len(self.entries)):
  #     if self.entries[i].isEmpty or self.entries[i].isDeleted or self.entries[i].isLabel: 
  #       continue
  #     if self.entries[i].isSubEntry: 
  #       filename = self.entries[i].name + filename
  #     else:
  #       print(filename)
  #       filename = ""

class FAT32:
  importantInfo = [
    "Bytes Per Sector",
    "Sectors Per Cluster", 
    "Reserved Sectors", 
    "Sectors Per FAT",
    "No. Copies of FAT",
    "No. Sectors In Volume",
    "Starting Cluster of RDET",
    "Starting Sector of Data",
    "FAT Name"
  ]
  def __init__(self, name) -> None:
    self.name = name
    try:
      self.fd = open(r'\\.\%s:' % self.name, 'rb')
    except FileNotFoundError:
      print(f"[ERROR] No volume named {name}")
      exit()
    except PermissionError:
      print("[ERROR] Permission denied, try again as admin/root")
      exit()
    except Exception as e:
      print(e)
      print("[ERROR] Unknown error occurred")
      exit() 
    
    try:
      self.bootSectorRaw = self.fd.read(0x200)
      self.bootSector = {}
      self.__extractBootSector()
      if self.bootSector["FAT Name"] != b"FAT32   ":
        raise Exception("Not FAT32")
      self.bootSector["FAT Name"] = self.bootSector["FAT Name"].decode()
      SB = self.bootSector['Reserved Sectors']
      SF = self.bootSector["Sectors Per FAT"]
      NF = self.bootSector["No. Copies of FAT"]
      SC = self.bootSector["Sectors Per Cluster"]
      BS = self.bootSector["Bytes Per Sector"]
      self.bootSectorReservedRaw = self.fd.read(BS * (SB - 1))
      
      FATsize = BS * SF
      self.FAT = []
      for _ in range(NF):
        self.FAT.append(FAT(self.fd.read(FATsize)))

      self.RDET = None
      if self.bootSector["Starting Cluster of RDET"] == 2:
        self.RDET = RDET(self.fd.read(BS * SC))
      elif self.bootSector["Starting Cluster of RDET"] > 2:
        self.RDET = RDET(self.fd.read(BS * SC * (self.bootSector["Starting Cluster of RDET"] - 1))[-BS * SC:])
      else:
        raise Exception("Hold on, Something ain't right")
      
      
      # print(SC * (self.bootSector["Starting Cluster of RDET"] - 2))
      # print(self.FATraw[0][:40])
      # print(self.FATraw[1][:40])
      # print(len(self.RDET))
      # print(self.RDET[:512])
      # print(self.bootSector['Reserved Sectors'] + FATsize * 2)
      # self.RDETraw = self

    except Exception as e:
      print(f"[ERROR] {e}")
      exit()
    
  def __extractBootSector(self):
    self.bootSector['Jump_Code'] = self.bootSectorRaw[:3]
    self.bootSector['OEM_ID'] = self.bootSectorRaw[3:0xB]
    self.bootSector['Bytes Per Sector'] = int.from_bytes(self.bootSectorRaw[0xB:0xD], byteorder='little')
    self.bootSector['Sectors Per Cluster'] = int.from_bytes(self.bootSectorRaw[0xD:0xE], byteorder='little')
    self.bootSector['Reserved Sectors'] = int.from_bytes(self.bootSectorRaw[0xE:0x10], byteorder='little')
    self.bootSector['No. Copies of FAT'] = int.from_bytes(self.bootSectorRaw[0x10:0x11], byteorder='little')
    self.bootSector['Media Descriptor'] = self.bootSectorRaw[0x15:0x16]
    self.bootSector['Sectors Per Track'] = int.from_bytes(self.bootSectorRaw[0x18:0x1A], byteorder='little')
    self.bootSector['No. Heads'] = int.from_bytes(self.bootSectorRaw[0x1A:0x1C], byteorder='little')
    self.bootSector['No. Sectors In Volume'] = int.from_bytes(self.bootSectorRaw[0x20:0x24], byteorder='little')
    self.bootSector['Sectors Per FAT'] = int.from_bytes(self.bootSectorRaw[0x24:0x28], byteorder='little')
    self.bootSector['Flags'] = int.from_bytes(self.bootSectorRaw[0x28:0x2A], byteorder='little')
    self.bootSector['FAT32 Version'] = self.bootSectorRaw[0x2A:0x2C]
    self.bootSector['Starting Cluster of RDET'] = int.from_bytes(self.bootSectorRaw[0x2C:0x30], byteorder='little')
    # self.bootSector['Sector Number of the FileSystem Information Sector'] = self.bootSectorRaw[0x30:0x32]
    self.bootSector['Sector Number of BackupBoot'] = self.bootSectorRaw[0x32:0x34]
    self.bootSector['FAT Name'] = self.bootSectorRaw[0x52:0x5A]
    self.bootSector['Executable Code'] = self.bootSectorRaw[0x5A:0x1FE]
    self.bootSector['Signature'] = self.bootSectorRaw[0x1FE:0x200]
    self.bootSector['Starting Sector of Data'] = self.bootSector['Reserved Sectors'] + self.bootSector['No. Copies of FAT'] * self.bootSector['Sectors Per FAT']

  def printAll(self):
    print("Volume name:", self.name)
    print("Volume information:")
    for key in self.bootSector:
      print(f"{key}: {self.bootSector[key]}")

  def printImportant(self):

    print("Volume name:", self.name)
    print("Volume information:")
    for key in FAT32.importantInfo:
      print(f"{key}: {self.bootSector[key]}")

  def getDir(self, dir=""):
    if dir == "":
      filelist = self.RDET.getFileListing()
      ret = []
      for file in filelist:
        obj = {}
        obj["Flags"] = file[1].attr.value
        obj["Date Modified"] = file[1].dateUpdated
        obj["Size"] = file[1].size
        obj["Name"] = file[0]
        ret.append(obj)
      return ret
    return None

  def __str__(self) -> str:
    s = ""
    s += "Volume name: " + self.name
    s += "\nVolume information:\n"
    for key in FAT32.importantInfo:
      s += f"{key}: {self.bootSector[key]}\n"
    return s

  def __del__(self):
    if getattr(self, "fd", None):
      print("Closing Volume")
      self.fd.close()
