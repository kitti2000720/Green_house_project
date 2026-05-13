#ifndef RULES_H
#define RULES_H

#include <mosquitto.h>
#include "mqtt_handler.h"

#define RULE_SOIL_MOISTURE_MIN  30
#define RULE_SOIL_MOISTURE_MAX  55
#define RULE_TEMP_MAX           30
#define RULE_TEMP_MIN           25
#define RULE_CO2_ENRICH_ON      600
#define RULE_CO2_ENRICH_OFF     900
#define RULE_CO2_VENT_ON        1200
#define RULE_CO2_VENT_OFF       900
#define RULE_CO2_MAX            1500

void rules_evaluate_snapshot(struct mosquitto         *mosq,
                              int                       greenhouse_id,
                              const sensor_snapshot_t  *snapshot,
                              actuator_state_t         *act);

#endif
