class Task:
    def __init__(self, source: str,
                 data,
                 offset: float,
                 overlap: float,
                 task_id: str,
                 socket_id: str,
                 is_final: bool,
                 time_start: float,
                 time_submit: float) -> None:
        self.source = source
        self.data = data
        self.offset = offset
        self.overlap = overlap
        self.task_id = task_id
        self.socket_id = socket_id
        self.is_final = is_final
        self.time_start = time_start
        self.time_submit = time_submit
        self.samplerate = 16000


class Result:
    def __init__(self, task_id, socket_id, source) -> None:
        self.task_id = task_id          # 任务 id
        self.socket_id = socket_id      # socket id
        self.source = source            # 是从 'file' 还是 'mic' 的音频流得到的结果

        self.duration = 0               # 全部音频时长
        self.time_start = 0             # 录音开始的时刻
        self.time_submit = 0            # 片段提交时间
        self.time_complete = 0          # 识别完成时间

        self.tokens = []                # 字级 token
        self.timestamps = []            # 字级 token 的时间戳
        self.text = ''                  # 合并的文字
        self.is_final = False           # 是否已完成所有片段识别
