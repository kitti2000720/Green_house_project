#ifndef MQTT_HANDLER_H
#define MQTT_HANDLER_H

#include <mosquitto.h>
#include <pthread.h>

/*
 * Maximum number of plant nodes per greenhouse.
 * Plant IDs are 1-based; index 0 is unused.
 */
#define MAX_PLANTS 16

/*
 * sensor_snapshot_t - latest sensor readings for all plants.
 *
 * Written by the MQTT callback thread; read by the RT control thread.
 * Access must be protected by the embedded mutex.
 *
 * received[plant_id] is a bitmask:
 *   bit 0 (0x1) : soil reading arrived
 *   bit 1 (0x2) : temp reading arrived
 *   bit 2 (0x4) : co2 reading arrived
 */
typedef struct {
    int             soil[MAX_PLANTS + 1];
    int             temp[MAX_PLANTS + 1];
    int             co2[MAX_PLANTS + 1];
    int             received[MAX_PLANTS + 1];
    int             updated;
    pthread_mutex_t lock;
} sensor_snapshot_t;

/*
 * mqtt_context_t - holds all state for one MQTT connection.
 *
 * Pass a pointer to this struct to mqtt_handler_init().
 * The context is owned by the caller; call mqtt_handler_cleanup()
 * before freeing it.
 */
typedef struct {
    struct mosquitto  *mosq;
    int                greenhouse_id;
    int                connected;
    sensor_snapshot_t  snapshot;
} mqtt_context_t;

int  mqtt_handler_init(mqtt_context_t *ctx,
                       const char     *host,
                       int             port,
                       int             greenhouse_id);

void mqtt_handler_cleanup(mqtt_context_t *ctx);

#endif /* MQTT_HANDLER_H */
