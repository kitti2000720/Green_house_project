#include "rules.h"

#include <stdio.h>
#include <string.h>

/* ------------------------------------------------------------------ */
/* Internal helpers                                                     */
/* ------------------------------------------------------------------ */

static void publish(struct mosquitto *mosq,
                    const char       *topic,
                    const char       *payload,
                    int               qos)
{
    int len = (int)strlen(payload);
    if (mosquitto_publish(mosq, NULL, topic, len, payload, qos, false) != MOSQ_ERR_SUCCESS) {
        fprintf(stderr, "[Rules] Publish failed: %s\n", topic);
    }
}

/* ------------------------------------------------------------------ */
/* Rule evaluation                                                      */
/* ------------------------------------------------------------------ */

/*
 * rules_evaluate_snapshot - called by the RT thread every control cycle.
 *
 * The snapshot is a local copy taken under the mutex in the main loop,
 * so this function runs fully lock-free and with bounded execution time.
 *
 * Each rule checks one metric and publishes one actuator command when
 * the threshold is crossed.  Only metrics marked as received are checked.
 */
void rules_evaluate_snapshot(struct mosquitto         *mosq,
                              int                       greenhouse_id,
                              int                       plant_id,
                              const sensor_snapshot_t  *snap)
{
    char out_topic[128];

    /* RULE_SOIL: low moisture -> pump ON */
    if ((snap->received[plant_id] & 0x1) &&
        snap->soil[plant_id] < RULE_SOIL_MOISTURE_MIN)
    {
        snprintf(out_topic, sizeof(out_topic),
                 "greenhouse/%d/plant/%d/pump", greenhouse_id, plant_id);
        printf("[Rules] RULE_SOIL: plant=%d  moisture=%d%% < %d%%  -> pump ON\n",
               plant_id, snap->soil[plant_id], RULE_SOIL_MOISTURE_MIN);
        publish(mosq, out_topic, "ON", 1);
    }

    /* RULE_TEMP: high temperature -> window OPEN */
    if ((snap->received[plant_id] & 0x2) &&
        snap->temp[plant_id] > RULE_TEMP_MAX)
    {
        snprintf(out_topic, sizeof(out_topic),
                 "greenhouse/%d/plant/%d/window", greenhouse_id, plant_id);
        printf("[Rules] RULE_TEMP: plant=%d  temp=%dC > %dC  -> window OPEN\n",
               plant_id, snap->temp[plant_id], RULE_TEMP_MAX);
        publish(mosq, out_topic, "OPEN", 1);
    }

    /* RULE_CO2: critical CO2 -> alarm */
    if ((snap->received[plant_id] & 0x4) &&
        snap->co2[plant_id] > RULE_CO2_MAX)
    {
        snprintf(out_topic, sizeof(out_topic),
                 "greenhouse/%d/status/alarm", greenhouse_id);
        printf("[Rules] RULE_CO2: plant=%d  co2=%dppm > %dppm  -> alarm CRITICAL\n",
               plant_id, snap->co2[plant_id], RULE_CO2_MAX);
        publish(mosq, out_topic, "CRITICAL", 1);
    }
}
