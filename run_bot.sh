#!/bin/bash

# ==================================================================
# SCRIPT ĐIỀU HÀNH VÀ TỰ ĐỘNG HỒI SINH BOT MA SÓI TRÊN TERMUX
# ==================================================================

# Định nghĩa tên tệp Python chính của hệ thống Ma Sói
BOT_SCRIPT="bot_sieucap_masoi.py"

echo "🐺 [HỆ THỐNG MASTER] Khởi động trình quản lý Process Daemon..."
echo "⚡ Hệ thống tự động hồi sinh khi Bot bị sập đã được kích hoạt vĩnh viễn."

# Vòng lặp vô hạn (Infinite Loop) quản lý sinh mệnh của tiến trình Python
while true; do
    echo "🚀 [START] -> Đang kích hoạt tệp nguồn $BOT_SCRIPT..."
    
    # Khởi chạy Bot Python thực tế
    python "$BOT_SCRIPT"
    
    # Đoạn code dưới đây chỉ được chạy khi tiến trình Python phía trên bị kết thúc (Sập/Crash)
    EXIT_CODE=$?
    echo "⚠️ [CẢNH BÁO] -> Tiến trình Bot Ma Sói đã bị dừng với mã lỗi: $EXIT_CODE"
    echo "⏳ [HỒI SINH] -> Đang đếm ngược 3 giây để tự động cấu hình lại hệ thống và bật lại..."
    
    # Tạm dừng 3 giây để tránh tình trạng spam tài nguyên CPU nếu Bot bị lỗi lặp vòng lặp
    sleep 3
done
