import os
import json
import time
import threading
from typing import List, Dict, Any

# ==========================================
# 1. CẤU TRÚC DỮ LIỆU LOG (DATASET SPECIFICATION)
# ==========================================
class LogEntry:
    def __init__(self, timestamp: int, error_level: str, message: str):
        self.timestamp = timestamp  # Khóa chính (Key) để sắp xếp
        self.error_level = error_level
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "error_level": self.error_level,
            "message": self.message
        }

# ==========================================
# 2. THÀNH PHẦN LƯU TRỮ LSM-TREE TRÊN MỖI NODE
# ==========================================
class LSMTreeStorageEngine:
    def __init__(self, node_name: str, memtable_max_size: int = 3):
        self.node_name = node_name
        self.memtable_max_size = memtable_max_size
        self.memtable: List[Dict[str, Any]] = []  # Bộ nhớ đệm RAM (MemTable)
        self.sstable_count = 0
        self.lock = threading.Lock()
        
        # Tạo thư mục lưu trữ vật lý cho từng Node
        self.storage_dir = f"./storage_{node_name}"
        os.makedirs(self.storage_dir, exist_ok=True)

    def write(self, log: LogEntry):
        """ Ghi dữ liệu log vào MemTable (Ghi tuần tự vào RAM) """
        with self.lock:
            self.memtable.append(log.to_dict())
            # Sắp xếp MemTable theo Timestamp (Key)
            self.memtable.sort(key=lambda x: x["timestamp"])
            print(f"[{self.node_name}] Đã ghi vào MemTable. Kích thước hiện tại: {len(self.memtable)}/{self.memtable_max_size}")

            # Nếu MemTable đầy, thực hiện Flush xuống đĩa thành SSTable
            if len(self.memtable) >= self.memtable_max_size:
                self._flush_to_sstable()

    def _flush_to_sstable(self):
        """ Chuyển đổi MemTable thành file SSTable sắp xếp trên đĩa """
        self.sstable_count += 1
        sstable_path = os.path.join(self.storage_dir, f"sstable_{self.sstable_count}.json")
        
        with open(sstable_path, 'w') as f:
            json.dump(self.memtable, f, indent=4)
        
        print(f"💥 [{self.node_name}] MemTable ĐẦY! Đã flush xuống đĩa thành công: {sstable_path}")
        self.memtable = []  # Xóa sạch MemTable sau khi flush

    def trigger_compaction(self):
        """ Tiến trình Background Merger gộp 2 SSTable cũ nhất và xóa trùng lặp """
        with self.lock:
            # Lấy danh sách các file SSTable hiện có
            sstables = sorted([f for f in os.listdir(self.storage_dir) if f.startswith("sstable_") and f.endswith(".json")])
            
            # Bỏ qua các file đã được merge hoặc file tạm để tránh nhận diện sai
            sstables = [f for f in sstables if not f.startswith("sstable_merged_")]
            
            if len(sstables) < 2:
                print(f"⏳ [{self.node_name}] Không đủ số lượng SSTable để thực hiện Compaction (Hiện có: {len(sstables)} file).")
                return

            # Chọn 2 file cũ nhất để tiến hành gộp
            file1_path = os.path.join(self.storage_dir, sstables[0])
            file2_path = os.path.join(self.storage_dir, sstables[1])
            
            print(f"🔄 [{self.node_name}] Đang chạy Background Merger cho: {sstables[0]} và {sstables[1]}")
            
            with open(file1_path, 'r') as f1, open(file2_path, 'r') as f2:
                data1 = json.load(f1)
                data2 = json.load(f2)

            # Thuật toán Hợp nhất hai con trỏ (Two-Pointer Merge) và loại bỏ trùng lặp khóa
            merged_data = self._merge_and_compact(data1, data2)

            # Tạo tên file đích cố định dựa trên số thứ tự
            final_filename = f"sstable_merged_{sstables[0].split('_')[1]}"
            final_path = os.path.join(self.storage_dir, final_filename)
            
            # Ghi dữ liệu đã compacted vào một file tạm (.tmp) trước
            temp_path = os.path.join(self.storage_dir, f"{final_filename}.tmp")
            with open(temp_path, 'w') as f_out:
                json.dump(merged_data, f_out, indent=4)

            # Xóa các file thành phần cũ
            os.remove(file1_path)
            os.remove(file2_path)
            
            # SỬA LỖI WINERROR 183: Nếu file đích đã tồn tại (do phiên chạy trước), xóa nó trước khi rename
            if os.path.exists(final_path):
                os.remove(final_path)
                
            os.rename(temp_path, final_path)
            print(f"✅ [{self.node_name}] Compaction HOÀN THÀNH! File mới: {final_path}")

    def _merge_and_compact(self, list1: List[Dict], list2: List[Dict]) -> List[Dict]:
        """ Hợp nhất hai danh sách đã sắp xếp và loại bỏ trùng khóa (giữ bản ghi có thông tin mới hơn) """
        merged = {}
        # Nạp dữ liệu từ danh sách cũ trước, danh sách mới sau để đè ghi dữ liệu mới nhất nếu trùng khóa Timestamp
        for entry in list1 + list2:
            merged[entry["timestamp"]] = entry # Khóa trùng sẽ tự động bị ghi đè
            
        # Trả về danh sách được sắp xếp theo khóa
        return [merged[k] for k in sorted(merged.keys())]

