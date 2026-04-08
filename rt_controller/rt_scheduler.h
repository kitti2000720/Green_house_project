#ifndef RT_SCHEDULER_H
#define RT_SCHEDULER_H

/* Default SCHED_FIFO priority (1-99, higher = more priority). */
#define RT_PRIORITY 80

/*
 * rt_scheduler_init - configure the calling process for real-time execution.
 *
 * Sets SCHED_FIFO scheduling at the given priority and locks all
 * memory pages to prevent page faults during the control loop.
 *
 * Returns  0 on success,
 *         -1 on failure (process continues at normal priority).
 *
 * Requires CAP_SYS_NICE (i.e. run with sudo or set capabilities).
 */
int rt_scheduler_init(int priority);

#endif /* RT_SCHEDULER_H */
