import logging
import os
import re
from datetime import datetime
from typing import overload, Optional
from bilibili_api import Credential
from utils import FileUtils


@overload
class LiveInfo:
    pass


class GlobalConfig:
    """ 录播bot配置
    Configs:
        record_dir: B站录播姬工作目录
        work_dir: 录播bot工作目录
        delete: 是否上传后删除
        port: 录播bot监听端口
        webhooks: webhook发送url
        workers: 线程数
        multipart: 是否多p
        auto_upload: 是否自动上传
        min_time: 单个录播最小时长
        credential: B站凭据
    """
    record_dir: str
    work_dir: str
    config_dir: str
    delete: bool
    port: int
    webhooks: list[str]
    workers: int
    multipart: bool
    auto_upload: bool
    min_time: int
    credential: Credential
    docker: bool

    def __init__(self, work_dir: str):
        self.config_dir = os.path.join(work_dir, 'config')
        config = FileUtils.YmlReader(os.path.join(self.config_dir, 'global-config.yml'))
        self.docker = config['recorder'].get('is-docker', False)
        if self.docker:
            self.record_dir = '/record'
            self.work_dir = '/process'
            self.port = 8866
        else:
            self.record_dir = config['recorder']['record-dir']
            self.work_dir = work_dir
            self.port = config['server']['port']
        self.delete = config['recorder'].get('delete-after-upload', True)
        self.webhooks = config['server'].get('webhooks', [])
        self.workers = config['recorder'].get('workers', 1)
        self.multipart = config['recorder'].get('multipart', False)
        self.auto_upload = config['recorder'].get('auto-upload', True)
        if self.auto_upload:
            self.credential = Credential(**config['account']['credential'])
        self.min_time = eval(str(config['recorder'].get('min-time', 0)))

    def get_config(self, name: str) -> str:
        return os.path.join(self.work_dir, 'config', name)


class Condition:
    """ 房间额外条件配置
    Fields:
        item: 条件名称
        regexp: 正则表达式
        tags: 此条件下的上传标签
        channel: 此条件下的上传频道
        process: 此条件是否需要处理
    """
    item: str
    regexp: str
    tags: list[str]
    channel: (str, str)
    process: bool

    def __init__(self, config: dict):
        self.item = config['item']
        self.regexp = str(config['regexp'])
        self.process = config.get('process', True)
        self.tags = config.get('tags', '').split(',')
        channels = config.get('channel', '').split()
        self.channel = (channels[0], channels[1]) if len(channels) == 2 else None


class RoomConfig:
    """ 房间配置
    Configs:
        id: 房间id, 长短号均可
        title: 视频标题(模板字符串)
        description: 视频描述(模板字符串)
        dynamic: 视频动态(模板字符串)
        channel: 上传频道
        tags: 上传标签
        conditions: 房间额外条件
    """
    id: int
    title: str
    description: str
    dynamic: str
    channel: (str, str)
    tags: list[str]
    conditions: list[Condition]

    def __init__(self, config: dict):
        default_desc = '本录播由@_Gliese_的脚本自动处理上传'

        self.id = config['id']
        self.title = config.get('title', '{title}')
        self.description = config.get('description', default_desc)
        self.dynamic = config.get('dynamic', '')
        self.tags = config.get('tags', '').split(',')
        self.conditions = [Condition(c) for c in config.get('conditions', [])]
        channels = config.get('channel', '').split()
        self.channel = (channels[0], channels[1]) if len(channels) == 2 else None

    @classmethod
    def get_config(cls, global_config: GlobalConfig, room_id: int, short_id: int = 0) -> Optional['RoomConfig']:
        room_config_dir = os.path.join(global_config.config_dir, 'room-config.yml')
        configs = FileUtils.YmlReader(room_config_dir)
        for room in configs['rooms']:
            if int(room['id']) == room_id or int(room['id']) == short_id:
                return cls(room)
        return None

    def list_conditions(self, live_info: LiveInfo) -> list[Condition]:
        """ 返回符合条件的额外条件

        :param live_info: 直播信息
        :return: 符合条件的额外条件
        """
        result = []
        for condition in self.conditions:
            try:
                if re.search(pattern=condition.regexp, string=live_info.__getattribute__(condition.item)):
                    result.append(condition)
            except AttributeError as _:
                logging.error('Invalid condition: %s', condition.item)
        return result

    def set_channel(self, channel_str: str):
        """ 设置频道

        :param channel_str: 频道(空格分割)
        """
        channels = channel_str.split()
        if len(channels) == 2:
            self.channel = (channels[0], channels[1])


class LiveInfo:
    """ 直播信息
    Fields:
        room_id: 直播间长号
        short_id: 直播间短号
        anchor: 主播
        title: 直播间标题
        start_time: 开始时间
        parent_area: 父区域
        child_area: 子区域
        session_id: 会话id
    """
    room_id: int
    short_id: int
    anchor: str
    title: str
    start_time: datetime
    parent_area: str
    child_area: str
    session_id: str

    def __init__(self, event_data: dict):
        self.room_id = event_data['RoomId']
        self.short_id = event_data['ShortId']
        self.title = event_data['Title']
        self.session_id = event_data['SessionId']
        self.parent_area = event_data['AreaNameParent']
        self.child_area = event_data['AreaNameChild']
        self.anchor = event_data['Name']


class VideoInfo:
    """ 视频信息
    Fields:
        title: 视频标题
        videos: 视频列表(路径)
        description: 视频描述
        dynamic: 视频动态
        tid: 视频频道id
        tags: 视频标签
    """
    title: str
    videos: list[str]
    description: str
    dynamic: str
    tags: list[str]
    channel: (str, str)
    tid: int

    def __init__(self, room_config: RoomConfig, videos: list[str]):
        self.videos = videos
        self.description = room_config.description
        self.tags = room_config.tags
        self.dynamic = room_config.dynamic
        self.title = room_config.title

    def get_tags(self) -> str:
        if len(self.tags) == 0:
            return ''
        return ','.join(self.tags)

    def set_channel(self, channel: str):
        if channel is not None:
            channel = channel.split()
            if len(channel) == 2:
                self.channel = (channel[0], channel[1])
