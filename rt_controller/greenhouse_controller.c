#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sched.h>
#include <time.h>
#include <sys/mman.h>
#include <pthread.h>
#include <mqtt.h>
#include <memory.h>

#define MQTT_BROKER_HOST "localhost"
#define MQTT_BROKER_PORT 1883
#define MAX_BUF_SIZE 1024
#define PRIORITY 80

// Real-time task structure
typedef struct {
    int greenhouse_id;
    mqtt_client_t *client;
    int running;
} rt_context_t;

// Global context
rt_context_t rt_context;

// MQTT callback for handling incoming messages
void on_message_received(void **unused, struct mqtt_response_start *response, 
                         struct mqtt_response_publish *published, 
                         struct mqtt_response_puback *puback) {
    if (published) {
        char topic_buf[256];
        char payload_buf[256];
        
        memcpy(topic_buf, published->topic_name, published->topic_name_size);
        topic_buf[published->topic_name_size] = '\0';
        
        memcpy(payload_buf, published->application_message, 
               published->application_message_size);
        payload_buf[published->application_message_size] = '\0';
        
        printf("[RT-Controller] Received: Topic=%s, Payload=%s\n", topic_buf, payload_buf);
        
        // Parse and execute rules
        if (strstr(topic_buf, "soil")) {
            int moisture = atoi(payload_buf);
            // Rule 1: Targeted Watering
            if (moisture < 30) {
                int plant_id = 3; // Extract from topic
                char pump_topic[128];
                snprintf(pump_topic, sizeof(pump_topic), 
                         "greenhouse/%d/plant/%d/pump", rt_context.greenhouse_id, plant_id);
                
                printf("[RT-Controller] RULE 1: Soil moisture critical (%d%%). Turning ON pump.\n", moisture);
                mqtt_publish(rt_context.client, pump_topic, "ON", 2, MQTT_PUBLISH_QOS_1);
            }
        } 
        else if (strstr(topic_buf, "temp")) {
            int temp = atoi(payload_buf);
            // Rule 2: Ventilation Control
            if (temp > 30) {
                char window_topic[128];
                snprintf(window_topic, sizeof(window_topic), 
                         "greenhouse/%d/actuators/window", rt_context.greenhouse_id);
                
                printf("[RT-Controller] RULE 2: Temperature too high (%d°C). Opening window.\n", temp);
                mqtt_publish(rt_context.client, window_topic, "OPEN", 4, MQTT_PUBLISH_QOS_1);
            }
        }
        else if (strstr(topic_buf, "co2")) {
            int co2 = atoi(payload_buf);
            // Rule 3: Safety Alert
            if (co2 > 1500) {
                char alarm_topic[128];
                snprintf(alarm_topic, sizeof(alarm_topic), 
                         "greenhouse/%d/status/alarm", rt_context.greenhouse_id);
                
                printf("[RT-Controller] RULE 3: CO2 CRITICAL (%d ppm). Triggering ALARM.\n", co2);
                mqtt_publish(rt_context.client, alarm_topic, "CRITICAL", 8, MQTT_PUBLISH_QOS_1);
            }
        }
    }
}

// Real-time scheduler setup
int setup_realtime_scheduling() {
    struct sched_param param;
    param.sched_priority = PRIORITY;
    
    if (sched_setscheduler(0, SCHED_FIFO, &param) == -1) {
        perror("sched_setscheduler failed");
        return -1;
    }
    
    // Lock memory to prevent paging
    if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
        perror("mlockall failed");
        return -1;
    }
    
    printf("[RT-Controller] Real-time scheduling enabled (SCHED_FIFO, priority=%d)\n", PRIORITY);
    return 0;
}

// Main real-time control loop
void* rt_control_loop(void *arg) {
    rt_context_t *ctx = (rt_context_t *)arg;
    struct timespec ts;
    
    printf("[RT-Controller] Real-time control loop started.\n");
    
    while (ctx->running) {
        // Sleep with high precision timing
        clock_gettime(CLOCK_REALTIME, &ts);
        ts.tv_nsec += 100000000; // 100ms loop
        
        if (ts.tv_nsec >= 1000000000) {
            ts.tv_sec++;
            ts.tv_nsec -= 1000000000;
        }
        
        nanosleep(&ts, NULL);
    }
    
    return NULL;
}

// Initialize MQTT connection
int mqtt_connect(rt_context_t *ctx) {
    // Note: This is a simplified version. In production, use proper MQTT library
    // Recommended: Use libmosquitto or paho-mqtt-c
    printf("[RT-Controller] Connecting to MQTT broker at %s:%d\n", 
           MQTT_BROKER_HOST, MQTT_BROKER_PORT);
    
    // Subscribe to sensor topics
    printf("[RT-Controller] Subscribing to sensor topics...\n");
    printf("  - greenhouse/%d/plant/+/soil\n", ctx->greenhouse_id);
    printf("  - greenhouse/%d/env/temp\n", ctx->greenhouse_id);
    printf("  - greenhouse/%d/env/co2\n", ctx->greenhouse_id);
    
    return 0;
}

int main(int argc, char *argv[]) {
    printf("=========================================\n");
    printf("Greenhouse RT-Controller (Linux C RT)\n");
    printf("=========================================\n\n");
    
    // Initialize RT context
    rt_context.greenhouse_id = 1;
    rt_context.running = 1;
    
    // Setup real-time scheduling
    if (setup_realtime_scheduling() == -1) {
        fprintf(stderr, "WARNING: Could not set real-time scheduling. Running as normal priority.\n");
    }
    
    // Initialize MQTT
    if (mqtt_connect(&rt_context) == -1) {
        fprintf(stderr, "ERROR: Failed to connect to MQTT broker\n");
        return 1;
    }
    
    // Create RT control thread
    pthread_t rt_thread;
    pthread_create(&rt_thread, NULL, rt_control_loop, &rt_context);
    
    printf("\n[RT-Controller] System running. Waiting for sensor data...\n");
    printf("[RT-Controller] Rules active:\n");
    printf("  RULE 1: Soil moisture < 30%% -> Turn ON pump\n");
    printf("  RULE 2: Temperature > 30°C -> Open ventilation window\n");
    printf("  RULE 3: CO2 > 1500 ppm -> Trigger CRITICAL alarm\n\n");
    
    // Keep running until interrupted
    while (rt_context.running) {
        sleep(1);
    }
    
    rt_context.running = 0;
    pthread_join(rt_thread, NULL);
    
    printf("[RT-Controller] Shutting down gracefully.\n");
    return 0;
}
