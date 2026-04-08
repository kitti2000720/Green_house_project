#include "rules.h"

#include <stdio.h>
#include <stdlib.h>
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

/*
 * Extract the plant ID from a topic of the form
 * "greenhouse/<id>/plant/<plant_id>/..."
 *
 * Returns the plant ID, or -1 if the pattern is not found.
 */
static int extract_plant_id(const char *topic)
{
    const char *ptr = strstr(topic, "/plant/");
    if (!ptr) return -1;
    int id = atoi(ptr + 7);   /* skip "/plant/" */
    return (id > 0) ? id : -1;
}

/* ------------------------------------------------------------------ */
/* Rule evaluation                                                      */
/* ------------------------------------------------------------------ */

void rules_evaluate(struct mosquitto *mosq,
                    int               greenhouse_id,
                    const char       *topic,
                    const char       *payload)
{
    char out_topic[128];

    /* --- RULE_SOIL: low moisture -> turn pump ON ------------------- */
    if (strstr(topic, "/soil")) {
        int moisture = atoi(payload);
        if (moisture < RULE_SOIL_MOISTURE_MIN) {
            int plant_id = extract_plant_id(topic);
            if (plant_id < 1) return;

            snprintf(out_topic, sizeof(out_topic),
                     "greenhouse/%d/plant/%d/pump", greenhouse_id, plant_id);

            printf("[Rules] RULE_SOIL: plant=%d  moisture=%d%% < %d%%  -> pump ON\n",
                   plant_id, moisture, RULE_SOIL_MOISTURE_MIN);
            publish(mosq, out_topic, "ON", 1);
        }
        return;
    }

    /* --- RULE_TEMP: high temperature -> open ventilation window ---- */
    if (strstr(topic, "/temp")) {
        int temp = atoi(payload);
        if (temp > RULE_TEMP_MAX) {
            snprintf(out_topic, sizeof(out_topic),
                     "greenhouse/%d/actuators/window", greenhouse_id);

            printf("[Rules] RULE_TEMP: temp=%dC > %dC  -> window OPEN\n",
                   temp, RULE_TEMP_MAX);
            publish(mosq, out_topic, "OPEN", 1);
        }
        return;
    }

    /* --- RULE_CO2: high CO2 -> trigger alarm ----------------------- */
    if (strstr(topic, "/co2")) {
        int co2 = atoi(payload);
        if (co2 > RULE_CO2_MAX) {
            snprintf(out_topic, sizeof(out_topic),
                     "greenhouse/%d/status/alarm", greenhouse_id);

            printf("[Rules] RULE_CO2: co2=%dppm > %dppm  -> alarm CRITICAL\n",
                   co2, RULE_CO2_MAX);
            publish(mosq, out_topic, "CRITICAL", 1);
        }
        return;
    }
}
