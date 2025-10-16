"Return elapsed time and CPU time."

import time


class Timer:
    "Return elapsed time and CPU time since creation of the instance."

    def __init__(self):
        self.time = time.time()
        self.process_time = time.process_time()

    def __str__(self):
        return ", ".join(self.current.items())

    @property
    def elapsed(self):
        return time.time() - self.time

    @property
    def cputime(self):
        return time.process_time() - self.process_time

    @property
    def current(self):
        return {
            "elapsed time": f"{self.elapsed:.3f}",
            "CPU time": f"{self.cputime:.3f}",
        }

    @property
    def now(self):
        return time.strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    timer = Timer()
    print(timer.now)
    time.sleep(1)
    for a in range(1_000_000):
        b = a + a
    print(timer.current)
