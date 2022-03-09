from datetime import datetime
import logging
import os
import requests
from bilibili_api import Credential
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException
from sanic import Sanic
from exceptions import *
from utils.Uploader import Uploader
from utils.Processor import Processor
from utils.FileUtils import DeleteFolder, DeleteFiles
from models import RoomConfig, GlobalConfig, LiveInfo

app = Sanic.get_app()


@app.signal('session.start.<room_id:int>')
def session_start(room_id: int):
    """ 直播会话开始

    :param room_id: 房间id
    :return:
    """
    start_time = datetime.now()
    logging.debug('[%d] live session started at %s', room_id, start_time.strftime("%Y-%m-%d %H:%M:%S"))
    Processor.live_start(room_id=room_id, start_time=start_time)


@app.signal('file.open.<room_id:int>')
def file_open(room_id: int, file_path: str):
    """ 录播文件写入

    :param room_id: 房间id
    :param file_path: 录播文件路径
    :return:
    """
    logging.debug('[%d] file path: %s', room_id, file_path)
    Processor.file_open(room_id=room_id, file_path=file_path)


@app.signal('session.end.<room_id:int>')
async def session_end(room_id: int, event_data: dict, room_config: RoomConfig):
    """ 直播会话结束

    :param room_id: 房间id
    :param event_data: 录播姬webhook发送的event_data
    :param room_config: 房间配置
    :return:
    """
    global_config: GlobalConfig = app.ctx.global_config
    process = Processor(event_data=event_data, room_config=room_config)
    process.live_end()
    if process.check_if_need_process():
        logging.info('[%d] processing...', room_id)
        try:
            result_videos = await process.process(multipart=global_config.multipart)
        except FileExistsError as e:
            logging.warning(e)
            return

        # send webhook
        for url in global_config.webhooks:
            app.add_task(send_webhook(
                url=url, event_data=event_data, videos=result_videos,
                work_dir=global_config.work_dir
            ))
        # add video to upload queue
        if not global_config.auto_upload:
            logging.info('[%s] adding videos to waiting list...', room_id)
        upload_queue = app.ctx.upload_queue
        upload_queue.put({
            'videos': result_videos,
            'origin_stems': process.origin_stems,
            'live_info': process.live_info
        })
        if global_config.auto_upload:
            requests.get(f'http://localhost:{global_config.port}/upload')
    else:
        if global_config.delete:
            logging.info('[%d] deleting origin videos by global config...', room_id)
            DeleteFiles(file_stems=process.origin_stems, types=['flv', 'xml'])


@app.signal('record.upload.<room_id:int>')
async def video_upload(room_id: int, room_config: RoomConfig, credential: Credential, info: dict):
    """ 上传视频

    :param room_id: 房间id
    :param room_config: 房间配置
    :param info: 上传信息
    :param credential: 用户凭证
    """
    global_config = app.ctx.global_config
    uploader = Uploader(credential=credential, room_config=room_config, **info)
    live_info: LiveInfo = info['live_info']
    dir_path = os.path.join(global_config.work_dir, live_info.session_id)
    try:
        await uploader.upload()
        # successfully upload or no files -> delete files
        logging.info('[%d] uploading succeeded, deleting proceed videos in folder %s...', room_id, dir_path)
        DeleteFolder(dir_path)
        if global_config.delete:
            logging.info('[%d] deleting origin videos...', room_id)
            DeleteFiles(file_stems=info.get('origin_stems'), types=['flv', 'xml'])
    except (InvalidParamException, ResponseCodeException) as e:
        # failed to upload -> add to upload queue again
        logging.warning('[%d] uploading failed, adding to upload queue again...', room_id)
        logging.warning(e)
        upload_queue = app.ctx.upload_queue
        upload_queue.put(info)
    except FileNotFoundError:
        # no files
        logging.warning('[%d] no files to upload, deleting origin videos...', room_id)
        logging.error('please check the reason why no videos are proceeded, '
                      'also please remember that origin videos won\'t be deleted so you need to delete them manually')
        DeleteFolder(dir_path)


async def send_webhook(url: str, event_data: dict, videos: list[str], work_dir: str):
    logging.info('sending webhook to %s', url)
    request_body = {
        'EventType': 'VideoProceed',
        'TimeStamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'EventData': event_data,
        'ProceedVideos': [video.replace(work_dir, '') for video in videos],
        'WorkDictionary': work_dir
    }
    headers = {
        'User-Agent': 'Record Uploader',
        'content-type': 'application/json'
    }
    # send webhook to url with requests and set timeout 100s (retry 3 times)
    for _ in range(3):
        with requests.post(url, json=request_body, headers=headers, timeout=100) as response:
            if response.status_code == 200:
                logging.info('send webhook to %s successfully', url)
                return
            logging.error('%d: %s', response.status_code, response.reason)
