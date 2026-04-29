#ifndef RULES_H
#define RULES_H

#include <mosquitto.h>
#include "mqtt_handler.h"

/*
 * Rule thresholds — change these values to tune the control logic.
 * No recompilation of other modules is required.
 */
#define RULE_SOIL_MOISTURE_MIN  30      /* % - below this, pump turns ON    */
#define RULE_TEMP_MAX           30      /* C - above this, window opens     */
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
void rules_evaluate_snapshot(struct mosquitto         *mosq,
                              int                       greenhouse_id,
                              int                       plant_id,
                              const sensor_snapshot_t  *snapshot);

#endif /* RULES_H */
