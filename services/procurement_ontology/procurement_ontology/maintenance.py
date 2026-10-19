"""Single-process admission gate shared by service and persistence writers."""

import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps


class MaintenanceError(RuntimeError):
    pass


class WriteGate:
    def __init__(self):
        self._condition = threading.Condition()
        self._maintenance, self._active = False, 0
        self._depth = ContextVar("procurement_write_depth_" + str(id(self)), default=0)
        self._internal = ContextVar("procurement_maintenance_internal_" + str(id(self)), default=False)

    @property
    def maintenance_active(self):
        with self._condition:
            return self._maintenance

    @contextmanager
    def writer(self):
        if self._depth.get() or self._internal.get():
            yield
            return
        with self._condition:
            if self._maintenance:
                raise MaintenanceError("服务处于维护窗口，暂不接受新写入")
            self._active += 1
        token = self._depth.set(1)
        try:
            yield
        finally:
            self._depth.reset(token)
            with self._condition:
                self._active -= 1
                self._condition.notify_all()

    @contextmanager
    def maintenance(self):
        if self._depth.get():
            raise MaintenanceError("不能在进行中的写操作内开始备份")
        with self._condition:
            if self._maintenance:
                raise MaintenanceError("已有维护操作正在进行")
            self._maintenance = True
            deadline = time.monotonic() + 180
            while self._active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._maintenance = False
                    raise MaintenanceError("等待在途写入超时，未开始备份")
                self._condition.wait(remaining)
        token = self._internal.set(True)
        try:
            yield
        finally:
            self._internal.reset(token)
            with self._condition:
                self._maintenance = False
                self._condition.notify_all()


def business_write(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.store.gate.writer():
            return method(self, *args, **kwargs)
    return guarded
