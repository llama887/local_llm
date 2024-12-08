#!/usr/bin/env python3


import time

def long_running_task():
    # Simulate a long task
    with open('/tmp/long_running_process.log', 'a') as log_file:
        log_file.write(f"Task started at {time.ctime()}\n")
        time.sleep(60)  # Simulate long task
        log_file.write(f"Task ended at {time.ctime()}\n")
if __name__ == "__main__":
    long_running_task()
