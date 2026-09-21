"""Script tải và quản lý các video thực tế công trường phục vụ kiểm thử (Download Real Construction Videos).

Hỗ trợ:
1. Tải các video mẫu công trường thực tế (Royalty-Free / Open-Source Construction Footage).
2. Tải video camera giám sát công trường trực tiếp từ YouTube / RTSP stream bằng yt-dlp (nếu có).
3. Kiểm tra tính hợp lệ của video (Codec, FPS, độ phân giải, số khung hình).
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import cv2

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("VideoDownloader")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = PROJECT_ROOT / "data" / "videos"

# Danh sách một số mẫu video công trường mở bản quyền
SAMPLE_ONLINE_VIDEOS: List[Dict[str, str]] = [
    {
        "name": "construction_site_overview.mp4",
        "url": "https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "description": "Video mẫu kiểm tra luồng truyền tải và hiệu năng xử lý (High Bitrate Stream Benchmark)",
    },
]


def check_video_properties(file_path: Path) -> Dict[str, object]:
    """Kiểm tra thuộc tính kỹ thuật của tệp video bằng OpenCV.

    Args:
        file_path: Đường dẫn tệp video.

    Returns:
        Dict chứa width, height, fps, frame_count, duration_seconds.
    """
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        return {"valid": False, "error": "Không thể mở tệp video"}

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frames / fps if fps > 0 else 0.0

    cap.release()
    return {
        "valid": True,
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "frames": frames,
        "duration_seconds": round(duration, 2),
    }


def download_file_with_progress(url: str, output_path: Path) -> bool:
    """Tải tệp từ Internet kèm thanh đo tiến độ.

    Args:
        url: Đường dẫn URL tệp cần tải.
        output_path: Nơi lưu tệp trên ổ đĩa.

    Returns:
        True nếu tải thành công, False nếu thất bại.
    """
    try:
        logger.info(f"Bắt đầu tải từ: {url}")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )

        with urllib.request.urlopen(req, timeout=30) as response, open(output_path, "wb") as out_file:
            total_length = response.headers.get("Content-Length")
            total_bytes = int(total_length) if total_length else 0
            downloaded = 0
            block_size = 64 * 1024

            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)

                if total_bytes > 0:
                    percent = downloaded * 100 / total_bytes
                    sys.stdout.write(f"\rTiến trình: {percent:.1f}% ({downloaded // 1024} KB / {total_bytes // 1024} KB)")
                    sys.stdout.flush()

        print()
        logger.info(f"Tải thành công: {output_path} ({output_path.stat().st_size // 1024} KB)")
        return True

    except Exception as e:
        logger.error(f"Lỗi khi tải từ {url}: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def download_with_ytdlp(url: str, output_name: str) -> bool:
    """Tải video từ YouTube hoặc các nền tảng video khác bằng yt-dlp.

    Args:
        url: Đường dẫn YouTube video hoặc CCTV stream.
        output_name: Tên tệp đầu ra trong data/videos/.

    Returns:
        True nếu thành công, False nếu yt-dlp không có sẵn hoặc lỗi.
    """
    ytdlp_bin = shutil.which("yt-dlp")
    if not ytdlp_bin:
        logger.warning(
            "yt-dlp chưa được cài đặt. Để tải video từ YouTube, vui lòng chạy:\n"
            "  pip install yt-dlp\n"
            "hoặc tải file video trực tiếp và đặt vào thư mục 'data/videos/'."
        )
        return False

    out_file = VIDEOS_DIR / (output_name if output_name.endswith(".mp4") else f"{output_name}.mp4")
    cmd = [
        ytdlp_bin,
        "-f", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best",
        "-o", str(out_file),
        url,
    ]
    logger.info(f"Đang thực thi lệnh yt-dlp tải video: {url}")
    try:
        res = subprocess.run(cmd, check=True)
        return res.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi yt-dlp: {e}")
        return False


def list_available_videos() -> None:
    """Liệt kê và kiểm tra toàn bộ video hiện có trong data/videos/."""
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    video_files = sorted(VIDEOS_DIR.glob("*.mp4"))

    print("\n" + "=" * 75)
    print("DANH SÁCH CÁC VIDEO KIỂM THỬ CÔNG TRƯỜNG HIỆN CÓ (DATA/VIDEOS)")
    print("=" * 75)

    if not video_files:
        print("Chưa có video nào trong thư mục. Tải thêm bằng `python scripts/download_sample_videos.py --url <URL_VIDEO>`.")
        return

    for idx, v in enumerate(video_files, start=1):
        size_mb = v.stat().st_size / (1024 * 1024)
        props = check_video_properties(v)
        if props.get("valid"):
            print(
                f"{idx:02d}. {v.name:<35} | {size_mb:5.2f} MB | "
                f"{props['width']}x{props['height']} @ {props['fps']} fps | {props['duration_seconds']}s"
            )
        else:
            print(f"{idx:02d}. {v.name:<35} | {size_mb:5.2f} MB | (Lỗi đọc video)")
    print("=" * 75 + "\n")


def main() -> None:
    """Xử lý tham số dòng lệnh CLI."""
    parser = argparse.ArgumentParser(description="Tải và quản lý video kiểm thử công trường.")
    parser.add_argument("--list", action="store_true", help="Liệt kê danh sách video hiện có")
    parser.add_argument("--url", type=str, help="Tải video từ YouTube hoặc link trực tiếp")
    parser.add_argument("--name", type=str, default="custom_site_test.mp4", help="Tên file lưu trong data/videos/")
    parser.add_argument("--sample", action="store_true", help="Tải video mẫu kiểm tra luồng trực tuyến")

    args = parser.parse_args()

    if args.list or (len(sys.argv) == 1):
        list_available_videos()
        return

    if args.sample:
        for item in SAMPLE_ONLINE_VIDEOS:
            target = VIDEOS_DIR / item["name"]
            if not target.exists():
                download_file_with_progress(item["url"], target)
        list_available_videos()
        return

    if args.url:
        if "youtube.com" in args.url or "youtu.be" in args.url:
            download_with_ytdlp(args.url, args.name)
        else:
            target = VIDEOS_DIR / args.name
            download_file_with_progress(args.url, target)
        list_available_videos()


if __name__ == "__main__":
    main()
