import re
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
    self.flag = self.raw_data[0x16]
    if self.flag == 0 or self.flag == 2:
      # Deleted record
      raise Exception("Skip this record")
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
    elif data_sig[0] == 144:
      self.standard_info['flags'] |= NTFSAttribute.DIRECTORY
      self.data['size'] = 0
      self.data['resident'] = True
    self.childs: list[MFTRecord] = []

    del self.raw_data

  def is_directory(self):
    return NTFSAttribute.DIRECTORY in self.standard_info['flags']
  
  def is_leaf(self):
    return not len(self.childs)

  def is_active_record(self):
    flags = self.standard_info['flags']
    if NTFSAttribute.SYSTEM in flags or NTFSAttribute.HIDDEN in flags:
      return False
    return True
  
  def find_record(self, name: str):
    for record in self.childs:
      if record.file_name['long_name'] == name:
        return record
    return None
  
  def get_active_records(self) -> 'list[MFTRecord]':
    record_list: list[MFTRecord] = []
    for record in self.childs:
      if record.is_active_record():
        record_list.append(record)
    return record_list
  
  def __parse_data(self, start):
    self.data['resident'] = not bool(self.raw_data[start+0x8])
    if self.data['resident']:
      offset = int.from_bytes(self.raw_data[start + 0x14:start + 0x16], byteorder='little')
      self.data['size'] = int.from_bytes(self.raw_data[start+0x10:start+0x14], byteorder='little')
      self.data['content'] = self.raw_data[start + offset:start + offset + self.data['size']]
    else:
      cluster_chain = self.raw_data[start + 0x40]
      offset = (cluster_chain & 0xF0) >> 4
      size = cluster_chain & 0x0F
      self.data['size'] = int.from_bytes(self.raw_data[start + 0x30: start + 0x38], byteorder='little')
      self.data['cluster_size'] = int.from_bytes(self.raw_data[start + 0x41: start + 0x41 + size], byteorder='little')
      self.data['cluster_offset'] =  int.from_bytes(self.raw_data[start + 0x41 + size: start + 0x41 + size + offset], byteorder='little')


  def __parse_file_name(self, start):
    sig = int.from_bytes(self.raw_data[start:start + 4], byteorder='little')
    if sig != 0x30:
      raise Exception("Skip this record")
    
    # header = self.raw_data[start:start + 0x10]
    size = int.from_bytes(self.raw_data[start + 0x10:start + 0x14], byteorder='little')
    offset = int.from_bytes(self.raw_data[start + 0x14: start + 0x16], byteorder='little')
    body = self.raw_data[start + offset: start + offset + size]
    
    self.file_name["parent_id"] = int.from_bytes(body[:6], byteorder='little')
    name_length = body[64]
    self.file_name["long_name"] = body[66:66 + name_length * 2].decode('utf-16le')  # unicode

  def __parse_standard_info(self, start):
    sig = int.from_bytes(self.raw_data[start:start + 4], byteorder='little')
    if sig != 0x10:
      raise Exception("Something Wrong!")
    offset = int.from_bytes(self.raw_data[start + 20:start + 21], byteorder='little')
    begin = start + offset
    self.standard_info["created_time"] = as_datetime(int.from_bytes(self.raw_data[begin:begin + 8], byteorder='little'))
    self.standard_info["last_modified_time"] = as_datetime(int.from_bytes(self.raw_data[begin + 8:begin + 16], byteorder='little'))
    self.standard_info["flags"] = NTFSAttribute(int.from_bytes(self.raw_data[begin + 32:begin + 36], byteorder='little') & 0xFFFF)


class DirectoryTree:
  def __init__(self, nodes: 'list[MFTRecord]') -> None:
    self.root = None
    self.nodes_dict: dict[int, MFTRecord] = {}
    for node in nodes:
      self.nodes_dict[node.file_id] = node

    for key in self.nodes_dict:
      parent_id = self.nodes_dict[key].file_name['parent_id']
      if parent_id in self.nodes_dict:
        self.nodes_dict[parent_id].childs.append(self.nodes_dict[key])

    for key in self.nodes_dict:
      parent_id = self.nodes_dict[key].file_name['parent_id']
      if parent_id == self.nodes_dict[key].file_id:
        self.root = self.nodes_dict[key]
        break
    
    self.current_dir = self.root

  def find_record(self, name: str):
    return self.current_dir.find_record(name)
  
  def get_parent_record(self, record: MFTRecord):
    return self.nodes_dict[record.file_name['parent_id']]

  def get_active_records(self) -> 'list[MFTRecord]':
    return self.current_dir.get_active_records()

