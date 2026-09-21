"""Text & Typography Utility Functions for OpenCV Rendering.

Cung cấp các hàm chuẩn hóa chuỗi, loại bỏ dấu tiếng Việt và các ký tự đặc biệt
trước khi truyền vào cv2.putText() để tránh lỗi font hiển thị dấu chấm hỏi '???'.
"""

import re
import unicodedata


def strip_accents(text: str) -> str:
    """Chuyển đổi tiếng Việt có dấu và emoji thành ký tự ASCII thuần cho OpenCV cv2.putText.

    Tránh tuyệt đối lỗi hiển thị dấu chấm hỏi '???' do font Hershey của OpenCV không hỗ trợ Unicode.

    Args:
        text: Chuỗi văn bản đầu vào.

    Returns:
        str: Chuỗi văn bản ASCII thuần an toàn cho OpenCV.
    """
    if not text:
        return ""

    # Chuyển các ký tự có dấu phổ biến
    text = text.replace("đ", "d").replace("Đ", "D")

    # Tách dấu tổ hợp (Combining Diacritical Marks)
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Loại bỏ các emoji và ký tự ngoài dải ASCII in được (32 - 126)
    clean_text = "".join(c if 32 <= ord(c) <= 126 else " " for c in ascii_text)

    # Rút gọn khoảng trắng thừa
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    return clean_text
