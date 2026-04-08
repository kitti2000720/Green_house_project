#include "mqtt_handler.h"
#include "rules.h"

#include <stdio.h>
#include <string.h>

/* ------------------------------------------------------------------ */
/* Topic subscriptions                                                  */
/* Add a new entry here to subscribe to an additional topic pattern.   */
/* ------------------------------------------------------------------ */

static const char *TOPIC_PATTERNS[] = {
    "greenhouse/%d/plant/+/soil",
    "greenhouse/%d/env/temp",
    "greenhouse/%d/env/co2",
};

#define TOPIC_PATTERN_COUNT \
    (int)(sizeof(TOPIC_PATTERNS) / sizeof(TOPIC_PATTERNS[0]))

/* ------------------------------------------------------------------ */
/* MQTT callbacks                                                       */
/* ------------------------------------------------------------------ */

static void on_connect(struct mosquitto *mosq, void *userdata, int rc)
{
    if (rc != 0) {
        fprintf(stderr, "[MQTT] Connection failed: rc=%d\n", rc);
        return;
    }

    mqtt_context_t *ctx = (mqtt_context_t *)userdata;
    ctx->connected = 1;
    printf("[MQTT] Connected (greenhouse_id=%d)\n", ctx->greenhouse_id);

    char topic[128];
    for (int i = 0; i < TOPIC_PATTERN_COUNT; i++) {
        snprintf(topic, sizeof(topic), TOPIC_PATTERNS[i], ctx->greenhouse_id);
        mosquitto_subscribe(mosq, NULL, topic, 1);
        printf("[MQTT] Subscribed: %s\n", topic);
    }
}

static void on_disconnect(struct mosquitto *mosq, void *userdata, int rc)
{
    (void)mosq;
    mqtt_context_t *ctx = (mqtt_context_t *)userdata;
    ctx->connected = 0;
    if (rc != 0) {
        fprintf(stderr, "[MQTT] Unexpected disconnect: rc=%d\n", rc);
    }
}

static void on_message(struct mosquitto *mosq, void *userdata,
                       const struct mosquitto_message *msg)
{
    if (!msg || !msg->payload) return;

    mqtt_context_t *ctx = (mqtt_context_t *)userdata;

    /* Copy payload to a null-terminated buffer. */
    char payload[256];
    int  len = (msg->payloadlen < (int)sizeof(payload) - 1)
                   ? msg->payloadlen
                   : (int)sizeof(payload) - 1;
    memcpy(payload, msg->payload, len);
    payload[len] = '\0';

    printf("[MQTT] %s = %s\n", msg->topic, payload);
    rules_evaluate(mosq, ctx->greenhouse_id, msg->topic, payload);
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */

int mqtt_handler_init(mqtt_context_t *ctx,
                      const char     *host,
                      int             port,
                      int             greenhouse_id)
{
    ctx->greenhouse_id = greenhouse_id;
    ctx->connected     = 0;

    mosquitto_lib_init();

    ctx->mosq = mosquitto_new("greenhouse_rt_controller", true, ctx);
    if (!ctx->mosq) {
        fprintf(stderr, "[MQTT] Failed to create mosquitto client\n");
        mosquitto_lib_cleanup();
        return -1;
    }

    mosquitto_connect_callback_set(ctx->mosq,    on_connect);
    mosquitto_disconnect_callback_set(ctx->mosq, on_disconnect);
    mosquitto_message_callback_set(ctx->mosq,    on_message);

    printf("[MQTT] Connecting to %s:%d\n", host, port);
    if (mosquitto_connect(ctx->mosq, host, port, 60) != MOSQ_ERR_SUCCESS) {
        fprintf(stderr, "[MQTT] Failed to connect to broker\n");
        mosquitto_destroy(ctx->mosq);
        mosquitto_lib_cleanup();
        return -1;
    }

    mosquitto_loop_start(ctx->mosq);
    return 0;
}

void mqtt_handler_cleanup(mqtt_context_t *ctx)
{
    if (!ctx->mosq) return;
    mosquitto_loop_stop(ctx->mosq, true);
    mosquitto_destroy(ctx->mosq);
    mosquitto_lib_cleanup();
    ctx->mosq = NULL;
}
