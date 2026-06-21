from io import StringIO

from videocenter.models.hls import HlsTask
from videocenter.services.hls import _consume_ffmpeg_progress


def test_ffmpeg_progress_updates_task_from_output_time():
    class FakeDb:
        def __init__(self):
            self.progress_values = []

        def commit(self):
            self.progress_values.append(task.progress)

    class FakeProcess:
        stdout = iter(
            [
                "frame=10\n",
                "out_time_us=25000000\n",
                "out_time_us=50000000\n",
                "out_time_us=150000000\n",
            ]
        )
        stderr = StringIO("")

    task = HlsTask(resource_id=1, progress=5)
    db = FakeDb()

    _consume_ffmpeg_progress(db, task, FakeProcess(), 100)

    assert db.progress_values == [25.0, 50.0, 99]
    assert task.progress == 99
