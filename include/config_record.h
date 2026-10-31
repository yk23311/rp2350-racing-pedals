#ifndef CONFIG_RECORD_H
#define CONFIG_RECORD_H
#include "pedal.h"
#include <stddef.h>
#define CONFIG_RECORD_SIZE 40
bool config_encode(const pedal_config_t *config,uint32_t sequence,uint8_t out[CONFIG_RECORD_SIZE]);
bool config_decode(const uint8_t *data,size_t size,pedal_config_t *config,uint32_t *sequence);
int config_select(const uint8_t *a,size_t na,const uint8_t *b,size_t nb,pedal_config_t *config,uint32_t *sequence);
#endif
