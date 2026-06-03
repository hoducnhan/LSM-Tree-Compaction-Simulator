# 📦 LSM-Tree Compaction Simulator & Distributed Log Fragmentation

> **Project ID:** #55 (Category 3)  
> **Course:** Principles of Distributed Database Systems  
> **Theoretical Framework:** M. Tamer Özsu & Patrick Valduriez  

---

## 👥 1. Team Members
- **Members:** Hồ Đức Nhân

---

## 🎯 2. Project Overview & Problem Statement
Trong các hệ thống xử lý nhật ký tốc độ cao (High-Velocity Logs), cấu trúc dữ liệu B-Tree truyền thống gặp hạn chế lớn do chi phí **Ghi ngẫu nhiên (Random I/O)** khi phải liên tục tìm kiếm và cập nhật vị trí trực tiếp trên đĩa, gây nghẽn cổ chai hệ thống.

Dự án này ứng dụng cấu trúc **Cây trộn có cấu trúc nhật ký (LSM-Tree)** nhằm tối ưu hóa hiệu năng bằng cách chuyển đổi ghi ngẫu nhiên thành **Ghi tuần tự (Sequential I/O)** trên RAM (`MemTable`) rồi đẩy nguyên khối xuống đĩa (`SSTable`). Bên cạnh đó, hệ thống tích hợp mô hình phân tán 3 Node dựa trên lý thuyết phân rã dữ liệu của **Özsu & Valduriez** nhằm cô lập lỗi và tăng tốc độ truy vấn cứu hộ.

---

## 📐 3. System Architecture & Algorithms

### 📡 Distributed Layer (Tầng Phân Tán)
Áp dụng kỹ thuật **Phân rã ngang nguyên thủy (Primary Horizontal Fragmentation)** dựa trên các vị từ định tính của thuộc tính `ErrorLevel`:
- **Node A (Vị từ `DEBUG` | `INFO`):** Xử lý luồng log thông thường, chiếm dung lượng lớn nhằm tránh gây nghẽn đĩa ở các Node khác.
- **Node B (Vị từ `WARN` | `ERROR`):** Lưu trữ các log cảnh báo và lỗi phổ thông để quản trị viên dễ dàng lọc tìm hệ thống.
- **Node C (Vị từ `CRITICAL`):** Cô lập các lỗi nghiêm trọng gây sập hệ thống nhằm đảm bảo tốc độ truy vấn khẩn cấp luôn đạt mức nhanh nhất.

### 💾 Storage Layer (Tầng Lưu Trữ tại mỗi Node)
Mỗi Node vận hành một bộ máy lưu trữ LSM-Tree độc lập bao gồm:
1. **MemTable:** Bộ đệm trên vùng nhớ RAM, dữ liệu tự động được sắp xếp tăng dần theo khóa `Timestamp` ($O(1)$ khi ghi).
2. **SSTable:** File lưu trữ vật lý dạng JSON có tính chất **Bất biến (Immutable)** được sinh ra sau khi `MemTable` đạt ngưỡng giới hạn và kích hoạt cơ chế `Flush`.
3. **Background Compaction:** Tiến trình chạy ngầm sử dụng **Thuật toán trộn hai con trỏ (Two-Pointer Merge Algorithm)** và cơ chế **Khử trùng lặp khóa (Key Deduplication)** để gộp các file đĩa nhỏ cũ thành file nén lớn, tối ưu hóa không gian lưu trữ và khôi phục tốc độ đọc.

---

## 🛡️ 4. Failure Scenario & Recovery (Kịch bản chịu lỗi)
Hệ thống triển khai cơ chế ghi an toàn nguyên tử (Atomic Write Verification). Khi tiến trình Compaction diễn ra, dữ liệu đang trộn được kết xuất tạm thời ra file `.tmp`. 

Nếu Node bị sập nguồn đột ngột giữa chừng (Crash), các file dữ liệu gốc (`sstable_X.json`) hoàn toàn không bị ảnh hưởng nhờ tính chất bất biến. Khi hệ thống khởi động lại, hàm dựng sẽ tự động quét, dọn dẹp file `.tmp` lỗi và đưa hệ thống quay lại trạng thái nhất quán ổn định mà không cần con người can thiệp.

---

## 💻 5. Installation & Execution (Hướng dẫn cài đặt và Chạy)

### Yêu cầu hệ thống:
- Python phiên bản 3.x trở lên.

### Bước 1: Cài đặt thư viện giao diện đồ họa trực quan (Streamlit)
```bash
pip install streamlit
```
### Bước 2: Khởi chạy ứng dụng Web Dashboard
Mở Terminal tại thư mục dự án và thực hiện câu lệnh an toàn:
```bash
python -m streamlit run lsm_app.py

Hệ thống sẽ tự động khởi chạy giao diện đồ họa trực quan trên trình duyệt Web mặc định tại địa chỉ: http://localhost:8501.
---

##🛠️ 6. Tech Stack 
Language: Python

UI Framework: Streamlit (Web-based Interactive Dashboard)

Data Format: JSON (Key-Value Immutable SSTables)

Version Control: Git & GitHub
