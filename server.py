import asyncio
import getopt
import importlib
import logging
import multiprocessing
import queue
import sys
from concurrent.futures import ThreadPoolExecutor
from sanic import Sanic
from sanic.response import text

import consts
from models import GlobalConfig, RoomConfig, LiveInfo

logging.basicConfig(level=logging.DEBUG)
app = Sanic('auto-record-upload')


@app.on_request
def pre_action(*_):
    app.ctx.global_config = GlobalConfig(work_dir)


@app.post('/process')
async def processor(request):
    request_body = request.json
    event_type = request_body['EventType']
    event_data = request_body['EventData']
    room_id = int(event_data['RoomId'])
    short_id = int(event_data['ShortId'])

    if event_type == 'SessionStarted':
        logging.info('[%d] session started', room_id)
        app.add_task(app.dispatch(f'session.start.{room_id}'))
    elif event_type == 'FileOpening':
        logging.info('[%d] file opening', room_id)
        app.add_task(app.dispatch(f'file.open.{room_id}', context={
            'file_path': event_data['RelativePath'],
        }))
    elif event_type == 'SessionEnded':
        logging.info('[%d] session ended', room_id)
        app.ctx.process_pool.submit(asyncio.run, app.dispatch(f'session.end.{room_id}', context={
            'event_data': event_data,
            'room_config': RoomConfig.get_config(global_config, room_id, short_id)
        }))
    return text('done')


@app.route('/upload')
async def uploader(_):
    logging.info('uploading videos')
    # copy upload_queue to video_queue
    upload_queue = app.ctx.upload_queue
    _queue = queue.Queue()
    while upload_queue.qsize() > 0:
        _queue.put(upload_queue.get())
    # upload videos in video_queue
    while not _queue.empty():
        info = _queue.get()
        live_info: LiveInfo = info['live_info']
        credential = app.ctx.global_config.credential
        app.add_task(app.dispatch(f'record.upload.{live_info.room_id}', context={
            'credential': credential,
            'info': info,
            'room_config': RoomConfig.get_config(global_config, live_info.room_id, live_info.short_id)
        }))
    return text('done')


@app.main_process_start
def init(*_):
    cpu_count = multiprocessing.cpu_count()
    app.ctx.process_pool = ThreadPoolExecutor(max_workers=min(cpu_count, global_config.workers))
    app.ctx.global_config = global_config
    consts.Paths.init(global_config)
    app.ctx.upload_queue = queue.Queue()


if __name__ == '__main__':
    work_dir = ''
    try:
        options, args = getopt.getopt(sys.argv[1:], 'w:', ['work-dir='])
        for option, value in options:
            if option in ("-w", "--work-dir"):
                work_dir = value
                break
        if work_dir == '':
            raise getopt.GetoptError('work-dir is required')
    except getopt.GetoptError as e:
        logging.error(e)
        sys.exit(2)
    global_config = GlobalConfig(work_dir)
    importlib.import_module('tasks')  # import it to register singles
    app.run(host='0.0.0.0', port=global_config.port,
            debug=False, access_log=False, auto_reload=True)
