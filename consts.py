import os
from models import GlobalConfig
from utils.FileUtils import CopyFile


class Paths:
    VIDEO_CACHE = './cache/videos.json'
    TIME_CACHE = './cache/times.json'
    LIVE2VIDEO = './resources/live2video.json'
    DANMAKU_FACTORY: str
    FFMPEG: str

    @classmethod
    def init(cls, global_config: GlobalConfig):
        if global_config.docker:
            cls.DANMAKU_FACTORY = '/DanmakuFactory/DanmakuFactory'
            cls.FFMPEG = 'ffmpeg'
        else:
            cls.DANMAKU_FACTORY = 'resources\\DanmakuFactory'
            cls.FFMPEG = 'resources\\ffmpeg'
        new_live2video = os.path.join(global_config.config_dir, 'live2video.json')
        if not os.path.exists(new_live2video):
            CopyFile(cls.LIVE2VIDEO, global_config.config_dir)
        cls.LIVE2VIDEO = new_live2video
