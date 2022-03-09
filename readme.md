### 将B站录播姬录制的录播处理后上传到B站
## 使用文档
### 运行程序
#### python 启动
~~~ commandline
python server.py -w ${work dir}
~~~

#### docker 启动
~~~ commandline
docker run -d -p ${port-outside}:8866 -v ${work-dir}:/process -v ${bililive-recorder-path}:/record --name record-uploader gliese129/record-uploader:latest
~~~
~~~ yaml
# 请确保 global-config.yml 中:
recorder:
   is-docker: true
   
# 此时下面的字段将没有意义
recorder:
   recorder-dir: /record
server:
   port: 8866
~~~

**请确保该目录下存在 config/global-config.yml 和 config/room-config.yml**

**程序启动后config目录下会出现live2video.json，请勿删除**

**请在B站录播姬webhook v2 中加上[http://${your host}/process]()**
### 上传视频

处理完的录播将会放入上传队列等待上传，
此时需要向[http://{your host}:{your port}/upload]()发送get请求

**如果设置了自动上传，将会在视频处理完后自动发送请求**

上传失败的视频会重新放入队列中， 等待下次上传

**注意:重启程序会导致上传队列清空**

### 配置文件
#### global-config.yml
~~~ yaml
recorder:
  record-dir:  # 录播姬工作目录
  delete-after-upload:  # 是否在上传完成后删除*1
  is-docekr:  # 是否在docker中运行
  workers:  # 同时进行的处理视频任务数量*2
  mulipart:  # 视频是否多p(使用web接口，粉丝数不足时会无法成功上传，请注意)， 默认false
  auto-upload:  # 是否自动上传，默认true
  min-time:  # 最短录播时间m，单位为s，默认0s，支持表达式
server:
  port: # 运行端口
  webhooks: # webhook, 在视频处理完成后触发
account:
  credential: # 账户凭据, 详见 https://bili.moyu.moe/#/get-credential *3
    sessdata:
    bili_jct:
    buvid3:
~~~
1. 如果设置为true，即便录播不需要处理也会删除
2. 如果不设置，则默认取CPU核心数和32的最小值;如果设置，则取设置数值和CPU核心数的最小值
3. 账户凭据请勿url decode，否则会上传失败

webhook内容:
~~~ json
POST /test
Host: 127.0.0.1
Content-Type: application/json
User-Agent: Record Uploader

{
  "EventType": "VideoProceed",
  "TimeStamp": "2021-05-14 17:52:44",
  "EventData": {
    "SessionId": "7c7f3672-70ce-405a-aa12-886702ced6e5",
    "RoomId": 23058,
    "ShortId": 3,
    "Name": "3号直播间",
    "Title": "哔哩哔哩音悦台",
    "AreaNameParent": "生活",
    "AreaNameChild": "影音馆"
  },
  "ProceedVideos": ["/session-id/out1.flv", "/session-id/out2.flv"],
  "WorkDictionary": "C://work-dir"
}
~~~
#### room-config.yml
~~~ yaml
rooms:
  - id: # 需要上传的直播间 ID，长号短号均可
    tags:  # 上传所需的tag，英文逗号分割，注意不要加空格
    title: # 视频标题，可以使用模版*1
    description:  # 视频描述
    channel:  # 频道名称，父子分区用空格分割
    conditions:  # 额外的tag条件，注意判断逻辑为&
    - item: # 字段，例如title*2
      regexp: # 匹配的正则
      tags: # 该条件下额外的tag
      channel: # 该条件频道名称，父子分区用空格分割
      process: # 当匹配到对应条件时是否处理
~~~
1. title模板:
    1) ${anchor} => 主播
    2) ${title} => 直播间标题
    3) ${date} => 直播开始日期 YYYY-MM-DD
    4) ${time} => 直播开始时间 HH:mm:SS
    5) ${parent_area} => 直播主分区
    6) ${child_area} => 直播子分区
2. item: ( 该部分本质上是调用self.\_\_getattribute\_\_实现的，如果乱填可能导致程序崩溃，请注意)
    1) room_id 长号
    2) short_id 短号
    3) title 直播间标题
    4) parent_area 主分区
    5) child_area 子分区
   
**condition的判定策略为&(and), 即只要有一个不符合就判定不需要处理**

**channel覆盖逻辑: condition channel > live2video > default channel**
****

### live2video.json
直播分区与视频分区的映射
~~~json
[
  {
    "name": "手游",
    "channel": "游戏 手机游戏"
  },
  {
    "name": "生活",
    "children": [
      {
        "name": "萌宠",
        "channel": "生活 动物圈"
      }
    ]
  }
]
~~~
以上面的json文本为例，直播父分区为“手游”的录播会被直接归类为“游戏 手机游戏”，
而“生活”分区因为同级没有channel，不会被映射，但是“生活 萌宠”会被归类为“生活 动物圈”

直接修改/config/live2video.json即可，修改/resource/live2video.json是无效的