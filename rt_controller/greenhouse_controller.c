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

#define LOOP_PERIOD_NS      100000000L
#define DEADLINE_WARN_NS    5000000L

static volatile int   g_running = 1;
static mqtt_context_t g_mqtt;

static void handle_signal(int sig)
{
    (void)sig;
    g_running = 0;
}

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

        deadline.tv_nsec += LOOP_PERIOD_NS;
        if (deadline.tv_nsec >= 1000000000L) {
            deadline.tv_nsec -= 1000000000L;
            deadline.tv_sec  += 1;
        }

        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &deadline, NULL);

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

        if (cycle_count % 10 == 0) {
            printf("[RT] cycle=%-5ld  jitter=%3ld us  max=%3ld us\n",
                   cycle_count, jitter_ns / 1000L, jitter_max_ns / 1000L);
        }

        if (!ctx->connected) continue;

        sensor_snapshot_t snap;
        pthread_mutex_lock(&ctx->snapshot.lock);
        snap                  = ctx->snapshot;
        ctx->snapshot.updated = 0;
        pthread_mutex_unlock(&ctx->snapshot.lock);

        if (!snap.updated) continue;

        rules_evaluate_snapshot(ctx->mosq, ctx->greenhouse_id,
                                &snap, &ctx->actuators);
    }

    printf("[RT] Loop stopped.  cycles=%ld  max_jitter=%ld us\n",
           cycle_count, jitter_max_ns / 1000L);

    return NULL;
}

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