# ==========================================
# 3. ROUTER PHÂN PHỐI DỮ LIỆU PHÂN TÁN
# ==========================================
class DistributedLogRouter:
    def __init__(self, nodes: Dict[str, LSMTreeStorageEngine]):
        self.nodes = nodes

    def route_log(self, log: LogEntry):
        """ Chiến lược phân rã ngang (Horizontal Fragmentation) theo ErrorLevel """
        level = log.error_level.upper()
        if level in ["DEBUG", "INFO"]:
            self.nodes["Node_A"].write(log)
        elif level in ["WARN", "ERROR"]:
            self.nodes["Node_B"].write(log)
        elif level in ["CRITICAL"]:
            self.nodes["Node_C"].write(log)
        else:
            print(f"⚠️ Mức độ lỗi '{level}' không hợp lệ. Bỏ qua bản ghi.")

# ==========================================
# 4. CHƯƠNG TRÌNH MÔ PHỎNG CHẠY THỬ (SIMULATION)
# ==========================================
if __name__ == "__main__":
    # Khởi tạo cụm 3 Node phân tán
    cluster_nodes = {
        "Node_A": LSMTreeStorageEngine(node_name="Node_A"),
        "Node_B": LSMTreeStorageEngine(node_name="Node_B"),
        "Node_C": LSMTreeStorageEngine(node_name="Node_C")
    }
    
    router = DistributedLogRouter(nodes=cluster_nodes)

    print("=== BẮT ĐẦU MÔ PHỎNG LUỒNG GHI LOG TỐC ĐỘ CAO ===")
    
    # Giả lập các bản ghi log liên tục truyền vào hệ thống
    logs_stream = [
        LogEntry(1710000001, "INFO", "User logged in successfully."),
        LogEntry(1710000002, "INFO", "Dashboard rendered in 120ms."),
        LogEntry(1710000003, "DEBUG", "Database connection pool size: 10."),
        # Kích hoạt Flush trên Node A tại đây (đạt ngưỡng max_size = 3)
        
        LogEntry(1710000004, "WARN", "Memory usage reached 85%."),
        LogEntry(1710000005, "ERROR", "Failed to connect to payment gateway."),
        LogEntry(1710000006, "WARN", "Disk I/O latency high."),
        # Kích hoạt Flush trên Node B tại đây (đạt ngưỡng max_size = 3)

        LogEntry(1710000001, "INFO", "User logged in successfully (Duplicate Key Test)."), 
        LogEntry(1710000007, "INFO", "New session created."),
        LogEntry(1710000008, "INFO", "Image uploaded successfully.")
        # Kích hoạt Flush lần 2 trên Node A
    ]

    for log in logs_stream:
        router.route_log(log)
        time.sleep(0.2) # Giả lập khoảng trễ giữa các log

    print("\n=== KÍCH HOẠT TIẾN TRÌNH COMPACTION CHẠY NGẦM ===")
    # Mô phỏng lệnh gọi tiến trình nén từ Background Thread trên Node A
    compaction_thread = threading.Thread(target=cluster_nodes["Node_A"].trigger_compaction)
    compaction_thread.start()
    compaction_thread.join()