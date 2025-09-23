#!/usr/bin/env bash
set -e

# Tên thư mục venv
VENV_DIR="venv"

echo "👉 Đang tạo môi trường ảo ($VENV_DIR)..."
python3 -m venv "$VENV_DIR"

echo "👉 Kích hoạt môi trường ảo..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "👉 Nâng cấp pip..."
pip install --upgrade pip

if [ -f requirements.txt ]; then
    echo "👉 Cài đặt các package từ requirements.txt..."
    pip install -r requirements.txt
else
    echo "⚠️ Không tìm thấy requirements.txt, bỏ qua bước cài package."
fi

echo "✅ Hoàn tất! Môi trường ảo đã sẵn sàng."
echo "   Để kích hoạt lại sau này, chạy: source $VENV_DIR/bin/activate"
