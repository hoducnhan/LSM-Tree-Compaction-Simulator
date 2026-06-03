import os
import json
import time
import streamlit as st
from typing import List, Dict, Any

# ==========================================
# 1. CẤU TRÚC DỮ LIỆU LOG
# ==========================================
class LogEntry:
    def __init__(self, timestamp: int, error_level: str, message: str):
        self.timestamp = timestamp
        self.error_level = error_level
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {"timestamp": self.timestamp, "error_level": self.error_level, "message": self.message}

# ==========================================
# 2. LÕI LƯU TRỮ LSM-TREE
# ==========================================
class LSMTreeStorageEngine:
    def __init__(self, node_name: str, memtable_max_size: int = 3):
        self.node_name = node_name
        self.memtable_max_size = memtable_max_size
        self.storage_dir = f"./storage_{node_name}"
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Sử dụng State của Streamlit để lưu bộ nhớ RAM (MemTable) tránh bị reset khi reload web
        if f"mem_{node_name}" not in st.session_state:
            st.session_state[f"mem_{node_name}"] = []

    def get_memtable(self) -> List[Dict]:
        return st.session_state[f"mem_{self.node_name}"]

    def set_memtable(self, data: List[Dict]):
        st.session_state[f"mem_{self.node_name}"] = data

    def write(self, log: LogEntry):
        mem = self.get_memtable()
        mem.append(log.to_dict())
        mem.sort(key=lambda x: x["timestamp"])
        self.set_memtable(mem)
        
        st.toast(f"📥 [{self.node_name}] Đã ghi vào RAM MemTable ({len(mem)}/{self.memtable_max_size})")

        if len(mem) >= self.memtable_max_size:
            self._flush_to_sstable()

    def _flush_to_sstable(self):
        mem = self.get_memtable()
        existing_files = [f for f in os.listdir(self.storage_dir) if f.startswith("sstable_") and f.endswith(".json") and not f.startswith("sstable_merged_")]
        next_index = len(existing_files) + 1
        
        sstable_path = os.path.join(self.storage_dir, f"sstable_{next_index}.json")
        with open(sstable_path, 'w') as f:
            json.dump(mem, f, indent=4)
        
        st.success(f"💥 [{self.node_name}] ĐẦY RAM! Đã Flush xuống đĩa: {sstable_path}")
        self.set_memtable([]) # Xóa sạch MemTable trên RAM

    def trigger_compaction(self):
        sstables = sorted([f for f in os.listdir(self.storage_dir) if f.startswith("sstable_") and f.endswith(".json")])
        sstables = [f for f in sstables if not f.startswith("sstable_merged_")]
        
        if len(sstables) < 2:
            st.warning(f"⏳ [{self.node_name}] Không đủ số lượng SSTable để nén (Hiện có: {len(sstables)} file).")
            return

        file1_path = os.path.join(self.storage_dir, sstables[0])
        file2_path = os.path.join(self.storage_dir, sstables[1])
        
        with open(file1_path, 'r') as f1, open(file2_path, 'r') as f2:
            data1 = json.load(f1)
            data2 = json.load(f2)

        # Trộn và khử trùng
        merged = {}
        for entry in data1 + data2:
            merged[entry["timestamp"]] = entry
        merged_data = [merged[k] for k in sorted(merged.keys())]

        final_filename = f"sstable_merged_{sstables[0].split('_')[1]}"
        final_path = os.path.join(self.storage_dir, final_filename)
        temp_path = os.path.join(self.storage_dir, f"{final_filename}.tmp")
        
        with open(temp_path, 'w') as f_out:
            json.dump(merged_data, f_out, indent=4)

        os.remove(file1_path)
        os.remove(file2_path)
        
        if os.path.exists(final_path):
            os.remove(final_path)
            
        os.rename(temp_path, final_path)
        st.balloons() # Hiệu ứng chúc mừng trên giao diện Web
        st.info(f"✅ [{self.node_name}] Compaction Hoàn Thành! Sinh ra file nén sạch: {final_filename}")

# ==========================================
# 3. ĐIỀU PHỐI PHÂN MẢNH
# ==========================================
class DistributedLogRouter:
    def __init__(self, nodes: Dict[str, LSMTreeStorageEngine]):
        self.nodes = nodes

    def route_log(self, log: LogEntry):
        level = log.error_level.upper()
        if level in ["DEBUG", "INFO"]:
            self.nodes["Node_A"].write(log)
        elif level in ["WARN", "ERROR"]:
            self.nodes["Node_B"].write(log)
        elif level in ["CRITICAL"]:
            self.nodes["Node_C"].write(log)

