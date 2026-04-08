#ifndef MQTT_HANDLER_H
#define MQTT_HANDLER_H

#include <mosquitto.h>

/*
 * mqtt_context_t - holds all state for one MQTT connection.
 *
 * Pass a pointer to this struct to mqtt_handler_init().
 * The context is owned by the caller; call mqtt_handler_cleanup()
 * before freeing it.
 */
typedef struct {
    struct mosquitto *mosq;
    int               greenhouse_id;
    int               connected;
} mqtt_context_t;

/*
 * mqtt_handler_init - create a mosquitto client, connect to the broker,
 *                     register callbacks and start the network loop.
 *
 * Parameters
 * ----------
 * ctx          : caller-allocated context struct (zeroed before calling)
 * host         : MQTT broker hostname or IP
 * port         : MQTT broker port (typically 1883)
 * greenhouse_id: numeric ID forwarded to the rule engine
 *
 * Returns  0 on success,
 *         -1 on failure.
 */
int  mqtt_handler_init(mqtt_context_t *ctx,
                       const char     *host,
                       int             port,
                       int             greenhouse_id);

/*
 * mqtt_handler_cleanup - stop the network loop, destroy the client,
 *                        and release library resources.
 */
void mqtt_handler_cleanup(mqtt_context_t *ctx);

#endif /* MQTT_HANDLER_H */
