# -*- coding: utf-8 -*-
import logging
import os
from typing import Optional
from bilibili_api import video_uploader, Credential
from sanic import Sanic
from utils import FileUtils
from models import RoomConfig, LiveInfo, VideoInfo, GlobalConfig
from exceptions import *

app = Sanic.get_app()


class Uploader:
    """上传
    Fields:
        credential: 用户凭据
        live_info: 直播间信息
        video_info: 视频信息
        room_config: 该房间的配置信息
    """
    credential: video_uploader.Credential
    live_info: LiveInfo
    video_info: VideoInfo
    room_config: RoomConfig

    def __init__(self, credential: Credential, room_config: RoomConfig, videos: list[str], live_info: LiveInfo, **_):
        self.credential = credential
        self.video_info = VideoInfo(room_config=room_config, videos=videos)
        self.room_config = room_config
        self.live_info = live_info

    def set_module(self, module_string: str) -> str:
        """ 设置模板

        :param module_string: 模板字符串
        :return: 替换后的结果
        """
        live_info = self.live_info
        return module_string \
            .replace('${anchor}', live_info.anchor) \
            .replace('${title}', live_info.title) \
            .replace('${date}', live_info.start_time.strftime('%Y-%m-%d')) \
            .replace('${time}', live_info.start_time.strftime('%H:%M:%S')) \
            .replace('${parent_area}', live_info.parent_area) \
            .replace('${child_area}', live_info.child_area)

    def set_tags_and_channel(self):
        """ 设置标签和分区

        :exception No channel found
        """
        global_config: GlobalConfig = app.ctx.global_config
        # room_config
        self.video_info.channel = self.room_config.channel
        self.video_info.tags = self.room_config.tags
        # live2video

        def get_live2video_channel(live2video: dict) -> (str, str):
            def to_channel(channel: str) -> Optional[tuple[str, str]]:
                channel = channel.split(' ')
                if len(channel) == 2:
                    return channel[0], channel[1]
                return None
            for parent_area in live2video:
                if parent_area.get('name') == self.live_info.parent_area:
                    # 直播父分区可以直接对应频道
                    if parent_area.get('channel') is not None:
                        return to_channel(parent_area.get('channel'))
                    # 直播父分区无法直接对应，查找子分区
                    if parent_area.get('children') is not None:
                        for child_area in parent_area.get('children'):
                            if child_area.get('name') == self.live_info.child_area:
                                # 子分区可以直接对应频道
                                return to_channel(child_area.get('channel'))
        data = FileUtils.ReadJson(global_config.get_config('live2video.json'))
        result = get_live2video_channel(data)
        if result is not None:
            self.video_info.channel = result

        # condition
        conditions = self.room_config.list_conditions(live_info=self.live_info)
        for condition in conditions:
            self.video_info.tags.extend(condition.tags)
            if condition.channel is not None:
                self.video_info.channel = condition.channel

        # no channel
        if self.video_info.channel is None:
            logging.error('[%d] %s-%s -> ?',
                          self.live_info.room_id, self.live_info.parent_area, self.live_info.child_area)
            raise InvalidParamException('No channel found!')
        logging.debug('[%d] %s-%s -> %s-%s',
                      self.live_info.room_id, self.live_info.parent_area, self.live_info.child_area,
                      self.video_info.channel[0], self.video_info.channel[1])

    @staticmethod
    def set_pages(videos: list[str]) -> list[video_uploader.VideoUploaderPage]:
        """ 分页设置

        :param videos: 视频列表
        :return: 分页
        """
        pages = []
        for index, video in enumerate(videos):
            if os.path.exists(video) and os.path.getsize(video) > 0:
                page_info = {
                    'path': video,
                    'title': f'part{index + 1}',
                    'description': ''
                }
                page = video_uploader.VideoUploaderPage(**page_info)
                pages.append(page)
        return pages

    @staticmethod
    def fetch_channel(parent_area: str, child_area: str) -> int:
        """ 获取分区id

        :param parent_area: 父区域
        :param child_area: 子区域
        :return: 分区id
        """
        channel = FileUtils.ReadJson(path='./resources/channel.json')
        tid = 0
        for main_ch in channel:
            if main_ch['name'] == parent_area:
                for sub_ch in main_ch['sub']:
                    if sub_ch['name'] == child_area:
                        tid = sub_ch['tid']
        return tid

    async def upload(self):
        """ 上传视频

        :exception No channel found
        :exception No video found
        :return: 是否上传成功
        """
        self.video_info.title = self.set_module(self.video_info.title)
        self.video_info.description = self.set_module(self.video_info.description)
        self.set_tags_and_channel()
        logging.info('[%d] fetching channel...', self.live_info.room_id)
        tid = self.fetch_channel(*self.video_info.channel)
        meta = {
            'act_reserve_create': 0,
            'copyright': 2,
            'source': f'https://live.bilibili.com/{self.live_info.room_id}',
            'desc': self.video_info.description,
            'dynamic': self.video_info.dynamic,
            'interactive': 0,
            'no_reprint': 0,
            'open_elec': 0,
            'origin_state': 0,
            'subtitles': {
                "lan": '',
                'open': 0
            },
            'tag': self.video_info.get_tags(),
            'tid': tid,
            'title': self.video_info.title,
            'up_close_danmaku': False,
            'up_close_reply': False,
            'up_selection_reply': False
        }
        pages = self.set_pages(videos=self.video_info.videos)
        if len(pages) == 0:
            raise FileNotFoundError('no videos to upload')
        uploader = video_uploader.VideoUploader(pages=pages, meta=meta, credential=self.credential)
        logging.info('[%d] uploading...', self.live_info.room_id)
        logging.debug('file info:\ntitle: %s\nchannel: %s\ntags: %s',
                      self.video_info.title, self.video_info.channel, self.video_info.get_tags())
        ids = await uploader.start()
        logging.info('[%d] upload finished, bvid=%s, aid=%s', self.live_info.room_id, ids['bvid'], ids['aid'])
