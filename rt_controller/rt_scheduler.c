#include "rt_scheduler.h"

#include <sched.h>
#include <sys/mman.h>
#include <stdio.h>

int rt_scheduler_init(int priority)
{
    struct sched_param param;
    param.sched_priority = priority;

    if (sched_setscheduler(0, SCHED_FIFO, &param) == -1) {
        perror("[RT-Scheduler] sched_setscheduler failed");
        return -1;
    }

    if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
        perror("[RT-Scheduler] mlockall failed");
        return -1;
    }

    printf("[RT-Scheduler] SCHED_FIFO enabled (priority=%d)\n", priority);
    return 0;
}