# ==========================================
# 4. GIAO DIỆN ĐỒ HỌA TRỰC QUAN (STREAMLIT UI)
# ==========================================
st.set_page_config(page_title="LSM-Tree Distributed Simulator", layout="wide")
st.title("📦 Hệ Thống Minh Họa LSM-Tree & Phân Rã Ngang Log")
st.caption("Mô phỏng trực quan theo lý thuyết Hệ cơ sở dữ liệu phân tán (Özsu & Valduriez)")

# Khởi tạo các Node hệ thống
nodes = {
    "Node_A": LSMTreeStorageEngine("Node_A"),
    "Node_B": LSMTreeStorageEngine("Node_B"),
    "Node_C": LSMTreeStorageEngine("Node_C")
}
router = DistributedLogRouter(nodes)

# THÀNH PHẦN 1: ĐIỀU KHIỂN GHI LOG (Bên trái giao diện)
st.sidebar.header("🕹️ Bảng Điều Khiển Hệ Thống")

# Tính năng 1: Ghi log thủ công bằng Form
with st.sidebar.form("manual_log"):
    st.subheader("Ghi 1 dòng Log thủ công")
    msg = st.text_input("Nội dung Log Message:", "User requested billing info.")
    lvl = st.selectbox("Mức độ lỗi (ErrorLevel):", ["INFO", "DEBUG", "WARN", "ERROR", "CRITICAL"])
    # submitted = st.form_submit_with_button("Gửi Log vào Hệ Thống")
    # Đoạn code MỚI đã sửa lỗi:
    submitted = st.form_submit_button("Gửi Log vào Hệ Thống")
    if submitted:
        new_log = LogEntry(int(time.time()), lvl, msg)
        router.route_log(new_log)

# Tính năng 2: Kích hoạt luồng chạy tự động sinh log hàng loạt
st.sidebar.write("---")
st.sidebar.subheader("Giả lập luồng Log tự động")
if st.sidebar.button("🚀 Chạy luồng log mẫu (Gây tràn RAM)"):
    sample_logs = [
        LogEntry(1710000001, "INFO", "User logged in successfully."),
        LogEntry(1710000002, "INFO", "Dashboard rendered in 120ms."),
        LogEntry(1710000003, "DEBUG", "Database connection pool size: 10."), # Kích hoạt Flush Node A
        LogEntry(1710000004, "WARN", "Memory usage reached 85%."),
        LogEntry(1710000005, "ERROR", "Failed to connect to gateway."),
        LogEntry(1710000006, "WARN", "Disk I/O latency high."), # Kích hoạt Flush Node B
        LogEntry(1710000001, "INFO", "User logged in (Duplicate Key Test)."), 
        LogEntry(1710000007, "INFO", "New session created."),
        LogEntry(1710000008, "INFO", "Image uploaded successfully.") # Kích hoạt Flush Node A lần 2
    ]
    for log in sample_logs:
        router.route_log(log)
        time.sleep(0.3)
    st.rerun()

# THÀNH PHẦN 2: HIỂN THỊ CÁC SITE/NODE PHÂN TÁN (Giao diện chính ở giữa)
cols = st.columns(3)

for idx, (node_name, node_obj) in enumerate(nodes.items()):
    with cols[idx]:
        st.header(f"🖥️ {node_name}")
        
        # Thuyết minh quy tắc phân mảnh dựa trên vị từ toán học của nhóm
        if node_name == "Node_A": st.caption("🟡 Chứa Vị từ: `DEBUG` hoặc `INFO` [Dung lượng lớn]")
        elif node_name == "Node_B": st.caption("🟠 Chứa Vị từ: `WARN` hoặc `ERROR` [Cảnh báo lỗi]")
        elif node_name == "Node_C": st.caption("🔴 Chứa Vị từ: `CRITICAL` [Sự cố hệ thống]")
        
        # Hiện trạng thái RAM (MemTable) hiện tại của Node đó
        st.subheader("📟 Vùng nhớ RAM (MemTable)")
        current_mem = node_obj.get_memtable()
        if current_mem:
            st.json(current_mem)
        else:
            st.info("RAM trống (Đang chờ log hoặc vừa được Flush)")

        # Hiện trạng thái ĐĨA CỨNG (SSTables) vật lý đang lưu trữ trong thư mục
        st.subheader("💾 Dữ liệu dưới Đĩa (SSTables)")
        if os.path.exists(node_obj.storage_dir):
            files = sorted([f for f in os.listdir(node_obj.storage_dir) if f.endswith(".json")])
            if files:
                for file in files:
                    with st.expander(f"📁 {file}"):
                        with open(os.path.join(node_obj.storage_dir, file), 'r') as f:
                            st.json(json.load(f))
            else:
                st.write("Chưa có file SSTable nào trên ổ đĩa.")
        
        # Nút bấm kích hoạt Compaction nén dữ liệu thủ công cho từng Node
        st.write("---")
        if st.button(f"🔄 Chạy Compaction trên {node_name}"):
            node_obj.trigger_compaction()
            time.sleep(0.5)
            st.rerun()