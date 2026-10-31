#ifndef CONTROL_RECORD_H
#define CONTROL_RECORD_H
#include "control_profile.h"
#include <stddef.h>
#define CONTROL_RECORD_SIZE 256
/* Portable little-endian PDL2 record. Decoding also accepts 40-byte PDL1. */
bool control_record_encode(const pedal_config_t *pedal,const control_profile_t *profile,uint32_t sequence,uint8_t out[CONTROL_RECORD_SIZE]);
bool control_record_decode(const uint8_t *data,size_t size,pedal_config_t *pedal,control_profile_t *profile,uint32_t *sequence);
int control_record_select(const uint8_t *a,size_t na,const uint8_t *b,size_t nb,pedal_config_t *pedal,control_profile_t *profile,uint32_t *sequence);
#endif
