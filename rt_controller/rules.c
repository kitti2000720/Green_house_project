#include "rules.h"

#include <stdio.h>
#include <string.h>


static void publish_retained(struct mosquitto *mosq,
                              const char       *topic,
                              const char       *payload)
{
    int len = (int)strlen(payload);
    if (mosquitto_publish(mosq, NULL, topic, len, payload, 1, true) != MOSQ_ERR_SUCCESS)
        fprintf(stderr, "[Rules] Publish failed: %s\n", topic);
}

/* Publish only when desired state differs from last known state. */
static void publish_if_changed(struct mosquitto *mosq,
                                const char       *topic,
                                int               desired,
                                int              *current,
                                const char       *on_str,
                                const char       *off_str,
                                const char       *label)
{
    if (*current == desired) return;
    const char *payload = (desired == ACT_ON) ? on_str : off_str;
    printf("[Rules] %s -> %s\n", label, payload);
    publish_retained(mosq, topic, payload);
    *current = desired;
}


void rules_evaluate_snapshot(struct mosquitto         *mosq,
                              int                       greenhouse_id,
                              const sensor_snapshot_t  *snap,
                              actuator_state_t         *act)
{
    char topic[128];
    char label[80];

    /* ---- Per-plant: PUMP ----------------------------------------- */
    for (int pid = 1; pid <= MAX_PLANTS; pid++) {
        if (!(snap->received[pid] & 0x1)) continue;

        int desired;
        if      (snap->soil[pid] <  RULE_SOIL_MOISTURE_MIN) desired = ACT_ON;
        else if (snap->soil[pid] >= RULE_SOIL_MOISTURE_MAX) desired = ACT_OFF;
        else continue;   /* hysteresis band — hold current state */

        snprintf(topic, sizeof(topic),
                 "greenhouse/%d/plant/%d/pump", greenhouse_id, pid);
        snprintf(label, sizeof(label),
                 "PUMP gh=%d plant=%d soil=%d%%", greenhouse_id, pid, snap->soil[pid]);
        publish_if_changed(mosq, topic, desired, &act->pump[pid],
                           "ON", "OFF", label);
    }

    /* ---- Greenhouse-level: WINDOW -------------------------------- */
    /*
     * Opens when ANY plant exceeds RULE_TEMP_MAX (temperature)
     *        OR  ANY plant exceeds RULE_CO2_VENT_ON (CO2 ventilation).
     * Closes when ALL measured plants are within safe limits AND
     *   CO2 data has been received (avoids transient CLOSED at startup).
     */
    {
        int want_open  = 0;
        int want_close = 1;
        int have_data  = 0;
        int have_co2   = 0;

        for (int pid = 1; pid <= MAX_PLANTS; pid++) {
            int has_temp = snap->received[pid] & 0x2;
            int has_co2  = snap->received[pid] & 0x4;
            if (!has_temp && !has_co2) continue;
            have_data = 1;
            if (has_co2) have_co2 = 1;

            if (has_temp && snap->temp[pid] > RULE_TEMP_MAX)    want_open  = 1;
            if (has_co2  && snap->co2[pid]  > RULE_CO2_VENT_ON) want_open  = 1;

            if (has_temp && snap->temp[pid] > RULE_TEMP_MIN)     want_close = 0;
            if (has_co2  && snap->co2[pid]  > RULE_CO2_VENT_OFF) want_close = 0;
        }

        if (have_data && have_co2) {
            int desired_win;
            if      (want_open)  desired_win = ACT_ON;
            else if (want_close) desired_win = ACT_OFF;
            else                 desired_win = act->window;  /* hysteresis — hold */

            if (desired_win != ACT_UNKNOWN) {
                snprintf(topic, sizeof(topic), "greenhouse/%d/window", greenhouse_id);
                snprintf(label, sizeof(label), "WINDOW gh=%d", greenhouse_id);
                publish_if_changed(mosq, topic, desired_win, &act->window,
                                   "OPEN", "CLOSED", label);
            }
        }
    }

    /* ---- Greenhouse-level: CO2 ENRICHER -------------------------- */
    /*
     * Turns ON when CO2 < RULE_CO2_ENRICH_ON and window is closed.
     * Turns OFF when CO2 >= RULE_CO2_ENRICH_OFF or window opens.
     */
    {
        int co2_low  = 0;
        int co2_ok   = 1;
        int have_co2 = 0;

        for (int pid = 1; pid <= MAX_PLANTS; pid++) {
            if (!(snap->received[pid] & 0x4)) continue;
            have_co2 = 1;
            if (snap->co2[pid] <  RULE_CO2_ENRICH_ON)  co2_low = 1;
            if (snap->co2[pid] >= RULE_CO2_ENRICH_OFF)  co2_ok  = 0;
        }

        if (have_co2) {
            int window_open = (act->window == ACT_ON);
            int desired_enrich;

            if      (window_open) desired_enrich = ACT_OFF;
            else if (co2_low)     desired_enrich = ACT_ON;
            else if (!co2_ok)     desired_enrich = ACT_OFF;
            else                  desired_enrich = act->co2_enricher;  /* hold */

            if (desired_enrich != ACT_UNKNOWN) {
                snprintf(topic, sizeof(topic), "greenhouse/%d/co2_enricher", greenhouse_id);
                snprintf(label, sizeof(label), "CO2_ENRICHER gh=%d", greenhouse_id);
                publish_if_changed(mosq, topic, desired_enrich, &act->co2_enricher,
                                   "ON", "OFF", label);
            }
        }
    }

    /* ---- CO2 ALARM ----------------------------------------------- */
    /*
     * Publishes CRITICAL when any plant exceeds RULE_CO2_MAX.
     * Publishes OK (retained) once all measured plants are below threshold
     * so the dashboard can clear the alert automatically.
     */
    {
        int alarm_active = 0;
        int have_co2     = 0;

        for (int pid = 1; pid <= MAX_PLANTS; pid++) {
            if (!(snap->received[pid] & 0x4)) continue;
            have_co2 = 1;
            if (snap->co2[pid] > RULE_CO2_MAX) alarm_active = 1;
        }

        if (have_co2) {
            snprintf(topic, sizeof(topic), "greenhouse/%d/status/alarm", greenhouse_id);
            int desired_alarm = alarm_active ? ACT_ON : ACT_OFF;
            if (desired_alarm != act->alarm) {
                const char *payload = alarm_active ? "CRITICAL" : "OK";
                printf("[Rules] CO2 ALARM gh=%d -> %s\n", greenhouse_id, payload);
                publish_retained(mosq, topic, payload);
                act->alarm = desired_alarm;
            }
        }
    }
}
