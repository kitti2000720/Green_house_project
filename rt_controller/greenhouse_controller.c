#include <stdio.h>
#include <stdlib.h>
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
#define LOOP_INTERVAL_NS    100000000   /* 100 ms */

/* ------------------------------------------------------------------ */

static volatile int     g_running = 1;
static mqtt_context_t   g_mqtt;

/* ------------------------------------------------------------------ */

static void handle_signal(int sig)
{
    (void)sig;
    g_running = 0;
}

/*
 * rt_control_loop - high-frequency periodic task.
 *
 * Currently sleeps at 100 ms intervals.  Extend this function when
 * deterministic per-cycle work is needed (e.g. PID calculations).
 */
static void *rt_control_loop(void *arg)
{
    (void)arg;
    struct timespec ts = {0, LOOP_INTERVAL_NS};

    printf("[RT] Control loop started (%d ms tick)\n",
           LOOP_INTERVAL_NS / 1000000);

    while (g_running) {
        nanosleep(&ts, NULL);
    }

    return NULL;
}

/* ------------------------------------------------------------------ */

int main(void)
{
    printf("=== Greenhouse RT-Controller ===\n\n");

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
                          GREENHOUSE_ID) != 0) {
        return EXIT_FAILURE;
    }

    pthread_t rt_thread;
    if (pthread_create(&rt_thread, NULL, rt_control_loop, NULL) != 0) {
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
