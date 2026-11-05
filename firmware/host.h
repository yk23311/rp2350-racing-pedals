#ifndef PEDAL_HOST_H
#define PEDAL_HOST_H
#include "bridge.h"
#include <stdbool.h>
void host_init(void);
void host_task(void);
const bridge_t *host_bridge(void);
bool host_ready(void);
void host_rumble_receive(const uint8_t report[8]);
void host_rumble_enable(bool enabled);
void host_rumble_stop(void);
bool host_rumble_test(uint8_t left,uint8_t right,uint32_t duration_ms);
typedef struct {
    uint32_t received,sent,errors;
    uint8_t left,right;
    bool pending,in_flight,enabled,available,faulted,testing;
    uint32_t remaining_ms;
} host_rumble_status_t;
void host_rumble_status(host_rumble_status_t *status);
#endif
