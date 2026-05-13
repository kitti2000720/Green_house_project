#ifndef MQTT_HANDLER_H
#define MQTT_HANDLER_H

#include <mosquitto.h>
#include <pthread.h>

#define MAX_PLANTS 16

typedef struct {
    int             soil[MAX_PLANTS + 1];
    int             temp[MAX_PLANTS + 1];
    int             co2[MAX_PLANTS + 1];
    int             received[MAX_PLANTS + 1];
    int             updated;
    pthread_mutex_t lock;
} sensor_snapshot_t;

#define ACT_UNKNOWN -1
#define ACT_OFF      0
#define ACT_ON       1

typedef struct {
    int pump[MAX_PLANTS + 1];
    int window;
    int co2_enricher;
    int alarm;
} actuator_state_t;

typedef struct {
    struct mosquitto  *mosq;
    int                greenhouse_id;
    int                connected;
    sensor_snapshot_t  snapshot;
    actuator_state_t   actuators;
} mqtt_context_t;

int  mqtt_handler_init(mqtt_context_t *ctx,
                       const char     *host,
                       int             port,
                       int             greenhouse_id);

void mqtt_handler_cleanup(mqtt_context_t *ctx);

#endif
