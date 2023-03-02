from enum import Flag, auto
from datetime import datetime
class NTFSAttribute(Flag):
    READ_ONLY = auto()
    HIDDEN = auto()
    SYSTEM = auto()
    VOLLABLE = auto()
    DIRECTORY = auto()
    ARCHIVE = auto()
    DEVICE = auto()
    NORMAL = auto()
    TEMPORARY = auto()
    SPARSE_FILE = auto()
    REPARSE_POINT = auto()
    COMPRESSED = auto()
    OFFLINE = auto()
    NOT_INDEXED = auto()
    ENCRYPTED = auto()

def as_datetime(timestamp):
  return datetime.fromtimestamp((timestamp - 116444736000000000) // 10000000)
class MFTRecord:
  def __init__(self, data) -> None:
    self.raw_data = data
    self.file_id = int.from_bytes(self.raw_data[0x2C:0x30], byteorder='little')
    # if self.file_id < 39:
    #   raise Exception("Skip this entry")
    self.flag = self.raw_data[0x16]
    standard_info_start = int.from_bytes(self.raw_data[0x14:0x16], byteorder='little')
    standard_info_size = int.from_bytes(self.raw_data[standard_info_start + 4:standard_info_start + 8], byteorder='little')
    self.standard_info = {}
    self.__parse_standard_info(standard_info_start)
    file_name_start = standard_info_start + standard_info_size
    file_name_size = int.from_bytes(self.raw_data[file_name_start + 4:file_name_start + 8], byteorder='little')
    self.file_name = {}
    self.__parse_file_name(file_name_start)
    data_start = file_name_start + file_name_size
    data_sig = self.raw_data[data_start:data_start + 4]
    if data_sig[0] == 64:
      data_start += int.from_bytes(self.raw_data[data_start + 4:data_start + 8], byteorder='little')
    
    data_sig = self.raw_data[data_start:data_start + 4]
    self.data = {}
    if data_sig[0] == 128:
      self.__parse_data(data_start)
      # print(self.raw_data[data_start:data_start+200])
  
  def __parse_data(self, start):
    pass

  def __parse_file_name(self, start):
    sig = int.from_bytes(self.raw_data[start:start + 4], byteorder='little')
    if sig != 0x30:
      raise Exception("Skip this entry")
    
    # header = self.raw_data[start:start + 0x10]
    size = int.from_bytes(self.raw_data[start + 0x10:start + 0x14], byteorder='little')
    offset = int.from_bytes(self.raw_data[start + 0x14: start + 0x16], byteorder='little')
    body = self.raw_data[start + offset: start + offset + size]
    
    self.file_name["parent_id"] = int.from_bytes(body[:6], byteorder='little')
    name_length = body[64]
    self.file_name["long_name"] = body[66:66 + name_length * 2].decode('utf-16le')  # unicode
    # print(name, self.file_name['parent_id'], self.file_id, self.standard_info[])

  def __parse_standard_info(self, start):
    sig = int.from_bytes(self.raw_data[start:start + 4], byteorder='little')
    if sig != 0x10:
      raise Exception("Something Wrong!")
    offset = int.from_bytes(self.raw_data[start + 20:start + 21], byteorder='little')
    size = int.from_bytes(self.raw_data[start + 16:start + 19], byteorder='little')
    begin = start + offset
    self.standard_info["created_time"] = as_datetime(int.from_bytes(self.raw_data[begin:begin + 8], byteorder='little'))
    self.standard_info["last_modified_time"] = as_datetime(int.from_bytes(self.raw_data[begin + 16:begin + 24], byteorder='little'))
    self.standard_info["flags"] = NTFSAttribute(int.from_bytes(self.raw_data[begin + 32:begin + 36], byteorder='little') & 0xFFFF)
    # .value -> int
    # status = int.from_bytes(self.raw_data[begin + 32:begin + 36], byteorder='little')
  

class MFTFile:
  def __init__(self, data: bytes) -> None:
    self.raw_data = data
    self.info_offset = int.from_bytes(self.raw_data[0x14:0x16], byteorder='little')
    self.info_len = int.from_bytes(self.raw_data[0x3C:0x40], byteorder='little')
    self.file_name_offset = self.info_offset + self.info_len
    self.file_name_len = int.from_bytes(self.raw_data[0x9C:0xA0], byteorder='little')
    self.data_offset = self.file_name_offset + self.file_name_len
    self.data_len = int.from_bytes(self.raw_data[0x104:0x108], byteorder='little')
    self.size_sector = (int.from_bytes(self.raw_data[0x118:0x120], byteorder='little') + 1) * 8

class NTFS:
  important_info = [
    "OEM_ID",
    "Serial Number",
    "Bytes Per Sector",
    "Sectors Per Cluster", 
    "Reserved Sectors",
    "No. Sectors In Volume",
    "First Cluster of $MFT",
    "First Cluster of $MFTMirr",
    "MFT record size"
  ]
  def __init__(self, name: str) -> None:
    self.name = name
    self.cwd = [self.name]
    try:
      self.fd = open(r'\\.\%s' % self.name, 'rb')
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
      self.boot_sector_raw = self.fd.read(0x200)
      self.boot_sector = {}
      self.__extract_boot_sector()

      if self.boot_sector["OEM_ID"] != b'NTFS    ':
        raise Exception("Not NTFS")
      self.boot_sector["OEM_ID"] = self.boot_sector["OEM_ID"].decode()
      self.boot_sector['Serial Number'] = hex(self.boot_sector['Serial Number'] & 0xFFFFFFFF)[2:].upper()
      self.boot_sector['Serial Number'] = self.boot_sector['Serial Number'][:4] + "-" + self.boot_sector['Serial Number'][4:]
      # self.SB = self.boot_sector['Reserved Sectors']
      self.SC = self.boot_sector["Sectors Per Cluster"]
      self.BS = self.boot_sector["Bytes Per Sector"]

      self.record_size = self.BS * 2
      self.mft_offset = self.boot_sector['First Cluster of $MFT']
      # print(self.mft_offset * self.SC * self.BS)
      self.fd.seek(self.mft_offset * self.SC * self.BS)
      self.mft_file = MFTFile(self.fd.read(self.record_size))
      self.mft_record = []
      for _ in range(2, self.mft_file.size_sector, 2):
        dat = self.fd.read(self.record_size)
        if dat[:4] == b"FILE":
          try:
            self.mft_record.append(MFTRecord(dat))
          except Exception as e:
            print(e)
            pass
        # break

      # 1024
      # self.boot_sector = {}
      # self.__extractboot_sector()
      # if self.boot_sector["FAT Name"] != b"FAT32   ":
      #   raise Exception("Not FAT32")
      # self.boot_sector["FAT Name"] = self.boot_sector["FAT Name"].decode()
      # self.SB = self.boot_sector['Reserved Sectors']
      # self.SF = self.boot_sector["Sectors Per FAT"]
      # self.NF = self.boot_sector["No. Copies of FAT"]
      # self.SC = self.boot_sector["Sectors Per Cluster"]
      # self.BS = self.boot_sector["Bytes Per Sector"]
      # self.boot_sector_reserved_raw = self.fd.read(self.BS * (self.SB - 1))

      # FAT_size = self.BS * self.SF
      # self.FAT: list[FAT] = []
      # for _ in range(self.NF):
      #   self.FAT.append(FAT(self.fd.read(FAT_size)))

      # self.DET = {}

      # start = self.boot_sector["Starting Cluster of RDET"]
      # self.DET[start] = RDET(self.get_all_cluster_data(start))
      # self.RDET = self.DET[start]
  
    except Exception as e:
      print(f"[ERROR] {e}")
      exit()
  def __extract_boot_sector(self):
    self.boot_sector['Jump_Code'] = self.boot_sector_raw[:3]
    self.boot_sector['OEM_ID'] = self.boot_sector_raw[3:0xB]
    self.boot_sector['Bytes Per Sector'] = int.from_bytes(self.boot_sector_raw[0xB:0xD], byteorder='little')
    self.boot_sector['Sectors Per Cluster'] = int.from_bytes(self.boot_sector_raw[0xD:0xE], byteorder='little')
    self.boot_sector['Reserved Sectors'] = int.from_bytes(self.boot_sector_raw[0xE:0x10], byteorder='little')
    self.boot_sector['Media Descriptor'] = self.boot_sector_raw[0x15:0x16]
    self.boot_sector['Sectors Per Track'] = int.from_bytes(self.boot_sector_raw[0x18:0x1A], byteorder='little')
    self.boot_sector['No. Heads'] = int.from_bytes(self.boot_sector_raw[0x1A:0x1C], byteorder='little')
    self.boot_sector['No. Sectors In Volume'] = int.from_bytes(self.boot_sector_raw[0x28:0x30], byteorder='little')
    self.boot_sector['First Cluster of $MFT'] = int.from_bytes(self.boot_sector_raw[0x30:0x38], byteorder='little')
    self.boot_sector['First Cluster of $MFTMirr'] = int.from_bytes(self.boot_sector_raw[0x38:0x40], byteorder='little')
    self.boot_sector['Clusters Per File Record Segment'] = int.from_bytes(self.boot_sector_raw[0x40:0x41], byteorder='little', signed=True)
    self.boot_sector['MFT record size'] = 2 ** abs(self.boot_sector['Clusters Per File Record Segment'])
    self.boot_sector['Clusters Per Index Buffer'] = int.from_bytes(self.boot_sector_raw[0x44:0x45], byteorder='little')
    self.boot_sector['Serial Number'] = int.from_bytes(self.boot_sector_raw[0x48:0x50], byteorder='little')
    self.boot_sector['Bootstrap Code'] = self.boot_sector_raw[0x54:0x1FE]
    self.boot_sector['Signature'] = self.boot_sector_raw[0x1FE:0x200]

  def __str__(self) -> str:
    s = ""
    s += "Volume name: " + self.name
    s += "\nVolume information:\n"
    for key in NTFS.important_info:
      s += f"{key}: {self.boot_sector[key]}\n"
    return s
  
  def __del__(self):
      if getattr(self, "fd", None):
        print("Closing Volume...")
        self.fd.close()
