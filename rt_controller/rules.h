#ifndef RULES_H
#define RULES_H

#include <mosquitto.h>
#include "mqtt_handler.h"

/*
 * Rule thresholds — change these values to tune the control logic.
 * No recompilation of other modules is required.
 */
#define RULE_SOIL_MOISTURE_MIN  30      /* % - below this,  pump turns ON   */
#define RULE_SOIL_MOISTURE_MAX  55      /* % - above this,  pump turns OFF  */
#define RULE_TEMP_MAX           30      /* C  - above this, window opens    */
#define RULE_TEMP_MIN           25      /* C  - below this, window closes   */
#define RULE_CO2_ENRICH_ON      600     /* ppm - below this, CO2 enricher ON  */
#define RULE_CO2_ENRICH_OFF     900     /* ppm - above this, CO2 enricher OFF */
#define RULE_CO2_VENT_ON        1200    /* ppm - above this, window opens for ventilation */
#define RULE_CO2_VENT_OFF       900     /* ppm - below this, window can close (CO2 ok)   */
#define RULE_CO2_MAX            1500    /* ppm - above this, alarm fires    */

/*
 * rules_evaluate_snapshot - apply all control rules for one plant.
 *
 * Called from the RT control thread on each periodic cycle.
 * Only evaluates plants whose readings have been received at least once
 * (checked by the caller via snapshot->received[plant_id]).
 *
 * Parameters
 * ----------
 * mosq          : active mosquitto client used for publishing actuator cmds
 * greenhouse_id : numeric ID of the greenhouse (used to build output topics)
 * plant_id      : numeric ID of the plant being evaluated (1-based)
 * snapshot      : read-only copy of the shared sensor state (already unlocked)
 */
/*
 * rules_evaluate_snapshot - evaluate all rules for the greenhouse.
 *
 * Publishes actuator commands only when the desired state differs from the
 * last known state in `act`, then updates `act` to reflect the change.
 * This prevents redundant MQTT traffic on every control cycle.
 */
void rules_evaluate_snapshot(struct mosquitto         *mosq,
                              int                       greenhouse_id,
                              const sensor_snapshot_t  *snapshot,
                              actuator_state_t         *act);

#endif /* RULES_H */
