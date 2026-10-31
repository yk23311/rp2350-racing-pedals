#ifndef PEDAL_HOST_H
#define PEDAL_HOST_H
#include "bridge.h"
#include <stdbool.h>
void host_init(void);
void host_task(void);
const bridge_t *host_bridge(void);
bool host_ready(void);
#endif
