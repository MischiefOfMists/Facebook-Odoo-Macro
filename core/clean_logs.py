import os
import shutil

TARGET_FOLDERS = ["fb_screenshots", "session_logs"]

def execute_cleaning(base_dir, log_callback=print):
    """
    Hàm thực thi dọn dẹp chính, tối giản hóa log hiển thị.
    """
    log_callback("Bắt đầu dọn dẹp log.")
    
    total_deleted = 0
    has_folder = False

    for folder_name in TARGET_FOLDERS:
        possible_paths = [
            os.path.join(base_dir, folder_name),
            os.path.join(base_dir, "data", folder_name)
        ]
        
        folder_path = None
        for p in possible_paths:
            if os.path.exists(p) and os.path.isdir(p):
                folder_path = p
                break
                
        if not folder_path:
            continue

        has_folder = True
        files_in_folder = os.listdir(folder_path)
        
        for item in files_in_folder:
            item_path = os.path.join(folder_path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    total_deleted += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    total_deleted += 1
            except Exception as e:
                log_callback(f"Khong the xoa {item}: {str(e)}")

    if not has_folder:
        log_callback("Không tìm thấy các thư mục log.")
    elif total_deleted == 0:
        log_callback("Các thư mục log hiện tại đã trống.")
    else:
        log_callback(f"Đã dọn dẹp log. Tổng số tệp đã xóa: {total_deleted}")