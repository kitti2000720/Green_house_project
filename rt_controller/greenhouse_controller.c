#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <pthread.h>
#include <time.h>

#include "mqtt_handler.h"
#include "rules.h"
#include "rt_scheduler.h"

#define MQTT_BROKER_HOST    "localhost"
#define MQTT_BROKER_PORT    1883
#define GREENHOUSE_ID       1

/*
 * Control loop period: 100 ms expressed in nanoseconds.
 * clock_nanosleep with TIMER_ABSTIME advances an absolute deadline by this
 * amount each cycle, so accumulated drift is zero over time.
 */
#define LOOP_PERIOD_NS      100000000L   /* 100 ms */

/*
 * Warn when a cycle wakes up more than 5 ms late.
 * Under SCHED_FIFO on real hardware this should rarely trigger.
 */
#define DEADLINE_WARN_NS    5000000L     /* 5 ms */

/* ------------------------------------------------------------------ */

static volatile int   g_running = 1;
static mqtt_context_t g_mqtt;

/* ------------------------------------------------------------------ */

static void handle_signal(int sig)
{
    (void)sig;
    g_running = 0;
}

/*
 * rt_control_loop - periodic real-time task running at SCHED_FIFO priority.
 *
 * Each cycle:
 *  1. Sleep until the next absolute deadline (clock_nanosleep TIMER_ABSTIME).
 *     This eliminates drift: the deadline advances by exactly LOOP_PERIOD_NS
 *     regardless of how long the work took.
 *  2. Measure actual wakeup jitter with clock_gettime(CLOCK_MONOTONIC).
 *  3. Take a lock-free snapshot of the latest sensor readings.
 *  4. Apply control rules for every plant that has received data.
 *
 * Separating rule evaluation from the MQTT callback thread is the reason
 * SCHED_FIFO priority matters: the RT thread is never preempted by the
 * network or OS scheduler while evaluating rules or publishing commands.
 */
static void *rt_control_loop(void *arg)
{
    mqtt_context_t *ctx = (mqtt_context_t *)arg;

    struct timespec deadline;
    clock_gettime(CLOCK_MONOTONIC, &deadline);

    long jitter_max_ns = 0;
    long cycle_count   = 0;

    printf("[RT] Control loop started (period=%ld ms, SCHED_FIFO)\n",
           LOOP_PERIOD_NS / 1000000L);

    while (g_running) {

        /* Advance absolute deadline by one period (no drift). */
        deadline.tv_nsec += LOOP_PERIOD_NS;
        if (deadline.tv_nsec >= 1000000000L) {
            deadline.tv_nsec -= 1000000000L;
            deadline.tv_sec  += 1;
        }

        /* Sleep until the absolute deadline. */
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &deadline, NULL);

        /* Measure how late we actually woke up (jitter). */
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        long jitter_ns = (now.tv_sec  - deadline.tv_sec)  * 1000000000L
                       + (now.tv_nsec - deadline.tv_nsec);

        if (jitter_ns > jitter_max_ns) jitter_max_ns = jitter_ns;

        if (jitter_ns > DEADLINE_WARN_NS) {
            fprintf(stderr,
                    "[RT] WARNING: deadline miss  cycle=%ld  jitter=%ld us\n",
                    cycle_count, jitter_ns / 1000L);
        }

        cycle_count++;

        /* Log timing statistics every 10 cycles (~1 s). */
        if (cycle_count % 10 == 0) {
            printf("[RT] cycle=%-5ld  jitter=%3ld us  max=%3ld us\n",
                   cycle_count, jitter_ns / 1000L, jitter_max_ns / 1000L);
        }

        /* Skip rule evaluation if the broker is not yet connected. */
        if (!ctx->connected) continue;

        /* Take a local copy of the snapshot under the mutex,
         * then immediately release the lock so the MQTT thread is not
         * blocked while rules are evaluated. */
        sensor_snapshot_t snap;
        pthread_mutex_lock(&ctx->snapshot.lock);
        snap                  = ctx->snapshot;
        ctx->snapshot.updated = 0;
        pthread_mutex_unlock(&ctx->snapshot.lock);

        /* Only evaluate rules when new sensor data has arrived. */
        if (!snap.updated) continue;

        for (int plant_id = 1; plant_id <= MAX_PLANTS; plant_id++) {
            if (snap.received[plant_id] == 0) continue;
            rules_evaluate_snapshot(ctx->mosq, ctx->greenhouse_id,
                                    plant_id, &snap);
        }
    }

    printf("[RT] Loop stopped.  cycles=%ld  max_jitter=%ld us\n",
           cycle_count, jitter_max_ns / 1000L);

    return NULL;
}

/* ------------------------------------------------------------------ */

int main(int argc, char *argv[])
{
    int greenhouse_id = GREENHOUSE_ID;
    for (int i = 1; i < argc - 1; i++) {
        if (strcmp(argv[i], "--greenhouse-id") == 0) {
            greenhouse_id = atoi(argv[i + 1]);
            i++;
        }
    }

    printf("=== Greenhouse RT-Controller (greenhouse_id=%d) ===\n\n",
           greenhouse_id);

    signal(SIGINT,  handle_signal);
    signal(SIGTERM, handle_signal);

    /* Attempt SCHED_FIFO + mlockall.  Falls back gracefully if unprivileged. */
    if (rt_scheduler_init(RT_PRIORITY) != 0) {
        fprintf(stderr,
                "[Main] Real-time scheduling unavailable. "
                "Running at normal priority.\n");
    }

    if (mqtt_handler_init(&g_mqtt,
                          MQTT_BROKER_HOST,
                          MQTT_BROKER_PORT,
                          greenhouse_id) != 0) {
        return EXIT_FAILURE;
    }

    /* Pass the MQTT context to the RT thread so it can read the snapshot
     * and publish actuator commands directly. */
    pthread_t rt_thread;
    if (pthread_create(&rt_thread, NULL, rt_control_loop, &g_mqtt) != 0) {
        perror("[Main] pthread_create failed");
        mqtt_handler_cleanup(&g_mqtt);
        return EXIT_FAILURE;
    }

    printf("\n[Main] System running. Active rules:\n");
    printf("  RULE_SOIL : moisture < %d%%    -> pump ON\n",   RULE_SOIL_MOISTURE_MIN);
    printf("  RULE_TEMP : temp     > %dC     -> window OPEN\n", RULE_TEMP_MAX);
    printf("  RULE_CO2  : co2      > %d ppm  -> alarm CRITICAL\n\n", RULE_CO2_MAX);

    while (g_running) {
        sleep(1);
    }

    printf("\n[Main] Shutting down...\n");
    pthread_join(rt_thread, NULL);
    mqtt_handler_cleanup(&g_mqtt);
    printf("[Main] Done.\n");

    return EXIT_SUCCESS;
}
