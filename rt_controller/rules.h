#ifndef RULES_H
#define RULES_H

#include <mosquitto.h>

/*
 * Rule thresholds - change these values to tune the control logic.
 * No recompilation of other modules is required.
 */
#define RULE_SOIL_MOISTURE_MIN  30      /* % - below this, pump turns ON    */
#define RULE_TEMP_MAX           30      /* C - above this, window opens     */
#define RULE_CO2_MAX            1500    /* ppm - above this, alarm fires    */

/*
 * rules_evaluate - check one sensor reading against all active rules
 *                  and publish actuator commands if a rule fires.
 *
 * Parameters
 * ----------
 * mosq          : active mosquitto client used for publishing
 * greenhouse_id : numeric ID of the greenhouse (used to build topics)
 * topic         : incoming MQTT topic string
 * payload       : incoming MQTT payload string (null-terminated)
 */
void rules_evaluate(struct mosquitto *mosq,
                    int               greenhouse_id,
                    const char       *topic,
                    const char       *payload);

#endif /* RULES_H */
