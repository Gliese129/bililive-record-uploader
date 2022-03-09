import os.path
from moviepy.editor import VideoFileClip


def get_time(video_path: str) -> int:
    """获取单个视频时长

    :param video_path: 视频路径
    :return: 时长(s)
    """
    video_clip = VideoFileClip(video_path)
    duration = video_clip.duration
    video_clip.close()
    return duration


def get_total_time(video_paths: list[str]) -> int:
    result = 0
    for path in video_paths:
        if os.path.exists(path):
            result += get_time(path)
    return result