class MFTFile:
  def __init__(self, data: bytes) -> None:
    self.raw_data = data
    self.info_offset = int.from_bytes(self.raw_data[0x14:0x16], byteorder='little')
    self.info_len = int.from_bytes(self.raw_data[0x3C:0x40], byteorder='little')
    self.file_name_offset = self.info_offset + self.info_len
    self.file_name_len = int.from_bytes(self.raw_data[0x9C:0xA0], byteorder='little')
    self.data_offset = self.file_name_offset + self.file_name_len
    self.data_len = int.from_bytes(self.raw_data[0x104:0x108], byteorder='little')
    self.num_sector = (int.from_bytes(self.raw_data[0x118:0x120], byteorder='little') + 1) * 8
    del self.raw_data

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
      self.SC = self.boot_sector["Sectors Per Cluster"]
      self.BS = self.boot_sector["Bytes Per Sector"]

      self.record_size = self.boot_sector["MFT record size"]
      self.mft_offset = self.boot_sector['First Cluster of $MFT']
      self.fd.seek(self.mft_offset * self.SC * self.BS)
      self.mft_file = MFTFile(self.fd.read(self.record_size))
      mft_record: list[MFTRecord] = []
      for _ in range(2, self.mft_file.num_sector, 2):
        dat = self.fd.read(self.record_size)
        if dat[:4] == b"FILE":
          try:
            mft_record.append(MFTRecord(dat))
          except Exception as e:
            pass
  
      self.dir_tree = DirectoryTree(mft_record)
    except Exception as e:
      print(f"[ERROR] {e}")
      exit()

  @staticmethod
  def check_ntfs(name: str):
    try:
      with open(r'\\.\%s' % name, 'rb') as fd:
        oem_id = fd.read(0xB)[3:]
        if oem_id == b'NTFS    ':
          return True
        return False
    except Exception as e:
      print(f"[ERROR] {e}")
      exit()

  def __extract_boot_sector(self):
    # self.boot_sector['Jump_Code'] = self.boot_sector_raw[:3]
    self.boot_sector['OEM_ID'] = self.boot_sector_raw[3:0xB]
    self.boot_sector['Bytes Per Sector'] = int.from_bytes(self.boot_sector_raw[0xB:0xD], byteorder='little')
    self.boot_sector['Sectors Per Cluster'] = int.from_bytes(self.boot_sector_raw[0xD:0xE], byteorder='little')
    self.boot_sector['Reserved Sectors'] = int.from_bytes(self.boot_sector_raw[0xE:0x10], byteorder='little')
    # self.boot_sector['Media Descriptor'] = self.boot_sector_raw[0x15:0x16]
    # self.boot_sector['Sectors Per Track'] = int.from_bytes(self.boot_sector_raw[0x18:0x1A], byteorder='little')
    # self.boot_sector['No. Heads'] = int.from_bytes(self.boot_sector_raw[0x1A:0x1C], byteorder='little')
    self.boot_sector['No. Sectors In Volume'] = int.from_bytes(self.boot_sector_raw[0x28:0x30], byteorder='little')
    self.boot_sector['First Cluster of $MFT'] = int.from_bytes(self.boot_sector_raw[0x30:0x38], byteorder='little')
    self.boot_sector['First Cluster of $MFTMirr'] = int.from_bytes(self.boot_sector_raw[0x38:0x40], byteorder='little')
    self.boot_sector['Clusters Per File Record Segment'] = int.from_bytes(self.boot_sector_raw[0x40:0x41], byteorder='little', signed=True)
    self.boot_sector['MFT record size'] = 2 ** abs(self.boot_sector['Clusters Per File Record Segment'])
    # self.boot_sector['Clusters Per Index Buffer'] = int.from_bytes(self.boot_sector_raw[0x44:0x45], byteorder='little')
    self.boot_sector['Serial Number'] = int.from_bytes(self.boot_sector_raw[0x48:0x50], byteorder='little')
    # self.boot_sector['Bootstrap Code'] = self.boot_sector_raw[0x54:0x1FE]
    self.boot_sector['Signature'] = self.boot_sector_raw[0x1FE:0x200]
  

  def __parse_path(self, path):
    dirs = re.sub(r"[/\\]+", r"\\", path).strip("\\").split("\\")
    return dirs
  
  def visit_dir(self, path) -> MFTRecord:
    if path == "":
      raise Exception("Directory name is required!")
    path = self.__parse_path(path)

    if path[0] == self.name:
      cur_dir = self.dir_tree.root
      path.pop(0)
    else:
      cur_dir = self.dir_tree.current_dir
    for d in path:
      if d == "..":
        cur_dir = self.dir_tree.get_parent_record(cur_dir)
        continue
      elif d == ".":
        continue
      record = cur_dir.find_record(d)
      if record is None:
        raise Exception("Directory not found!")
      if record.is_directory():
        cur_dir = record
      else:
        raise Exception("Not a directory")
    return cur_dir

  def get_dir(self, path = ""):
    try:
      if path != "":
        next_dir = self.visit_dir(path)
        record_list = next_dir.get_active_records()
      else:
        record_list = self.dir_tree.get_active_records()
      ret = []
      for record in record_list:
        obj = {}
        obj["Flags"] = record.standard_info['flags'].value
        obj["Date Modified"] = record.standard_info['last_modified_time']
        obj["Size"] = record.data['size']
        obj["Name"] = record.file_name['long_name']
        if record.data['resident']:
          obj["Sector"] = self.mft_offset * self.SC + record.file_id
        else:
          obj["Sector"] = record.data['cluster_offset'] * self.SC
        ret.append(obj)
      return ret
    except Exception as e:
      raise (e)

  def change_dir(self, path=""):
    if path == "":
      raise Exception("Path to directory is required!")
    try:
      next_dir = self.visit_dir(path)
      self.dir_tree.current_dir = next_dir

      dirs = self.__parse_path(path)
      if dirs[0] == self.name:
        self.cwd.clear()
        self.cwd.append(self.name)
        dirs.pop(0)
      for d in dirs:
        if d == "..":
          if len(self.cwd) > 1: self.cwd.pop()
        elif d != ".":
          self.cwd.append(d)
    except Exception as e:
      raise (e)

  def get_cwd(self):
    if len(self.cwd) == 1:
      return self.cwd[0] + "\\"
    return "\\".join(self.cwd)
  
  def get_file_content(self, path: str):
    path = self.__parse_path(path)
    if len(path) > 1:
      name = path[-1]
      path = "\\".join(path[:-1])
      next_dir = self.visit_dir(path)
      record = next_dir.find_record(name)
    else:
      record = self.dir_tree.find_record(path[0])

    if record is None:
      raise Exception("File doesn't exist")
    if record.is_directory():
      raise Exception("Is a directory")

    if 'resident' not in record.data:
      return b''
    if record.data['resident']:
      return record.data['content']
    else:
      real_size = record.data['size']
      offset = record.data['cluster_offset'] * self.SC * self.BS
      size = record.data['cluster_size'] * self.SC * self.BS
      self.fd.seek(offset)
      data = self.fd.read(min(size, real_size))
      return data

  def get_text_file(self, path: str) -> str:
    path = self.__parse_path(path)
    if len(path) > 1:
      name = path[-1]
      path = "\\".join(path[:-1])
      next_dir = self.visit_dir(path)
      record = next_dir.find_record(name)
    else:
      record = self.dir_tree.find_record(path[0])

    if record is None:
      raise Exception("File doesn't exist")
    if record.is_directory():
      raise Exception("Is a directory")
    if 'resident' not in record.data:
      return ''
    if record.data['resident']:
      try:
        data = record.data['content'].decode()
      except UnicodeDecodeError as e:
        raise Exception(
            "Not a text file, please use appropriate software to open.")
      except Exception as e:
        raise (e)
      return data
    else:
      data = ""
      size_left = record.data['size']
      offset = record.data['cluster_offset'] * self.SC * self.BS
      cluster_num = record.data['cluster_size']
      self.fd.seek(offset)
      for _ in range(cluster_num):
        if size_left <= 0:
          break
        raw_data = self.fd.read(min(self.SC * self.BS, size_left))
        size_left -= self.SC * self.BS
        try:
          data += raw_data.decode()
        except UnicodeDecodeError as e:
          raise Exception("Not a text file, please use appropriate software to open.")
        except Exception as e:
          raise (e)
      return data
  
  def __str__(self) -> str:
    s = "Volume name: " + self.name
    s += "\nVolume information:\n"
    for key in NTFS.important_info:
      s += f"{key}: {self.boot_sector[key]}\n"
    return s
  
  def __del__(self):
    if getattr(self, "fd", None):
      print("Closing Volume...")
      self.fd.close()
