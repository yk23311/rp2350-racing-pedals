#ifndef PEDAL_STORAGE_H
#define PEDAL_STORAGE_H
#include "pedal.h"
void storage_load(pedal_config_t *config);
bool storage_save(const pedal_config_t *config);
#endif
